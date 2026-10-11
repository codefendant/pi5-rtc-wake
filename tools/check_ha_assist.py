#!/usr/bin/env python3
"""Run the real native Assist platform/config flow against a simulated app.

Run inside the official Home Assistant 2026.10.1 container. No actual Pi,
UPS, phone, or model is accessed. Core, schemas, flow, loader, and ToolResult
dispatch are real; the app's hardware/services are simulated.
"""

import asyncio
import importlib
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import sys
import threading
import unittest
from unittest.mock import patch

from homeassistant import bootstrap, loader
from homeassistant.config_entries import SOURCE_HASSIO, ConfigEntryState
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers import llm
from homeassistant.helpers.service_info.hassio import HassioServiceInfo
from homeassistant.util import yaml as yaml_util

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
from test_assist import AssistTests
from assist_http import AssistHandler
from assist_install import Installer


def check_companion_mapping():
    """The published app must mount Core's folder where the installer writes.

    Supervisor defaults homeassistant_config to /homeassistant, so omitting
    path does not satisfy the installer even when the map type is correct.
    """
    config = yaml_util.load_yaml(str(ROOT / "pi5_rtc_wake" / "config.yaml"))
    mappings = config["map"]
    core = [item for item in mappings if item["type"] == "homeassistant_config"]
    assert len(core) == 1, "Map exactly one Home Assistant configuration folder"
    assert core[0].get("path") == str(Installer(ROOT).root), "Mount and installer paths must match explicitly"
    assert core[0].get("read_only") is False, "Companion installation needs a writable configuration mount"
    assert not any(item["type"] == "config" for item in mappings), "Legacy config mapping overrides homeassistant_config"
    print("Published app configuration passed: explicit writable Core folder matches the companion installer.")


async def check():
    check_companion_mapping()
    fixture = AssistTests("test_request_is_a_draft_and_approval_saves_only_in_calendar")
    fixture.setUp()
    fixture.connect(writes=False)
    owner = fixture.assist

    class Handler(AssistHandler):
        assistant = owner

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    hass = HomeAssistant(str(fixture.config))
    loader.async_setup(hass)
    try:
        assert await bootstrap.async_from_config_dict(
            {"http": {"server_host": "127.0.0.1", "server_port": 8123}, "llm": {}}, hass=hass
        ) is hass
        native = importlib.import_module("custom_components.pi5_rtc_wake.api")
        original = native.Client.__init__

        def simulated_network(client, session, config):
            original(client, session, config)
            client.base = f"http://127.0.0.1:{server.server_port}"

        connection = {"host": "local-pi5-rtc-wake", "port": 8098, "protocol": 1, "token": owner._secret()}
        discovery = HassioServiceInfo(config=connection, name="Pi Wake & Sleep", slug="local_pi5_rtc_wake", uuid="a" * 32)
        with patch.object(native.Client, "__init__", simulated_network):
            flow = await hass.config_entries.flow.async_init("pi5_rtc_wake", context={"source": SOURCE_HASSIO}, data=discovery)
            assert flow["type"] == "form" and flow["step_id"] == "confirm", flow
            configured = await hass.config_entries.flow.async_configure(flow["flow_id"], {})
            assert configured["type"] == "create_entry", configured
            await hass.async_block_till_done()
            entry = configured["result"]
            assert entry.state is ConfigEntryState.LOADED, (entry, entry.reason)
            context = llm.LLMContext(platform="ollama", context=Context(), language="en", assistant="conversation", device_id=None)
            api = await llm.async_get_api(hass, "assist", context)
            assert any(tool.integration != "pi5_rtc_wake" for tool in api.tools), "Normal Assist tools must remain available"
            own = [tool for tool in api.tools if tool.integration == "pi5_rtc_wake"]
            assert [tool.name for tool in own] == ["pi5_rtc_wake__status"], own
            status = await api.async_call_tool(llm.ToolInput(tool_name="pi5_rtc_wake__status", tool_args={}))
            assert isinstance(status, llm.ToolResult) and not status.error and status.data["pi_ready"]
            assert "csrf" not in status.data and owner._secret() not in json.dumps(status.data)

            owner.save_settings({"enabled": True, "allow_requests": True})
            await entry.runtime_data.async_refresh()
            api = await llm.async_get_api(hass, "assist", context)
            own = [tool for tool in api.tools if tool.integration == "pi5_rtc_wake"]
            assert len(own) == 5 and all(tool.name.startswith("pi5_rtc_wake__") for tool in own)
            for tool in own:
                assert isinstance(tool.annotations, llm.ToolAnnotations)
                assert isinstance(tool.parameters, __import__("probatio").Schema)
            args = fixture.period()
            args.pop("kind")
            proposal = await api.async_call_tool(llm.ToolInput(tool_name="pi5_rtc_wake__request_off_period", tool_args=args))
            assert isinstance(proposal, llm.ToolResult) and not proposal.error, proposal
            assert proposal.data["status"] == "awaiting_app_approval"
            assert fixture.supervisor.created_events == []
            fixture.approve(proposal.data)
            assert len(fixture.supervisor.created_events) == 1

            # A previously issued tool instance cannot bypass live revocation.
            owner.save_settings({"enabled": False, "allow_requests": False})
            revoked = await api.async_call_tool(llm.ToolInput(tool_name="pi5_rtc_wake__request_off_period", tool_args=args))
            assert revoked.error and len(fixture.supervisor.created_events) == 1
            await entry.runtime_data.async_refresh()
            disabled = await llm.async_get_api(hass, "assist", context)
            assert not any(tool.integration == "pi5_rtc_wake" for tool in disabled.tools)
            assert await hass.config_entries.async_unload(entry.entry_id)
            unloaded = await llm.async_get_api(hass, "assist", context)
            assert not any(tool.integration == "pi5_rtc_wake" for tool in unloaded.tools)
            print("Native Home Assistant 2026.10.1 passed: discovery/confirmation, real platform loading, read-only defaults, native tool schemas/results, approved Calendar save, immediate revocation, and unload. Simulated app hardware only.")
    finally:
        await hass.async_stop(force=True)
        server.shutdown()
        server.server_close()
        fixture.doCleanups()


if __name__ == "__main__":
    asyncio.run(check())
