"""NBE Stoker Cloud."""
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
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
    # Get aiohttp session and create client
    session = async_get_clientsession(hass)
    client = StokerCloudClient(entry.data[CONF_USERNAME], session)
    hass.data[DOMAIN][entry.entry_id] = client
    
    # Forward entry setups
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    
    if unload_ok:
        client = hass.data[DOMAIN].pop(entry.entry_id)
        await client.close()
    
    return unload_ok