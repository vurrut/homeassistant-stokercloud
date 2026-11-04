"""Services for NBE StokerCloud."""
from __future__ import annotations

import re

import voluptuous as vol

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse, SupportsResponse
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN
from .coordinator import StokerCloudCoordinator

SERVICE_SET_VALUE = "set_value"
ATTR_CONFIG_ENTRY = "config_entry_id"
ATTR_SETTING = "setting"
ATTR_VALUE = "value"

# Setting ids look like "boiler.temp", "hot_water.diff_under", "hopper.content"
_SETTING_RE = re.compile(r"^[a-z0-9_]+\.[a-z0-9_]+$")

SET_VALUE_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_CONFIG_ENTRY): cv.string,
        vol.Required(ATTR_SETTING): vol.All(cv.string, vol.Match(_SETTING_RE)),
        vol.Required(ATTR_VALUE): vol.Coerce(float),
    }
)


def _coordinator(hass: HomeAssistant, entry_id: str | None) -> StokerCloudCoordinator:
    entries = [
        e
        for e in hass.config_entries.async_entries(DOMAIN)
        if e.state is ConfigEntryState.LOADED and (entry_id is None or e.entry_id == entry_id)
    ]
    if not entries:
        raise ServiceValidationError("No loaded StokerCloud entry found")
    if len(entries) > 1:
        raise ServiceValidationError(
            "Several StokerCloud entries are loaded; pass config_entry_id"
        )
    return entries[0].runtime_data


def async_setup_services(hass: HomeAssistant) -> None:
    async def set_value(call: ServiceCall) -> ServiceResponse:
        coordinator = _coordinator(hass, call.data.get(ATTR_CONFIG_ENTRY))
        setting: str = call.data[ATTR_SETTING]
        value: float = call.data[ATTR_VALUE]

        # Validate against the limits the controller reports, when we have them.
        menu = setting.split(".", 1)[0]
        limits = coordinator.data.setting(setting)
        if limits is None and menu not in ("boiler", "hot_water", "hopper"):
            try:
                limits = (await coordinator.client.async_get_menu(menu)).get(setting)
            except Exception:  # noqa: BLE001 - validation is best effort
                limits = None
        if limits is not None:
            lo, hi = float(limits.get("min", -1)), float(limits.get("max", -1))
            if lo == -1 and hi == -1:
                raise ServiceValidationError(f"{setting} is not a numeric setting")
            if not lo <= value <= hi:
                raise ServiceValidationError(f"{setting} must be between {lo:g} and {hi:g}")
            factor = float(limits.get("factor", 1) or 1)
            # factor 10 -> one decimal, 100 -> two decimals, 1 -> integer
            value = round(value, len(str(int(factor))) - 1)

        response = await coordinator.async_write(
            lambda: coordinator.client.async_set_value(setting, value),
            f"Setting {setting} to {value:g}",
        )
        return {"response": response}

    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_VALUE,
        set_value,
        schema=SET_VALUE_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )
