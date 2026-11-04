"""Data coordinator for NBE StokerCloud: one API poll shared by all entities.

Polling strategy
----------------
The controller pushes new data to the cloud roughly once a minute. With
"fast updates" enabled (default) we poll the tiny ``getstatus.php`` every
``FAST_INTERVAL`` seconds and fetch the full data only when its timestamp
changes, so changes show up within seconds without extra load. The full data
is fetched at least every ``scan_interval`` seconds either way.

Settings (min/max/current value of writable fields) and consumption history
change slowly and are refreshed every few minutes, or right after a write.
"""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import logging
import time
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from stokercloud import (
    STATE_LABELS,
    Client,
    ControllerData,
    PowerState,
    StokerCloudAuthError,
    StokerCloudError,
)

from .const import (
    CONF_FAST_UPDATES,
    CONF_SCAN_INTERVAL,
    DEFAULT_FAST_UPDATES,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    EVENT_STOKERCLOUD,
    FAST_INTERVAL,
    HISTORY_REFRESH_SECONDS,
    SETTINGS_REFRESH_SECONDS,
)

_LOGGER = logging.getLogger(__name__)

MENUS = ("boiler", "hot_water", "hopper", "regulation", "oxygen")

EVENT_STATE_CHANGED = "state_changed"
EVENT_ALARM = "alarm"
EVENT_ALARM_CLEARED = "alarm_cleared"
EVENT_TYPES = [EVENT_STATE_CHANGED, EVENT_ALARM, EVENT_ALARM_CLEARED]


@dataclass
class ConsumptionHistory:
    """Pellet consumption (kg) from ``getconsumption.php``."""

    hourly: list[tuple[datetime, float]] = field(default_factory=list)  # newest first
    daily: list[tuple[datetime, float]] = field(default_factory=list)
    this_month: float | None = None
    last_month: float | None = None
    this_year: float | None = None
    last_year: float | None = None
    month_start: datetime | None = None
    year_start: datetime | None = None

    @property
    def avg_daily_7d(self) -> float | None:
        """Average of the last seven rolling 24 h windows (newest first)."""
        days = [kg for _, kg in self.daily[:7]]
        return sum(days) / len(days) if len(days) == 7 else None


@dataclass
class StokerCloudData:
    """Snapshot handed to entities."""

    controller: ControllerData
    settings: dict[str, dict[str, Any]] = field(default_factory=dict)
    history: ConsumptionHistory = field(default_factory=ConsumptionHistory)
    events: list[tuple[str, dict[str, Any]]] = field(default_factory=list)

    def setting(self, key: str) -> dict[str, Any] | None:
        """Return ``{"min","max","factor","val"}`` for a writable setting."""
        return self.settings.get(key)


type StokerCloudConfigEntry = ConfigEntry["StokerCloudCoordinator"]


def _detect_events(old: ControllerData | None, new: ControllerData) -> list[tuple[str, dict[str, Any]]]:
    if old is None:
        return []
    events: list[tuple[str, dict[str, Any]]] = []
    if old.state is not new.state:
        events.append(
            (
                EVENT_STATE_CHANGED,
                {
                    "from_state": STATE_LABELS.get(old.state, str(old.state_raw)),
                    "to_state": STATE_LABELS.get(new.state, str(new.state_raw)),
                    "code": new.state_raw,
                },
            )
        )
    if old.alarm is not new.alarm:
        events.append(
            (
                EVENT_ALARM if new.alarm is PowerState.ON else EVENT_ALARM_CLEARED,
                {"state": STATE_LABELS.get(new.state, str(new.state_raw)), "code": new.state_raw},
            )
        )
    return events


