"""NBE StokerCloud integration."""
from __future__ import annotations

import logging

from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from stokercloud import Client, StokerCloudAuthError

from .const import PLATFORMS
from .coordinator import StokerCloudConfigEntry, StokerCloudCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: StokerCloudConfigEntry) -> bool:
    """Set up StokerCloud from a config entry."""
    password = entry.data.get(CONF_PASSWORD)
    if not password:
        # Entries created by v1/v2 may only have a username: ask for the password.
        raise ConfigEntryAuthFailed("A StokerCloud password is now required")

    try:
        client = Client(
            entry.data[CONF_USERNAME],
            async_get_clientsession(hass),
            password=password,
        )
    except StokerCloudAuthError as err:
        raise ConfigEntryAuthFailed(str(err)) from err

    coordinator = StokerCloudCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: StokerCloudConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
