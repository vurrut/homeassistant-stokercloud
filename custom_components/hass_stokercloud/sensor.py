"""Platform for sensor integration."""
from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.const import (
    CONF_USERNAME,
    UnitOfPower,
    UnitOfTemperature,
    UnitOfMass,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.config_entries import ConfigEntry

from stokercloud.controller_data import Unit, Value
from stokercloud.client import Client as StokerCloudClient

import datetime
from .const import DOMAIN
from .mixins import StokerCloudControllerMixin

import logging

logger = logging.getLogger(__name__)

MIN_TIME_BETWEEN_UPDATES = datetime.timedelta(minutes=1)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    client = hass.data[DOMAIN][entry.entry_id]
    serial = entry.data[CONF_USERNAME]
    
    async_add_entities([
        # Temperature Sensors (with explicit unit)
        StokerCloudControllerSensor(
            client, serial, 'Boiler Temperature', 'boiler_temperature_current', 
            SensorDeviceClass.TEMPERATURE, default_unit=UnitOfTemperature.CELSIUS
        ),
        StokerCloudControllerSensor(
            client, serial, 'Boiler Temperature Requested', 'boiler_temperature_requested', 
            SensorDeviceClass.TEMPERATURE, default_unit=UnitOfTemperature.CELSIUS
        ),
        StokerCloudControllerSensor(
            client, serial, 'Boiler Temp (Front)', 'boilertemp', 
            SensorDeviceClass.TEMPERATURE, default_unit=UnitOfTemperature.CELSIUS
        ),
        StokerCloudControllerSensor(
            client, serial, 'Wanted Boiler Temperature', 'wantedboilertemp', 
            SensorDeviceClass.TEMPERATURE, default_unit=UnitOfTemperature.CELSIUS
        ),
        StokerCloudControllerSensor(
            client, serial, 'DHW Temperature', 'dhw', 
            SensorDeviceClass.TEMPERATURE, default_unit=UnitOfTemperature.CELSIUS
        ),
        
        # Power Sensors (with explicit unit)
        StokerCloudControllerSensor(
            client, serial, 'Boiler Effect', 'boiler_kwh', 
            SensorDeviceClass.POWER, default_unit=UnitOfPower.KILO_WATT
        ),
        
        # Other Sensors
        StokerCloudControllerSensor(
            client, serial, 'Total Consumption', 'consumption_total', 
            state_class=SensorStateClass.TOTAL_INCREASING
        ),
        StokerCloudControllerSensor(client, serial, 'State', 'state'),
        StokerCloudControllerSensor(client, serial, 'Boiler Photo Sensor', 'boiler_photosensor'),
        StokerCloudControllerSensor(client, serial, 'Output Percentage', 'output_percentage'),
        StokerCloudControllerSensor(client, serial, 'Hopper Distance', 'hopper_distance'),
    ])


class StokerCloudControllerSensor(StokerCloudControllerMixin, SensorEntity):
    """Representation of a Sensor."""

    def __init__(
        self, 
        client: StokerCloudClient, 
        serial: str, 
        name: str, 
        client_key: str, 
        device_class: SensorDeviceClass = None, 
        state_class: SensorStateClass = None,
        default_unit: str = None
    ):
        """Initialize the sensor."""
        super().__init__(client, serial, name, client_key)
        self._attr_device_class = device_class
        self._attr_state_class = state_class
        self._default_unit = default_unit

    @property
    def native_value(self):
        """Return the value reported by the sensor."""
        if self._state:
            if isinstance(self._state, Value):
                return self._state.value
            return self._state
        return None

    @property
    def native_unit_of_measurement(self):
        """Return the unit of measurement."""
        # If state has a unit, use it
        if self._state and isinstance(self._state, Value) and self._state.unit:
            unit_map = {
                Unit.KWH: UnitOfPower.KILO_WATT,
                Unit.DEGREE: UnitOfTemperature.CELSIUS,
                Unit.KILO_GRAM: UnitOfMass.KILOGRAMS,
            }
            return unit_map.get(self._state.unit)
        
        # Otherwise use the default unit
        return self._default_unit