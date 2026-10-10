from copy import deepcopy
from datetime import datetime, timedelta
import hashlib
import http.client
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from zoneinfo import ZoneInfo
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "pi5_rtc_wake"))
import host_helper
import server
from services import HostError
from state import StateStore, UserError, atomic_json
from test_rtc_wake import FakeRTC, epoch
from rtc_wake import next_daily_epoch

CONFIG = "[all]\n# Keep SSD first\nBOOT_ORDER=0xf416\nBOOT_UART=1\nPOWER_OFF_ON_HALT=1\nWAKE_ON_GPIO=0\n"


class FakeSupervisor:
    def __init__(self):
        # HAOS rpi5-64/meta: BOARD_ID is the /os/info board value;
        # SUPERVISOR_MACHINE=raspberrypi5-64 belongs in the app manifest.
        self.os = {"version": "18.0", "board": "rpi5-64"}
        self.firmware = {"current_version": "1778498402", "latest_version": "1778498402", "update_available": False, "update_pending": False, "update_blocked": False}
        self.shutdowns = 0
        self.reboots = 0
        self.fail_shutdown = False
        self.calendar_list = []
        self.events = {}
        self.notices = []
        self.power_rows = {"rows": []}
        self.power_notices = []
        self.recovery_notices = []
        self.created_events = []
        self.calendar_is_writable = True
        self.sensor_registry = []
        self.enabled_sensors = []
        self.shutdown_owner = {"state": "not_found", "addon_id": None, "message": "Simulated: no local host-shutdown controller."}

    def os_info(self): return deepcopy(self.os)
    def firmware_info(self): return deepcopy(self.firmware)
    def timezone(self): return "America/Chicago"
    def calendars(self): return deepcopy(self.calendar_list)
    def calendar_events(self, entity_id, now):
        if entity_id not in self.events:
            raise UserError("The calendar could not be read.", "Select an available calendar.")
        return deepcopy(self.events[entity_id])
    def reboot_notice(self, required): self.notices.append(required)
    def power_sources(self): return deepcopy(self.power_rows)
    def nut_sensors(self): return deepcopy(self.sensor_registry)
    def shutdown_controller(self): return deepcopy(self.shutdown_owner)
    def enable_nut_sensor(self, device_id, entity_id):
        row = next((row for row in self.sensor_registry if row["device_id"] == device_id and row["entity_id"] == entity_id and row["can_enable"]), None)
        if row is None: raise UserError("Wrong sensor", "Scan again")
        row.update(disabled_by=None, can_enable=False)
        self.enabled_sensors.append(entity_id)
        return {"require_restart": False}
    def power_notice(self, notice=None): self.power_notices.append(deepcopy(notice))
    def recovery_notice(self, notice=None): self.recovery_notices.append(deepcopy(notice))
    def calendar_writable(self, entity_id):
        if not self.calendar_is_writable or entity_id not in self.events:
            raise UserError("Calendar cannot create events.", "Choose a writable Local Calendar.")
        return True
    def create_power_event(self, entity_id, start, end, kind, token):
        self.calendar_writable(entity_id)
        stamp = lambda value: datetime.fromtimestamp(value, ZoneInfo("UTC")).isoformat()
        event = {"summary": "UPS retry" if kind == "retry" else "UPS final shutdown", "description": "Pi Wake & Sleep UPS v1:" + kind + ":" + token,
                 "start": {"dateTime": stamp(start)}, "end": {"dateTime": stamp(end)}}
        self.events[entity_id].append(event)
        self.created_events.append(deepcopy(event))
    def shutdown(self):
        self.shutdowns += 1
        if self.fail_shutdown:
            raise UserError("Request timed out.", "Try later.")
    def reboot(self): self.reboots += 1


