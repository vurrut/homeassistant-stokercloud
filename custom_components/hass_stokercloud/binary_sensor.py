"""Binary sensor platform for NBE Stoker Cloud."""
from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.const import CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.config_entries import ConfigEntry

from stokercloud.client import Client as StokerCloudClient
from stokercloud.controller_data import PowerState

from .const import DOMAIN
from .mixins import StokerCloudControllerMixin

import logging

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the binary sensor platform."""
    client = hass.data[DOMAIN][entry.entry_id]
    serial = entry.data[CONF_USERNAME]
    
    async_add_entities([
        StokerCloudControllerBinarySensor(
            client, serial, 'Running', 'running', BinarySensorDeviceClass.RUNNING
        ),
        StokerCloudControllerBinarySensor(
            client, serial, 'Alarm', 'alarm', BinarySensorDeviceClass.PROBLEM
        ),
        StokerCloudControllerBinarySensor(
            client, serial, 'Circulate Pump', 'output_pump', BinarySensorDeviceClass.RUNNING
        ),
    ])


class StokerCloudControllerBinarySensor(StokerCloudControllerMixin, BinarySensorEntity):
    """Representation of a Binary Sensor."""

    def __init__(
        self, 
        client: StokerCloudClient, 
        serial: str, 
        name: str, 
        client_key: str, 
        device_class: BinarySensorDeviceClass
    ):
        """Initialize the sensor."""
        super().__init__(client, serial, name, client_key)
        self._attr_device_class = device_class

    @property
    def is_on(self) -> bool:
        """If the switch is currently on or off."""
        return self._state is PowerState.ON