from datetime import datetime
import http.client
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "pi5_rtc_wake"))
import rtc_wake as app


def epoch(value):
    return int(datetime.fromisoformat(value).timestamp())


class FakeRTC:
    def __init__(self, clock):
        self.clock = clock
        self.drift = 0
        self.enabled = False
        self.epoch = 0
        self.readback_error = 0
        self.writes = 0
        self.failure = False

    def name(self):
        if self.failure:
            raise OSError("RTC device unavailable")
        return "rpi-rtc soc:rpi_rtc"

    def read_time(self):
        return int(self.clock()) + self.drift

    def read_alarm(self):
        return {"enabled": self.enabled, "epoch": self.epoch}

    def set_alarm(self, when):
        self.writes += 1
        self.enabled = True
        self.epoch = when + self.readback_error

    def clear_alarm(self):
        self.enabled = False


class ControllerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.now = epoch("2026-10-09T16:44:50+00:00")
        self.tick = 100.0
        self.rtc = FakeRTC(lambda: self.now)
        self.ownership = Path(self.temp.name) / "owned.json"
        self.controller = self.make_controller()

    def make_controller(self, configured=True):
        return app.Controller(
            self.rtc, firmware_configured=configured, ownership_file=self.ownership,
            clock=lambda: self.now, monotonic=lambda: self.tick,
        )

    def arm(self, request="test-1", **updates):
        payload = {"mode": "relative", "seconds": 600, "request_id": request,
                   "timezone": "America/Chicago"}
        payload.update(updates)
        return self.controller.arm(payload)

    def verify(self, result, **updates):
        payload = {"request_id": result["request_id"], "wake_epoch": result["wake_epoch"]}
        payload.update(updates)
        return self.controller.verify(payload)

    def test_shutdown_ack_requires_fresh_matching_alarm(self):
        result = self.arm()
        checked = self.verify(result)
        self.assertTrue(checked["shutdown_allowed"])
        self.assertEqual(checked["wake_epoch"], self.now + 600)
        self.assertEqual(result["wake_local"], "2026-10-09T11:54:50-05:00")

    def test_firmware_setup_required_before_any_write(self):
        self.controller = self.make_controller(configured=False)
        with self.assertRaises(app.PolicyError):
            self.arm()
        self.assertEqual(self.rtc.writes, 0)
        self.assertEqual(self.controller.status()["status"], "needs_firmware_setup")

    def test_clock_mismatch_blocks_writes(self):
        self.rtc.drift = 60
        with self.assertRaises(app.PolicyError):
            self.arm()
        self.assertEqual(self.rtc.writes, 0)

    def test_clock_changes_after_arm_block_shutdown(self):
        result = self.arm()
        self.rtc.drift = -60
        with self.assertRaises(app.PolicyError):
            self.verify(result)

    def test_short_negative_and_past_requests_are_rejected(self):
        for seconds in (-100, 0, 60, 179):
            with self.subTest(seconds=seconds), self.assertRaises(app.PolicyError):
                self.arm(seconds=seconds)
        self.assertEqual(self.rtc.writes, 0)

    def test_non_integer_intervals_are_rejected(self):
        for seconds in (True, False, "600", 600.0, None, []):
            with self.subTest(seconds=seconds), self.assertRaises(app.PolicyError):
                self.arm(seconds=seconds)

    def test_excessive_duration_is_rejected(self):
        with self.assertRaises(app.PolicyError):
            self.arm(seconds=app.MAX_WAKE_SECONDS + 1)

    def test_absolute_calendar_end_is_programmed_and_verified_exactly(self):
        wake = self.now + 3600
        result = self.arm(mode="at", wake_epoch=wake)
        self.assertEqual(self.rtc.epoch, wake)
        self.assertEqual(self.verify(result)["wake_epoch"], wake)

    def test_absolute_end_requires_an_integer_epoch_within_wake_bounds(self):
        for wake in (True, "1791565200", self.now + 3600.0, self.now - 1, self.now + app.MIN_WAKE_SECONDS - 1, self.now + app.MAX_WAKE_SECONDS + 1):
            with self.subTest(wake=wake), self.assertRaises(app.PolicyError):
                self.arm(mode="at", wake_epoch=wake)
        self.assertEqual(self.rtc.writes, 0)

    def test_absolute_calendar_alarm_preserves_another_programs_alarm(self):
        self.rtc.enabled, self.rtc.epoch = True, self.now + 1200
        with self.assertRaises(app.PolicyError):
            self.arm(mode="at", wake_epoch=self.now + 3600)
        self.assertEqual(self.rtc.epoch, self.now + 1200)
        self.assertEqual(self.rtc.writes, 0)

    def test_invalid_timezone_rejected_before_write(self):
        with self.assertRaises(app.PolicyError):
            self.arm(timezone="Imaginary/City")
        self.assertEqual(self.rtc.writes, 0)

    def test_numeric_request_identifier_is_rejected(self):
        with self.assertRaises(app.PolicyError):
            self.arm(request=123.456)

    def test_external_future_alarm_is_preserved(self):
        self.rtc.enabled = True
        self.rtc.epoch = self.now + 1000
        with self.assertRaises(app.PolicyError):
            self.arm()
        self.assertEqual(self.rtc.writes, 0)
        self.assertEqual(self.rtc.epoch, self.now + 1000)

    def test_owned_alarm_can_be_replaced(self):
        self.arm()
        replacement = self.arm(request="test-2", seconds=900)
        self.assertEqual(replacement["wake_epoch"], self.now + 900)

    def test_owned_alarm_survives_restart_but_ack_does_not(self):
        result = self.arm()
        self.controller = self.make_controller()
        with self.assertRaises(app.PolicyError):
            self.verify(result)
        self.arm(request="new-process")

    def test_readback_mismatch_never_acknowledges(self):
        self.rtc.readback_error = 30
        with self.assertRaises(app.PolicyError):
            self.arm()
        self.assertIsNone(self.controller.transaction)

    def test_disabled_alarm_blocks_final_ack(self):
        result = self.arm()
        self.rtc.enabled = False
        with self.assertRaises(app.PolicyError):
            self.verify(result)

    def test_external_alarm_change_blocks_final_ack(self):
        result = self.arm()
        self.rtc.epoch += 60
        with self.assertRaises(app.PolicyError):
            self.verify(result)

    def test_wrong_id_blocks_final_ack(self):
        result = self.arm()
        with self.assertRaises(app.PolicyError):
            self.verify(result, request_id="another-request")

    def test_wrong_epoch_blocks_final_ack(self):
        result = self.arm()
        with self.assertRaises(app.PolicyError):
            self.verify(result, wake_epoch=result["wake_epoch"] + 1)

    def test_expired_ack_blocks_shutdown(self):
        result = self.arm()
        self.tick += app.TRANSACTION_LIFETIME + 1
        with self.assertRaises(app.PolicyError):
            self.verify(result)

    def test_new_arm_invalidates_old_ack(self):
        old = self.arm()
        self.arm(request="new-request")
        with self.assertRaises(app.PolicyError):
            self.verify(old)

    def test_failed_new_request_invalidates_old_ack(self):
        old = self.arm()
        with self.assertRaises(app.PolicyError):
            self.arm(request="new-request", seconds=1)
        with self.assertRaises(app.PolicyError):
            self.verify(old)

    def test_approaching_alarm_blocks_shutdown(self):
        result = self.arm()
        self.now += 481
        with self.assertRaises(app.PolicyError):
            self.verify(result)

    def test_cancel_only_clears_current_owned_alarm(self):
        result = self.arm()
        self.assertTrue(self.controller.clear({"request_id": result["request_id"]})["cleared"])
        self.assertFalse(self.rtc.enabled)
        with self.assertRaises(app.PolicyError):
            self.verify(result)

    def test_cancel_preserves_alarm_changed_externally(self):
        result = self.arm()
        self.rtc.epoch += 60
        with self.assertRaises(app.PolicyError):
            self.controller.clear({"request_id": result["request_id"]})
        self.assertTrue(self.rtc.enabled)

    def test_device_failure_is_reported_without_success(self):
        self.rtc.failure = True
        self.assertEqual(self.controller.status()["status"], "error")
        with self.assertRaises(OSError):
            self.arm()