class FakeHost:
    def __init__(self, now):
        self.config = CONFIG
        self.version = "1778498402"
        self.image_version = self.version
        self.pending = False
        self.identity = "boot-a"
        self.started = now - 3600
        self.applies = 0

    def inspect(self):
        values = host_helper.config_values(self.config)
        return {"config": self.config, "config_sha256": host_helper.sha(self.config), "config_fingerprint": host_helper.sha(json.dumps(values, sort_keys=True)), "editable": True,
                "wake_configured": all(values.get(k) == v for k, v in host_helper.WAKE_SETTINGS.items()), "current_version": self.version,
                "image_version": self.image_version, "image_sha256": "abc123", "image": "/usr/lib/firmware/raspberrypi/bootloader-2712/default/pieeprom-2026-05-11.bin", "pending": self.pending}

    def apply(self, snapshot):
        self.applies += 1
        self.proposed = host_helper.patched_config(self.config)
        self.pending = True
        return {"reboot_required": True, "expected_config_fingerprint": host_helper.sha(json.dumps(host_helper.config_values(self.proposed), sort_keys=True))}

    def boot_id(self): return self.identity
    def boot_epoch(self, now=None): return self.started


class Fixture:
    def setup_app(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.now = epoch("2026-10-09T17:00:00Z")
        self.mono = 1000.0
        self.rtc = FakeRTC(lambda: self.now)
        self.supervisor = FakeSupervisor()
        self.host = FakeHost(self.now)
        self.app = self.new_app()
        self.app.refresh()

    def new_app(self):
        return server.Application(self.temp.name, self.rtc, self.supervisor, self.host, clock=lambda: self.now, monotonic=lambda: self.mono)

    def advance(self, seconds):
        self.now += seconds
        self.mono += seconds

    def begin(self, kind):
        self.app.begin_job(kind, {"confirmed": True})
        self.app.process_task()

    def pass_test(self):
        self.begin("test")
        wake = self.app.pending["wake_epoch"]
        self.advance(server.COUNTDOWN)
        self.app.tick()
        self.host.identity = "boot-b"
        self.host.started = wake
        self.now = wake + 90
        self.mono += 660
        self.app = self.new_app()
        self.app.refresh()
        self.assertEqual(self.app.store.data["test"]["status"], "awaiting_confirmation")
        self.app.confirm_test({"returned_automatically": True})

    def enable(self, sleep_time="23:00", wake_time="07:00"):
        # Emulate occurrences expanded by HA's Calendar, never an app scheduler.
        zone = ZoneInfo("America/Chicago")
        today = datetime.fromtimestamp(self.now, zone).date()
        events = []
        for day in range(64):
            midnight = datetime.combine(today + timedelta(days=day), datetime.min.time(), zone).timestamp()
            start = next_daily_epoch(sleep_time, "America/Chicago", midnight - 1)
            end = next_daily_epoch(wake_time, "America/Chicago", start)
            events.append({"summary": "Pi off", "start": {"dateTime": datetime.fromtimestamp(start, zone).isoformat()}, "end": {"dateTime": datetime.fromtimestamp(end, zone).isoformat()}})
        identity = "calendar.test_pi"
        self.supervisor.calendar_list = [item for item in self.supervisor.calendar_list if item["entity_id"] != identity] + [{"entity_id": identity, "name": "Test Pi"}]
        self.supervisor.events[identity] = events
        self.app.refresh(force_calendar_discovery=True)
        self.app.save_settings({"source": "calendar", "calendar_entity_id": identity, "timezone": "America/Chicago", "enabled": True})


class WizardTests(unittest.TestCase, Fixture):
    def setUp(self): self.setup_app()

    def test_fresh_install_detects_timezone_and_defaults_to_off(self):
        status = self.app.snapshot()
        self.assertTrue(status["checks"]["ok"])
        self.assertFalse(status["schedule"]["enabled"])
        self.assertEqual(status["schedule"]["timezone"], "America/Chicago")
        self.assertEqual(self.supervisor.shutdowns, 0)

    def test_real_haos_pi5_board_can_reach_preparation(self):
        self.host.config = "[all]\nBOOT_ORDER=0xf416\nPOWER_OFF_ON_HALT=0\nWAKE_ON_GPIO=1\n"
        self.app.refresh()
        self.assertTrue(self.app.checks.get("can_prepare"))
        self.assertEqual(self.app.checks["items"][0]["label"], "Raspberry Pi 5")
        self.assertEqual(self.app.store.data["schedule"]["timezone"], "America/Chicago")
        self.assertFalse(self.app.store.data["schedule"]["enabled"])
        self.assertEqual(self.host.applies, 0)
        self.assertEqual(self.supervisor.shutdowns, 0)

    def test_unsupported_board_blocks_host_access_and_preparation(self):
        for board in ("rpi4-64", "generic-x86-64", "raspberrypi5-64", "rpi5", "rpi50-64", None):
            with self.subTest(board=board), patch.object(self.host, "inspect") as inspect:
                self.supervisor.os["board"] = board
                self.app.refresh()
                inspect.assert_not_called()
                self.assertFalse(self.app.checks["ok"])
                self.assertFalse(self.app.checks.get("can_prepare", False))
        self.assertEqual(self.host.applies, 0)
        self.assertEqual(self.rtc.writes, 0)
        self.assertEqual(self.supervisor.shutdowns, 0)

    def test_old_os_and_wrong_board_explain_next_action(self):
        self.supervisor.os["version"] = "17.2"
        self.app.refresh()
        self.assertFalse(self.app.checks["ok"])
        self.assertIn("Updates", self.app.checks["action"])
        self.supervisor.os["board"] = "rpi4-64"
        self.app.refresh()
        self.assertIn("Pi 5", self.app.checks["action"])

    def test_pending_native_firmware_update_blocks_shutdown(self):
        self.supervisor.firmware["update_pending"] = True
        self.begin("test")
        self.assertIsNone(self.app.pending)
        self.assertEqual(self.rtc.writes, 0)
        self.assertEqual(self.supervisor.shutdowns, 0)

    def test_unsupported_updater_reports_boot_device_before_host_access(self):
        self.supervisor.firmware["update_blocked"] = True
        with patch.object(self.host, "inspect") as inspect:
            self.app.refresh()
            inspect.assert_not_called()
        self.assertFalse(self.app.checks["ok"])
        self.assertIn("boot device", self.app.checks["message"])
        self.assertIn("maintainer", self.app.checks["action"])

    def test_enable_requires_physical_test_confirmation(self):
        with self.assertRaises(UserError): self.enable()
        self.assertFalse(self.app.store.data["schedule"]["enabled"])

    def test_addon_restart_cannot_count_as_wake_test(self):
        self.begin("test")
        self.advance(server.COUNTDOWN)
        self.app.tick()
        self.app = self.new_app()
        self.app.refresh()
        self.assertEqual(self.app.store.data["test"]["status"], "waiting")
        with self.assertRaises(UserError): self.app.confirm_test({"returned_automatically": True})

    def test_early_host_reboot_cannot_pass_the_test(self):
        self.begin("test")
        self.advance(server.COUNTDOWN)
        self.app.tick()
        self.host.identity = "early-reboot"
        self.host.started = self.now + 10
        self.advance(40)
        self.app = self.new_app()
        self.app.refresh()
        self.assertEqual(self.app.store.data["test"]["status"], "failed")
        with self.assertRaises(UserError): self.enable()

    def test_real_boot_window_still_requires_user_confirmation(self):
        self.pass_test()
        self.assertEqual(self.app.store.data["test"]["status"], "passed")
        self.assertFalse(self.app.store.data["schedule"]["enabled"])
        self.enable()
        self.assertTrue(self.app.snapshot()["schedule_active"])

    def test_update_preserves_times_timezone_enabled_and_confirmation(self):
        self.pass_test()
        self.enable("21:15", "06:45")
        replacement = self.new_app()
        replacement.refresh()
        self.assertEqual(replacement.store.data["schedule"], self.app.store.data["schedule"])
        self.assertTrue(replacement.snapshot()["schedule_active"])

    def test_firmware_change_preserves_times_but_requires_retest(self):
        self.pass_test()
        self.enable("21:15", "06:45")
        self.host.version = self.host.image_version = "1778499999"
        self.supervisor.firmware["current_version"] = "1778499999"
        self.app.refresh()
        status = self.app.snapshot()
        self.assertTrue(status["schedule"]["enabled"])
        self.assertEqual(status["schedule"]["calendar_entity_id"], "calendar.test_pi")
        self.assertNotIn("sleep_time", status["schedule"])
        self.assertEqual(status["test_status"], "needs_retest")
        self.assertFalse(status["schedule_active"])

    def test_boot_setting_change_requires_retest(self):
        self.pass_test()
        self.host.config = CONFIG.replace("BOOT_UART=1", "BOOT_UART=0")
        self.app.refresh()
        self.assertEqual(self.app.snapshot()["test_status"], "needs_retest")

    def test_cancel_before_worker_preflight_prevents_alarm_write(self):
        self.app.begin_job("test", {"confirmed": True})
        self.app.cancel()
        self.app.process_task()
        self.assertEqual(self.rtc.writes, 0)
        self.assertIsNone(self.app.pending)

    def test_cancel_countdown_clears_alarm_and_never_shuts_down(self):
        self.begin("test")
        self.app.cancel()
        self.advance(60)
        self.app.tick()
        self.assertFalse(self.rtc.enabled)
        self.assertEqual(self.supervisor.shutdowns, 0)

    def test_clock_change_during_countdown_keeps_pi_on(self):
        self.begin("test")
        self.rtc.drift = 90
        self.advance(30)
        self.app.tick()
        self.assertEqual(self.supervisor.shutdowns, 0)
        self.assertIsNone(self.app.pending)

    def test_external_alarm_change_during_countdown_is_preserved(self):
        self.begin("test")
        self.rtc.epoch += 60
        self.advance(30)
        self.app.tick()
        self.assertEqual(self.supervisor.shutdowns, 0)
        self.assertTrue(self.rtc.enabled)

    def test_ambiguous_shutdown_timeout_keeps_wake_alarm(self):
        self.begin("test")
        self.supervisor.fail_shutdown = True
        self.advance(30)
        self.app.tick()
        self.assertEqual(self.supervisor.shutdowns, 1)
        self.assertTrue(self.rtc.enabled)
        self.assertIn("wake time is still set", self.app.message["text"])
        with self.assertRaises(UserError): self.app.cancel()
        with self.assertRaises(UserError): self.begin("test")

    def test_failed_shutdown_can_be_rechecked_after_two_minutes(self):
        self.begin("test")
        self.supervisor.fail_shutdown = True
        self.advance(30)
        self.app.tick()
        self.advance(120)
        self.begin("check")
        self.assertIsNone(self.app.shutdown_requested_at)
        self.assertTrue(self.rtc.enabled)

    def test_storage_failure_before_shutdown_keeps_pi_on(self):
        self.begin("test")
        with patch.object(self.app.store, "save", side_effect=OSError("disk full")):
            self.advance(30)
            self.app.tick()
        self.assertEqual(self.supervisor.shutdowns, 0)
        self.assertFalse(self.rtc.enabled)

    def test_native_firmware_update_is_not_reimplemented(self):
        self.host.config = CONFIG.replace("POWER_OFF_ON_HALT=1", "POWER_OFF_ON_HALT=0")
        self.host.image_version = "1778499999"
        self.supervisor.firmware["update_available"] = True
        self.begin("prepare")
        self.assertEqual(self.host.applies, 0)
        self.assertIn("Updates", self.app.message["action"])

    def test_prepare_preserves_boot_order_and_requires_new_boot(self):
        self.host.config = CONFIG.replace("POWER_OFF_ON_HALT=1", "POWER_OFF_ON_HALT=0")
        self.begin("prepare")
        self.assertEqual(self.host.applies, 1)
        before = host_helper.config_values(self.host.config)
        after = host_helper.config_values(self.host.proposed)
        self.assertEqual(before["BOOT_ORDER"], after["BOOT_ORDER"])
        self.assertEqual(before["BOOT_UART"], after["BOOT_UART"])
        self.assertFalse(self.app.checks["ok"])
        self.assertTrue(self.app.checks["needs_reboot"])
        backup = json.loads((Path(self.temp.name) / "firmware-backup.json").read_text())
        self.assertEqual(backup["config"], self.host.config)
        self.host.config = self.host.proposed
        self.host.pending = False
        self.app.refresh()  # An immediate write still needs a host reboot.
        self.assertFalse(self.app.checks["ok"])
        self.host.identity = "prepared-boot"
        self.app.refresh()
        self.assertTrue(self.app.checks["ok"])

    def test_pending_update_and_downgrade_block_preparation(self):
        self.host.config = CONFIG.replace("POWER_OFF_ON_HALT=1", "POWER_OFF_ON_HALT=0")
        self.host.pending = True
        self.begin("prepare")
        self.assertEqual(self.host.applies, 0)
        self.host.pending = False
        self.host.image_version = "1778498000"
        self.begin("prepare")
        self.assertEqual(self.host.applies, 0)

    def test_unrelated_post_prepare_change_blocks_completion(self):
        self.host.config = CONFIG.replace("POWER_OFF_ON_HALT=1", "POWER_OFF_ON_HALT=0")
        self.begin("prepare")
        self.host.config = self.host.proposed.replace("BOOT_ORDER=0xf416", "BOOT_ORDER=0xf41")
        self.host.pending = False
        self.host.identity = "unexpected-prepared-boot"
        self.app.refresh()
        self.assertFalse(self.app.checks["ok"])
        self.assertIn("maintainer", self.app.checks["action"])

    def test_schedule_runs_once_and_cancelled_minute_is_not_retried(self):
        self.pass_test()
        self.enable()
        self.now = epoch("2026-10-10T04:00:10Z")
        self.app.tick()
        self.app.process_task()
        self.assertEqual(self.app.pending["kind"], "schedule")
        self.app.cancel()
        self.app.tick()
        self.assertTrue(self.app.tasks.empty())

    def test_missed_shutdown_minute_is_not_caught_up(self):
        self.pass_test()
        self.enable()
        self.now = epoch("2026-10-10T04:01:00Z")
        self.app.tick()
        self.assertTrue(self.app.tasks.empty())

    def test_dst_repeated_shutdown_hour_runs_only_once(self):
        self.pass_test()
        self.enable("01:30", "07:00")
        self.now = epoch("2026-11-01T06:30:05Z")
        self.app.tick()
        self.app.process_task()
        self.app.cancel()
        self.now = epoch("2026-11-01T07:30:05Z")
        self.app = self.new_app()
        self.app.refresh()
        self.app.tick()
        self.assertTrue(self.app.tasks.empty())


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)

    def test_schema_migration_preserves_selected_timezone(self):
        path = Path(self.temp.name) / "settings.json"
        atomic_json(path, {"schema_version": 1, "schedule": {"sleep_time": "22:00", "wake_time": "06:30", "timezone": "Europe/London", "enabled": False}})
        store = StateStore(self.temp.name)
        self.assertEqual(store.data["schedule"]["timezone"], "Europe/London")
        self.assertTrue(store.data["timezone_detected"])
        store.save()
        self.assertEqual(json.loads(path.read_text())["schema_version"], 6)

    def test_future_schema_is_never_overwritten(self):
        path = Path(self.temp.name) / "settings.json"
        atomic_json(path, {"schema_version": 99})
        original = path.read_bytes()
        store = StateStore(self.temp.name)
        with self.assertRaises(UserError): store.save()
        self.assertEqual(path.read_bytes(), original)

    def test_corrupt_primary_recovers_times_and_disables_schedule(self):
        store = StateStore(self.temp.name)
        store.data["schedule"].update(calendar_entity_id="calendar.before", enabled=True)
        store.save()
        store.data["schedule"]["calendar_entity_id"] = "calendar.after"
        store.save()
        store.path.write_text("corrupted")
        recovered = StateStore(self.temp.name)
        self.assertEqual(recovered.data["schedule"]["calendar_entity_id"], "calendar.before")
        self.assertFalse(recovered.data["schedule"]["enabled"])
        recovered.save()
        self.assertEqual(json.loads(recovered.backup.read_text())["schedule"]["calendar_entity_id"], "calendar.before")

    def test_failed_atomic_replace_keeps_original_settings(self):
        store = StateStore(self.temp.name)
        store.save()
        original = store.path.read_bytes()
        store.data["schedule"]["calendar_entity_id"] = "calendar.changed"
        with patch("state.os.replace", side_effect=OSError("disk full")):
            with self.assertRaises(OSError): store.save()
        self.assertEqual(store.path.read_bytes(), original)


