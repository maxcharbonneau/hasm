from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.config_entries import ConfigEntryState
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hasm.const import DOMAIN
from custom_components.hasm.const import SERVICE_CALL_REMOTE
from custom_components.hasm.models import HAHealth, HasmSnapshot


@pytest.fixture
def mock_entry():
    return MockConfigEntry(
        domain=DOMAIN,
        title="Maison",
        data={"url": "https://ha.example", "token": "TOKEN", "verify_ssl": True},
        options={"scan_interval": 120},
        unique_id="ha-uuid-1",
    )


async def test_setup_and_unload(hass, mock_entry):
    mock_entry.add_to_hass(hass)
    snap = HasmSnapshot(
        health=HAHealth(online=True, core_version="2026.6.3"), location_name="Maison"
    )
    with patch(
        "custom_components.hasm.HasmApiClient.async_get_snapshot",
        new=AsyncMock(return_value=snap),
    ):
        assert await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()
        assert mock_entry.state is ConfigEntryState.LOADED

        assert await hass.config_entries.async_unload(mock_entry.entry_id)
        await hass.async_block_till_done()
        assert mock_entry.state is ConfigEntryState.NOT_LOADED


async def test_call_remote_service_relays_to_client(hass, mock_entry):
    mock_entry.add_to_hass(hass)
    snap_patch = patch(
        "custom_components.hasm.HasmApiClient.async_get_snapshot",
        new=AsyncMock(return_value=HasmSnapshot(health=HAHealth(online=True))),
    )
    call_mock = AsyncMock()
    with (
        snap_patch,
        patch("custom_components.hasm.HasmApiClient.async_call_service", new=call_mock),
    ):
        assert await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()
        assert hass.services.has_service("hasm", SERVICE_CALL_REMOTE)
        await hass.services.async_call(
            "hasm",
            SERVICE_CALL_REMOTE,
            {
                "config_entry_id": mock_entry.entry_id,
                "remote_domain": "homeassistant",
                "remote_service": "restart",
                "service_data": {},
            },
            blocking=True,
        )
    call_mock.assert_awaited_once_with("homeassistant", "restart", {})


async def test_call_remote_service_unknown_entry_raises(hass, mock_entry):
    from homeassistant.exceptions import ServiceValidationError

    mock_entry.add_to_hass(hass)
    snap = HasmSnapshot(health=HAHealth(online=True))
    with patch(
        "custom_components.hasm.HasmApiClient.async_get_snapshot",
        new=AsyncMock(return_value=snap),
    ):
        assert await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()
        assert hass.services.has_service("hasm", SERVICE_CALL_REMOTE)
        with pytest.raises(ServiceValidationError):
            await hass.services.async_call(
                "hasm",
                SERVICE_CALL_REMOTE,
                {
                    "config_entry_id": "does-not-exist",
                    "remote_domain": "homeassistant",
                    "remote_service": "restart",
                    "service_data": {},
                },
                blocking=True,
            )
