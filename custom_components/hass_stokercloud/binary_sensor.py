"""Binary sensor platform for Stokercloud integration."""
from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Stokercloud binary sensors."""
    coordinator: StokerCloudDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    
    binary_sensors = []
    
    # Create binary sensors from coordinator data
    if coordinator.data and "binary_sensors" in coordinator.data:
        for sensor_id, sensor_data in coordinator.data["binary_sensors"].items():
            binary_sensors.append(
                StokerCloudBinarySensor(coordinator, entry, sensor_id, sensor_data)
            )
    
    async_add_entities(binary_sensors)


class StokerCloudBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Representation of a Stokercloud binary sensor."""

    def __init__(
        self,
        coordinator: StokerCloudDataUpdateCoordinator,
        entry: ConfigEntry,
        sensor_id: str,
        sensor_data: dict,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator)
        
        self._sensor_id = sensor_id
        self._attr_unique_id = f"{entry.entry_id}_{sensor_id}"
        self._attr_name = sensor_data.get("name", sensor_id)
        self._attr_device_class = sensor_data.get("device_class")
        self._attr_icon = sensor_data.get("icon")
        
        # Convert category string to EntityCategory enum
        category = sensor_data.get("category")
        if category == "diagnostic":
            self._attr_entity_category = EntityCategory.DIAGNOSTIC
        elif category == "config":
            self._attr_entity_category = EntityCategory.CONFIG
        else:
            self._attr_entity_category = None
        
        # Device info
        device_info = coordinator.data.get("device_info", {})
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": f"Stokercloud {device_info.get('alias', entry.data.get('username'))}",
            "manufacturer": "Stokercloud",
            "model": device_info.get("model", "Unknown"),
            "sw_version": device_info.get("serial", ""),
        }

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        if self.coordinator.data and "binary_sensors" in self.coordinator.data:
            sensor_data = self.coordinator.data["binary_sensors"].get(self._sensor_id, {})
            return sensor_data.get("value")
        return None