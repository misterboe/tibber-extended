# Tibber Extended für Home Assistant

Home Assistant Custom Component für intelligente Strompreissteuerung mit Tibber.

## Features

- **7 Sensoren** für Preisinformationen
- **7 Binary Sensoren** zum direkten Schalten von Geräten
- Nutzt die offiziellen Tibber API Preis-Level (VERY_CHEAP, CHEAP, NORMAL, EXPENSIVE, VERY_EXPENSIVE)
- Automatische Identifikation der 3 günstigsten/teuersten Stunden des Tages
- Perfekt für Smart Charging (Tesla, BYD Battery, etc.)

## Installation

### Schritt 1: Custom Component kopieren

Kopiere den `custom_components/tibber_extended` Ordner in dein Home Assistant `config` Verzeichnis:

```
/config/custom_components/tibber_extended/
```

### Schritt 2: Konfiguration

Füge folgendes in deine `configuration.yaml` ein:

```yaml
tibber_extended:
  - api_key: "YOUR_TIBBER_API_KEY_HERE"
    # Optional: home_id (wenn du mehrere Häuser hast)
    # home_id: "YOUR_HOME_ID_HERE"
```

**Tibber API Key bekommen:**
1. Gehe zu https://developer.tibber.com/
2. Melde dich mit deinem Tibber Account an
3. Generiere einen Personal Access Token

### Schritt 3: Home Assistant neu starten

Starte Home Assistant neu, damit die Integration geladen wird.

## Verfügbare Sensoren

### Preis-Sensoren

| Sensor | Beschreibung | Einheit |
|--------|--------------|---------|
| `sensor.tibber_current_price` | Aktueller Strompreis | EUR/kWh |
| `sensor.tibber_average_price` | Durchschnittspreis heute | EUR/kWh |
| `sensor.tibber_min_price` | Günstigster Preis heute | EUR/kWh |
| `sensor.tibber_max_price` | Teuerster Preis heute | EUR/kWh |
| `sensor.tibber_price_level` | Aktuelles Preis-Level | VERY_CHEAP, CHEAP, NORMAL, EXPENSIVE, VERY_EXPENSIVE |
| `sensor.tibber_cheapest_hours` | Die 3 günstigsten Stunden | Text mit Zeiten und Preisen |
| `sensor.tibber_most_expensive_hours` | Die 3 teuersten Stunden | Text mit Zeiten und Preisen |

**Zusätzliche Attribute bei `sensor.tibber_current_price`:**
- `energy`: Reiner Energiepreis ohne Steuern
- `tax`: Steueranteil
- `level`: Preis-Level
- `starts_at`: Zeitstempel
- `today`: Alle heutigen Stundenpreise
- `tomorrow`: Alle morgigen Stundenpreise (ab ~13 Uhr verfügbar)

### Binary Sensoren (zum Schalten)

| Binary Sensor | Wann ON? | Verwendung |
|---------------|----------|------------|
| `binary_sensor.tibber_is_very_cheap` | Preis ist VERY_CHEAP | Sofort laden! |
| `binary_sensor.tibber_is_cheap` | Preis ist CHEAP oder VERY_CHEAP | Gute Ladezeit |
| `binary_sensor.tibber_is_expensive` | Preis ist EXPENSIVE oder VERY_EXPENSIVE | Laden vermeiden |
| `binary_sensor.tibber_is_very_expensive` | Preis ist VERY_EXPENSIVE | Definitiv nicht laden! |
| `binary_sensor.tibber_is_cheapest_hour` | Aktuelle Stunde ist Top 3 günstigste | Smart Charging |
| `binary_sensor.tibber_is_most_expensive_hour` | Aktuelle Stunde ist Top 3 teuerste | Batterie entladen |
| `binary_sensor.tibber_is_good_charging_time` | Kombination: CHEAP oder Top 3 | **Haupt-Sensor zum Laden** |

## Verwendungsbeispiele

### 1. Tesla bei günstigen Preisen laden

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

### 2. BYD Batterie bei sehr günstigen Preisen laden

```yaml
automation:
  - alias: "BYD Battery Smart Charge"
    trigger:
      - platform: state
        entity_id: binary_sensor.tibber_is_very_cheap
        to: "on"
    condition:
      - condition: numeric_state
        entity_id: sensor.byd_soc
        below: 90
    action:
      # Hier dein Service zum Batterie laden
      - service: notify.mobile_app
        data:
          message: "BYD Batterie wird geladen - Strom ist sehr günstig ({{ states('sensor.tibber_current_price') }} EUR/kWh)"
```

### 3. Batterie bei teuren Preisen entladen

