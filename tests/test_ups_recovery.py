from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from test_setup import Fixture
from test_power_sources import hook_row, nut_rows, stamp
from calendar_schedule import due_period, parse_periods
from power_sources import discover_sources
from services import Supervisor
from state import StateStore, UserError, atomic_json
from ups_recovery import DEFAULTS, retry_is_safe, retry_minutes, validate_policy, with_runtime


class PolicyValidationTests(unittest.TestCase):
    def test_defaults_keep_main_ha_running_to_runtime_threshold_and_control_off(self):
        policy = validate_policy({})
        self.assertFalse(policy["enabled"])
        self.assertFalse(policy["early_shutdown"])
        self.assertEqual(policy["shutdown_runtime_minutes"], 30)

    def test_confirmation_and_integer_bounds_are_enforced(self):
        for value in ({"enabled": True}, {"first_retry_minutes": True}, {"max_retries": 0},
                      {"runtime_entity_id": "sensor.bad/route"}, {"shutdown_runtime_minutes": 10},
                      {"first_retry_minutes": 20, "max_retry_minutes": 10}):
            with self.subTest(value=value), self.assertRaises(UserError): validate_policy(value)

    def test_backoff_and_limit_do_not_create_unbounded_loops(self):
        policy = {**DEFAULTS, "max_retry_minutes": 60}
        self.assertEqual([retry_minutes(policy, n) for n in range(5)], [15, 30, 60, 60, 60])
        source = {"runtime_seconds": 100000, "battery_percent": 100}
        self.assertFalse(retry_is_safe(source, policy, 3))

    def test_runtime_reserve_and_low_charge_disable_retries(self):
        for source in ({"runtime_seconds": 100, "battery_percent": 100},
                       {"runtime_seconds": 100000, "battery_percent": 20},
                       {"runtime_seconds": None, "battery_percent": 100},
                       {"runtime_seconds": 100000, "battery_percent": 100, "low_battery": True},
                       {"runtime_seconds": 100000, "battery_percent": 100, "forced_shutdown": True}):
            with self.subTest(source=source): self.assertFalse(retry_is_safe(source, DEFAULTS, 0))

    def test_nut_runtime_is_selected_from_same_device_and_normalized(self):
        now = 1791586800
        value = nut_rows(now)
        value["rows"].extend([{**value["rows"][0], "entity_id": "sensor.renamed_runtime", "state": "30",
            "attributes": {"friendly_name": "Remaining runtime", "device_class": "duration", "unit_of_measurement": "min"}},
            {**value["rows"][0], "entity_id": "sensor.restart_delay", "state": "10",
            "attributes": {"device_class": "duration", "unit_of_measurement": "s"}}])
        source = discover_sources(value, now)[0][0]
        self.assertIsNone(source["runtime_seconds"])
        policy = {**DEFAULTS, "runtime_entity_id": "sensor.renamed_runtime"}
        self.assertEqual(with_runtime(source, policy, now)["runtime_seconds"], 1800)
        self.assertIsNone(with_runtime(source, {**policy, "runtime_entity_id": "sensor.other_ups"}, now)["runtime_seconds"])
        self.assertIsNone(with_runtime(source, policy, now+181)["runtime_seconds"])

    def test_managed_calendar_dates_do_not_replay_as_ordinary_shutdowns(self):
        now = 1791586800
        marker = "Pi Wake & Sleep UPS v1:retry:" + "a"*32
        stamp = lambda epoch: datetime.fromtimestamp(epoch, timezone.utc).isoformat()
        events = [{"summary": "UPS retry", "description": marker, "start": {"dateTime": stamp(now)}, "end": {"dateTime": stamp(now+900)}},
                  {"summary": "Normal off", "start": {"dateTime": stamp(now+100)}, "end": {"dateTime": stamp(now+1000)}}]
        periods = parse_periods(events, "calendar.pi", now)
        self.assertIsNone(due_period(periods, now))
        self.assertEqual(due_period(periods, now+100)["title"], "Normal off")

    def test_final_stop_is_a_calendar_record_without_a_wake_date(self):
        now = 1791586800
        stamp = lambda epoch: datetime.fromtimestamp(epoch, timezone.utc).isoformat()
        event = {"description": "Pi Wake & Sleep UPS v1:stop:" + "b"*32,
                 "start": {"dateTime": stamp(now+30)}, "end": {"dateTime": stamp(now+90)}}
        period = parse_periods([event], "calendar.pi", now)[0]
        self.assertEqual(period["power_action"], "stop")
        self.assertIsNone(due_period([period], now+30))


