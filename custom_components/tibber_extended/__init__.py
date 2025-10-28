"""The Tibber Extended integration."""
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import (
    CONF_API_KEY,
    CONF_BATTERY_EFFICIENCY,
    DEFAULT_BATTERY_EFFICIENCY,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)
from .coordinator import TibberDataUpdateCoordinator
from .time_window import TimeWindowManager

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Tibber Extended from a config entry."""
    api_key = entry.data[CONF_API_KEY]
    battery_efficiency = entry.data.get(
        CONF_BATTERY_EFFICIENCY, DEFAULT_BATTERY_EFFICIENCY
    )

    coordinator = TibberDataUpdateCoordinator(
        hass,
        api_key=api_key,
        update_interval=DEFAULT_SCAN_INTERVAL,
        battery_efficiency=battery_efficiency,
    )

    # Fetch initial data
    # This will raise ConfigEntryNotReady if connection fails
    try:
        await coordinator.async_config_entry_first_refresh()
    except Exception as err:
        raise ConfigEntryNotReady(f"Unable to connect to Tibber API: {err}") from err

    # Initialize TimeWindowManager
    window_manager = TimeWindowManager(hass, entry, coordinator)

    # Store coordinator and window manager
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator
    hass.data[DOMAIN][f"{entry.entry_id}_window_manager"] = window_manager

    # Setup platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register services
    await async_setup_services(hass, entry, coordinator, window_manager)

    # Setup options update listener
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
        hass.data[DOMAIN].pop(f"{entry.entry_id}_window_manager", None)

        # Unregister services if this was the last entry
        if not hass.config_entries.async_entries(DOMAIN):
            hass.services.async_remove(DOMAIN, "calculate_best_time_window")
            hass.services.async_remove(DOMAIN, "add_time_window")
            hass.services.async_remove(DOMAIN, "remove_time_window")
            hass.services.async_remove(DOMAIN, "get_price_forecast")

    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry when options change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_setup_services(
    hass: HomeAssistant,
    entry: ConfigEntry,
    coordinator: TibberDataUpdateCoordinator,
    window_manager: TimeWindowManager,
) -> None:
    """Set up services for Tibber Extended."""
    from . import services

    # Only register services once (for first config entry)
    if hass.services.has_service(DOMAIN, "calculate_best_time_window"):
        return

    await services.async_setup_services(hass, coordinator, window_manager)
