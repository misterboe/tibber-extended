"""The Tibber Extended integration."""
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import (
    CONF_API_KEY,
    CONF_BATTERY_EFFICIENCY,
    CONF_HOURS_DURATION,
    CONF_TIME_WINDOW_END,
    CONF_TIME_WINDOW_START,
    DEFAULT_BATTERY_EFFICIENCY,
    DEFAULT_HOURS_DURATION,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_TIME_WINDOW_END,
    DEFAULT_TIME_WINDOW_START,
    DOMAIN,
)
from .coordinator import TibberDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Tibber Extended from a config entry."""
    # Migrate: Initialize options if not present (for existing installations)
    if not entry.options:
        hass.config_entries.async_update_entry(
            entry,
            options={
                CONF_HOURS_DURATION: DEFAULT_HOURS_DURATION,
                CONF_TIME_WINDOW_START: DEFAULT_TIME_WINDOW_START,
                CONF_TIME_WINDOW_END: DEFAULT_TIME_WINDOW_END,
            },
        )
    # Migrate: Add time window settings to existing options if not present
    elif CONF_TIME_WINDOW_START not in entry.options:
        hass.config_entries.async_update_entry(
            entry,
            options={
                **entry.options,
                CONF_TIME_WINDOW_START: DEFAULT_TIME_WINDOW_START,
                CONF_TIME_WINDOW_END: DEFAULT_TIME_WINDOW_END,
            },
        )

    api_key = entry.data[CONF_API_KEY]
    battery_efficiency = entry.data.get(
        CONF_BATTERY_EFFICIENCY, DEFAULT_BATTERY_EFFICIENCY
    )
    hours_duration = entry.options.get(
        CONF_HOURS_DURATION, DEFAULT_HOURS_DURATION
    )
    time_window_start = entry.options.get(
        CONF_TIME_WINDOW_START, DEFAULT_TIME_WINDOW_START
    )
    time_window_end = entry.options.get(
        CONF_TIME_WINDOW_END, DEFAULT_TIME_WINDOW_END
    )

    coordinator = TibberDataUpdateCoordinator(
        hass,
        api_key=api_key,
        update_interval=DEFAULT_SCAN_INTERVAL,
        battery_efficiency=battery_efficiency,
        hours_duration=hours_duration,
        time_window_start=time_window_start,
        time_window_end=time_window_end,
    )

    # Fetch initial data
    # This will raise ConfigEntryNotReady if connection fails
    try:
        await coordinator.async_config_entry_first_refresh()
    except Exception as err:
        raise ConfigEntryNotReady(f"Unable to connect to Tibber API: {err}") from err

    # Setup hourly refresh at the top of each hour (XX:00:05)
    await coordinator.async_setup_hourly_refresh()

    # Store coordinator
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    # Setup platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register services
    await async_setup_services(hass, coordinator)

    # Setup options update listener
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        coordinator = hass.data[DOMAIN].pop(entry.entry_id)
        # Shutdown coordinator (cancels hourly refresh subscription)
        await coordinator.async_shutdown()

        # Unregister services if this was the last entry
        if not hass.config_entries.async_entries(DOMAIN):
            hass.services.async_remove(DOMAIN, "calculate_best_time_window")
            hass.services.async_remove(DOMAIN, "get_price_forecast")

    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry when options change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_setup_services(
    hass: HomeAssistant,
    coordinator: TibberDataUpdateCoordinator,
) -> None:
    """Set up services for Tibber Extended."""
    from . import services

    # Only register services once (for first config entry)
    if hass.services.has_service(DOMAIN, "calculate_best_time_window"):
        return

    await services.async_setup_services(hass, coordinator)
