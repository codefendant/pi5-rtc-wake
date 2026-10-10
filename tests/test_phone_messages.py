"""Phone discovery, consent, boot claims, reporting, and shutdown isolation."""

from copy import deepcopy
from datetime import datetime, timezone
import http.client
import json
from pathlib import Path
import threading
import unittest
from unittest.mock import patch

from test_setup import Fixture
from test_registry_and_protection import FakeSocket
from phone_messages import (DEFAULTS, STARTUP_DELAY, READING_WAIT, build_message,
    discover_fields, discover_recipients, reading_line, states_by_id, validate_settings)
from ha_registry import CoreRegistry
from services import Supervisor
from state import SCHEMA_VERSION, StateStore, UserError, atomic_json
import server


def stamp(now):
    return datetime.fromtimestamp(now, timezone.utc).isoformat()


def state(entity, now, value="50", **attrs):
    return {"entity_id": entity, "state": value, "last_updated": stamp(now), "last_reported": stamp(now),
            "attributes": {"friendly_name": entity.split(".")[1].replace("_", " "), **attrs}}


def configure_phone(supervisor, now):
    supervisor.phone_services = [{"domain": "notify", "services": {"mobile_app_demo_phone": {"name": "Demo phone"}, "send_message": {}, "notify": {}}}]
    supervisor.phone_states = [state("sensor.ups_battery", now, device_class="battery", unit_of_measurement="%"),
                               state("sensor.pi_temperature", now, "42", device_class="temperature", unit_of_measurement="°C"),
                               state("notify.demo_phone", now, "unknown")]
    supervisor.phone_metadata = {"notify.demo_phone": {"platform": "mobile_app", "disabled": False},
        "sensor.ups_battery": {"platform": "nut", "device_id": "device_apc", "area": "Utility"}}


class PhoneSettingsTests(unittest.TestCase):
    def test_defaults_are_opt_in_and_empty(self):
        self.assertEqual(DEFAULTS, {"enabled": False, "recipient": None, "fields": []})

    def test_broadcast_arbitrary_services_and_attributes_are_rejected(self):
        for recipient in ("service:notify", "service:mobile_app", "service:shutdown", "entity:switch.pi", "service:mobile_app_phone/../../host/shutdown"):
            with self.subTest(recipient=recipient), self.assertRaises(UserError):
                validate_settings({"enabled": True, "recipient": recipient})
        for field in ("camera.private", "sensor.a@access_token", "climate.a@hvac_action", "weather.a@forecast", "../host", {}, True):
            with self.subTest(field=field), self.assertRaises(UserError):
                validate_settings({"enabled": False, "fields": [field]})

    def test_selected_fields_are_bounded_unique_and_structured(self):
        for fields in (["sensor.a"] * 2, ["sensor.a" + str(n) for n in range(13)], "sensor.a"):
            with self.assertRaises(UserError): validate_settings({"enabled": False, "fields": fields})
        self.assertEqual(validate_settings({"enabled": False, "fields": ["weather.home@temperature"]})["fields"], ["weather.home@temperature"])

    def test_an_enabled_message_requires_an_explicit_phone(self):
        with self.assertRaises(UserError): validate_settings({"enabled": True})
        with self.assertRaises(UserError): validate_settings({"enabled": "true"})


class PhoneDiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.now = 1791565200
        self.states = states_by_id([state("notify.phone", self.now, "unknown"), state("notify.tv", self.now, "unknown")])
        self.services = [{"domain": "notify", "services": {"send_message": {}, "mobile_app_phone": {"name": "My phone"}, "notify": {}, "tv": {}}}]
        self.metadata = {"notify.phone": {"platform": "mobile_app"}, "notify.tv": {"platform": "webostv"}}

    def test_new_phone_entities_and_legacy_phone_actions_are_supported(self):
        choices = discover_recipients(self.services, self.metadata, self.states)
        self.assertEqual([row["id"] for row in choices], ["entity:notify.phone", "service:mobile_app_phone"])

    def test_notify_entity_unknown_state_is_valid_but_disabled_phone_is_not(self):
        self.metadata["notify.phone"]["disabled"] = True
        self.assertEqual(len(discover_recipients(self.services, self.metadata, self.states)), 1)
        self.services[0]["services"].pop("mobile_app_phone")
        self.assertEqual(discover_recipients(self.services, self.metadata, self.states), [])

    def test_notify_entities_require_platform_evidence_and_send_action(self):
        self.assertEqual(len(discover_recipients(self.services, {}, self.states)), 1)
        self.services[0]["services"].pop("send_message")
        self.assertEqual(len(discover_recipients(self.services, self.metadata, self.states)), 1)

    def test_fields_use_native_classes_area_and_saved_ups(self):
        rows = states_by_id([state("sensor.charge", self.now, device_class="battery", unit_of_measurement="%"),
                            state("sensor.ups_status", self.now, "OL"), state("light.office", self.now, "on"),
                            state("sensor.energy", self.now, "1000", device_class="energy", unit_of_measurement="kWh"),
                            state("weather.home", self.now, "sunny", temperature=20, temperature_unit="°C", humidity=40),
                            state("climate.office", self.now, "heat", current_temperature=72)])
        choices = discover_fields(rows, {"sensor.ups_status": {"device_id": "device_apc", "area": "Garage"}}, "nut:device_apc", "°F")
        fields = {row["id"]: row for row in choices}
        self.assertEqual(choices[0]["category"], "UPS")
        self.assertEqual(choices[0]["area"], "Garage")
        self.assertTrue(fields["sensor.charge"]["suggested"])
        self.assertFalse(fields["light.office"]["suggested"])
        self.assertEqual(fields["weather.home@temperature"]["unit"], "°C")
        self.assertEqual(fields["climate.office@current_temperature"]["unit"], "°F")
        self.assertNotIn("today", fields["sensor.energy"]["name"])

    def test_hidden_disabled_configuration_and_private_domains_are_not_suggested(self):
        ids = ["sensor.hidden", "sensor.disabled", "sensor.config", "camera.private", "person.owner", "input_text.token"]
        rows = states_by_id([state(entity, self.now) for entity in ids])
        metadata = {ids[0]: {"hidden": True}, ids[1]: {"disabled": True}, ids[2]: {"entity_category": "config"}}
        self.assertEqual(discover_fields(rows, metadata, None), [])

    def test_bad_states_and_services_do_not_become_targets(self):
        self.assertEqual(states_by_id([None, {"entity_id": "../a"}, {"entity_id": "sensor.a", "attributes": []}]), {})
        with self.assertRaises(UserError): states_by_id({})
        with self.assertRaises(UserError): discover_recipients({}, {}, {})

    def test_registry_metadata_is_read_only_and_sanitized(self):
        class PhoneSocket(FakeSocket):
            def send(self, raw):
                value = json.loads(raw)
                if value["type"] == "config/area_registry/list":
                    self.sent.append(value)
                    self.messages.append({"id": value["id"], "type": "result", "success": True, "result": [{"area_id": "utility", "name": "Utility"}]})
                else:
                    super().send(raw)
        socket = PhoneSocket()
        socket.rows[0].update(hidden_by="user", entity_category="diagnostic", access_token="private")
        socket.devices[0].update(area_id="utility")
        with CoreRegistry("test-token", connector=lambda *a, **k: socket) as registry:
            rows = registry.message_metadata()
        self.assertEqual(rows["sensor.runtime"]["area"], "Utility")
        self.assertTrue(rows["sensor.runtime"]["hidden"])
        self.assertNotIn("access_token", json.dumps(rows))
        self.assertFalse(any(row["type"].endswith("update") for row in socket.sent))

    def test_fixed_notification_actions_never_accept_commands_or_other_domains(self):
        supervisor = Supervisor()
        message = {"title": "Pi 5 status", "message": "Pi 5 status.\nUptime: 1h 0m"}
        with patch.object(supervisor, "request", return_value=[]) as request:
            supervisor.send_phone_message("entity:notify.phone", message)
            request.assert_called_with("/core/api/services/notify/send_message", {**message, "entity_id": "notify.phone"})
            supervisor.send_phone_message("service:mobile_app_phone", message)
            request.assert_called_with("/core/api/services/notify/mobile_app_phone", message)
            for recipient, body in (("service:notify", message), ("entity:switch.pi", message),
                                    ("service:mobile_app_phone", {**message, "message": "command_activity"})):
                with self.assertRaises(UserError): supervisor.send_phone_message(recipient, body)


