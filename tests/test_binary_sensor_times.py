"""Tests that simulate binary sensor behavior at different times."""
import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

import pytest
from aioresponses import aioresponses
from homeassistant.core import HomeAssistant

from custom_components.tibber_extended.const import TIBBER_API_URL
from custom_components.tibber_extended.coordinator import TibberDataUpdateCoordinator


@pytest.fixture
def api_response():
    """Load the real API response fixture."""
    fixture_path = Path(__file__).parent / "fixtures" / "api_response.json"
    with open(fixture_path) as f:
        return json.load(f)


def modify_current_hour(api_response, hour: int):
    """Create a modified API response with different current hour."""
    modified = deepcopy(api_response)
    today_prices = modified["data"]["viewer"]["homes"][0]["currentSubscription"]["priceInfo"]["today"]

    # Find the price for the requested hour
    for price in today_prices:
        if f"T{hour:02d}:00" in price["startsAt"]:
            modified["data"]["viewer"]["homes"][0]["currentSubscription"]["priceInfo"]["current"] = deepcopy(price)
            break

    return modified


class TestBinarySensorAtDifferentTimes:
    """Test binary sensor states at different hours."""

    @pytest.mark.asyncio
    async def test_is_cheap_hour_at_21(self, hass: HomeAssistant, api_response):
        """Test is_cheap_hour at 21:00 (should be ON - 2nd cheapest)."""
        modified = modify_current_hour(api_response, 21)

        with aioresponses() as m:
            m.post(TIBBER_API_URL, payload=modified, repeat=True)

            coord = TibberDataUpdateCoordinator(hass=hass, api_key="test", hours_duration=3, calculation_hour=0)
            await coord.async_refresh()

            home_id = list(coord.data.keys())[0]
            home_data = coord.data[home_id]

            cheapest_hours = home_data["cheapest_hours"]
            current_time = home_data["current"]["startsAt"]

            is_cheap = any(h["start"] == current_time for h in cheapest_hours)

            print(f"\nAt 21:00:")
            print(f"  Current time: {current_time}")
            print(f"  Cheapest hours: {[h['start'].split('T')[1][:5] for h in cheapest_hours]}")
            print(f"  is_cheap_hour: {is_cheap}")

            assert is_cheap, "21:00 should be a cheap hour"

    @pytest.mark.asyncio
    async def test_is_cheap_hour_at_22(self, hass: HomeAssistant, api_response):
        """Test is_cheap_hour at 22:00 (should be ON - 3rd cheapest)."""
        modified = modify_current_hour(api_response, 22)

        with aioresponses() as m:
            m.post(TIBBER_API_URL, payload=modified, repeat=True)

            coord = TibberDataUpdateCoordinator(hass=hass, api_key="test", hours_duration=3, calculation_hour=0)
            await coord.async_refresh()

            home_id = list(coord.data.keys())[0]
            home_data = coord.data[home_id]

            is_cheap = any(h["start"] == home_data["current"]["startsAt"] for h in home_data["cheapest_hours"])

            assert is_cheap, "22:00 should be a cheap hour"

    @pytest.mark.asyncio
    async def test_is_cheap_hour_at_23(self, hass: HomeAssistant, api_response):
        """Test is_cheap_hour at 23:00 (should be ON - cheapest hour)."""
        modified = modify_current_hour(api_response, 23)

        with aioresponses() as m:
            m.post(TIBBER_API_URL, payload=modified, repeat=True)

            coord = TibberDataUpdateCoordinator(hass=hass, api_key="test", hours_duration=3, calculation_hour=0)
            await coord.async_refresh()

            home_id = list(coord.data.keys())[0]
            home_data = coord.data[home_id]

            is_cheap = any(h["start"] == home_data["current"]["startsAt"] for h in home_data["cheapest_hours"])

            assert is_cheap, "23:00 should be a cheap hour (the cheapest!)"

    @pytest.mark.asyncio
    async def test_is_cheap_hour_at_12(self, hass: HomeAssistant, api_response):
        """Test is_cheap_hour at 12:00 (should be OFF)."""
        modified = modify_current_hour(api_response, 12)

        with aioresponses() as m:
            m.post(TIBBER_API_URL, payload=modified, repeat=True)

            coord = TibberDataUpdateCoordinator(hass=hass, api_key="test", hours_duration=3, calculation_hour=0)
            await coord.async_refresh()

            home_id = list(coord.data.keys())[0]
            home_data = coord.data[home_id]

            is_cheap = any(h["start"] == home_data["current"]["startsAt"] for h in home_data["cheapest_hours"])

            assert not is_cheap, "12:00 should NOT be a cheap hour"

    @pytest.mark.asyncio
    async def test_is_expensive_hour_at_08(self, hass: HomeAssistant, api_response):
        """Test is_expensive_hour at 08:00 (should be ON - most expensive)."""
        modified = modify_current_hour(api_response, 8)

        with aioresponses() as m:
            m.post(TIBBER_API_URL, payload=modified, repeat=True)

            coord = TibberDataUpdateCoordinator(hass=hass, api_key="test", hours_duration=3, calculation_hour=0)
            await coord.async_refresh()

            home_id = list(coord.data.keys())[0]
            home_data = coord.data[home_id]

            expensive_hours = home_data["most_expensive_hours"]
            is_expensive = any(h["start"] == home_data["current"]["startsAt"] for h in expensive_hours)

            print(f"\nAt 08:00:")
            print(f"  Expensive hours: {[h['start'].split('T')[1][:5] for h in expensive_hours]}")
            print(f"  is_expensive_hour: {is_expensive}")

            assert is_expensive, "08:00 should be an expensive hour (the most expensive!)"


