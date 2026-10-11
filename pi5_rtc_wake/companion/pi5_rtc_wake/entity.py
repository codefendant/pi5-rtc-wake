"""Shared, read-only Pi entities for user-created Home Assistant cards."""

from homeassistant.helpers.device_registry import DeviceInfo, DeviceEntryType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN


class PiEntity(CoordinatorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator, key, name, icon):
        super().__init__(coordinator)
        self.key = key
        self._attr_name = name
        self._attr_icon = icon
        self._attr_unique_id = coordinator.config_entry.entry_id + "_" + key
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, coordinator.config_entry.entry_id)},
                                           name="Home Assistant Pi", manufacturer="Raspberry Pi", model="Pi 5",
                                           entry_type=DeviceEntryType.SERVICE)
