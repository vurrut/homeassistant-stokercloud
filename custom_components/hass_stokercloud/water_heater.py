"""Water heater platform for NBE Stoker Cloud."""
from __future__ import annotations

import logging

from homeassistant.components.water_heater import WaterHeaterEntity
from homeassistant.const import CONF_USERNAME, UnitOfTemperature, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType
import homeassistant.util.dt as dt_util

from .const import DOMAIN
from .mixins import StokerCloudControllerMixin
from stokercloud.controller_data import State

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config, async_add_entities):
    """Set up the water heater platform."""
    client = hass.data[DOMAIN][config.entry_id]
    serial = config.data[CONF_USERNAME]
    async_add_entities([
        StokerCloudWaterHeater(client, serial, 'Hot Water', ''),
    ])


class StokerCloudWaterHeater(StokerCloudControllerMixin, WaterHeaterEntity):
    """Representation of a Stoker Cloud Water Heater."""
    
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_supported_features = 0

    @property
    def current_operation(self) -> str:
        """Return current operation."""
        if self.controller_data:
            if self.controller_data.state == State.HOT_WATER:
                return STATE_ON
        return STATE_OFF

    @property
    def current_temperature(self):
        """Return the current temperature."""
        if self.controller_data and self.controller_data.hotwater_temperature_current:
            return float(self.controller_data.hotwater_temperature_current.value)

    @property
    def target_temperature(self):
        """Return the target temperature."""
        if self.controller_data and self.controller_data.hotwater_temperature_requested:
            return float(self.controller_data.hotwater_temperature_requested.value)