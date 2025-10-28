"""Time window management for Tibber Extended."""
from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import async_get_platforms

from .const import CONF_TIME_WINDOWS, DOMAIN

_LOGGER = logging.getLogger(__name__)


@dataclass
class TimeWindow:
    """Represents a user-configured time window optimization."""

    name: str  # User-defined, used in entity_id (e.g., "3h_billig", "nacht_laden")
    duration_hours: float  # Duration in hours (0.5 - 24)
    power_kw: float | None = None  # Optional power rating for cost calculations


class TimeWindowManager:
    """Manages time windows and their associated entities."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        coordinator,
    ) -> None:
        """Initialize the TimeWindowManager."""
        self._hass = hass
        self._config_entry = config_entry
        self._coordinator = coordinator
        self._windows: dict[str, TimeWindow] = {}
        self._entity_registry = {}

        # Load existing windows from config
        self._load_windows_from_config()

    def _load_windows_from_config(self) -> None:
        """Load time windows from config entry options."""
        windows_data = self._config_entry.options.get(CONF_TIME_WINDOWS, [])

        for window_data in windows_data:
            name = window_data.get("name")
            if name:
                self._windows[name] = TimeWindow(
                    name=name,
                    duration_hours=window_data.get("duration_hours", 1.0),
                    power_kw=window_data.get("power_kw"),
                )

        _LOGGER.debug("Loaded %d time windows from config", len(self._windows))

    async def save_windows_to_config(self) -> None:
        """Save current time windows to config entry options."""
        windows_data = [
            {
                "name": window.name,
                "duration_hours": window.duration_hours,
                "power_kw": window.power_kw,
            }
            for window in self._windows.values()
        ]

        new_options = {
            **self._config_entry.options,
            CONF_TIME_WINDOWS: windows_data,
        }

        self._hass.config_entries.async_update_entry(
            self._config_entry,
            options=new_options,
        )

        _LOGGER.debug("Saved %d time windows to config", len(self._windows))

    async def add_window(
        self,
        name: str,
        duration: float,
        power_kw: float | None = None,
    ) -> bool:
        """
        Add a time window and create its entities.

        Args:
            name: User-defined name (will be part of entity_id)
            duration: Duration in hours
            power_kw: Optional power rating

        Returns:
            True if successful, False if window already exists
        """
        if name in self._windows:
            _LOGGER.warning("Time window '%s' already exists", name)
            return False

        # Validate name (alphanumeric, underscore, hyphen only)
        if not name.replace("_", "").replace("-", "").isalnum():
            _LOGGER.error("Invalid window name '%s' - use only alphanumeric, underscore, hyphen", name)
            return False

        # Create window
        window = TimeWindow(name=name, duration_hours=duration, power_kw=power_kw)
        self._windows[name] = window

        # Save to config
        await self.save_windows_to_config()

        # Create entities for this window
        await self._create_entities_for_window(window)

        _LOGGER.info("Added time window '%s' (duration: %sh, power: %s kW)", name, duration, power_kw)
        return True

    async def remove_window(self, name: str) -> bool:
        """
        Remove time window and its entities.

        Args:
            name: Window name to remove

        Returns:
            True if successful, False if window doesn't exist
        """
        if name not in self._windows:
            _LOGGER.warning("Time window '%s' does not exist", name)
            return False

        # Remove entities first
        await self._remove_entities_for_window(name)

        # Remove from windows dict
        del self._windows[name]

        # Save to config
        await self.save_windows_to_config()

        _LOGGER.info("Removed time window '%s'", name)
        return True

    async def _create_entities_for_window(self, window: TimeWindow) -> None:
        """Dynamically create sensor and binary_sensor entities for a window."""
        from .window_sensor import (
            TibberBestStartTimeSensor,
            TibberOptimalStartBinarySensor,
            TibberInOptimalWindowBinarySensor,
        )

        # Get coordinator data
        if not self._coordinator.data:
            _LOGGER.warning("No coordinator data available yet")
            return

        # Create entities for each home
        sensor_entities = []
        binary_sensor_entities = []

        for home_id in self._coordinator.data:
            # Create sensor for best start time
            sensor_entities.append(
                TibberBestStartTimeSensor(
                    self._coordinator,
                    home_id,
                    window.name,
                    window.duration_hours,
                    window.power_kw,
                )
            )

            # Create binary sensors
            binary_sensor_entities.append(
                TibberOptimalStartBinarySensor(
                    self._coordinator,
                    home_id,
                    window.name,
                    window.duration_hours,
                )
            )
            binary_sensor_entities.append(
                TibberInOptimalWindowBinarySensor(
                    self._coordinator,
                    home_id,
                    window.name,
                    window.duration_hours,
                )
            )

        # Add entities to Home Assistant
        if sensor_entities:
            for platform in async_get_platforms(self._hass, DOMAIN):
                if platform.domain == "sensor":
                    await platform.async_add_entities(sensor_entities)
                    break

        if binary_sensor_entities:
            for platform in async_get_platforms(self._hass, DOMAIN):
                if platform.domain == "binary_sensor":
                    await platform.async_add_entities(binary_sensor_entities)
                    break

        # Track entities
        self._entity_registry[window.name] = {
            "sensors": sensor_entities,
            "binary_sensors": binary_sensor_entities,
        }

        _LOGGER.debug(
            "Created %d entities for window '%s'",
            len(sensor_entities) + len(binary_sensor_entities),
            window.name,
        )

    async def _remove_entities_for_window(self, name: str) -> None:
        """Remove all entities associated with a time window."""
        if name not in self._entity_registry:
            return

        entities = self._entity_registry[name]

        # Remove sensor entities
        for entity in entities.get("sensors", []):
            await entity.async_remove()

        # Remove binary sensor entities
        for entity in entities.get("binary_sensors", []):
            await entity.async_remove()

        # Remove from registry
        del self._entity_registry[name]

        _LOGGER.debug("Removed entities for window '%s'", name)

    def get_window(self, name: str) -> TimeWindow | None:
        """Get a time window by name."""
        return self._windows.get(name)

    def get_all_windows(self) -> dict[str, TimeWindow]:
        """Get all configured time windows."""
        return self._windows.copy()

    async def reload_entities(self) -> None:
        """Reload all entities for all windows."""
        _LOGGER.info("Reloading entities for %d time windows", len(self._windows))

        # Remove all existing entities
        for name in list(self._entity_registry.keys()):
            await self._remove_entities_for_window(name)

        # Recreate entities for all windows
        for window in self._windows.values():
            await self._create_entities_for_window(window)
