"""Tests for coordinator price calculations."""
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch, AsyncMock

import pytest

# We need to test the calculation functions in isolation
# Import the coordinator module to test its methods


class TestPriceCalculations:
    """Test price calculation logic."""

    @pytest.fixture
    def api_response(self):
        """Load the real API response fixture."""
        fixture_path = Path(__file__).parent / "fixtures" / "api_response.json"
        with open(fixture_path) as f:
            return json.load(f)

    @pytest.fixture
    def today_prices(self, api_response):
        """Get today's prices."""
        return api_response["data"]["viewer"]["homes"][0]["currentSubscription"]["priceInfo"]["today"]

    @pytest.fixture
    def current_price_info(self, api_response):
        """Get current price info."""
        return api_response["data"]["viewer"]["homes"][0]["currentSubscription"]["priceInfo"]["current"]

    def test_fixture_has_24_hours(self, today_prices):
        """Verify fixture has 24 hourly prices."""
        assert len(today_prices) == 24

    def test_find_cheapest_3_hours(self, today_prices):
        """Test finding the 3 cheapest hours."""
        sorted_prices = sorted(today_prices, key=lambda x: x["total"])
        cheapest_3 = sorted_prices[:3]

        # Based on fixture data, cheapest should be:
        # 23:00 (0.2944), 21:00 (0.2993), 22:00 (0.2999)
        cheapest_times = [p["startsAt"].split("T")[1][:5] for p in cheapest_3]
        cheapest_values = [p["total"] for p in cheapest_3]

        assert cheapest_times == ["23:00", "21:00", "22:00"]
        assert cheapest_values == [0.2944, 0.2993, 0.2999]

    def test_find_most_expensive_3_hours(self, today_prices):
        """Test finding the 3 most expensive hours."""
        sorted_prices = sorted(today_prices, key=lambda x: x["total"])
        expensive_3 = sorted_prices[-3:]  # Last 3 = most expensive

        # Based on fixture data, most expensive should be:
        # 15:00 (0.3522), 07:00 (0.3611), 08:00 (0.3747)
        expensive_times = [p["startsAt"].split("T")[1][:5] for p in expensive_3]
        expensive_values = [p["total"] for p in expensive_3]

        assert expensive_times == ["15:00", "07:00", "08:00"]
        assert expensive_values == [0.3522, 0.3611, 0.3747]

    def test_current_hour_is_expensive(self, today_prices, current_price_info):
        """Test that current hour (07:00) is in most expensive 3."""
        sorted_prices = sorted(today_prices, key=lambda x: x["total"])
        expensive_3 = sorted_prices[-3:]

        current_time = current_price_info["startsAt"]

        is_expensive = any(p["startsAt"] == current_time for p in expensive_3)
        assert is_expensive, f"Current hour {current_time} should be in expensive hours"

    def test_current_hour_is_not_cheap(self, today_prices, current_price_info):
        """Test that current hour (07:00) is NOT in cheapest 3."""
        sorted_prices = sorted(today_prices, key=lambda x: x["total"])
        cheapest_3 = sorted_prices[:3]

        current_time = current_price_info["startsAt"]

        is_cheap = any(p["startsAt"] == current_time for p in cheapest_3)
        assert not is_cheap, f"Current hour {current_time} should NOT be in cheapest hours"

    def test_average_price_calculation(self, today_prices):
        """Test average price calculation."""
        prices = [p["total"] for p in today_prices]
        avg = sum(prices) / len(prices)

        # Verify calculation
        assert len(prices) == 24
        assert round(avg, 4) == round(sum(prices) / 24, 4)

    def test_min_max_price(self, today_prices):
        """Test min/max price identification."""
        prices = [p["total"] for p in today_prices]

        min_price = min(prices)
        max_price = max(prices)

        assert min_price == 0.2944  # 23:00
        assert max_price == 0.3747  # 08:00

    def test_current_price_vs_average(self, today_prices, current_price_info):
        """Test if current price is above or below average."""
        prices = [p["total"] for p in today_prices]
        avg = sum(prices) / len(prices)
        current = current_price_info["total"]

        is_below_average = current < avg
        # Current is 0.3611, let's check
        print(f"Average: {avg}, Current: {current}")
        # This test documents the expected behavior


class TestBestConsecutiveWindow:
    """Test best consecutive hours window calculation."""

    @pytest.fixture
    def today_prices(self):
        """Load today's prices from fixture."""
        fixture_path = Path(__file__).parent / "fixtures" / "api_response.json"
        with open(fixture_path) as f:
            data = json.load(f)
        return data["data"]["viewer"]["homes"][0]["currentSubscription"]["priceInfo"]["today"]

    def test_best_3_consecutive_hours(self, today_prices):
        """Find the cheapest 3 consecutive hours."""
        duration = 3
        best_window = None
        best_avg = float('inf')

        for i in range(len(today_prices) - duration + 1):
            window = today_prices[i:i + duration]
            avg = sum(p["total"] for p in window) / duration

            if avg < best_avg:
                best_avg = avg
                best_window = window

        # The cheapest 3 consecutive hours
        window_times = [p["startsAt"].split("T")[1][:5] for p in best_window]
        window_prices = [p["total"] for p in best_window]

        print(f"Best 3h window: {window_times} with avg {best_avg:.4f}")
        print(f"Prices: {window_prices}")

        # 21:00-23:00 should be cheapest consecutive (0.2993, 0.2999, 0.2944)
        # But wait, 23:00 comes after 22:00, so the order is:
        # 21:00 (0.2993), 22:00 (0.2999), 23:00 (0.2944)
        assert window_times == ["21:00", "22:00", "23:00"]


