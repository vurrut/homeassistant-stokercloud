"""Config flow for NBE StokerCloud."""
from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from stokercloud import Client, StokerCloudAuthError, StokerCloudError

from .const import DOMAIN

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
