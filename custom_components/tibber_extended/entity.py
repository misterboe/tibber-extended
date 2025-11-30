"""Base entity for Tibber Smart Control."""
from __future__ import annotations

from typing import Any

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
        home_id: str | None,
        sensor_type: str,
    ) -> None:
        """Initialize the entity.

        Args:
            coordinator: The data update coordinator
            home_id: Home ID for per-home sensors, None for global sensors
            sensor_type: Type identifier for the sensor
        """
        super().__init__(coordinator)
        self._home_id = home_id
        self._sensor_type = sensor_type
        self._is_global = home_id is None

        # Entity name is just the sensor type (device name provides prefix)
        self._attr_name = sensor_type.replace('_', ' ').title()

        # Unique ID: global sensors use domain prefix, per-home use home_id
        if self._is_global:
            self._attr_unique_id = f"{DOMAIN}_{sensor_type}"
        else:
            self._attr_unique_id = f"{home_id}_{sensor_type}"

    @property
    def _home_data(self) -> dict | None:
        """Get data for this home (None for global sensors)."""
        if self._is_global or not self.coordinator.data:
            return None
        return self.coordinator.data.get(self._home_id)

    @property
    def available(self) -> bool:
        """Return if entity is available.

        For per-home sensors: available if coordinator has data for this home.
        For global sensors: available if coordinator has any data.
        Entity remains available even if last_update_success is False
        (prevents brief unavailability during API timeouts).
        """
        if self._is_global:
            return self.coordinator.data is not None
        return self._home_data is not None

    @property
    def _data_status_attributes(self) -> dict[str, Any]:
        """Return data freshness attributes (for use in extra_state_attributes)."""
        attrs = {}

        # Add info about data freshness
        if self.coordinator._last_successful_fetch:
            attrs["last_successful_update"] = self.coordinator._last_successful_fetch.isoformat()

        if self.coordinator._using_cached_data:
            attrs["data_status"] = "cached"
            attrs["data_warning"] = "Using cached data due to API error"
        else:
            attrs["data_status"] = "live"

        return attrs

    @property
    def device_info(self) -> DeviceInfo | None:
        """Return device information to group entities."""
        # Global sensors use integration-level device
        if self._is_global:
            return DeviceInfo(
                identifiers={(DOMAIN, "api_diagnostics")},
                name="Tibber Extended API",
                manufacturer="Tibber",
                model="API Diagnostics",
                configuration_url="https://developer.tibber.com",
            )

        # Per-home sensors use home-specific device
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
