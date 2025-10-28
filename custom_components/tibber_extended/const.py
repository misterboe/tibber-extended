"""Constants for the Tibber Extended integration."""

DOMAIN = "tibber_extended"

# Configuration
CONF_API_KEY = "api_key"

# Defaults
DEFAULT_SCAN_INTERVAL = 900  # 15 minutes

# Tibber API
TIBBER_API_URL = "https://api.tibber.com/v1-beta/gql"

# Time Window Configuration (for Architecture v2.0)
CONF_TIME_WINDOWS = "time_windows"

# Battery Configuration
CONF_BATTERY_EFFICIENCY = "battery_efficiency"
DEFAULT_BATTERY_EFFICIENCY = 75  # percentage, 0-100
