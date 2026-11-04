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
    UnitOfEnergy,
    UnitOfMass,
    UnitOfPower,
    UnitOfPressure,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from stokercloud import STATE_LABELS, ControllerData, Value

from .const import CONF_CALORIFIC_VALUE, DEFAULT_CALORIFIC_VALUE
from .coordinator import StokerCloudConfigEntry, StokerCloudCoordinator
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


def _temp(
    key: str,
    attr: str,
    value_fn_override: Callable[[ControllerData], Any] | None = None,
    **kw: Any,
) -> StokerCloudSensorDescription:
    return StokerCloudSensorDescription(
        key=key,
        name=key,
        value_fn=value_fn_override or _v(attr),
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
    StokerCloudSensorDescription(
        key="Hopper Content",
        name="Hopper Content",
        value_fn=_v("hoppercontent"),
        device_class=SensorDeviceClass.WEIGHT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfMass.KILOGRAMS,
        icon="mdi:silo",
    ),
)

PELLET_ENERGY = SensorEntityDescription(
    key="Pellet Energy",
    name="Pellet Energy",
    device_class=SensorDeviceClass.ENERGY,
    state_class=SensorStateClass.TOTAL_INCREASING,
    native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
    suggested_display_precision=0,
    icon="mdi:fire",
)


def _zone_value(zone: int, field: str) -> Callable[[ControllerData], Any]:
    def get(cd: ControllerData) -> Any:
        item = (cd.raw.get("weathercomp") or {}).get(f"zone{zone}-{field}") or {}
        try:
            return float(item.get("val"))
        except (TypeError, ValueError):
            return None

    return get


def _zone_sensors(zone: int) -> tuple[StokerCloudSensorDescription, ...]:
    return (
        _temp(f"Zone {zone} Wanted Temperature", "", value_fn_override=_zone_value(zone, "wanted")),
        _temp(f"Zone {zone} Forward Temperature", "", value_fn_override=_zone_value(zone, "actual")),
        StokerCloudSensorDescription(
            key=f"Zone {zone} Valve",
            name=f"Zone {zone} Valve",
            value_fn=_zone_value(zone, "valve"),
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=PERCENTAGE,
            icon="mdi:valve",
        ),
    )


def _active_zones(cd: ControllerData) -> list[int]:
    wc = cd.raw.get("weathercomp") or {}
    return [z for z in range(1, 5) if str(wc.get(f"zone{z}active")) == "1"]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: StokerCloudConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    descriptions = list(SENSORS)
    for zone in _active_zones(coordinator.data.controller):
        descriptions.extend(_zone_sensors(zone))
    entities: list[SensorEntity] = [StokerCloudSensor(coordinator, d) for d in descriptions]
    entities.append(
        StokerCloudPelletEnergySensor(
            coordinator,
            PELLET_ENERGY,
            entry.options.get(CONF_CALORIFIC_VALUE, DEFAULT_CALORIFIC_VALUE),
        )
    )
    async_add_entities(entities)


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


class StokerCloudPelletEnergySensor(StokerCloudEntity, SensorEntity):
    """Fuel energy burned: total pellet consumption x calorific value.

    Add it to the Energy dashboard (as gas/fuel) and set a price per kWh there.
    """

    def __init__(
        self,
        coordinator: StokerCloudCoordinator,
        description: SensorEntityDescription,
        calorific_value: float,
    ) -> None:
        super().__init__(coordinator, description)
        self._calorific_value = calorific_value

    @property
    def native_value(self) -> float | None:
        kg = _v("consumption_total")(self.coordinator.data.controller)
        if not isinstance(kg, (int, float)) or kg < 0:
            return None
        return round(kg * self._calorific_value, 1)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"calorific_value_kwh_per_kg": self._calorific_value}
