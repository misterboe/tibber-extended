"""The Tibber Smart Control integration."""
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import CONF_API_KEY, CONF_HOME_ID, DEFAULT_SCAN_INTERVAL, DOMAIN
from .coordinator import TibberDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Tibber Smart Control from a config entry."""
    api_key = entry.data[CONF_API_KEY]
    home_id = entry.data.get(CONF_HOME_ID)

    coordinator = TibberDataUpdateCoordinator(
        hass,
        api_key=api_key,
        home_id=home_id,
        update_interval=DEFAULT_SCAN_INTERVAL,
    )

    # Fetch initial data
    # This will raise ConfigEntryNotReady if connection fails
    try:
        await coordinator.async_config_entry_first_refresh()
    except Exception as err:
        raise ConfigEntryNotReady(f"Unable to connect to Tibber API: {err}") from err

    # Store coordinator
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    # Setup platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