class FirmwarePatchTests(unittest.TestCase):
    def test_only_wake_settings_change(self):
        before = CONFIG.replace("POWER_OFF_ON_HALT=1", "POWER_OFF_ON_HALT=0").replace("WAKE_ON_GPIO=0", "WAKE_ON_GPIO=1")
        result = host_helper.patched_config(before)
        self.assertIn("# Keep SSD first\nBOOT_ORDER=0xf416\nBOOT_UART=1\n", result)
        self.assertEqual(host_helper.config_values(result)["POWER_OFF_ON_HALT"], "1")
        self.assertEqual(host_helper.config_values(result)["WAKE_ON_GPIO"], "0")

    def test_conditional_signed_and_duplicate_configs_are_refused(self):
        for text in (CONFIG + "[pi5]\nFOO=1\n", CONFIG + "SIGNED_BOOT=1\n", CONFIG + "BOOT_ORDER=0xf41\n", CONFIG.replace("BOOT_ORDER=0xf416\n", "")):
            with self.subTest(text=text), self.assertRaises(ValueError): host_helper.patched_config(text)

    def test_apply_refuses_version_change_and_stale_snapshot(self):
        host = FakeHost(0)
        snapshot = host.inspect()
        snapshot["image_version"] = "9999999999"
        with patch.object(host_helper, "inspect", return_value=snapshot), patch.object(host_helper, "run") as run:
            with self.assertRaises(ValueError): host_helper.apply(snapshot)
            run.assert_not_called()
        snapshot = host.inspect()
        with patch.object(host_helper, "inspect", return_value=snapshot), patch.object(host_helper, "run") as run:
            with self.assertRaises(ValueError): host_helper.apply({**snapshot, "config_sha256": "changed"})
            run.assert_not_called()

    def test_apply_pins_the_existing_firmware_image(self):
        host = FakeHost(0)
        snapshot = host.inspect()
        with patch.object(host_helper, "inspect", return_value=snapshot), patch.object(host_helper, "run") as run:
            result = host_helper.apply(snapshot)
            arguments = run.call_args.args[0]
            self.assertEqual(arguments[:2], ["/usr/bin/rpi-eeprom-config", "--apply"])
            self.assertEqual(arguments[-1], snapshot["image"])
            self.assertTrue(result["reboot_required"])


