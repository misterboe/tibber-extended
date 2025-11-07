"""Binary sensor platform for Tibber Smart Control."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
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

    # Create entities for ALL homes
    entities = []

    if coordinator.data:
        for home_id in coordinator.data:
            entities.extend([
                TibberIsVeryCheapSensor(coordinator, home_id),
                TibberIsCheapSensor(coordinator, home_id),
                TibberIsExpensiveSensor(coordinator, home_id),
                TibberIsVeryExpensiveSensor(coordinator, home_id),
                TibberIsCheapHourSensor(coordinator, home_id),
                TibberIsExpensiveHourSensor(coordinator, home_id),
                TibberIsGoodChargingTimeSensor(coordinator, home_id),
                # Architecture v2.0 - Threshold Binary Sensors
                TibberIsBelowAverageSensor(coordinator, home_id),
                # Time Window Optimization
                TibberIsInBestConsecutiveHoursWindowSensor(coordinator, home_id),
                # Battery Charging Optimization
                TibberBatteryChargingRecommendedSensor(coordinator, home_id),
                # Single Cheapest Hour (absolute minimum)
                TibberIsCheapestHourSensor(coordinator, home_id),
                # Time Window Cheapest Hours
                TibberIsTimeWindowCheapHourBinarySensor(coordinator, home_id),
            ])

    async_add_entities(entities)


class TibberBinarySensorBase(TibberEntityBase, BinarySensorEntity):
    """Base class for Tibber binary sensors."""

    pass


class TibberIsVeryCheapSensor(TibberBinarySensorBase):
    """Binary sensor indicating if current price is VERY_CHEAP."""

    def __init__(self, coordinator: TibberDataUpdateCoordinator, home_id: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, home_id, "is_very_cheap")

    @property
    def is_on(self) -> bool:
        """Return true if current price level is VERY_CHEAP."""
        if self._home_data:
            level = self._home_data["current"].get("level")
            return level == "VERY_CHEAP"
        return False

    @property
    def icon(self) -> str:
        """Return icon."""
        return "mdi:cash-check" if self.is_on else "mdi:cash"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        if not self._home_data:
            return {}

        return {
            "current_price": self._home_data["current"]["total"],
            "price_level": self._home_data["current"].get("level"),
        }


class TibberIsCheapSensor(TibberBinarySensorBase):
    """Binary sensor indicating if current price is CHEAP or VERY_CHEAP."""

    def __init__(self, coordinator: TibberDataUpdateCoordinator, home_id: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, home_id, "is_cheap")

    @property
    def is_on(self) -> bool:
        """Return true if current price level is CHEAP or VERY_CHEAP."""
        if self._home_data:
            level = self._home_data["current"].get("level")
            return level in ["CHEAP", "VERY_CHEAP"]
        return False

    @property
    def icon(self) -> str:
        """Return icon."""
        return "mdi:lightning-bolt" if self.is_on else "mdi:lightning-bolt-outline"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        if not self._home_data:
            return {}

        return {
            "current_price": self._home_data["current"]["total"],
            "average_price": self._home_data["average_price"],
            "price_level": self._home_data["current"].get("level"),
        }


class TibberIsExpensiveSensor(TibberBinarySensorBase):
    """Binary sensor indicating if current price is EXPENSIVE or VERY_EXPENSIVE."""

    def __init__(self, coordinator: TibberDataUpdateCoordinator, home_id: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, home_id, "is_expensive")

    @property
    def is_on(self) -> bool:
        """Return true if current price level is EXPENSIVE or VERY_EXPENSIVE."""
        if self._home_data:
            level = self._home_data["current"].get("level")
            return level in ["EXPENSIVE", "VERY_EXPENSIVE"]
        return False

    @property
    def icon(self) -> str:
        """Return icon."""
        return "mdi:alert-circle" if self.is_on else "mdi:check-circle-outline"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        if not self._home_data:
            return {}

        return {
            "current_price": self._home_data["current"]["total"],
            "average_price": self._home_data["average_price"],
            "price_level": self._home_data["current"].get("level"),
        }


class TibberIsVeryExpensiveSensor(TibberBinarySensorBase):
    """Binary sensor indicating if current price is VERY_EXPENSIVE."""

    def __init__(self, coordinator: TibberDataUpdateCoordinator, home_id: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, home_id, "is_very_expensive")

    @property
    def is_on(self) -> bool:
        """Return true if current price level is VERY_EXPENSIVE."""
        if self._home_data:
            level = self._home_data["current"].get("level")
            return level == "VERY_EXPENSIVE"
        return False

    @property
    def icon(self) -> str:
        """Return icon."""
        return "mdi:alert-octagon" if self.is_on else "mdi:cash"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        if not self._home_data:
            return {}

        return {
            "current_price": self._home_data["current"]["total"],
            "price_level": self._home_data["current"].get("level"),
        }


class TibberIsCheapHourSensor(TibberBinarySensorBase):
    """Binary sensor indicating if current hour is one of the N cheap hours (top N cheapest)."""

    def __init__(self, coordinator: TibberDataUpdateCoordinator, home_id: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, home_id, "is_cheap_hour")

    @property
    def is_on(self) -> bool:
        """Return true if current hour is one of the cheapest."""
        if not self._home_data:
            return False

        cheapest = self._home_data.get("cheapest_hours", [])
        current_time = self._home_data["current"].get("startsAt")

        for hour in cheapest:
            if hour.get("start") == current_time:
                return True

        return False

    @property
    def icon(self) -> str:
        """Return icon."""
        return "mdi:star" if self.is_on else "mdi:star-outline"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        if not self._home_data:
            return {}

        cheapest_hours = []
        for hour in self._home_data.get("cheapest_hours", []):
            time_str = hour["start"].split("T")[1][:5]
            cheapest_hours.append(f"{time_str} ({hour['price']:.4f}€)")

        return {
            "current_price": self._home_data["current"]["total"],
            "cheapest_hours": cheapest_hours,
        }


class TibberIsExpensiveHourSensor(TibberBinarySensorBase):
    """Binary sensor indicating if current hour is one of the N expensive hours (top N most expensive)."""

    def __init__(self, coordinator: TibberDataUpdateCoordinator, home_id: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, home_id, "is_expensive_hour")

    @property
    def is_on(self) -> bool:
        """Return true if current hour is one of the most expensive."""
        if not self._home_data:
            return False

        most_expensive = self._home_data.get("most_expensive_hours", [])
        current_time = self._home_data["current"].get("startsAt")

        for hour in most_expensive:
            if hour.get("start") == current_time:
                return True

        return False

    @property
    def icon(self) -> str:
        """Return icon."""
        return "mdi:alert" if self.is_on else "mdi:check"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        if not self._home_data:
            return {}

        expensive_hours = []
        for hour in self._home_data.get("most_expensive_hours", []):
            time_str = hour["start"].split("T")[1][:5]
            expensive_hours.append(f"{time_str} ({hour['price']:.4f}€)")

        return {
            "current_price": self._home_data["current"]["total"],
            "most_expensive_hours": expensive_hours,
        }


class TibberIsGoodChargingTimeSensor(TibberBinarySensorBase):
    """Binary sensor for smart charging decision (cheap OR cheapest hour)."""

    def __init__(self, coordinator: TibberDataUpdateCoordinator, home_id: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, home_id, "is_good_charging_time")

    @property
    def is_on(self) -> bool:
        """Return true if it's a good time to charge (CHEAP/VERY_CHEAP or cheapest hour)."""
        if not self._home_data:
            return False

        # Check if price level is cheap
        level = self._home_data["current"].get("level")
        if level in ["CHEAP", "VERY_CHEAP"]:
            return True

        # Check if it's one of the cheapest hours
        cheapest = self._home_data.get("cheapest_hours", [])
        current_time = self._home_data["current"].get("startsAt")

        for hour in cheapest:
            if hour.get("start") == current_time:
                return True

        return False

    @property
    def icon(self) -> str:
        """Return icon."""
        return "mdi:ev-station" if self.is_on else "mdi:ev-plug-type2"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        if not self._home_data:
            return {}

        cheapest_hours = []
        for hour in self._home_data.get("cheapest_hours", []):
            time_str = hour["start"].split("T")[1][:5]
            cheapest_hours.append(f"{time_str} ({hour['price']:.4f}€)")

        return {
            "current_price": self._home_data["current"]["total"],
            "average_price": self._home_data["average_price"],
            "price_level": self._home_data["current"].get("level"),
            "cheapest_hours": cheapest_hours,
            "reason": self._get_reason(),
        }

    def _get_reason(self) -> str:
        """Get reason why it's a good charging time."""
        if not self.is_on:
            return "Not a good time - price too high"

        level = self._home_data["current"].get("level")
        if level == "VERY_CHEAP":
            return "Very cheap electricity right now"
        if level == "CHEAP":
            return "Cheap electricity right now"

        # Check if it's cheapest hour
        cheapest = self._home_data.get("cheapest_hours", [])
        current_time = self._home_data["current"].get("startsAt")

        for i, hour in enumerate(cheapest):
            if hour.get("start") == current_time:
                return f"One of the {i+1} cheapest hours today"

        return "Good charging time"


