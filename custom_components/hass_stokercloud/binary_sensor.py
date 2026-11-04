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

from typing import Any

from stokercloud import ControllerData, PowerState, Unit, Value

from .const import CONF_LOW_HOPPER_KG, DEFAULT_LOW_HOPPER_KG
from .coordinator import StokerCloudConfigEntry, StokerCloudCoordinator
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
    entities: list[BinarySensorEntity] = [
        StokerCloudBinarySensor(coordinator, d) for d in BINARY_SENSORS
    ]
    entities.append(
        StokerCloudHopperLowSensor(
            coordinator,
            HOPPER_LOW,
            entry.options.get(CONF_LOW_HOPPER_KG, DEFAULT_LOW_HOPPER_KG),
        )
    )
    async_add_entities(entities)


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


HOPPER_LOW = BinarySensorEntityDescription(
    key="Hopper Low",
    name="Hopper Low",
    device_class=BinarySensorDeviceClass.PROBLEM,
    icon="mdi:silo-outline",
)


def _float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


class StokerCloudHopperLowSensor(StokerCloudEntity, BinarySensorEntity):
    """On when the hopper is nearly empty.

    Uses the tracked hopper content (kg) when it is set (>= 0); otherwise the
    hopper distance sensor in % against the controller's own warning level
    (``hopper.distwarn``). Unknown when neither is available.
    """

    def __init__(
        self,
        coordinator: StokerCloudCoordinator,
        description: BinarySensorEntityDescription,
        threshold_kg: float,
    ) -> None:
        super().__init__(coordinator, description)
        self._threshold_kg = threshold_kg

    def _threshold(self) -> float:
        controller_min = _float((self.coordinator.data.setting("hopper.min_content") or {}).get("val"))
        return max(self._threshold_kg, controller_min or 0)

    @property
    def is_on(self) -> bool | None:
        data = self.coordinator.data
        content = data.controller.hoppercontent
        if isinstance(content, Value) and isinstance(content.value, (int, float)) and content.value >= 0:
            return content.value <= self._threshold()
        sensor_on = str((data.setting("hopper.distance_sensor") or {}).get("val", "0")) not in ("0", "")
        level = data.controller.hopper_level
        warn = _float((data.setting("hopper.distwarn") or {}).get("val"))
        if sensor_on and isinstance(level, Value) and level.unit is Unit.PERCENT and warn is not None:
            return float(level.value) <= warn
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"threshold_kg": self._threshold()}
