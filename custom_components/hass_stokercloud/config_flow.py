"""Config flow for Stokercloud integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Optional(CONF_PASSWORD): str,
    }
)


class StokerCloudConnectionError(Exception):
    """Error to indicate we cannot connect."""
    pass


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect."""
    session = async_get_clientsession(hass)
    
    # Import Client from stokercloud library
    from stokercloud.client import Client
    
    # Get password if provided
    password = data.get(CONF_PASSWORD)
    
    # Create client with or without password
    client = Client(data[CONF_USERNAME], session, password=password)
    
    # Test the connection
    try:
        await client.authenticate()
        await client.async_get_data()
    except Exception as e:
        raise StokerCloudConnectionError(f"Cannot connect: {e}")
    
    # Return info that you want to store in the config entry
    title = f"Stokercloud ({data[CONF_USERNAME]})"
    if password:
        title += " (with write access)"
    
    return {"title": title}


class StokerCloudConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Stokercloud."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        
        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
            except StokerCloudConnectionError:
                errors["base"] = "cannot_connect"
            except StokerCloudError:
                errors["base"] = "unknown"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                # Check if already configured
                await self.async_set_unique_id(user_input[CONF_USERNAME])
                self._abort_if_unique_id_configured()
                
                return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user", 
            data_schema=STEP_USER_DATA_SCHEMA, 
            errors=errors
        )