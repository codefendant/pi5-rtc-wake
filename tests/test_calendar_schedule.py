from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "pi5_rtc_wake"))
import calendar_schedule as calendar
from services import Supervisor
from state import StateStore, UserError, atomic_json, validate_schedule
from test_rtc_wake import epoch
from test_setup import CONFIG, Fixture

ENTITY = "calendar.pi_sleep"


def event(start, end, title="Pi off"):
    as_text = lambda value: datetime.fromtimestamp(value, timezone.utc).isoformat()
    return {"summary": title, "start": {"dateTime": as_text(start)}, "end": {"dateTime": as_text(end)}}


class EventTests(unittest.TestCase):
    def setUp(self):
        self.now = epoch("2026-10-09T17:00:00Z")

    def parse(self, events):
        return calendar.parse_periods(events, ENTITY, self.now)

    def test_expanded_recurrences_are_sorted_and_keep_absolute_end_times(self):
        first = event(self.now + 60, self.now + 3660)
        second = event(self.now + 86460, self.now + 90060)
        periods = self.parse([second, first])
        self.assertEqual([row["start_epoch"] for row in periods], [self.now + 60, self.now + 86460])
        self.assertEqual(periods[0]["end_epoch"], self.now + 3660)
        self.assertNotEqual(periods[0]["attempt_key"], periods[1]["attempt_key"])

    def test_autumn_repeated_hour_uses_explicit_calendar_offsets(self):
        value = {"summary": "Clock change", "start": {"dateTime": "2026-11-01T01:10:00-05:00"}, "end": {"dateTime": "2026-11-01T01:40:00-06:00"}}
        period = self.parse([value])[0]
        self.assertEqual(period["start_epoch"], epoch("2026-11-01T06:10:00Z"))
        self.assertEqual(period["end_epoch"] - period["start_epoch"], 90 * 60)

    def test_spring_clock_change_uses_native_calendar_instants(self):
        value = {"start": {"dateTime": "2027-03-14T01:30:00-06:00"}, "end": {"dateTime": "2027-03-14T03:30:00-05:00"}}
        period = self.parse([value])[0]
        self.assertEqual(period["end_epoch"] - period["start_epoch"], 3600)

    def test_cancelled_and_completed_events_are_ignored(self):
        self.assertEqual(self.parse([{"status": "cancelled"}, event(self.now - 1200, self.now - 60)]), [])

    def test_all_day_event_explains_how_to_fix_it(self):
        with self.assertRaises(UserError) as raised:
            self.parse([{"start": {"date": "2026-10-10"}, "end": {"date": "2026-10-11"}}])
        self.assertIn("All day", raised.exception.action)

    def test_missing_offset_fractional_second_and_unreadable_time_are_rejected(self):
        for text in ("2026-10-10T20:00:00", "2026-10-10T20:00:00.1Z", "not a time", None):
            value = event(self.now + 60, self.now + 3660)
            value["start"]["dateTime"] = text
            with self.subTest(text=text), self.assertRaises(UserError): self.parse([value])

    def test_short_long_and_reversed_off_periods_are_rejected(self):
        for duration in (-600, 0, 599, 7 * 86400 + 1):
            with self.subTest(duration=duration), self.assertRaises(UserError):
                self.parse([event(self.now + 60, self.now + 60 + duration)])

    def test_overlapping_and_touching_periods_require_a_single_event_or_gap(self):
        for next_start in (self.now + 1800, self.now + 3660):
            with self.subTest(next_start=next_start), self.assertRaises(UserError) as raised:
                self.parse([event(self.now + 60, self.now + 3660), event(next_start, next_start + 3600)])
            self.assertIn("gap", raised.exception.action)

    def test_large_or_unreadable_response_is_rejected(self):
        for events in ({"events": []}, [event(self.now, self.now + 600)] * 257, [None]):
            with self.subTest(kind=type(events)), self.assertRaises(UserError): self.parse(events)

    def test_due_period_has_no_late_catch_up(self):
        period = self.parse([event(self.now + 60, self.now + 3660)])[0]
        self.assertIsNone(calendar.due_period([period], self.now))
        self.assertEqual(calendar.due_period([period], self.now + 119), period)
        self.assertIsNone(calendar.due_period([period], self.now + 120))

    def test_wake_edit_changes_verification_key_but_not_attempt_identity(self):
        before = self.parse([event(self.now + 60, self.now + 3660)])[0]
        after = self.parse([event(self.now + 60, self.now + 4260)])[0]
        self.assertNotEqual(before["key"], after["key"])
        self.assertEqual(before["attempt_key"], after["attempt_key"])


