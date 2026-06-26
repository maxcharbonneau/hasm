"""Tests for the HASM config flow."""

from unittest.mock import AsyncMock, patch

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hasm.const import DOMAIN
from custom_components.hasm.exceptions import HasmAuthError, HasmConnectionError
from custom_components.hasm.models import HAConfig

USER_INPUT = {"url": "https://ha.example", "token": "TOKEN", "verify_ssl": True}


def _patch_validate(side_effect=None, config=None, unique_id="ha-uuid-1"):
    cfg = config or HAConfig(
        core_version="2026.6.3", location_name="Maison", components=[]
    )
    return patch(
        "custom_components.hasm.config_flow._async_validate",
        new=AsyncMock(side_effect=side_effect, return_value=(cfg, unique_id)),
    )


async def test_user_flow_success(hass):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    with _patch_validate():
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], USER_INPUT
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Maison"
    assert result["data"]["url"] == "https://ha.example"


async def test_user_flow_cannot_connect(hass):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    with _patch_validate(side_effect=HasmConnectionError("down")):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], USER_INPUT
        )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_user_flow_invalid_auth(hass):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    with _patch_validate(side_effect=HasmAuthError("nope")):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], USER_INPUT
        )
    assert result["errors"] == {"base": "invalid_auth"}


async def test_options_flow_sets_scan_interval(hass):
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Maison",
        data={**USER_INPUT},
        options={},
        unique_id="https://ha.example",
    )
    entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"scan_interval": 300}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"]["scan_interval"] == 300


async def test_reconfigure_updates_token(hass):
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Maison",
        data={**USER_INPUT},
        unique_id="https://ha.example",
    )
    entry.add_to_hass(hass)
    result = await entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    # _async_validate derives the unique_id from the URL: url.rstrip('/').lower()
    # => "https://ha.example", consistent with the entry's. So we align the
    # patched value with this real behavior (instead of "ha-uuid-1") so as NOT
    # to weaken the mismatch check in production.
    with _patch_validate(unique_id="https://ha.example"):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"url": "https://ha.example", "token": "NEW", "verify_ssl": True},
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data["token"] == "NEW"


def _patch_validate_components(components):
    cfg = HAConfig(core_version="2026.6.1", location_name="X", components=components)
    return patch(
        "custom_components.hasm.config_flow._async_validate",
        new=AsyncMock(return_value=(cfg, "https://ha.example")),
    )


async def test_user_flow_warns_when_remote_runs_hasm(hass):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    with _patch_validate_components(["sensor", "hasm"]):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], USER_INPUT)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "loop_warning"
    # acknowledge -> entry created
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"]["url"] == "https://ha.example"


async def test_user_flow_no_warning_when_no_hasm(hass):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    with _patch_validate_components(["sensor"]):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], USER_INPUT)
    assert result["type"] is FlowResultType.CREATE_ENTRY
