# Tibber Extended for Home Assistant

Smart energy price control with Tibber - optimized for automation and battery management.

## Features

- ✅ **Config Flow Setup** - Easy UI-based installation
- 📊 **11+ Sensors** - Complete price information and analytics
- 🔌 **10 Binary Sensors** - Direct automation triggers
- 🔋 **Battery Optimization** - Configurable efficiency settings
- ⏰ **Flexible Time Windows** - Configurable consecutive hours (1-24h)
- 🏠 **Multi-Home Support** - All Tibber homes automatically detected
- 🌍 **Multilingual** - German and English translations
- 🔄 **Smart Updates** - Every 15 minutes with error resilience

## Installation

### via HACS (Recommended)

1. Open HACS in Home Assistant
2. Go to "Integrations"
3. Click "⋮" → "Custom repositories"
4. Add repository URL: `https://github.com/misterboe/tibber-extended`
5. Category: "Integration"
6. Click "Add"
7. Search for "Tibber Extended"
8. Click "Download"
9. Restart Home Assistant

### Manual Installation

1. Copy the `custom_components/tibber_extended` folder to your `config/custom_components` directory
2. Restart Home Assistant

## Configuration

### Step 1: Add Integration

1. Go to **Settings** → **Devices & Services**
2. Click **"+ Add Integration"**
3. Search for **"Tibber Extended"**
4. Enter your **Tibber API Key**
5. Optionally configure **Battery Efficiency** (default: 75%)

**Get your Tibber API Key:**
1. Open https://developer.tibber.com/
2. Login with your Tibber account
3. Generate a "Personal Access Token"

### Step 2: Configure Options (Optional)

After installation, click **"Configure"** to access:

- **Battery Efficiency** - Set charge/discharge efficiency (1-100%, default: 75%)
- **Hours Duration** - Number of consecutive hours for best/worst windows (1-24h, default: 3h)

## Available Sensors

### Price Sensors

| Entity ID | Description | Unit |
|-----------|-------------|------|
| `sensor.tibber_current_price` | Current electricity price | EUR/kWh |
| `sensor.tibber_average_price` | Average price today | EUR/kWh |
| `sensor.tibber_min_price` | Lowest price today | EUR/kWh |
| `sensor.tibber_max_price` | Highest price today | EUR/kWh |
| `sensor.tibber_price_level` | Current price level | VERY_CHEAP / CHEAP / NORMAL / EXPENSIVE / VERY_EXPENSIVE |
| `sensor.tibber_cheapest_hours` | Top 3 cheapest hours | Text |
| `sensor.tibber_most_expensive_hours` | Top 3 most expensive hours | Text |
| `sensor.tibber_best_consecutive_hours` | Best consecutive hours window | Text (configurable duration) |
| `sensor.tibber_price_deviation_percent` | Deviation from average | % |
| `sensor.tibber_price_deviation_absolute` | Absolute deviation | EUR/kWh |
| `sensor.tibber_battery_breakeven_price` | Economical charging threshold | EUR/kWh |

**Extra attributes on `sensor.tibber_current_price`:**
- `current` - Full current price data (total, energy, tax, level, startsAt)
- `today` - All hourly prices for today
- `tomorrow` - All hourly prices for tomorrow (available from ~13:00)
- `average_price`, `min_price`, `max_price`
- `cheapest_hours`, `most_expensive_hours`
- `best_consecutive_hours` - Best consecutive hours window
- `rank`, `percentile` - Current price ranking

### Binary Sensors (Automation Triggers)

| Entity ID | Trigger | Use Case |
|-----------|---------|----------|
| `binary_sensor.tibber_is_very_cheap` | Price is VERY_CHEAP | Instant charging |
| `binary_sensor.tibber_is_cheap` | Price is CHEAP or VERY_CHEAP | Good charging time |
| `binary_sensor.tibber_is_expensive` | Price is EXPENSIVE or VERY_EXPENSIVE | Avoid charging |
| `binary_sensor.tibber_is_very_expensive` | Price is VERY_EXPENSIVE | Definitely avoid! |
| `binary_sensor.tibber_is_cheapest_hour` | In top 3 cheapest hours | Smart scheduling |
| `binary_sensor.tibber_is_most_expensive_hour` | In top 3 most expensive | Battery discharge |
| `binary_sensor.tibber_is_good_charging_time` | CHEAP or top 3 | **Main charging trigger** |
| `binary_sensor.tibber_is_below_average` | Below average price | Cost-effective |
| `binary_sensor.tibber_is_in_best_consecutive_hours` | In best consecutive window | Optimal window |
| `binary_sensor.tibber_battery_charging_recommended` | Below breakeven price | Battery charging |

## Usage Examples

### 1. Tesla Smart Charging

```yaml
automation:
  - alias: "Tesla Smart Charging"
    trigger:
      - platform: state
        entity_id: binary_sensor.tibber_is_good_charging_time
        to: "on"
    condition:
      - condition: numeric_state
        entity_id: sensor.tesla_battery_level
        below: 80
    action:
      - service: switch.turn_on
        target:
          entity_id: switch.tesla_charger
```

