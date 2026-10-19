"""Config flow for MSI Mystic Light."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_TOKEN
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import NumberSelector, NumberSelectorConfig, NumberSelectorMode

from .api import MysticLightApi, MysticLightAuthError, MysticLightError
from .const import CONF_MAX_POWER, DEFAULT_MAX_POWER, DEFAULT_PORT, DOMAIN

SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
        vol.Optional(CONF_TOKEN, default=""): str,
    }
)


class MysticLightConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> MysticLightOptionsFlow:
        return MysticLightOptionsFlow()

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            await self.async_set_unique_id(f"{user_input[CONF_HOST]}:{user_input[CONF_PORT]}")
            self._abort_if_unique_id_configured()
            api = MysticLightApi(
                async_get_clientsession(self.hass),
                user_input[CONF_HOST],
                user_input[CONF_PORT],
                user_input[CONF_TOKEN],
            )
            try:
                leds = await api.get_leds()
            except MysticLightAuthError:
                errors["base"] = "invalid_auth"
            except MysticLightError:
                errors["base"] = "cannot_connect"
            else:
                if not leds:
                    errors["base"] = "no_leds"
                else:
                    return self.async_create_entry(
                        title=f"Mystic Light ({user_input[CONF_HOST]})", data=user_input
                    )
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(SCHEMA, user_input),
            errors=errors,
        )


class MysticLightOptionsFlow(OptionsFlow):
    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        current = self.config_entry.options.get(CONF_MAX_POWER, DEFAULT_MAX_POWER)
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_MAX_POWER, default=current): NumberSelector(
                        NumberSelectorConfig(
                            min=10, max=100, step=5, unit_of_measurement="%", mode=NumberSelectorMode.SLIDER
                        )
                    )
                }
            ),
        )
