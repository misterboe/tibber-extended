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
    """Set up Tibber sensors from config entry."""
    coordinator: TibberDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    # Create entities for ALL homes
    entities = []

    if coordinator.data:
        for home_id in coordinator.data:
            entities.extend([
                TibberCurrentPriceSensor(coordinator, home_id),
                TibberAveragePriceSensor(coordinator, home_id),
                TibberMinPriceSensor(coordinator, home_id),
                TibberMaxPriceSensor(coordinator, home_id),
                TibberPriceLevelSensor(coordinator, home_id),
                TibberCheapestHoursSensor(coordinator, home_id),
                TibberMostExpensiveHoursSensor(coordinator, home_id),
                # Best consecutive hours (configurable duration)
                TibberBestConsecutiveHoursSensor(coordinator, home_id),
                # Architecture v2.0 - Deviation Sensors
                TibberPriceDeviationPercentSensor(coordinator, home_id),
                TibberPriceDeviationAbsoluteSensor(coordinator, home_id),
                # Battery Charging Optimization
                TibberBatteryBreakevenPriceSensor(coordinator, home_id),
            ])

    async_add_entities(entities)


class TibberSensorBase(TibberEntityBase, SensorEntity):
    """Base class for Tibber sensors."""

    pass


class TibberCurrentPriceSensor(TibberSensorBase):
    """Sensor for current electricity price."""

    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "EUR/kWh"

    def __init__(self, coordinator: TibberDataUpdateCoordinator, home_id: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, home_id, "current_price")

    @property
    def native_value(self) -> float | None:
        """Return the current price."""
        if self._home_data:
            return self._home_data["current"]["total"]
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes - SAME structure as REST sensor for compatibility."""
        if not self._home_data:
            return {}

        # Primary attributes - exactly like REST sensor
        return {
            # Core Tibber API data (1:1 wie REST sensor)
            "current": self._home_data.get("current"),
            "today": self._home_data.get("today", []),
            "tomorrow": self._home_data.get("tomorrow", []),

            # Extended analysis (zusätzlich zur REST sensor Struktur)
            "average_price": self._home_data.get("average_price"),
            "min_price": self._home_data.get("min_price"),
            "max_price": self._home_data.get("max_price"),
            "price_level": self._home_data["current"].get("level"),

            # Deviation analysis
            "deviation_percent": self._home_data.get("deviation_percent"),
            "deviation_absolute": self._home_data.get("deviation_absolute"),

            # Rank analysis
            "rank": self._home_data.get("rank"),
            "percentile": self._home_data.get("percentile"),

            # Simplified hour recommendations (new structure)
            "cheapest_hours": self._home_data.get("cheapest_hours", []),
            "most_expensive_hours": self._home_data.get("most_expensive_hours", []),
            "next_cheap_window": self._home_data.get("next_cheap_window"),

            # Best consecutive time window
            "best_3h_window": self._home_data.get("best_3h_window"),
        }


class TibberAveragePriceSensor(TibberSensorBase):
    """Sensor for average price today."""

    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "EUR/kWh"

    def __init__(self, coordinator: TibberDataUpdateCoordinator, home_id: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, home_id, "average_price")

    @property
    def native_value(self) -> float | None:
        """Return the average price."""
        if self._home_data:
            return round(self._home_data["average_price"], 4)
        return None


class TibberMinPriceSensor(TibberSensorBase):
    """Sensor for minimum price today."""

    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "EUR/kWh"

    def __init__(self, coordinator: TibberDataUpdateCoordinator, home_id: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, home_id, "min_price")

    @property
    def native_value(self) -> float | None:
        """Return the minimum price."""
        if self._home_data:
            return round(self._home_data["min_price"], 4)
        return None


class TibberMaxPriceSensor(TibberSensorBase):
    """Sensor for maximum price today."""

    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "EUR/kWh"

    def __init__(self, coordinator: TibberDataUpdateCoordinator, home_id: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, home_id, "max_price")

    @property
    def native_value(self) -> float | None:
        """Return the maximum price."""
        if self._home_data:
            return round(self._home_data["max_price"], 4)
        return None


class TibberPriceLevelSensor(TibberSensorBase):
    """Sensor for current price level."""

    def __init__(self, coordinator: TibberDataUpdateCoordinator, home_id: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, home_id, "price_level")

    @property
    def native_value(self) -> str | None:
        """Return the current price level."""
        if self._home_data:
            return self._home_data["current"].get("level")
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

    def __init__(self, coordinator: TibberDataUpdateCoordinator, home_id: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, home_id, "cheapest_hours")

    @property
    def native_value(self) -> str | None:
        """Return cheapest hours as readable string."""
        if not self._home_data or not self._home_data.get("cheapest_hours"):
            return None

        hours = []
        for hour in self._home_data["cheapest_hours"]:
            time_str = hour["start"].split("T")[1][:5]  # Extract HH:MM
            price = hour["price"]
            hours.append(f"{time_str} ({price:.4f}€)")

        return ", ".join(hours)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return detailed hour information with new structure."""
        if not self._home_data:
            return {}

        return {
            "cheapest_hours": self._home_data.get("cheapest_hours", []),
            "next_cheap_window": self._home_data.get("next_cheap_window"),
        }

    @property
    def icon(self) -> str:
        """Return icon."""
        return "mdi:cash-check"


