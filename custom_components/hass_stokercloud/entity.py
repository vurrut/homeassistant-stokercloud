"""Base entity for NBE StokerCloud."""
from __future__ import annotations

from homeassistant.const import CONF_USERNAME
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DEVICE_NAME, DOMAIN, MANUFACTURER
from .coordinator import StokerCloudCoordinator


class StokerCloudEntity(CoordinatorEntity[StokerCloudCoordinator]):
    """Common device info and unique id.

    unique_id stays ``<username>-<name>`` as in v1/v2 so existing entities
    (and their history) are kept on upgrade.
    """

    _attr_has_entity_name = True

    def __init__(self, coordinator: StokerCloudCoordinator, description: EntityDescription) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        username = coordinator.config_entry.data[CONF_USERNAME]
        self._attr_unique_id = f"{username}-{description.key}"
        controller = coordinator.data.controller
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, username)},
            name=DEVICE_NAME,
            manufacturer=MANUFACTURER,
            model=f"StokerCloud {controller.controller_type or 'v16'}",
            serial_number=controller.serial or None,
            configuration_url="https://v16.stokercloud.dk/",
        )

    @property
    def available(self) -> bool:
        return super().available and not self.coordinator.data.controller.notconnected
