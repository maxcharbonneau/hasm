"""Home Assistant Site Manager (HASM) integration."""

from __future__ import annotations

from dataclasses import dataclass

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_TOKEN, CONF_URL
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import HasmApiClient
from .const import (
    ATTR_DOMAIN,
    ATTR_SERVICE,
    ATTR_SERVICE_DATA,
    CONF_SCAN_INTERVAL,
    CONF_VERIFY_SSL,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_TIMEOUT,
    DOMAIN,
    PLATFORMS,
    SERVICE_CALL_REMOTE,
)
from .coordinator import HasmDataUpdateCoordinator


@dataclass
class HasmRuntimeData:
    coordinator: HasmDataUpdateCoordinator
    client: HasmApiClient


type HasmConfigEntry = ConfigEntry[HasmRuntimeData]


CALL_REMOTE_SCHEMA = vol.Schema(
    {
        vol.Required("config_entry_id"): cv.string,
        vol.Required(ATTR_DOMAIN): cv.string,
        vol.Required(ATTR_SERVICE): cv.string,
        vol.Optional(ATTR_SERVICE_DATA, default={}): dict,
    }
)


def _register_services(hass: HomeAssistant) -> None:
    if hass.services.has_service(DOMAIN, SERVICE_CALL_REMOTE):
        return

    async def _handle_call_remote(call: ServiceCall) -> None:
        entry_id = call.data["config_entry_id"]
        entry = hass.config_entries.async_get_entry(entry_id)
        if (
            entry is None
            or entry.domain != DOMAIN
            or getattr(entry, "runtime_data", None) is None
        ):
            raise ServiceValidationError(f"HASM instance not found: {entry_id}")
        client = entry.runtime_data.client
        await client.async_call_service(
            call.data[ATTR_DOMAIN],
            call.data[ATTR_SERVICE],
            call.data[ATTR_SERVICE_DATA],
        )

    hass.services.async_register(
        DOMAIN, SERVICE_CALL_REMOTE, _handle_call_remote, schema=CALL_REMOTE_SCHEMA
    )


async def async_setup_entry(hass: HomeAssistant, entry: HasmConfigEntry) -> bool:
    verify_ssl = entry.data.get(CONF_VERIFY_SSL, True)
    session = async_get_clientsession(hass, verify_ssl=verify_ssl)
    client = HasmApiClient(
        entry.data[CONF_URL],
        entry.data[CONF_TOKEN],
        session,
        verify_ssl=verify_ssl,
        timeout=DEFAULT_TIMEOUT,
    )
    scan_interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    coordinator = HasmDataUpdateCoordinator(
        hass, client, scan_interval=scan_interval, name=entry.title, entry=entry
    )
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = HasmRuntimeData(coordinator=coordinator, client=client)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload_on_update))
    _register_services(hass)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: HasmConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_reload_on_update(hass: HomeAssistant, entry: HasmConfigEntry) -> None:
    """Reload the entry when the options (interval, verify_ssl) change."""
    await hass.config_entries.async_reload(entry.entry_id)
