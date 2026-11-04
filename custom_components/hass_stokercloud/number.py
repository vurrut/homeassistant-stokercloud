"""Writable setpoints for NBE StokerCloud."""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
import time
from typing import Any

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.const import EntityCategory, UnitOfMass, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from stokercloud import Client, ControllerData, Value

from .coordinator import StokerCloudConfigEntry, StokerCloudCoordinator
from .entity import StokerCloudEntity

# Keep showing the value the user just set until the cloud reports it
# (the boiler syncs with the cloud every few seconds) or this many seconds pass.
OPTIMISTIC_SECONDS = 120


@dataclass(frozen=True, kw_only=True)
class StokerCloudNumberDescription(NumberEntityDescription):
    setting: str  # field id in getmenudata.php / updatevalue.php
    value_fn: Callable[[ControllerData], Any]
    set_fn: Callable[[Client, float], Awaitable[dict]]


NUMBERS: tuple[StokerCloudNumberDescription, ...] = (
    StokerCloudNumberDescription(
        key="Wanted Boiler Temperature",  # v2 name, keeps unique_id
        name="Wanted Boiler Temperature",
        setting="boiler.temp",
        value_fn=lambda cd: cd.wantedboilertemp,
        set_fn=lambda client, v: client.async_set_boiler_temp(v),
        device_class=NumberDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        native_min_value=30,
        native_max_value=85,
        native_step=1,
        mode=NumberMode.BOX,
        icon="mdi:thermometer-water",
    ),
    StokerCloudNumberDescription(
        key="Wanted DHW Temperature",
        name="Wanted DHW Temperature",
        setting="hot_water.temp",
        value_fn=lambda cd: cd.dhwwanted,
        set_fn=lambda client, v: client.async_set_dhw_temp(v),
        device_class=NumberDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        native_min_value=10,
        native_max_value=70,
        native_step=1,
        mode=NumberMode.BOX,
        icon="mdi:water-boiler",
    ),
    StokerCloudNumberDescription(
        key="Hopper Content Setting",
        name="Hopper Content",
        setting="hopper.content",
        value_fn=lambda cd: cd.hoppercontent,
        set_fn=lambda client, v: client.async_set_value("hopper.content", int(v)),
        device_class=NumberDeviceClass.WEIGHT,
        native_unit_of_measurement=UnitOfMass.KILOGRAMS,
        native_min_value=-30000,
        native_max_value=30000,
        native_step=1,
        mode=NumberMode.BOX,
        entity_category=EntityCategory.CONFIG,
        icon="mdi:silo",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: StokerCloudConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(StokerCloudNumber(coordinator, d) for d in NUMBERS)


def _num(value: Any) -> float | None:
    if isinstance(value, Value):
        value = value.value
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


class StokerCloudNumber(StokerCloudEntity, NumberEntity):
    entity_description: StokerCloudNumberDescription

    def __init__(
        self, coordinator: StokerCloudCoordinator, description: StokerCloudNumberDescription
    ) -> None:
        super().__init__(coordinator, description)
        self._pending: float | None = None
        self._pending_until = 0.0

    def _setting(self) -> dict[str, Any] | None:
        return self.coordinator.data.setting(self.entity_description.setting)

    @property
    def native_min_value(self) -> float:
        setting = self._setting()
        api_min = _num(setting.get("min")) if setting else None
        default = self.entity_description.native_min_value
        # The API often reports min 0; keep a sane lower bound for a boiler.
        return max(api_min, default) if api_min is not None else default

    @property
    def native_max_value(self) -> float:
        setting = self._setting()
        api_max = _num(setting.get("max")) if setting else None
        return api_max if api_max else self.entity_description.native_max_value

    @property
    def native_value(self) -> float | None:
        if self._pending is not None:
            return self._pending
        value = _num(self.entity_description.value_fn(self.coordinator.data.controller))
        if value is None and (setting := self._setting()):
            value = _num(setting.get("val"))
        return value

    @callback
    def _handle_coordinator_update(self) -> None:
        if self._pending is not None:
            reported = _num(self.entity_description.value_fn(self.coordinator.data.controller))
            if reported == self._pending or time.monotonic() > self._pending_until:
                self._pending = None
        super()._handle_coordinator_update()

    async def async_set_native_value(self, value: float) -> None:
        value = float(round(value))
        await self.coordinator.async_write(
            lambda: self.entity_description.set_fn(self.coordinator.client, value),
            f"Setting {self.entity_description.setting} to {value:g}",
        )
        self._pending = value
        self._pending_until = time.monotonic() + OPTIMISTIC_SECONDS
        self.async_write_ha_state()
