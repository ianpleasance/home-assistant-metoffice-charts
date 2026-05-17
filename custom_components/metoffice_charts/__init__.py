"""The MAVIS Aviation Charts integration."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers import entity_registry as er

from .const import (
    DOMAIN,
    CONF_AUTH_TOKEN,
    CONF_USERNAME,
    CONF_PASSWORD,
    CONF_CHARTS,
    CONF_SCAN_INTERVAL,
)
try:
    from .coordinator import MavisChartsCoordinator
except Exception as _import_err:
    import logging
    logging.getLogger(__name__).exception("Failed to import coordinator: %s", _import_err)
    raise

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.IMAGE, Platform.SENSOR]


def _entry_data(entry: ConfigEntry) -> dict:
    """Return merged entry data, with options taking precedence."""
    return {**entry.data, **entry.options}


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up MAVIS Aviation Charts from a config entry."""
    data = _entry_data(entry)
    session = async_get_clientsession(hass)

    coordinator = MavisChartsCoordinator(
        hass,
        session,
        username=data.get(CONF_USERNAME, ""),
        password=data.get(CONF_PASSWORD, ""),
        charts=data.get(CONF_CHARTS, []),
        scan_interval=data.get(CONF_SCAN_INTERVAL, 60),
        entry_id=entry.entry_id,
        auth_token=data.get(CONF_AUTH_TOKEN, ""),
    )

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry when options change, cleaning up removed chart entities."""
    data = _entry_data(entry)
    new_charts = data.get(CONF_CHARTS, [])

    coordinator: MavisChartsCoordinator | None = hass.data.get(DOMAIN, {}).get(
        entry.entry_id
    )

    if coordinator:
        old_charts = coordinator.charts
        removed = set(old_charts) - set(new_charts)
        if removed:
            ent_reg = er.async_get(hass)
            for chart_key in removed:
                for platform in ("image", "sensor"):
                    unique_id = f"{entry.entry_id}_{chart_key}_{platform}"
                    entity_id = ent_reg.async_get_entity_id(platform, DOMAIN, unique_id)
                    if entity_id:
                        ent_reg.async_remove(entity_id)
                        _LOGGER.debug(
                            "Removed entity %s for deselected chart %s",
                            entity_id, chart_key,
                        )
            coordinator.update_charts(new_charts)

    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)
