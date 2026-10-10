from copy import deepcopy
from datetime import datetime, timezone
import unittest
from unittest.mock import patch

from test_setup import Fixture
from test_rtc_wake import epoch
from power_sources import DISCOVERY_TEMPLATE, discover_sources, notice_for, validate_settings
from state import StateStore, UserError, atomic_json
from services import Supervisor

NOW = epoch("2026-10-10T00:00:00Z")


def stamp(value=NOW): return datetime.fromtimestamp(value, timezone.utc).isoformat()


def nut_rows(now=NOW, status="OL", battery="100"):
    base = {"kind": "nut", "device_id": "device_apc", "name": "APC UPS", "manufacturer": "APC", "model": "Test UPS", "reported_at": stamp(now)}
    return {"rows": [{**base, "entity_id": "sensor.renamed_raw_status", "state": status, "attributes": {"friendly_name": "UPS Status data"}},
                     {**base, "entity_id": "sensor.renamed_charge", "state": battery, "attributes": {"device_class": "battery", "unit_of_measurement": "%", "friendly_name": "Battery charge"}}]}


def hook_row(now=NOW, **updates):
    fields = {"schema_version": 1, "provider": "Example local adapter", "observed_at": stamp(now), "power_state": "battery", "battery_percent": 45, "runtime_seconds": 1800, "low_battery": False}
    fields.update(updates)
    return {"kind": "hook", "entity_id": "sensor.rv_power_hook", "name": "RV power", "reported_at": stamp(now), "state": "battery", "attributes": {"rtc_wake_power": fields}}


