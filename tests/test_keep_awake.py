"""Persistent suspension of every app power path, with simulated hardware."""

from copy import deepcopy
import unittest
from unittest.mock import patch

from test_calendar_schedule import Fixture, event
from rtc_wake import PolicyError
from state import StateStore, UserError
from phone_messages import build_message


class KeepAwakeTests(unittest.TestCase, Fixture):
    def setUp(self):
        self.setup_app()
        self.pass_test()
        self.enable()

    def pause(self):
        self.app.dashboard.action("keep-awake", {"active": True, "confirmed": True})

    def resume(self):
        self.app.dashboard.action("keep-awake", {"active": False, "confirmed": True})

    def test_pause_survives_restart_and_preserves_all_saved_choices_and_dates(self):
        original = deepcopy(self.app.store.data)
        dates = deepcopy(self.supervisor.events)
        self.pause()
        self.app = self.new_app()
        self.app.refresh()
        self.assertTrue(self.app.snapshot()["keep_awake"])
        self.assertFalse(self.app.snapshot()["schedule_active"])
        self.assertIsNone(self.app.snapshot()["next_sleep_epoch"])
        for key in ("schedule", "recovery", "ups", "test", "messages", "assist", "dashboard", "preparation"):
            self.assertEqual(self.app.store.data[key], original[key])
        self.assertEqual(self.supervisor.events, dates)
        self.resume()
        self.assertFalse(StateStore(self.temp.name).data["keep_awake"])
        self.assertTrue(self.app.snapshot()["schedule_active"])

    def test_paused_calendar_dates_are_not_claimed_or_replayed_after_resume(self):
        self.supervisor.events["calendar.test_pi"] = [event(self.now + 10, self.now + 3610), event(self.now + 4000, self.now + 8000)]
        self.app.refresh_calendar()
        self.pause()
        self.advance(80)
        self.app.refresh()
        self.app.tick()
        self.assertIsNone(self.app.job)
        self.assertNotIn("last_calendar_attempt", self.app.store.data)
        self.resume()
        self.app.tick()
        self.assertIsNone(self.app.job)
        self.advance(3920)
        self.app.refresh()
        self.app.tick()
        self.assertEqual(self.app.job["kind"], "schedule")

    def test_pause_cancels_countdown_and_its_owned_alarm(self):
        self.app.begin_job("test", {"confirmed": True})
        self.app.process_task()
        self.assertTrue(self.rtc.enabled)
        self.pause()
        self.assertIsNone(self.app.pending)
        self.assertFalse(self.rtc.enabled)
        self.advance(31)
        self.app.tick()
        self.assertEqual(self.supervisor.shutdowns, 1)  # Only the earlier commissioning test.

    def test_save_failure_does_not_cancel_a_countdown_or_change_the_alarm(self):
        self.app.begin_job("test", {"confirmed": True})
        self.app.process_task()
        pending = deepcopy(self.app.pending)
        with patch.object(self.app.store, "save", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                self.pause()
        self.assertFalse(self.app.store.data["keep_awake"])
        self.assertEqual(self.app.pending, pending)
        self.assertTrue(self.rtc.enabled)

    def test_alarm_clear_failure_still_persists_suspension(self):
        self.app.begin_job("test", {"confirmed": True})
        self.app.process_task()
        with patch.object(self.app.controller, "clear", side_effect=PolicyError("RTC unavailable")):
            self.pause()
        self.assertTrue(StateStore(self.temp.name).data["keep_awake"])
        self.assertIsNone(self.app.pending)
        self.assertTrue(self.app.message["error"])
        self.advance(31)
        self.app.tick()
        self.assertEqual(self.supervisor.shutdowns, 1)

    def test_queued_power_jobs_are_cancelled_even_if_resumed_before_worker_runs(self):
        for kind in ("test", "reboot"):
            with self.subTest(kind=kind):
                before = self.rtc.writes
                self.app.begin_job(kind, {"confirmed": True, "dashboard_reviewed": True})
                self.pause()
                self.resume()
                self.app.process_task()
                self.assertIsNone(self.app.pending)
                self.assertEqual(self.rtc.writes, before)
                self.assertEqual(self.supervisor.reboots, 0)
                self.assertTrue(self.app.store.data["schedule"]["enabled"])

    def test_new_manual_ai_and_automatic_power_jobs_cannot_bypass_pause(self):
        self.pause()
        for kind in ("test", "reboot", "sleep", "schedule", "ups"):
            with self.subTest(kind=kind), self.assertRaises(UserError):
                self.app.begin_job(kind, {"confirmed": True, "assist_reviewed": True})
        self.app.begin_job("check", {})
        self.app.process_task()
        self.assertTrue(self.app.checks["ok"])

    def test_an_already_submitted_shutdown_cannot_be_cancelled_or_clear_the_alarm(self):
        self.app.begin_job("test", {"confirmed": True})
        self.app.process_task()
        self.supervisor.fail_shutdown = True
        self.advance(30)
        self.app.tick()
        self.assertIsNotNone(self.app.shutdown_requested_at)
        with self.assertRaises(UserError):
            self.pause()
        self.assertFalse(self.app.store.data["keep_awake"])
        self.assertTrue(self.rtc.enabled)

    def test_confirmation_and_boolean_are_required_for_both_directions(self):
        for payload in ({}, {"active": True}, {"active": True, "confirmed": False},
                        {"active": "true", "confirmed": True}, {"active": False, "confirmed": True, "extra": 1}):
            with self.subTest(payload=payload), self.assertRaises(UserError):
                self.app.dashboard.action("keep-awake", payload)
        self.assertFalse(self.app.store.data["keep_awake"])

    def test_schema_nine_migration_defaults_to_running_without_replacing_choices(self):
        saved = deepcopy(self.app.store.data)
        self.app.store.data["schema_version"] = 9
        self.app.store.data.pop("keep_awake")
        self.app.store.save()
        restored = StateStore(self.temp.name)
        self.assertFalse(restored.data["keep_awake"])
        for key in ("schedule", "test", "recovery", "messages", "assist", "dashboard"):
            self.assertEqual(restored.data[key], saved[key])

    def test_phone_status_explains_global_pause_without_claiming_a_next_shutdown(self):
        self.pause()
        body, current = build_message(self.app.snapshot(), [], {}, {}, self.now, self.host.started)
        self.assertTrue(current)
        self.assertIn("Keep awake is on", body["message"])
        self.assertIn("including UPS protection", body["message"])
        self.assertNotIn("check Setup", body["message"])
