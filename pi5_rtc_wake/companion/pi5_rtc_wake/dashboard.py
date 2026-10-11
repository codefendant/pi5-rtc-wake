"""Native cards and user-authenticated dashboard operations."""

from pathlib import Path

import probatio

from homeassistant.components import websocket_api
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntryState
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN


def entry_for(hass, entry_id):
    entries = [entry for entry in hass.config_entries.async_entries(DOMAIN)
               if entry.state is ConfigEntryState.LOADED and hasattr(entry, "runtime_data")
               and (not entry_id or entry.entry_id == entry_id)]
    if len(entries) != 1:
        raise HomeAssistantError("Choose the Pi Wake & Sleep integration in this card's visual editor.")
    return entries[0]


@websocket_api.websocket_command({probatio.Required("type"): DOMAIN + "/entries"})
@websocket_api.async_response
async def entries(hass, connection, msg):
    connection.send_result(msg["id"], [{"entry_id": entry.entry_id, "title": entry.title}
                           for entry in hass.config_entries.async_entries(DOMAIN)
                           if entry.state is ConfigEntryState.LOADED])


@websocket_api.websocket_command({probatio.Required("type"): DOMAIN + "/status",
                                  probatio.Optional("entry_id", default=""): str})
@websocket_api.async_response
async def status(hass, connection, msg):
    try:
        entry = entry_for(hass, msg["entry_id"])
        value = await entry.runtime_data.client.dashboard_status()
        connection.send_result(msg["id"], value)
    except HomeAssistantError as error:
        connection.send_error(msg["id"], "pi_unavailable", str(error))


@websocket_api.websocket_command({probatio.Required("type"): DOMAIN + "/message_options",
                                  probatio.Optional("entry_id", default=""): str})
@websocket_api.async_response
async def message_options(hass, connection, msg):
    if not connection.user.is_admin:
        connection.send_error(msg["id"], "unauthorized", "An administrator can choose phone recipients and readings.")
        return
    try:
        entry = entry_for(hass, msg["entry_id"])
        connection.send_result(msg["id"], await entry.runtime_data.client.call("/v1/message-options"))
    except HomeAssistantError as error:
        connection.send_error(msg["id"], "pi_unavailable", str(error))


@websocket_api.websocket_command({probatio.Required("type"): DOMAIN + "/action",
                                  probatio.Optional("entry_id", default=""): str,
                                  probatio.Required("action"): str,
                                  probatio.Optional("payload", default=dict): dict})
@websocket_api.async_response
async def action(hass, connection, msg):
    # A card being visible or an Assist agent being enabled never grants admin rights.
    if not connection.user.is_admin:
        connection.send_error(msg["id"], "unauthorized", "An administrator can change Pi settings and run power operations.")
        return
    try:
        entry = entry_for(hass, msg["entry_id"])
        payload = {**msg["payload"], "entry_id": entry.entry_id} if msg["action"] == "restore-cards" else msg["payload"]
        value = await entry.runtime_data.client.call("/v1/dashboard/action", {"action": msg["action"], "payload": payload})
        await entry.runtime_data.async_request_refresh()
        connection.send_result(msg["id"], value)
    except HomeAssistantError as error:
        connection.send_error(msg["id"], "pi_action_failed", str(error))


async def async_register_dashboard(hass):
    await hass.http.async_register_static_paths([
        StaticPathConfig("/pi5_rtc_wake/pi-cards.js", str(Path(__file__).with_name("frontend") / "pi-cards.js"), cache_headers=False)])
    for handler in (entries, status, message_options, action):
        websocket_api.async_register_command(hass, handler)
