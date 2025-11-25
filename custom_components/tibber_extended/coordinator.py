"""Data update coordinator for Tibber Smart Control."""
from datetime import datetime, timedelta, timezone
import logging
import re
from typing import Any

import aiohttp

from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.event import async_track_time_change
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
        time_window_start: str = "00:00",
        time_window_end: str = "23:59",
    ) -> None:
        """Initialize the coordinator."""
        self.api_key = api_key
        self.battery_efficiency = battery_efficiency
        self.hours_duration = hours_duration
        self.time_window_start = time_window_start
        self.time_window_end = time_window_end
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        self._hourly_unsub: callable | None = None

        # Use longer backup interval (1 hour) since we trigger at full hour
        # This serves as a safety net in case hourly trigger is missed
        super().__init__(
            hass,
            _LOGGER,
            name="Tibber Smart Control",
            update_interval=timedelta(hours=1),
        )

    async def async_setup_hourly_refresh(self) -> None:
        """Set up hourly refresh at the top of each hour."""
        # Cancel existing subscription if any
        if self._hourly_unsub:
            self._hourly_unsub()

        @callback
        def _hourly_refresh(now: datetime) -> None:
            """Trigger refresh at the top of each hour."""
            _LOGGER.debug("Hourly refresh triggered at %s", now)
            self.hass.async_create_task(self.async_request_refresh())

        # Schedule refresh at minute=0, second=5 of every hour
        # Using second=5 to give Tibber API time to update after hour change
        self._hourly_unsub = async_track_time_change(
            self.hass,
            _hourly_refresh,
            minute=0,
            second=5,
        )
        _LOGGER.info("Hourly refresh scheduled at XX:00:05")

    async def async_shutdown(self) -> None:
        """Shut down the coordinator."""
        if self._hourly_unsub:
            self._hourly_unsub()
            self._hourly_unsub = None
        await super().async_shutdown()

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
                    app_nickname = home_data.get("appNickname") or "home"

                    # Create a clean slug for entity IDs from appNickname
                    # Remove special chars, convert to lowercase, replace spaces with underscore
                    slug = re.sub(r'[^a-z0-9]+', '_', app_nickname.lower()).strip('_')
                    # Keep pure numbers as-is (like "27"), don't add home_ prefix
                    if not slug:
                        slug = "home"

                    home_info = {
                        "id": home_id,
                        "name": app_nickname,
                        "slug": slug,  # Clean identifier for entity IDs
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
                        # Time window cheapest hours
                        "time_window_cheapest_hours": self._calculate_time_window_cheapest_hours(
                            prices=price_info.get("today", []) + price_info.get("tomorrow", []),
                            time_window_start=self.time_window_start,
                            time_window_end=self.time_window_end,
                            hours_count=int(self.hours_duration),
                        ),
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

    def _calculate_time_window_cheapest_hours(
        self,
        prices: list[dict],
        time_window_start: str,
        time_window_end: str,
        hours_count: int,
    ) -> list[dict[str, Any]]:
        """
        Find the cheapest N hours within a specific time window.

        Args:
            prices: List of price dictionaries with 'total' and 'startsAt'
            time_window_start: Start time in HH:MM format
            time_window_end: End time in HH:MM format
            hours_count: Number of cheapest hours to find

        Returns:
            List of cheapest hours in the time window (sorted by price)
        """
        if not prices or hours_count <= 0:
            return []

        # Filter prices within the time window
        filtered_prices = []

        # Parse window times
        start_hour, start_minute = map(int, time_window_start.split(':'))
        end_hour, end_minute = map(int, time_window_end.split(':'))

        # Check if window spans midnight
        spans_midnight = (end_hour < start_hour) or (end_hour == start_hour and end_minute < start_minute)

        for price_data in prices:
            # Parse the timestamp
            hour_time = datetime.fromisoformat(price_data["startsAt"].replace("Z", "+00:00"))
            hour = hour_time.hour
            minute = hour_time.minute

            # Check if this hour is within the time window
            in_window = False

            if spans_midnight:
                # Window like 17:00-07:00 (crosses midnight)
                # Include if >= start OR <= end
                if (hour > start_hour or (hour == start_hour and minute >= start_minute)):
                    in_window = True
                elif (hour < end_hour or (hour == end_hour and minute < end_minute)):
                    in_window = True
            else:
                # Window like 08:00-16:00 (same day)
                # Include if >= start AND < end
                if (hour > start_hour or (hour == start_hour and minute >= start_minute)):
                    if (hour < end_hour or (hour == end_hour and minute < end_minute)):
                        in_window = True

            if in_window:
                filtered_prices.append(price_data)

        # If no prices in window or window matches all day, use all prices
        if not filtered_prices or (time_window_start == "00:00" and time_window_end == "23:59"):
            filtered_prices = prices

        # Sort by price and get the cheapest N hours
        sorted_prices = sorted(filtered_prices, key=lambda x: x["total"])
        cheapest = sorted_prices[:hours_count] if len(sorted_prices) >= hours_count else sorted_prices

        # Return in simplified format like cheapest_hours
        return [
            {
                "start": p["startsAt"],
                "price": round(p["total"], 4),
                "price_level": p.get("level", "NORMAL"),
            }
            for p in cheapest
        ]
