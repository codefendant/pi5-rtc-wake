#!/usr/bin/env python3
"""Verify native dashboard, entities, calendar creation, and admin boundaries in real Core.

Run in the official Home Assistant 2026.10.1 container. Pi, UPS and phone services
are simulated; Home Assistant's integration loading, REST and WebSocket APIs are real.
"""

import asyncio
import importlib
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import sys
import threading
from unittest.mock import patch

import aiohttp
from homeassistant import bootstrap, loader
from homeassistant.auth.const import GROUP_ID_ADMIN
from homeassistant.config_entries import SOURCE_HASSIO, ConfigEntryState
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers import llm
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.service_info.hassio import HassioServiceInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
from test_assist import AssistTests
from assist_http import AssistHandler
from dashboard import Dashboard, starter_config, restore_cards
from ha_registry import CoreRegistry
from services import Supervisor
from websocket import create_connection
import urllib.request
from wake_devices import ping_template, registry_identity, discover
from state import UserError


async def check():
    fixture = AssistTests("test_request_is_a_draft_and_approval_saves_only_in_calendar")
    fixture.setUp()
    fixture.app.dashboard.connect({"confirmed": True})
    owner = fixture.assist

    class Handler(AssistHandler):
        assistant = owner

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    hass = HomeAssistant(str(fixture.config))
    loader.async_setup(hass)
    try:
        assert await bootstrap.async_from_config_dict(
            {"http": {"server_host": "127.0.0.1", "server_port": 8123}, "frontend": {}, "lovelace": {}, "llm": {}}, hass=hass
        ) is hass
        native = importlib.import_module("custom_components.pi5_rtc_wake.api")
        original = native.Client.__init__

        def simulated_network(client, session, config):
            original(client, session, config)
            client.base = f"http://127.0.0.1:{server.server_port}"

        discovery = HassioServiceInfo(config={"host": "local-pi5-rtc-wake", "port": 8098, "protocol": 1, "token": owner._secret()},
                                     name="Pi Wake & Sleep", slug="local_pi5_rtc_wake", uuid="a" * 32)
        with patch.object(native.Client, "__init__", simulated_network):
            flow = await hass.config_entries.flow.async_init("pi5_rtc_wake", context={"source": SOURCE_HASSIO}, data=discovery)
            configured = await hass.config_entries.flow.async_configure(flow["flow_id"], {})
            assert configured["type"] == "create_entry", configured
            await hass.async_block_till_done()
            entry = configured["result"]
            assert entry.state is ConfigEntryState.LOADED, (entry, entry.reason)
            assert fixture.app.store.data["assist"] == {"enabled": False, "allow_requests": False}
            assert fixture.app.store.data["dashboard"]["connected"]
            entities = [hass.states.get(row.entity_id) for row in er.async_get(hass).entities.values() if row.config_entry_id == entry.entry_id]
            assert all(state is not None for state in entities)
            assert len(entities) == 9, [(state.entity_id, state.state) for state in hass.states.async_all()]
            assert any(state.entity_id.endswith("wake_ready") and state.state == "on" for state in entities)
            context = llm.LLMContext(platform="ollama", context=Context(), language="en", assistant="conversation", device_id=None)
            api = await llm.async_get_api(hass, "assist", context)
            assert not any(tool.integration == "pi5_rtc_wake" for tool in api.tools), "Dashboard connection must not enable AI tools"

            admin = await hass.auth.async_create_user("Dashboard test admin", group_ids=[GROUP_ID_ADMIN])
            admin_refresh = await hass.auth.async_create_refresh_token(admin, client_id="http://127.0.0.1:8123/")
            admin_token = hass.auth.async_create_access_token(admin_refresh)
            viewer = await hass.auth.async_create_user("Dashboard test viewer")
            viewer_refresh = await hass.auth.async_create_refresh_token(viewer, client_id="http://127.0.0.1:8123/")
            viewer_token = hass.auth.async_create_access_token(viewer_refresh)

            async with aiohttp.ClientSession() as session:
                async def connect(token):
                    socket = await session.ws_connect("http://127.0.0.1:8123/api/websocket")
                    assert (await socket.receive_json())["type"] == "auth_required"
                    await socket.send_json({"type": "auth", "access_token": token})
                    assert (await socket.receive_json())["type"] == "auth_ok"
                    return socket

                socket = await connect(admin_token)
                serial = 0
                async def command(kind, **values):
                    nonlocal serial
                    serial += 1
                    await socket.send_json({"id": serial, "type": kind, **values})
                    while True:
                        result = await socket.receive_json()
                        if result.get("id") == serial:
                            assert result.get("success"), result
                            return result.get("result")

                status = await command("pi5_rtc_wake/status", entry_id=entry.entry_id)
                assert status["test_status"] == "passed" and not status["enabled"]
                assert status["dashboard"]["active"], "Authenticated companion contact must be visible to setup UI"
                assert "csrf" not in status and owner._secret() not in json.dumps(status)
                original_schedule = dict(status["schedule"])
                await command("pi5_rtc_wake/action", entry_id=entry.entry_id, action="keep-awake", payload={"active": True, "confirmed": True})
                paused = await command("pi5_rtc_wake/status", entry_id=entry.entry_id)
                assert paused["keep_awake"] and not paused["schedule_active"] and not paused["recovery"]["emergency_active"], paused
                assert paused["schedule"] == original_schedule and paused["test_status"] == "passed"
                await command("pi5_rtc_wake/action", entry_id=entry.entry_id, action="keep-awake", payload={"active": False, "confirmed": True})
                assert not (await command("pi5_rtc_wake/status", entry_id=entry.entry_id))["keep_awake"]
                resources = await command("lovelace/resources/list")
                resource = await command("lovelace/resources/create", res_type="module", url="/pi5_rtc_wake/pi-cards.js?v=test")
                await command("lovelace/resources/update", resource_id=resource["id"], res_type="module", url="/pi5_rtc_wake/pi-cards.js?v=0.10.0-rc.2")
                # Exercise first dashboard creation through the actual app
                # readiness endpoint and real Core APIs, not a prefilled layout.
                assert not any(row["url_path"] == "pi-wake-sleep" for row in await command("lovelace/dashboards/list"))
                supervisor = Supervisor()
                supervisor.token = admin_token
                def local_core(_url, **values):
                    return create_connection("ws://127.0.0.1:8123/api/websocket", **values)
                fixture.app.dashboard.ready_entry_id = None
                with patch("services.CoreRegistry", side_effect=lambda token: CoreRegistry(token, connector=local_core)), \
                     patch.object(fixture.supervisor, "ensure_dashboard", side_effect=supervisor.ensure_dashboard):
                    created = await hass.async_add_executor_job(lambda: fixture.app.dashboard.ready({
                        "entry_id": entry.entry_id, "companion_version": native.COMPANION_VERSION}))
                assert created["created"] and fixture.app.snapshot()["dashboard"]["ready"]
                config = starter_config(entry.entry_id)
                saved = await command("lovelace/config", url_path="pi-wake-sleep")
                assert saved == config, saved
                picture = {"type": "picture", "image": "/local/my-rv.jpg"}
                saved["views"][0]["sections"].append({"type": "grid", "cards": [picture]})
                restored = restore_cards(saved, entry.entry_id)
                await command("lovelace/config/save", url_path="pi-wake-sleep", config=restored)
                assert any(picture in section.get("cards", []) for section in restored["views"][0]["sections"])
                # The app can restart while the HA companion stays loaded.
                # Its previous successful check must not hide missing readiness.
                fixture.app.dashboard = Dashboard(fixture.app, fixture.temp.name)
                assert not fixture.app.snapshot()["dashboard"]["ready"]
                assert entry.runtime_data.dashboard_ready
                entry.runtime_data.dashboard_attempt = -float("inf")
                with patch("services.CoreRegistry", side_effect=lambda token: CoreRegistry(token, connector=local_core)), \
                     patch.object(fixture.supervisor, "ensure_dashboard", side_effect=supervisor.ensure_dashboard):
                    # Simulate the next periodic update directly; a user-requested
                    # refresh can be debounced while the initial load is recent.
                    await entry.runtime_data.async_refresh()
                assert fixture.app.snapshot()["dashboard"]["ready"]
                assert entry.runtime_data.data["dashboard"]["ready"]
                assert await command("lovelace/config", url_path="pi-wake-sleep") == restored
                response = await session.get("http://127.0.0.1:8123/pi5_rtc_wake/pi-cards.js")
                assert response.status == 200 and "customCards" in await response.text()

                headers = {"Authorization": "Bearer " + admin_token}
                # Real native WOL config flow/button service; UDP is patched so
                # verification never sends a packet to a computer.
                from homeassistant.config_entries import SOURCE_USER
                with patch("wakeonlan.send_magic_packet") as send_packet:
                    wol_flow = await hass.config_entries.flow.async_init("wake_on_lan", context={"source": SOURCE_USER})
                    wol_created = await hass.config_entries.flow.async_configure(wol_flow["flow_id"], {"mac": "02:00:00:00:00:01"})
                    assert wol_created["type"] == "create_entry", wol_created
                    await hass.async_block_till_done()
                    wol_entry = wol_created["result"]
                    wol_entity = next(row.entity_id for row in er.async_get(hass).entities.values() if row.config_entry_id == wol_entry.entry_id and row.domain == "button")
                    registry = er.async_get(hass)
                    ping_entry = registry.async_get_or_create("binary_sensor", "ping", "simulated-ping", suggested_object_id="test_pc_ping", config_entry=wol_entry)
                    hass.states.async_set(ping_entry.entity_id, "on", {"device_class": "connectivity"})
                    old_reported = hass.states.get(ping_entry.entity_id).last_reported
                    hass.states.async_set(ping_entry.entity_id, "on", {"device_class": "connectivity"})
                    assert hass.states.get(ping_entry.entity_id).last_reported >= old_reported
                    supervisor = Supervisor()
                    supervisor.token = admin_token
                    def local_core(_url, **values):
                        return create_connection("ws://127.0.0.1:8123/api/websocket", **values)
                    def local_request(path, payload=None):
                        request = urllib.request.Request("http://127.0.0.1:8123" + path.removeprefix("/core"),
                            data=json.dumps(payload).encode() if payload is not None else None, headers={**headers, "Content-Type": "application/json"})
                        with urllib.request.urlopen(request, timeout=15) as response:
                            return json.loads(response.read())
                    supervisor.request = local_request
                    with patch("services.CoreRegistry", side_effect=lambda token: CoreRegistry(token, connector=local_core)):
                        before_layout = await command("lovelace/config", url_path="pi-wake-sleep")
                        before_layout["views"][0]["sections"] = [section for section in before_layout["views"][0]["sections"] if not any(card.get("type") == "custom:pi-wake-devices-card" for card in section.get("cards", []))]
                        await command("lovelace/config/save", url_path="pi-wake-sleep", config=before_layout)
                        await hass.async_add_executor_job(lambda: supervisor.ensure_dashboard(entry.entry_id, add_wake_devices=True))
                        after_layout = await command("lovelace/config", url_path="pi-wake-sleep")
                        assert after_layout["views"][0]["sections"][:-1] == before_layout["views"][0]["sections"]
                        assert after_layout["views"][0]["sections"][-1]["cards"][0]["type"] == "custom:pi-wake-devices-card"
                        metadata = await hass.async_add_executor_job(supervisor.wake_metadata)
                        assert metadata[wol_entity]["platform"] == "wake_on_lan" and registry_identity(metadata[wol_entity])
                        assert metadata[ping_entry.entity_id]["platform"] == "ping"
                        response = await session.get("http://127.0.0.1:8123/api/states", headers=headers)
                        from phone_messages import states_by_id
                        choices = discover(states_by_id(await response.json()), metadata)
                        assert any(row["entity_id"] == wol_entity for row in choices["devices"])
                        await hass.async_add_executor_job(supervisor.press_wake_button, wol_entity, registry_identity(metadata[wol_entity]))
                        assert send_packet.call_count == 1
                        readings = await hass.async_add_executor_job(supervisor.wake_ping_states, [ping_entry.entity_id])
                        assert readings["rows"][0]["state"] == "on" and readings["rows"][0]["last_reported"]
                        assert readings["rows"][0]["identity"] == registry_identity(metadata[ping_entry.entity_id])
                        registry.async_update_entity(wol_entity, disabled_by=er.RegistryEntryDisabler.USER)
                        try:
                            await hass.async_add_executor_job(supervisor.press_wake_button, wol_entity, registry_identity(metadata[wol_entity]))
                        except UserError:
                            pass
                        else:
                            raise AssertionError("Disabled WOL button was pressed")
                        assert send_packet.call_count == 1
                device_options = await command("pi5_rtc_wake/wake_device_options", entry_id=entry.entry_id)
                assert device_options == {"devices": [], "pings": []}
                response = await session.post("http://127.0.0.1:8123/api/config/config_entries/flow", headers=headers,
                                              json={"handler": "local_calendar", "show_advanced_options": False})
                calendar_flow = await response.json()
                assert calendar_flow["type"] == "form", calendar_flow
                response = await session.post("http://127.0.0.1:8123/api/config/config_entries/flow/" + calendar_flow["flow_id"],
                                              headers=headers, json={"calendar_name": "Pi Sleep", "import": "create_empty"})
                created = await response.json()
                assert created["type"] == "create_entry" and created["result"]["entry_id"], created
                await hass.async_block_till_done()
                response = await session.get("http://127.0.0.1:8123/api/calendars", headers=headers)
                assert any(item["name"] == "Pi Sleep" for item in await response.json())
                await socket.close()

                socket = await connect(viewer_token)
                await socket.send_json({"id": 1, "type": "pi5_rtc_wake/status", "entry_id": entry.entry_id})
                assert (await socket.receive_json())["success"]
                await socket.send_json({"id": 2, "type": "pi5_rtc_wake/action", "entry_id": entry.entry_id,
                                        "action": "reboot-now", "payload": {"confirmed": True}})
                denied = await socket.receive_json()
                assert not denied["success"] and denied["error"]["code"] == "unauthorized", denied
                await socket.send_json({"id": 3, "type": "pi5_rtc_wake/action", "entry_id": entry.entry_id,
                                        "action": "keep-awake", "payload": {"active": True, "confirmed": True}})
                denied = await socket.receive_json()
                assert not denied["success"] and denied["error"]["code"] == "unauthorized", denied
                assert not fixture.app.store.data["keep_awake"]
                await socket.send_json({"id": 4, "type": "pi5_rtc_wake/wake_device_options", "entry_id": entry.entry_id})
                denied = await socket.receive_json()
                assert not denied["success"] and denied["error"]["code"] == "unauthorized", denied
                await socket.send_json({"id": 5, "type": "pi5_rtc_wake/action", "entry_id": entry.entry_id,
                                        "action": "wake-devices", "payload": {"confirmed": True}})
                denied = await socket.receive_json()
                assert not denied["success"] and denied["error"]["code"] == "unauthorized", denied
                await socket.close()
                assert fixture.supervisor.reboots == 0
            print("Real Core passed: fresh dashboard creation and cached-companion readiness recheck with personal cards retained, dashboard without AI, 9 native entities, authenticated Keep awake/resume with settings retention, resource registration, editable storage layout, personal-card retention, native Local Calendar REST setup, native Wake on LAN flow/registry/button with UDP patched, Ping last-reported template, additive layout upgrade, and non-admin power/device-option/wake denial.")
    finally:
        await hass.async_stop(force=True)
        server.shutdown()
        server.server_close()
        fixture.doCleanups()


if __name__ == "__main__":
    asyncio.run(check())