class RecoveryTests(unittest.TestCase, Fixture):
    def setUp(self):
        self.setup_app()
        self.pass_test()
        self.enable()
        self.reading("mains", 7200)
        self.app.save_power_settings({"source_id": "hook:sensor.rv_power_hook", "notifications": True, "low_battery_percent": 25})
        self.policy = {**deepcopy(DEFAULTS), "enabled": True, "supply_confirmed": True, "final_shutdown_confirmed": True,
                       "owner_confirmed": True,
                       "expected_source_id": "hook:sensor.rv_power_hook", "expected_calendar_entity_id": "calendar.test_pi"}
        self.app.recovery.save_settings(self.policy)

    def reading(self, state, runtime=7200, battery=100, **updates):
        self.supervisor.power_rows = {"rows": [hook_row(self.now, power_state=state, runtime_seconds=runtime, battery_percent=battery, **updates)]}
        self.app.refresh_power()

    def start(self, runtime=1800, **updates):
        self.reading("battery", runtime, **updates)
        self.app.tick()
        self.assertEqual(self.app.job["kind"], "ups")
        self.app.process_task()
        return self.app.pending

    def finish(self):
        self.advance(30)
        self.app.tick()

    def reboot(self, wake):
        self.host.identity += "-next"
        self.host.started = wake
        self.now = wake + 90
        self.mono += 660
        self.app = self.new_app()
        self.reading("battery", 6000)
        self.app.refresh()

    def test_default_does_not_shut_down_after_five_minutes_with_ample_runtime(self):
        self.reading("battery", 7200)
        self.app.tick()
        self.advance(301)
        self.reading("battery", 6900)
        self.app.tick()
        self.assertIsNone(self.app.job)
        self.assertEqual(self.supervisor.shutdowns, 1)  # Only the earlier simulated wake test.
        self.assertFalse(self.app.snapshot()["schedule_active"])

    def test_runtime_threshold_records_calendar_before_arm_and_graceful_shutdown(self):
        pending = self.start()
        event = self.supervisor.created_events[-1]
        self.assertEqual(pending["wake_epoch"], int(datetime.fromisoformat(event["end"]["dateTime"]).timestamp()))
        self.assertIn("retry", event["description"])
        self.assertEqual(self.app.store.data["outage"]["attempts"], 1)
        self.finish()
        self.assertEqual(self.supervisor.shutdowns, 2)
        self.assertEqual(self.app.store.data["outage"]["phase"], "submitted")

    def test_early_shutdown_delay_is_optional_and_does_not_count_mains_time(self):
        self.app.recovery.save_settings({**self.policy, "early_shutdown": True})
        self.reading("battery", 7200)
        self.app.tick()
        self.advance(299)
        self.reading("battery", 7200)
        self.app.tick()
        self.assertIsNone(self.app.job)
        self.advance(1)
        self.reading("battery", 7200)
        self.app.tick()
        self.app.process_task()
        self.assertTrue(self.app.pending["retry"])

    def test_new_boot_retains_attempts_and_schedules_next_backoff_in_calendar(self):
        wake = self.start()["wake_epoch"]
        self.finish()
        self.reboot(wake)
        self.app.tick()
        self.app.process_task()
        self.assertEqual(self.app.store.data["outage"]["attempts"], 2)
        self.assertEqual(self.app.pending["wake_epoch"] - self.now, 30 + 30*60)
        self.assertEqual(len(self.supervisor.created_events), 2)

    def test_fresh_utility_must_stay_stable_before_session_and_calendar_resume(self):
        self.reading("battery", 7200)
        self.app.tick()
        self.reading("mains", 7200)
        self.app.tick()
        self.advance(119)
        self.reading("mains", 7200)
        self.app.tick()
        self.assertFalse(self.app.snapshot()["schedule_active"])
        self.advance(1)
        self.reading("mains", 7200)
        self.app.tick()
        self.assertEqual(self.app.store.data["outage"], {})
        self.app.refresh()
        self.assertTrue(self.app.snapshot()["schedule_active"])

    def test_unknown_reading_resets_stable_power_timer(self):
        self.reading("battery")
        self.app.tick()
        self.reading("mains")
        self.app.tick()
        self.advance(90)
        self.reading("unknown")
        self.app.tick()
        self.reading("mains")
        self.app.tick()
        self.advance(60)
        self.reading("mains")
        self.app.tick()
        self.assertTrue(self.app.store.data["outage"])

    def test_power_return_during_retry_countdown_cancels_shutdown_and_alarm(self):
        self.start()
        self.reading("mains")
        self.finish()
        self.assertIsNone(self.app.pending)
        self.assertFalse(self.rtc.enabled)
        self.assertEqual(self.supervisor.shutdowns, 1)

    def test_low_runtime_causes_final_graceful_stop_without_alarm(self):
        pending = self.start(runtime=400)
        self.assertFalse(pending["retry"])
        self.assertIsNone(pending["wake_epoch"])
        self.assertFalse(self.rtc.enabled)
        self.assertIn(":stop:", self.supervisor.created_events[-1]["description"])
        self.finish()
        self.assertEqual(self.supervisor.shutdowns, 2)
        self.assertEqual(self.app.store.data["outage"]["phase"], "stopped")

    def test_low_charge_and_hardware_low_battery_never_authorize_retry(self):
        for updates in ({"battery": 20}, {"low_battery": True}):
            with self.subTest(updates=updates):
                pending = self.start(runtime=7200, **updates)
                self.assertFalse(pending["retry"])
                with self.assertRaises(UserError): self.app.cancel()
                self.reading("mains")
                self.finish()
                self.app.tick()
                self.advance(120)
                self.reading("mains")
                self.app.tick()

    def test_cancel_final_shutdown_works_without_rtc_transaction(self):
        self.start(runtime=400)
        self.app.cancel()
        self.assertIsNone(self.app.pending)
        self.assertEqual(self.app.store.data["outage"]["phase"], "paused")
        self.reading("battery", 100)
        self.app.tick()
        self.assertEqual(self.app.job["kind"], "ups")
        self.app.process_task()
        self.assertTrue(self.app.pending["emergency"])
        self.assertFalse(self.app.pending["retry"])

    def test_retry_limit_is_persistent_and_leads_to_final_stop(self):
        for n in range(3):
            pending = self.start(runtime=1800 if n == 0 else 10000) if n == 0 else self.app.pending
            if n:
                self.assertTrue(pending["retry"])
            wake = pending["wake_epoch"]
            self.finish()
            self.reboot(wake)
            self.app.tick()
            self.app.process_task()
        self.assertEqual(self.app.store.data["outage"]["attempts"], 3)
        self.assertFalse(self.app.pending["retry"])

    def test_lost_readings_during_known_outage_wait_then_stop_without_retry(self):
        self.reading("battery", 7200)
        self.app.tick()
        self.reading("unknown", None)
        self.app.tick()
        self.advance(179)
        self.reading("unknown", None)
        self.app.tick()
        self.assertIsNone(self.app.job)
        self.advance(1)
        self.reading("unknown", None)
        self.app.tick()
        self.app.process_task()
        self.assertFalse(self.app.pending["retry"])

    def test_unknown_without_known_outage_does_not_invent_an_emergency(self):
        self.reading("unknown", None)
        self.app.tick()
        self.advance(600)
        self.reading("unknown", None)
        self.app.tick()
        self.assertIsNone(self.app.job)
        self.assertEqual(self.app.store.data["outage"], {})

    def test_stale_runtime_after_new_boot_is_not_reused(self):
        wake = self.start()["wake_epoch"]
        self.finish()
        self.reboot(wake)
        self.supervisor.power_rows["rows"][0]["attributes"]["rtc_wake_power"]["observed_at"] = stamp(wake-1)
        self.app.refresh_power()
        self.app.tick()
        self.assertIsNone(self.app.job)
        self.assertIn("Waiting", self.app.store.data["outage"]["message"])

    def test_source_change_turns_off_recovery_and_invalidates_qualification(self):
        self.app.save_power_settings({"source_id": None, "notifications": False, "low_battery_percent": 25})
        self.assertFalse(self.app.store.data["recovery"]["enabled"])
        self.assertIsNone(self.app.store.data["recovery"]["qualification"])

    def test_calendar_change_pauses_retries_preserves_emergency_and_does_not_move_events(self):
        self.supervisor.events["calendar.other"] = []
        self.app.save_settings({"source": "calendar", "calendar_entity_id": "calendar.other", "timezone": "UTC", "enabled": False})
        self.assertTrue(self.app.store.data["recovery"]["enabled"])
        self.assertFalse(self.app.recovery.eligible())
        self.assertTrue(self.app.recovery.protection_eligible())
        self.assertEqual(self.supervisor.created_events, [])

    def test_readonly_calendar_cannot_enable_control(self):
        self.supervisor.calendar_is_writable = False
        with self.assertRaises(UserError): self.app.recovery.save_settings(self.policy)

    def test_missing_remaining_runtime_cannot_enable_control(self):
        self.reading("mains", None)
        with self.assertRaises(UserError): self.app.recovery.save_settings(self.policy)

    def test_provider_cannot_supply_its_own_qualification(self):
        before = self.app.store.data["recovery"]["qualification"]
        self.app.recovery.save_settings({**self.policy, "qualification": {"fake": "claim"}})
        self.assertEqual(self.app.store.data["recovery"]["qualification"], before)

    def test_calendar_write_failure_does_not_arm_or_retry_creation(self):
        with patch.object(self.supervisor, "create_power_event", side_effect=UserError("Offline", "Retry")) as create:
            pending = self.start()
            self.assertIsNone(pending)
            self.assertEqual(self.app.store.data["outage"]["phase"], "blocked")
            self.app.tick()
            self.assertIsNone(self.app.job)
            self.assertEqual(create.call_count, 1)
            self.assertFalse(self.rtc.enabled)

    def test_lost_create_response_is_reconciled_by_readback_without_duplicate(self):
        original = self.supervisor.create_power_event
        def uncertain(*args):
            original(*args)
            raise UserError("Lost response", "Check Calendar")
        with patch.object(self.supervisor, "create_power_event", side_effect=uncertain) as create:
            self.assertTrue(self.start()["retry"])
            self.assertEqual(create.call_count, 1)
            self.assertEqual(len(self.supervisor.created_events), 1)

    def test_final_shutdown_can_protect_host_when_calendar_is_unavailable(self):
        with patch.object(self.supervisor, "create_power_event", side_effect=UserError("Offline", "Retry")):
            self.assertFalse(self.start(runtime=200)["retry"])
            self.finish()
        self.assertEqual(self.supervisor.shutdowns, 2)
        self.assertFalse(self.rtc.enabled)

    def test_calendar_edit_during_countdown_prevents_shutdown(self):
        self.start()
        event = self.supervisor.events["calendar.test_pi"][-1]
        event["end"]["dateTime"] = stamp(self.now+2400)
        self.finish()
        self.assertEqual(self.supervisor.shutdowns, 1)
        self.assertFalse(self.rtc.enabled)

    def test_delete_during_countdown_prevents_shutdown(self):
        self.start()
        self.supervisor.events["calendar.test_pi"].pop()
        self.finish()
        self.assertEqual(self.supervisor.shutdowns, 1)

    def test_ambiguous_host_response_keeps_alarm_and_same_boot_cannot_repeat(self):
        wake = self.start()["wake_epoch"]
        self.supervisor.fail_shutdown = True
        self.finish()
        self.assertTrue(self.rtc.enabled)
        self.assertEqual(self.app.store.data["outage"]["phase"], "paused")
        self.app = self.new_app()
        self.app.refresh()
        self.app.tick()
        self.assertEqual(self.rtc.epoch, wake)
        self.assertTrue(self.rtc.enabled)
        self.assertIsNotNone(self.app.shutdown_requested_at)
        self.assertIsNone(self.app.job)
        self.assertEqual(self.supervisor.shutdowns, 2)

    def test_app_restart_during_countdown_pauses_instead_of_replaying(self):
        self.start()
        self.app = self.new_app()
        self.app.refresh()
        self.app.tick()
        self.assertEqual(self.app.store.data["outage"]["phase"], "paused")
        self.assertIsNone(self.app.job)
        self.assertFalse(self.rtc.enabled)

    def test_claim_write_failure_prevents_event_and_host_request(self):
        self.reading("battery", 1800)
        self.app.tick()
        with patch.object(self.app.store, "save", side_effect=OSError("disk full")):
            self.app.process_task()
        self.assertEqual(self.supervisor.created_events, [])
        self.assertEqual(self.supervisor.shutdowns, 1)

    def test_cancel_consumes_attempt_and_preserves_emergency_after_app_restart(self):
        self.start()
        self.app.cancel()
        self.assertEqual(self.app.store.data["outage"]["attempts"], 1)
        self.reading("battery", 1800)
        self.app.tick()
        self.assertIsNone(self.app.job)
        self.app = self.new_app()
        self.app.refresh()
        self.app.tick()
        self.assertEqual(self.app.store.data["outage"]["attempts"], 1)
        self.assertIsNone(self.app.job)
        self.reading("battery", 100)
        self.app.tick()
        self.app.process_task()
        self.assertTrue(self.app.pending["emergency"])
        self.assertIsNone(self.app.pending["wake_epoch"])

    def test_reboot_after_final_stop_remains_paused_until_stable_utility(self):
        self.start(runtime=100)
        self.finish()
        self.reboot(self.now+60)
        self.app.tick()
        self.assertEqual(self.app.store.data["outage"]["phase"], "paused")
        self.assertIsNone(self.app.job)

    def test_update_preserves_policy_source_and_attempt_counter(self):
        self.start()
        old = deepcopy(self.app.store.data)
        replacement = StateStore(self.temp.name)
        self.assertEqual(replacement.data["recovery"], old["recovery"])
        self.assertEqual(replacement.data["outage"]["attempts"], 1)
        self.assertEqual(replacement.data["schedule"], old["schedule"])

    def test_corrupt_primary_recovery_disables_control(self):
        self.start()
        self.app.store.save()
        self.app.store.path.write_text("corrupt")
        recovered = StateStore(self.temp.name)
        self.assertFalse(recovered.data["recovery"]["enabled"])
        self.assertIsNone(recovered.data["recovery"]["qualification"])

    def test_new_unowned_alarm_is_preserved_without_blocking_emergency_stop(self):
        self.rtc.epoch = self.now+3600
        self.rtc.enabled = True
        self.start(runtime=100)
        self.assertTrue(self.app.pending["emergency"])
        self.assertIsNone(self.app.pending["wake_epoch"])
        self.assertTrue(self.rtc.enabled)
        self.app.tick()
        self.assertEqual(self.supervisor.shutdowns, 2)

    def test_blocked_calendar_retry_still_protects_host_at_critical_reserve(self):
        with patch.object(self.supervisor, "create_power_event", side_effect=UserError("Offline", "Retry")):
            self.start()
        self.reading("battery", 200)
        self.app.tick()
        self.app.process_task()
        self.assertFalse(self.app.pending["retry"])
        self.finish()
        self.assertEqual(self.supervisor.shutdowns, 2)

    def test_runtime_drop_during_countdown_cancels_retry_then_final_stop(self):
        self.start()
        self.reading("battery", 200)
        self.finish()
        self.assertFalse(self.rtc.enabled)
        self.assertEqual(self.supervisor.shutdowns, 1)
        self.app.tick()
        self.app.process_task()
        self.assertFalse(self.app.pending["retry"])

    def test_nut_recovery_uses_explicit_runtime_entity_without_changing_monitor_source(self):
        value = nut_rows(self.now)
        value["rows"].append({**value["rows"][0], "entity_id": "sensor.ups_remaining", "state": "3600",
            "attributes": {"friendly_name": "UPS Battery runtime", "device_class": "duration", "unit_of_measurement": "s"}})
        self.supervisor.power_rows = value
        self.app.refresh_power()
        self.app.save_power_settings({"source_id": "nut:device_apc", "notifications": True, "low_battery_percent": 25})
        self.app.recovery.save_settings({**self.policy, "runtime_entity_id": "sensor.ups_remaining", "expected_source_id": "nut:device_apc"})
        self.assertTrue(self.app.recovery.eligible())
        self.assertEqual(self.app.recovery.source()["runtime_seconds"], 3600)
        self.assertIsNone(self.app.snapshot()["ups"]["selected"]["runtime_seconds"])

    def test_firmware_change_pauses_retries_and_preserves_emergency_protection(self):
        self.host.config = self.host.config.replace("BOOT_UART=1", "BOOT_UART=0")
        self.app.refresh()
        self.assertFalse(self.app.recovery.eligible())
        self.reading("battery", 200)
        self.app.tick()
        self.app.process_task()
        self.assertTrue(self.app.pending["emergency"])
        self.assertIsNone(self.app.pending["wake_epoch"])
        self.assertTrue(self.app.recovery.protection_eligible())

    def test_critical_reserve_skips_calendar_and_countdown_delay(self):
        with patch.object(self.supervisor, "create_power_event") as create:
            pending = self.start(runtime=60)
        self.assertTrue(pending["urgent"])
        self.assertEqual(pending["deadline"], self.mono)
        create.assert_not_called()
        self.app.tick()
        self.assertEqual(self.supervisor.shutdowns, 2)
        self.assertFalse(self.rtc.enabled)

    def test_stale_browser_selection_cannot_qualify_a_different_source(self):
        before = deepcopy(self.app.store.data)
        with self.assertRaises(UserError):
            self.app.recovery.save_settings({**self.policy, "expected_source_id": "nut:someone_else"})
        self.assertEqual(self.app.store.data, before)

    def test_disabling_policy_clears_its_own_native_warning(self):
        self.reading("battery", 7200)
        self.app.tick()
        self.assertIsNotNone(self.supervisor.recovery_notices[-1])
        self.app.recovery.save_settings({**self.policy, "enabled": False, "confirmed_disable_emergency": True})
        self.assertIsNone(self.supervisor.recovery_notices[-1])

    def test_notice_failure_is_throttled_without_blocking_control(self):
        with patch.object(self.supervisor, "recovery_notice", side_effect=UserError("Offline", "Retry")) as notice:
            self.reading("battery", 7200)
            self.app.tick()
            self.app.tick()
            self.assertFalse(self.app.recovery.notices_ok)
            self.assertEqual(notice.call_count, 1)

    def test_firmware_retest_can_run_on_utility_and_turns_recovery_off(self):
        self.host.config = self.host.config.replace("BOOT_UART=1", "BOOT_UART=0")
        self.app.refresh()
        self.begin("test")
        self.assertEqual(self.app.pending["kind"], "test")
        self.assertFalse(self.app.store.data["recovery"]["enabled"])

    def test_separate_manual_test_does_not_bypass_active_outage_policy(self):
        self.reading("battery", 7200)
        self.app.tick()
        self.begin("test")
        self.assertIsNone(self.app.pending)
        self.assertTrue(self.app.store.data["recovery"]["enabled"])

    def test_uncertain_final_shutdown_does_not_claim_an_alarm_or_resume_retries(self):
        self.start(runtime=60)
        self.supervisor.fail_shutdown = True
        self.app.tick()
        self.assertEqual(self.app.store.data["outage"]["phase"], "stopped")
        self.assertIn("No timed wake", self.app.store.data["outage"]["message"])
        self.assertFalse(self.rtc.enabled)
        self.reboot(self.now+60)
        self.app.tick()
        self.assertEqual(self.app.store.data["outage"]["phase"], "paused")
        self.assertIsNone(self.app.job)


