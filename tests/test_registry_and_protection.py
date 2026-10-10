"""Regression boundaries for registry changes and independent emergency stops."""

from copy import deepcopy
import http.client
import json
import threading
import unittest
from unittest.mock import patch

import test_ups_recovery as recovery_fixture
from test_setup import Fixture
from test_power_sources import nut_rows, stamp
from ha_registry import CoreRegistry
from power_sources import discover_sources
from services import Supervisor
from state import StateStore, UserError, atomic_json
from ups_recovery import DEFAULTS, retry_requirements, validate_policy, validate_session
import server


class FakeSocket:
    def __init__(self):
        self.messages = [{"type": "auth_required"}]
        self.sent = []
        self.closed = False
        self.rows = [self.sensor("device_apc", "sensor.runtime", "nut", "integration"),
                     self.sensor("device_other", "sensor.other", "nut", "user"),
                     self.sensor("device_apc", "sensor.unrelated", "mqtt", "integration")]
        self.devices = [{"id": "device_apc", "name": "APC UPS", "disabled_by": None}]
        self.reply_override = None

    @staticmethod
    def sensor(device, entity, platform, disabled):
        return {"entity_id": entity, "device_id": device, "platform": platform, "disabled_by": disabled,
                "name": "Renamed runtime", "unique_id": "unique_battery.runtime"}

    def settimeout(self, seconds): pass
    def close(self, **_): self.closed = True
    def recv(self): return json.dumps(self.messages.pop(0))
    def send(self, text):
        value = json.loads(text)
        self.sent.append(value)
        if value["type"] == "auth":
            self.messages.append({"type": "auth_ok"})
            return
        kind = value["type"]
        result = self.rows if kind == "config/entity_registry/list" else self.devices if kind == "config/device_registry/list" else deepcopy(next(row for row in self.rows if row["entity_id"] == value["entity_id"]))
        if kind == "config/entity_registry/update":
            result.update(disabled_by=None)
            result = {"entity_entry": result, "reload_delay": 30}
        reply = {"id": value["id"], "type": "result", "success": True, "result": result}
        self.messages.append(self.reply_override or reply)


