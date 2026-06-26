"""Connectivity binary sensor for a remote HA instance."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import slugify

from . import HasmConfigEntry
from .const import MAX_BACKUP_AGENTS
from .entity import HasmEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: HasmConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = entry.runtime_data.coordinator
    async_add_entities([HasmConnectivity(coordinator), HasmBackupInProgress(coordinator)])

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
            new.append(HasmBackupProblem(coordinator, ag))
        if new:
            async_add_entities(new)

    _add_backup_agents()
    entry.async_on_unload(coordinator.async_add_listener(_add_backup_agents))


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


class HasmBackupInProgress(HasmEntity, BinarySensorEntity):
    _attr_translation_key = "backup_in_progress"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "backup_in_progress")

    @property
    def is_on(self) -> bool:
        return bool(
            self.coordinator.data
            and self.coordinator.data.backups
            and self.coordinator.data.backups.in_progress
        )


class HasmBackupProblem(HasmEntity, BinarySensorEntity):
    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_translation_key = "backup_problem"

    def __init__(self, coordinator, agent) -> None:
        super().__init__(coordinator, f"backup_problem_{slugify(agent.agent_id)}")
        self._agent_id = agent.agent_id
        self._attr_translation_placeholders = {"agent": agent.name or agent.agent_id}

    @property
    def is_on(self) -> bool:
        ov = self.coordinator.data.backups if self.coordinator.data else None
        s = (
            next((x for x in ov.per_agent if x.agent_id == self._agent_id), None)
            if ov
            else None
        )
        return bool(s and s.has_problem)
