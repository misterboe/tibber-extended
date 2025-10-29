"""Config flow for Tibber Extended integration."""
from __future__ import annotations

import logging
from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import selector

from .const import (
    CONF_API_KEY,
    CONF_BATTERY_EFFICIENCY,
    CONF_HOURS_DURATION,
    DEFAULT_BATTERY_EFFICIENCY,
    DEFAULT_HOURS_DURATION,
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
        async with aiohttp.ClientSession() as session:
            async with session.post(
                TIBBER_API_URL,
                json={"query": query},
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as response:
                if response.status == 401:
                    raise InvalidAuth

                if response.status != 200:
                    raise CannotConnect

                data = await response.json()

                if "errors" in data:
                    raise InvalidAuth

                homes = data.get("data", {}).get("viewer", {}).get("homes", [])

                if not homes:
                    raise NoHomes

                return {"homes": homes}

    except aiohttp.ClientError as err:
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
                    options={
                        CONF_HOURS_DURATION: DEFAULT_HOURS_DURATION,
                    },
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
        """Manage battery settings and hours duration."""
        return self.async_show_menu(
            step_id="init",
            menu_options=[
                "battery_settings",
                "hours_duration",
            ],
        )

    async def async_step_hours_duration(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Configure hours duration setting."""
        if user_input is not None:
            # Update config entry options with new hours duration
            self.hass.config_entries.async_update_entry(
                self.config_entry,
                options={
                    **self.config_entry.options,
                    CONF_HOURS_DURATION: user_input[CONF_HOURS_DURATION],
                },
            )
            return self.async_create_entry(title="", data={})

        # Get current hours duration from options
        current_duration = self.config_entry.options.get(
            CONF_HOURS_DURATION, DEFAULT_HOURS_DURATION
        )

        return self.async_show_form(
            step_id="hours_duration",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_HOURS_DURATION, default=int(current_duration)
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=1, max=24, mode=selector.NumberSelectorMode.BOX
                        )
                    ),
                }
            ),
            description_placeholders={
                "current_duration": f"{int(current_duration)}",
            },
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