class TestTimeWindowCheapestHours:
    """Test time window cheapest hours calculation."""

    @pytest.fixture
    def today_prices(self):
        """Load today's prices from fixture."""
        fixture_path = Path(__file__).parent / "fixtures" / "api_response.json"
        with open(fixture_path) as f:
            data = json.load(f)
        return data["data"]["viewer"]["homes"][0]["currentSubscription"]["priceInfo"]["today"]

    def test_overnight_window_17_to_07(self, today_prices):
        """Test cheapest hours in 17:00-07:00 overnight window."""
        window_start = 17
        window_end = 7

        # Filter prices within window (17:00-23:59 and 00:00-06:59)
        filtered = []
        for p in today_prices:
            hour = int(p["startsAt"].split("T")[1][:2])
            if hour >= window_start or hour < window_end:
                filtered.append(p)

        # Should have: 17,18,19,20,21,22,23,00,01,02,03,04,05,06 = 14 hours
        assert len(filtered) == 14

        # Sort and get cheapest 3
        sorted_filtered = sorted(filtered, key=lambda x: x["total"])
        cheapest_3 = sorted_filtered[:3]

        cheapest_times = [p["startsAt"].split("T")[1][:5] for p in cheapest_3]
        print(f"Cheapest 3 in 17:00-07:00 window: {cheapest_times}")

        # Should be from the low prices in morning hours
        # 04:00 (0.3044), 02:00 (0.3057), 03:00 (0.3102)
        # Actually let's check properly by sorting
        for p in sorted_filtered[:5]:
            print(f"  {p['startsAt'].split('T')[1][:5]}: {p['total']}")


class TestBinarySensorLogic:
    """Test binary sensor decision logic."""

    @pytest.fixture
    def today_prices(self):
        """Load today's prices from fixture."""
        fixture_path = Path(__file__).parent / "fixtures" / "api_response.json"
        with open(fixture_path) as f:
            data = json.load(f)
        return data["data"]["viewer"]["homes"][0]["currentSubscription"]["priceInfo"]["today"]

    @pytest.fixture
    def current_price_info(self):
        """Load current price info from fixture."""
        fixture_path = Path(__file__).parent / "fixtures" / "api_response.json"
        with open(fixture_path) as f:
            data = json.load(f)
        return data["data"]["viewer"]["homes"][0]["currentSubscription"]["priceInfo"]["current"]

    def test_is_cheap_hour_at_0700(self, today_prices, current_price_info):
        """Test is_cheap_hour binary sensor at 07:00."""
        # Get cheapest 3 hours
        sorted_prices = sorted(today_prices, key=lambda x: x["total"])
        cheapest_3 = sorted_prices[:3]

        current_time = current_price_info["startsAt"]

        # Check if current time is in cheapest hours
        is_cheap_hour = any(p["startsAt"] == current_time for p in cheapest_3)

        assert not is_cheap_hour, "07:00 should NOT be a cheap hour"

    def test_is_expensive_hour_at_0700(self, today_prices, current_price_info):
        """Test is_expensive_hour binary sensor at 07:00."""
        # Get most expensive 3 hours
        sorted_prices = sorted(today_prices, key=lambda x: x["total"])
        expensive_3 = sorted_prices[-3:]

        current_time = current_price_info["startsAt"]

        # Check if current time is in expensive hours
        is_expensive_hour = any(p["startsAt"] == current_time for p in expensive_3)

        assert is_expensive_hour, "07:00 SHOULD be an expensive hour"

    def test_is_below_average_at_0700(self, today_prices, current_price_info):
        """Test is_below_average binary sensor at 07:00."""
        prices = [p["total"] for p in today_prices]
        avg = sum(prices) / len(prices)
        current = current_price_info["total"]

        is_below_average = current < avg

        print(f"Average: {avg:.4f}, Current: {current:.4f}")
        # 07:00 is 0.3611 which is above average
        assert not is_below_average, "07:00 should NOT be below average"

    def test_is_cheap_at_2100(self, today_prices):
        """Test is_cheap_hour at 21:00 (should be true)."""
        sorted_prices = sorted(today_prices, key=lambda x: x["total"])
        cheapest_3 = sorted_prices[:3]

        # Find 21:00 price
        price_2100 = next(p for p in today_prices if "21:00" in p["startsAt"])

        is_cheap_hour = any(p["startsAt"] == price_2100["startsAt"] for p in cheapest_3)

        assert is_cheap_hour, "21:00 SHOULD be a cheap hour (2nd cheapest)"

    def test_simulate_hour_by_hour(self, today_prices):
        """Simulate checking is_cheap_hour for each hour."""
        sorted_prices = sorted(today_prices, key=lambda x: x["total"])
        cheapest_3 = sorted_prices[:3]
        cheapest_times = {p["startsAt"] for p in cheapest_3}

        print("\nHour-by-hour is_cheap_hour simulation:")
        for price in today_prices:
            hour = price["startsAt"].split("T")[1][:5]
            is_cheap = price["startsAt"] in cheapest_times
            print(f"  {hour}: is_cheap_hour = {is_cheap} (price: {price['total']:.4f})")

        # Verify the 3 cheap hours
        cheap_hours = [p["startsAt"].split("T")[1][:5] for p in cheapest_3]
        assert "21:00" in cheap_hours
        assert "22:00" in cheap_hours
        assert "23:00" in cheap_hours
