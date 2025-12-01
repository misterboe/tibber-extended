"""Integration tests for Tibber Extended using HA test framework."""
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from aioresponses import aioresponses
from homeassistant.core import HomeAssistant

from custom_components.tibber_extended.const import DOMAIN, TIBBER_API_URL
from custom_components.tibber_extended.coordinator import TibberDataUpdateCoordinator


@pytest.fixture
def api_response():
    """Load the real API response fixture."""
    fixture_path = Path(__file__).parent / "fixtures" / "api_response.json"
    with open(fixture_path) as f:
        return json.load(f)


@pytest.fixture
def mock_tibber_api(api_response):
    """Mock the Tibber API response."""
    with aioresponses() as m:
        m.post(TIBBER_API_URL, payload=api_response, repeat=True)
        yield m


@pytest.fixture
async def coordinator(hass: HomeAssistant, mock_tibber_api, api_response):
    """Create and setup coordinator with mocked API."""
    coord = TibberDataUpdateCoordinator(
        hass=hass,
        api_key="test_key",
        update_interval=300,
        battery_efficiency=86,
        hours_duration=3,
        time_window_start="00:00",
        time_window_end="23:59",
        calculation_hour=0,  # Use 0 for backwards-compatible test behavior
    )

    # Manually process data like _async_update_data does
    await coord.async_config_entry_first_refresh()

    return coord


class TestCoordinatorSetup:
    """Test coordinator setup and data processing."""

    @pytest.mark.asyncio
    async def test_coordinator_loads_data(self, hass: HomeAssistant, mock_tibber_api, api_response):
        """Test that coordinator loads and processes data."""
        coord = TibberDataUpdateCoordinator(
            hass=hass,
            api_key="test_key",
            hours_duration=3,
            calculation_hour=0,
        )

        # Fetch data
        await coord.async_refresh()

        # Check data was loaded
        assert coord.data is not None
        assert len(coord.data) > 0

    @pytest.mark.asyncio
    async def test_cheapest_hours_calculated(self, hass: HomeAssistant, mock_tibber_api):
        """Test that cheapest_hours is calculated correctly."""
        coord = TibberDataUpdateCoordinator(
            hass=hass,
            api_key="test_key",
            hours_duration=3,
            calculation_hour=0,
        )

        await coord.async_refresh()

        # Get first home's data
        home_id = list(coord.data.keys())[0]
        home_data = coord.data[home_id]

        cheapest_hours = home_data.get("cheapest_hours", [])
        assert len(cheapest_hours) == 3

        # Check times
        times = [h["start"].split("T")[1][:5] for h in cheapest_hours]
        assert "21:00" in times
        assert "22:00" in times
        assert "23:00" in times

    @pytest.mark.asyncio
    async def test_expensive_hours_calculated(self, hass: HomeAssistant, mock_tibber_api):
        """Test that most_expensive_hours is calculated correctly."""
        coord = TibberDataUpdateCoordinator(
            hass=hass,
            api_key="test_key",
            hours_duration=3,
            calculation_hour=0,
        )

        await coord.async_refresh()

        home_id = list(coord.data.keys())[0]
        home_data = coord.data[home_id]

        expensive_hours = home_data.get("most_expensive_hours", [])
        assert len(expensive_hours) == 3

        times = [h["start"].split("T")[1][:5] for h in expensive_hours]
        assert "08:00" in times
        assert "07:00" in times
        assert "15:00" in times

    @pytest.mark.asyncio
    async def test_best_consecutive_hours(self, hass: HomeAssistant, mock_tibber_api):
        """Test best_consecutive_hours calculation."""
        coord = TibberDataUpdateCoordinator(
            hass=hass,
            api_key="test_key",
            hours_duration=3,
            calculation_hour=0,
        )

        await coord.async_refresh()

        home_id = list(coord.data.keys())[0]
        home_data = coord.data[home_id]

        best = home_data.get("best_consecutive_hours", {})
        assert best.get("hours") is not None
        assert len(best["hours"]) == 3

        times = [h["start"].split("T")[1][:5] for h in best["hours"]]
        # Best consecutive should be 21:00, 22:00, 23:00
        assert times == ["21:00", "22:00", "23:00"]


class TestBinarySensorLogic:
    """Test binary sensor logic with real coordinator data."""

    @pytest.mark.asyncio
    async def test_is_cheap_hour_at_current(self, hass: HomeAssistant, mock_tibber_api):
        """Test is_cheap_hour logic at current time (07:00)."""
        coord = TibberDataUpdateCoordinator(
            hass=hass,
            api_key="test_key",
            hours_duration=3,
            calculation_hour=0,
        )

        await coord.async_refresh()

        home_id = list(coord.data.keys())[0]
        home_data = coord.data[home_id]

        cheapest_hours = home_data.get("cheapest_hours", [])
        current_time = home_data["current"]["startsAt"]

        is_cheap_hour = any(h["start"] == current_time for h in cheapest_hours)

        # 07:00 is NOT a cheap hour
        assert not is_cheap_hour

    @pytest.mark.asyncio
    async def test_is_expensive_hour_at_current(self, hass: HomeAssistant, mock_tibber_api):
        """Test is_expensive_hour logic at current time (07:00)."""
        coord = TibberDataUpdateCoordinator(
            hass=hass,
            api_key="test_key",
            hours_duration=3,
            calculation_hour=0,
        )

        await coord.async_refresh()

        home_id = list(coord.data.keys())[0]
        home_data = coord.data[home_id]

        expensive_hours = home_data.get("most_expensive_hours", [])
        current_time = home_data["current"]["startsAt"]

        is_expensive_hour = any(h["start"] == current_time for h in expensive_hours)

        # 07:00 IS an expensive hour (2nd most expensive)
        assert is_expensive_hour

    @pytest.mark.asyncio
    async def test_is_below_average(self, hass: HomeAssistant, mock_tibber_api):
        """Test is_below_average logic."""
        coord = TibberDataUpdateCoordinator(
            hass=hass,
            api_key="test_key",
            hours_duration=3,
            calculation_hour=0,
        )

        await coord.async_refresh()

        home_id = list(coord.data.keys())[0]
        home_data = coord.data[home_id]

        current_price = home_data["current"]["total"]
        average_price = home_data["average_price"]

        is_below_average = current_price < average_price

        # 07:00 at 0.3611 should be ABOVE average
        assert not is_below_average
