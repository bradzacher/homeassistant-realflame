"""Config flow for Real Flame."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector

from .client import RealFlameClient
from .const import (
    CONF_AUTO_OFF_HOURS,
    CONF_BLOCK_TURN_ON,
    CONF_HOST,
    CONF_NAME,
    CONF_POLL_INTERVAL,
    CONF_PORT,
    DEFAULT_AUTO_OFF_HOURS,
    DEFAULT_NAME,
    DEFAULT_POLL_INTERVAL,
    DEFAULT_PORT,
    DOMAIN,
)


class RealFlameConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            port = int(user_input.get(CONF_PORT, DEFAULT_PORT))
            await self.async_set_unique_id(f"{host}:{port}")
            self._abort_if_unique_id_configured()
            client = RealFlameClient(host, port)
            try:
                await client.async_validate()
            except Exception:
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(
                    title=user_input.get(CONF_NAME) or DEFAULT_NAME,
                    data={
                        CONF_HOST: host,
                        CONF_PORT: port,
                        CONF_NAME: user_input.get(CONF_NAME) or DEFAULT_NAME,
                        CONF_POLL_INTERVAL: user_input.get(
                            CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL
                        ),
                        CONF_AUTO_OFF_HOURS: user_input.get(
                            CONF_AUTO_OFF_HOURS, DEFAULT_AUTO_OFF_HOURS
                        ),
                        CONF_BLOCK_TURN_ON: user_input.get(CONF_BLOCK_TURN_ON, False),
                    },
                )

        schema = vol.Schema(
            {
                vol.Required(CONF_HOST): selector.TextSelector(),
                vol.Optional(CONF_PORT, default=DEFAULT_PORT): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=1, max=65535, mode=selector.NumberSelectorMode.BOX
                    )
                ),
                vol.Optional(CONF_NAME, default=DEFAULT_NAME): selector.TextSelector(),
                vol.Optional(
                    CONF_POLL_INTERVAL, default=DEFAULT_POLL_INTERVAL
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=15, max=300, mode=selector.NumberSelectorMode.BOX
                    )
                ),
                vol.Optional(
                    CONF_AUTO_OFF_HOURS, default=DEFAULT_AUTO_OFF_HOURS
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0,
                        max=24,
                        step=0.5,
                        mode=selector.NumberSelectorMode.BOX,
                    )
                ),
                vol.Optional(CONF_BLOCK_TURN_ON, default=False): selector.BooleanSelector(),
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):
        return RealFlameOptionsFlow(config_entry)


class RealFlameOptionsFlow(config_entries.OptionsFlow):
    """Options: poll / auto-off / block turn-on."""

    def __init__(self, entry: config_entries.ConfigEntry) -> None:
        self._entry = entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)
        data = {**self._entry.data, **self._entry.options}
        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_POLL_INTERVAL,
                    default=data.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=15, max=300, mode=selector.NumberSelectorMode.BOX
                    )
                ),
                vol.Optional(
                    CONF_AUTO_OFF_HOURS,
                    default=data.get(CONF_AUTO_OFF_HOURS, DEFAULT_AUTO_OFF_HOURS),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0,
                        max=24,
                        step=0.5,
                        mode=selector.NumberSelectorMode.BOX,
                    )
                ),
                vol.Optional(
                    CONF_BLOCK_TURN_ON,
                    default=data.get(CONF_BLOCK_TURN_ON, False),
                ): selector.BooleanSelector(),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
