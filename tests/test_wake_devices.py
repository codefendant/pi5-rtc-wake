"""Device waking is opt-in, identity-bound, at-most-once per boot, and isolated."""

from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import threading
import unittest
from unittest.mock import patch

from test_setup import Fixture
from test_calendar_schedule import event
from phone_messages import states_by_id
from services import Supervisor
from state import StateStore, UserError, atomic_json
from wake_devices import DEFAULTS, discover, registry_identity, validate_settings, ping_template
from dashboard import add_wake_devices_card, starter_config


def configure_devices(supervisor, now):
    supervisor.wake_registry = {}
    for entity, name, platform in (("button.office_pc", "Office PC", "wake_on_lan"),
                                    ("button.backup_server", "Backup server", "wake_on_lan"),
                                    ("binary_sensor.office_pc", "Office PC Ping", "ping")):
        supervisor.wake_registry[entity] = {"registry_id": "registry-" + entity, "unique_id": "unique-" + entity,
            "config_entry_id": "entry-" + entity, "platform": platform, "name": name, "area": "Office", "disabled": False}
        supervisor.phone_states.append({"entity_id": entity, "state": "off" if platform == "ping" else "unknown",
            "attributes": {"friendly_name": name, **({"device_class": "connectivity"} if platform == "ping" else {})}})


