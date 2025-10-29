# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2024-10-29

### Added
- Initial release of Tibber Extended for Home Assistant
- **Config Flow** for easy UI-based setup
- **7 Price Sensors:**
  - Current Price
  - Average Price (today)
  - Minimum Price (today)
  - Maximum Price (today)
  - Price Level (VERY_CHEAP, CHEAP, NORMAL, EXPENSIVE, VERY_EXPENSIVE)
  - Cheapest Hours (top 3)
  - Most Expensive Hours (top 3)
- **7 Binary Sensors** for automation triggers:
  - Is Very Cheap
  - Is Cheap
  - Is Expensive
  - Is Very Expensive
  - Is Cheapest Hour (top 3)
  - Is Most Expensive Hour (top 3)
  - Is Good Charging Time (combined logic)
- **Multi-Home Support** - Supports all Tibber homes in your account
- **Battery Efficiency Settings** - Configurable via Options Flow
- **Time Window Management:**
  - Add custom time windows via UI
  - Remove time windows via UI
  - View configured windows
- **4 Services:**
  - `calculate_best_time_window` - Find cheapest consecutive hours
  - `add_time_window` - Dynamically add time windows
  - `remove_time_window` - Remove time windows
  - `get_price_forecast` - Get detailed price forecast
- **Translations:**
  - German (de)
  - English (en)
- Uses official Tibber GraphQL API
- Automatic update interval: 15 minutes
- Smart error handling with data retention on API failures

### Technical
- Built with modern Home Assistant patterns
- Config Flow and Options Flow
- DataUpdateCoordinator for efficient data management
- Async/await with aiohttp for non-blocking HTTP requests
- Type hints throughout codebase
- Comprehensive error handling

[1.0.0]: https://github.com/misterboe/tibber-extended/releases/tag/v1.0.0