class RegistryTests(unittest.TestCase):
    def session(self, socket): return CoreRegistry("private-supervisor-token", connector=lambda *a, **k: socket)

    def test_native_registry_includes_disabled_sensors_and_ignores_other_integrations(self):
        socket = FakeSocket()
        with self.session(socket) as registry: rows = registry.nut_sensors()
        self.assertEqual([row["entity_id"] for row in rows], ["sensor.runtime", "sensor.other"])
        self.assertTrue(rows[0]["can_enable"])
        self.assertTrue(rows[0]["runtime_measurement"])
        self.assertEqual(rows[0]["device_name"], "APC UPS")
        self.assertTrue(socket.closed)

    def test_registry_entities_without_a_string_device_identity_are_ignored(self):
        socket = FakeSocket()
        socket.rows.extend([socket.sensor(None, "sensor.no_device", "nut", "integration"),
                            socket.sensor(123, "sensor.invalid_device", "nut", "integration")])
        with self.session(socket) as registry: rows = registry.nut_sensors()
        self.assertEqual([row["entity_id"] for row in rows], ["sensor.runtime", "sensor.other"])

    def test_enable_is_fixed_update_and_read_back_confirmation(self):
        socket = FakeSocket()
        with self.session(socket) as registry: result = registry.enable_nut_sensor("device_apc", "sensor.runtime")
        self.assertEqual(result["reload_delay"], 30)
        update = socket.sent[-1]
        self.assertEqual(update, {"id": 2, "type": "config/entity_registry/update", "entity_id": "sensor.runtime", "disabled_by": None})

    def test_wrong_device_or_platform_cannot_be_enabled(self):
        for device, entity in (("device_apc", "sensor.other"), ("device_apc", "sensor.unrelated")):
            socket = FakeSocket()
            with self.session(socket) as registry, self.assertRaises(UserError): registry.enable_nut_sensor(device, entity)
            self.assertFalse(any(row["type"].endswith("/update") for row in socket.sent))

    def test_disabled_device_and_config_entry_are_not_overridden(self):
        for reason in ("device", "config_entry"):
            socket = FakeSocket(); socket.rows[0]["disabled_by"] = reason
            with self.session(socket) as registry, self.assertRaises(UserError): registry.enable_nut_sensor("device_apc", "sensor.runtime")

    def test_already_enabled_sensor_is_not_written_again(self):
        socket = FakeSocket(); socket.rows[0]["disabled_by"] = None
        with self.session(socket) as registry: result = registry.enable_nut_sensor("device_apc", "sensor.runtime")
        self.assertTrue(result["already_enabled"])
        self.assertEqual(len(socket.sent), 2)

    def test_ambiguous_or_denied_response_is_not_retried_or_exposed(self):
        socket = FakeSocket()
        socket.reply_override = {"id": 1, "type": "result", "success": False, "error": {"message": "private-server-details"}}
        with self.session(socket) as registry:
            with self.assertRaises(UserError) as error: registry.nut_sensors()
        self.assertNotIn("private", str(error.exception))
        self.assertEqual(len(socket.sent), 2)

    def test_authentication_uses_only_internal_fixed_proxy(self):
        socket = FakeSocket()
        with patch("ha_registry.time.monotonic", return_value=100), patch.object(socket, "send", wraps=socket.send):
            connector = unittest.mock.Mock(return_value=socket)
            with CoreRegistry("private-token", connector=connector): pass
        self.assertEqual(connector.call_args.args, ("ws://supervisor/core/websocket",))
        self.assertEqual(socket.sent[0], {"type": "auth", "access_token": "private-token"})

    def test_arbitrary_command_and_entity_paths_are_rejected(self):
        socket = FakeSocket()
        with self.session(socket) as registry:
            with self.assertRaises(ValueError): registry.command("call_service", domain="hassio")
            with self.assertRaises(UserError): registry.enable_nut_sensor("device_apc", "sensor.bad/../route")
        self.assertEqual(len(socket.sent), 1)

    def test_closed_socket_or_bad_auth_produces_plain_action(self):
        socket = FakeSocket(); socket.messages = [{"type": "auth_invalid", "message": "private-token"}]
        with self.assertRaises(UserError) as error:
            with self.session(socket): pass
        self.assertNotIn("private-token", str(error.exception))
        self.assertTrue(socket.closed)

    def test_nut_saved_options_are_sanitized_and_no_options_are_changed(self):
        supervisor = Supervisor()
        for setting, state in ((True, "conflict"), ("true", "conflict"), (False, "ready"), ("false", "ready"), (1, "review"), (None, "review")):
            with self.subTest(setting=setting), patch.object(supervisor, "request", side_effect=[{"addons": [{"slug": "a0d7b954_nut"}]}, {"state": "started", "options": {"shutdown_host": setting, "password": "private-password"}}]) as request:
                result = supervisor.shutdown_controller()
                self.assertEqual(result["state"], state)
                self.assertNotIn("private-password", json.dumps(result))
                self.assertTrue(all(len(call.args) == 1 for call in request.call_args_list))

    def test_stopped_nut_is_not_claimed_as_coordinated(self):
        with patch.object(Supervisor, "request", side_effect=[{"addons": [{"slug": "a0d7b954_nut"}]}, {"state": "stopped", "options": {"shutdown_host": False}}]):
            self.assertEqual(Supervisor().shutdown_controller()["state"], "review")


class StatusAndReserveTests(unittest.TestCase):
    def test_ol_test_and_auxiliary_flags_keep_the_ups_discovered(self):
        now = 1791586800
        for status in ("OL TEST", "OL CAL TEST", "OL VENDOR_FLAG", "OB TEST DISCHRG"):
            with self.subTest(status=status):
                sources, _ = discover_sources(nut_rows(now, status), now)
                self.assertEqual(len(sources), 1)
                self.assertEqual(sources[0]["power_state"], "battery" if status.startswith("OB") else "mains")

    def test_conflicting_flags_remain_unknown_and_untrusted_text_is_not_raw_status(self):
        now = 1791586800
        self.assertFalse(discover_sources(nut_rows(now, "OL OB TEST"), now)[0][0]["ok"])
        for status in ("Online TEST", "OL invalid", "OL " + "X" * 150):
            self.assertEqual(discover_sources(nut_rows(now, status), now)[0], [])

    def test_requirements_describe_each_conditional_decision(self):
        self.assertEqual([row["minimum_runtime_minutes"] for row in retry_requirements(DEFAULTS)], [24, 39, 69])
        rows = retry_requirements({**DEFAULTS, "max_retries": 4, "max_retry_minutes": 30})
        self.assertEqual([row["interval_minutes"] for row in rows], [15, 30, 30, 30])

    def test_enabled_policy_requires_a_protection_action(self):
        with self.assertRaises(UserError):
            validate_policy({**DEFAULTS, "enabled": True, "retry_enabled": False, "emergency_enabled": False,
                             "final_shutdown_confirmed": True})


