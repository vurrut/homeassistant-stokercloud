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
    Platform.WATER_HEATER,
    Platform.EVENT,
]

CONF_SCAN_INTERVAL = "scan_interval"
CONF_CALORIFIC_VALUE = "calorific_value"
CONF_FAST_UPDATES = "fast_updates"
CONF_LOW_HOPPER_KG = "low_hopper_kg"
CONF_IMPORT_STATISTICS = "import_statistics"

DEFAULT_SCAN_INTERVAL = 60  # seconds
MIN_SCAN_INTERVAL = 30
# Typical net calorific value of EN-plus wood pellets (kWh per kg)
DEFAULT_CALORIFIC_VALUE = 4.8
DEFAULT_FAST_UPDATES = True
DEFAULT_LOW_HOPPER_KG = 50
DEFAULT_IMPORT_STATISTICS = True

SCAN_INTERVAL = timedelta(seconds=DEFAULT_SCAN_INTERVAL)
# Fast updates: poll the cheap getstatus.php this often (seconds) and fetch
# the full data only when it changes.
FAST_INTERVAL = 10
# Settings menus and consumption history change slowly.
SETTINGS_REFRESH_SECONDS = 30 * 60
HISTORY_REFRESH_SECONDS = 30 * 60

EVENT_STOKERCLOUD = f"{DOMAIN}_event"

MANUFACTURER = "NBE"
DEVICE_NAME = "NBE"
