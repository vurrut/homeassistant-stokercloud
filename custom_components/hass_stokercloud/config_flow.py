"""Config flow for NBE StokerCloud."""
from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from stokercloud import Client, StokerCloudAuthError, StokerCloudError

from .const import (
    CONF_CALORIFIC_VALUE,
    CONF_SCAN_INTERVAL,
    DEFAULT_CALORIFIC_VALUE,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MIN_SCAN_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)

USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)
REAUTH_SCHEMA = vol.Schema({vol.Required(CONF_PASSWORD): str})


class StokerCloudConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for StokerCloud."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return StokerCloudOptionsFlow()

    async def _async_validate(self, username: str, password: str) -> dict[str, str]:
        """Log in and fetch data once. Returns an errors dict (empty when OK)."""
        try:
            client = Client(username, async_get_clientsession(self.hass), password=password)
            await client.async_get_data()
        except StokerCloudAuthError:
            return {"base": "invalid_auth"}
        except StokerCloudError:
            return {"base": "cannot_connect"}
        except Exception:  # noqa: BLE001
            _LOGGER.exception("Unexpected error validating StokerCloud login")
            return {"base": "unknown"}
        return {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            username = user_input[CONF_USERNAME].strip()
            await self.async_set_unique_id(username)
            self._abort_if_unique_id_configured()
            errors = await self._async_validate(username, user_input[CONF_PASSWORD])
            if not errors:
                return self.async_create_entry(
                    title=f"Stokercloud ({username})",
                    data={CONF_USERNAME: username, CONF_PASSWORD: user_input[CONF_PASSWORD]},
                )
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(USER_SCHEMA, user_input),
            errors=errors,
        )

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        """Triggered when the password is missing (old entries) or rejected."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        entry = self._get_reauth_entry()
        username = entry.data[CONF_USERNAME]
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = await self._async_validate(username, user_input[CONF_PASSWORD])
            if not errors:
                return self.async_update_reload_and_abort(
                    entry,
                    title=f"Stokercloud ({username})",
                    data_updates={CONF_PASSWORD: user_input[CONF_PASSWORD]},
                )
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=REAUTH_SCHEMA,
            description_placeholders={"username": username},
            errors=errors,
        )


class StokerCloudOptionsFlow(OptionsFlow):
    """Update interval and pellet calorific value."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        options = self.config_entry.options
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_SCAN_INTERVAL,
                    default=options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
                ): vol.All(vol.Coerce(int), vol.Range(min=MIN_SCAN_INTERVAL, max=3600)),
                vol.Required(
                    CONF_CALORIFIC_VALUE,
                    default=options.get(CONF_CALORIFIC_VALUE, DEFAULT_CALORIFIC_VALUE),
                ): vol.All(vol.Coerce(float), vol.Range(min=1, max=10)),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
