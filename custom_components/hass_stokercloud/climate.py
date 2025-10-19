"""Climate platform for NBE Stoker Cloud."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, CONF_USERNAME, UnitOfTemperature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from stokercloud.client import Client as StokerCloudClient
from stokercloud.controller_data import PowerState

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the climate platform."""
    client: StokerCloudClient = hass.data[DOMAIN][entry.entry_id]
    serial = entry.data[CONF_USERNAME]
    
    # Only add climate entity if password is configured (write access)
    has_password = entry.data.get("password") is not None
    
    entities = []
    
    if has_password:
        entities.append(StokerCloudBoilerClimate(client, serial, "Boiler"))
    
    async_add_entities(entities)


class StokerCloudBoilerClimate(ClimateEntity):
    """Representation of a Stokercloud Boiler Climate entity."""

    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_hvac_modes = [HVACMode.HEAT, HVACMode.OFF]
    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE
    _attr_min_temp = 30
    _attr_max_temp = 90
    _attr_target_temperature_step = 1

    def __init__(self, client: StokerCloudClient, serial: str, name: str):
        """Initialize the climate entity."""
        self._client = client
        self._serial = serial
        self._attr_name = f"NBE {name}"
        self._attr_unique_id = f"{serial}-{name.lower()}-climate"
        self._controller_data = None
        
        # Device info
        self._attr_device_info = {
            "identifiers": {(DOMAIN, serial)},
            "name": f"NBE Stokercloud {serial}",
            "manufacturer": "NBE",
            "model": "Stokercloud",
        }

    async def async_update(self) -> None:
        """Fetch new state data for the climate entity."""
        try:
            await self._client.async_get_data()
            self._controller_data = self._client.controller_data()
        except Exception as e:
            _LOGGER.error(f"Error updating {self.name}: {e}")

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        if self._controller_data and self._controller_data.boilertemp:
            return float(self._controller_data.boilertemp.value)
        return None

    @property
    def target_temperature(self) -> float | None:
        """Return the target temperature."""
        if self._controller_data and self._controller_data.wantedboilertemp:
            return float(self._controller_data.wantedboilertemp.value)
        return None

    @property
    def hvac_mode(self) -> HVACMode:
        """Return current HVAC mode."""
        if self._controller_data and self._controller_data.running == PowerState.ON:
            return HVACMode.HEAT
        return HVACMode.OFF

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return

        try:
            _LOGGER.info(f"Setting boiler temperature to {temperature}°C")
            await self._client.async_set_boiler_temp(temperature)
            
            # Wait a bit for the change to take effect
            import asyncio
            await asyncio.sleep(2)
            
            # Update to reflect the change
            await self.async_update()
            self.async_write_ha_state()
            
        except Exception as e:
            _LOGGER.error(f"Failed to set temperature: {e}")

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set HVAC mode."""
        # Note: Stokercloud doesn't support turning on/off via API
        # This is here for interface compatibility but doesn't do anything
        _LOGGER.warning(f"Setting HVAC mode not supported for {self.name}")

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self._controller_data is not None