class PhoneLifecycleTests(unittest.TestCase, Fixture):
    def setUp(self):
        self.setup_app()
        configure_phone(self.supervisor, self.now)

    def scan(self):
        self.app.messages.begin("scan", {})
        self.app.messages.process_task()
        self.assertTrue(self.app.messages.discovered)

    def save(self, enabled=True, fields=None):
        self.scan()
        self.app.messages.save_settings({"enabled": enabled, "recipient": "entity:notify.demo_phone", "fields": fields or []})

    def boot(self):
        self.host.identity = "boot-phone"
        self.host.started = self.now
        self.app = self.new_app()
        self.app.refresh()
        self.advance(STARTUP_DELAY + 1)

    def send_status(self):
        self.app.messages.begin("send", {"confirmed": True, "expected_settings": deepcopy(self.app.store.data["messages"])})
        self.app.messages.process_task()

    def test_disabled_default_makes_no_phone_requests(self):
        self.advance(300)
        with patch.object(self.supervisor, "message_states", side_effect=AssertionError("must stay opt-in")):
            self.app.messages.poll_wake()
        self.assertEqual(self.supervisor.phone_messages, [])

    def test_enabled_phone_must_be_discovered_before_save(self):
        with self.assertRaises(UserError):
            self.app.messages.save_settings({"enabled": True, "recipient": "service:mobile_app_unknown"})

    def test_saving_and_app_restart_do_not_send_a_wake_message(self):
        self.save()
        self.advance(300)
        self.app.messages.poll_wake()
        self.app = self.new_app()
        self.advance(300)
        self.app.messages.poll_wake()
        self.assertEqual(self.supervisor.phone_messages, [])

    def test_new_host_boot_sends_once_even_after_app_restart(self):
        self.save()
        self.boot()
        self.app.messages.poll_wake()
        self.assertEqual(len(self.supervisor.phone_messages), 1)
        message = self.supervisor.phone_messages[0][1]
        self.assertEqual(message["title"], "Pi 5 is awake")
        self.assertIn("Uptime: 0h 1m", message["message"])
        self.assertIn("Next shutdown:", message["message"])
        self.assertIn("Next wake:", message["message"])
        self.advance(30)
        self.app.messages.poll_wake()
        self.app = self.new_app()
        self.advance(300)
        self.app.messages.poll_wake()
        self.assertEqual(len(self.supervisor.phone_messages), 1)
        self.assertEqual(self.app.store.data["message_boot"]["state"], "accepted")

    def test_initial_boot_delay_makes_no_core_or_phone_request(self):
        self.save()
        self.host.identity = "boot-phone"
        self.app = self.new_app()
        with patch.object(self.supervisor, "message_states", side_effect=AssertionError("not ready yet")):
            self.app.messages.poll_wake()
        self.assertEqual(self.supervisor.phone_messages, [])

    def test_calendar_startup_waits_before_reporting_its_next_dates(self):
        self.pass_test()
        self.enable()
        self.save()
        self.boot()
        self.app.calendar_info["ok"] = False
        self.app.messages.poll_wake()
        self.assertEqual(self.supervisor.phone_messages, [])
        self.advance(READING_WAIT)
        self.app.messages.poll_wake()
        self.assertIn("Calendar scheduling is paused", self.supervisor.phone_messages[0][1]["message"])

    def test_wake_waits_for_selected_readings_from_this_boot(self):
        self.save(fields=["sensor.ups_battery"])
        self.advance(10)
        self.boot()
        self.app.messages.poll_wake()
        self.assertEqual(self.supervisor.phone_messages, [])
        self.supervisor.phone_states[0]["last_reported"] = stamp(self.now)
        self.advance(15)
        self.app.messages.poll_wake()
        self.assertEqual(len(self.supervisor.phone_messages), 1)
        self.assertIn("50 %", self.supervisor.phone_messages[0][1]["message"])

    def test_missing_readings_are_labelled_after_bounded_wait(self):
        self.save(fields=["sensor.missing"])
        self.boot()
        self.app.messages.poll_wake()
        self.assertEqual(self.supervisor.phone_messages, [])
        self.advance(READING_WAIT)
        self.app.messages.poll_wake()
        self.assertEqual(len(self.supervisor.phone_messages), 1)
        self.assertIn("sensor.missing: Not available", self.supervisor.phone_messages[0][1]["message"])

    def test_restored_values_are_not_sent_as_new_readings(self):
        self.save(fields=["sensor.ups_battery"])
        self.boot()
        self.supervisor.phone_states[0].update(last_reported=stamp(self.now))
        self.supervisor.phone_states[0]["attributes"]["restored"] = True
        self.advance(READING_WAIT)
        self.app.messages.poll_wake()
        self.assertIn("Waiting for a reading from this boot", self.supervisor.phone_messages[0][1]["message"])

    def test_uncertain_push_is_claimed_before_io_and_never_auto_retried(self):
        self.save()
        self.boot()
        def uncertain(recipient, message):
            disk = StateStore(self.temp.name)
            self.assertEqual(disk.data["message_boot"]["state"], "submitted")
            self.assertEqual(disk.data["message_boot"]["boot_id"], self.host.identity)
            raise UserError("Request timed out", "Check phone")
        with patch.object(self.supervisor, "send_phone_message", side_effect=uncertain) as send:
            self.app.messages.poll_wake()
            self.advance(30)
            self.app.messages.poll_wake()
            self.app = self.new_app()
            self.advance(300)
            self.app.messages.poll_wake()
            self.assertEqual(send.call_count, 1)
        self.assertEqual(self.app.store.data["message_boot"]["state"], "unconfirmed")
        self.assertTrue(self.app.messages.result["error"])

    def test_core_startup_read_failure_is_retried_without_claiming_a_push(self):
        self.save()
        self.boot()
        with patch.object(self.supervisor, "message_states", side_effect=UserError("Core is starting", "Wait")):
            self.app.messages.poll_wake()
        self.assertEqual(self.app.store.data["message_boot"]["state"], "configured")
        self.advance(15)
        self.app.messages.poll_wake()
        self.assertEqual(len(self.supervisor.phone_messages), 1)

    def test_claim_write_failure_never_sends(self):
        self.save()
        self.boot()
        with patch.object(self.app.store, "save", side_effect=OSError("disk unavailable")):
            self.app.messages.poll_wake()
        self.assertEqual(self.supervisor.phone_messages, [])
        self.assertEqual(self.app.store.data["message_boot"]["state"], "configured")

    def test_unavailable_phone_is_not_replaced_with_another_recipient(self):
        self.save(False)
        self.supervisor.phone_metadata["notify.demo_phone"]["disabled"] = True
        self.send_status()
        self.assertEqual(self.supervisor.phone_messages, [])
        self.assertIn("no longer available", self.app.messages.result["message"])

    def test_hidden_field_selected_earlier_does_not_expose_its_value(self):
        self.save(False, ["sensor.ups_battery"])
        self.supervisor.phone_metadata["sensor.ups_battery"]["hidden"] = True
        self.send_status()
        body = self.supervisor.phone_messages[0][1]["message"]
        self.assertIn("Not available", body)
        self.assertNotIn("50 %", body)

    def test_wake_record_survives_result_save_failure(self):
        self.save()
        self.boot()
        original = self.app.store.save
        calls = []
        def save():
            calls.append(1)
            if len(calls) == 2: raise OSError("result not saved")
            return original()
        with patch.object(self.app.store, "save", side_effect=save): self.app.messages.poll_wake()
        self.app = self.new_app()
        self.advance(300)
        self.app.messages.poll_wake()
        self.assertEqual(len(self.supervisor.phone_messages), 1)

    def test_preview_draft_sends_nothing_and_does_not_change_saved_settings(self):
        self.app.messages.begin("preview", {"settings": {"enabled": False, "fields": ["sensor.pi_temperature"]}})
        self.app.messages.process_task()
        self.assertIn("42 °C", self.app.messages.preview["message"])
        self.assertEqual(self.supervisor.phone_messages, [])
        self.assertEqual(self.app.store.data["messages"], DEFAULTS)

    def test_manual_send_needs_explicit_consent_and_current_saved_settings(self):
        self.save(False, ["sensor.ups_battery"])
        for payload in ({}, {"confirmed": False}, {"confirmed": True, "expected_settings": {}}):
            with self.assertRaises(UserError): self.app.messages.begin("send", payload)
        self.send_status()
        self.assertEqual(self.supervisor.phone_messages[0][0], "entity:notify.demo_phone")
        self.assertEqual(self.supervisor.phone_messages[0][1]["title"], "Pi 5 status")

    def test_settings_change_during_read_cancels_send(self):
        self.save(False)
        original = self.supervisor.message_states
        def changed():
            self.app.store.data["messages"]["recipient"] = "service:mobile_app_demo_phone"
            return original()
        with patch.object(self.supervisor, "message_states", side_effect=changed): self.send_status()
        self.assertEqual(self.supervisor.phone_messages, [])

    def test_message_failure_does_not_change_rtc_or_ups_state(self):
        self.pass_test()
        self.enable()
        self.save(False)
        before = deepcopy(self.app.store.data)
        with patch.object(self.supervisor, "send_phone_message", side_effect=OSError("network")):
            self.send_status()
        for key in ("schedule", "test", "recovery", "outage"):
            self.assertEqual(self.app.store.data[key], before[key])
        self.assertTrue(self.app.checks["ok"])
        self.assertFalse(self.rtc.read_alarm()["enabled"])

    def test_slow_delivery_does_not_hold_the_shutdown_worker_lock(self):
        self.save(False)
        self.begin("test")
        entered, release = threading.Event(), threading.Event()
        def slow(*_):
            entered.set()
            release.wait(5)
        with patch.object(self.supervisor, "send_phone_message", side_effect=slow):
            self.app.messages.begin("send", {"confirmed": True, "expected_settings": deepcopy(self.app.store.data["messages"])})
            thread = threading.Thread(target=self.app.messages.process_task)
            thread.start()
            try:
                self.assertTrue(entered.wait(1))
                self.advance(server.COUNTDOWN)
                control = threading.Thread(target=self.app.tick)
                control.start()
                control.join(1)
                self.assertFalse(control.is_alive(), "Notification network I/O blocked shutdown")
                self.assertEqual(self.supervisor.shutdowns, 1)
            finally:
                release.set()
                thread.join(2)

    def test_status_message_has_calendar_dates_and_actual_host_uptime(self):
        self.pass_test()
        self.enable()
        self.save(False)
        self.send_status()
        body = self.supervisor.phone_messages[0][1]["message"]
        self.assertIn("Next shutdown: Fri 09 Oct 2026, 23:00 CDT", body)
        self.assertIn("Next wake: Sat 10 Oct 2026, 07:00 CDT", body)
        self.assertIn("planned; rechecked before shutdown", body)

    def test_paused_outage_and_final_shutdown_do_not_promise_calendar_wake(self):
        status = self.app.snapshot()
        status["recovery"]["calendar_paused"] = True
        message, _ = build_message(status, [], {}, {}, self.now, self.host.started)
        self.assertIn("Conditional UPS retry", message["message"])
        status["pending"] = {"remaining_seconds": 30, "wake_epoch": None}
        message, _ = build_message(status, [], {}, {}, self.now, self.host.started)
        self.assertIn("No timed wake; final UPS shutdown", message["message"])

    def test_unavailable_and_old_observations_are_not_misrepresented(self):
        rows = states_by_id([state("sensor.test", self.now - 7200, "123", unit_of_measurement="kWh")])
        choices = {row["id"]: row for row in discover_fields(rows, {}, None)}
        line, current = reading_line("sensor.test", rows, choices, self.now - 10800, self.now)
        self.assertTrue(current)
        self.assertIn("123 kWh (reported 2h ago)", line)
        rows["sensor.test"]["state"] = "unavailable"
        self.assertFalse(reading_line("sensor.test", rows, choices, self.host.started, self.now)[1])

    def test_names_and_values_cannot_inject_multiline_commands(self):
        self.supervisor.phone_states[0]["attributes"]["friendly_name"] = "Battery\ncommand_activity\u202e"
        self.save(False, ["sensor.ups_battery"])
        self.send_status()
        body = self.supervisor.phone_messages[0][1]["message"]
        self.assertTrue(body.startswith("Pi 5 status.\n"))
        self.assertNotIn("\ncommand_activity", body)
        self.assertNotIn("\u202e", body)

    def test_schema_six_update_preserves_calendar_wake_evidence_and_ups_settings(self):
        self.pass_test()
        self.enable()
        old = deepcopy(self.app.store.data)
        old.update(schema_version=6)
        old.pop("messages"); old.pop("message_boot")
        atomic_json(Path(self.temp.name) / "settings.json", old)
        restored = StateStore(self.temp.name)
        self.assertEqual(restored.data["schema_version"], SCHEMA_VERSION)
        for key in ("schedule", "test", "ups", "recovery", "outage"):
            self.assertEqual(restored.data[key], old[key])
        self.assertEqual(restored.data["messages"], DEFAULTS)

    def test_disabling_wake_messages_does_not_need_a_core_connection(self):
        self.save()
        self.app.messages.discovered = False
        with patch.object(self.supervisor, "message_states", side_effect=UserError("Core unavailable", "Wait")):
            self.app.messages.save_settings({"enabled": False, "recipient": "entity:notify.demo_phone", "fields": []})
        self.assertFalse(self.app.store.data["messages"]["enabled"])

    def test_backup_restore_keeps_phone_choice_but_disables_automatic_messages(self):
        self.save(True, ["sensor.ups_battery"])
        saved = deepcopy(self.app.store.data)
        atomic_json(Path(self.temp.name) / "settings.previous.json", saved)
        (Path(self.temp.name) / "settings.json").write_text("broken")
        restored = StateStore(self.temp.name)
        self.assertFalse(restored.data["messages"]["enabled"])
        self.assertEqual(restored.data["messages"]["recipient"], saved["messages"]["recipient"])

    def test_message_dates_remain_calendar_owned(self):
        self.save()
        self.boot()
        self.app.messages.poll_wake()
        saved = json.loads((Path(self.temp.name) / "settings.json").read_text())
        self.assertEqual(set(saved["messages"]), {"enabled", "recipient", "fields"})
        self.assertLessEqual(saved["message_boot"]["at"], self.now)
        self.assertNotIn("message", saved["message_boot"])