class PowerAdapterTests(unittest.TestCase):
    def test_native_nut_status_and_charge_work_after_entities_are_renamed(self):
        sources, warnings = discover_sources(nut_rows(status="OB DISCHRG", battery="45"), NOW)
        self.assertEqual(warnings, [])
        self.assertEqual(sources[0]["id"], "nut:device_apc")
        self.assertEqual(sources[0]["power_state"], "battery")
        self.assertEqual(sources[0]["battery_percent"], 45)
        self.assertEqual(sources[0]["recovery"], "unverified")

    def test_raw_status_is_used_instead_of_translated_display_text(self):
        data = nut_rows(status="OB LB", battery="10")
        data["rows"].append({**data["rows"][0], "entity_id": "sensor.readable_status", "state": "On Battery Battery Low"})
        source = discover_sources(data, NOW)[0][0]
        self.assertTrue(source["low_battery"])
        self.assertEqual(source["power_state"], "battery")

    def test_display_status_alone_does_not_create_a_guessed_provider(self):
        sources, warnings = discover_sources(nut_rows(status="On Battery"), NOW)
        self.assertEqual(sources, [])
        self.assertIn("Status data", warnings[0])

    def test_conflicting_or_duplicate_raw_status_is_not_trusted(self):
        source = discover_sources(nut_rows(status="OL OB"), NOW)[0][0]
        self.assertFalse(source["ok"])
        data = nut_rows()
        data["rows"].append({**data["rows"][0], "entity_id": "sensor.extra_status"})
        self.assertEqual(discover_sources(data, NOW)[0], [])

    def test_nut_reading_age_is_not_reset_by_a_successful_api_read(self):
        source = discover_sources(nut_rows(now=NOW - 181), NOW)[0][0]
        self.assertFalse(source["ok"])
        self.assertEqual(source["power_state"], "unknown")

    def test_charge_threshold_settings_are_not_confused_with_battery_measurement(self):
        data = nut_rows(battery="50")
        data["rows"].append({**data["rows"][1], "entity_id": "sensor.low_charge_setting", "state": "20", "attributes": {"unit_of_measurement": "%"}})
        source = discover_sources(data, NOW)[0][0]
        self.assertEqual(source["battery_percent"], 50)
        self.assertEqual(len(source["readings"]), 3)

    def test_multiple_battery_measurements_are_not_silently_chosen(self):
        data = nut_rows()
        data["rows"].append({**data["rows"][1], "entity_id": "sensor.second_battery", "state": "40"})
        self.assertIsNone(discover_sources(data, NOW)[0][0]["battery_percent"])

    def test_seconds_unit_does_not_guess_runtime_from_a_restart_delay(self):
        data = nut_rows()
        data["rows"].append({**data["rows"][0], "entity_id": "sensor.ups_delay", "state": "15", "attributes": {"unit_of_measurement": "s"}})
        self.assertIsNone(discover_sources(data, NOW)[0][0]["runtime_seconds"])

    def test_other_devices_are_grouped_separately(self):
        data = nut_rows(status="OL")
        second = nut_rows(status="OB", battery="20")
        for row in second["rows"]:
            row["device_id"] = "device_other"
            row["entity_id"] += "_other"
        data["rows"].extend(second["rows"])
        sources = discover_sources(data, NOW)[0]
        self.assertEqual(len(sources), 2)
        self.assertEqual({source["power_state"] for source in sources}, {"mains", "battery"})

    def test_hook_has_typed_battery_runtime_and_no_automatic_control_capability(self):
        source = discover_sources({"rows": [hook_row(capabilities={"shutdown_return": True})]}, NOW)[0][0]
        self.assertEqual(source["runtime_seconds"], 1800)
        self.assertEqual(source["battery_percent"], 45)
        self.assertEqual(source["recovery"], "unverified")
        self.assertNotIn("capabilities", source)

    def test_bad_hook_does_not_hide_a_good_nut_device(self):
        data = nut_rows()
        data["rows"].append(hook_row(schema_version=2))
        sources, warnings = discover_sources(data, NOW)
        self.assertEqual(len(sources), 1)
        self.assertIn("unsupported version", warnings[0])

    def test_stale_future_and_naive_hook_observation_times_are_unknown(self):
        for value in (stamp(NOW - 181), stamp(NOW + 11), "2026-10-10T00:00:00"):
            with self.subTest(value=value):
                source = discover_sources({"rows": [hook_row(observed_at=value)]}, NOW)[0][0]
                self.assertFalse(source["ok"])
                self.assertEqual(source["power_state"], "unknown")

    def test_fresh_hook_attrs_do_not_override_unavailable_entity(self):
        row = hook_row()
        row["state"] = "unavailable"
        self.assertFalse(discover_sources({"rows": [row]}, NOW)[0][0]["ok"])

    def test_invalid_battery_values_are_not_treated_as_zero_or_full_charge(self):
        for value in (True, False, "nan", "inf", -1, 101, 10**1000, {}, None):
            with self.subTest(value=value):
                source = discover_sources({"rows": [hook_row(battery_percent=value)]}, NOW)[0][0]
                self.assertIsNone(source["battery_percent"])

    def test_duplicate_hook_identity_is_refused(self):
        with self.assertRaises(UserError): discover_sources({"rows": [hook_row(), hook_row()]}, NOW)

    def test_settings_require_a_source_and_valid_integer_threshold(self):
        for value in ({"source_id": None, "notifications": True, "low_battery_percent": 25},
                      {"source_id": "hook:../config", "notifications": True, "low_battery_percent": 25},
                      {"source_id": "nut:device_apc", "notifications": True, "low_battery_percent": True}):
            with self.subTest(value=value), self.assertRaises(UserError): validate_settings(value)

    def test_notification_requires_on_battery_not_just_a_low_charge_number(self):
        settings = {"low_battery_percent": 25}
        source = discover_sources(nut_rows(status="OL", battery="20"), NOW)[0][0]
        self.assertEqual(notice_for(source, settings)["kind"], "mains")
        source = discover_sources(nut_rows(status="OB", battery="20"), NOW)[0][0]
        self.assertEqual(notice_for(source, settings)["kind"], "low_battery")