```yaml
automation:
  - alias: "BYD Battery Discharge at High Prices"
    trigger:
      - platform: state
        entity_id: binary_sensor.tibber_is_expensive
        to: "on"
    condition:
      - condition: numeric_state
        entity_id: sensor.byd_soc
        above: 50
    action:
      # Hier dein Service zum Batterie entladen
      - service: notify.mobile_app
        data:
          message: "BYD Batterie entlädt - Strom ist teuer ({{ states('sensor.tibber_current_price') }} EUR/kWh)"
```

### 4. Benachrichtigung bei den 3 günstigsten Stunden

```yaml
automation:
  - alias: "Notify Cheapest Hours"
    trigger:
      - platform: state
        entity_id: binary_sensor.tibber_is_cheapest_hour
        to: "on"
    action:
      - service: notify.mobile_app
        data:
          title: "⚡ Günstige Stunde!"
          message: >
            Jetzt ist eine der 3 günstigsten Stunden heute!
            Aktueller Preis: {{ states('sensor.tibber_current_price') }} EUR/kWh
            Durchschnitt: {{ states('sensor.tibber_average_price') }} EUR/kWh
```

### 5. Dashboard Karte

```yaml
type: entities
title: Tibber Strompreise
entities:
  - entity: sensor.tibber_current_price
    name: Aktueller Preis
  - entity: sensor.tibber_average_price
    name: Durchschnitt Heute
  - entity: sensor.tibber_price_level
    name: Preis-Level
  - type: divider
  - entity: binary_sensor.tibber_is_good_charging_time
    name: Gute Ladezeit
  - entity: binary_sensor.tibber_is_cheapest_hour
    name: Top 3 Günstigste Stunde
  - entity: binary_sensor.tibber_is_expensive
    name: Teuer
  - type: divider
  - entity: sensor.tibber_cheapest_hours
    name: Günstigste Stunden
  - entity: sensor.tibber_most_expensive_hours
    name: Teuerste Stunden
```

### 6. Erweiterte Automatisierung mit Bedingungen

```yaml
automation:
  - alias: "Smart Home Energy Management"
    trigger:
      - platform: time_pattern
        minutes: "/5"  # Alle 5 Minuten prüfen
    action:
      - choose:
          # Fall 1: VERY_CHEAP -> Alles laden
          - conditions:
              - condition: state
                entity_id: binary_sensor.tibber_is_very_cheap
                state: "on"
            sequence:
              - service: switch.turn_on
                target:
                  entity_id:
                    - switch.tesla_charger
                    - switch.heat_pump_boost
              - service: notify.mobile_app
                data:
                  message: "Strom sehr günstig - alle Verbraucher aktiviert"

          # Fall 2: CHEAP -> Nur essentielles laden
          - conditions:
              - condition: state
                entity_id: binary_sensor.tibber_is_cheap
                state: "on"
            sequence:
              - service: switch.turn_on
                target:
                  entity_id: switch.tesla_charger

          # Fall 3: EXPENSIVE -> Batterie nutzen
          - conditions:
              - condition: state
                entity_id: binary_sensor.tibber_is_expensive
                state: "on"
            sequence:
              - service: switch.turn_off
                target:
                  entity_id:
                    - switch.tesla_charger
                    - switch.heat_pump_boost
```

## Preis-Level Erklärung

Die Tibber API berechnet automatisch das Preis-Level basierend auf dem Durchschnitt:

- **VERY_CHEAP**: Deutlich unter Durchschnitt (ca. < 70%)
- **CHEAP**: Unter Durchschnitt (ca. 70-90%)
- **NORMAL**: Um den Durchschnitt (ca. 90-110%)
- **EXPENSIVE**: Über Durchschnitt (ca. 110-130%)
- **VERY_EXPENSIVE**: Deutlich über Durchschnitt (ca. > 130%)

*Die genauen Schwellwerte werden von Tibber berechnet.*

## Update-Intervall

Die Integration holt alle **5 Minuten** neue Daten von der Tibber API.

## Troubleshooting

### Integration lädt nicht

1. Prüfe die Logs: `Settings -> System -> Logs`
2. Suche nach Fehlern mit "tibber_extended"
3. Stelle sicher, dass der API Key korrekt ist

### Sensoren zeigen "unavailable"

1. Prüfe deine Internet-Verbindung
2. Prüfe ob der Tibber API Key noch gültig ist
3. Restart Home Assistant

### Morgen-Preise nicht verfügbar

Die Preise für morgen werden von Tibber erst **ab ca. 13 Uhr** bereitgestellt.

## Support

Bei Fragen oder Problemen:
1. Prüfe die Home Assistant Logs
2. Erstelle ein Issue auf GitHub
3. Tibber Developer Docs: https://developer.tibber.com/

## Lizenz

MIT License