# ============================================================================
# Architecture v2.0 - Threshold Binary Sensors
# ============================================================================


class TibberIsBelowAverageSensor(TibberBinarySensorBase):
    """Binary sensor indicating if current price is below average."""

    def __init__(self, coordinator: TibberDataUpdateCoordinator, home_id: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, home_id, "is_below_average")

    @property
    def is_on(self) -> bool:
        """Return true if current price is below average."""
        if not self._home_data:
            return False

        current = self._home_data["current"]["total"]
        average = self._home_data["average_price"]
        return current < average

    @property
    def icon(self) -> str:
        """Return icon."""
        return "mdi:trending-down" if self.is_on else "mdi:trending-up"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        if not self._home_data:
            return {}

        return {
            "current_price": self._home_data["current"]["total"],
            "average_price": self._home_data["average_price"],
            "deviation_percent": self._home_data.get("deviation_percent"),
            "deviation_absolute": self._home_data.get("deviation_absolute"),
        }


# ============================================================================
# Time Window Optimization Sensors
# ============================================================================


class TibberIsInBestConsecutiveHoursWindowSensor(TibberBinarySensorBase):
    """Binary sensor indicating if currently in best consecutive hours window (configurable duration)."""

    def __init__(self, coordinator: TibberDataUpdateCoordinator, home_id: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, home_id, "is_in_best_consecutive_hours")

    @property
    def is_on(self) -> bool:
        """Return true if currently in best consecutive hours window."""
        if not self._home_data:
            return False

        best_window = self._home_data.get("best_consecutive_hours")
        if not best_window or not best_window.get("hours"):
            return False

        current_time = self._home_data["current"].get("startsAt")
        if not current_time:
            return False

        # Check if current time is within the consecutive hours window
        window_hours = best_window.get("hours", [])
        for hour in window_hours:
            if hour.get("start") == current_time:
                return True

        return False

    @property
    def icon(self) -> str:
        """Return icon."""
        return "mdi:clock-check" if self.is_on else "mdi:clock-outline"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        if not self._home_data:
            return {}

        best_window = self._home_data.get("best_consecutive_hours")
        if not best_window or not best_window.get("hours"):
            return {
                "status": "No window data available",
            }

        # Format window times
        window_hours_list = best_window.get("hours", [])
        window_hours_formatted = []
        for hour in window_hours_list:
            time_str = hour["start"].split("T")[1][:5]
            window_hours_formatted.append(f"{time_str} ({hour['price']:.4f}€)")

        # Calculate savings
        avg_price = self._home_data.get("average_price", 0)
        window_avg = best_window.get("average_price", 0)
        savings_per_kwh = avg_price - window_avg
        savings_percent = (savings_per_kwh / avg_price * 100) if avg_price > 0 else 0

        return {
            "current_price": self._home_data["current"]["total"],
            "best_consecutive_hours": window_hours_list,
            "window_start": best_window.get("window_start"),
            "window_end": best_window.get("window_end"),
            "window_average_price": window_avg,
            "daily_average_price": avg_price,
            "savings_per_kwh": round(savings_per_kwh, 4),
            "savings_percent": round(savings_percent, 1),
            "window_hours_formatted": window_hours_formatted,
            "window_duration_hours": int(self.coordinator.hours_duration),
        }


