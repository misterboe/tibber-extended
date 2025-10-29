"""Constants for the Tibber Extended integration."""

DOMAIN = "tibber_extended"

# Configuration
CONF_API_KEY = "api_key"

# Defaults
DEFAULT_SCAN_INTERVAL = 900  # 15 minutes

# Tibber API
TIBBER_API_URL = "https://api.tibber.com/v1-beta/gql"

# Hours Duration Configuration
CONF_HOURS_DURATION = "hours_duration"
DEFAULT_HOURS_DURATION = 3  # Default to 3 consecutive hours (integer only)

# Battery Configuration
CONF_BATTERY_EFFICIENCY = "battery_efficiency"
DEFAULT_BATTERY_EFFICIENCY = 75  # percentage, 0-100
