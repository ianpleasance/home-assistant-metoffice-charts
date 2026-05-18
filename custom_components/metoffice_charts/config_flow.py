"""Config flow for MAVIS Aviation Charts."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from .auth import authenticate
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
import homeassistant.helpers.config_validation as cv

from .const import (
    DOMAIN,
    CONF_AUTH_TOKEN,
    CONF_USERNAME,
    CONF_PASSWORD,
    CONF_CHARTS,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
    MAX_SCAN_INTERVAL,
    CHART_DEFINITIONS,
    DEFAULT_CHARTS,
)

_LOGGER = logging.getLogger(__name__)







class MavisChartsConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for MAVIS Aviation Charts."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Single step — credentials and chart selection."""
        errors: dict[str, str] = {}

        if user_input is not None:
            username = user_input[CONF_USERNAME].strip()
            password = user_input[CONF_PASSWORD]

            result = await self.hass.async_add_executor_job(
                authenticate, username, password
            )
            if result:
                auth_token, _ = result
                selected = user_input.get(CONF_CHARTS, DEFAULT_CHARTS) or DEFAULT_CHARTS
                return self.async_create_entry(
                    title="MAVIS Aviation Charts",
                    data={
                        CONF_USERNAME: username,
                        CONF_PASSWORD: password,
                        CONF_AUTH_TOKEN: auth_token,
                        CONF_CHARTS: selected,
                        CONF_SCAN_INTERVAL: user_input.get(
                            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                        ),
                    },
                )
            else:
                errors["base"] = "invalid_auth"

        chart_options = {
            key: f"{defn[0]} — {defn[1]}"
            for key, defn in CHART_DEFINITIONS.items()
        }

        schema = vol.Schema({
            vol.Required(CONF_USERNAME): str,
            vol.Required(CONF_PASSWORD): str,
            vol.Required(CONF_CHARTS, default=DEFAULT_CHARTS): cv.multi_select(chart_options),
            vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): vol.All(
                vol.Coerce(int), vol.Range(min=MIN_SCAN_INTERVAL, max=MAX_SCAN_INTERVAL)
            ),
        })

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> MavisChartsOptionsFlow:
        """Return the options flow."""
        return MavisChartsOptionsFlow()


class MavisChartsOptionsFlow(config_entries.OptionsFlow):
    """Handle options for MAVIS Aviation Charts."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage options."""
        errors: dict[str, str] = {}
        current = {**self.config_entry.data, **self.config_entry.options}

        if user_input is not None:
            username = user_input[CONF_USERNAME].strip()
            password = user_input[CONF_PASSWORD]

            result = await self.hass.async_add_executor_job(
                authenticate, username, password
            )
            if result:
                auth_token, _ = result
                new_data = {
                    **current,
                    CONF_USERNAME: username,
                    CONF_PASSWORD: password,
                    CONF_AUTH_TOKEN: auth_token,
                    CONF_CHARTS: [
                        k for k in user_input.get(CONF_CHARTS, DEFAULT_CHARTS)
                        if k in CHART_DEFINITIONS
                    ],
                    CONF_SCAN_INTERVAL: user_input.get(
                        CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                    ),
                }
                return self.async_create_entry(title="MAVIS Aviation Charts", data=new_data)
            else:
                errors["base"] = "invalid_auth"

        chart_options = {
            key: f"{defn[0]} — {defn[1]}"
            for key, defn in CHART_DEFINITIONS.items()
        }

        schema = vol.Schema({
            vol.Required(CONF_USERNAME, default=current.get(CONF_USERNAME, "")): str,
            vol.Required(CONF_PASSWORD): str,
            vol.Required(
                CONF_CHARTS,
                default=[k for k in current.get(CONF_CHARTS, DEFAULT_CHARTS) if k in CHART_DEFINITIONS],
            ): cv.multi_select(chart_options),
            vol.Optional(
                CONF_SCAN_INTERVAL,
                default=current.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
            ): vol.All(
                vol.Coerce(int), vol.Range(min=MIN_SCAN_INTERVAL, max=MAX_SCAN_INTERVAL)
            ),
        })

        return self.async_show_form(
            step_id="init",
            data_schema=schema,
            errors=errors,
        )
