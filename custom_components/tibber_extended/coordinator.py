"""Data update coordinator for Tibber Smart Control."""
import asyncio
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
        self._last_successful_fetch: datetime | None = None
        self._using_cached_data: bool = False

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

    async def _fetch_with_retry(self, max_retries: int = 3) -> dict | None:
        """Fetch data from Tibber API with retry logic.

        Args:
            max_retries: Maximum number of retry attempts (default: 3)

        Returns:
            API response dict or None if all retries failed
        """
        last_error = None

        for attempt in range(max_retries):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        TIBBER_API_URL,
                        json={"query": GRAPHQL_QUERY},
                        headers=self.headers,
                        timeout=aiohttp.ClientTimeout(total=30),
                    ) as resp:
                        resp.raise_for_status()
                        return await resp.json()

            except (aiohttp.ClientError, asyncio.TimeoutError) as err:
                last_error = err
                if attempt < max_retries - 1:
                    # Exponential backoff: 1s, 2s, 4s
                    wait_time = 2 ** attempt
                    _LOGGER.warning(
                        f"Tibber API request failed (attempt {attempt + 1}/{max_retries}): {err}. "
                        f"Retrying in {wait_time}s..."
                    )
                    await asyncio.sleep(wait_time)
                else:
                    _LOGGER.warning(
                        f"Tibber API request failed after {max_retries} attempts: {err}"
                    )

        # All retries failed
        raise last_error if last_error else aiohttp.ClientError("Unknown error")

    async def _async_update_data(self) -> dict[str, dict[str, Any]]:
        """Fetch data from Tibber API for ALL homes."""
        try:
            response = await self._fetch_with_retry(max_retries=3)

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
                    self._using_cached_data = True
                    return self.data
                raise UpdateFailed("Failed to process any homes from Tibber API")

            # Success! Update tracking variables
            self._last_successful_fetch = datetime.now(timezone.utc)
            self._using_cached_data = False
            return all_homes_data

        except aiohttp.ClientResponseError as err:
            if err.status in (401, 403):
                raise ConfigEntryAuthFailed(f"Authentication failed: {err}") from err
            # Keep last valid data on HTTP errors
            if self.data:
                _LOGGER.warning(f"HTTP error from Tibber API: {err}, keeping last valid data")
                self._using_cached_data = True
                return self.data
            raise UpdateFailed(f"HTTP error from Tibber API: {err}") from err
        except asyncio.TimeoutError as err:
            # Keep last valid data on timeout (critical fix for sensor unavailability)
            if self.data:
                _LOGGER.warning("Timeout connecting to Tibber API, keeping last valid data")
                self._using_cached_data = True
                return self.data
            raise UpdateFailed("Timeout connecting to Tibber API") from err
        except aiohttp.ClientError as err:
            # Keep last valid data on connection errors (timeout, network issues)
            if self.data:
                _LOGGER.warning(f"Error communicating with Tibber API: {err}, keeping last valid data")
                self._using_cached_data = True
                return self.data
            raise UpdateFailed(f"Error communicating with Tibber API: {err}") from err
        except (KeyError, ValueError) as err:
            # Keep last valid data on parsing errors
            if self.data:
                _LOGGER.warning(f"Error parsing Tibber data: {err}, keeping last valid data")
                self._using_cached_data = True
                return self.data
            raise UpdateFailed(f"Error parsing Tibber data: {err}") from err
        except Exception as err:
            # Catch-all: keep last valid data on any unexpected error
            if self.data:
                _LOGGER.error(f"Unexpected error from Tibber API: {err}, keeping last valid data", exc_info=True)
                self._using_cached_data = True
                return self.data
            raise UpdateFailed(f"Unexpected error from Tibber API: {err}") from err

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

    # ==========================================================================
    # Time Window Helper Functions
    # ==========================================================================

    def _parse_tibber_timestamp(self, timestamp: str) -> datetime:
        """Parse Tibber API timestamp to timezone-aware datetime.

        Args:
            timestamp: ISO format timestamp from Tibber API

        Returns:
            Timezone-aware datetime object
        """
        return datetime.fromisoformat(timestamp.replace("Z", "+00:00"))

    def _parse_time_window(
        self, window_start: str, window_end: str
    ) -> tuple[int, int, int, int, bool]:
        """Parse time window and determine if it spans midnight.

        Args:
            window_start: Start time in HH:MM format
            window_end: End time in HH:MM format

        Returns:
            Tuple of (start_hour, start_minute, end_hour, end_minute, spans_midnight)
        """
        # Validate and parse with fallback
        time_pattern = re.compile(r'^([01]\d|2[0-3]):([0-5]\d)$')

        if not time_pattern.match(window_start):
            _LOGGER.warning(f"Invalid time_window_start format: {window_start}, using 00:00")
            start_hour, start_minute = 0, 0
        else:
            start_hour, start_minute = map(int, window_start.split(':'))

        if not time_pattern.match(window_end):
            _LOGGER.warning(f"Invalid time_window_end format: {window_end}, using 23:59")
            end_hour, end_minute = 23, 59
        else:
            end_hour, end_minute = map(int, window_end.split(':'))

        # Check if window spans midnight (e.g., 17:00-07:00)
        spans_midnight = (end_hour < start_hour) or (
            end_hour == start_hour and end_minute < start_minute
        )

        return start_hour, start_minute, end_hour, end_minute, spans_midnight

    def _is_time_in_window(
        self,
        hour: int,
        minute: int,
        start_hour: int,
        start_minute: int,
        end_hour: int,
        end_minute: int,
        spans_midnight: bool,
    ) -> bool:
        """Check if a time is within a time window.

        Args:
            hour: Hour to check (0-23)
            minute: Minute to check (0-59)
            start_hour, start_minute: Window start time
            end_hour, end_minute: Window end time
            spans_midnight: True if window crosses midnight

        Returns:
            True if time is within the window
        """
        if spans_midnight:
            # Window like 17:00-07:00 (crosses midnight)
            # Include if >= start OR < end
            in_evening = hour > start_hour or (hour == start_hour and minute >= start_minute)
            in_morning = hour < end_hour or (hour == end_hour and minute < end_minute)
            return in_evening or in_morning
        else:
            # Window like 08:00-16:00 (same day)
            # Include if >= start AND < end
            after_start = hour > start_hour or (hour == start_hour and minute >= start_minute)
            before_end = hour < end_hour or (hour == end_hour and minute < end_minute)
            return after_start and before_end

    def _get_active_window_boundaries(
        self,
        now: datetime,
        start_hour: int,
        start_minute: int,
        end_hour: int,
        end_minute: int,
        spans_midnight: bool,
    ) -> tuple[datetime, datetime]:
        """Calculate the datetime boundaries of the active time window.

        For overnight windows (e.g., 17:00-07:00), determines whether we're
        currently IN a window (use current window) or OUTSIDE (use next window).

        Args:
            now: Current datetime (timezone-aware)
            start_hour, start_minute: Window start time
            end_hour, end_minute: Window end time
            spans_midnight: True if window crosses midnight

        Returns:
            Tuple of (window_start_datetime, window_end_datetime)
        """
        today = now.date()
        tz = now.tzinfo

        if spans_midnight:
            # Overnight window (e.g., 17:00-07:00)
            current_hour = now.hour
            current_minute = now.minute

            # Check which part of the window we're in (or if we're outside)
            in_evening = current_hour > start_hour or (
                current_hour == start_hour and current_minute >= start_minute
            )
            in_morning = current_hour < end_hour or (
                current_hour == end_hour and current_minute < end_minute
            )

            if in_evening:
                # We're in evening part: Window is TODAY start → TOMORROW end
                window_start = datetime(
                    today.year, today.month, today.day,
                    start_hour, start_minute, tzinfo=tz
                )
                tomorrow = today + timedelta(days=1)
                window_end = datetime(
                    tomorrow.year, tomorrow.month, tomorrow.day,
                    end_hour, end_minute, tzinfo=tz
                )
            elif in_morning:
                # We're in morning part: Window is YESTERDAY start → TODAY end
                yesterday = today - timedelta(days=1)
                window_start = datetime(
                    yesterday.year, yesterday.month, yesterday.day,
                    start_hour, start_minute, tzinfo=tz
                )
                window_end = datetime(
                    today.year, today.month, today.day,
                    end_hour, end_minute, tzinfo=tz
                )
            else:
                # We're outside the window (between end and start)
                # Use the NEXT upcoming window: TODAY start → TOMORROW end
                window_start = datetime(
                    today.year, today.month, today.day,
                    start_hour, start_minute, tzinfo=tz
                )
                tomorrow = today + timedelta(days=1)
                window_end = datetime(
                    tomorrow.year, tomorrow.month, tomorrow.day,
                    end_hour, end_minute, tzinfo=tz
                )
        else:
            # Same-day window (e.g., 08:00-16:00)
            current_hour = now.hour
            current_minute = now.minute

            # Check if we're past today's window end
            past_end = current_hour > end_hour or (
                current_hour == end_hour and current_minute >= end_minute
            )

            if past_end:
                # Use tomorrow's window
                tomorrow = today + timedelta(days=1)
                window_start = datetime(
                    tomorrow.year, tomorrow.month, tomorrow.day,
                    start_hour, start_minute, tzinfo=tz
                )
                window_end = datetime(
                    tomorrow.year, tomorrow.month, tomorrow.day,
                    end_hour, end_minute, tzinfo=tz
                )
            else:
                # Use today's window
                window_start = datetime(
                    today.year, today.month, today.day,
                    start_hour, start_minute, tzinfo=tz
                )
                window_end = datetime(
                    today.year, today.month, today.day,
                    end_hour, end_minute, tzinfo=tz
                )

        return window_start, window_end

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
            try:
                hour_time = self._parse_tibber_timestamp(price_data["startsAt"])
            except (ValueError, KeyError):
                continue

            # Skip past hours
            if hour_time <= now:
                continue

            # Check if this hour is cheap
            if price_data["total"] <= cheap_threshold:
                end_time = hour_time + timedelta(hours=1)

                return {
                    "start": price_data["startsAt"],
                    "end": end_time.isoformat(),
                    "average_price": round(price_data["total"], 4),
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

        # Parse time constraints if provided (supports overnight windows)
        constraint_params = None
        if start_after and end_before:
            constraint_params = self._parse_time_window(start_after, end_before)

        windows = []

        for i in range(len(prices) - duration_hours + 1):
            window = prices[i:i + duration_hours]

            # Check time constraints if provided
            if constraint_params:
                start_h, start_m, end_h, end_m, spans_midnight = constraint_params

                try:
                    # Get the hour of the first price in this window
                    first_hour_time = self._parse_tibber_timestamp(window[0]["startsAt"])
                    # Get the hour of the last price in this window
                    last_hour_time = self._parse_tibber_timestamp(window[-1]["startsAt"])

                    # Check if window start is within the time constraint
                    start_in_window = self._is_time_in_window(
                        first_hour_time.hour, first_hour_time.minute,
                        start_h, start_m, end_h, end_m, spans_midnight
                    )
                    # Check if window end is within the time constraint
                    end_in_window = self._is_time_in_window(
                        last_hour_time.hour, last_hour_time.minute,
                        start_h, start_m, end_h, end_m, spans_midnight
                    )

                    # Both start and end must be within constraints
                    if not (start_in_window and end_in_window):
                        continue
                except (ValueError, KeyError):
                    continue
            elif start_after or end_before:
                # Fallback for single constraint (legacy behavior)
                try:
                    first_hour_time = self._parse_tibber_timestamp(window[0]["startsAt"])
                    last_hour_time = self._parse_tibber_timestamp(window[-1]["startsAt"])

                    if start_after:
                        start_h, start_m = map(int, start_after.split(':'))
                        if first_hour_time.hour < start_h or (
                            first_hour_time.hour == start_h and first_hour_time.minute < start_m
                        ):
                            continue
                    if end_before:
                        end_h, end_m = map(int, end_before.split(':'))
                        if last_hour_time.hour > end_h or (
                            last_hour_time.hour == end_h and last_hour_time.minute >= end_m
                        ):
                            continue
                except (ValueError, KeyError):
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

        # Calculate end time
        try:
            start_dt = self._parse_tibber_timestamp(window_prices[0]["startsAt"])
            end_dt = start_dt + timedelta(hours=duration_hours)
        except (ValueError, KeyError):
            return {
                "hours": hours,
                "window_start": window_prices[0]["startsAt"] if window_prices else None,
                "window_end": None,
                "average_price": best["average_price"],
            }

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
        Find the cheapest N hours within the CURRENT or NEXT active time window.

        This function calculates the actual datetime boundaries of the active window
        based on the current time, then filters prices to only include hours within
        that specific window instance. This prevents mixing hours from different
        window instances (e.g., mixing tonight's evening hours with tomorrow's
        morning hours).

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

        # Special case: all-day window bypasses filtering
        if time_window_start == "00:00" and time_window_end == "23:59":
            sorted_prices = sorted(prices, key=lambda x: x["total"])
            cheapest = sorted_prices[:hours_count] if len(sorted_prices) >= hours_count else sorted_prices
            return [
                {
                    "start": p["startsAt"],
                    "price": round(p["total"], 4),
                    "price_level": p.get("level", "NORMAL"),
                }
                for p in cheapest
            ]

        # Parse time window using helper (with validation)
        start_hour, start_minute, end_hour, end_minute, spans_midnight = self._parse_time_window(
            time_window_start, time_window_end
        )

        # Get current time and calculate active window boundaries
        now = datetime.now(timezone.utc)
        window_start_dt, window_end_dt = self._get_active_window_boundaries(
            now, start_hour, start_minute, end_hour, end_minute, spans_midnight
        )

        _LOGGER.debug(
            f"Time window {time_window_start}-{time_window_end}: "
            f"Active window is {window_start_dt.isoformat()} to {window_end_dt.isoformat()}"
        )

        # Filter prices within the active window boundaries (using full datetime comparison)
        filtered_prices = []
        for price_data in prices:
            try:
                hour_time = self._parse_tibber_timestamp(price_data["startsAt"])

                # Include if within the calculated window boundaries
                if window_start_dt <= hour_time < window_end_dt:
                    filtered_prices.append(price_data)
            except (ValueError, KeyError) as e:
                _LOGGER.warning(f"Failed to parse price data: {e}")
                continue

        # If no prices in window, return empty (don't fall back to all prices)
        if not filtered_prices:
            _LOGGER.debug(
                f"No prices found in window {window_start_dt.isoformat()} to {window_end_dt.isoformat()}"
            )
            return []

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
