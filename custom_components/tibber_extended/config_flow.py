"""Config flow for Tibber Extended integration."""
from __future__ import annotations

import logging
from typing import Any

import requests
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError

from .const import (
    CONF_API_KEY,
    CONF_BATTERY_EFFICIENCY,
    DEFAULT_BATTERY_EFFICIENCY,
    DOMAIN,
    TIBBER_API_URL,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_KEY): str,
        vol.Optional(
            CONF_BATTERY_EFFICIENCY, default=DEFAULT_BATTERY_EFFICIENCY
        ): vol.All(vol.Coerce(float), vol.Range(min=1, max=100)),
    }
)


async def validate_api_key(hass: HomeAssistant, api_key: str) -> dict[str, Any]:
    """Validate the API key by making a test request."""
    query = """
    {
      viewer {
        homes {
          id
          appNickname
        }
      }
    }
    """

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    try:
        response = await hass.async_add_executor_job(
            lambda: requests.post(
                TIBBER_API_URL,
                json={"query": query},
                headers=headers,
                timeout=10,
            )
        )

        if response.status_code == 401:
            raise InvalidAuth

        if response.status_code != 200:
            raise CannotConnect

        data = response.json()

        if "errors" in data:
            raise InvalidAuth

        homes = data.get("data", {}).get("viewer", {}).get("homes", [])

        if not homes:
            raise NoHomes

        return {"homes": homes}

    except requests.exceptions.RequestException as err:
        raise CannotConnect from err


class TibberConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Tibber Extended."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                info = await validate_api_key(self.hass, user_input[CONF_API_KEY])

                # Create a unique ID based on API key
                await self.async_set_unique_id(user_input[CONF_API_KEY])
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title="Tibber Extended",
                    data=user_input,
                )

            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except NoHomes:
                errors["base"] = "no_homes"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> TibberOptionsFlowHandler:
        """Get the options flow for this handler."""
        return TibberOptionsFlowHandler()


class TibberOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow for Tibber Extended - Time Window Management."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage time windows and battery settings."""
        return self.async_show_menu(
            step_id="init",
            menu_options=[
                "battery_settings",
                "add_window",
                "remove_window",
                "list_windows",
            ],
        )

    async def async_step_add_window(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Add a new time window."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Validate window name
            name = user_input["name"].strip().lower().replace(" ", "_")

            if not name.replace("_", "").replace("-", "").isalnum():
                errors["name"] = "invalid_name"
            else:
                # Add window via TimeWindowManager
                from .time_window import TimeWindowManager

                window_manager: TimeWindowManager = self.hass.data[DOMAIN].get(
                    f"{self.config_entry.entry_id}_window_manager"
                )

                if window_manager:
                    success = await window_manager.add_window(
                        name=name,
                        duration=user_input["duration"],
                        power_kw=user_input.get("power_kw"),
                    )

                    if success:
                        return self.async_create_entry(title="", data={})
                    else:
                        errors["name"] = "already_exists"

        return self.async_show_form(
            step_id="add_window",
            data_schema=vol.Schema(
                {
                    vol.Required("name"): str,
                    vol.Required("duration", default=3.0): vol.All(
                        vol.Coerce(float), vol.Range(min=0.5, max=24.0)
                    ),
                    vol.Optional("power_kw"): vol.All(
                        vol.Coerce(float), vol.Range(min=0.1, max=50.0)
                    ),
                }
            ),
            errors=errors,
        )

    async def async_step_remove_window(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Remove a time window."""
        from .time_window import TimeWindowManager

        window_manager: TimeWindowManager = self.hass.data[DOMAIN].get(
            f"{self.config_entry.entry_id}_window_manager"
        )

        if not window_manager:
            return self.async_abort(reason="no_window_manager")

        windows = window_manager.get_all_windows()

        if not windows:
            return self.async_abort(reason="no_windows")

        if user_input is not None:
            name = user_input["window_name"]
            await window_manager.remove_window(name)
            return self.async_create_entry(title="", data={})

        # Create selection dict
        window_options = {name: name for name in windows.keys()}

        return self.async_show_form(
            step_id="remove_window",
            data_schema=vol.Schema(
                {
                    vol.Required("window_name"): vol.In(window_options),
                }
            ),
        )

    async def async_step_list_windows(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """List all configured time windows."""
        from .time_window import TimeWindowManager

        window_manager: TimeWindowManager = self.hass.data[DOMAIN].get(
            f"{self.config_entry.entry_id}_window_manager"
        )

        if not window_manager:
            return self.async_abort(reason="no_window_manager")

        windows = window_manager.get_all_windows()

        if not windows:
            return self.async_abort(reason="no_windows")

        # Build description
        description = "**Configured Time Windows:**\n\n"
        for window in windows.values():
            power_info = f"{window.power_kw} kW" if window.power_kw else "No power specified"
            description += f"- **{window.name}**: {window.duration_hours}h, {power_info}\n"

        return self.async_show_form(
            step_id="list_windows",
            description_placeholders={"windows_info": description},
        )

    async def async_step_battery_settings(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Configure battery efficiency settings."""
        if user_input is not None:
            # Update config entry data with new battery efficiency
            self.hass.config_entries.async_update_entry(
                self.config_entry,
                data={
                    **self.config_entry.data,
                    CONF_BATTERY_EFFICIENCY: user_input[CONF_BATTERY_EFFICIENCY],
                },
            )
            return self.async_create_entry(title="", data={})

        # Get current battery efficiency from config
        current_efficiency = self.config_entry.data.get(
            CONF_BATTERY_EFFICIENCY, DEFAULT_BATTERY_EFFICIENCY
        )

        return self.async_show_form(
            step_id="battery_settings",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_BATTERY_EFFICIENCY, default=current_efficiency
                    ): vol.All(vol.Coerce(float), vol.Range(min=1, max=100)),
                }
            ),
            description_placeholders={
                "current_efficiency": f"{current_efficiency}%",
            },
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""


class NoHomes(HomeAssistantError):
    """Error to indicate no homes found in account."""
