"""Services for Tibber Extended integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse, SupportsResponse
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN
from .coordinator import TibberDataUpdateCoordinator
from .time_window import TimeWindowManager

_LOGGER = logging.getLogger(__name__)

# Service schemas
SERVICE_CALCULATE_BEST_TIME_WINDOW_SCHEMA = vol.Schema(
    {
        vol.Required("duration_hours"): vol.All(vol.Coerce(int), vol.Range(min=1, max=24)),
        vol.Optional("power_kw"): vol.All(vol.Coerce(float), vol.Range(min=0.1, max=50.0)),
        vol.Optional("start_after"): cv.string,  # HH:MM format
        vol.Optional("end_before"): cv.string,   # HH:MM format
        vol.Optional("include_tomorrow", default=False): cv.boolean,
    }
)

SERVICE_ADD_TIME_WINDOW_SCHEMA = vol.Schema(
    {
        vol.Required("name"): cv.string,
        vol.Required("duration"): vol.All(vol.Coerce(float), vol.Range(min=0.5, max=24.0)),
        vol.Optional("power_kw"): vol.All(vol.Coerce(float), vol.Range(min=0.1, max=50.0)),
    }
)

SERVICE_REMOVE_TIME_WINDOW_SCHEMA = vol.Schema(
    {
        vol.Required("name"): cv.string,
    }
)

SERVICE_GET_PRICE_FORECAST_SCHEMA = vol.Schema(
    {
        vol.Optional("hours_ahead"): vol.All(vol.Coerce(int), vol.Range(min=1, max=48)),
    }
)


async def async_setup_services(
    hass: HomeAssistant,
    coordinator: TibberDataUpdateCoordinator,
    window_manager: TimeWindowManager,
) -> None:
    """Set up services for Tibber Extended."""

    async def calculate_best_time_window(call: ServiceCall) -> ServiceResponse:
        """Service to calculate best time window."""
        duration_hours = call.data["duration_hours"]
        power_kw = call.data.get("power_kw")
        start_after = call.data.get("start_after")
        end_before = call.data.get("end_before")
        include_tomorrow = call.data.get("include_tomorrow", False)

        # Get first available coordinator data
        if not coordinator.data:
            return {
                "error": "No data available",
                "success": False,
            }

        home_id = list(coordinator.data.keys())[0]
        home_data = coordinator.data[home_id]

        # Build price list
        prices = home_data.get("today", [])
        if include_tomorrow:
            prices += home_data.get("tomorrow", [])

        if not prices:
            return {
                "error": "No price data available",
                "success": False,
            }

        # Calculate best window
        best_window = coordinator.calculate_best_time_window(
            duration_hours=duration_hours,
            prices=prices,
            start_after=start_after,
            end_before=end_before,
        )

        if not best_window:
            return {
                "error": "Could not find suitable time window",
                "success": False,
            }

        # Build response
        avg_price_today = home_data.get("average_price", 0)
        window_avg_price = best_window["average_price"]

        savings_vs_average = 0
        total_cost = None

        if avg_price_today > 0:
            savings_vs_average = round(
                (avg_price_today - window_avg_price) * duration_hours,
                4
            )

        if power_kw:
            total_cost = round(duration_hours * power_kw * window_avg_price, 4)

        # Build price breakdown
        price_breakdown = []
        for price_data in best_window.get("prices", []):
            time_str = price_data["startsAt"].split("T")[1][:5]
            price_breakdown.append({
                "start": time_str,
                "price": round(price_data["total"], 4),
                "level": price_data.get("level"),
            })

        return {
            "success": True,
            "best_start_time": best_window["start_time"],
            "best_end_time": best_window["end_time"],
            "duration_hours": duration_hours,
            "average_price_window": round(window_avg_price, 4),
            "total_cost": total_cost,
            "savings_vs_average": savings_vs_average,
            "price_breakdown": price_breakdown,
        }

    async def add_time_window(call: ServiceCall) -> ServiceResponse:
        """Service to add a time window."""
        name = call.data["name"].strip().lower().replace(" ", "_")
        duration = call.data["duration"]
        power_kw = call.data.get("power_kw")

        success = await window_manager.add_window(
            name=name,
            duration=duration,
            power_kw=power_kw,
        )

        if success:
            return {
                "success": True,
                "message": f"Time window '{name}' added successfully",
                "window": {
                    "name": name,
                    "duration_hours": duration,
                    "power_kw": power_kw,
                },
            }
        else:
            return {
                "success": False,
                "error": f"Window '{name}' already exists or invalid name",
            }

    async def remove_time_window(call: ServiceCall) -> ServiceResponse:
        """Service to remove a time window."""
        name = call.data["name"]

        success = await window_manager.remove_window(name)

        if success:
            return {
                "success": True,
                "message": f"Time window '{name}' removed successfully",
            }
        else:
            return {
                "success": False,
                "error": f"Window '{name}' does not exist",
            }

    async def get_price_forecast(call: ServiceCall) -> ServiceResponse:
        """Service to get price forecast."""
        hours_ahead = call.data.get("hours_ahead")

        # Get first available coordinator data
        if not coordinator.data:
            return {
                "error": "No data available",
                "success": False,
            }

        home_id = list(coordinator.data.keys())[0]
        home_data = coordinator.data[home_id]

        # Build price list
        prices = home_data.get("today", []) + home_data.get("tomorrow", [])

        if not prices:
            return {
                "error": "No price data available",
                "success": False,
            }

        # Limit to hours_ahead if specified
        if hours_ahead:
            prices = prices[:hours_ahead]

        # Build structured response
        forecast = []
        avg_price = home_data.get("average_price", 0)

        for price_data in prices:
            price = price_data["total"]
            deviation_percent = (
                ((price - avg_price) / avg_price * 100) if avg_price > 0 else 0
            )

            forecast.append({
                "time": price_data["startsAt"],
                "price": round(price, 4),
                "level": price_data.get("level"),
                "deviation_percent": round(deviation_percent, 2),
                "energy": price_data.get("energy"),
                "tax": price_data.get("tax"),
            })

        return {
            "success": True,
            "average_price_today": round(avg_price, 4),
            "forecast": forecast,
        }

    # Register services
    hass.services.async_register(
        DOMAIN,
        "calculate_best_time_window",
        calculate_best_time_window,
        schema=SERVICE_CALCULATE_BEST_TIME_WINDOW_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )

    hass.services.async_register(
        DOMAIN,
        "add_time_window",
        add_time_window,
        schema=SERVICE_ADD_TIME_WINDOW_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )

    hass.services.async_register(
        DOMAIN,
        "remove_time_window",
        remove_time_window,
        schema=SERVICE_REMOVE_TIME_WINDOW_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )

    hass.services.async_register(
        DOMAIN,
        "get_price_forecast",
        get_price_forecast,
        schema=SERVICE_GET_PRICE_FORECAST_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )

    _LOGGER.info("Tibber Extended services registered")
