"""The Met Office Charts integration."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import voluptuous as vol

from .const import (
    CONF_API_KEY,
    CONF_ORDER_ID,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    SERVICE_REFRESH_ALL,
    SERVICE_REFRESH_ORDER,
)
from .coordinator import MetOfficeChartsCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.IMAGE]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Met Office Charts from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    session = async_get_clientsession(hass)

    scan_interval = entry.options.get(
        CONF_SCAN_INTERVAL,
        entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
    )

    coordinator = MetOfficeChartsCoordinator(
        hass,
        session,
        api_key=entry.data[CONF_API_KEY],
        order_id=entry.data[CONF_ORDER_ID],
        scan_interval=scan_interval,
    )

    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
        CONF_ORDER_ID: entry.data[CONF_ORDER_ID],
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Setup options update listener
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    # Register services (once)
    if not hass.data[DOMAIN].get("_services_registered"):
        await async_setup_services(hass)
        hass.data[DOMAIN]["_services_registered"] = True

    _LOGGER.info(
        "Set up Met Office Charts for order '%s' with %d minute refresh interval",
        entry.data[CONF_ORDER_ID],
        scan_interval,
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

        # Remove services if this was the last entry
        if len([k for k in hass.data[DOMAIN].keys() if k != "_services_registered"]) == 0:
            hass.services.async_remove(DOMAIN, SERVICE_REFRESH_ORDER)
            hass.services.async_remove(DOMAIN, SERVICE_REFRESH_ALL)
            hass.data[DOMAIN].pop("_services_registered", None)

    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    # Clean up entities if order_id changed (shouldn't happen, but handle it)
    entity_reg = er.async_get(hass)

    old_order_id = entry.options.get("_old_order_id", entry.data.get(CONF_ORDER_ID))
    new_order_id = entry.data.get(CONF_ORDER_ID)

    if old_order_id and old_order_id != new_order_id:
        _LOGGER.info(
            "Order ID changed from %s to %s - removing old entities",
            old_order_id,
            new_order_id,
        )
        to_remove = []
        for entity_entry in list(entity_reg.entities.values()):
            if (
                entity_entry.config_entry_id == entry.entry_id
                and f"_{old_order_id}_" in entity_entry.unique_id
            ):
                to_remove.append(entity_entry.entity_id)

        for entity_id in to_remove:
            entity_reg.async_remove(entity_id)

        _LOGGER.info("Removed %d entities for old order %s", len(to_remove), old_order_id)

        # Store current order_id for future comparisons
        updated_options = {**entry.options, "_old_order_id": new_order_id}
        hass.config_entries.async_update_entry(entry, options=updated_options)

    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)


async def async_setup_services(hass: HomeAssistant) -> None:
    """Set up services for the integration."""

    async def handle_refresh_order(call: ServiceCall) -> None:
        """Handle refresh order service call."""
        order_id = call.data[CONF_ORDER_ID]

        for entry_id, data in hass.data[DOMAIN].items():
            if isinstance(data, dict) and data.get(CONF_ORDER_ID) == order_id:
                coordinator = data["coordinator"]
                _LOGGER.info("Manually refreshing order %s", order_id)
                await coordinator.async_request_refresh()
                return

        _LOGGER.warning("Order %s not found in configured orders", order_id)

    async def handle_refresh_all(call: ServiceCall) -> None:
        """Handle refresh all orders service call."""
        _LOGGER.info("Manually refreshing all Met Office Charts orders")

        for entry_id, data in hass.data[DOMAIN].items():
            if not isinstance(data, dict) or CONF_ORDER_ID not in data:
                continue

            coordinator = data["coordinator"]
            order_id = data[CONF_ORDER_ID]
            _LOGGER.info("Refreshing order %s", order_id)
            await coordinator.async_request_refresh()

    hass.services.async_register(
        DOMAIN,
        SERVICE_REFRESH_ORDER,
        handle_refresh_order,
        schema=vol.Schema(
            {
                vol.Required(CONF_ORDER_ID): cv.string,
            }
        ),
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_REFRESH_ALL,
        handle_refresh_all,
    )