### 2. Battery Charging with Efficiency

```yaml
automation:
  - alias: "Battery Smart Charge"
    trigger:
      - platform: state
        entity_id: binary_sensor.tibber_battery_charging_recommended
        to: "on"
    condition:
      - condition: numeric_state
        entity_id: sensor.battery_soc
        below: 90
    action:
      - service: notify.mobile_app
        data:
          message: "Charging economical ({{ states('sensor.tibber_current_price') }}€/kWh < {{ states('sensor.tibber_battery_breakeven_price') }}€/kWh)"
```

### 3. Best Consecutive Hours Window

```yaml
automation:
  - alias: "Charge in Best Window"
    trigger:
      - platform: state
        entity_id: binary_sensor.tibber_is_in_best_consecutive_hours
        to: "on"
    action:
      - service: switch.turn_on
        target:
          entity_id: switch.heavy_load
      - service: notify.mobile_app
        data:
          title: "⚡ Optimal Charging Time"
          message: >
            Now in best {{ state_attr('sensor.tibber_best_consecutive_hours', 'duration_hours') }}h window!
            Average: {{ state_attr('sensor.tibber_best_consecutive_hours', 'average_price') }}€/kWh
```

### 4. Dashboard Card

```yaml
type: entities
title: Tibber Strompreise
entities:
  - entity: sensor.tibber_current_price
    name: Aktueller Preis
  - entity: sensor.tibber_price_level
    name: Preis-Level
  - entity: sensor.tibber_average_price
    name: Durchschnitt
  - type: divider
  - entity: binary_sensor.tibber_is_good_charging_time
    name: Gute Ladezeit
  - entity: binary_sensor.tibber_is_in_best_consecutive_hours
    name: In bestem Zeitfenster
  - entity: binary_sensor.tibber_battery_charging_recommended
    name: Batterie laden empfohlen
  - type: divider
  - entity: sensor.tibber_best_consecutive_hours
    name: Bestes Zeitfenster
  - entity: sensor.tibber_battery_breakeven_price
    name: Batterie Break-Even
```

## Services

### `tibber_extended.calculate_best_time_window`

Calculate the cheapest consecutive time window dynamically.

```yaml
service: tibber_extended.calculate_best_time_window
data:
  duration_hours: 4
  power_kw: 11
  start_after: "14:00"
  end_before: "22:00"
  include_tomorrow: true
```

**Response:**
```yaml
success: true
best_start_time: "15:00"
best_end_time: "19:00"
average_price_window: 0.2145
total_cost: 9.44
savings_vs_average: 1.2
```

### `tibber_extended.get_price_forecast`

Get detailed price forecast.

```yaml
service: tibber_extended.get_price_forecast
data:
  hours_ahead: 24
```

## Multi-Home Support

If you have multiple homes in your Tibber account, **all homes are automatically detected**. Each home gets its own set of sensors with a suffix:

- Single home: `sensor.tibber_current_price`
- Multiple homes: `sensor.tibber_current_price_home1`, `sensor.tibber_current_price_home2`

## Price Levels Explained

Tibber API automatically calculates price levels based on daily average:

- **VERY_CHEAP**: Significantly below average (~< 70%)
- **CHEAP**: Below average (~70-90%)
- **NORMAL**: Around average (~90-110%)
- **EXPENSIVE**: Above average (~110-130%)
- **VERY_EXPENSIVE**: Significantly above average (~> 130%)

*Exact thresholds are calculated by Tibber.*

## Technical Details

- **Update Interval:** 15 minutes
- **API:** Tibber GraphQL API
- **Data Retention:** Last valid data kept during API failures
- **Requirements:** `aiohttp>=3.8.0`
- **Home Assistant:** 2023.9.0 or newer

## Configuration Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `api_key` | string | *required* | Your Tibber API token |
| `battery_efficiency` | int | 75 | Battery efficiency percentage (1-100%) |
| `hours_duration` | int | 3 | Consecutive hours for best/worst windows (1-24h) |

## Troubleshooting

### Integration doesn't load

1. Check Home Assistant logs: **Settings** → **System** → **Logs**
2. Search for errors containing "tibber_extended"
3. Verify API key is correct
4. Check internet connection

### Sensors show "unavailable"

1. Verify internet connection
2. Check if Tibber API key is still valid
3. Restart Home Assistant
4. Check Tibber API status at https://status.tibber.com/

### Tomorrow prices not available

Tomorrow's prices are published by Tibber **around 13:00 CET** each day.

### Entity ID changed after update

**Breaking change in v1.0.0:**
- `sensor.tibber_best_3_hours` → `sensor.tibber_best_consecutive_hours`
- `binary_sensor.tibber_is_in_best_3h_window` → `binary_sensor.tibber_is_in_best_consecutive_hours`

Update your automations accordingly.

## Support

- **Issues:** https://github.com/misterboe/tibber-extended/issues
- **Tibber Developer Docs:** https://developer.tibber.com/
- **Home Assistant Community:** https://community.home-assistant.io/

## License

MIT License - see [LICENSE](LICENSE) file for details

## Credits

Developed by [@misterboe](https://github.com/misterboe)
