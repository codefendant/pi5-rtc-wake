"""Read-only status, timing, and selected UPS measurements."""

from datetime import datetime, timezone

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.const import PERCENTAGE, UnitOfTime

from .entity import PiEntity

SENSORS = (
    ("uptime_seconds", "Uptime", "mdi:timer-outline", SensorDeviceClass.DURATION, UnitOfTime.SECONDS),
    ("next_sleep_epoch", "Next shutdown", "mdi:power-sleep", SensorDeviceClass.TIMESTAMP, None),
    ("next_wake_epoch", "Next wake", "mdi:white-balance-sunny", SensorDeviceClass.TIMESTAMP, None),
    ("battery_percent", "UPS battery", "mdi:battery", SensorDeviceClass.BATTERY, PERCENTAGE),
    ("runtime_seconds", "UPS runtime", "mdi:timer-sand", SensorDeviceClass.DURATION, UnitOfTime.SECONDS),
    ("power_state", "UPS power", "mdi:power-plug", None, None),
)


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([PiSensor(entry.runtime_data, *row) for row in SENSORS])


class PiSensor(PiEntity, SensorEntity):
    def __init__(self, coordinator, key, name, icon, device_class, unit):
        super().__init__(coordinator, key, name, icon)
        self._attr_device_class = device_class
        self._attr_native_unit_of_measurement = unit
        if key == "battery_percent":
            self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self):
        data = self.coordinator.data or {}
        if self.key in ("battery_percent", "runtime_seconds", "power_state"):
            source = data.get("ups", {}).get("selected") or {}
            return source.get(self.key) if source.get("ok") else None
        if self.key in ("next_sleep_epoch", "next_wake_epoch"):
            value = data.get(self.key) if data.get("schedule_active") else None
            return datetime.fromtimestamp(value, timezone.utc) if value else None
        return data.get(self.key)