class CalendarSchedulingTests(unittest.TestCase, Fixture):
    def setUp(self):
        self.setup_app()
        self.pass_test()
        self.supervisor.shutdowns = 0
        self.start, self.end = self.now + 120, self.now + 3720
        self.supervisor.calendar_list = [{"entity_id": ENTITY, "name": "Pi Sleep"}]
        self.supervisor.events[ENTITY] = [event(self.start, self.end)]
        self.app.refresh(force_calendar_discovery=True)

    def select_calendar(self, enabled=True):
        value = {**self.app.store.data["schedule"], "source": "calendar", "calendar_entity_id": ENTITY, "enabled": enabled}
        self.app.save_settings(value)

    def begin_period(self):
        self.select_calendar()
        self.advance(self.start - self.now)
        self.app.refresh()
        self.app.tick()
        self.app.process_task()
        self.assertIsNotNone(self.app.pending)

    def test_calendar_sets_exact_end_alarm_then_rechecks_before_shutdown(self):
        self.begin_period()
        self.assertEqual(self.rtc.epoch, self.end)
        self.assertEqual(self.app.pending["wake_epoch"], self.end)
        with patch.object(self.supervisor, "calendar_events", wraps=self.supervisor.calendar_events) as fetch:
            self.advance(30)
            self.app.tick()
            fetch.assert_called_once()
        self.assertEqual(self.supervisor.shutdowns, 1)
        self.assertTrue(self.rtc.enabled)

    def test_saved_calendar_and_confirmation_survive_an_app_update(self):
        self.select_calendar()
        replacement = self.new_app()
        replacement.refresh()
        status = replacement.snapshot()
        self.assertEqual(status["schedule"]["calendar_entity_id"], ENTITY)
        self.assertTrue(status["schedule_active"])
        self.assertEqual(status["test_status"], "passed")
        self.assertEqual(status["next_sleep_epoch"], self.start)
        self.assertEqual(status["next_wake_epoch"], self.end)

    def test_saving_calendar_off_shows_periods_immediately_without_enabling(self):
        self.select_calendar(False)
        status = self.app.snapshot()
        self.assertFalse(status["schedule"]["enabled"])
        self.assertTrue(status["calendar"]["ok"])
        self.assertEqual(status["calendar"]["periods"][0]["start_epoch"], self.start)

    def test_empty_calendar_is_enabled_and_waits_without_shutting_down(self):
        self.supervisor.events[ENTITY] = []
        self.select_calendar()
        self.assertTrue(self.app.snapshot()["schedule_active"])
        self.assertIsNone(self.app.snapshot()["next_sleep_epoch"])
        self.app.tick()
        self.assertTrue(self.app.tasks.empty())

    def test_native_calendar_outage_pauses_schedule_without_failing_hardware_checks(self):
        self.enable()
        with patch.object(self.supervisor, "calendars", side_effect=UserError("Calendar offline", "Retry later")):
            self.app.refresh(force_calendar_discovery=True)
        self.assertFalse(self.app.snapshot()["schedule_active"])
        self.assertFalse(self.app.calendar_info["ok"])
        self.assertTrue(self.app.checks["ok"])

    def test_repeating_calendar_summary_has_paired_shutdown_and_wake(self):
        self.enable("23:00", "07:00")
        status = self.app.snapshot()
        self.assertEqual(status["next_sleep_epoch"], epoch("2026-10-10T04:00:00Z"))
        self.assertEqual(status["next_wake_epoch"], epoch("2026-10-10T12:00:00Z"))

    def test_outage_before_arm_keeps_pi_on_without_an_alarm_write(self):
        self.select_calendar()
        self.advance(120)
        self.app.refresh()
        before = self.rtc.writes
        self.app.tick()
        with patch.object(self.supervisor, "calendar_events", side_effect=UserError("Calendar offline", "Retry later")):
            self.app.process_task()
        self.assertIsNone(self.app.pending)
        self.assertEqual(self.rtc.writes, before)
        self.assertEqual(self.supervisor.shutdowns, 0)

    def test_deleted_event_during_countdown_clears_owned_alarm_and_stays_on(self):
        self.begin_period()
        self.supervisor.events[ENTITY] = []
        self.advance(30)
        self.app.tick()
        self.assertFalse(self.rtc.enabled)
        self.assertIsNone(self.app.pending)
        self.assertEqual(self.supervisor.shutdowns, 0)

    def test_changed_wake_during_countdown_cancels_without_retrying_same_start(self):
        self.begin_period()
        self.supervisor.events[ENTITY] = [event(self.start, self.end + 600)]
        self.advance(30)
        self.app.tick()
        self.assertFalse(self.rtc.enabled)
        self.assertEqual(self.supervisor.shutdowns, 0)
        self.app.tick()
        self.assertTrue(self.app.tasks.empty())

    def test_api_failure_during_countdown_cancels_and_clears_owned_alarm(self):
        self.begin_period()
        self.advance(30)
        with patch.object(self.supervisor, "calendar_events", side_effect=UserError("Calendar offline", "Retry later")):
            self.app.tick()
        self.assertFalse(self.rtc.enabled)
        self.assertEqual(self.supervisor.shutdowns, 0)
        self.assertFalse(self.app.snapshot()["schedule_active"])

    def test_keep_awake_and_restart_do_not_retry_the_occurrence(self):
        self.begin_period()
        self.app.cancel()
        self.advance(10)
        self.app = self.new_app()
        self.app.refresh()
        self.app.tick()
        self.assertTrue(self.app.tasks.empty())
        self.assertEqual(self.supervisor.shutdowns, 0)
        self.assertFalse(self.rtc.enabled)

    def test_next_expanded_recurrence_can_run_after_previous_was_cancelled(self):
        self.supervisor.events[ENTITY].append(event(self.start + 86400, self.end + 86400))
        self.begin_period()
        self.app.cancel()
        self.advance(86400)
        self.app.refresh()
        self.app.tick()
        self.app.process_task()
        self.assertEqual(self.app.pending["wake_epoch"], self.end + 86400)

    def test_missed_or_stale_calendar_period_is_not_started(self):
        self.select_calendar()
        self.advance(180)
        self.app.refresh()
        self.app.tick()
        self.assertTrue(self.app.tasks.empty())
        self.assertEqual(self.supervisor.shutdowns, 0)

    def test_invalid_calendar_cannot_replace_working_calendar_selection(self):
        self.enable("22:15", "06:45")
        saved = deepcopy(self.app.store.data["schedule"])
        self.supervisor.events[ENTITY] = [{"start": {"date": "2026-10-10"}, "end": {"date": "2026-10-11"}}]
        with self.assertRaises(UserError): self.select_calendar()
        self.assertEqual(self.app.store.data["schedule"], saved)

    def test_disabling_calendar_works_when_core_calendar_api_is_offline(self):
        self.select_calendar()
        with patch.object(self.supervisor, "calendar_events", side_effect=UserError("Calendar offline", "Retry later")):
            self.select_calendar(False)
        self.assertFalse(self.app.store.data["schedule"]["enabled"])

    def test_manual_shutdown_cannot_bypass_calendar_event_times(self):
        self.select_calendar()
        before = self.rtc.writes
        self.begin("sleep")
        self.assertEqual(self.rtc.writes, before)
        self.assertIsNone(self.app.pending)
        self.assertIn("calendar", self.app.message["text"])

    def test_check_again_discovers_a_new_native_calendar_immediately(self):
        self.supervisor.calendar_list.append({"entity_id": "calendar.new_pi", "name": "New Pi"})
        self.begin("check")
        self.assertEqual(len(self.app.calendar_info["calendars"]), 2)

    def test_schema_two_daily_times_pause_and_test_evidence_is_preserved(self):
        before = deepcopy(self.app.store.data)
        before["schema_version"] = 2
        before["schedule"] = {"sleep_time": "23:00", "wake_time": "07:00", "timezone": "America/Chicago", "enabled": True}
        atomic_json(self.app.store.path, before)
        store = StateStore(self.temp.name)
        self.assertEqual(store.data["schema_version"], 6)
        self.assertFalse(store.data["schedule"]["enabled"])
        self.assertNotIn("sleep_time", store.data["schedule"])
        self.assertIn("23:00", store.data["migration_notice"])
        self.assertEqual(store.data["test"], before["test"])


