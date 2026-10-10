"""Screen-only setup from authenticated Supervisor app discovery."""

import probatio

from homeassistant import config_entries
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import Client, validate_connection
from .const import DOMAIN


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_hassio(self, discovery_info):
        try:
            config = validate_connection(discovery_info.config, discovery_info.slug)
        except HomeAssistantError:
            return self.async_abort(reason="invalid_discovery")
        await self.async_set_unique_id(discovery_info.uuid)
        self._connection = {**config, "slug": discovery_info.slug}
        self._abort_if_unique_id_configured(updates=self._connection)
        self.context["title_placeholders"] = {"name": "Pi Wake & Sleep"}
        return await self.async_step_confirm()

    async def async_step_confirm(self, user_input=None):
        errors = {}
        if user_input is not None:
            try:
                await Client(async_get_clientsession(self.hass), self._connection).status()
            except HomeAssistantError:
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(title="Pi Wake & Sleep", data=self._connection)
        return self.async_show_form(step_id="confirm", data_schema=probatio.Schema({}), errors=errors)

    async def async_step_user(self, user_input=None):
        return self.async_abort(reason="use_discovery")
