"""Platform for sensor integration."""
from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType


from stokercloud.controller_data import PowerState, Unit, Value
from stokercloud.client import Client as StokerCloudClient
from homeassistant.components.sensor import STATE_CLASS_MEASUREMENT
from homeassistant.components.sensor import STATE_CLASS_TOTAL


import datetime
from homeassistant.const import CONF_USERNAME, POWER_KILO_WATT, TEMP_CELSIUS, MASS_KILOGRAMS
from .const import DOMAIN
from .mixins import StokerCloudControllerMixin

import logging

logger = logging.getLogger(__name__)

MIN_TIME_BETWEEN_UPDATES = datetime.timedelta(minutes=1)

async def async_setup_entry(hass, config, async_add_entities):
    """Set up the sensor platform."""
    client = hass.data[DOMAIN][config.entry_id]
    serial = config.data[CONF_USERNAME]
    async_add_entities([
        StokerCloudControllerBinarySensor(client, serial, 'Running', 'running', 'power'),
        StokerCloudControllerBinarySensor(client, serial, 'Alarm', 'alarm', 'problem'),
        StokerCloudControllerSensor(client, serial, 'Boiler Temperature', 'boiler_temperature_current', SensorDeviceClass.TEMPERATURE),
        StokerCloudControllerSensor(client, serial, 'Boiler Temperature Requested', 'boiler_temperature_requested', SensorDeviceClass.TEMPERATURE),
        StokerCloudControllerSensor(client, serial, 'Boiler Effect', 'boiler_kwh', SensorDeviceClass.POWER),
        StokerCloudControllerSensor(client, serial, 'Total Consumption', 'consumption_total', state_class=SensorStateClass.TOTAL_INCREASING), # state class STATE_CLASS_TOTAL_INCREASING
        StokerCloudControllerSensor(client, serial, 'State', 'state'),
        StokerCloudControllerSensor(client, serial, 'boiler Photo sensor ', 'boiler_photosensor'),
        StokerCloudControllerSensor(client, serial, 'Output Percentage', 'output_percentage', state_class=STATE_CLASS_MEASUREMENT),
        StokerCloudControllerSensor(client, serial, 'Hopper Distance', 'hopper_distance', state_class=STATE_CLASS_TOTAL),
    ])


    @property
    def output_percentage(self):
        """Return the value reported by the sensor."""
        if self._state and isinstance(self._state, Value):
            return self._state.value

    @property
    def hopper_distance(self):
        """Return the value reported by the sensor."""
        if self._state and isinstance(self._state, Value):
            return self._state.value

    @property
    def state_class(self):
        """Return the state class of the sensor."""
        if self._attr_state_class:
            return self._attr_state_class
        # Add more conditions based on your requirements
        elif self._client_key == 'output_percentage':
            return STATE_CLASS_MEASUREMENT
        elif self._client_key == 'hopper_distance':
            return STATE_CLASS_TOTAL


class StokerCloudControllerBinarySensor(StokerCloudControllerMixin, BinarySensorEntity):
    """Representation of a Sensor."""

    def __init__(self, client: StokerCloudClient, serial, name: str, client_key: str, device_class):
        """Initialize the sensor."""
        super(StokerCloudControllerBinarySensor, self).__init__(client, serial, name, client_key)
        self._device_class = device_class

    @property
    def is_on(self):
        """If the switch is currently on or off."""
        return self._state is PowerState.ON

    @property
    def device_class(self):
        return self._device_class


class StokerCloudControllerSensor(StokerCloudControllerMixin, SensorEntity):
    """Representation of a Sensor."""

    def __init__(self, client: StokerCloudClient, serial, name: str, client_key: str, device_class=None, state_class=None):
        """Initialize the sensor."""
        super(StokerCloudControllerSensor, self).__init__(client, serial, name, client_key)
        self._device_class = device_class
        self._attr_state_class = state_class

    @property
    def device_class(self):
        return self._device_class

    @property
    def native_value(self):
        """Return the value reported by the sensor."""
        if self._state:
            if isinstance(self._state, Value):
                return self._state.value
            return self._state

    @property
    def native_unit_of_measurement(self):
        if self._state and isinstance(self._state, Value):
            return {
                Unit.KWH: POWER_KILO_WATT,
                Unit.DEGREE: TEMP_CELSIUS,
                Unit.KILO_GRAM: MASS_KILOGRAMS,
            }.get(self._state.unit)