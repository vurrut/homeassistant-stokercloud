"""Constants for the NBE StokerCloud integration."""
from __future__ import annotations

from datetime import timedelta

from homeassistant.const import Platform

DOMAIN = "hass_stokercloud"

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.NUMBER,
    Platform.SWITCH,
    Platform.BUTTON,
]

SCAN_INTERVAL = timedelta(seconds=60)
# Settings limits change rarely; refresh them every N data updates.
MENU_REFRESH_EVERY = 30

MANUFACTURER = "NBE"
DEVICE_NAME = "NBE"
