"""Constants for the Stokercloud integration."""
from __future__ import annotations

from homeassistant.const import Platform

# Integration domain
DOMAIN = "hass_stokercloud"

# Platforms
PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BINARY_SENSOR, Platform.CLIMATE]

# API Configuration
API_BASE_URL = "https://stokercloud.dk/v3/data"

# Configuration
CONF_USERNAME = "username"

# Default values
SCAN_INTERVAL = 60  # 1 minutes
DEFAULT_NAME = "Stokercloud"

# API endpoints and configuration
API_BASE_URL = "https://stokercloud.dk/v3/api"
API_TIMEOUT = 30

# Device classes and unit mappings
SENSOR_TYPES = {
    "temperature": {
        "device_class": "temperature",
        "state_class": "measurement",
        "unit_of_measurement": "°C",
        "icon": "mdi:thermometer",
    },
    "power": {
        "device_class": "power", 
        "state_class": "measurement",
        "unit_of_measurement": "kW",
        "icon": "mdi:flash",
    },
    "mass": {
        "device_class": "weight",
        "state_class": "measurement", 
        "unit_of_measurement": "kg",
        "icon": "mdi:weight-kilogram",
    },
    "energy": {
        "device_class": "energy",
        "state_class": "total_increasing",
        "unit_of_measurement": "kWh", 
        "icon": "mdi:lightning-bolt",
    },
}

# Error messages
ERROR_CANNOT_CONNECT = "cannot_connect"
ERROR_INVALID_AUTH = "invalid_auth"
ERROR_UNKNOWN = "unknown"