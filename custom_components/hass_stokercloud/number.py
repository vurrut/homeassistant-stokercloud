"""Number platform for NBE Stoker Cloud."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.const import CONF_USERNAME, UnitOfTemperature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from stokercloud.client import Client as StokerCloudClient

from .const import DOMAIN
from .mixins import StokerCloudControllerMixin

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the number platform."""
    client: StokerCloudClient = hass.data[DOMAIN][entry.entry_id]
    serial = entry.data[CONF_USERNAME]
    
    # Only add number entities if password is configured (write access)
    has_password = entry.data.get("password") is not None
    
    entities = []
    
    if has_password:
        entities.append(
            StokerCloudBoilerTempNumber(
                client, 
                serial, 
                "Wanted Boiler Temperature", 
                "wantedboilertemp"
            )
        )
    
    async_add_entities(entities)


class StokerCloudBoilerTempNumber(StokerCloudControllerMixin, NumberEntity):
    """Representation of a writable number entity for boiler temperature."""

    _attr_native_min_value = 30
    _attr_native_max_value = 90
    _attr_native_step = 1
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_mode = NumberMode.SLIDER

    def __init__(
        self, 
        client: StokerCloudClient, 
        serial: str, 
        name: str, 
        client_key: str
    ):
        """Initialize the number entity."""
        super().__init__(client, serial, name, client_key)

    @property
    def native_value(self) -> float | None:
        """Return the current value."""
        if self._state and hasattr(self._state, 'value'):
            return float(self._state.value)
        return None

    async def async_set_native_value(self, value: float) -> None:
        """Set new value."""
        try:
            _LOGGER.info(f"Setting boiler temperature to {value}°C")
            await self.hass.async_add_executor_job(
                self._client.set_boiler_temp, value
            )
            
            # Update state
            await self.async_update()
            self.async_write_ha_state()
            
        except Exception as e:
            _LOGGER.error(f"Failed to set temperature: {e}")