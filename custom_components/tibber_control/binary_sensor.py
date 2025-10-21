"""Binary sensor platform for Tibber Smart Control."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
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
    """Set up Tibber binary sensors from config entry."""
    coordinator: TibberDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities = [
        TibberIsVeryCheapSensor(coordinator),
        TibberIsCheapSensor(coordinator),
        TibberIsExpensiveSensor(coordinator),
        TibberIsVeryExpensiveSensor(coordinator),
        TibberIsCheapestHourSensor(coordinator),
        TibberIsMostExpensiveHourSensor(coordinator),
        TibberIsGoodChargingTimeSensor(coordinator),
    ]

    async_add_entities(entities)


class TibberBinarySensorBase(TibberEntityBase, BinarySensorEntity):
    """Base class for Tibber binary sensors."""

    pass


class TibberIsVeryCheapSensor(TibberBinarySensorBase):
    """Binary sensor indicating if current price is VERY_CHEAP."""

    def __init__(self, coordinator: TibberDataUpdateCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, "is_very_cheap")

    @property
    def is_on(self) -> bool:
        """Return true if current price level is VERY_CHEAP."""
        if self.coordinator.data:
            level = self.coordinator.data["current"].get("level")
            return level == "VERY_CHEAP"
        return False

    @property
    def icon(self) -> str:
        """Return icon."""
        return "mdi:cash-check" if self.is_on else "mdi:cash"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        if not self.coordinator.data:
            return {}

        return {
            "current_price": self.coordinator.data["current"]["total"],
            "price_level": self.coordinator.data["current"].get("level"),
        }


class TibberIsCheapSensor(TibberBinarySensorBase):
    """Binary sensor indicating if current price is CHEAP or VERY_CHEAP."""

    def __init__(self, coordinator: TibberDataUpdateCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, "is_cheap")

    @property
    def is_on(self) -> bool:
        """Return true if current price level is CHEAP or VERY_CHEAP."""
        if self.coordinator.data:
            level = self.coordinator.data["current"].get("level")
            return level in ["CHEAP", "VERY_CHEAP"]
        return False

    @property
    def icon(self) -> str:
        """Return icon."""
        return "mdi:lightning-bolt" if self.is_on else "mdi:lightning-bolt-outline"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        if not self.coordinator.data:
            return {}

        return {
            "current_price": self.coordinator.data["current"]["total"],
            "average_price": self.coordinator.data["average_price"],
            "price_level": self.coordinator.data["current"].get("level"),
        }


class TibberIsExpensiveSensor(TibberBinarySensorBase):
    """Binary sensor indicating if current price is EXPENSIVE or VERY_EXPENSIVE."""

    def __init__(self, coordinator: TibberDataUpdateCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, "is_expensive")

    @property
    def is_on(self) -> bool:
        """Return true if current price level is EXPENSIVE or VERY_EXPENSIVE."""
        if self.coordinator.data:
            level = self.coordinator.data["current"].get("level")
            return level in ["EXPENSIVE", "VERY_EXPENSIVE"]
        return False

    @property
    def icon(self) -> str:
        """Return icon."""
        return "mdi:alert-circle" if self.is_on else "mdi:check-circle-outline"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        if not self.coordinator.data:
            return {}

        return {
            "current_price": self.coordinator.data["current"]["total"],
            "average_price": self.coordinator.data["average_price"],
            "price_level": self.coordinator.data["current"].get("level"),
        }


class TibberIsVeryExpensiveSensor(TibberBinarySensorBase):
    """Binary sensor indicating if current price is VERY_EXPENSIVE."""

    def __init__(self, coordinator: TibberDataUpdateCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, "is_very_expensive")

    @property
    def is_on(self) -> bool:
        """Return true if current price level is VERY_EXPENSIVE."""
        if self.coordinator.data:
            level = self.coordinator.data["current"].get("level")
            return level == "VERY_EXPENSIVE"
        return False

    @property
    def icon(self) -> str:
        """Return icon."""
        return "mdi:alert-octagon" if self.is_on else "mdi:cash"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        if not self.coordinator.data:
            return {}

        return {
            "current_price": self.coordinator.data["current"]["total"],
            "price_level": self.coordinator.data["current"].get("level"),
        }


class TibberIsCheapestHourSensor(TibberBinarySensorBase):
    """Binary sensor indicating if current hour is one of the 3 cheapest."""

    def __init__(self, coordinator: TibberDataUpdateCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, "is_cheapest_hour")

    @property
    def is_on(self) -> bool:
        """Return true if current hour is one of the cheapest."""
        if not self.coordinator.data:
            return False

        cheapest = self.coordinator.data.get("cheapest_hours", [])
        current_time = self.coordinator.data["current"].get("startsAt")

        for hour in cheapest:
            if hour.get("startsAt") == current_time:
                return True

        return False

    @property
    def icon(self) -> str:
        """Return icon."""
        return "mdi:star" if self.is_on else "mdi:star-outline"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        if not self.coordinator.data:
            return {}

        cheapest_hours = []
        for hour in self.coordinator.data.get("cheapest_hours", []):
            time_str = hour["startsAt"].split("T")[1][:5]
            cheapest_hours.append(f"{time_str} ({hour['total']:.4f}€)")

        return {
            "current_price": self.coordinator.data["current"]["total"],
            "cheapest_hours": cheapest_hours,
        }


class TibberIsMostExpensiveHourSensor(TibberBinarySensorBase):
    """Binary sensor indicating if current hour is one of the 3 most expensive."""

    def __init__(self, coordinator: TibberDataUpdateCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, "is_most_expensive_hour")

    @property
    def is_on(self) -> bool:
        """Return true if current hour is one of the most expensive."""
        if not self.coordinator.data:
            return False

        most_expensive = self.coordinator.data.get("most_expensive_hours", [])
        current_time = self.coordinator.data["current"].get("startsAt")

        for hour in most_expensive:
            if hour.get("startsAt") == current_time:
                return True

        return False

    @property
    def icon(self) -> str:
        """Return icon."""
        return "mdi:alert" if self.is_on else "mdi:check"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        if not self.coordinator.data:
            return {}

        expensive_hours = []
        for hour in self.coordinator.data.get("most_expensive_hours", []):
            time_str = hour["startsAt"].split("T")[1][:5]
            expensive_hours.append(f"{time_str} ({hour['total']:.4f}€)")

        return {
            "current_price": self.coordinator.data["current"]["total"],
            "most_expensive_hours": expensive_hours,
        }


class TibberIsGoodChargingTimeSensor(TibberBinarySensorBase):
    """Binary sensor for smart charging decision (cheap OR cheapest hour)."""

    _attr_device_class = BinarySensorDeviceClass.POWER

    def __init__(self, coordinator: TibberDataUpdateCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, "is_good_charging_time")

    @property
    def is_on(self) -> bool:
        """Return true if it's a good time to charge (CHEAP/VERY_CHEAP or cheapest hour)."""
        if not self.coordinator.data:
            return False

        # Check if price level is cheap
        level = self.coordinator.data["current"].get("level")
        if level in ["CHEAP", "VERY_CHEAP"]:
            return True

        # Check if it's one of the cheapest hours
        cheapest = self.coordinator.data.get("cheapest_hours", [])
        current_time = self.coordinator.data["current"].get("startsAt")

        for hour in cheapest:
            if hour.get("startsAt") == current_time:
                return True

        return False

    @property
    def icon(self) -> str:
        """Return icon."""
        return "mdi:ev-station" if self.is_on else "mdi:ev-plug-type2"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        if not self.coordinator.data:
            return {}

        cheapest_hours = []
        for hour in self.coordinator.data.get("cheapest_hours", []):
            time_str = hour["startsAt"].split("T")[1][:5]
            cheapest_hours.append(f"{time_str} ({hour['total']:.4f}€)")

        return {
            "current_price": self.coordinator.data["current"]["total"],
            "average_price": self.coordinator.data["average_price"],
            "price_level": self.coordinator.data["current"].get("level"),
            "cheapest_hours": cheapest_hours,
            "reason": self._get_reason(),
        }

    def _get_reason(self) -> str:
        """Get reason why it's a good charging time."""
        if not self.is_on:
            return "Not a good time - price too high"

        level = self.coordinator.data["current"].get("level")
        if level == "VERY_CHEAP":
            return "Very cheap electricity right now"
        if level == "CHEAP":
            return "Cheap electricity right now"

        # Check if it's cheapest hour
        cheapest = self.coordinator.data.get("cheapest_hours", [])
        current_time = self.coordinator.data["current"].get("startsAt")

        for i, hour in enumerate(cheapest):
            if hour.get("startsAt") == current_time:
                return f"One of the {i+1} cheapest hours today"

        return "Good charging time"
