"""Diagnostics for NBE StokerCloud (Settings → Devices → NBE → Download diagnostics)."""
from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from .coordinator import StokerCloudConfigEntry

TO_REDACT = {CONF_PASSWORD, CONF_USERNAME, "serial", "alias", "token", "userid"}


def _redact_city(raw: dict[str, Any]) -> dict[str, Any]:
    raw = dict(raw)
    weather = []
    for item in raw.get("weatherdata") or []:
        if isinstance(item, dict) and item.get("id") == "weather-city":
            item = {**item, "value": "**REDACTED**"}
        weather.append(item)
    raw["weatherdata"] = weather
    return raw


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: StokerCloudConfigEntry
) -> dict[str, Any]:
    coordinator = entry.runtime_data
    data = coordinator.data
    return {
        "entry": {
            "data": async_redact_data(dict(entry.data), TO_REDACT),
            "options": dict(entry.options),
        },
        "last_update_success": coordinator.last_update_success,
        "state": str(data.controller.state),
        "controller": async_redact_data(_redact_city(data.controller.raw), TO_REDACT),
        "settings": data.settings,
    }
