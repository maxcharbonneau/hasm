from unittest.mock import AsyncMock

import pytest
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.hasm.coordinator import HasmDataUpdateCoordinator
from custom_components.hasm.exceptions import HasmAuthError, HasmConnectionError
from custom_components.hasm.models import HAHealth, HasmSnapshot


@pytest.fixture
def make_coordinator(hass):
    def _make(client):
        return HasmDataUpdateCoordinator(hass, client, scan_interval=120, name="Maison")

    return _make


async def test_coordinator_returns_snapshot(make_coordinator):
    client = AsyncMock()
    snap = HasmSnapshot(health=HAHealth(online=True, core_version="2026.6.3"))
    client.async_get_snapshot.return_value = snap
    coord = make_coordinator(client)
    result = await coord._async_update_data()
    assert result is snap


async def test_coordinator_auth_error_maps_to_reauth(make_coordinator):
    client = AsyncMock()
    client.async_get_snapshot.side_effect = HasmAuthError("nope")
    coord = make_coordinator(client)
    with pytest.raises(ConfigEntryAuthFailed):
        await coord._async_update_data()


async def test_coordinator_connection_error_maps_to_update_failed(make_coordinator):
    client = AsyncMock()
    client.async_get_snapshot.side_effect = HasmConnectionError("down")
    coord = make_coordinator(client)
    with pytest.raises(UpdateFailed):
        await coord._async_update_data()
