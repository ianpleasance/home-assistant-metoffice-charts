"""Config flow for Met Office Charts integration."""
from __future__ import annotations

import logging
from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_API_KEY,
    CONF_ORDER_ID,
    CONF_SCAN_INTERVAL,
    DATAHUB_BASE_URL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)


class MetOfficeChartsConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Met Office Charts."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            # Validate the API key and order ID
            api_key = user_input[CONF_API_KEY]
            order_id = user_input[CONF_ORDER_ID]

            validation_result = await self._validate_credentials(api_key, order_id)

            if validation_result is True:
                # Create unique ID from order_id
                await self.async_set_unique_id(f"{DOMAIN}_{order_id}")
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=f"Met Office Charts ({order_id})",
                    data=user_input,
                )
            else:
                errors["base"] = validation_result

        data_schema = vol.Schema(
            {
                vol.Required(CONF_API_KEY): str,
                vol.Required(CONF_ORDER_ID): str,
                vol.Required(
                    CONF_SCAN_INTERVAL,
                    default=DEFAULT_SCAN_INTERVAL,
                ): vol.All(
                    vol.Coerce(int),
                    vol.Range(min=MIN_SCAN_INTERVAL, max=MAX_SCAN_INTERVAL),
                ),
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
            description_placeholders={
                "register_url": "https://datahub.metoffice.gov.uk/",
                "min_interval": str(MIN_SCAN_INTERVAL),
                "max_interval": str(MAX_SCAN_INTERVAL),
            },
        )

    async def _validate_credentials(
        self, api_key: str, order_id: str
    ) -> bool | str:
        """Validate the DataHub API credentials.

        Returns True if valid, or an error key string if invalid.
        """
        try:
            session = async_get_clientsession(self.hass)
            # Test with a files list request
            test_url = f"{DATAHUB_BASE_URL}/orders/{order_id}/latest"
            headers = {"apikey": api_key}

            async with session.get(
                test_url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                if response.status == 200:
                    return True
                elif response.status == 401:
                    _LOGGER.warning("Invalid API key for order %s", order_id)
                    return "invalid_api_key"
                elif response.status == 404:
                    _LOGGER.warning("Order %s not found", order_id)
                    return "order_not_found"
                else:
                    _LOGGER.warning(
                        "API validation failed with status %d for order %s",
                        response.status,
                        order_id,
                    )
                    return "cannot_connect"

        except aiohttp.ClientError as err:
            _LOGGER.error("Network error validating credentials: %s", err)
            return "cannot_connect"
        except Exception as err:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected error validating credentials: %s", err)
            return "unknown"

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        return MetOfficeChartsOptionsFlow() 


class MetOfficeChartsOptionsFlow(config_entries.OptionsFlow):
    """Handle options flow for Met Office Charts."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            # Update the config entry
            updated_data = {
                **self.config_entry.data,
                CONF_SCAN_INTERVAL: user_input[CONF_SCAN_INTERVAL],
            }

            self.hass.config_entries.async_update_entry(
                self.config_entry, data=updated_data
            )

            return self.async_create_entry(title="", data={})

        current_interval = self.config_entry.data.get(
            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
        )

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_SCAN_INTERVAL,
                    default=current_interval,
                ): vol.All(
                    vol.Coerce(int),
                    vol.Range(min=MIN_SCAN_INTERVAL, max=MAX_SCAN_INTERVAL),
                ),
            }
        )

        return self.async_show_form(
            step_id="init",
            data_schema=schema,
            description_placeholders={
                "min_interval": str(MIN_SCAN_INTERVAL),
                "max_interval": str(MAX_SCAN_INTERVAL),
            },
        )
