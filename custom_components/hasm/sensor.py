"""Supervision sensors for a remote HA instance."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import HasmConfigEntry
from .entity import HasmEntity
from .models import HasmSnapshot


@dataclass(frozen=True, kw_only=True)
class HasmSensorDescription(SensorEntityDescription):
    value_fn: Callable[[HasmSnapshot], str | int | None]


SENSORS: tuple[HasmSensorDescription, ...] = (
    HasmSensorDescription(
        key="core_version",
        translation_key="core_version",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda s: s.health.core_version,
    ),
    HasmSensorDescription(
        key="os_version",
        translation_key="os_version",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda s: s.health.os_version,
    ),
    HasmSensorDescription(
        key="supervisor_version",
        translation_key="supervisor_version",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda s: s.health.supervisor_version,
    ),
    HasmSensorDescription(
        key="updates_available",
        translation_key="updates_available",
        native_unit_of_measurement="updates",
        state_class="measurement",
        value_fn=lambda s: s.health.updates_available,
    ),
    HasmSensorDescription(
        key="error_count",
        translation_key="error_count",
        native_unit_of_measurement="errors",
        state_class="measurement",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda s: s.health.error_count,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: HasmConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = entry.runtime_data.coordinator
    async_add_entities(HasmSensor(coordinator, desc) for desc in SENSORS)


class HasmSensor(HasmEntity, SensorEntity):
    entity_description: HasmSensorDescription

    def __init__(self, coordinator, description: HasmSensorDescription) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self):
        if self.coordinator.data is None:
            return None
        return self.entity_description.value_fn(self.coordinator.data)
