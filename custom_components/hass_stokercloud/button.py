"""Reset-alarm button for NBE StokerCloud."""
from __future__ import annotations

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import StokerCloudConfigEntry
from .entity import StokerCloudEntity

RESET_ALARM = ButtonEntityDescription(
    key="Reset Alarm",
    name="Reset Alarm",
    icon="mdi:alarm-light-off",
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: StokerCloudConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    async_add_entities([StokerCloudResetAlarmButton(entry.runtime_data, RESET_ALARM)])


class StokerCloudResetAlarmButton(StokerCloudEntity, ButtonEntity):
    async def async_press(self) -> None:
        await self.coordinator.async_write(
            self.coordinator.client.async_reset_alarm, "Resetting alarm"
        )
