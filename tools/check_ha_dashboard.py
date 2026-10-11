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
from dashboard import starter_config, restore_cards


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
                assert "csrf" not in status and owner._secret() not in json.dumps(status)
                resources = await command("lovelace/resources/list")
                resource = await command("lovelace/resources/create", res_type="module", url="/pi5_rtc_wake/pi-cards.js?v=test")
                await command("lovelace/resources/update", resource_id=resource["id"], res_type="module", url="/pi5_rtc_wake/pi-cards.js?v=0.9.0-rc.2")
                await command("lovelace/dashboards/create", url_path="pi-wake-sleep", title="Pi Wake & Sleep", icon="mdi:power-sleep", show_in_sidebar=True, require_admin=False)
                config = starter_config(entry.entry_id)
                await command("lovelace/config/save", url_path="pi-wake-sleep", config=config)
                saved = await command("lovelace/config", url_path="pi-wake-sleep")
                assert saved == config, saved
                picture = {"type": "picture", "image": "/local/my-rv.jpg"}
                saved["views"][0]["sections"].append({"type": "grid", "cards": [picture]})
                restored = restore_cards(saved, entry.entry_id)
                await command("lovelace/config/save", url_path="pi-wake-sleep", config=restored)
                assert picture in json.loads(json.dumps(restored))["views"][0]["sections"][10]["cards"]
                response = await session.get("http://127.0.0.1:8123/pi5_rtc_wake/pi-cards.js")
                assert response.status == 200 and "customCards" in await response.text()

                headers = {"Authorization": "Bearer " + admin_token}
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
                await socket.close()
                assert fixture.supervisor.reboots == 0
            print("Real Core passed: dashboard without AI, 9 native entities, authenticated card API, resource registration, editable storage layout, personal-card retention, native Local Calendar REST setup, and non-admin power denial.")
    finally:
        await hass.async_stop(force=True)
        server.shutdown()
        server.server_close()
        fixture.doCleanups()


if __name__ == "__main__":
    asyncio.run(check())
