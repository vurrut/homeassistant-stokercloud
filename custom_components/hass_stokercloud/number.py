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
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfMass, UnitOfTemperature
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


@dataclass(frozen=True, kw_only=True)
class StokerCloudSettingDescription(NumberEntityDescription):
    """A controller setting read from (and written to) the settings menus."""

    setting: str


def _adv(key: str, setting: str, unit: str | None, icon: str) -> StokerCloudSettingDescription:
    return StokerCloudSettingDescription(
        key=key,
        name=key,
        setting=setting,
        native_unit_of_measurement=unit,
        device_class=NumberDeviceClass.TEMPERATURE if unit == UnitOfTemperature.CELSIUS else None,
        mode=NumberMode.BOX,
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        icon=icon,
    )


ADVANCED: tuple[StokerCloudSettingDescription, ...] = (
    _adv("Boiler Start Difference", "boiler.diff_under", UnitOfTemperature.CELSIUS, "mdi:thermometer-chevron-down"),
    _adv("Boiler Stop Difference", "boiler.diff_over", UnitOfTemperature.CELSIUS, "mdi:thermometer-chevron-up"),
    _adv("Minimum Return Temperature", "boiler.min_return", UnitOfTemperature.CELSIUS, "mdi:thermometer-low"),
    _adv("Boiler Temperature Reduction", "boiler.reduction", UnitOfTemperature.CELSIUS, "mdi:thermometer-minus"),
    _adv("DHW Start Difference", "hot_water.diff_under", UnitOfTemperature.CELSIUS, "mdi:water-thermometer"),
    _adv("Boiler Minimum Power", "regulation.boiler_power_min", PERCENTAGE, "mdi:fire"),
    _adv("Boiler Maximum Power", "regulation.boiler_power_max", PERCENTAGE, "mdi:fire"),
    _adv("DHW Minimum Power", "regulation.dhw_power_min", PERCENTAGE, "mdi:fire"),
    _adv("DHW Maximum Power", "regulation.dhw_power_max", PERCENTAGE, "mdi:fire"),
    _adv("O2 Target Low Power", "oxygen.o2_low", PERCENTAGE, "mdi:molecule"),
    _adv("O2 Target Medium Power", "oxygen.o2_medium", PERCENTAGE, "mdi:molecule"),
    _adv("O2 Target High Power", "oxygen.o2_high", PERCENTAGE, "mdi:molecule"),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: StokerCloudConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    entities: list[NumberEntity] = [StokerCloudNumber(coordinator, d) for d in NUMBERS]
    entities.extend(
        StokerCloudSettingNumber(coordinator, d)
        for d in ADVANCED
        if coordinator.data.setting(d.setting) is not None
    )
    async_add_entities(entities)


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


class StokerCloudSettingNumber(StokerCloudEntity, NumberEntity):
    """Advanced controller setting; disabled by default."""

    entity_description: StokerCloudSettingDescription
    _pending: float | None = None
    _pending_until = 0.0

    def _setting(self) -> dict[str, Any]:
        return self.coordinator.data.setting(self.entity_description.setting) or {}

    @property
    def available(self) -> bool:
        return super().available and bool(self._setting())

    @property
    def native_min_value(self) -> float:
        return _num(self._setting().get("min")) or 0

    @property
    def native_max_value(self) -> float:
        return _num(self._setting().get("max")) or 100

    @property
    def native_step(self) -> float:
        factor = _num(self._setting().get("factor")) or 1
        return 1 / factor if factor > 1 else 1

    @property
    def native_value(self) -> float | None:
        if self._pending is not None:
            return self._pending
        return _num(self._setting().get("val"))

    @callback
    def _handle_coordinator_update(self) -> None:
        if self._pending is not None:
            if _num(self._setting().get("val")) == self._pending or time.monotonic() > self._pending_until:
                self._pending = None
        super()._handle_coordinator_update()

    async def async_set_native_value(self, value: float) -> None:
        step = self.native_step
        value = round(round(value / step) * step, 2)
        await self.coordinator.async_write(
            lambda: self.coordinator.client.async_set_value(self.entity_description.setting, value),
            f"Setting {self.entity_description.setting} to {value:g}",
        )
        self._pending = value
        self._pending_until = time.monotonic() + OPTIMISTIC_SECONDS
        self.async_write_ha_state()