class WakeDeviceTests(unittest.TestCase, Fixture):
    def setUp(self):
        self.setup_app()
        configure_devices(self.supervisor, self.now)
        self.worker = self.app.wake_devices
        self.scan()

    def scan(self):
        self.worker.begin("scan", {})
        self.worker.process_once()

    def settings(self, **values):
        row = self.worker.options["devices"][1]  # Office PC, alphabetic list
        result = {**deepcopy(DEFAULTS), "require_mains": False, "devices": [{"entity_id": row["entity_id"],
            "identity": row["identity"], "name": row["name"], "online_entity_id": None, "online_identity": None}]}
        result.update(values)
        return result

    def save(self, **values):
        value = self.settings(**values)
        self.worker.save_settings(value)
        return deepcopy(self.app.store.data["wake_devices"])

    def wake(self):
        self.worker.begin("wake", {"confirmed": True, "expected_settings": deepcopy(self.app.store.data["wake_devices"])})
        self.worker.process_once()

    def next_boot(self, at=None):
        self.host.identity += "-next"
        self.host.started = self.now if at is None else at
        self.app = self.new_app()
        self.worker = self.app.wake_devices
        self.advance(61)

    def ping(self, state="on", age=0, restored=False, identity=None):
        return {"entity_id": "binary_sensor.office_pc", "state": state, "attributes": {"restored": restored},
                "last_reported": datetime.fromtimestamp(self.now - age, timezone.utc).isoformat(),
                "identity": identity or registry_identity(self.supervisor.wake_registry["binary_sensor.office_pc"])}

    def test_schema_ten_upgrade_preserves_all_existing_settings_and_starts_off(self):
        old = deepcopy(self.app.store.data)
        old.pop("wake_devices")
        old["schema_version"] = 10
        atomic_json(self.app.store.path, old)
        upgraded = StateStore(self.temp.name)
        self.assertEqual(upgraded.data["wake_devices"], DEFAULTS)
        for key in old:
            if key != "schema_version": self.assertEqual(upgraded.data[key], old[key])

    def test_saved_feature_choices_survive_upgrade_and_restart(self):
        selected = self.save(enabled=True)
        self.assertEqual(self.new_app().store.data["wake_devices"], selected)
        self.assertFalse(self.app.store.data["messages"]["enabled"])

    def test_discovery_accepts_unpressed_unknown_buttons_and_only_native_platforms(self):
        self.assertEqual(len(self.worker.options["devices"]), 2)
        metadata = deepcopy(self.supervisor.wake_registry)
        metadata["button.office_pc"]["platform"] = "script"
        metadata["button.backup_server"]["disabled"] = True
        self.assertEqual(discover(states_by_id(self.supervisor.phone_states), metadata)["devices"], [])

    def test_corrupt_and_oversized_settings_are_rejected(self):
        for changes in ({"enabled": 1}, {"delay_seconds": 0}, {"check_timeout_seconds": 301},
                        {"devices": [{}]}, {"arbitrary_service": "switch.turn_off"}, {"enabled": True, "devices": []}):
            with self.subTest(changes=changes), self.assertRaises(UserError):
                validate_settings({**deepcopy(DEFAULTS), **changes})

    def test_saving_does_not_send_and_suppresses_current_boot(self):
        self.save(enabled=True, after_every_boot=True)
        self.advance(100)
        self.worker.poll_boot()
        self.assertEqual(self.supervisor.wake_buttons, [])
        self.worker = self.new_app().wake_devices
        self.advance(100)
        self.worker.poll_boot()
        self.assertEqual(self.supervisor.wake_buttons, [])

    def test_every_boot_runs_once_even_after_app_restart_and_settings_edits(self):
        self.save(enabled=True, after_every_boot=True)
        self.next_boot()
        self.worker.poll_boot()
        self.assertEqual(len(self.supervisor.wake_buttons), 1)
        self.app = self.new_app()
        self.worker = self.app.wake_devices
        self.advance(100)
        self.worker.poll_boot()
        self.assertEqual(len(self.supervisor.wake_buttons), 1)

    def test_startup_delay_is_required(self):
        self.save(enabled=True, after_every_boot=True)
        self.next_boot()
        self.worker.started = self.mono
        self.worker.poll_boot()
        self.assertEqual(self.supervisor.wake_buttons, [])
        self.advance(61)
        self.worker.poll_boot()
        self.assertEqual(len(self.supervisor.wake_buttons), 1)

    def test_default_trigger_skips_manual_boot_and_wake_test(self):
        self.save(enabled=True)
        self.next_boot()
        self.worker.poll_boot()
        self.assertEqual(self.supervisor.wake_buttons, [])
        self.assertIn("not a recorded Calendar wake", self.worker.result["message"])

    def test_recorded_calendar_wake_dispatches_without_another_date_store(self):
        self.save(enabled=True)
        self.worker.scheduled_shutdown({"wake_epoch": self.now + 600})
        self.advance(600)
        self.next_boot()
        self.worker.poll_boot()
        self.assertEqual(len(self.supervisor.wake_buttons), 1)
        self.assertEqual(self.worker.trace["last_run"]["trigger"], "Calendar wake")
        self.assertEqual(set(self.worker.trace["receipt"]), {"boot_id", "wake_epoch"})

    def test_early_or_late_boot_does_not_match_scheduled_receipt(self):
        self.save(enabled=True)
        self.worker.scheduled_shutdown({"wake_epoch": self.now + 600})
        self.next_boot()
        self.worker.poll_boot()
        self.assertEqual(self.supervisor.wake_buttons, [])

    def test_real_calendar_shutdown_records_only_at_final_verified_submission(self):
        self.pass_test()
        self.worker = self.app.wake_devices
        self.supervisor.calendar_list = [{"entity_id": "calendar.pi_sleep", "name": "Pi Sleep"}]
        self.supervisor.events["calendar.pi_sleep"] = [event(self.now + 120, self.now + 900)]
        self.app.save_settings({**self.app.store.data["schedule"], "calendar_entity_id": "calendar.pi_sleep", "enabled": True})
        self.advance(120)
        self.app.refresh_calendar(force_discovery=True)
        self.app.tick()
        self.app.process_task()
        self.assertEqual(self.worker.trace["receipt"], {})
        self.advance(31)
        self.app.tick()
        self.assertEqual(self.worker.trace["receipt"]["wake_epoch"], self.now - 151 + 900)
        self.assertEqual(self.supervisor.shutdowns, 2)  # Earlier simulated wake test

    def test_recording_failure_cannot_cancel_the_pis_own_wake_alarm(self):
        with patch("wake_devices.atomic_json", side_effect=OSError()):
            self.worker.scheduled_shutdown({"wake_epoch": self.now + 600})
        self.assertEqual(self.worker.trace["receipt"], {})
        self.assertTrue(self.worker.result["error"])

    def test_manual_wake_works_with_automatic_disabled_and_keep_awake(self):
        self.save()
        self.app.store.data["keep_awake"] = True
        self.wake()
        self.assertEqual(len(self.supervisor.wake_buttons), 1)
        self.assertEqual(self.supervisor.shutdowns, 0)
        self.assertEqual(self.worker.trace["last_run"]["devices"][0]["state"], "submitted")

    def test_manual_consent_is_bound_to_saved_devices_and_options(self):
        settings = self.save()
        settings["delay_seconds"] += 1
        with self.assertRaises(UserError): self.worker.begin("wake", {"confirmed": True, "expected_settings": settings})
        with self.assertRaises(UserError): self.worker.begin("wake", {"confirmed": False, "expected_settings": self.app.store.data["wake_devices"]})
        self.assertEqual(self.supervisor.wake_buttons, [])

    def test_registry_identity_change_after_selection_never_wakes_replacement(self):
        self.save()
        self.supervisor.wake_registry["button.office_pc"]["unique_id"] = "different-mac"
        self.wake()
        self.assertEqual(self.supervisor.wake_buttons, [])
        self.assertEqual(self.worker.trace["last_run"]["devices"][0]["state"], "unavailable")

    def test_shutdown_countdown_prevents_wake_requests(self):
        self.save()
        self.app.pending = {"kind": "ups", "emergency": True}
        with self.assertRaises(UserError): self.wake()
        self.assertEqual(self.supervisor.wake_buttons, [])

    def test_mid_run_emergency_prevents_remaining_devices(self):
        settings = self.settings()
        row = self.worker.options["devices"][0]
        settings["devices"].append({"entity_id": row["entity_id"], "identity": row["identity"], "name": row["name"], "online_entity_id": None, "online_identity": None})
        self.worker.save_settings(settings)
        def first(entity, identity):
            self.supervisor.wake_buttons.append((entity, identity))
            self.app.pending = {"kind": "ups", "emergency": True}
        self.supervisor.press_wake_button = first
        self.wake()
        self.assertEqual(len(self.supervisor.wake_buttons), 1)

    def test_slow_home_assistant_request_leaves_power_lock_available(self):
        self.save()
        entered, release = threading.Event(), threading.Event()
        original = self.supervisor.message_states
        def slow():
            entered.set()
            release.wait(3)
            return original()
        self.supervisor.message_states = slow
        self.worker.begin("wake", {"confirmed": True, "expected_settings": self.app.store.data["wake_devices"]})
        thread = threading.Thread(target=self.worker.process_once)
        thread.start()
        try:
            self.assertTrue(entered.wait(1))
            self.assertTrue(self.app.lock.acquire(timeout=0.2))
            self.app.lock.release()
        finally:
            release.set()
            thread.join(3)
        self.assertFalse(thread.is_alive())

    def test_no_packets_when_durable_claim_cannot_be_written(self):
        self.save()
        with patch("wake_devices.atomic_json", side_effect=OSError()): self.wake()
        self.assertEqual(self.supervisor.wake_buttons, [])
        self.assertTrue(self.worker.result["error"])

    def test_uncertain_service_response_is_not_retried_after_restart(self):
        self.save(enabled=True, after_every_boot=True)
        self.next_boot()
        with patch.object(self.supervisor, "press_wake_button", side_effect=UserError("Timed out", "Check device")) as press:
            self.worker.poll_boot()
            self.assertEqual(press.call_count, 1)
            self.app = self.new_app()
            self.worker = self.app.wake_devices
            self.advance(120)
            self.worker.poll_boot()
            self.assertEqual(press.call_count, 1)
        self.assertEqual(self.worker.trace["last_run"]["devices"][0]["state"], "unconfirmed")

    def test_utility_power_guard_requires_current_boot_fresh_mains(self):
        self.save()
        settings = {**deepcopy(self.app.store.data["wake_devices"]), "require_mains": True}
        self.worker.save_settings(settings)
        for state, age in (("battery", 0), ("unknown", 0), ("mains", 181), ("mains", 4000)):
            source = {"ok": True, "power_state": state, "observed_epoch": self.now - age}
            with patch.object(self.app, "_selected_power", return_value=source), self.assertRaises(UserError): self.wake()
        with patch.object(self.app, "_selected_power", return_value={"ok": True, "power_state": "mains", "observed_epoch": self.now}): self.wake()
        self.assertEqual(len(self.supervisor.wake_buttons), 1)

    def test_auto_waits_for_mains_then_wakes_once_or_skips_after_fifteen_minutes(self):
        settings = self.settings(enabled=True, after_every_boot=True, require_mains=True)
        self.app.store.data["ups"]["source_id"] = "nut:test"
        self.worker.save_settings(settings)
        self.next_boot()
        self.worker.poll_boot()
        self.assertEqual(self.supervisor.wake_buttons, [])
        with patch.object(self.app, "_selected_power", return_value={"ok": True, "power_state": "mains", "observed_epoch": self.now}): self.worker.poll_boot()
        self.assertEqual(len(self.supervisor.wake_buttons), 1)

    def test_auto_startup_wait_expires_without_later_surprise_wake(self):
        settings = self.settings(enabled=True, after_every_boot=True, require_mains=True)
        self.app.store.data["ups"]["source_id"] = "nut:test"
        self.worker.save_settings(settings)
        self.next_boot()
        self.advance(900)
        self.worker.poll_boot()
        self.assertIn("skipped", self.worker.result["message"])
        with patch.object(self.app, "_selected_power", return_value={"ok": True, "power_state": "mains", "observed_epoch": self.now}): self.worker.poll_boot()
        self.assertEqual(self.supervisor.wake_buttons, [])

    def test_failed_settings_save_keeps_old_preferences_and_sends_nothing(self):
        before = deepcopy(self.app.store.data["wake_devices"])
        with patch.object(self.app.store, "save", side_effect=OSError()), self.assertRaises(OSError): self.save(enabled=True)
        self.assertEqual(self.app.store.data["wake_devices"], before)
        self.assertEqual(self.supervisor.wake_buttons, [])

    def test_corrupt_primary_backup_restore_disables_device_automation(self):
        self.save(enabled=True, after_every_boot=True)
        self.app.store.save()
        self.app.store.path.write_text("broken")
        restored = StateStore(self.temp.name)
        self.assertFalse(restored.data["wake_devices"]["enabled"])
        self.assertEqual(restored.data["wake_devices"]["devices"], self.app.store.data["wake_devices"]["devices"])

    def test_interrupted_checks_do_not_keep_showing_checking_after_restart(self):
        settings = self.save()
        self.worker.trace["last_run"] = {"at": self.now, "trigger": "Manual wake", "devices": [
            {"entity_id": settings["devices"][0]["entity_id"], "name": "Office PC", "state": "checking"}]}
        atomic_json(self.worker.path, self.worker.trace)
        restarted = self.new_app().wake_devices
        self.assertEqual(restarted.trace["last_run"]["devices"][0]["state"], "unconfirmed")

    def test_online_check_uses_post_request_last_reported_when_state_is_unchanged(self):
        settings = self.settings()
        ping = self.worker.options["pings"][0]
        settings["devices"][0].update(online_entity_id=ping["entity_id"], online_identity=ping["identity"])
        self.worker.save_settings(settings)
        self.supervisor.ping_rows = [self.ping()]
        self.wake()
        self.assertEqual(self.worker.trace["last_run"]["devices"][0]["state"], "online")

    def test_stale_restored_or_replaced_ping_never_claims_device_is_online(self):
        for values in ({"age": 5}, {"restored": True}, {"identity": "0" * 64}, {"state": "off"}):
            with self.subTest(values=values):
                settings = self.settings()
                ping = self.worker.options["pings"][0]
                settings["devices"][0].update(online_entity_id=ping["entity_id"], online_identity=ping["identity"])
                self.worker.save_settings(settings)
                self.supervisor.ping_rows = [self.ping(**values)]
                with patch.object(self.app.stop_event, "wait", side_effect=lambda seconds: self.advance(121) or False): self.wake()
                self.assertEqual(self.worker.trace["last_run"]["devices"][0]["state"], "not_reachable")

    def test_unreadable_history_pauses_auto_until_explicit_save(self):
        self.save(enabled=True, after_every_boot=True)
        self.worker.path.write_text("broken")
        self.next_boot()
        self.worker.poll_boot()
        self.assertEqual(self.supervisor.wake_buttons, [])
        self.assertTrue(self.worker.storage_error)
        self.scan()
        self.save(enabled=True, after_every_boot=True)
        self.worker.poll_boot()
        self.assertEqual(self.supervisor.wake_buttons, [])
        self.assertFalse(self.worker.storage_error)

    def test_additive_layout_upgrade_keeps_custom_cards_and_does_not_return_deleted_card(self):
        config = starter_config("entry-a")
        config["views"][0]["sections"] = [section for section in config["views"][0]["sections"] if section["cards"][0]["type"] != "custom:pi-wake-devices-card"]
        config["views"][0]["sections"].append({"cards": [{"type": "picture", "image": "/local/photo.jpg"}]})
        upgraded = add_wake_devices_card(config, "entry-a")
        self.assertEqual(upgraded["views"][0]["sections"][:-1], config["views"][0]["sections"])
        self.assertEqual(add_wake_devices_card(upgraded, "entry-a"), upgraded)
        self.supervisor.dashboard_config = config
        self.app.dashboard.ready({"entry_id": "entry-a"})
        self.supervisor.dashboard_config["views"][0]["sections"].pop()
        removed = deepcopy(self.supervisor.dashboard_config)
        self.app.dashboard.ready({"entry_id": "entry-a"})
        self.assertEqual(self.supervisor.dashboard_config, removed)


