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
        self,
        coordinator: TibberDataUpdateCoordinator,
        home_id: str,
        sensor_type: str,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._home_id = home_id
        self._sensor_type = sensor_type

        # Entity name is just the sensor type (device name provides prefix)
        self._attr_name = sensor_type.replace('_', ' ').title()
        self._attr_unique_id = f"{home_id}_{sensor_type}"

    @property
    def _home_data(self) -> dict | None:
        """Get data for this home."""
        if not self.coordinator.data:
            return None
        return self.coordinator.data.get(self._home_id)

    @property
    def device_info(self) -> DeviceInfo | None:
        """Return device information to group entities."""
        home_data = self._home_data
        if not home_data or "home" not in home_data:
            return None

        home = home_data["home"]
        slug = home.get("slug", home["id"])

        return DeviceInfo(
            identifiers={(DOMAIN, home["id"])},
            name=f"tibber_extended_{slug}",
            manufacturer="Tibber",
            model="Smart Control",
            configuration_url="https://app.tibber.com",
            suggested_area="Energy",
            entry_type=None,
        )
