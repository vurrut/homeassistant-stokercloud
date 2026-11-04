"""Data coordinator for NBE StokerCloud: one API poll shared by all entities."""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from stokercloud import (
    Client,
    ControllerData,
    StokerCloudAuthError,
    StokerCloudError,
)

from .const import DOMAIN, MENU_REFRESH_EVERY, SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)

MENUS = ("boiler", "hot_water")


@dataclass
class StokerCloudData:
    """Snapshot handed to entities."""

    controller: ControllerData
    settings: dict[str, dict[str, Any]] = field(default_factory=dict)

    def setting(self, key: str) -> dict[str, Any] | None:
        """Return ``{"min","max","factor","val"}`` for a writable setting."""
        return self.settings.get(key)


type StokerCloudConfigEntry = ConfigEntry["StokerCloudCoordinator"]


class StokerCloudCoordinator(DataUpdateCoordinator[StokerCloudData]):
    """Polls controllerdata2.php and (less often) the settings menus."""

    config_entry: StokerCloudConfigEntry

    def __init__(self, hass: HomeAssistant, entry: StokerCloudConfigEntry, client: Client) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        self.client = client
        self._settings: dict[str, dict[str, Any]] = {}
        self._polls = 0
        self._cancel_delayed_refresh: Callable[[], None] | None = None

    async def _async_update_data(self) -> StokerCloudData:
        try:
            controller = await self.client.async_get_controller_data()
            if not self._settings or self._polls % MENU_REFRESH_EVERY == 0:
                settings: dict[str, dict[str, Any]] = {}
                for menu in MENUS:
                    settings.update(await self.client.async_get_menu(menu))
                self._settings = settings
        except StokerCloudAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except StokerCloudError as err:
            raise UpdateFailed(str(err)) from err
        self._polls += 1
        return StokerCloudData(controller=controller, settings=self._settings)

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

        # Force settings to be re-read on the next poll.
        self._polls = 0
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
            self.hass.async_create_task(self.async_request_refresh())

        self._cancel_delayed_refresh = async_call_later(self.hass, delay, _refresh)

    async def async_shutdown(self) -> None:
        if self._cancel_delayed_refresh:
            self._cancel_delayed_refresh()
            self._cancel_delayed_refresh = None
        await super().async_shutdown()