class IngressTests(unittest.TestCase, Fixture):
    def setUp(self):
        self.setup_app()
        class Handler(server.IngressHandler):
            application = self.app
            allowed_peers = frozenset({"127.0.0.1"})  # Local test server only.
        self.handler = Handler
        self.http = server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.http.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.http.server_close)
        self.addCleanup(self.http.shutdown)

    def request(self, method, path, body=None, headers=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.http.server_port, timeout=5)
        connection.request(method, path, body=body, headers=headers or {})
        response = connection.getresponse()
        status, response_headers, data = response.status, dict(response.getheaders()), response.read()
        connection.close()
        return status, response_headers, data

    def test_direct_access_cannot_spoof_ingress(self):
        self.handler.allowed_peers = server.IngressHandler.allowed_peers
        status, _, _ = self.request("GET", "/api/status", headers={"X-Forwarded-For": "172.30.32.2", "X-Remote-User-Id": "admin"})
        self.assertEqual(status, 403)

    def test_csrf_is_required_before_mutation(self):
        status, _, _ = self.request("POST", "/api/test", json.dumps({"confirmed": True}), {"Content-Type": "application/json"})
        self.assertEqual(status, 403)
        self.assertTrue(self.app.tasks.empty())

    def test_authorized_ingress_can_start_the_wizard(self):
        status, headers, body = self.request("GET", "/api/status")
        self.assertEqual(status, 200)
        data = json.loads(body)
        self.assertNotIn("SUPERVISOR_TOKEN", body.decode())
        self.assertIn("frame-ancestors 'self'", headers["Content-Security-Policy"])
        status, _, _ = self.request("POST", "/api/test", json.dumps({"confirmed": True}), {"Content-Type": "application/json", "X-Pi5-CSRF": data["csrf"]})
        self.assertEqual(status, 200)
        self.app.process_task()
        self.assertEqual(self.app.pending["kind"], "test")

    def test_host_error_details_reach_the_screen_and_keep_preparation_disabled(self):
        error = HostError("inspect", {"step": "host_entry", "error_type": "RuntimeError", "exit_code": 1, "reason": "permission_denied"})
        with patch.object(self.host, "inspect", side_effect=error):
            self.app.refresh()
        status, _, body = self.request("GET", "/api/status")
        self.assertEqual(status, 200)
        data = json.loads(body)
        self.assertFalse(data["checks"]["ok"])
        self.assertFalse(data["checks"].get("can_prepare", False))
        self.assertFalse(data["schedule_active"])
        self.assertEqual(data["checks"]["details"], error.details)
        self.assertIn("already off", data["checks"]["action"])
        self.assertIsNone(data["schedule"]["calendar_entity_id"])
        self.assertNotIn("sleep_time", data["schedule"])

    def test_recovered_host_check_clears_old_error_details(self):
        error = HostError("inspect", {"step": "running_config", "error_type": "CalledProcessError", "exit_code": 2})
        with patch.object(self.host, "inspect", side_effect=error):
            self.app.refresh()
        self.app.refresh()
        _, _, body = self.request("GET", "/api/status")
        data = json.loads(body)
        self.assertTrue(data["checks"]["ok"])
        self.assertNotIn("details", data["checks"])

    def test_unknown_and_legacy_endpoints_do_not_write_rtc(self):
        status, _, _ = self.request("POST", "/arm", "{}", {"Content-Type": "application/json", "X-Pi5-CSRF": self.app.csrf})
        self.assertEqual(status, 404)
        status, _, _ = self.request("GET", "/../settings.json")
        self.assertEqual(status, 404)
        self.assertEqual(self.rtc.writes, 0)

    def test_saved_times_round_trip_through_http(self):
        payload = {"source": "calendar", "calendar_entity_id": "calendar.pi_sleep", "timezone": "America/Chicago", "enabled": False}
        status, _, _ = self.request("POST", "/api/settings", json.dumps(payload), {"Content-Type": "application/json", "X-Pi5-CSRF": self.app.csrf})
        self.assertEqual(status, 200)
        status, _, body = self.request("GET", "/api/status")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["schedule"], payload)
        replacement = self.new_app()
        self.assertEqual(replacement.store.data["schedule"], payload)

    def test_invalid_json_reports_plain_action(self):
        status, _, body = self.request("POST", "/api/settings", "{", {"Content-Type": "application/json", "X-Pi5-CSRF": self.app.csrf})
        self.assertEqual(status, 400)
        self.assertIn("Refresh", json.loads(body)["action"])

    def test_recovery_route_is_protected_and_defaults_to_off(self):
        status, _, _ = self.request("POST", "/api/recovery-settings", '{"enabled":false}', {"Content-Type": "application/json"})
        self.assertEqual(status, 403)
        headers = {"Content-Type": "application/json", "X-Pi5-CSRF": self.app.csrf}
        status, _, _ = self.request("POST", "/api/recovery-settings", '{"enabled":true}', headers)
        self.assertEqual(status, 409)
        status, _, _ = self.request("POST", "/api/recovery-settings", '{"enabled":false}', headers)
        self.assertEqual(status, 200)
        _, _, body = self.request("GET", "/api/status")
        data = json.loads(body)
        self.assertFalse(data["recovery"]["settings"]["enabled"])
        self.assertEqual(self.supervisor.shutdowns, 0)
        self.assertEqual(self.rtc.writes, 0)

    def test_power_discovery_and_opt_in_settings_round_trip_without_rtc_or_shutdown(self):
        observed = datetime.fromtimestamp(self.now, ZoneInfo("UTC")).isoformat()
        self.supervisor.power_rows = {"rows": [{"kind": "hook", "entity_id": "sensor.local_ups", "name": "Local UPS",
            "state": "battery", "reported_at": observed, "attributes": {"rtc_wake_power": {
                "schema_version": 1, "provider": "Test adapter", "observed_at": observed,
                "power_state": "battery", "battery_percent": 20}}}]}
        before = deepcopy(self.app.store.data["schedule"])
        headers = {"Content-Type": "application/json", "X-Pi5-CSRF": self.app.csrf}
        status, _, _ = self.request("POST", "/api/scan-ups", "{}", headers)
        self.assertEqual(status, 200)
        self.app.process_task()
        _, _, body = self.request("GET", "/api/status")
        power = json.loads(body)["ups"]
        self.assertEqual(power["sources"][0]["id"], "hook:sensor.local_ups")
        self.assertIsNone(power["settings"]["source_id"])
        payload = {"source_id": "hook:sensor.local_ups", "notifications": True, "low_battery_percent": 25}
        status, _, _ = self.request("POST", "/api/power-settings", json.dumps(payload), headers)
        self.assertEqual(status, 200)
        self.assertEqual(self.new_app().store.data["ups"], payload)
        self.assertEqual(self.supervisor.power_notices[-1]["kind"], "low_battery")
        self.assertEqual(self.app.store.data["schedule"], before)
        self.assertEqual(self.supervisor.shutdowns, 0)
        self.assertEqual(self.rtc.writes, 0)

    def test_power_routes_require_csrf_and_refuse_unknown_source_or_invalid_threshold(self):
        before = deepcopy(self.app.store.data)
        for path in ("/api/power-settings", "/api/scan-ups"):
            status, _, _ = self.request("POST", path, "{}", {"Content-Type": "application/json"})
            self.assertEqual(status, 403)
        headers = {"Content-Type": "application/json", "X-Pi5-CSRF": self.app.csrf}
        for payload in ({"source_id": "nut:unregistered", "notifications": True, "low_battery_percent": 25},
                        {"source_id": None, "notifications": False, "low_battery_percent": 1}):
            status, _, body = self.request("POST", "/api/power-settings", json.dumps(payload), headers)
            self.assertEqual(status, 409)
            self.assertTrue(json.loads(body)["action"])
        status, _, _ = self.request("POST", "/api/sleep", "{}", headers)
        self.assertEqual(status, 404)
        self.assertEqual(self.app.store.data, before)
        self.assertEqual(self.supervisor.shutdowns, 0)
        self.assertEqual(self.rtc.writes, 0)


if __name__ == "__main__": unittest.main()
