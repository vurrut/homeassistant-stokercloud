"""Boiler events (state changes and alarms) as an event entity.

StokerCloud's own event log endpoint (geteventdata.php) currently times out,
so events are derived from consecutive data snapshots. The same events are
also fired on the bus as ``hass_stokercloud_event``.
"""
from __future__ import annotations

from homeassistant.components.event import EventEntity, EventEntityDescription
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import EVENT_TYPES, StokerCloudConfigEntry
from .entity import StokerCloudEntity

BOILER_EVENT = EventEntityDescription(
    key="Boiler Event",
    name="Boiler Event",
    event_types=EVENT_TYPES,
    icon="mdi:bell-ring",
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: StokerCloudConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    async_add_entities([StokerCloudEventEntity(entry.runtime_data, BOILER_EVENT)])


class StokerCloudEventEntity(StokerCloudEntity, EventEntity):
    @callback
    def _handle_coordinator_update(self) -> None:
        for event_type, data in self.coordinator.data.events:
            self._trigger_event(event_type, data)
        super()._handle_coordinator_update()
