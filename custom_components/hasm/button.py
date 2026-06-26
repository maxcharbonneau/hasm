"""Action buttons for a remote HA instance."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import HasmConfigEntry
from .api import HasmApiClient
from .const import BACKUP_TRIGGER_DOMAIN, BACKUP_TRIGGER_SERVICE
from .entity import HasmEntity


@dataclass(frozen=True, kw_only=True)
class HasmButtonDescription(ButtonEntityDescription):
    press_fn: Callable[[HasmApiClient], Coroutine[Any, Any, None]]


BUTTONS: tuple[HasmButtonDescription, ...] = (
    HasmButtonDescription(
        key="restart",
        translation_key="restart",
        device_class="restart",
        entity_category=EntityCategory.CONFIG,
        press_fn=lambda client: client.async_call_service("homeassistant", "restart"),
    ),
    HasmButtonDescription(
        key="reload_config",
        translation_key="reload_config",
        entity_category=EntityCategory.CONFIG,
        press_fn=lambda client: client.async_call_service(
            "homeassistant", "reload_core_config"
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: HasmConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = entry.runtime_data.coordinator
    async_add_entities(HasmButton(coordinator, desc) for desc in BUTTONS)
    async_add_entities([HasmBackupNowButton(coordinator)])


class HasmButton(HasmEntity, ButtonEntity):
    entity_description: HasmButtonDescription

    def __init__(self, coordinator, description: HasmButtonDescription) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    async def async_press(self) -> None:
        await self.entity_description.press_fn(self.coordinator.client)


class HasmBackupNowButton(HasmEntity, ButtonEntity):
    _attr_translation_key = "backup_now"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "backup_now")

    @property
    def available(self) -> bool:
        if not super().available:
            return False
        ov = self.coordinator.data.backups if self.coordinator.data else None
        return ov is not None and not ov.in_progress

    async def async_press(self) -> None:
        await self.coordinator.client.async_call_service(
            BACKUP_TRIGGER_DOMAIN, BACKUP_TRIGGER_SERVICE
        )
        await self.coordinator.async_request_refresh()