class TibberMostExpensiveHoursSensor(TibberSensorBase):
    """Sensor showing the 3 most expensive hours today."""

    def __init__(self, coordinator: TibberDataUpdateCoordinator, home_id: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, home_id, "most_expensive_hours")

    @property
    def native_value(self) -> str | None:
        """Return most expensive hours as readable string."""
        if (
            not self._home_data
            or not self._home_data.get("most_expensive_hours")
        ):
            return None

        hours = []
        for hour in self._home_data["most_expensive_hours"]:
            time_str = hour["start"].split("T")[1][:5]  # Extract HH:MM
            price = hour["price"]
            hours.append(f"{time_str} ({price:.4f}€)")

        return ", ".join(hours)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return detailed hour information with new structure."""
        if not self._home_data:
            return {}

        return {
            "most_expensive_hours": self._home_data.get("most_expensive_hours", []),
        }

    @property
    def icon(self) -> str:
        """Return icon."""
        return "mdi:alert-octagon"


class TibberBestConsecutiveHoursSensor(TibberSensorBase):
    """Sensor showing the best consecutive hours (cheapest window with configurable duration)."""

    def __init__(self, coordinator: TibberDataUpdateCoordinator, home_id: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, home_id, "best_consecutive_hours")

    @property
    def native_value(self) -> str | None:
        """Return best consecutive hours as readable string."""
        if not self._home_data or not self._home_data.get("best_consecutive_hours"):
            return None

        window = self._home_data["best_consecutive_hours"]
        hours = window.get("hours", [])

        if not hours:
            return None

        # Format as time range with average price
        start_time = hours[0]["start"].split("T")[1][:5]
        end_time = hours[-1]["start"].split("T")[1][:5]
        avg_price = window.get("average_price", 0)
        duration = int(self.coordinator.hours_duration)

        return f"{start_time}-{end_time} ({duration}h, Ø {avg_price:.4f}€)"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return detailed window information."""
        if not self._home_data:
            return {}

        window = self._home_data.get("best_consecutive_hours")
        if not window:
            return {"status": "No window data available"}

        return {
            "best_consecutive_hours": window.get("hours", []),
            "window_start": window.get("window_start"),
            "window_end": window.get("window_end"),
            "average_price": window.get("average_price"),
            "duration_hours": int(self.coordinator.hours_duration),
        }

    @property
    def icon(self) -> str:
        """Return icon."""
        return "mdi:clock-check"


# ============================================================================
# Architecture v2.0 - New Sensors
# ============================================================================


class TibberPriceDeviationPercentSensor(TibberSensorBase):
    """Sensor showing percentage deviation from average price."""

    _attr_native_unit_of_measurement = "%"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: TibberDataUpdateCoordinator, home_id: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, home_id, "price_deviation_percent")

    @property
    def native_value(self) -> float | None:
        """Return percentage deviation from average."""
        if self._home_data:
            return self._home_data.get("deviation_percent")
        return None

    @property
    def icon(self) -> str:
        """Return icon based on deviation."""
        value = self.native_value
        if value is None:
            return "mdi:percent"
        if value < -10:
            return "mdi:arrow-down-bold"
        if value > 10:
            return "mdi:arrow-up-bold"
        return "mdi:minus"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        if not self._home_data:
            return {}

        return {
            "current_price": self._home_data["current"]["total"],
            "average_price": self._home_data["average_price"],
            "deviation_absolute": self._home_data.get("deviation_absolute"),
        }


class TibberPriceDeviationAbsoluteSensor(TibberSensorBase):
    """Sensor showing absolute deviation from average price."""

    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "EUR/kWh"

    def __init__(self, coordinator: TibberDataUpdateCoordinator, home_id: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, home_id, "price_deviation_absolute")

    @property
    def native_value(self) -> float | None:
        """Return absolute deviation from average."""
        if self._home_data:
            return self._home_data.get("deviation_absolute")
        return None

    @property
    def icon(self) -> str:
        """Return icon based on deviation."""
        value = self.native_value
        if value is None:
            return "mdi:delta"
        if value < 0:
            return "mdi:arrow-down-bold-circle"
        if value > 0:
            return "mdi:arrow-up-bold-circle"
        return "mdi:equal"


class TibberBatteryBreakevenPriceSensor(TibberSensorBase):
    """Sensor showing the maximum price at which battery charging is economical."""

    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "EUR/kWh"

    def __init__(
        self, coordinator: TibberDataUpdateCoordinator, home_id: str
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, home_id, "battery_breakeven_price")
        self._attr_name = "Battery Breakeven Price"

    @property
    def native_value(self) -> float | None:
        """Return breakeven price for economical charging."""
        if self._home_data:
            return self._home_data.get("battery_breakeven_price")
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        if not self._home_data:
            return {}

        current_price = self._home_data["current"]["total"]
        breakeven = self._home_data.get("battery_breakeven_price", 0)
        average_price = self._home_data.get("average_price", 0)
        is_below_breakeven = current_price <= breakeven

        return {
            "current_price": current_price,
            "average_price": average_price,
            "battery_efficiency": self._home_data.get("battery_efficiency"),
            "is_below_breakeven": is_below_breakeven,
            "difference_to_breakeven": round(breakeven - current_price, 4),
        }

    @property
    def icon(self) -> str:
        """Return icon based on whether current price is below breakeven."""
        if not self._home_data:
            return "mdi:battery-charging-outline"

        current_price = self._home_data["current"]["total"]
        breakeven = self._home_data.get("battery_breakeven_price", 0)

        if current_price <= breakeven:
            return "mdi:battery-charging-100"
        return "mdi:battery-alert"
