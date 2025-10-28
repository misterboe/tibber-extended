"""Dynamic sensors for time window optimization."""
from __future__ import annotations

from datetime import datetime, timedelta
import logging
from typing import Any

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.util import dt as dt_util

from .coordinator import TibberDataUpdateCoordinator
from .entity import TibberEntityBase

_LOGGER = logging.getLogger(__name__)


class TibberBestStartTimeSensor(TibberEntityBase, SensorEntity):
    """Sensor showing optimal start time for a time window."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(
        self,
        coordinator: TibberDataUpdateCoordinator,
        home_id: str,
        window_name: str,
        duration_hours: float,
        power_kw: float | None = None,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, home_id, f"best_start_{window_name}")
        self._window_name = window_name
        self._duration_hours = duration_hours
        self._power_kw = power_kw

    @property
    def native_value(self) -> datetime | None:
        """Return optimal start time as timestamp."""
        if not self._home_data:
            return None

        # Get best window
        best_window = self._calculate_best_window()
        if not best_window:
            return None

        # Parse start time
        try:
            start_time_str = best_window["start_time"]
            return dt_util.parse_datetime(start_time_str)
        except (KeyError, ValueError, TypeError):
            return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        if not self._home_data:
            return {}

        best_window = self._calculate_best_window()
        if not best_window:
            return {"window_name": self._window_name}

        # Calculate savings
        avg_price_today = self._home_data.get("average_price", 0)
        window_avg_price = best_window["average_price"]
        savings_percent = (
            ((avg_price_today - window_avg_price) / avg_price_today * 100)
            if avg_price_today > 0
            else 0
        )

        # Calculate total cost if power is specified
        total_cost = None
        if self._power_kw:
            total_cost = round(
                self._duration_hours * self._power_kw * window_avg_price, 4
            )

        # Build price breakdown
        price_breakdown = []
        for price_data in best_window.get("prices", []):
            time_str = price_data["startsAt"].split("T")[1][:5]
            price_breakdown.append({
                "time": time_str,
                "price": round(price_data["total"], 4),
                "level": price_data.get("level"),
            })

        return {
            "window_name": self._window_name,
            "duration_hours": self._duration_hours,
            "power_kw": self._power_kw,
            "end_time": best_window.get("end_time"),
            "average_price_window": round(window_avg_price, 4),
            "total_cost": total_cost,
            "savings_vs_average_percent": round(savings_percent, 2),
            "price_breakdown": price_breakdown,
            "is_current_time_optimal": self._is_current_time_optimal(best_window),
        }

    def _calculate_best_window(self) -> dict[str, Any] | None:
        """Calculate best time window for this configuration."""
        if not self._home_data:
            return None

        today_prices = self._home_data.get("today", [])
        tomorrow_prices = self._home_data.get("tomorrow", [])

        # Combine today and tomorrow
        all_prices = today_prices + tomorrow_prices

        if not all_prices:
            return None

        # Use coordinator's window calculation
        return self.coordinator.calculate_best_time_window(
            duration_hours=int(self._duration_hours),
            prices=all_prices,
        )

    def _is_current_time_optimal(self, best_window: dict) -> bool:
        """Check if current time is the optimal start time."""
        if not best_window or not self._home_data:
            return False

        current_time = self._home_data["current"].get("startsAt")
        best_start = best_window.get("start_time")

        return current_time == best_start

    @property
    def icon(self) -> str:
        """Return icon."""
        if self._is_current_time_optimal(self._calculate_best_window() or {}):
            return "mdi:clock-start"
        return "mdi:clock-outline"


class TibberOptimalStartBinarySensor(TibberEntityBase, BinarySensorEntity):
    """Binary sensor indicating if NOW is optimal start time."""

    def __init__(
        self,
        coordinator: TibberDataUpdateCoordinator,
        home_id: str,
        window_name: str,
        duration_hours: float,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, home_id, f"optimal_start_{window_name}")
        self._window_name = window_name
        self._duration_hours = duration_hours

    @property
    def is_on(self) -> bool:
        """Return true if NOW is optimal start time."""
        if not self._home_data:
            return False

        best_window = self._calculate_best_window()
        if not best_window:
            return False

        current_time = self._home_data["current"].get("startsAt")
        best_start = best_window.get("start_time")

        return current_time == best_start

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        if not self._home_data:
            return {}

        best_window = self._calculate_best_window()
        if not best_window:
            return {"window_name": self._window_name}

        return {
            "window_name": self._window_name,
            "duration_hours": self._duration_hours,
            "best_start_time": best_window.get("start_time"),
            "average_price_window": round(best_window["average_price"], 4),
        }

    def _calculate_best_window(self) -> dict[str, Any] | None:
        """Calculate best time window."""
        if not self._home_data:
            return None

        today_prices = self._home_data.get("today", [])
        tomorrow_prices = self._home_data.get("tomorrow", [])
        all_prices = today_prices + tomorrow_prices

        if not all_prices:
            return None

        return self.coordinator.calculate_best_time_window(
            duration_hours=int(self._duration_hours),
            prices=all_prices,
        )

    @property
    def icon(self) -> str:
        """Return icon."""
        return "mdi:play-circle" if self.is_on else "mdi:play-circle-outline"


class TibberInOptimalWindowBinarySensor(TibberEntityBase, BinarySensorEntity):
    """Binary sensor indicating if we are WITHIN optimal window."""

    def __init__(
        self,
        coordinator: TibberDataUpdateCoordinator,
        home_id: str,
        window_name: str,
        duration_hours: float,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, home_id, f"in_optimal_window_{window_name}")
        self._window_name = window_name
        self._duration_hours = duration_hours

    @property
    def is_on(self) -> bool:
        """Return true if we are within optimal window."""
        if not self._home_data:
            return False

        best_window = self._calculate_best_window()
        if not best_window:
            return False

        # Parse times
        try:
            current_time_str = self._home_data["current"].get("startsAt")
            window_start_str = best_window["start_time"]
            window_end_str = best_window["end_time"]

            current_time = dt_util.parse_datetime(current_time_str)
            window_start = dt_util.parse_datetime(window_start_str)
            window_end = dt_util.parse_datetime(window_end_str)

            if not all([current_time, window_start, window_end]):
                return False

            # Add duration to end time (since end_time is start of last hour)
            window_end_actual = window_end + timedelta(hours=1)

            # Check if current time is within window
            return window_start <= current_time < window_end_actual

        except (KeyError, ValueError, TypeError):
            return False

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        if not self._home_data:
            return {}

        best_window = self._calculate_best_window()
        if not best_window:
            return {"window_name": self._window_name}

        # Calculate minutes remaining if in window
        minutes_remaining = None
        if self.is_on:
            try:
                current_time_str = self._home_data["current"].get("startsAt")
                window_end_str = best_window["end_time"]

                current_time = dt_util.parse_datetime(current_time_str)
                window_end = dt_util.parse_datetime(window_end_str)

                if current_time and window_end:
                    # Add duration + 1 hour to get actual end
                    window_end_actual = window_end + timedelta(hours=1)
                    remaining = window_end_actual - current_time
                    minutes_remaining = int(remaining.total_seconds() / 60)

            except (KeyError, ValueError, TypeError):
                pass

        return {
            "window_name": self._window_name,
            "duration_hours": self._duration_hours,
            "window_start_time": best_window.get("start_time"),
            "window_end_time": best_window.get("end_time"),
            "minutes_remaining": minutes_remaining,
            "average_price_window": round(best_window["average_price"], 4),
        }

    def _calculate_best_window(self) -> dict[str, Any] | None:
        """Calculate best time window."""
        if not self._home_data:
            return None

        today_prices = self._home_data.get("today", [])
        tomorrow_prices = self._home_data.get("tomorrow", [])
        all_prices = today_prices + tomorrow_prices

        if not all_prices:
            return None

        return self.coordinator.calculate_best_time_window(
            duration_hours=int(self._duration_hours),
            prices=all_prices,
        )

    @property
    def icon(self) -> str:
        """Return icon."""
        return "mdi:timer" if self.is_on else "mdi:timer-outline"
