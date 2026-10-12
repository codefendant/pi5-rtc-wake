"""Authenticated access to this app on Home Assistant's private app network."""

from collections.abc import Mapping
from datetime import timedelta
import json
import re
import time

import aiohttp

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import COMPANION_VERSION, DOMAIN, PORT, PROTOCOL


def validate_connection(config, slug):
    """Trust only a Supervisor-discovered instance of our own app."""
    if (not isinstance(slug, str) or not re.fullmatch(r"[a-z0-9]{1,32}_pi5_rtc_wake", slug)
            or not isinstance(config, Mapping) or config.get("host") != slug.replace("_", "-")
            or type(config.get("port")) is not int or config["port"] != PORT
            or type(config.get("protocol")) is not int or config["protocol"] != PROTOCOL
            or not isinstance(config.get("token"), str) or not re.fullmatch(r"[A-Za-z0-9_-]{43,128}", config["token"])):
        raise HomeAssistantError("Use Update / reconnect dashboard in the app Web UI’s Maintenance and connection repair. The discovered connection is invalid.")
    return {key: config[key] for key in ("host", "port", "protocol", "token")}


class Client:
    def __init__(self, session, config):
        self.session = session
        self.base = f"http://{config['host']}:{PORT}"
        self.token = config["token"]

    async def call(self, path, payload=None):
        if path not in ("/v1/status", "/v1/request", "/v1/keep-awake", "/v1/dashboard", "/v1/dashboard/action", "/v1/dashboard/ready", "/v1/message-options", "/v1/wake-device-options"):
            raise HomeAssistantError("That Pi Wake & Sleep action is not supported.")
        try:
            async with self.session.request(
                "GET" if payload is None else "POST", self.base + path,
                json=payload, headers={"Authorization": "Bearer " + self.token},
                timeout=aiohttp.ClientTimeout(total=90 if payload is not None else 20, connect=5), allow_redirects=False,
            ) as response:
                body = bytearray()
                async for chunk in response.content.iter_chunked(8192):
                    body.extend(chunk)
                    if len(body) > (2 * 1024 * 1024 if path in ("/v1/dashboard", "/v1/message-options", "/v1/wake-device-options") else 65536):
                        raise ValueError()
                value = json.loads(body)
                if not isinstance(value, dict):
                    raise ValueError()
                if response.status != 200:
                    raise HomeAssistantError(" ".join(str(value.get(key, "")) for key in ("message", "action")).strip() or
                                             "Use Update / reconnect dashboard in the app Web UI’s Maintenance and connection repair.")
                return value
        except (aiohttp.ClientError, TimeoutError, ValueError, UnicodeError):
            raise HomeAssistantError("Pi Wake & Sleep is unavailable. Keep the Pi powered and check that its app is running.") from None

    async def status(self):
        value = await self.call("/v1/status")
        if value.get("protocol") != PROTOCOL or any(type(value.get(key)) is not bool for key in ("enabled", "allow_requests")):
            raise HomeAssistantError("Update the Pi Wake & Sleep companion using Update / reconnect dashboard in Setup & maintenance, then restart Home Assistant if requested.")
        return value

    async def dashboard_status(self):
        value = await self.call("/v1/dashboard")
        if value.get("protocol") != PROTOCOL or any(type(value.get(key)) is not bool for key in ("enabled", "allow_requests")):
            raise HomeAssistantError("Update the companion using Update / reconnect dashboard in Setup & maintenance, then restart Home Assistant if requested.")
        return value


class Coordinator(DataUpdateCoordinator):
    def __init__(self, hass, logger, entry, client):
        super().__init__(hass, logger, name=DOMAIN, config_entry=entry,
                         update_interval=timedelta(seconds=30))
        self.client = client
        self.dashboard_ready = False
        self.dashboard_attempt = -float("inf")

    async def _async_update_data(self):
        try:
            value = await self.client.dashboard_status()
            if (value.get("dashboard", {}).get("connected")
                    and (not self.dashboard_ready or not value["dashboard"].get("ready"))
                    and time.monotonic() - self.dashboard_attempt >= 60):
                self.dashboard_attempt = time.monotonic()
                try:
                    await self.client.call("/v1/dashboard/ready", {"entry_id": self.config_entry.entry_id,
                                                                "companion_version": COMPANION_VERSION})
                    self.dashboard_ready = True
                    value["dashboard"].update(ready=True, restart_needed=False, setup_error=None)
                except HomeAssistantError as error:
                    value["dashboard"]["connection"] = str(error)
            return value
        except HomeAssistantError as error:
            raise UpdateFailed(str(error)) from error