class TibberBatteryChargingRecommendedSensor(TibberBinarySensorBase):
    """Binary sensor for battery charging recommendation based on efficiency."""

    def __init__(
        self, coordinator: TibberDataUpdateCoordinator, home_id: str
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, home_id, "is_cheap_power_now")

    @property
    def is_on(self) -> bool:
        """Return true when power is cheap (in cheapest hours AND below average)."""
        if not self._home_data:
            return False

        # Check if current hour is one of the 3 cheapest hours
        cheapest_hours = self._home_data.get("cheapest_hours", [])
        current_time = self._home_data["current"].get("startsAt")

        is_cheapest_hour = False
        for hour in cheapest_hours:
            if hour.get("start") == current_time:
                is_cheapest_hour = True
                break

        # Check if below average (with battery efficiency consideration)
        is_economical = self._home_data.get("battery_is_economical", False)

        # BOTH conditions must be true
        return is_cheapest_hour and is_economical

    @property
    def icon(self) -> str:
        """Return icon."""
        return "mdi:battery-charging" if self.is_on else "mdi:battery-check"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        if not self._home_data:
            return {}

        current_price = self._home_data["current"]["total"]
        battery_efficiency = self._home_data.get("battery_efficiency", 0)
        breakeven_price = self._home_data.get("battery_breakeven_price", 0)
        average_price = self._home_data.get("average_price", 0)
        cheapest_hours = self._home_data.get("cheapest_hours", [])

        return {
            "current_price": current_price,
            "battery_efficiency": battery_efficiency,
            "breakeven_price": breakeven_price,
            "average_price": average_price,
            "is_below_breakeven": current_price <= breakeven_price,
            "difference_to_breakeven": round(breakeven_price - current_price, 4),
            "cheapest_hours_today": len(cheapest_hours),
        }


