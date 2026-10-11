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
from dashboard import Dashboard, starter_config, restore_cards
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
        self.assertTrue(self.app.snapshot()["dashboard"]["restart_needed"])
        self.app.dashboard.ready({"entry_id": "entry-a"})
        self.assertFalse(self.app.snapshot()["dashboard"]["restart_needed"])
        self.advance(90)
        self.assertFalse(self.app.snapshot()["dashboard"]["active"])
        self.assertTrue(self.app.store.data["dashboard"]["connected"])
        self.assertTrue(self.app.dashboard.status()["dashboard"]["active"])

    def test_live_connection_status_does_not_change_saved_feature_choices(self):
        before = deepcopy(self.app.store.data)
        self.app.dashboard.status()
        self.app.dashboard.ready({"entry_id": "entry-a"})
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
        self.app.dashboard.ready({"entry_id": "entry-a"})
        user = {"type": "picture", "image": "/local/family.jpg"}
        self.supervisor.dashboard_config["views"][0]["sections"].append({"type": "grid", "cards": [user]})
        original = deepcopy(self.supervisor.dashboard_config)
        self.app.dashboard.ready({"entry_id": "entry-a"})
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
                              if card.get("type", "").startswith("custom:pi-wake-")]), 10)
        self.assertEqual(len(config["views"][0]["sections"]), 10)

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

