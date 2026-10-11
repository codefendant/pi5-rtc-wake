"""Read-only readiness and protection indicators."""

from homeassistant.components.binary_sensor import BinarySensorEntity

from .entity import PiEntity


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([PiBinarySensor(entry.runtime_data, "ready", "Wake ready", "mdi:check-circle-outline"),
                        PiBinarySensor(entry.runtime_data, "scheduling", "Calendar scheduling", "mdi:calendar-clock"),
                        PiBinarySensor(entry.runtime_data, "protection", "UPS emergency protection", "mdi:shield-check-outline")])


class PiBinarySensor(PiEntity, BinarySensorEntity):
    @property
    def is_on(self):
        data = self.coordinator.data or {}
        if self.key == "ready":
            return bool(data.get("checks", {}).get("ok") and data.get("test_status") == "passed")
        if self.key == "scheduling":
            return bool(data.get("schedule_active"))
        return bool(data.get("recovery", {}).get("emergency_active"))