class StokerCloudCoordinator(DataUpdateCoordinator[StokerCloudData]):
    """Polls StokerCloud and hands one snapshot to all entities."""

    config_entry: StokerCloudConfigEntry

    def __init__(self, hass: HomeAssistant, entry: StokerCloudConfigEntry, client: Client) -> None:
        self.scan_interval = int(entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL))
        self.fast_updates = bool(entry.options.get(CONF_FAST_UPDATES, DEFAULT_FAST_UPDATES))
        interval = min(FAST_INTERVAL, self.scan_interval) if self.fast_updates else self.scan_interval
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=interval),
            always_update=False,
        )
        self.client = client
        self._settings: dict[str, dict[str, Any]] = {}
        self._history = ConsumptionHistory()
        self._settings_at = 0.0
        self._history_at = 0.0
        self._full_at = 0.0
        self._status: str | None = None
        self._force_full = True
        self._cancel_delayed_refresh: Callable[[], None] | None = None
        # Called with the fresh history (statistics import); set by __init__.py
        self.history_listeners: list[Callable[[ConsumptionHistory], Awaitable[None]]] = []

    # ------------------------------------------------------------------ poll
    async def _async_update_data(self) -> StokerCloudData:
        now = time.monotonic()
        try:
            if self.data is not None and not self._force_full and self.fast_updates:
                status = await self.client.async_get_status()
                if status == self._status and now - self._full_at < self.scan_interval:
                    return self.data  # nothing new; always_update=False -> no state writes
                self._status = status
            elif self.fast_updates:
                self._status = await self.client.async_get_status()

            controller = await self.client.async_get_controller_data()
            self._full_at = now
            self._force_full = False

            if not self._settings or now - self._settings_at > SETTINGS_REFRESH_SECONDS:
                settings: dict[str, dict[str, Any]] = {}
                for menu in MENUS:
                    settings.update(await self.client.async_get_menu(menu))
                self._settings = settings
                self._settings_at = now

            if now - self._history_at > HISTORY_REFRESH_SECONDS or not self._history_at:
                await self._async_update_history()
                self._history_at = now
        except StokerCloudAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except StokerCloudError as err:
            raise UpdateFailed(str(err)) from err

        events = _detect_events(self.data.controller if self.data else None, controller)
        for event_type, data in events:
            self.hass.bus.async_fire(
                EVENT_STOKERCLOUD,
                {"type": event_type, "config_entry_id": self.config_entry.entry_id, **data},
            )
        return StokerCloudData(
            controller=controller, settings=self._settings, history=self._history, events=events
        )

    async def _async_update_history(self) -> None:
        """Refresh consumption history. Failures here never fail the poll."""
        try:
            hourly = await self.client.async_get_consumption("hours")
            daily = await self.client.async_get_consumption("days")
            months = await self.client.async_get_consumption("months")
            years = await self.client.async_get_consumption("years")
        except StokerCloudAuthError:
            raise
        except StokerCloudError as err:
            _LOGGER.debug("Consumption history unavailable: %s", err)
            return
        history = ConsumptionHistory(hourly=hourly, daily=daily)
        if months:
            history.month_start, history.this_month = months[0]
            history.last_month = months[1][1] if len(months) > 1 else None
        if years:
            history.year_start, history.this_year = years[0]
            history.last_year = years[1][1] if len(years) > 1 else None
        self._history = history
        for listener in self.history_listeners:
            try:
                await listener(history)
            except Exception:  # noqa: BLE001 - statistics import must not break polling
                _LOGGER.exception("Error handling consumption history")

    # ------------------------------------------------------------------ write
    async def async_write(
        self, action: Callable[[], Awaitable[dict]], description: str
    ) -> dict:
        """Run a write, translate errors, and refresh once the cloud has synced."""
        try:
            response = await action()
        except StokerCloudAuthError as err:
            self.config_entry.async_start_reauth(self.hass)
            raise HomeAssistantError(f"{description}: authentication failed ({err})") from err
        except StokerCloudError as err:
            raise HomeAssistantError(f"{description}: {err}") from err

        # Re-read settings and full data on the next poll.
        self._settings_at = 0.0
        self._force_full = True
        # The cloud tells us when the boiler will have synced the new value.
        delay = 5
        try:
            delay = min(max(int(response.get("secs_to_next_update", 5)) + 3, 3), 60)
        except (TypeError, ValueError):
            pass
        self._schedule_refresh_in(delay)
        return response

    @callback
    def _schedule_refresh_in(self, delay: float) -> None:
        if self._cancel_delayed_refresh:
            self._cancel_delayed_refresh()

        @callback
        def _refresh(_now: Any) -> None:
            self._cancel_delayed_refresh = None
            self._force_full = True
            self.hass.async_create_task(self.async_request_refresh())

        self._cancel_delayed_refresh = async_call_later(self.hass, delay, _refresh)

    async def async_shutdown(self) -> None:
        if self._cancel_delayed_refresh:
            self._cancel_delayed_refresh()
            self._cancel_delayed_refresh = None
        await super().async_shutdown()
