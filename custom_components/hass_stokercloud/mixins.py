"""Mixins for Stokercloud entities."""
from stokercloud.client import Client as StokerCloudClient
import logging

logger = logging.getLogger(__name__)


class StokerCloudControllerMixin:
    """Mixin for Stokercloud entities."""
    
    def __init__(self, client: StokerCloudClient, serial, name: str, client_key: str):
        """Initialize the sensor."""
        logger.debug("Initializing sensor %s" % name)
        self._state = None
        self._name = name
        self.client = client
        self.client_key = client_key
        self._serial = serial
        self.controller_data = None

    @property
    def unique_id(self):
        """The unique id of the sensor."""
        return f'{self._serial}-{self._name}'

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return "NBE %s" % self._name

    async def async_update(self) -> None:
        """Fetch new state data for the sensor (async version)."""
        logger.debug("Async updating %s" % self.name)
        try:
            # Fetch data using async method
            await self.client.async_get_data()
            self.controller_data = self.client.controller_data()
            
            if self.client_key:
                self._state = getattr(self.controller_data, self.client_key, None)
                logger.debug("New state for %s: %s" % (self.name, self._state))
        except Exception as e:
            logger.error(f"Error updating {self.name}: {e}", exc_info=True)