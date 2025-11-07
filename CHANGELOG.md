# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2025-11-07

### Added

#### Core Features
- **Config Flow** for easy UI-based setup with API key validation
- **Options Flow** for runtime configuration changes
- **Multi-Home Support** - Automatically detects and supports all homes in your Tibber account
- **Smart Updates** - 15-minute update interval with error resilience and data retention
- **Multilingual** - Full German (de) and English (en) translations

#### Sensors (12 Total)

**Price Sensors:**
- `sensor.tibber_current_price` - Current electricity price with rich attributes
- `sensor.tibber_average_price` - Average price today
- `sensor.tibber_min_price` - Lowest price today
- `sensor.tibber_max_price` - Highest price today
- `sensor.tibber_price_level` - Current price level (VERY_CHEAP/CHEAP/NORMAL/EXPENSIVE/VERY_EXPENSIVE)
- `sensor.tibber_cheapest_hours` - Cheapest N hours (configurable)
- `sensor.tibber_most_expensive_hours` - Most expensive N hours (configurable)
- `sensor.tibber_best_consecutive_hours` - Best consecutive time window (configurable duration)
- `sensor.tibber_price_deviation_percent` - Percentage deviation from average
- `sensor.tibber_price_deviation_absolute` - Absolute deviation from average
- `sensor.tibber_battery_breakeven_price` - Economical battery charging threshold
- `sensor.tibber_time_window_cheapest_hours` - **NEW** Cheapest hours within custom time window

#### Binary Sensors (11 Total)

**Price Level Triggers:**
- `binary_sensor.tibber_is_very_cheap` - Price is VERY_CHEAP
- `binary_sensor.tibber_is_cheap` - Price is CHEAP or VERY_CHEAP
- `binary_sensor.tibber_is_expensive` - Price is EXPENSIVE or VERY_EXPENSIVE
- `binary_sensor.tibber_is_very_expensive` - Price is VERY_EXPENSIVE

**Time-Based Triggers:**
- `binary_sensor.tibber_is_cheapest_hour` - Currently in one of N cheapest hours
- `binary_sensor.tibber_is_most_expensive_hour` - Currently in one of N most expensive hours
- `binary_sensor.tibber_is_in_best_consecutive_hours` - Currently in best consecutive window

**Smart Automation Triggers:**
- `binary_sensor.tibber_is_good_charging_time` - Combined logic: CHEAP OR in cheapest hours
- `binary_sensor.tibber_is_below_average` - Current price below daily average
- `binary_sensor.tibber_battery_charging_recommended` - Below battery breakeven price
- `binary_sensor.tibber_is_time_window_cheap_hour` - **NEW** In cheapest hours of custom time window

#### Configuration Options

**Battery Settings:**
- `battery_efficiency` - Charge/discharge efficiency (1-100%, default: 75%)

**Time Settings:**
- `hours_duration` - Number of hours for calculations (1-24h, default: 3)
- `time_window_start` - **NEW** Custom time window start (default: 17:00)
- `time_window_end` - **NEW** Custom time window end (default: 07:00)

#### Services (2 Total)

- `tibber_extended.calculate_best_time_window` - Calculate cheapest consecutive window dynamically
- `tibber_extended.get_price_forecast` - Get detailed price forecast

#### Time Window Feature ⭐ NEW

The **Custom Time Window** feature allows you to:
- Define specific time ranges (e.g., 17:00-07:00 for overnight)
- Automatically find the cheapest N hours within that window
- Perfect for electric vehicle charging, heat pumps, and battery optimization
- Supports time windows spanning midnight (e.g., 17:00-07:00)
- Configurable via Options Flow with time picker UI

**Use Cases:**
- ⚡ Electric vehicle charging during cheapest overnight hours
- 🏠 Heat pump optimization for evening/night periods
- 🔋 Battery storage charging cycles
- 🌡️ Smart appliance scheduling

### Technical

- Built with modern Home Assistant architecture patterns
- DataUpdateCoordinator for efficient data management
- Config Flow and Options Flow for user-friendly configuration
- Async/await with aiohttp for non-blocking API requests
- Complete type hints throughout codebase
- Comprehensive error handling with graceful degradation
- HACS-compatible with proper validation
- Home Assistant Brands integration
- Follows Home Assistant coding standards

### Changed

- Entity naming follows Home Assistant device-based conventions
- Sensor IDs use readable slugs based on home nickname
- Multi-home suffix only added when multiple homes exist

### Requirements

- Home Assistant 2023.9.0 or newer
- Python 3.11 or newer
- aiohttp >= 3.8.0

[1.0.0]: https://github.com/misterboe/tibber-extended/releases/tag/v1.0.0
