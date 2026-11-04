"""Burner on/off switch for NBE StokerCloud (same as the web app's on/off button)."""
from __future__ import annotations

import time
from typing import Any

from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity, SwitchEntityDescription
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from stokercloud import PowerState

from .coordinator import StokerCloudConfigEntry
from .entity import StokerCloudEntity

OPTIMISTIC_SECONDS = 120

BURNER = SwitchEntityDescription(
    key="Burner",
    name="Burner",
    device_class=SwitchDeviceClass.SWITCH,
    icon="mdi:fire",
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: StokerCloudConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    async_add_entities([StokerCloudBurnerSwitch(entry.runtime_data, BURNER)])


class StokerCloudBurnerSwitch(StokerCloudEntity, SwitchEntity):
    _pending: bool | None = None
    _pending_until = 0.0

    @property
    def is_on(self) -> bool:
        if self._pending is not None:
            return self._pending
        return self.coordinator.data.controller.running is PowerState.ON

    @callback
    def _handle_coordinator_update(self) -> None:
        if self._pending is not None:
            reported = self.coordinator.data.controller.running is PowerState.ON
            if reported == self._pending or time.monotonic() > self._pending_until:
                self._pending = None
        super()._handle_coordinator_update()

    async def _set(self, on: bool) -> None:
        client = self.coordinator.client
        await self.coordinator.async_write(
            client.async_turn_on if on else client.async_turn_off,
            "Turning burner " + ("on" if on else "off"),
        )
        self._pending = on
        self._pending_until = time.monotonic() + OPTIMISTIC_SECONDS
        self.async_write_ha_state()

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._set(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._set(False)
