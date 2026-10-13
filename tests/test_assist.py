"""Exercise the native companion boundary without real messages or host power actions."""

from copy import deepcopy
from datetime import datetime, timezone
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from test_setup import Fixture
from test_calendar_schedule import ENTITY, event
from state import StateStore, UserError, atomic_json
from assist import PORT, TTL, parse_time
from assist_http import AssistHandler
from assist_install import Installer, FILES


class AssistTests(unittest.TestCase, Fixture):
    def setUp(self):
        self.setup_app()
        self.pass_test()
        self.supervisor.calendar_list = [{"entity_id": ENTITY, "name": "Pi Sleep"}]
        self.supervisor.events[ENTITY] = []
        self.app.refresh(force_calendar_discovery=True)
        self.app.save_settings({**self.app.store.data["schedule"], "calendar_entity_id": ENTITY, "enabled": False})
        self.config = Path(self.temp.name) / "homeassistant"
        self.config.mkdir()
        self.assist = self.app.assistant
        self.assist.installer = Installer(self.temp.name, self.config)

    def connect(self, writes=True):
        self.assist.connect({"confirmed": True})
        self.assist.save_settings({"enabled": True, "allow_requests": writes})

    def period(self, start=None, end=None):
        start = start or self.now + 3600
        end = end or start + 3600
        stamp = lambda value: datetime.fromtimestamp(value, timezone.utc).isoformat()
        return {"kind": "create_period", "start": stamp(start), "end": stamp(end), "title": "Overnight Pi rest"}

    def approve(self, value, approve=True):
        return self.assist.review({"id": value["request_id"], "approve": approve, "confirmed": True})

    def test_defaults_disable_access_and_preserve_existing_configuration(self):
        self.assertEqual(self.app.store.data["assist"], {"enabled": False, "allow_requests": False})
        self.assertEqual(self.assist.status(), {"protocol": 1, "enabled": False, "allow_requests": False})
        with self.assertRaises(UserError): self.assist.request(self.period())
        self.assertEqual(self.supervisor.created_events, [])
        self.assertEqual(self.supervisor.shutdowns, 1)  # The fixture's completed wake test only.

    def test_connect_is_screen_only_default_read_only_and_secret_not_in_ui_or_status(self):
        with self.assertRaises(UserError): self.assist.connect({})
        self.assist.connect({"confirmed": True})
        self.assertTrue(self.assist.installer.installed())
        self.assertTrue(self.assist.restart_needed)
        self.assertEqual(self.app.store.data["assist"], {"enabled": True, "allow_requests": False})
        secret = self.supervisor.assist_connection["token"]
        self.assertEqual(self.assist.secret_path.stat().st_mode & 0o777, 0o600)
        self.assertNotIn(secret, json.dumps(self.app.snapshot()))
        self.assertNotIn(secret, json.dumps(self.assist.status()))
        self.assertNotIn("csrf", self.assist.status())
        with self.assertRaises(UserError): self.assist.request(self.period())
        with self.assertRaises(UserError): self.assist.keep_awake({})

    def test_old_core_explains_update_without_installing_or_enabling(self):
        with patch.object(self.supervisor, "core_version", return_value="2026.9.4"):
            with self.assertRaises(UserError) as error: self.assist.connect({"confirmed": True})
        self.assertIn("2026.10", error.exception.message)
        self.assertFalse(self.assist.installer.destination.exists())
        self.assertFalse(self.app.store.data["assist"]["enabled"])

    def test_missing_config_folder_explains_failure_and_allows_reconnect(self):
        self.config.rmdir()
        settings = deepcopy(self.app.store.data)
        with self.assertRaises(UserError) as error:
            self.assist.connect({"confirmed": True})
        self.assertIn("configuration folder", error.exception.message)
        connection = self.assist.snapshot()["connection"]
        self.assertIn(error.exception.message, connection)
        self.assertIn(error.exception.action, connection)
        self.assertNotIn("Select Connect Assist to begin", connection)
        self.assertEqual(self.app.store.data, settings)
        self.assertFalse(self.assist.secret_path.exists())
        self.assertFalse(hasattr(self.supervisor, "assist_connection"))
        self.config.mkdir()
        self.assist.connect({"confirmed": True})
        self.assertTrue(self.assist.installer.installed())
        self.assertIn("Connection offered", self.assist.snapshot()["connection"])
        self.assertTrue(self.app.store.data["assist"]["enabled"])

    def test_fresh_status_includes_uptime_timezone_and_active_dates(self):
        self.connect()
        self.supervisor.events[ENTITY] = [event(self.now + 3600, self.now + 7200)]
        self.app.save_settings({**self.app.store.data["schedule"], "enabled": True})
        value = self.assist.status()
        self.assertEqual(value["uptime_seconds"], int(self.now - self.host.started))
        self.assertEqual(value["timezone"], "America/Chicago")
        self.assertTrue(value["scheduling_active"])
        self.assertEqual(parse_time(value["next_shutdown"]), self.now + 3600)
        self.assertEqual(parse_time(value["next_wake"]), self.now + 7200)
        self.advance(61)
        value = self.assist.status()
        self.assertFalse(value["calendar_fresh"])
        self.assertIsNone(value["next_shutdown"])
        self.assertEqual(value["periods"], [])

    def test_request_is_a_draft_and_approval_saves_only_in_calendar(self):
        self.connect()
        value = self.assist.request(self.period())
        self.assertEqual(value["status"], "awaiting_app_approval")
        self.assertEqual(self.supervisor.created_events, [])
        self.assertIsNone(self.app.pending)
        self.approve(value)
        self.assertEqual(len(self.supervisor.created_events), 1)
        self.assertEqual(self.supervisor.created_events[0]["summary"], "Overnight Pi rest")
        self.assertEqual(len(self.app.calendar_info["periods"]), 1)
        self.assertFalse(self.app.store.data["schedule"]["enabled"])
        self.assertNotIn("requests", self.app.store.data)
        self.assertEqual(self.assist.snapshot()["requests"], [])
        with self.assertRaises(UserError): self.approve(value)

    def test_identical_request_deduplicates_and_drafts_expire(self):
        self.connect()
        first = self.assist.request(self.period())
        self.assertEqual(first, self.assist.request(self.period()))
        self.advance(TTL)
        self.assertEqual(self.assist.snapshot()["requests"], [])
        with self.assertRaises(UserError): self.approve(first)
        self.assertEqual(self.supervisor.created_events, [])

    def test_restart_preserves_access_secret_settings_and_clears_unapproved_drafts(self):
        self.connect()
        self.assist.request(self.period())
        token = self.assist._secret()
        restarted = self.new_app().assistant
        self.assertEqual(restarted._secret(), token)
        self.assertEqual(restarted.requests, {})
        self.assertEqual(restarted.app.store.data["assist"], {"enabled": True, "allow_requests": True})
        self.assertEqual(restarted.app.store.data["schedule"], self.app.store.data["schedule"])

    def test_disable_revokes_writes_and_status_immediately(self):
        self.connect()
        request = self.assist.request(self.period())
        self.assist.save_settings({"enabled": False, "allow_requests": False})
        self.assertEqual(set(self.assist.status()), {"protocol", "enabled", "allow_requests"})
        with self.assertRaises(UserError): self.assist.keep_awake({})
        with self.assertRaises(UserError): self.approve(request)
        self.assertEqual(self.supervisor.created_events, [])

    def test_malformed_ambiguous_short_past_and_distant_dates_fail_before_review(self):
        self.connect()
        for edit in ({"start": "2026-10-10T20:00:00"}, {"start": "not-a-time"}, {"end": self.period()["start"]},
                     {"start": datetime.fromtimestamp(self.now - 1, timezone.utc).isoformat()}, {"confirmed": True}):
            with self.subTest(edit=edit), self.assertRaises(UserError): self.assist.request({**self.period(), **edit})
        with self.assertRaises(UserError): self.assist.request(self.period(self.now + 31 * 86400))
        self.assertEqual(self.assist.requests, {})

    def test_explicit_autumn_offsets_preserve_both_instants(self):
        self.connect()
        value = self.assist.request({"kind": "create_period", "start": "2026-11-01T01:10:00-05:00", "end": "2026-11-01T01:40:00-06:00", "title": "Clock change"})
        self.approve(value)
        period = self.app.calendar_info["periods"][0]
        self.assertEqual(period["end_epoch"] - period["start_epoch"], 90 * 60)

    def test_approval_rechecks_calendar_selection_and_new_overlaps(self):
        self.connect()
        value = self.assist.request(self.period())
        self.app.store.data["schedule"]["calendar_entity_id"] = "calendar.other"
        with self.assertRaises(UserError): self.approve(value)
        self.app.store.data["schedule"]["calendar_entity_id"] = ENTITY
        self.supervisor.events[ENTITY] = [event(self.now + 3600, self.now + 7200)]
        with self.assertRaises(UserError): self.approve(value)
        self.assertEqual(self.supervisor.created_events, [])

    def test_calendar_commit_then_timeout_is_read_back_without_duplicate(self):
        self.connect()
        request = self.assist.request(self.period())
        original = self.supervisor.create_assist_event
        def committed(*args):
            original(*args)
            raise UserError("Timed out", "Check Calendar")
        with patch.object(self.supervisor, "create_assist_event", side_effect=committed): self.approve(request)
        self.assertEqual(len(self.supervisor.created_events), 1)
        self.assertEqual(self.assist.requests, {})

    def test_uncertain_write_is_never_resubmitted_and_remains_reviewable(self):
        self.connect()
        value = self.assist.request(self.period())
        with patch.object(self.supervisor, "create_assist_event", side_effect=UserError("Timeout", "Check Calendar")) as write:
            with self.assertRaises(UserError): self.approve(value)
            repeated = self.assist.request(self.period())
            self.assertEqual(repeated["request_id"], value["request_id"])
            self.assertEqual(repeated["status"], "awaiting_calendar_confirmation")
            self.assertIn("may already be saved", repeated["next_action"])
            self.advance(TTL + 1)
            with self.assertRaises(UserError): self.approve(value)
            self.assertEqual(write.call_count, 1)
        self.assertTrue(self.assist.snapshot()["requests"][0]["submitted"])

    def test_scheduling_request_cannot_bypass_failed_wake_test(self):
        self.connect()
        request = self.assist.request({"kind": "set_scheduling", "enabled": True})
        self.app.store.data["test"]["status"] = "failed"
        with self.assertRaises(UserError): self.approve(request)
        self.assertFalse(self.app.store.data["schedule"]["enabled"])

    def test_reboot_waits_for_review_and_cannot_confirm_wake_evidence(self):
        self.connect()
        request = self.assist.request({"kind": "reboot"})
        self.assertEqual(self.supervisor.reboots, 0)
        self.approve(request)
        self.app.process_task()
        self.assertEqual(self.supervisor.reboots, 1)
        with self.assertRaises(UserError): self.assist.request({"kind": "confirm_test", "confirmed": True})

    def test_cancelling_ordinary_countdown_keeps_emergency_protection(self):
        self.connect()
        self.app.begin_job("test", {"confirmed": True})
        self.app.process_task()
        policy = deepcopy(self.app.store.data["recovery"])
        self.assertIsNotNone(self.app.pending)
        self.assertEqual(self.assist.keep_awake({})["status"], "cancelled")
        self.assertIsNone(self.app.pending)
        self.assertEqual(self.app.store.data["recovery"], policy)
        self.app.pending = {"kind": "ups", "emergency": True}
        with self.assertRaises(UserError): self.assist.keep_awake({})
        self.assertIsNotNone(self.app.pending)

    def test_private_api_requires_authentication_and_has_no_approval_route(self):
        self.connect()
        owner = self.assist
        class Handler(AssistHandler): assistant = owner
        http = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=http.serve_forever, daemon=True).start()
        self.addCleanup(http.server_close)
        self.addCleanup(http.shutdown)
        base = f"http://127.0.0.1:{http.server_port}"
        with self.assertRaises(HTTPError) as unauthorized: urlopen(base + "/v1/status")
        self.assertEqual(unauthorized.exception.code, 401)
        headers = {"Authorization": "Bearer " + self.assist._secret(), "Content-Type": "application/json"}
        for path in ("/v1/review", "/api/confirm-test", "/v1/reboot"):
            with self.subTest(path=path), self.assertRaises(HTTPError) as unknown:
                urlopen(Request(base + path, data=b'{"confirmed":true}', headers=headers))
            self.assertEqual(unknown.exception.code, 404)
        with urlopen(Request(base + "/v1/status", headers=headers)) as response:
            self.assertTrue(json.load(response)["pi_ready"])

    def test_keep_awake_does_not_interrupt_emergency_preflight(self):
        self.connect()
        self.app.job = {"kind": "ups", "label": "Preparing UPS shutdown"}
        before = self.app.cancel_serial
        self.assertEqual(self.assist.keep_awake({})["status"], "no_countdown")
        self.assertEqual(self.app.cancel_serial, before)
        self.assertEqual(self.app.job["kind"], "ups")

    def test_reviewed_reboot_still_requires_the_supported_haos_host(self):
        self.connect()
        request = self.assist.request({"kind": "reboot"})
        self.supervisor.os["board"] = "rpi4-64"
        self.approve(request)
        self.app.process_task()
        self.assertEqual(self.supervisor.reboots, 0)


