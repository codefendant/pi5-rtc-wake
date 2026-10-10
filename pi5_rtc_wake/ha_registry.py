"""Fixed Core registry operations through the authenticated Supervisor proxy."""

import json
import re
import time

from power_sources import ENTITY_ID, label
from state import UserError

DEVICE_ID = re.compile(r"[a-zA-Z0-9_-]{1,100}")


class CoreRegistry:
    def __init__(self, token, connector=None):
        self.token, self.connector = token, connector
        self.socket = None
        self.serial = 0
        self.deadline = None

    def __enter__(self):
        try:
            if not self.token:
                raise ValueError()
            connector = self.connector
            if connector is None:
                from websocket import create_connection
                connector = create_connection
            self.deadline = time.monotonic() + 15
            self.socket = connector("ws://supervisor/core/websocket", timeout=6, http_no_proxy=["supervisor"])
            if self._receive().get("type") != "auth_required":
                raise ValueError()
            self.socket.send(json.dumps({"type": "auth", "access_token": self.token}))
            if self._receive().get("type") != "auth_ok":
                raise ValueError()
            return self
        except Exception:
            self.__exit__(None, None, None)
            raise UserError("Home Assistant's sensor settings could not be reached.", "Use the NUT device page to enable sensors, or try Find power sources again.") from None

    def __exit__(self, *_):
        if self.socket is not None:
            try:
                self.socket.close(timeout=1)
            except Exception:
                pass
            self.socket = None

    def _receive(self):
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError()
        self.socket.settimeout(min(6, remaining))
        text = self.socket.recv()
        if not isinstance(text, str) or len(text) > 8 * 1024 * 1024:
            raise ValueError()
        value = json.loads(text)
        if not isinstance(value, dict):
            raise ValueError()
        return value

    def command(self, kind, **values):
        # No arbitrary WebSocket command or service supplied by the browser.
        if kind not in {"config/device_registry/list", "config/entity_registry/list", "config/entity_registry/get", "config/entity_registry/update"}:
            raise ValueError("Unsupported registry operation")
        self.serial += 1
        try:
            self.socket.send(json.dumps({"id": self.serial, "type": kind, **values}))
            result = self._receive()
            if result.get("id") != self.serial or result.get("type") != "result" or result.get("success") is not True:
                raise ValueError()
            return result["result"]
        except Exception:
            raise UserError("Home Assistant did not confirm the sensor change.", "Check this sensor on the NUT device page before trying again. The request may already have succeeded.") from None

    def nut_sensors(self):
        rows = self.command("config/entity_registry/list")
        if not isinstance(rows, list) or len(rows) > 50000:
            raise UserError("The sensor list could not be read.", "Open the NUT device page in Home Assistant.")
        result = []
        for row in rows:
            if (not isinstance(row, dict) or row.get("platform") != "nut"
                    or not ENTITY_ID.fullmatch(str(row.get("entity_id", "")))
                    or not isinstance(row.get("device_id"), str)
                    or not DEVICE_ID.fullmatch(row["device_id"])):
                continue
            disabled = row.get("disabled_by")
            result.append({"entity_id": row["entity_id"], "device_id": row["device_id"],
                           "name": label(row.get("name") or row.get("original_name"), row["entity_id"]),
                           "disabled_by": disabled, "can_enable": disabled in ("integration", "user"),
                           "runtime_measurement": row.get("translation_key") == "battery_runtime" or str(row.get("unique_id", "")).endswith("_battery.runtime")})
        if result:
            devices = self.command("config/device_registry/list")
            if not isinstance(devices, list) or len(devices) > 20000:
                raise UserError("NUT's device list could not be read.", "Open the NUT device page in Home Assistant.")
            devices = {row["id"]: row for row in devices if isinstance(row, dict) and isinstance(row.get("id"), str)}
            for row in result:
                device = devices.get(row["device_id"], {})
                row.update(device_name=label(device.get("name_by_user") or device.get("name"), "NUT UPS"),
                           manufacturer=label(device.get("manufacturer"), ""), model=label(device.get("model"), ""))
                if device.get("disabled_by") is not None:
                    row["can_enable"] = False
        return result

    def enable_nut_sensor(self, device_id, entity_id):
        if not isinstance(entity_id, str) or not ENTITY_ID.fullmatch(entity_id) or not isinstance(device_id, str) or not DEVICE_ID.fullmatch(device_id):
            raise UserError("Choose a NUT sensor from the saved UPS.", "Refresh the power-source list and choose Enable beside that sensor.")
        row = self.command("config/entity_registry/get", entity_id=entity_id)
        if not isinstance(row, dict) or row.get("platform") != "nut" or row.get("device_id") != device_id or row.get("entity_id") != entity_id:
            raise UserError("This sensor no longer belongs to the selected NUT UPS.", "Find power sources again and review the saved UPS.")
        if row.get("disabled_by") is None:
            return {"already_enabled": True, "require_restart": False}
        if row.get("disabled_by") not in ("integration", "user"):
            raise UserError("This sensor's device or integration is disabled.", "Enable the NUT device or integration in Home Assistant first.")
        result = self.command("config/entity_registry/update", entity_id=entity_id, disabled_by=None)
        returned = result.get("entity_entry") if isinstance(result, dict) else None
        if not isinstance(returned, dict) or returned.get("entity_id") != entity_id or returned.get("disabled_by") is not None:
            raise UserError("The enabled sensor could not be confirmed.", "Open its NUT device page and check whether it is enabled. Do not repeat an uncertain request automatically.")
        return {"already_enabled": False, "require_restart": result.get("require_restart") is True,
                "reload_delay": result.get("reload_delay") if type(result.get("reload_delay")) is int else None}
