"""Data update coordinator for Tibber Smart Control."""
from datetime import timedelta
import logging
from typing import Any

import aiohttp

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import TIBBER_API_URL

_LOGGER = logging.getLogger(__name__)

GRAPHQL_QUERY = """
{
  viewer {
    homes {
      id
      appNickname
      currentSubscription {
        priceInfo {
          current {
            total
            energy
            tax
            startsAt
            level
          }
          today {
            total
            energy
            tax
            startsAt
            level
          }
          tomorrow {
            total
            energy
            tax
            startsAt
            level
          }
        }
      }
    }
  }
}
"""


class TibberDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching Tibber data."""

    def __init__(
        self,
        hass: HomeAssistant,
        api_key: str,
        update_interval: int = 300,
        battery_efficiency: float = 86,
        hours_duration: int = 3,
    ) -> None:
        """Initialize the coordinator."""
        self.api_key = api_key
        self.battery_efficiency = battery_efficiency
        self.hours_duration = hours_duration
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        super().__init__(
            hass,
            _LOGGER,
            name="Tibber Smart Control",
            update_interval=timedelta(seconds=update_interval),
        )

    async def _async_update_data(self) -> dict[str, dict[str, Any]]:
        """Fetch data from Tibber API for ALL homes."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    TIBBER_API_URL,
                    json={"query": GRAPHQL_QUERY},
                    headers=self.headers,
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    resp.raise_for_status()
                    response = await resp.json()

            if not response or "data" not in response:
                # Keep last valid data on API errors
                if self.data:
                    _LOGGER.warning("Invalid response from Tibber API, keeping last valid data")
                    return self.data
                raise UpdateFailed("Invalid response from Tibber API")

            homes = response["data"]["viewer"]["homes"]

            if not homes:
                # Keep last valid data if no homes found
                if self.data:
                    _LOGGER.warning("No homes found in Tibber API response, keeping last valid data")
                    return self.data
                raise UpdateFailed("No homes found in Tibber account")

            # Process ALL homes
            all_homes_data = {}

            for home_data in homes:
                try:
                    home_id = home_data.get("id")
                    if not home_id:
                        _LOGGER.warning("Home without ID found, skipping")
                        continue

                    # Safe access with None checks
                    current_subscription = home_data.get("currentSubscription")
                    if not current_subscription:
                        _LOGGER.warning(f"Home {home_id} has no currentSubscription, skipping")
                        continue

                    price_info = current_subscription.get("priceInfo")
                    if not price_info:
                        _LOGGER.warning(f"Home {home_id} has no priceInfo, skipping")
                        continue

                    current = price_info.get("current")
                    if not current or "total" not in current:
                        _LOGGER.warning(f"Home {home_id} has no current price, skipping")
                        continue

                    # Calculate statistics for this home
                    today_prices = [p["total"] for p in price_info.get("today", [])]
                    current_price = current["total"]

                    avg_price = sum(today_prices) / len(today_prices) if today_prices else current_price
                    min_price = min(today_prices) if today_prices else current_price
                    max_price = max(today_prices) if today_prices else current_price

                    # Find cheapest and most expensive hours
                    sorted_today = sorted(
                        price_info.get("today", []),
                        key=lambda x: x["total"]
                    )

                    n = int(self.hours_duration)
                    cheapest_hours = sorted_today[:n] if len(sorted_today) >= n else sorted_today
                    expensive_hours = sorted_today[-n:] if len(sorted_today) >= n else sorted_today

                    # Calculate deviation from average
                    deviation_absolute = current_price - avg_price
                    deviation_percent = (deviation_absolute / avg_price * 100) if avg_price > 0 else 0

                    # Calculate rank (1 = cheapest, 24 = most expensive)
                    rank = self._calculate_price_rank(current_price, today_prices)

                    # Calculate percentile (0-100, lower = cheaper)
                    percentile = (rank / len(today_prices) * 100) if today_prices else 50

                    # Simplified cheapest_hours structure with price_level
                    cheapest_hours_simple = [
                        {
                            "start": h["startsAt"],
                            "price": round(h["total"], 4),
                            "price_level": h.get("level", "NORMAL")
                        }
                        for h in cheapest_hours
                    ]
                    expensive_hours_simple = [
                        {
                            "start": h["startsAt"],
                            "price": round(h["total"], 4),
                            "price_level": h.get("level", "NORMAL")
                        }
                        for h in expensive_hours
                    ]

                    # Calculate next cheap window (next time it becomes cheap)
                    next_cheap_window = self._calculate_next_cheap_window(
                        price_info.get("today", []),
                        price_info.get("tomorrow", []),
                        current_price
                    )

                    # Calculate best consecutive window (configurable duration)
                    best_consecutive_hours = self.calculate_best_time_window(
                        duration_hours=int(self.hours_duration),
                        prices=price_info.get("today", [])
                    )

                    # Extract home info for device
                    home_info = {
                        "id": home_id,
                        "name": home_data.get("appNickname") or "Tibber Home",
                    }

                    # Battery charging optimization
                    current_price_val = current["total"]  # Use already validated 'current'
                    battery_efficiency_decimal = self.battery_efficiency / 100

                    # Calculate breakeven price: the maximum price at which charging is economical
                    # Formula: average_price * efficiency (accounting for losses)
                    breakeven_price = (
                        avg_price * battery_efficiency_decimal
                        if battery_efficiency_decimal > 0
                        else avg_price
                    )

                    # Check if current price is below breakeven (economical to charge)
                    battery_is_economical = current_price_val <= breakeven_price

                    all_homes_data[home_id] = {
                        "home": home_info,
                        "current": current,  # Use already validated 'current'
                        "today": price_info.get("today", []),
                        "tomorrow": price_info.get("tomorrow", []),
                        "average_price": avg_price,
                        "min_price": min_price,
                        "max_price": max_price,
                        # Simplified structures
                        "cheapest_hours": cheapest_hours_simple,
                        "most_expensive_hours": expensive_hours_simple,
                        "next_cheap_window": next_cheap_window,
                        # Architecture v2.0 fields
                        "deviation_absolute": round(deviation_absolute, 4),
                        "deviation_percent": round(deviation_percent, 2),
                        "rank": rank,
                        "percentile": round(percentile, 1),
                        # Best consecutive hours window (configurable duration)
                        "best_consecutive_hours": best_consecutive_hours,
                        # Battery charging fields
                        "battery_efficiency": self.battery_efficiency,
                        "battery_breakeven_price": round(breakeven_price, 4),
                        "battery_is_economical": battery_is_economical,
                    }

                    _LOGGER.debug(f"Successfully processed home {home_id}")

                except Exception as err:
                    # Log error but continue with other homes
                    _LOGGER.error(
                        f"Error processing home {home_data.get('id', 'unknown')}: {err}",
                        exc_info=True
                    )
                    # If we have previous data for this home, keep it
                    if self.data and home_data.get("id") in self.data:
                        all_homes_data[home_data.get("id")] = self.data[home_data.get("id")]
                        _LOGGER.info(f"Keeping last valid data for home {home_data.get('id')}")
                    continue

            # If no homes were successfully processed, keep last valid data
            if not all_homes_data:
                if self.data:
                    _LOGGER.warning("No homes could be processed, keeping last valid data")
                    return self.data
                raise UpdateFailed("Failed to process any homes from Tibber API")

            return all_homes_data

        except aiohttp.ClientResponseError as err:
            if err.status in (401, 403):
                raise ConfigEntryAuthFailed(f"Authentication failed: {err}") from err
            # Keep last valid data on HTTP errors
            if self.data:
                _LOGGER.warning(f"HTTP error from Tibber API: {err}, keeping last valid data")
                return self.data
            raise UpdateFailed(f"HTTP error from Tibber API: {err}") from err
        except aiohttp.ClientError as err:
            # Keep last valid data on connection errors (timeout, network issues)
            if self.data:
                _LOGGER.warning(f"Error communicating with Tibber API: {err}, keeping last valid data")
                return self.data
            raise UpdateFailed(f"Error communicating with Tibber API: {err}") from err
        except (KeyError, ValueError) as err:
            # Keep last valid data on parsing errors
            if self.data:
                _LOGGER.warning(f"Error parsing Tibber data: {err}, keeping last valid data")
                return self.data
            raise UpdateFailed(f"Error parsing Tibber data: {err}") from err

    def _calculate_price_rank(self, current_price: float, all_prices: list[float]) -> int:
        """Calculate rank of current price (1 = cheapest, higher = more expensive)."""
        if not all_prices:
            return 1

        sorted_prices = sorted(all_prices)
        try:
            return sorted_prices.index(current_price) + 1
        except ValueError:
            # If current price not in list, find closest position
            for i, price in enumerate(sorted_prices):
                if current_price <= price:
                    return i + 1
            return len(sorted_prices)

    def _calculate_next_cheap_window(
        self,
        today_prices: list[dict],
        tomorrow_prices: list[dict],
        current_price: float,
    ) -> dict[str, Any] | None:
        """
        Calculate the next cheap window (when it becomes cheap next).

        Returns the next hour where price is in top 25% cheapest.
        """
        from datetime import datetime, timedelta, timezone

        if not today_prices:
            return None

        # Combine today and tomorrow
        all_prices = today_prices + tomorrow_prices

        # Find top 25% cheapest prices
        sorted_prices = sorted([p["total"] for p in all_prices])
        threshold_index = max(1, len(sorted_prices) // 4)
        cheap_threshold = sorted_prices[threshold_index - 1]

        # Find next hour that is cheap - use timezone-aware datetime
        now = datetime.now(timezone.utc)

        for price_data in all_prices:
            hour_time = datetime.fromisoformat(price_data["startsAt"].replace("Z", "+00:00"))

            # Skip past hours
            if hour_time <= now:
                continue

            # Check if this hour is cheap
            if price_data["total"] <= cheap_threshold:
                end_time = hour_time + timedelta(hours=1)

                return {
                    "start": price_data["startsAt"],
                    "end": end_time.isoformat(),
                    "mean_price": round(price_data["total"], 4),
                    "price_level": price_data.get("level", "NORMAL"),
                }

        return None

    def calculate_best_time_window(
        self,
        duration_hours: int,
        prices: list[dict],
        start_after: str | None = None,
        end_before: str | None = None,
    ) -> dict[str, Any]:
        """
        Find the cheapest consecutive N-hour window.

        Args:
            duration_hours: Number of consecutive hours needed
            prices: List of price dictionaries with 'total' and 'startsAt'
            start_after: Optional HH:MM format, don't start before this time
            end_before: Optional HH:MM format, must end before this time

        Returns:
            Dictionary with best window info (always returns a result if prices exist)
        """
        # Default empty result if no prices
        if not prices or duration_hours <= 0 or len(prices) < duration_hours:
            return {
                "hours": [],
                "window_start": None,
                "window_end": None,
                "average_price": 0,
            }

        windows = []

        for i in range(len(prices) - duration_hours + 1):
            window = prices[i:i + duration_hours]

            # Check time constraints if provided
            if start_after or end_before:
                start_time = window[0]["startsAt"].split("T")[1][:5]
                end_time = window[-1]["startsAt"].split("T")[1][:5]

                if start_after and start_time < start_after:
                    continue
                if end_before and end_time >= end_before:
                    continue

            avg_price = sum(p["total"] for p in window) / duration_hours

            windows.append({
                "window": window,
                "average_price": round(avg_price, 4),
            })

        # If no valid windows due to constraints, use first available window
        if not windows:
            window = prices[:duration_hours]
            avg_price = sum(p["total"] for p in window) / duration_hours
            windows.append({
                "window": window,
                "average_price": round(avg_price, 4),
            })

        # Get window with lowest average price
        best = sorted(windows, key=lambda x: x["average_price"])[0]
        window_prices = best["window"]

        # Build simplified structure like cheapest_hours with price_level
        from datetime import datetime, timedelta

        hours = [
            {
                "start": p["startsAt"],
                "price": round(p["total"], 4),
                "price_level": p.get("level", "NORMAL")
            }
            for p in window_prices
        ]

        # Calculate end time (3 hours after start)
        start_dt = datetime.fromisoformat(window_prices[0]["startsAt"].replace("Z", "+00:00"))
        end_dt = start_dt + timedelta(hours=duration_hours)

        return {
            "hours": hours,
            "window_start": window_prices[0]["startsAt"],
            "window_end": end_dt.isoformat(),
            "average_price": best["average_price"],
        }
