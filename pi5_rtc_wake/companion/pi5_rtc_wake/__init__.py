"""Expose the Pi app through Home Assistant's native Assist tool platform."""

import logging

from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import Client, Coordinator, validate_connection
from .const import DOMAIN

LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry):
    config = validate_connection(entry.data, entry.data["slug"])
    client = Client(async_get_clientsession(hass), config)
    coordinator = Coordinator(hass, LOGGER, entry, client)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    @callback
    def updated():
        """Keep capabilities current even when no entity platform is loaded."""

    entry.async_on_unload(coordinator.async_add_listener(updated))
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    return True


async def async_reload_entry(hass, entry):
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass, entry):
    return True
