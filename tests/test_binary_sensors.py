"""Tests for actual binary sensor classes."""
import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, PropertyMock

import pytest
from aioresponses import aioresponses
from homeassistant.core import HomeAssistant

from custom_components.tibber_extended.const import TIBBER_API_URL
from custom_components.tibber_extended.coordinator import TibberDataUpdateCoordinator
from custom_components.tibber_extended.binary_sensor import (
    TibberIsCheapHourSensor,
    TibberIsExpensiveHourSensor,
    TibberIsCheapSensor,
    TibberIsExpensiveSensor,
    TibberIsVeryCheapSensor,
    TibberIsVeryExpensiveSensor,
    TibberIsBelowAverageSensor,
    TibberIsInBestConsecutiveHoursWindowSensor,
    TibberBatteryChargingRecommendedSensor,
    TibberIsCheapestHourSensor,
    TibberIsTimeWindowCheapHourBinarySensor,
    TibberIsGoodChargingTimeSensor,
)


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

    for price in today_prices:
        if f"T{hour:02d}:00" in price["startsAt"]:
            modified["data"]["viewer"]["homes"][0]["currentSubscription"]["priceInfo"]["current"] = deepcopy(price)
            break

    return modified


class TestTibberIsCheapHourSensor:
    """Test is_cheap_hour binary sensor."""

    @pytest.mark.asyncio
    async def test_is_on_at_21(self, hass: HomeAssistant, api_response):
        """Test sensor is ON at 21:00 (2nd cheapest hour)."""
        modified = modify_current_hour(api_response, 21)

        with aioresponses() as m:
            m.post(TIBBER_API_URL, payload=modified, repeat=True)

            coord = TibberDataUpdateCoordinator(hass=hass, api_key="test", hours_duration=3, calculation_hour=0)
            await coord.async_refresh()

            home_id = list(coord.data.keys())[0]
            sensor = TibberIsCheapHourSensor(coord, home_id)

            assert sensor.is_on is True, "Sensor should be ON at 21:00"

    @pytest.mark.asyncio
    async def test_is_on_at_22(self, hass: HomeAssistant, api_response):
        """Test sensor is ON at 22:00 (3rd cheapest hour)."""
        modified = modify_current_hour(api_response, 22)

        with aioresponses() as m:
            m.post(TIBBER_API_URL, payload=modified, repeat=True)

            coord = TibberDataUpdateCoordinator(hass=hass, api_key="test", hours_duration=3, calculation_hour=0)
            await coord.async_refresh()

            home_id = list(coord.data.keys())[0]
            sensor = TibberIsCheapHourSensor(coord, home_id)

            assert sensor.is_on is True, "Sensor should be ON at 22:00"

    @pytest.mark.asyncio
    async def test_is_on_at_23(self, hass: HomeAssistant, api_response):
        """Test sensor is ON at 23:00 (cheapest hour)."""
        modified = modify_current_hour(api_response, 23)

        with aioresponses() as m:
            m.post(TIBBER_API_URL, payload=modified, repeat=True)

            coord = TibberDataUpdateCoordinator(hass=hass, api_key="test", hours_duration=3, calculation_hour=0)
            await coord.async_refresh()

            home_id = list(coord.data.keys())[0]
            sensor = TibberIsCheapHourSensor(coord, home_id)

            assert sensor.is_on is True, "Sensor should be ON at 23:00"

    @pytest.mark.asyncio
    async def test_is_off_at_12(self, hass: HomeAssistant, api_response):
        """Test sensor is OFF at 12:00 (not a cheap hour)."""
        modified = modify_current_hour(api_response, 12)

        with aioresponses() as m:
            m.post(TIBBER_API_URL, payload=modified, repeat=True)

            coord = TibberDataUpdateCoordinator(hass=hass, api_key="test", hours_duration=3, calculation_hour=0)
            await coord.async_refresh()

            home_id = list(coord.data.keys())[0]
            sensor = TibberIsCheapHourSensor(coord, home_id)

            assert sensor.is_on is False, "Sensor should be OFF at 12:00"

    @pytest.mark.asyncio
    async def test_is_off_at_08(self, hass: HomeAssistant, api_response):
        """Test sensor is OFF at 08:00 (most expensive hour)."""
        modified = modify_current_hour(api_response, 8)

        with aioresponses() as m:
            m.post(TIBBER_API_URL, payload=modified, repeat=True)

            coord = TibberDataUpdateCoordinator(hass=hass, api_key="test", hours_duration=3, calculation_hour=0)
            await coord.async_refresh()

            home_id = list(coord.data.keys())[0]
            sensor = TibberIsCheapHourSensor(coord, home_id)

            assert sensor.is_on is False, "Sensor should be OFF at 08:00"


