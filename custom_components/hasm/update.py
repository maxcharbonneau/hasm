"""Native update.* entities mirroring the updates of remote instances."""

from __future__ import annotations

import logging

from homeassistant.components import persistent_notification
from homeassistant.components.update import (
    UpdateEntity,
    UpdateEntityFeature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import HasmConfigEntry
from .const import CONF_MAX_UPDATE_ENTITIES, DEFAULT_MAX_UPDATE_ENTITIES
from .entity import HasmEntity
from .models import HAUpdate

_LOGGER = logging.getLogger(__name__)


@callback
def _warn_cap_reached(
    hass: HomeAssistant, entry: HasmConfigEntry, max_entities: int
) -> None:
    """Warns (WARNING log + persistent notification) that the update entity cap
    has been reached. Idempotent on the notification side thanks to a stable
    notification_id; the call is triggered only once anyway (`warned` flag)."""
    title = entry.title
    lang = (getattr(hass.config, "language", None) or "en").lower()
    if lang.startswith("fr"):
        notif_title = "HASM : limite d'entités atteinte"
        message = (
            f"L'instance « {title} » expose plus de {max_entities} entités de mise "
            "à jour ; au-delà de cette limite, les entités supplémentaires ne sont "
            "plus créées (protection anti-surcharge). Augmentez la limite dans les "
            "options de l'intégration si c'est attendu, ou vérifiez la configuration "
            "(une instance qui se supervise elle-même peut générer des entités en "
            "boucle)."
        )
    else:
        notif_title = "HASM: update entity limit reached"
        message = (
            f"Instance “{title}” exposes more than {max_entities} update "
            "entities; beyond this limit, extra ones are no longer created (overload "
            "protection). Raise the limit in the integration options if this is "
            "expected, or check the configuration (an instance supervising itself can "
            "generate entities in a loop)."
        )
    _LOGGER.warning(
        "Update entity cap reached (%s) for %s - extra entities not created "
        "(overload protection). Raise the limit in the options, or check the "
        "configuration (self-supervision loop?).",
        max_entities,
        title,
    )
    persistent_notification.async_create(
        hass,
        message,
        title=notif_title,
        notification_id=f"hasm_update_cap_{entry.entry_id}",
    )


async def async_setup_entry(
    hass: HomeAssistant, entry: HasmConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = entry.runtime_data.coordinator
    known: set[str] = set()
    warned = False

    @callback
    def _add_new() -> None:
        nonlocal warned
        if coordinator.data is None:
            return
        max_entities = entry.options.get(
            CONF_MAX_UPDATE_ENTITIES, DEFAULT_MAX_UPDATE_ENTITIES
        )
        new = []
        for upd in coordinator.data.updates:
            if upd.entity_id in known:
                continue
            if len(known) >= max_entities:
                if not warned:
                    warned = True
                    _warn_cap_reached(hass, entry, max_entities)
                break
            known.add(upd.entity_id)
            new.append(HasmUpdate(coordinator, upd.entity_id))
        if new:
            async_add_entities(new)

    _add_new()
    entry.async_on_unload(coordinator.async_add_listener(_add_new))


class HasmUpdate(HasmEntity, UpdateEntity):
    """Mirrors a remote update.* entity (Core, OS, Supervisor, add-on...)."""

    # Marks our mirrors: surfaced in /api/states so a remote read
    # (self-supervision / A->B->A chain) can ignore them (see parse_updates).
    _attr_extra_state_attributes = {"hasm_mirror": True}
    # Monochrome MDI icon following the light/dark theme.
    _attr_icon = "mdi:update"

    def __init__(self, coordinator, remote_entity_id: str) -> None:
        super().__init__(coordinator, f"update_{remote_entity_id}")
        self._remote_entity_id = remote_entity_id

    @property
    def entity_picture(self) -> str | None:
        # No hasm brand image -> force None to avoid "icon not available".
        # The monochrome _attr_icon (mdi:update) takes over and follows the theme.
        return None

    def _remote(self) -> HAUpdate | None:
        if self.coordinator.data is None:
            return None
        for upd in self.coordinator.data.updates:
            if upd.entity_id == self._remote_entity_id:
                return upd
        return None

    @property
    def name(self) -> str | None:
        # Deliberate override despite has_entity_name: the remote title ("Core",
        # "Home Assistant OS"...) is clearer than a device-prefixed name.
        upd = self._remote()
        return upd.title if upd and upd.title else self._remote_entity_id

    @property
    def supported_features(self) -> UpdateEntityFeature:
        upd = self._remote()
        features = UpdateEntityFeature.INSTALL
        if upd and upd.supports_backup:
            features |= UpdateEntityFeature.BACKUP
        if upd and upd.supports_progress:
            features |= UpdateEntityFeature.PROGRESS
        return features

    @property
    def installed_version(self) -> str | None:
        upd = self._remote()
        return upd.installed_version if upd else None

    @property
    def latest_version(self) -> str | None:
        upd = self._remote()
        return upd.latest_version if upd else None

    @property
    def in_progress(self) -> bool:
        upd = self._remote()
        return bool(upd and upd.in_progress)

    @property
    def update_percentage(self) -> float | None:
        upd = self._remote()
        return upd.update_percentage if upd else None

    async def async_install(self, version: str | None, backup: bool, **kwargs) -> None:
        await self.coordinator.client.async_install_update(
            self._remote_entity_id, version=version, backup=backup
        )
        await self.coordinator.async_request_refresh()