class TestFullDaySimulation:
    """Simulate a full day and verify sensor states."""

    @pytest.mark.asyncio
    async def test_full_day_cheap_hours(self, hass: HomeAssistant, api_response):
        """Simulate all 24 hours and verify is_cheap_hour states."""
        print("\n=== Full Day is_cheap_hour Simulation ===")
        cheap_on_hours = []

        for hour in range(24):
            modified = modify_current_hour(api_response, hour)

            with aioresponses() as m:
                m.post(TIBBER_API_URL, payload=modified, repeat=True)

                coord = TibberDataUpdateCoordinator(hass=hass, api_key="test", hours_duration=3, calculation_hour=0)
                await coord.async_refresh()

                home_id = list(coord.data.keys())[0]
                home_data = coord.data[home_id]

                is_cheap = any(h["start"] == home_data["current"]["startsAt"] for h in home_data["cheapest_hours"])

                if is_cheap:
                    cheap_on_hours.append(hour)
                print(f"  {hour:02d}:00 - is_cheap_hour: {'ON' if is_cheap else 'off'}")

        print(f"\nHours with is_cheap_hour=ON: {cheap_on_hours}")

        # Should be exactly 3 hours
        assert len(cheap_on_hours) == 3
        assert 21 in cheap_on_hours
        assert 22 in cheap_on_hours
        assert 23 in cheap_on_hours

    @pytest.mark.asyncio
    async def test_full_day_expensive_hours(self, hass: HomeAssistant, api_response):
        """Simulate all 24 hours and verify is_expensive_hour states."""
        print("\n=== Full Day is_expensive_hour Simulation ===")
        expensive_on_hours = []

        for hour in range(24):
            modified = modify_current_hour(api_response, hour)

            with aioresponses() as m:
                m.post(TIBBER_API_URL, payload=modified, repeat=True)

                coord = TibberDataUpdateCoordinator(hass=hass, api_key="test", hours_duration=3, calculation_hour=0)
                await coord.async_refresh()

                home_id = list(coord.data.keys())[0]
                home_data = coord.data[home_id]

                is_expensive = any(h["start"] == home_data["current"]["startsAt"] for h in home_data["most_expensive_hours"])

                if is_expensive:
                    expensive_on_hours.append(hour)
                print(f"  {hour:02d}:00 - is_expensive_hour: {'ON' if is_expensive else 'off'}")

        print(f"\nHours with is_expensive_hour=ON: {expensive_on_hours}")

        # Should be exactly 3 hours
        assert len(expensive_on_hours) == 3
        assert 7 in expensive_on_hours   # 2nd most expensive
        assert 8 in expensive_on_hours   # most expensive
        assert 15 in expensive_on_hours  # 3rd most expensive
