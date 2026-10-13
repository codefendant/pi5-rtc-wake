"""User flows and boundaries for the native dashboard; no real power operations."""

from copy import deepcopy
import http.client
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import threading
import unittest
from unittest.mock import MagicMock, patch

from test_calendar_schedule import Fixture, event
from test_setup import server, UserError
from assist_http import AssistHandler
from assist_install import Installer
from dashboard import Dashboard, starter_config, restore_cards, compact_dashboard_config, fill_starter_section_cards
from services import Supervisor
from state import StateStore


class DashboardTests(unittest.TestCase, Fixture):
    def setUp(self):
        self.setup_app()
        self.config = Path(self.temp.name) / "homeassistant"
        self.config.mkdir()
        self.app.assistant.installer = Installer(self.temp.name, self.config)

    def test_dashboard_connect_does_not_enable_ai_or_any_power_feature(self):
        before = deepcopy(self.app.store.data)
        self.app.dashboard.connect({"confirmed": True})
        after = self.app.store.data
        self.assertTrue(after["dashboard"]["connected"])
        for key in ("assist", "schedule", "recovery", "messages", "test"):
            self.assertEqual(before[key], after[key])
        self.assertTrue(self.app.assistant.installer.installed())
        self.assertNotIn(self.app.assistant._secret(), json.dumps(self.app.dashboard.status()))
        self.assertNotIn("csrf", self.app.dashboard.status())

    def test_saved_installation_is_not_a_live_connection_and_contact_expires(self):
        self.app.dashboard.connect({"confirmed": True})
        self.assertFalse(self.app.snapshot()["dashboard"]["active"])
        self.assertTrue(self.app.dashboard.status()["dashboard"]["active"])
        self.assertFalse(self.app.snapshot()["dashboard"]["ready"])
        self.assertTrue(self.app.snapshot()["dashboard"]["restart_needed"])
        self.app.dashboard.ready({"entry_id": "entry-a", "companion_version": self.app.dashboard.companion_version})
        self.assertFalse(self.app.snapshot()["dashboard"]["restart_needed"])
        self.assertTrue(self.app.snapshot()["dashboard"]["ready"])
        self.advance(90)
        self.assertFalse(self.app.snapshot()["dashboard"]["active"])
        self.assertTrue(self.app.store.data["dashboard"]["connected"])
        self.assertTrue(self.app.dashboard.status()["dashboard"]["active"])

    def test_failed_creation_is_visible_after_contact_and_polling(self):
        self.app.dashboard.connect({"confirmed": True})
        self.app.dashboard.status()
        with patch.object(self.supervisor, "ensure_dashboard", side_effect=UserError("Dashboard could not be created.", "Reconnect in Devices & services.")):
            with self.assertRaises(UserError):
                self.app.dashboard.ready({"entry_id": "entry-a", "companion_version": self.app.dashboard.companion_version})
        status = self.app.dashboard.status()["dashboard"]
        self.assertTrue(status["active"])
        self.assertFalse(status["ready"])
        self.assertEqual(status["setup_error"]["action"], "Reconnect in Devices & services.")
        self.app.dashboard.ready({"entry_id": "entry-a", "companion_version": self.app.dashboard.companion_version})
        status = self.app.dashboard.status()["dashboard"]
        self.assertTrue(status["ready"])
        self.assertIsNone(status["setup_error"])

    def test_restart_notification_survives_app_restart_and_clears_on_matching_readiness(self):
        before = deepcopy(self.app.store.data)
        self.app.dashboard.connect({"confirmed": True})
        self.assertEqual(self.supervisor.companion_notices, [True])
        self.assertTrue(self.app.assistant.installer.restart_required())
        self.app = self.new_app()
        self.assertTrue(self.app.snapshot()["dashboard"]["restart_needed"])
        self.app.dashboard.sync_restart_notice()
        self.assertEqual(self.supervisor.companion_notices, [True, True])
        self.app.dashboard.status()
        self.assertTrue(self.app.assistant.installer.restart_required())
        with self.assertRaises(UserError):
            self.app.dashboard.ready({"entry_id": "entry-a", "companion_version": "old"})
        self.assertTrue(self.app.assistant.installer.restart_required())
        self.app.dashboard.ready({"entry_id": "entry-a", "companion_version": self.app.dashboard.companion_version})
        self.assertEqual(self.supervisor.companion_notices, [True, True, False])
        self.assertFalse(self.app.assistant.installer.restart_required())
        for key in ("assist", "schedule", "recovery", "messages", "test"):
            self.assertEqual(self.app.store.data[key], before[key])
        self.assertEqual(self.supervisor.reboots, 0)
        self.assertEqual(self.supervisor.shutdowns, 0)

    def test_notification_failure_is_informational_and_retries_with_a_bound(self):
        with patch.object(self.supervisor, "companion_restart_notice", side_effect=UserError("Core is starting", "Wait")) as notice:
            self.app.dashboard.connect({"confirmed": True})
            self.assertFalse(self.app.snapshot()["dashboard"]["restart_notice_ok"])
            self.assertTrue(self.app.store.data["dashboard"]["connected"])
            self.app.dashboard.sync_restart_notice()
            self.advance(59)
            self.app.dashboard.sync_restart_notice()
            self.assertEqual(notice.call_count, 1)
            self.advance(1)
            self.app.dashboard.sync_restart_notice()
            self.assertEqual(notice.call_count, 2)
        self.advance(60)
        self.app.dashboard.sync_restart_notice()
        self.assertTrue(self.app.snapshot()["dashboard"]["restart_notice_ok"])
        self.assertEqual(self.supervisor.reboots, 0)
        self.assertEqual(self.supervisor.shutdowns, 0)

    def test_failed_dashboard_creation_does_not_clear_restart_notification(self):
        self.app.dashboard.connect({"confirmed": True})
        with patch.object(self.supervisor, "ensure_dashboard", side_effect=UserError("Not ready", "Try again")):
            with self.assertRaises(UserError):
                self.app.dashboard.ready({"entry_id": "entry-a", "companion_version": self.app.dashboard.companion_version})
        self.assertEqual(self.supervisor.companion_notices, [True])
        self.assertTrue(self.app.assistant.installer.restart_required())

    def test_homeassistant_restart_notice_uses_only_its_own_notification(self):
        supervisor = Supervisor()
        with patch.object(supervisor, "request") as request:
            supervisor.companion_restart_notice(True)
            path, payload = request.call_args.args
            self.assertEqual(path, "/core/api/services/persistent_notification/create")
            self.assertEqual(payload["notification_id"], "pi5_rtc_wake_homeassistant_restart_required")
            self.assertIn("restart Home Assistant", payload["title"])
            self.assertIn("[Settings](/config)", payload["message"])
            supervisor.companion_restart_notice(False)
            request.assert_called_with("/core/api/services/persistent_notification/dismiss", {
                "notification_id": payload["notification_id"]})

    def test_old_loaded_companion_cannot_add_cards_before_update(self):
        for payload in ({"entry_id": "entry-a"}, {"entry_id": "entry-a", "companion_version": "0.10.0-rc.1"}):
            with patch.object(self.supervisor, "ensure_dashboard") as ensure:
                with self.assertRaisesRegex(UserError, "older Pi dashboard companion"):
                    self.app.dashboard.ready(payload)
                ensure.assert_not_called()
            status = self.app.snapshot()["dashboard"]
            self.assertFalse(status["ready"])
            self.assertIn("restart Home Assistant", status["setup_error"]["action"])

    def test_restart_requires_dashboard_recheck_and_keeps_personal_cards(self):
        self.app.dashboard.connect({"confirmed": True})
        self.app.dashboard.ready({"entry_id": "entry-a", "companion_version": self.app.dashboard.companion_version})
        user = {"type": "picture", "image": "/local/family.jpg"}
        self.supervisor.dashboard_config["views"][0]["sections"].append({"type": "grid", "cards": [user]})
        original = deepcopy(self.supervisor.dashboard_config)
        self.app = self.new_app()
        self.assertTrue(self.app.store.data["dashboard"]["connected"])
        self.assertFalse(self.app.snapshot()["dashboard"]["ready"])
        self.app.dashboard.status()
        self.assertFalse(self.app.snapshot()["dashboard"]["ready"])
        self.app.dashboard.ready({"entry_id": "entry-a", "companion_version": self.app.dashboard.companion_version})
        self.assertTrue(self.app.snapshot()["dashboard"]["ready"])
        self.assertEqual(self.supervisor.dashboard_config, original)

    def test_live_connection_status_does_not_change_saved_feature_choices(self):
        before = deepcopy(self.app.store.data)
        self.app.dashboard.status()
        self.app.dashboard.ready({"entry_id": "entry-a", "companion_version": self.app.dashboard.companion_version})
        self.assertEqual(self.app.store.data, before)
        self.assertEqual(self.supervisor.shutdowns, 0)
        self.assertEqual(self.supervisor.reboots, 0)

    def test_permissions_gate_precedes_firmware_and_host_inspection(self):
        with patch.object(self.supervisor, "app_info", return_value={"protected": True, "slug": "local_pi5_rtc_wake"}), \
             patch.object(self.host, "inspect") as inspect, patch.object(self.supervisor, "firmware_info") as firmware:
            self.app.refresh()
        self.assertFalse(self.app.checks["ok"])
        self.assertIn("Protection mode", self.app.checks["message"])
        self.assertIn("Stop", self.app.checks["action"])
        inspect.assert_not_called()
        firmware.assert_not_called()
        self.assertTrue(self.app.host_shutdown_supported)

    def test_unknown_permissions_do_not_assume_access(self):
        with patch.object(self.supervisor, "app_info", return_value={"slug": "local_pi5_rtc_wake"}), patch.object(self.host, "inspect") as inspect:
            self.app.refresh()
        self.assertFalse(self.app.checks["ok"])
        inspect.assert_not_called()

    def test_create_calendar_before_wake_test_selects_once_and_keeps_scheduling_off(self):
        self.app.dashboard.create_calendar({"confirmed": True})
        self.assertEqual(self.app.store.data["schedule"]["calendar_entity_id"], "calendar.pi_sleep")
        self.assertFalse(self.app.store.data["schedule"]["enabled"])
        self.assertEqual(self.supervisor.events["calendar.pi_sleep"], [])
        with self.assertRaises(UserError): self.app.dashboard.create_calendar({"confirmed": True})
        self.assertEqual(len(self.supervisor.calendar_list), 1)

    def test_calendar_creating_already_existing_calendar_reuses_its_dates(self):
        self.supervisor.ensure_sleep_calendar()
        dates = [event(self.now + 3600, self.now + 7200)]
        self.supervisor.events["calendar.pi_sleep"] = deepcopy(dates)
        self.app.dashboard.create_calendar({"confirmed": True})
        self.assertEqual(self.supervisor.events["calendar.pi_sleep"], dates)
        self.assertEqual(len(self.supervisor.calendar_list), 1)
        self.assertFalse(self.app.store.data["schedule"]["enabled"])

    def test_existing_schedule_is_not_replaced_by_calendar_creation(self):
        self.app.store.data["schedule"]["calendar_entity_id"] = "calendar.personal_pi"
        with patch.object(self.supervisor, "ensure_sleep_calendar") as create:
            with self.assertRaises(UserError): self.app.dashboard.create_calendar({"confirmed": True})
        create.assert_not_called()

    def test_calendar_pause_persists_without_deleting_dates_or_wake_evidence(self):
        self.pass_test()
        self.supervisor.calendar_list = [{"entity_id": "calendar.pi_sleep", "name": "Pi Sleep"}]
        dates = [event(self.now + 3600, self.now + 7200)]
        self.supervisor.events["calendar.pi_sleep"] = deepcopy(dates)
        self.app.dashboard.action("settings", {**self.app.store.data["schedule"], "calendar_entity_id": "calendar.pi_sleep", "enabled": True})
        before = deepcopy(self.app.store.data)
        self.app.dashboard.action("settings", {**before["schedule"], "enabled": False})
        restored = StateStore(self.temp.name)
        self.assertFalse(restored.data["schedule"]["enabled"])
        self.assertEqual(restored.data["schedule"]["calendar_entity_id"], "calendar.pi_sleep")
        self.assertEqual(self.supervisor.events["calendar.pi_sleep"], dates)
        for key in ("test", "recovery", "ups", "messages", "assist"):
            self.assertEqual(before[key], restored.data[key])

    def test_schema_eight_update_preserves_settings_and_wake_evidence(self):
        self.pass_test()
        self.app.store.data["schema_version"] = 8
        self.app.store.data.pop("dashboard")
        original = deepcopy(self.app.store.data)
        self.app.store.save()
        restored = StateStore(self.temp.name)
        self.assertEqual(restored.data["dashboard"], {"connected": False})
        for key in ("assist", "schedule", "recovery", "messages", "test", "preparation"):
            self.assertEqual(original[key], restored.data[key])

    def test_dashboard_creation_and_updates_preserve_existing_personal_cards(self):
        self.app.dashboard.ready({"entry_id": "entry-a", "companion_version": self.app.dashboard.companion_version})
        user = {"type": "picture", "image": "/local/family.jpg"}
        self.supervisor.dashboard_config["views"][0]["sections"].append({"type": "grid", "cards": [user]})
        original = deepcopy(self.supervisor.dashboard_config)
        self.app.dashboard.ready({"entry_id": "entry-a", "companion_version": self.app.dashboard.companion_version})
        self.assertEqual(self.supervisor.dashboard_config, original)

    def test_restore_keeps_nested_personal_cards_and_metadata(self):
        config = starter_config("entry-a")
        user = {"type": "history-graph", "entities": ["sensor.freezer_temperatures"]}
        other_pi = {"type": "custom:pi-wake-status-card", "entry_id": "another-pi"}
        config["views"][0]["sections"][4]["cards"].append({"type": "vertical-stack", "cards": [user, other_pi]})
        config["views"][0]["background"] = "/local/my-photo.jpg"
        restored = restore_cards(config, "entry-a")
        self.assertIn(user, restored["views"][0]["sections"][4]["cards"][0]["cards"])
        self.assertIn(other_pi, restored["views"][0]["sections"][4]["cards"][0]["cards"])
        self.assertEqual(restored["views"][0]["background"], "/local/my-photo.jpg")
        self.assertEqual(len([card for section in restored["views"][0]["sections"] for card in section["cards"]
                              if card.get("type", "").startswith("custom:pi-wake-")]), 7)
        self.assertEqual(len(config["views"][0]["sections"]), 7)

    @staticmethod
    def legacy_layout(entry_id="entry-a"):
        config = starter_config(entry_id)
        kinds = ("setup", "status", "shutdown", "wake", "calendar", "ups", "controls", "devices", "messages", "assist", "activity")
        config["views"][0]["sections"] = [{"type": "grid", "column_span": 3 if kind in ("setup", "activity") else 2 if kind in ("calendar", "devices") else 1,
            "cards": [{"type": f"custom:pi-wake-{kind}-card", "entry_id": entry_id, "grid_options": {"columns": 12, "rows": "auto"}}]} for kind in kinds]
        return config

    def test_compact_layout_preserves_dates_settings_and_interleaved_personal_cards(self):
        config = self.legacy_layout()
        photo = {"type": "grid", "cards": [{"type": "picture", "image": "/local/family.jpg"}]}
        config["views"][0]["sections"].insert(2, photo)
        config["views"][0]["background"] = "/local/rv.jpg"
        config["views"].append({"path": "other", "cards": [{"type": "history-graph"}]})
        before = deepcopy(config)
        settings = deepcopy(self.app.store.data)
        updated = compact_dashboard_config(config, "entry-a")
        sections = updated["views"][0]["sections"]
        self.assertEqual(sections[0]["cards"][0]["type"], "custom:pi-wake-summary-card")
        self.assertEqual(sections[1], photo)
        self.assertEqual(sections[2:], [row for row in before["views"][0]["sections"] if row["cards"][0]["type"] in
            {"custom:pi-wake-" + kind + "-card" for kind in ("calendar", "ups", "devices", "messages", "assist", "activity")}])
        self.assertEqual(updated["views"][1], before["views"][1])
        self.assertEqual(updated["views"][0]["background"], "/local/rv.jpg")
        self.assertEqual(config, before)
        self.assertEqual(self.app.store.data, settings)
        self.assertEqual(compact_dashboard_config(updated, "entry-a"), updated)

    def test_compact_layout_respects_custom_headers_and_other_pis(self):
        for change in ("title", "resize", "personal", "missing", "duplicate", "other-pi", "masonry", "summary"):
            with self.subTest(change=change):
                config = self.legacy_layout()
                view = config["views"][0]
                if change == "title": view["sections"][1]["cards"][0]["title"] = "My Pi"
                elif change == "resize": view["sections"][1]["column_span"] = 2
                elif change == "personal": view["sections"][1]["cards"].append({"type": "weather-forecast"})
                elif change == "missing": view["sections"].pop(1)
                elif change == "duplicate": view["sections"].append(deepcopy(view["sections"][1]))
                elif change == "other-pi": view["sections"][1]["cards"][0]["entry_id"] = "entry-b"
                elif change == "masonry": view["type"] = "masonry"
                elif change == "summary": view["sections"].append(starter_config("entry-a")["views"][0]["sections"][0])
                self.assertEqual(compact_dashboard_config(config, "entry-a"), config)

    def test_wide_starter_cards_fill_sections_without_moving_personal_cards(self):
        config = starter_config("entry-a")
        for section in config["views"][0]["sections"]:
            section["cards"][0]["grid_options"]["columns"] = 12
            section["cards"][0].pop("pi_layout_version", None)
        config["views"][0]["background"] = "/local/cabin.jpg"
        personal = {"type": "grid", "column_span": 2, "cards": [{"type": "history-graph", "grid_options": {"columns": 12}}]}
        config["views"][0]["sections"].insert(2, personal)
        before = deepcopy(config)
        fixed = fill_starter_section_cards(config, "entry-a")
        for section in fixed["views"][0]["sections"]:
            if section["cards"][0]["type"] in {"custom:pi-wake-summary-card", "custom:pi-wake-calendar-card", "custom:pi-wake-activity-card"}:
                self.assertEqual(section["cards"][0]["grid_options"], {"columns": "full", "rows": "auto"})
        self.assertEqual(fixed["views"][0]["sections"][2], personal)
        self.assertEqual(fixed["views"][0]["background"], before["views"][0]["background"])
        self.assertEqual(config, before)
        self.assertEqual(fill_starter_section_cards(fixed, "entry-a"), fixed)
        fixed["views"][0]["sections"][0]["cards"][0]["grid_options"]["columns"] = 12
        self.assertEqual(fill_starter_section_cards(fixed, "entry-a"), fixed)

    def test_full_width_repair_keeps_explicit_card_and_section_customizations(self):
        for change in ("card-size", "row-size", "title", "section-size", "section-title", "mixed", "other-pi", "masonry"):
            with self.subTest(change=change):
                section = {"type": "grid", "column_span": 2, "cards": [{"type": "custom:pi-wake-calendar-card", "entry_id": "entry-a", "grid_options": {"columns": 12, "rows": "auto"}}]}
                config = {"views": [{"type": "sections", "sections": [section]}]}
                card = section["cards"][0]
                if change == "card-size": card["grid_options"]["columns"] = 6
                elif change == "row-size": card["grid_options"]["rows"] = 4
                elif change == "title": card["title"] = "My calendar"
                elif change == "section-size": section["column_span"] = 3
                elif change == "section-title": section["title"] = "My dates"
                elif change == "mixed": section["cards"].append({"type": "picture"})
                elif change == "other-pi": card["entry_id"] = "entry-b"
                else: config["views"][0]["type"] = "masonry"
                self.assertEqual(fill_starter_section_cards(config, "entry-a"), config)

    def test_default_summary_replaces_duplicate_top_controls(self):
        cards = [section["cards"][0]["type"] for section in starter_config("entry-a")["views"][0]["sections"]]
        self.assertEqual(cards[0], "custom:pi-wake-summary-card")
        self.assertEqual(len(cards), 7)
        self.assertTrue(all("custom:pi-wake-" + kind + "-card" not in cards for kind in ("setup", "status", "shutdown", "wake", "controls")))

    def test_restore_preserves_users_changed_view_type(self):
        config = {"views": [{"title": "My layout", "type": "masonry", "path": "overview", "cards": [{"type": "picture", "image": "/local/rv.jpg"}]}]}
        result = restore_cards(config, "entry-a")
        self.assertEqual(result["views"][0], config["views"][0])
        self.assertEqual(result["views"][1]["path"], "pi-controls")

    def test_emergency_cannot_be_cancelled_and_dashboard_actions_are_allowlisted(self):
        self.app.pending = {"emergency": True, "kind": "ups"}
        with self.assertRaises(UserError): self.app.dashboard.action("cancel", {})
        self.assertTrue(self.app.pending["emergency"])
        with self.assertRaises(UserError): self.app.dashboard.action("shell", {"command": "anything"})

    def test_dashboard_auth_stays_required_when_ai_is_disabled(self):
        self.app.dashboard.connect({"confirmed": True})
        owner = self.app.assistant
        class Handler(AssistHandler):
            assistant = owner
        http = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=http.serve_forever, daemon=True).start()
        self.addCleanup(http.server_close)
        self.addCleanup(http.shutdown)
        connection = http_client(http.server_port)
        self.addCleanup(connection.close)
        connection.request("GET", "/v1/dashboard")
        response = connection.getresponse()
        self.assertEqual(response.status, 401); response.read()
        connection.request("GET", "/v1/dashboard", headers={"Authorization": "Bearer " + owner._secret()})
        response = connection.getresponse()
        self.assertEqual(response.status, 200)
        state = json.loads(response.read())
        self.assertFalse(state["enabled"])
        self.assertIn("schedule", state)
        self.assertNotIn("csrf", state)