class PowerMonitorTests(unittest.TestCase, Fixture):
    def setUp(self):
        self.setup_app()
        self.supervisor.power_rows = nut_rows(self.now)
        self.app.refresh_power()

    def select(self, notifications=True):
        self.app.save_power_settings({"source_id": "nut:device_apc", "notifications": notifications, "low_battery_percent": 25})

    def test_discovery_does_not_auto_select_notify_or_shut_down(self):
        self.assertEqual(len(self.app.power_info["sources"]), 1)
        self.assertIsNone(self.app.store.data["ups"]["source_id"])
        self.assertFalse(self.app.store.data["ups"]["notifications"])
        self.assertEqual(self.supervisor.shutdowns, 0)
        self.assertEqual(self.rtc.writes, 0)

    def test_on_battery_low_and_restored_notices_are_scoped_and_deduplicated(self):
        self.select()
        self.supervisor.power_rows = nut_rows(self.now, "OB", "50")
        self.app.refresh_power()
        self.app.refresh_power()
        self.assertEqual(self.supervisor.power_notices[-1]["kind"], "battery")
        count = len(self.supervisor.power_notices)
        self.app.refresh_power()
        self.assertEqual(len(self.supervisor.power_notices), count)
        self.supervisor.power_rows = nut_rows(self.now, "OB LB", "15")
        self.app.refresh_power()
        self.assertEqual(self.supervisor.power_notices[-1]["kind"], "low_battery")
        self.supervisor.power_rows = nut_rows(self.now, "OL", "15")
        self.app.refresh_power()
        self.assertIsNone(self.supervisor.power_notices[-1])
        self.assertEqual(self.supervisor.shutdowns, 0)
        self.assertEqual(self.rtc.writes, 0)

    def test_selection_and_notification_settings_survive_update(self):
        self.select()
        replacement = self.new_app()
        replacement.refresh()
        self.assertEqual(replacement.store.data["ups"], self.app.store.data["ups"])
        self.assertEqual(replacement.snapshot()["ups"]["selected"]["id"], "nut:device_apc")

    def test_read_failure_is_unknown_and_never_a_power_restored_signal(self):
        self.select()
        with patch.object(self.supervisor, "power_sources", side_effect=UserError("Core offline", "Retry")):
            self.app.refresh_power()
        self.assertIsNone(self.app.snapshot()["ups"]["selected"])
        self.assertEqual(self.supervisor.power_notices[-1]["kind"], "unknown")
        self.assertEqual(self.supervisor.shutdowns, 0)

    def test_notification_failure_does_not_break_calendar_hardware_checks(self):
        self.pass_test()
        self.enable()
        self.select()
        self.supervisor.power_rows = nut_rows(self.now, "OB", "50")
        with patch.object(self.supervisor, "power_notice", side_effect=UserError("Notice offline", "Retry")):
            self.app.refresh_power()
        self.assertFalse(self.app.power_notice_ok)
        self.assertTrue(self.app.snapshot()["schedule_active"])

    def test_monitor_cache_expires_without_relabeling_old_data_as_fresh(self):
        self.select()
        self.advance(91)
        self.assertIsNone(self.app.snapshot()["ups"]["selected"])

    def test_failed_setting_write_restores_previous_selection(self):
        before = deepcopy(self.app.store.data)
        with patch.object(self.app.store, "save", side_effect=OSError("disk full")):
            with self.assertRaises(OSError): self.select()
        self.assertEqual(self.app.store.data, before)

    def test_native_template_and_notice_use_core_api_without_ups_commands(self):
        supervisor = Supervisor()
        with patch.object(supervisor, "request", return_value={"rows": []}) as request:
            supervisor.power_sources()
            supervisor.power_notice({"message": "On battery"})
            supervisor.power_notice(None)
        paths = [call.args[0] for call in request.call_args_list]
        self.assertEqual(paths, ["/core/api/template", "/core/api/services/persistent_notification/create", "/core/api/services/persistent_notification/dismiss"])
        self.assertEqual(request.call_args_list[0].args[1], {"template": DISCOVERY_TEMPLATE})


class CalendarOnlyMigrationTests(unittest.TestCase, Fixture):
    def setUp(self): self.setup_app()

    def test_old_selected_calendar_and_test_survive_without_duplicate_time_fields(self):
        self.pass_test()
        self.enable()
        old = deepcopy(self.app.store.data)
        old["schema_version"] = 3
        old["schedule"].update(sleep_time="23:00", wake_time="07:00")
        atomic_json(self.app.store.path, old)
        replacement = self.new_app()
        replacement.refresh()
        self.assertTrue(replacement.snapshot()["schedule_active"])
        self.assertEqual(replacement.store.data["test"], old["test"])
        self.assertNotIn("sleep_time", replacement.store.data["schedule"])
        self.assertNotIn("wake_time", replacement.store.data["schedule"])

    def test_legacy_daily_post_cannot_reenable_a_separate_scheduler(self):
        with self.assertRaises(UserError):
            self.app.save_settings({"sleep_time": "23:00", "wake_time": "07:00", "timezone": "America/Chicago", "enabled": True})
        self.assertFalse(self.app.store.data["schedule"]["enabled"])


if __name__ == "__main__": unittest.main()