class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "config"
        self.root.mkdir()
        self.installer = Installer(self.temp.name, self.root)

    def test_repeat_install_is_idempotent_and_leaves_other_configuration_untouched(self):
        config = self.root / "configuration.yaml"
        config.write_text("existing: configuration\n")
        self.assertTrue(self.installer.install())
        self.assertFalse(self.installer.install())
        self.assertEqual(config.read_text(), "existing: configuration\n")
        self.assertTrue(self.installer.installed())

    def test_customized_companion_is_never_overwritten(self):
        self.installer.install()
        target = self.installer.destination / "llm.py"
        target.write_text("# User customization\n")
        with self.assertRaises(UserError): self.installer.install()
        self.assertEqual(target.read_text(), "# User customization\n")

    def test_restart_requirement_is_retained_until_confirmed_loaded(self):
        self.assertFalse(self.installer.restart_required())
        self.installer.install()
        self.assertTrue(self.installer.restart_required())
        self.assertFalse(self.installer.install())
        replacement = Installer(self.temp.name, self.root)
        self.assertTrue(replacement.restart_required())
        replacement.confirm_loaded()
        self.assertFalse(self.installer.restart_required())
        self.assertFalse(replacement.install())
        self.assertFalse(replacement.restart_required())

    def test_legacy_installation_receipt_is_kept_on_update(self):
        self.installer.install()
        record = json.loads(self.installer.receipt.read_text())
        record.pop("restart_required")
        self.installer.receipt.write_text(json.dumps(record))
        self.assertFalse(self.installer.restart_required())
        self.assertFalse(self.installer.install())
        self.assertEqual(json.loads(self.installer.receipt.read_text())["files"], record["files"])

    def test_unknown_files_and_symlink_paths_block_install(self):
        target = self.root / "custom_components"
        outside = Path(self.temp.name) / "outside"
        outside.mkdir()
        target.symlink_to(outside, target_is_directory=True)
        with self.assertRaises(UserError): self.installer.install()
        self.assertEqual(list(outside.iterdir()), [])

    def test_schema_seven_migration_preserves_other_settings_with_assist_off(self):
        store = StateStore(self.temp.name)
        store.data["schema_version"] = 7
        store.data.pop("assist")
        atomic_json(store.path, store.data)
        migrated = StateStore(self.temp.name)
        self.assertFalse(migrated.read_only)
        self.assertEqual(migrated.data["schedule"], store.data["schedule"])
        self.assertEqual(migrated.data["assist"], {"enabled": False, "allow_requests": False})
