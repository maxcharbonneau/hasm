"""Supervision sensors for a remote HA instance."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import slugify

from . import HasmConfigEntry
from .const import MAX_BACKUP_AGENTS
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
    async_add_entities([
        HasmGlobalBackupSensor(coordinator, "backup_last_completed", "last_completed_at"),
        HasmGlobalBackupSensor(coordinator, "backup_next", "next_at"),
    ])

    async_add_entities([
        HasmServerUsageSensor(coordinator, "cpu_usage", "cpu_percent"),
        HasmServerUsageSensor(coordinator, "memory_usage", "memory_percent"),
        HasmServerUsageSensor(coordinator, "disk_usage", "disk_percent"),
    ])

    known_agents: set[str] = set()

    @callback
    def _add_backup_agents() -> None:
        ov = coordinator.data.backups if coordinator.data else None
        if ov is None:
            return
        new = []
        for ag in ov.agents:
            if ag.agent_id in known_agents:
                continue
            if len(known_agents) >= MAX_BACKUP_AGENTS:
                break
            known_agents.add(ag.agent_id)
            new.extend([
                HasmBackupSizeSensor(coordinator, ag),
                HasmBackupLastFullSensor(coordinator, ag),
                HasmBackupCountSensor(coordinator, ag),
            ])
        if new:
            async_add_entities(new)

    _add_backup_agents()
    entry.async_on_unload(coordinator.async_add_listener(_add_backup_agents))


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


class HasmGlobalBackupSensor(HasmEntity, SensorEntity):
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, coordinator, key: str, field: str) -> None:
        super().__init__(coordinator, key)
        self._attr_translation_key = key
        self._field = field

    @property
    def native_value(self):
        from homeassistant.util import dt as dt_util
        ov = self.coordinator.data.backups if self.coordinator.data else None
        if ov is None:
            return None
        raw = getattr(ov, self._field)
        return dt_util.parse_datetime(raw) if raw else None


class HasmServerUsageSensor(HasmEntity, SensorEntity):
    _attr_native_unit_of_measurement = "%"
    _attr_state_class = "measurement"

    def __init__(self, coordinator, key: str, usage_attr: str) -> None:
        super().__init__(coordinator, key)
        self._usage_attr = usage_attr
        self._attr_translation_key = key

    @property
    def native_value(self):
        su = self.coordinator.data.server_usage if self.coordinator.data else None
        return getattr(su, self._usage_attr) if su else None


class _HasmAgentSensorBase(HasmEntity, SensorEntity):
    _key_prefix: str

    def __init__(self, coordinator, agent) -> None:
        super().__init__(coordinator, f"{self._key_prefix}_{slugify(agent.agent_id)}")
        self._agent_id = agent.agent_id
        self._attr_translation_placeholders = {"agent": agent.name or agent.agent_id}

    def _summary(self):
        ov = self.coordinator.data.backups if self.coordinator.data else None
        if ov is None:
            return None
        return next((s for s in ov.per_agent if s.agent_id == self._agent_id), None)


class HasmBackupSizeSensor(_HasmAgentSensorBase):
    _key_prefix = "backup_size"
    _attr_translation_key = "backup_size"
    # Presented directly in MB. We intentionally do NOT use device_class DATA_SIZE:
    # its unit conversion is seeded from the entity registry on first registration, so a
    # suggested MB unit does not apply to entities already registered under an earlier
    # version (they stayed in bytes). A plain MB native unit is deterministic on both
    # fresh installs and updates.
    _attr_native_unit_of_measurement = "MB"
    _attr_suggested_display_precision = 1
    _attr_state_class = "measurement"

    @property
    def native_value(self):
        s = self._summary()
        return round(s.total_size_bytes / 1_000_000, 1) if s else None


class HasmBackupLastFullSensor(_HasmAgentSensorBase):
    _key_prefix = "backup_last_full"
    _attr_translation_key = "backup_last_full"
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    @property
    def native_value(self):
        from homeassistant.util import dt as dt_util
        s = self._summary()
        return dt_util.parse_datetime(s.last_full_at) if (s and s.last_full_at) else None


class HasmBackupCountSensor(_HasmAgentSensorBase):
    _key_prefix = "backup_count"
    _attr_translation_key = "backup_count"
    _attr_state_class = "measurement"

    @property
    def native_value(self):
        s = self._summary()
        return s.backup_count if s else None
