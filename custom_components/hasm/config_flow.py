"""Config flow for the HASM integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_TOKEN, CONF_URL
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import HasmApiClient
from .const import (
    CONF_MAX_UPDATE_ENTITIES,
    CONF_SCAN_INTERVAL,
    CONF_VERIFY_SSL,
    DEFAULT_MAX_UPDATE_ENTITIES,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_TIMEOUT,
    DOMAIN,
    MAX_MAX_UPDATE_ENTITIES,
    MIN_MAX_UPDATE_ENTITIES,
)
from .exceptions import HasmAuthError, HasmConnectionError
from .models import HAConfig

STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_URL): str,
        vol.Required(CONF_TOKEN): str,
        vol.Optional(CONF_VERIFY_SSL, default=True): bool,
    }
)


async def _async_validate(
    hass: HomeAssistant, url: str, token: str, verify_ssl: bool
) -> tuple[HAConfig, str | None]:
    """Tests the connection. Returns (config, unique_id). Raises Hasm*Error otherwise."""
    session = async_get_clientsession(hass, verify_ssl=verify_ssl)
    client = HasmApiClient(
        url, token, session, verify_ssl=verify_ssl, timeout=DEFAULT_TIMEOUT
    )
    config = await client.async_get_config()
    unique_id = url.rstrip("/").lower()
    return config, unique_id


class HasmConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handles adding a remote HA instance."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry) -> "HasmOptionsFlow":
        return HasmOptionsFlow()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                config, unique_id = await _async_validate(
                    self.hass,
                    user_input[CONF_URL],
                    user_input[CONF_TOKEN],
                    user_input.get(CONF_VERIFY_SSL, True),
                )
            except HasmAuthError:
                errors["base"] = "invalid_auth"
            except HasmConnectionError:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                errors["base"] = "unknown"
            else:
                if unique_id:
                    await self.async_set_unique_id(unique_id)
                    self._abort_if_unique_id_configured()
                title = config.location_name or user_input[CONF_URL]
                return self.async_create_entry(title=title, data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_SCHEMA, errors=errors
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                config, unique_id = await _async_validate(
                    self.hass,
                    user_input[CONF_URL],
                    user_input[CONF_TOKEN],
                    user_input.get(CONF_VERIFY_SSL, True),
                )
            except HasmAuthError:
                errors["base"] = "invalid_auth"
            except HasmConnectionError:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_mismatch(reason="wrong_instance")
                return self.async_update_reload_and_abort(entry, data=user_input)

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_SCHEMA, entry.data
            ),
            errors=errors,
        )


class HasmOptionsFlow(OptionsFlow):
    """Handles the options (polling interval, verify_ssl)."""

    async def async_step_init(self, user_input=None) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        current = self.config_entry.options.get(
            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
        )
        schema = vol.Schema(
            {
                vol.Optional(CONF_SCAN_INTERVAL, default=current): vol.All(
                    int, vol.Range(min=30, max=3600)
                ),
                vol.Optional(
                    CONF_VERIFY_SSL,
                    default=self.config_entry.data.get(CONF_VERIFY_SSL, True),
                ): bool,
                vol.Optional(
                    CONF_MAX_UPDATE_ENTITIES,
                    default=self.config_entry.options.get(
                        CONF_MAX_UPDATE_ENTITIES, DEFAULT_MAX_UPDATE_ENTITIES
                    ),
                ): vol.All(
                    int,
                    vol.Range(min=MIN_MAX_UPDATE_ENTITIES, max=MAX_MAX_UPDATE_ENTITIES),
                ),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