class ProtectionRegressionTests(unittest.TestCase, Fixture):
    setUp = recovery_fixture.RecoveryTests.setUp
    reading = recovery_fixture.RecoveryTests.reading
    start = recovery_fixture.RecoveryTests.start
    finish = recovery_fixture.RecoveryTests.finish
    reboot = recovery_fixture.RecoveryTests.reboot

    def test_cancelled_retry_does_not_cancel_later_hardware_low_battery(self):
        self.start(); self.app.cancel()
        self.reading("battery", 6000, low_battery=True)
        self.app.tick(); self.app.process_task()
        self.assertTrue(self.app.pending["emergency"])
        self.assertFalse(self.app.pending["retry"])
        self.assertEqual(self.app.store.data["outage"]["attempts"], 1)

    def test_failed_rtc_io_does_not_block_emergency_host_request(self):
        self.reading("battery", 7200); self.app.tick()
        with patch.object(self.host, "inspect", side_effect=OSError("RTC unavailable")):
            self.app.refresh()
        self.assertFalse(self.app.checks["ok"])
        self.reading("battery", 60)
        with patch.object(self.app.controller, "status", side_effect=OSError("RTC unavailable")) as status, patch.object(self.app.controller, "arm") as arm:
            self.app.tick(); self.app.process_task(); self.app.tick()
        status.assert_not_called(); arm.assert_not_called()
        self.assertEqual(self.supervisor.shutdowns, 2)

    def test_calendar_failure_and_cancel_do_not_block_emergency(self):
        self.start(); self.app.cancel()
        self.reading("battery", 60)
        with patch.object(self.supervisor, "calendar_events", side_effect=UserError("Offline", "Retry")):
            self.app.tick(); self.app.process_task(); self.app.tick()
        self.assertEqual(self.supervisor.shutdowns, 2)

    def test_separate_explicit_disable_of_emergency_is_required_and_respected(self):
        self.reading("battery", 7200); self.app.tick(); self.app.recovery.pause_retries()
        value = {**self.policy, "emergency_enabled": False}
        with self.assertRaises(UserError): self.app.recovery.save_settings(value)
        self.app.recovery.save_settings({**value, "confirmed_disable_emergency": True})
        self.reading("battery", 60, low_battery=True)
        self.app.tick()
        self.assertIsNone(self.app.job)
        self.assertFalse(self.app.snapshot()["recovery"]["emergency_active"])

    def test_pause_retries_before_countdown_keeps_protection_active(self):
        self.reading("battery", 7200); self.app.tick()
        self.app.recovery.pause_retries()
        self.reading("battery", 1800); self.app.tick()
        self.assertIsNone(self.app.job)
        self.reading("battery", 200); self.app.tick(); self.app.process_task()
        self.assertTrue(self.app.pending["emergency"])

    def test_five_minute_emergency_threshold_is_distinct_from_normal_retry_threshold(self):
        self.reading("battery", 7200); self.app.tick(); self.app.recovery.pause_retries()
        self.reading("battery", 301); self.app.tick()
        self.assertIsNone(self.app.job)
        self.advance(2); self.app.tick(); self.app.process_task()
        self.assertTrue(self.app.pending["emergency"])

    def test_aging_reading_does_not_freeze_estimated_reserve(self):
        self.reading("battery", 7200); self.app.tick(); self.app.recovery.pause_retries()
        self.reading("battery", 350); self.app.tick()
        self.advance(51); self.app.tick(); self.app.process_task()
        self.assertTrue(self.app.pending["emergency"])

    def test_known_low_reserve_caps_lost_reading_wait_after_app_restart(self):
        self.reading("battery", 7200); self.app.tick(); self.app.recovery.pause_retries()
        self.reading("battery", 350); self.app.tick()
        self.advance(291)
        self.app = self.new_app()
        self.reading("unknown", None); self.app.refresh()
        with patch.object(self.supervisor, "create_power_event") as create:
            self.app.tick(); self.app.process_task()
        create.assert_not_called()
        self.assertTrue(self.app.pending["emergency"])
        self.assertTrue(self.app.pending["urgent"])
        self.app.tick()
        self.assertEqual(self.supervisor.shutdowns, 2)

    def test_fresh_low_battery_does_not_wait_for_a_missing_runtime_sensor(self):
        for updates in ({"low_battery": True}, {"battery": 19}):
            with self.subTest(updates=updates):
                self.setUp()
                self.reading("battery", None, **updates)
                self.app.tick(); self.app.process_task()
                self.assertTrue(self.app.pending["emergency"])
                self.assertFalse(self.app.pending["retry"])
                self.finish()
                self.assertEqual(self.supervisor.shutdowns, 2)

    def test_emergency_only_does_not_block_normal_calendar_on_utility(self):
        self.app.recovery.save_settings({**self.policy, "retry_enabled": False,
                                        "shutdown_runtime_minutes": 5, "emergency_runtime_minutes": 10})
        self.app.tick()
        self.assertTrue(self.app.snapshot()["schedule_active"])
        self.assertFalse(self.app.snapshot()["recovery"]["calendar_paused"])
        self.assertIn("Emergency low-battery protection is enabled", self.app.message["text"])

    def test_missing_data_after_cancel_still_uses_known_outage_emergency_fallback(self):
        self.start(); self.app.cancel()
        self.reading("unknown", None); self.app.tick()
        self.advance(180); self.reading("unknown", None)
        self.app.tick(); self.app.process_task()
        self.assertTrue(self.app.pending["emergency"])

    def test_nut_controller_conflict_blocks_requalification(self):
        self.supervisor.shutdown_owner["state"] = "conflict"
        with self.assertRaises(UserError): self.app.recovery.save_settings(self.policy)
        self.assertFalse(self.app.recovery.eligible())
        self.assertTrue(self.app.recovery.protection_eligible())

    def test_controller_change_before_retry_submission_cancels_alarm_and_keeps_emergency(self):
        self.start()
        self.supervisor.shutdown_owner["state"] = "conflict"
        self.app.refresh_nut_settings(sensors=False)
        self.finish()
        self.assertEqual(self.supervisor.shutdowns, 1)
        self.assertFalse(self.rtc.enabled)
        self.reading("battery", 60); self.app.tick(); self.app.process_task(); self.app.tick()
        self.assertEqual(self.supervisor.shutdowns, 2)

    def test_source_identity_change_is_not_authorized_by_old_confirmation(self):
        self.reading("battery", 60, provider="A different controller")
        self.app.tick()
        self.assertFalse(self.app.recovery.protection_eligible())
        self.assertIsNone(self.app.job)

    def test_source_cannot_be_switched_during_known_outage(self):
        self.reading("battery", 7200); self.app.tick()
        with self.assertRaises(UserError): self.app.save_power_settings({"source_id": None, "notifications": False, "low_battery_percent": 25})
        self.assertTrue(self.app.recovery.protection_eligible())

    def test_emergency_only_policy_does_not_need_working_rtc_or_calendar(self):
        self.app.recovery.save_settings({**self.policy, "enabled": False, "confirmed_disable_emergency": True})
        self.app.save_settings({"enabled": False, "timezone": "UTC", "source": "calendar", "calendar_entity_id": None})
        self.host.config = self.host.config.replace("POWER_OFF_ON_HALT=1", "POWER_OFF_ON_HALT=0")
        self.app.refresh()
        self.app.recovery.save_settings({**self.policy, "retry_enabled": False, "expected_calendar_entity_id": None})
        restored = StateStore(self.temp.name)
        self.assertTrue(restored.data["recovery"]["enabled"])
        self.reading("battery", 1800); self.app.tick()
        self.assertIsNone(self.app.job)
        self.reading("battery", 60); self.app.tick(); self.app.process_task(); self.app.tick()
        self.assertEqual(self.supervisor.shutdowns, 2)

    def test_schema_five_update_preserves_settings_but_requires_ownership_review(self):
        old = deepcopy(self.app.store.data); old["schema_version"] = 5
        for key in ("owner_confirmed", "emergency_enabled", "retry_enabled", "emergency_runtime_minutes"): old["recovery"].pop(key)
        atomic_json(self.app.store.path, old)
        self.app = self.new_app(); self.app.refresh()
        self.assertFalse(self.app.store.read_only)
        self.assertTrue(self.app.store.data["recovery"]["enabled"])
        self.assertFalse(self.app.recovery.protection_eligible())
        self.assertEqual(self.app.store.data["schedule"], old["schedule"])
        self.assertEqual(self.app.store.data["test"], old["test"])
        self.app.store.save()
        self.assertFalse(StateStore(self.temp.name).read_only)

    def test_invalid_past_reserve_metadata_is_not_accepted(self):
        self.reading("battery", 7200); self.app.tick()
        session = deepcopy(self.app.store.data["outage"])
        for updates in ({"last_runtime_seconds": float("inf")}, {"last_runtime_epoch": True}):
            with self.subTest(updates=updates), self.assertRaises(UserError): validate_session({**session, **updates})
        session.pop("last_runtime_epoch")
        with self.assertRaises(UserError): validate_session(session)

    def test_fsd_without_power_or_runtime_reading_requests_immediate_emergency_stop(self):
        rows = nut_rows(self.now)
        rows["rows"].append({**rows["rows"][0], "entity_id": "sensor.runtime", "state": "7200",
                              "attributes": {"device_class": "duration", "unit_of_measurement": "s"}})
        self.supervisor.power_rows = rows; self.app.refresh_power()
        self.app.save_power_settings({"source_id": "nut:device_apc", "notifications": False, "low_battery_percent": 25})
        self.app.recovery.save_settings({**self.policy, "expected_source_id": "nut:device_apc", "runtime_entity_id": "sensor.runtime"})
        self.supervisor.power_rows = nut_rows(self.now, "FSD")
        self.app.refresh_power(); self.app.tick(); self.app.process_task()
        self.assertTrue(self.app.pending["urgent"])
        self.assertFalse(self.app.pending["retry"])
        self.app.tick()
        self.assertEqual(self.supervisor.shutdowns, 2)


