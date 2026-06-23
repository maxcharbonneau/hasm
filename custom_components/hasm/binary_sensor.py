"""Connectivity binary sensor for a remote HA instance."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import HasmConfigEntry
from .entity import HasmEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: HasmConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    async_add_entities([HasmConnectivity(entry.runtime_data.coordinator)])


class HasmConnectivity(HasmEntity, BinarySensorEntity):
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_translation_key = "connectivity"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "connectivity")

    @property
    def available(self) -> bool:
        # Always available once a poll has happened: must be able to report "off".
        return self.coordinator.last_update_success or self.coordinator.data is not None

    @property
    def is_on(self) -> bool:
        return bool(self.coordinator.data and self.coordinator.data.health.online)