class TibberIsCheapestHourSensor(TibberBinarySensorBase):
    """Binary sensor indicating if current hour is THE cheapest hour of the day (00:00-23:59)."""

    def __init__(
        self, coordinator: TibberDataUpdateCoordinator, home_id: str
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, home_id, "is_cheapest_hour")

    @property
    def is_on(self) -> bool:
        """Return true if current hour is THE cheapest hour of the entire day."""
        if not self._home_data:
            return False

        # Get the cheapest hour (first in sorted cheapest_hours list)
        cheapest_hours = self._home_data.get("cheapest_hours", [])
        if not cheapest_hours:
            return False

        # The first entry is the cheapest
        cheapest = cheapest_hours[0]
        current_time = self._home_data["current"].get("startsAt")

        return cheapest.get("start") == current_time

    @property
    def icon(self) -> str:
        """Return icon."""
        return "mdi:trophy" if self.is_on else "mdi:trophy-outline"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        if not self._home_data:
            return {}

        cheapest_hours = self._home_data.get("cheapest_hours", [])
        if not cheapest_hours:
            return {"status": "No price data available"}

        cheapest = cheapest_hours[0]
        current_price = self._home_data["current"]["total"]

        # Format cheapest hour info
        cheapest_time = cheapest["start"].split("T")[1][:5]
        cheapest_price = cheapest["price"]

        return {
            "current_price": current_price,
            "cheapest_hour": f"{cheapest_time} ({cheapest_price:.4f}€)",
            "cheapest_price": cheapest_price,
            "cheapest_time": cheapest_time,
            "difference_to_cheapest": round(current_price - cheapest_price, 4),
        }


class TibberIsTimeWindowCheapHourBinarySensor(TibberBinarySensorBase):
    """Binary sensor indicating if current hour is one of the cheapest in configured time window."""

    def __init__(
        self, coordinator: TibberDataUpdateCoordinator, home_id: str
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, home_id, "is_time_window_cheap_hour")

    @property
    def is_on(self) -> bool:
        """Return true if current hour is in time window AND is one of the cheapest hours."""
        if not self._home_data:
            return False

        # Get current time info
        current_time = self._home_data["current"].get("startsAt")
        if not current_time:
            return False

        # Get time window cheapest hours
        time_window_cheapest = self._home_data.get("time_window_cheapest_hours", [])
        if not time_window_cheapest:
            return False

        # Check if current time is one of the time window cheapest hours
        for hour in time_window_cheapest:
            if hour.get("start") == current_time:
                return True

        return False

    @property
    def icon(self) -> str:
        """Return icon."""
        return "mdi:clock-check" if self.is_on else "mdi:clock-outline"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        if not self._home_data:
            return {}

        time_window_cheapest = self._home_data.get("time_window_cheapest_hours", [])

        # Format cheap hours for display
        cheap_hours_formatted = []
        for hour in time_window_cheapest:
            time_str = hour["start"].split("T")[1][:5]
            cheap_hours_formatted.append(f"{time_str} ({hour['price']:.4f}€)")

        return {
            "current_price": self._home_data["current"]["total"],
            "time_window_start": self.coordinator.time_window_start,
            "time_window_end": self.coordinator.time_window_end,
            "time_window_cheapest_hours": cheap_hours_formatted,
            "hours_count": int(self.coordinator.hours_duration),
        }