class CalendarTests(unittest.TestCase):
    def test_daily_wake_same_day(self):
        self.assertEqual(
            app.next_daily_epoch("17:00:00", "America/Chicago", epoch("2026-10-09T16:44:50Z")),
            epoch("2026-10-09T22:00:00Z"),
        )

    def test_daily_wake_rolls_to_tomorrow(self):
        self.assertEqual(
            app.next_daily_epoch("07:00:00", "America/Chicago", epoch("2026-10-10T04:00:00Z")),
            epoch("2026-10-10T12:00:00Z"),
        )

    def test_fall_transition_is_25_hours_not_24(self):
        wake = app.next_daily_epoch("07:00", "America/Chicago", epoch("2026-10-31T12:00:00Z"))
        self.assertEqual(wake, epoch("2026-11-01T13:00:00Z"))

    def test_ambiguous_hour_chooses_first_future_occurrence(self):
        before = epoch("2026-11-01T05:00:00Z")
        between = epoch("2026-11-01T06:45:00Z")
        self.assertEqual(app.next_daily_epoch("01:30", "America/Chicago", before),
                         epoch("2026-11-01T06:30:00Z"))
        self.assertEqual(app.next_daily_epoch("01:30", "America/Chicago", between),
                         epoch("2026-11-01T07:30:00Z"))

    def test_spring_transition_is_23_hours_not_24(self):
        wake = app.next_daily_epoch("07:00", "America/Chicago", epoch("2027-03-13T13:00:00Z"))
        self.assertEqual(wake, epoch("2027-03-14T12:00:00Z"))

    def test_nonexistent_spring_time_is_rejected(self):
        with self.assertRaises(app.PolicyError):
            app.next_daily_epoch("02:30", "America/Chicago", epoch("2027-03-14T07:00:00Z"))

    def test_invalid_times_are_rejected(self):
        for value in ("24:00", "09:70", "bad", "00:00:99", None, 700):
            with self.subTest(value=value), self.assertRaises(app.PolicyError):
                app.next_daily_epoch(value, "America/Chicago", epoch("2026-10-09T16:44:50Z"))

    def test_linux_utc_field_conversion(self):
        for when in (0, epoch("2026-10-09T16:44:50Z"), epoch("2028-02-29T23:59:59Z")):
            with self.subTest(when=when):
                self.assertEqual(app.fields_epoch(app.rtc_fields(when)), when)

    def test_invalid_device_date_is_not_normalized(self):
        with self.assertRaises(ValueError):
            app.fields_epoch((0, 0, 0, 32, 0, 126, 0, 0, 0))


