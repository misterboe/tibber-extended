"""Data update coordinator for Tibber Smart Control."""
from datetime import timedelta
import logging
from typing import Any

import requests

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
        home_id: str | None = None,
        update_interval: int = 300,
    ) -> None:
        """Initialize the coordinator."""
        self.api_key = api_key
        self.home_id = home_id
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

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from Tibber API."""
        try:
            response = await self.hass.async_add_executor_job(
                self._fetch_data
            )

            if not response or "data" not in response:
                raise UpdateFailed("Invalid response from Tibber API")

            homes = response["data"]["viewer"]["homes"]

            if not homes:
                raise UpdateFailed("No homes found in Tibber account")

            # Use first home or specified home_id
            home_data = homes[0]
            if self.home_id:
                for home in homes:
                    if home["id"] == self.home_id:
                        home_data = home
                        break

            price_info = home_data["currentSubscription"]["priceInfo"]

            # Calculate statistics
            today_prices = [p["total"] for p in price_info.get("today", [])]
            current_price = price_info["current"]["total"]

            avg_price = sum(today_prices) / len(today_prices) if today_prices else current_price
            min_price = min(today_prices) if today_prices else current_price
            max_price = max(today_prices) if today_prices else current_price

            # Find cheapest and most expensive hours
            sorted_today = sorted(
                price_info.get("today", []),
                key=lambda x: x["total"]
            )

            cheapest_hours = sorted_today[:3] if len(sorted_today) >= 3 else sorted_today
            expensive_hours = sorted_today[-3:] if len(sorted_today) >= 3 else sorted_today

            # Extract home info for device
            home_info = {
                "id": home_data["id"],
                "name": home_data.get("appNickname") or "Tibber Home",
                "address": home_data.get("address", {}),
            }

            return {
                "home": home_info,
                "current": price_info["current"],
                "today": price_info.get("today", []),
                "tomorrow": price_info.get("tomorrow", []),
                "average_price": avg_price,
                "min_price": min_price,
                "max_price": max_price,
                "cheapest_hours": cheapest_hours,
                "most_expensive_hours": expensive_hours,
            }

        except requests.exceptions.HTTPError as err:
            if err.response.status_code in (401, 403):
                raise ConfigEntryAuthFailed(f"Authentication failed: {err}") from err
            raise UpdateFailed(f"HTTP error from Tibber API: {err}") from err
        except requests.RequestException as err:
            raise UpdateFailed(f"Error communicating with Tibber API: {err}") from err
        except (KeyError, ValueError) as err:
            raise UpdateFailed(f"Error parsing Tibber data: {err}") from err

    def _fetch_data(self) -> dict[str, Any]:
        """Fetch data from Tibber API (blocking)."""
        response = requests.post(
            TIBBER_API_URL,
            json={"query": GRAPHQL_QUERY},
            headers=self.headers,
            timeout=10,
        )
        response.raise_for_status()
        return response.json()