class TestTibberIsExpensiveHourSensor:
    """Test is_expensive_hour binary sensor."""

    @pytest.mark.asyncio
    async def test_is_on_at_08(self, hass: HomeAssistant, api_response):
        """Test sensor is ON at 08:00 (most expensive hour)."""
        modified = modify_current_hour(api_response, 8)

        with aioresponses() as m:
            m.post(TIBBER_API_URL, payload=modified, repeat=True)

            coord = TibberDataUpdateCoordinator(hass=hass, api_key="test", hours_duration=3, calculation_hour=0)
            await coord.async_refresh()

            home_id = list(coord.data.keys())[0]
            sensor = TibberIsExpensiveHourSensor(coord, home_id)

            assert sensor.is_on is True, "Sensor should be ON at 08:00"

    @pytest.mark.asyncio
    async def test_is_on_at_07(self, hass: HomeAssistant, api_response):
        """Test sensor is ON at 07:00 (2nd most expensive)."""
        modified = modify_current_hour(api_response, 7)

        with aioresponses() as m:
            m.post(TIBBER_API_URL, payload=modified, repeat=True)

            coord = TibberDataUpdateCoordinator(hass=hass, api_key="test", hours_duration=3, calculation_hour=0)
            await coord.async_refresh()

            home_id = list(coord.data.keys())[0]
            sensor = TibberIsExpensiveHourSensor(coord, home_id)

            assert sensor.is_on is True, "Sensor should be ON at 07:00"

    @pytest.mark.asyncio
    async def test_is_on_at_15(self, hass: HomeAssistant, api_response):
        """Test sensor is ON at 15:00 (3rd most expensive)."""
        modified = modify_current_hour(api_response, 15)

        with aioresponses() as m:
            m.post(TIBBER_API_URL, payload=modified, repeat=True)

            coord = TibberDataUpdateCoordinator(hass=hass, api_key="test", hours_duration=3, calculation_hour=0)
            await coord.async_refresh()

            home_id = list(coord.data.keys())[0]
            sensor = TibberIsExpensiveHourSensor(coord, home_id)

            assert sensor.is_on is True, "Sensor should be ON at 15:00"

    @pytest.mark.asyncio
    async def test_is_off_at_23(self, hass: HomeAssistant, api_response):
        """Test sensor is OFF at 23:00 (cheapest hour)."""
        modified = modify_current_hour(api_response, 23)

        with aioresponses() as m:
            m.post(TIBBER_API_URL, payload=modified, repeat=True)

            coord = TibberDataUpdateCoordinator(hass=hass, api_key="test", hours_duration=3, calculation_hour=0)
            await coord.async_refresh()

            home_id = list(coord.data.keys())[0]
            sensor = TibberIsExpensiveHourSensor(coord, home_id)

            assert sensor.is_on is False, "Sensor should be OFF at 23:00"


class TestTibberIsBelowAverageSensor:
    """Test is_below_average binary sensor."""

    @pytest.mark.asyncio
    async def test_is_on_at_23(self, hass: HomeAssistant, api_response):
        """Test sensor is ON at 23:00 (cheapest, below average)."""
        modified = modify_current_hour(api_response, 23)

        with aioresponses() as m:
            m.post(TIBBER_API_URL, payload=modified, repeat=True)

            coord = TibberDataUpdateCoordinator(hass=hass, api_key="test", hours_duration=3, calculation_hour=0)
            await coord.async_refresh()

            home_id = list(coord.data.keys())[0]
            sensor = TibberIsBelowAverageSensor(coord, home_id)

            # 23:00 price is 0.2944, average is ~0.32, so below average
            assert sensor.is_on is True, "Sensor should be ON at 23:00"

    @pytest.mark.asyncio
    async def test_is_off_at_08(self, hass: HomeAssistant, api_response):
        """Test sensor is OFF at 08:00 (most expensive, above average)."""
        modified = modify_current_hour(api_response, 8)

        with aioresponses() as m:
            m.post(TIBBER_API_URL, payload=modified, repeat=True)

            coord = TibberDataUpdateCoordinator(hass=hass, api_key="test", hours_duration=3, calculation_hour=0)
            await coord.async_refresh()

            home_id = list(coord.data.keys())[0]
            sensor = TibberIsBelowAverageSensor(coord, home_id)

            # 08:00 price is 0.3747, average is ~0.32, so above average
            assert sensor.is_on is False, "Sensor should be OFF at 08:00"


