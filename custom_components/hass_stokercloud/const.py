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

CONF_SCAN_INTERVAL = "scan_interval"
CONF_CALORIFIC_VALUE = "calorific_value"

DEFAULT_SCAN_INTERVAL = 60  # seconds
MIN_SCAN_INTERVAL = 30
# Typical net calorific value of EN-plus wood pellets (kWh per kg)
DEFAULT_CALORIFIC_VALUE = 4.8

SCAN_INTERVAL = timedelta(seconds=DEFAULT_SCAN_INTERVAL)
# Settings limits change rarely; refresh them every N data updates.
MENU_REFRESH_EVERY = 30

MANUFACTURER = "NBE"
DEVICE_NAME = "NBE"
