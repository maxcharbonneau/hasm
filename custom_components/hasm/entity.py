"""Common base for HASM entities."""

from __future__ import annotations

from homeassistant.const import CONF_URL
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import HasmDataUpdateCoordinator


class HasmEntity(CoordinatorEntity[HasmDataUpdateCoordinator]):
    """Entity attached to the device of a remote HA instance."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: HasmDataUpdateCoordinator, key: str) -> None:
        super().__init__(coordinator)
        self._key = key
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.config_entry.entry_id)},
            name=coordinator.config_entry.title,
            manufacturer="Home Assistant Site Manager",
            model="Remote HA instance",
            sw_version=coordinator.data.health.core_version
            if coordinator.data
            else None,
            configuration_url=coordinator.config_entry.data.get(CONF_URL),
        )

    @property
    def available(self) -> bool:
        return (
            super().available
            and self.coordinator.data is not None
            and self.coordinator.data.health.online
        )