class WakeServiceTests(unittest.TestCase):
    def test_press_rechecks_native_platform_identity_and_fixed_service(self):
        supervisor = Supervisor()
        row = {"registry_id": "a", "unique_id": "b", "config_entry_id": "c", "platform": "wake_on_lan", "disabled": False}
        with patch.object(supervisor, "wake_metadata", return_value={"button.pc": row}), patch.object(supervisor, "request") as request:
            supervisor.press_wake_button("button.pc", registry_identity(row))
            request.assert_called_once_with("/core/api/services/button/press", {"entity_id": "button.pc"})
            row["disabled"] = True
            with self.assertRaises(UserError): supervisor.press_wake_button("button.pc", registry_identity(row))
            self.assertEqual(request.call_count, 1)

    def test_arbitrary_services_addresses_and_templates_are_rejected(self):
        supervisor = Supervisor()
        with patch.object(supervisor, "request") as request:
            for entity in ("switch.poe", "script.shutdown", "button.pc/../press", "http://target"):
                with self.assertRaises(UserError): supervisor.press_wake_button(entity, "a" * 64)
            for entities in (["binary_sensor.x';x"], ["button.pc"], ["binary_sensor.pc"] * 13):
                with self.assertRaises(ValueError): ping_template(entities)
            request.assert_not_called()


if __name__ == "__main__": unittest.main()
