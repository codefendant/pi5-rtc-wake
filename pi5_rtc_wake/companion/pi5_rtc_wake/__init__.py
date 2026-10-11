"""Expose the Pi app through Home Assistant's native Assist tool platform."""

import logging

from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import Client, Coordinator, validate_connection
from .const import DOMAIN
from .dashboard import async_register_dashboard

LOGGER = logging.getLogger(__name__)
PLATFORMS = ["sensor", "binary_sensor"]


async def async_setup(hass, config):
    await async_register_dashboard(hass)
    return True


async def async_setup_entry(hass, entry):
    config = validate_connection(entry.data, entry.data["slug"])
    client = Client(async_get_clientsession(hass), config)
    coordinator = Coordinator(hass, LOGGER, entry, client)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    @callback
    def updated():
        """Keep capabilities current even when no entity platform is loaded."""

    entry.async_on_unload(coordinator.async_add_listener(updated))
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    return True


async def async_reload_entry(hass, entry):
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass, entry):
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
