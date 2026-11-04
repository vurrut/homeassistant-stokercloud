"""NBE StokerCloud integration."""
from __future__ import annotations

import logging

from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType

from stokercloud import Client, StokerCloudAuthError

from .const import (
    CONF_CALORIFIC_VALUE,
    CONF_IMPORT_STATISTICS,
    DEFAULT_CALORIFIC_VALUE,
    DEFAULT_IMPORT_STATISTICS,
    DOMAIN,
    PLATFORMS,
)
from .coordinator import StokerCloudConfigEntry, StokerCloudCoordinator
from .services import async_setup_services

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register integration-wide services."""
    async_setup_services(hass)
    return True


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
    if (
        entry.options.get(CONF_IMPORT_STATISTICS, DEFAULT_IMPORT_STATISTICS)
        and "recorder" in hass.config.components
    ):
        from .statistics import StatisticsImporter  # noqa: PLC0415 - needs recorder

        importer = StatisticsImporter(
            hass,
            entry.data[CONF_USERNAME],
            entry.options.get(CONF_CALORIFIC_VALUE, DEFAULT_CALORIFIC_VALUE),
        )
        coordinator.history_listeners.append(importer.async_import)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))
    return True


async def _async_options_updated(hass: HomeAssistant, entry: StokerCloudConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: StokerCloudConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