class RecoveryServiceTests(unittest.TestCase):
    def test_fixed_native_calendar_create_and_scoped_notice_routes(self):
        supervisor = Supervisor()
        with patch.object(supervisor, "request", return_value={"state": "off", "attributes": {"supported_features": 7}}) as request:
            self.assertTrue(supervisor.calendar_writable("calendar.pi_sleep"))
            supervisor.create_power_event("calendar.pi_sleep", 1791586800, 1791587700, "retry", "a"*32)
            supervisor.recovery_notice({"message": "Retry"})
            supervisor.recovery_notice()
        calls = request.call_args_list
        self.assertEqual(calls[1].args[0], "/core/api/services/calendar/create_event")
        self.assertEqual(calls[1].args[1]["entity_id"], "calendar.pi_sleep")
        self.assertEqual(calls[2].args[1]["notification_id"], "pi5_rtc_wake_ups_recovery")
        self.assertTrue(calls[3].args[0].endswith("/dismiss"))

    def test_unavailable_and_readonly_calendar_are_refused(self):
        for value in ({"state": "unavailable", "attributes": {"supported_features": 7}},
                      {"state": "off", "attributes": {"supported_features": 0}},
                      {"state": "off", "attributes": {"supported_features": True}}):
            with self.subTest(value=value), patch.object(Supervisor, "request", return_value=value):
                with self.assertRaises(UserError): Supervisor().calendar_writable("calendar.pi_sleep")


if __name__ == "__main__": unittest.main()