class TestTibberIsCheapestHourSensor:
    """Test is_cheapest_hour binary sensor (single cheapest)."""

    @pytest.mark.asyncio
    async def test_is_on_at_23(self, hass: HomeAssistant, api_response):
        """Test sensor is ON at 23:00 (THE cheapest hour)."""
        modified = modify_current_hour(api_response, 23)

        with aioresponses() as m:
            m.post(TIBBER_API_URL, payload=modified, repeat=True)

            coord = TibberDataUpdateCoordinator(hass=hass, api_key="test", hours_duration=3, calculation_hour=0)
            await coord.async_refresh()

            home_id = list(coord.data.keys())[0]
            sensor = TibberIsCheapestHourSensor(coord, home_id)

            assert sensor.is_on is True, "Sensor should be ON at 23:00 (THE cheapest)"

    @pytest.mark.asyncio
    async def test_is_off_at_21(self, hass: HomeAssistant, api_response):
        """Test sensor is OFF at 21:00 (2nd cheapest, not THE cheapest)."""
        modified = modify_current_hour(api_response, 21)

        with aioresponses() as m:
            m.post(TIBBER_API_URL, payload=modified, repeat=True)

            coord = TibberDataUpdateCoordinator(hass=hass, api_key="test", hours_duration=3, calculation_hour=0)
            await coord.async_refresh()

            home_id = list(coord.data.keys())[0]
            sensor = TibberIsCheapestHourSensor(coord, home_id)

            assert sensor.is_on is False, "Sensor should be OFF at 21:00 (not THE cheapest)"


class TestTibberIsInBestConsecutiveHoursSensor:
    """Test is_in_best_consecutive_hours binary sensor."""

    @pytest.mark.asyncio
    async def test_is_on_at_21(self, hass: HomeAssistant, api_response):
        """Test sensor is ON at 21:00 (in best 3h window 21-23)."""
        modified = modify_current_hour(api_response, 21)

        with aioresponses() as m:
            m.post(TIBBER_API_URL, payload=modified, repeat=True)

            coord = TibberDataUpdateCoordinator(hass=hass, api_key="test", hours_duration=3, calculation_hour=0)
            await coord.async_refresh()

            home_id = list(coord.data.keys())[0]
            sensor = TibberIsInBestConsecutiveHoursWindowSensor(coord, home_id)

            assert sensor.is_on is True, "Sensor should be ON at 21:00"

    @pytest.mark.asyncio
    async def test_is_on_at_22(self, hass: HomeAssistant, api_response):
        """Test sensor is ON at 22:00 (in best 3h window 21-23)."""
        modified = modify_current_hour(api_response, 22)

        with aioresponses() as m:
            m.post(TIBBER_API_URL, payload=modified, repeat=True)

            coord = TibberDataUpdateCoordinator(hass=hass, api_key="test", hours_duration=3, calculation_hour=0)
            await coord.async_refresh()

            home_id = list(coord.data.keys())[0]
            sensor = TibberIsInBestConsecutiveHoursWindowSensor(coord, home_id)

            assert sensor.is_on is True, "Sensor should be ON at 22:00"

    @pytest.mark.asyncio
    async def test_is_on_at_23(self, hass: HomeAssistant, api_response):
        """Test sensor is ON at 23:00 (in best 3h window 21-23)."""
        modified = modify_current_hour(api_response, 23)

        with aioresponses() as m:
            m.post(TIBBER_API_URL, payload=modified, repeat=True)

            coord = TibberDataUpdateCoordinator(hass=hass, api_key="test", hours_duration=3, calculation_hour=0)
            await coord.async_refresh()

            home_id = list(coord.data.keys())[0]
            sensor = TibberIsInBestConsecutiveHoursWindowSensor(coord, home_id)

            assert sensor.is_on is True, "Sensor should be ON at 23:00"

    @pytest.mark.asyncio
    async def test_is_off_at_20(self, hass: HomeAssistant, api_response):
        """Test sensor is OFF at 20:00 (NOT in best 3h window)."""
        modified = modify_current_hour(api_response, 20)

        with aioresponses() as m:
            m.post(TIBBER_API_URL, payload=modified, repeat=True)

            coord = TibberDataUpdateCoordinator(hass=hass, api_key="test", hours_duration=3, calculation_hour=0)
            await coord.async_refresh()

            home_id = list(coord.data.keys())[0]
            sensor = TibberIsInBestConsecutiveHoursWindowSensor(coord, home_id)

            assert sensor.is_on is False, "Sensor should be OFF at 20:00"


