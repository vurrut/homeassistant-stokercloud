"""Domestic hot water (DHW) as a water heater entity."""
from __future__ import annotations

import time
from typing import Any

from homeassistant.components.water_heater import (
    WaterHeaterEntity,
    WaterHeaterEntityDescription,
    WaterHeaterEntityFeature,
)
from homeassistant.const import ATTR_TEMPERATURE, STATE_OFF, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from stokercloud import PowerState, State, Value

from .coordinator import StokerCloudConfigEntry
from .entity import StokerCloudEntity

OPTIMISTIC_SECONDS = 120
# Shown while the boiler is heating hot water; otherwise "off"
OPERATION_HEATING = "heating"

HOT_WATER = WaterHeaterEntityDescription(key="Hot Water", name="Hot Water")


async def async_setup_entry(
    hass: HomeAssistant,
    entry: StokerCloudConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    async_add_entities([StokerCloudWaterHeater(entry.runtime_data, HOT_WATER)])


def _num(value: Any) -> float | None:
    if isinstance(value, Value):
        value = value.value
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


class StokerCloudWaterHeater(StokerCloudEntity, WaterHeaterEntity):
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_supported_features = WaterHeaterEntityFeature.TARGET_TEMPERATURE
    _attr_target_temperature_step = 1
    _attr_operation_list = [OPERATION_HEATING, STATE_OFF]
    _attr_icon = "mdi:water-boiler"
    _pending: float | None = None
    _pending_until = 0.0

    @property
    def current_temperature(self) -> float | None:
        return _num(self.coordinator.data.controller.dhw)

    @property
    def target_temperature(self) -> float | None:
        if self._pending is not None:
            return self._pending
        return _num(self.coordinator.data.controller.dhwwanted)

    @property
    def min_temp(self) -> float:
        setting = self.coordinator.data.setting("hot_water.temp") or {}
        return max(_num(setting.get("min")) or 0, 10)

    @property
    def max_temp(self) -> float:
        setting = self.coordinator.data.setting("hot_water.temp") or {}
        return _num(setting.get("max")) or 70

    @property
    def current_operation(self) -> str:
        cd = self.coordinator.data.controller
        if cd.state is State.HOT_WATER or cd.output_dhw_valve is PowerState.ON:
            return OPERATION_HEATING
        return STATE_OFF

    @callback
    def _handle_coordinator_update(self) -> None:
        if self._pending is not None:
            reported = _num(self.coordinator.data.controller.dhwwanted)
            if reported == self._pending or time.monotonic() > self._pending_until:
                self._pending = None
        super()._handle_coordinator_update()

    async def async_set_temperature(self, **kwargs: Any) -> None:
        if (temperature := kwargs.get(ATTR_TEMPERATURE)) is None:
            return
        value = float(round(temperature))
        await self.coordinator.async_write(
            lambda: self.coordinator.client.async_set_dhw_temp(value),
            f"Setting hot water temperature to {value:g}",
        )
        self._pending = value
        self._pending_until = time.monotonic() + OPTIMISTIC_SECONDS
        self.async_write_ha_state()