def http_client(port):
    return http.client.HTTPConnection("127.0.0.1", port, timeout=5)


class CoreDashboardRequests(unittest.TestCase):
    def setUp(self):
        self.supervisor = Supervisor()
        self.supervisor.token = "test-token"
        self.core = MagicMock()
        self.registry = patch("services.CoreRegistry")
        factory = self.registry.start()
        factory.return_value.__enter__.return_value = self.core
        self.addCleanup(self.registry.stop)

    def test_existing_local_calendar_is_reused_even_with_renamed_entity_id(self):
        self.core.command.return_value = [{"platform": "google", "original_name": "Pi Sleep", "entity_id": "calendar.pi_sleep"},
                                          {"platform": "local_calendar", "original_name": "Pi Sleep", "entity_id": "calendar.my_pi", "disabled_by": None}]
        with patch.object(self.supervisor, "request") as request:
            request.return_value = {"attributes": {"supported_features": 1}}
            self.assertEqual(self.supervisor.ensure_sleep_calendar(), "calendar.my_pi")
            self.assertTrue(all("config_entries/flow" not in call.args[0] for call in request.call_args_list))

    def test_creation_follows_real_local_calendar_flow_and_resolves_entry_entity(self):
        self.core.command.side_effect = [[], [{"platform": "local_calendar", "config_entry_id": "new-entry", "entity_id": "calendar.pi_sleep_2", "disabled_by": None}]]
        with patch.object(self.supervisor, "request", side_effect=[{"type": "form", "step_id": "user", "flow_id": "flow-a"},
                                                                  {"type": "create_entry", "result": {"entry_id": "new-entry"}},
                                                                  {"attributes": {"supported_features": 1}}]) as request:
            self.assertEqual(self.supervisor.ensure_sleep_calendar(), "calendar.pi_sleep_2")
        self.assertEqual(request.call_args_list[1].args[1], {"calendar_name": "Pi Sleep", "import": "create_empty"})

    def test_existing_dashboard_is_not_overwritten_and_resource_version_is_updated(self):
        self.core.command.side_effect = [[{"id": "r1", "type": "module", "url": "/pi5_rtc_wake/pi-cards.js?v=old"}], {}, [{"url_path": "pi-wake-sleep"}], {"views": [{"cards": [{"type": "picture"}]}]}]
        self.assertFalse(self.supervisor.ensure_dashboard("entry-a")["created"])
        self.assertNotIn("lovelace/config/save", [call.args[0] for call in self.core.command.call_args_list])
        self.assertIn("lovelace/resources/update", [call.args[0] for call in self.core.command.call_args_list])
        version = json.loads(Path("pi5_rtc_wake/companion/pi5_rtc_wake/manifest.json").read_text())["version"]
        update = next(call for call in self.core.command.call_args_list if call.args[0] == "lovelace/resources/update")
        self.assertEqual(update.kwargs["url"], "/pi5_rtc_wake/pi-cards.js?v=" + version)

    def test_legacy_header_is_compacted_only_after_readback_with_personal_cards_retained(self):
        config = DashboardTests.legacy_layout()
        config["views"][0]["sections"].append({"type": "grid", "cards": [{"type": "picture", "image": "/local/rv.jpg"}]})
        self.core.command.side_effect = [[], {}, [{"url_path": "pi-wake-sleep"}], config, deepcopy(config), {}]
        self.assertFalse(self.supervisor.ensure_dashboard("entry-a")["created"])
        saved = self.core.command.call_args.kwargs["config"]
        self.assertEqual(saved, fill_starter_section_cards(compact_dashboard_config(config, "entry-a"), "entry-a"))
        self.assertEqual(saved["views"][0]["sections"][-1], config["views"][0]["sections"][-1])
        self.assertEqual([call.args[0] for call in self.core.command.call_args_list].count("lovelace/config"), 2)

    def test_concurrent_dashboard_edit_prevents_compact_layout_save(self):
        config = DashboardTests.legacy_layout()
        edited = deepcopy(config)
        edited["views"][0]["sections"][1]["cards"][0]["title"] = "My Pi"
        self.core.command.side_effect = [[], {}, [{"url_path": "pi-wake-sleep"}], config, edited]
        with self.assertRaises(UserError):
            self.supervisor.ensure_dashboard("entry-a")
        self.assertNotIn("lovelace/config/save", [call.args[0] for call in self.core.command.call_args_list])

    def test_interrupted_empty_dashboard_setup_can_be_retried(self):
        from ha_registry import CoreCommandError
        self.core.command.side_effect = [[], {}, [{"url_path": "pi-wake-sleep"}], CoreCommandError("config_not_found"), {}]
        self.assertTrue(self.supervisor.ensure_dashboard("entry-a")["created"])
        self.assertEqual(self.core.command.call_args.args, ("lovelace/config/save",))
        self.assertEqual(self.core.command.call_args.kwargs["config"], starter_config("entry-a"))

    def test_uncertain_dashboard_read_never_overwrites_a_layout(self):
        self.core.command.side_effect = [[], {}, [{"url_path": "pi-wake-sleep"}], UserError("Connection interrupted", "Try again")]
        with self.assertRaises(UserError):
            self.supervisor.ensure_dashboard("entry-a")
        self.assertNotIn("lovelace/config/save", [call.args[0] for call in self.core.command.call_args_list])