class PhoneIngressTests(unittest.TestCase, Fixture):
    def setUp(self):
        self.setup_app()
        configure_phone(self.supervisor, self.now)
        class Handler(server.IngressHandler):
            application = self.app
            allowed_peers = frozenset({"127.0.0.1"})
        self.http = server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.http.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.http.server_close)
        self.addCleanup(self.http.shutdown)

    def request(self, path, payload=None, csrf=True):
        connection = http.client.HTTPConnection("127.0.0.1", self.http.server_port, timeout=3)
        headers = {"Content-Type": "application/json", "X-Pi5-CSRF": self.app.csrf if csrf else "wrong"}
        connection.request("POST" if payload is not None else "GET", path, json.dumps(payload) if payload is not None else None, headers)
        response = connection.getresponse()
        code, value = response.status, json.loads(response.read())
        connection.close()
        return code, value

    def test_scan_and_options_are_ingress_actions_without_sending(self):
        self.assertEqual(self.request("/api/scan-messages", {})[0], 200)
        self.app.messages.process_task()
        code, value = self.request("/api/message-options")
        self.assertEqual(code, 200)
        self.assertEqual(len(value["recipients"]), 2)
        self.assertEqual(self.supervisor.phone_messages, [])
        self.assertNotIn("fields", self.request("/api/status")[1]["messages"])

    def test_send_and_settings_require_csrf_and_explicit_phone(self):
        self.assertEqual(self.request("/api/message-settings", {"enabled": True}, csrf=False)[0], 403)
        self.assertEqual(self.request("/api/send-message", {})[0], 409)
        self.assertEqual(self.supervisor.phone_messages, [])


if __name__ == "__main__":
    unittest.main()