class RegistryHTTPTests(unittest.TestCase, Fixture):
    def setUp(self):
        self.setup_app()
        self.supervisor.power_rows = nut_rows(self.now)
        self.supervisor.sensor_registry = [{"entity_id": "sensor.runtime", "device_id": "device_apc", "name": "Battery runtime", "disabled_by": "integration", "can_enable": True, "runtime_measurement": True}]
        self.app.refresh_power(settings=True)
        self.app.save_power_settings({"source_id": "nut:device_apc", "notifications": False, "low_battery_percent": 25})
        app = self.app
        class Handler(server.IngressHandler):
            application = app
            allowed_peers = frozenset({"127.0.0.1"})
        self.http = server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=self.http.serve_forever, daemon=True).start()
        self.addCleanup(self.http.server_close); self.addCleanup(self.http.shutdown)

    def post(self, path, value, valid=True):
        conn = http.client.HTTPConnection("127.0.0.1", self.http.server_port, timeout=3)
        try:
            conn.request("POST", "/api/" + path, json.dumps(value), {"Content-Type": "application/json", "X-Pi5-CSRF": self.app.csrf if valid else "wrong"})
            response = conn.getresponse(); response.read(); return response.status
        finally: conn.close()

    def test_sensor_enable_requires_csrf_and_saved_source_binding(self):
        value = {"confirmed": True, "expected_source_id": "nut:device_apc", "entity_id": "sensor.runtime"}
        self.assertEqual(self.post("enable-nut-sensor", value, False), 403)
        self.assertEqual(self.supervisor.enabled_sensors, [])
        self.assertEqual(self.post("enable-nut-sensor", {**value, "expected_source_id": "nut:other"}), 409)
        self.assertEqual(self.post("enable-nut-sensor", value), 200)
        self.assertEqual(self.supervisor.enabled_sensors, ["sensor.runtime"])

    def test_sensor_enable_on_battery_is_blocked_without_a_registry_write(self):
        self.supervisor.power_rows = nut_rows(self.now, "OB")
        self.app.refresh_power()
        self.assertEqual(self.post("enable-nut-sensor", {"confirmed": True, "expected_source_id": "nut:device_apc", "entity_id": "sensor.runtime"}), 409)
        self.assertEqual(self.supervisor.enabled_sensors, [])

    def test_disabled_status_sensor_can_be_selected_and_enabled_without_guessing_a_reading(self):
        self.supervisor.power_rows = {"rows": []}
        self.app.refresh_power()
        source = self.app.snapshot()["ups"]["selected"]
        self.assertEqual(source["power_state"], "unknown")
        self.assertFalse(source["ok"])
        self.assertEqual(self.post("enable-nut-sensor", {"confirmed": True, "expected_source_id": "nut:device_apc", "entity_id": "sensor.runtime"}), 200)

    def test_pause_api_does_not_accept_missing_csrf_or_invent_outage(self):
        self.assertEqual(self.post("pause-rtc-retries", {}, False), 403)
        self.assertEqual(self.post("pause-rtc-retries", {}), 409)
        self.assertEqual(self.supervisor.shutdowns, 0)


if __name__ == "__main__": unittest.main()
