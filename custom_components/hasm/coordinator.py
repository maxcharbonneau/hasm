"""Polling coordinator for a remote HA instance."""

from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import HasmApiClient
from .const import DOMAIN
from .exceptions import HasmAuthError, HasmError
from .models import HasmSnapshot

_LOGGER = logging.getLogger(__name__)


class HasmDataUpdateCoordinator(DataUpdateCoordinator[HasmSnapshot]):
    """Polls a remote HA instance at a regular interval."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: HasmApiClient,
        *,
        scan_interval: int,
        name: str,
        entry: ConfigEntry | None = None,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN} {name}",
            update_interval=timedelta(seconds=scan_interval),
            config_entry=entry,
        )
        self.client = client

    async def _async_update_data(self) -> HasmSnapshot:
        try:
            return await self.client.async_get_snapshot()
        except HasmAuthError as e:
            raise ConfigEntryAuthFailed(str(e)) from e
        except HasmError as e:
            raise UpdateFailed(str(e)) from e
