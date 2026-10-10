"""Authenticated access to this app on Home Assistant's private app network."""

import asyncio
from datetime import timedelta
import json
import re

import aiohttp

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, PORT, PROTOCOL


def validate_connection(config, slug):
    """Trust only a Supervisor-discovered instance of our own app."""
    if (not isinstance(slug, str) or not re.fullmatch(r"[a-z0-9]{1,32}_pi5_rtc_wake", slug)
            or not isinstance(config, dict) or config.get("host") != slug.replace("_", "-")
            or type(config.get("port")) is not int or config["port"] != PORT
            or type(config.get("protocol")) is not int or config["protocol"] != PROTOCOL
            or not isinstance(config.get("token"), str) or not re.fullmatch(r"[A-Za-z0-9_-]{43,128}", config["token"])):
        raise HomeAssistantError("Reconnect Assist from the Pi Wake & Sleep app. The discovered connection is invalid.")
    return {key: config[key] for key in ("host", "port", "protocol", "token")}


class Client:
    def __init__(self, session, config):
        self.session = session
        self.base = f"http://{config['host']}:{PORT}"
        self.token = config["token"]

    async def call(self, path, payload=None):
        if path not in ("/v1/status", "/v1/request", "/v1/keep-awake"):
            raise HomeAssistantError("That Pi Wake & Sleep action is not supported.")
        try:
            async with self.session.request(
                "GET" if payload is None else "POST", self.base + path,
                json=payload, headers={"Authorization": "Bearer " + self.token},
                timeout=aiohttp.ClientTimeout(total=20, connect=5), allow_redirects=False,
            ) as response:
                body = await response.content.read(65537)
                if len(body) > 65536:
                    raise ValueError()
                value = json.loads(body)
                if not isinstance(value, dict):
                    raise ValueError()
                if response.status != 200:
                    raise HomeAssistantError(" ".join(str(value.get(key, "")) for key in ("message", "action")).strip() or
                                             "Reconnect Assist from the Pi Wake & Sleep app.")
                return value
        except (aiohttp.ClientError, TimeoutError, ValueError, UnicodeError):
            raise HomeAssistantError("Pi Wake & Sleep is unavailable. Keep the Pi powered and check that its app is running.") from None

    async def status(self):
        value = await self.call("/v1/status")
        if value.get("protocol") != PROTOCOL or any(type(value.get(key)) is not bool for key in ("enabled", "allow_requests")):
            raise HomeAssistantError("Update the Pi Wake & Sleep companion using Connect Assist in the app, then restart Home Assistant.")
        return value


class Coordinator(DataUpdateCoordinator):
    def __init__(self, hass, logger, entry, client):
        super().__init__(hass, logger, name=DOMAIN, config_entry=entry,
                         update_interval=timedelta(seconds=30))
        self.client = client

    async def _async_update_data(self):
        try:
            return await self.client.status()
        except HomeAssistantError as error:
            raise UpdateFailed(str(error)) from error