class RebootNoticeTests(unittest.TestCase, Fixture):
    def setUp(self): self.setup_app()

    def test_preparation_notifies_immediately_and_successful_reboot_clears(self):
        self.host.config = CONFIG.replace("POWER_OFF_ON_HALT=1", "POWER_OFF_ON_HALT=0")
        self.begin("prepare")
        self.assertEqual(self.supervisor.notices, [False, True])
        self.host.config = self.host.proposed
        self.host.pending = False
        self.host.identity = "new-boot"
        self.app.refresh()
        self.assertEqual(self.supervisor.notices, [False, True, False])
        self.assertFalse(self.app.store.data["preparation"]["reboot_required"])

    def test_host_check_failure_does_not_dismiss_a_known_reboot_requirement(self):
        self.supervisor.firmware["update_pending"] = True
        self.app.refresh()
        with patch.object(self.host, "inspect", side_effect=UserError("Host unreadable", "Check again")):
            self.app.refresh()
        self.assertEqual(self.supervisor.notices, [False, True])
        self.assertTrue(self.app.checks["needs_reboot"])

    def test_unreadable_first_check_after_restart_keeps_existing_reminder(self):
        self.app = self.new_app()
        self.supervisor.notices.clear()
        with patch.object(self.host, "inspect", side_effect=UserError("Host unreadable", "Check again")):
            self.app.refresh()
        self.assertEqual(self.supervisor.notices, [])

    def test_notification_failure_does_not_block_test_and_retries_later(self):
        self.supervisor.firmware["update_pending"] = True
        with patch.object(self.supervisor, "reboot_notice", side_effect=UserError("Core offline", "Check again")) as send:
            self.app.refresh()
            self.app.refresh()
            self.assertEqual(send.call_count, 1)
        self.assertFalse(self.app.reboot_notice_ok)
        self.advance(60)
        self.app.refresh()
        self.assertTrue(self.app.reboot_notice_ok)
        self.supervisor.firmware["update_pending"] = False
        self.app.refresh()
        self.assertTrue(self.app.checks["ok"])


