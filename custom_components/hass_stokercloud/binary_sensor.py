"""Binary sensors for NBE StokerCloud."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from stokercloud import ControllerData, PowerState

from .coordinator import StokerCloudConfigEntry
from .entity import StokerCloudEntity


@dataclass(frozen=True, kw_only=True)
class StokerCloudBinaryDescription(BinarySensorEntityDescription):
    is_on_fn: Callable[[ControllerData], bool | None]
    always_available: bool = False


BINARY_SENSORS: tuple[StokerCloudBinaryDescription, ...] = (
    # Keys/names from v1/v2 (unique_id compatibility)
    StokerCloudBinaryDescription(
        key="Running",
        name="Running",
        device_class=BinarySensorDeviceClass.RUNNING,
        is_on_fn=lambda cd: cd.running is PowerState.ON,
    ),
    StokerCloudBinaryDescription(
        key="Alarm",
        name="Alarm",
        device_class=BinarySensorDeviceClass.PROBLEM,
        is_on_fn=lambda cd: cd.alarm is PowerState.ON,
    ),
    StokerCloudBinaryDescription(
        key="Circulate Pump",
        name="Circulate Pump",
        device_class=BinarySensorDeviceClass.RUNNING,
        is_on_fn=lambda cd: None if cd.output_pump is None else cd.output_pump is PowerState.ON,
    ),
    # New
    StokerCloudBinaryDescription(
        key="DHW Valve",
        name="DHW Valve",
        device_class=BinarySensorDeviceClass.OPENING,
        is_on_fn=lambda cd: None
        if cd.output_dhw_valve is None
        else cd.output_dhw_valve is PowerState.ON,
    ),
    StokerCloudBinaryDescription(
        key="Connected",
        name="Connected",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
        is_on_fn=lambda cd: not cd.notconnected,
        always_available=True,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: StokerCloudConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(StokerCloudBinarySensor(coordinator, d) for d in BINARY_SENSORS)


class StokerCloudBinarySensor(StokerCloudEntity, BinarySensorEntity):
    entity_description: StokerCloudBinaryDescription

    @property
    def available(self) -> bool:
        if self.entity_description.always_available:
            return self.coordinator.last_update_success
        return super().available

    @property
    def is_on(self) -> bool | None:
        return self.entity_description.is_on_fn(self.coordinator.data.controller)
