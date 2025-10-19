"""NBE Stoker Cloud."""
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType
from .const import DOMAIN, PLATFORMS
from homeassistant.config_entries import ConfigEntry
from stokercloud.client import Client as StokerCloudClient
from homeassistant.const import CONF_USERNAME


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the component."""
    hass.data[DOMAIN] = {}
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up from a config entry."""
    hass.data[DOMAIN][entry.entry_id] = StokerCloudClient(entry.data[CONF_USERNAME])
    
    # Fixed: Correct way to forward entry setups
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    
    return unload_ok