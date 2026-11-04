"""Sensors for NBE StokerCloud."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfMass,
    UnitOfPower,
    UnitOfPressure,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from stokercloud import STATE_LABELS, ControllerData, Value

from .coordinator import StokerCloudConfigEntry
from .entity import StokerCloudEntity


def _v(attr: str) -> Callable[[ControllerData], Any]:
    def get(cd: ControllerData) -> Any:
        val = getattr(cd, attr, None)
        return val.value if isinstance(val, Value) else val

    return get


@dataclass(frozen=True, kw_only=True)
class StokerCloudSensorDescription(SensorEntityDescription):
    value_fn: Callable[[ControllerData], Any]
    attrs_fn: Callable[[ControllerData], dict[str, Any]] | None = None


def _temp(key: str, attr: str, **kw: Any) -> StokerCloudSensorDescription:
    return StokerCloudSensorDescription(
        key=key,
        name=key,
        value_fn=_v(attr),
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        **kw,
    )


STATE_OPTIONS = sorted(set(STATE_LABELS.values()))

SENSORS: tuple[StokerCloudSensorDescription, ...] = (
    # --- keys/names below exist since v1/v2: do not rename (unique_id) ---
    _temp("Boiler Temperature", "boilertemp"),
    _temp("Boiler Temperature Requested", "wantedboilertemp"),
    _temp("DHW Temperature", "dhw"),
    StokerCloudSensorDescription(
        key="Boiler Effect",
        name="Boiler Effect",
        value_fn=_v("boiler_kwh"),
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
    ),
    StokerCloudSensorDescription(
        key="Total Consumption",
        name="Total Consumption",
        value_fn=_v("consumption_total"),
        device_class=SensorDeviceClass.WEIGHT,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfMass.KILOGRAMS,
        icon="mdi:grain",
    ),
    StokerCloudSensorDescription(
        key="State",
        name="State",
        value_fn=lambda cd: cd.state_label if cd.state_label in STATE_OPTIONS else None,
        attrs_fn=lambda cd: {"code": cd.state_raw, "substate": cd.substate_raw},
        device_class=SensorDeviceClass.ENUM,
        options=STATE_OPTIONS,
        icon="mdi:fire",
    ),
    StokerCloudSensorDescription(
        key="Boiler Photo Sensor",
        name="Boiler Photo Sensor",
        value_fn=_v("boiler_photosensor"),
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:brightness-6",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    StokerCloudSensorDescription(
        key="Output Percentage",
        name="Output Percentage",
        value_fn=_v("output_percentage"),
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:gauge",
    ),
    StokerCloudSensorDescription(
        key="Hopper Distance",
        name="Hopper Distance",
        value_fn=_v("hopper_distance"),
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:arrow-expand-vertical",
    ),
    # --- new in v3 ---
    _temp("DHW Temperature Requested", "dhwwanted"),
    _temp("Smoke Temperature", "smoketemp"),
    _temp("Outdoor Temperature", "outdoor_temperature"),
    StokerCloudSensorDescription(
        key="Oxygen",
        name="Oxygen",
        value_fn=_v("oxygen"),
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:molecule",
    ),
    StokerCloudSensorDescription(
        key="Boiler Power",
        name="Boiler Power",
        value_fn=_v("boiler_power_pct"),
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:fire-circle",
    ),
    StokerCloudSensorDescription(
        key="Consumption 24h",
        name="Consumption 24h",
        value_fn=_v("consumption_day"),
        device_class=SensorDeviceClass.WEIGHT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfMass.KILOGRAMS,
        icon="mdi:grain",
    ),
    StokerCloudSensorDescription(
        key="Chamber Pressure",
        name="Chamber Pressure",
        value_fn=_v("pressure"),
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPressure.PA,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: StokerCloudConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(StokerCloudSensor(coordinator, desc) for desc in SENSORS)


class StokerCloudSensor(StokerCloudEntity, SensorEntity):
    entity_description: StokerCloudSensorDescription

    @property
    def native_value(self) -> Any:
        value = self.entity_description.value_fn(self.coordinator.data.controller)
        if self.entity_description.device_class == SensorDeviceClass.ENUM:
            return value
        return value if isinstance(value, (int, float)) else None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        if self.entity_description.attrs_fn is None:
            return None
        return self.entity_description.attrs_fn(self.coordinator.data.controller)