class TestFullDaySensorSimulation:
    """Simulate full day and verify exact ON/OFF states."""

    @pytest.mark.asyncio
    async def test_is_cheap_hour_all_24_hours(self, hass: HomeAssistant, api_response):
        """Test is_cheap_hour for all 24 hours."""
        print("\n=== is_cheap_hour Full Day Test ===")
        expected_on = {21, 22, 23}  # Cheapest 3 hours
        actual_on = set()

        for hour in range(24):
            modified = modify_current_hour(api_response, hour)

            with aioresponses() as m:
                m.post(TIBBER_API_URL, payload=modified, repeat=True)

                coord = TibberDataUpdateCoordinator(hass=hass, api_key="test", hours_duration=3, calculation_hour=0)
                await coord.async_refresh()

                home_id = list(coord.data.keys())[0]
                sensor = TibberIsCheapHourSensor(coord, home_id)

                if sensor.is_on:
                    actual_on.add(hour)
                print(f"  {hour:02d}:00 - is_on: {sensor.is_on}")

        print(f"\nExpected ON: {expected_on}")
        print(f"Actual ON: {actual_on}")

        assert actual_on == expected_on, f"Mismatch! Expected {expected_on}, got {actual_on}"

    @pytest.mark.asyncio
    async def test_is_expensive_hour_all_24_hours(self, hass: HomeAssistant, api_response):
        """Test is_expensive_hour for all 24 hours."""
        print("\n=== is_expensive_hour Full Day Test ===")
        expected_on = {7, 8, 15}  # Most expensive 3 hours
        actual_on = set()

        for hour in range(24):
            modified = modify_current_hour(api_response, hour)

            with aioresponses() as m:
                m.post(TIBBER_API_URL, payload=modified, repeat=True)

                coord = TibberDataUpdateCoordinator(hass=hass, api_key="test", hours_duration=3, calculation_hour=0)
                await coord.async_refresh()

                home_id = list(coord.data.keys())[0]
                sensor = TibberIsExpensiveHourSensor(coord, home_id)

                if sensor.is_on:
                    actual_on.add(hour)
                print(f"  {hour:02d}:00 - is_on: {sensor.is_on}")

        print(f"\nExpected ON: {expected_on}")
        print(f"Actual ON: {actual_on}")

        assert actual_on == expected_on, f"Mismatch! Expected {expected_on}, got {actual_on}"

    @pytest.mark.asyncio
    async def test_is_in_best_consecutive_hours_all_24(self, hass: HomeAssistant, api_response):
        """Test is_in_best_consecutive_hours for all 24 hours."""
        print("\n=== is_in_best_consecutive_hours Full Day Test ===")
        expected_on = {21, 22, 23}  # Best 3h consecutive window
        actual_on = set()

        for hour in range(24):
            modified = modify_current_hour(api_response, hour)

            with aioresponses() as m:
                m.post(TIBBER_API_URL, payload=modified, repeat=True)

                coord = TibberDataUpdateCoordinator(hass=hass, api_key="test", hours_duration=3, calculation_hour=0)
                await coord.async_refresh()

                home_id = list(coord.data.keys())[0]
                sensor = TibberIsInBestConsecutiveHoursWindowSensor(coord, home_id)

                if sensor.is_on:
                    actual_on.add(hour)
                print(f"  {hour:02d}:00 - is_on: {sensor.is_on}")

        print(f"\nExpected ON: {expected_on}")
        print(f"Actual ON: {actual_on}")

        assert actual_on == expected_on, f"Mismatch! Expected {expected_on}, got {actual_on}"
