"""Constants for the Tibber Smart Control integration."""

DOMAIN = "tibber_control"

# Configuration
CONF_API_KEY = "api_key"
CONF_HOME_ID = "home_id"

# Defaults
DEFAULT_SCAN_INTERVAL = 300  # 5 minutes
DEFAULT_NAME = "Tibber"

# Tibber API
TIBBER_API_URL = "https://api.tibber.com/v1-beta/gql"

# Sensor types
SENSOR_CURRENT_PRICE = "current_price"
SENSOR_AVERAGE_PRICE = "average_price"
SENSOR_MIN_PRICE = "min_price"
SENSOR_MAX_PRICE = "max_price"
SENSOR_CHEAPEST_HOURS = "cheapest_hours"
SENSOR_MOST_EXPENSIVE_HOURS = "most_expensive_hours"
SENSOR_PRICE_LEVEL = "price_level"

# Binary sensor types
BINARY_SENSOR_IS_CHEAP = "is_cheap"
BINARY_SENSOR_IS_EXPENSIVE = "is_expensive"
BINARY_SENSOR_IS_CHEAPEST_HOUR = "is_cheapest_hour"

# Attributes
ATTR_ENERGY_PRICE = "energy"
ATTR_TAX = "tax"
ATTR_STARTS_AT = "starts_at"
ATTR_LEVEL = "level"
ATTR_TODAY_PRICES = "today"
ATTR_TOMORROW_PRICES = "tomorrow"
ATTR_HOURS = "hours"
ATTR_THRESHOLD = "threshold"
