"""Base entity for Tibber Smart Control."""
from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import TibberDataUpdateCoordinator


class TibberEntityBase(CoordinatorEntity[TibberDataUpdateCoordinator]):
    """Common base for all Tibber entities."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: TibberDataUpdateCoordinator, sensor_type: str
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._sensor_type = sensor_type
        self._attr_name = sensor_type.replace("_", " ").title()

        # Set unique ID with home ID
        if coordinator.data and "home" in coordinator.data:
            home_id = coordinator.data["home"]["id"]
            self._attr_unique_id = f"{home_id}_{sensor_type}"
        else:
            self._attr_unique_id = f"tibber_{sensor_type}"

    @property
    def device_info(self) -> DeviceInfo | None:
        """Return device information to group entities."""
        if not self.coordinator.data or "home" not in self.coordinator.data:
            return None

        home = self.coordinator.data["home"]

        return DeviceInfo(
            identifiers={(DOMAIN, home["id"])},
            name=home["name"],
            manufacturer="Tibber",
            model="Smart Control",
            configuration_url="https://app.tibber.com",
            suggested_area="Energy",
            entry_type=None,
        )