class NativeApiTests(unittest.TestCase):
    def setUp(self): self.supervisor = Supervisor()

    def test_calendar_events_use_bounded_encoded_utc_window_and_core_proxy(self):
        now = epoch("2026-10-09T17:00:00Z")
        with patch.object(self.supervisor, "request", return_value=[]) as request:
            self.assertEqual(self.supervisor.calendar_events(ENTITY, now), [])
        url = urlsplit(request.call_args.args[0])
        self.assertEqual(url.path, "/core/api/calendars/" + ENTITY)
        query = parse_qs(url.query)
        self.assertEqual(epoch(query["start"][0]), now - 60)
        self.assertEqual(epoch(query["end"][0]), now + 31 * 86400)

    def test_calendar_entity_path_injection_is_refused_before_api_call(self):
        for value in ("calendar.pi?start=bad", "../config", "calendar.pi/../config", None):
            with self.subTest(value=value), patch.object(self.supervisor, "request") as request:
                with self.assertRaises(UserError): self.supervisor.calendar_events(value, 1000)
                request.assert_not_called()

    def test_reboot_notice_uses_only_its_own_persistent_notification(self):
        with patch.object(self.supervisor, "request", return_value=[]) as request:
            self.supervisor.reboot_notice(True)
            self.supervisor.reboot_notice(False)
        create, dismiss = request.call_args_list
        self.assertEqual(create.args[0], "/core/api/services/persistent_notification/create")
        self.assertEqual(dismiss.args[0], "/core/api/services/persistent_notification/dismiss")
        self.assertEqual(create.args[1]["notification_id"], dismiss.args[1]["notification_id"])
        self.assertEqual(list(dismiss.args[1]), ["notification_id"])

    def test_core_json_list_is_not_treated_as_a_supervisor_envelope(self):
        events = [event(1791565200, 1791568800)]
        self.supervisor.token = "simulated-token"
        with patch("services.urllib.request.urlopen") as open_url:
            open_url.return_value.__enter__.return_value.read.return_value = json.dumps(events).encode()
            result = self.supervisor.calendar_events(ENTITY, 1791565100)
        self.assertEqual(result, events)
        request = open_url.call_args.args[0]
        self.assertTrue(request.full_url.startswith("http://supervisor/core/api/calendars/"))
        self.assertIsNone(request.data)


if __name__ == "__main__": unittest.main()
