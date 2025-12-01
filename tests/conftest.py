"""Pytest fixtures for Tibber Extended tests."""
import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock

import pytest


@pytest.fixture
def api_response():
    """Load the real API response fixture."""
    fixture_path = Path(__file__).parent / "fixtures" / "api_response.json"
    with open(fixture_path) as f:
        return json.load(f)


@pytest.fixture
def price_info(api_response):
    """Extract price info from API response."""
    home = api_response["data"]["viewer"]["homes"][0]
    return home["currentSubscription"]["priceInfo"]


@pytest.fixture
def today_prices(price_info):
    """Get today's prices."""
    return price_info["today"]


@pytest.fixture
def tomorrow_prices(price_info):
    """Get tomorrow's prices."""
    return price_info["tomorrow"]


@pytest.fixture
def current_price(price_info):
    """Get current price info."""
    return price_info["current"]


@pytest.fixture
def mock_hass():
    """Create a mock Home Assistant instance."""
    hass = MagicMock()
    hass.async_create_task = MagicMock()
    return hass


@pytest.fixture
def coordinator_config():
    """Default coordinator configuration."""
    return {
        "api_key": "test_key",
        "update_interval": 300,
        "battery_efficiency": 86,
        "hours_duration": 3,
        "time_window_start": "00:00",
        "time_window_end": "23:59",
    }
