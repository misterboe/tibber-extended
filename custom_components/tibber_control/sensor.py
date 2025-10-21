"""Sensor platform for Tibber Smart Control."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import TibberDataUpdateCoordinator
from .entity import TibberEntityBase

_LOGGER = logging.getLogger(__name__)

# Coordinator is used to centralize the data updates
PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Tibber sensors from config entry."""
    coordinator: TibberDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities = [
        TibberCurrentPriceSensor(coordinator),
        TibberAveragePriceSensor(coordinator),
        TibberMinPriceSensor(coordinator),
        TibberMaxPriceSensor(coordinator),
        TibberPriceLevelSensor(coordinator),
        TibberCheapestHoursSensor(coordinator),
        TibberMostExpensiveHoursSensor(coordinator),
    ]

    async_add_entities(entities)


class TibberSensorBase(TibberEntityBase, SensorEntity):
    """Base class for Tibber sensors."""

    pass


class TibberCurrentPriceSensor(TibberSensorBase):
    """Sensor for current electricity price."""

    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "EUR/kWh"

    def __init__(self, coordinator: TibberDataUpdateCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, "current_price")

    @property
    def native_value(self) -> float | None:
        """Return the current price."""
        if self.coordinator.data:
            return self.coordinator.data["current"]["total"]
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        if not self.coordinator.data:
            return {}

        current = self.coordinator.data["current"]
        return {
            "energy": current.get("energy"),
            "tax": current.get("tax"),
            "level": current.get("level"),
            "starts_at": current.get("startsAt"),
            "today": self.coordinator.data.get("today", []),
            "tomorrow": self.coordinator.data.get("tomorrow", []),
        }


class TibberAveragePriceSensor(TibberSensorBase):
    """Sensor for average price today."""

    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "EUR/kWh"

    def __init__(self, coordinator: TibberDataUpdateCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, "average_price")

    @property
    def native_value(self) -> float | None:
        """Return the average price."""
        if self.coordinator.data:
            return round(self.coordinator.data["average_price"], 4)
        return None


class TibberMinPriceSensor(TibberSensorBase):
    """Sensor for minimum price today."""

    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "EUR/kWh"

    def __init__(self, coordinator: TibberDataUpdateCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, "min_price")

    @property
    def native_value(self) -> float | None:
        """Return the minimum price."""
        if self.coordinator.data:
            return round(self.coordinator.data["min_price"], 4)
        return None


class TibberMaxPriceSensor(TibberSensorBase):
    """Sensor for maximum price today."""

    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "EUR/kWh"

    def __init__(self, coordinator: TibberDataUpdateCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, "max_price")

    @property
    def native_value(self) -> float | None:
        """Return the maximum price."""
        if self.coordinator.data:
            return round(self.coordinator.data["max_price"], 4)
        return None


class TibberPriceLevelSensor(TibberSensorBase):
    """Sensor for current price level."""

    def __init__(self, coordinator: TibberDataUpdateCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, "price_level")

    @property
    def native_value(self) -> str | None:
        """Return the current price level."""
        if self.coordinator.data:
            return self.coordinator.data["current"].get("level")
        return None

    @property
    def icon(self) -> str:
        """Return icon based on price level."""
        level = self.native_value
        if level in ["VERY_CHEAP", "CHEAP"]:
            return "mdi:cash-minus"
        if level == "EXPENSIVE":
            return "mdi:cash-plus"
        if level == "VERY_EXPENSIVE":
            return "mdi:alert-circle"
        return "mdi:cash"


class TibberCheapestHoursSensor(TibberSensorBase):
    """Sensor showing the 3 cheapest hours today."""

    def __init__(self, coordinator: TibberDataUpdateCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, "cheapest_hours")

    @property
    def native_value(self) -> str | None:
        """Return cheapest hours as readable string."""
        if not self.coordinator.data or not self.coordinator.data.get("cheapest_hours"):
            return None

        hours = []
        for hour in self.coordinator.data["cheapest_hours"]:
            time_str = hour["startsAt"].split("T")[1][:5]  # Extract HH:MM
            price = hour["total"]
            hours.append(f"{time_str} ({price:.4f}€)")

        return ", ".join(hours)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return detailed hour information."""
        if not self.coordinator.data:
            return {}

        return {"hours": self.coordinator.data.get("cheapest_hours", [])}

    @property
    def icon(self) -> str:
        """Return icon."""
        return "mdi:cash-check"


class TibberMostExpensiveHoursSensor(TibberSensorBase):
    """Sensor showing the 3 most expensive hours today."""

    def __init__(self, coordinator: TibberDataUpdateCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, "most_expensive_hours")

    @property
    def native_value(self) -> str | None:
        """Return most expensive hours as readable string."""
        if (
            not self.coordinator.data
            or not self.coordinator.data.get("most_expensive_hours")
        ):
            return None

        hours = []
        for hour in self.coordinator.data["most_expensive_hours"]:
            time_str = hour["startsAt"].split("T")[1][:5]  # Extract HH:MM
            price = hour["total"]
            hours.append(f"{time_str} ({price:.4f}€)")

        return ", ".join(hours)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return detailed hour information."""
        if not self.coordinator.data:
            return {}

        return {"hours": self.coordinator.data.get("most_expensive_hours", [])}

    @property
    def icon(self) -> str:
        """Return icon."""
        return "mdi:alert-octagon"
