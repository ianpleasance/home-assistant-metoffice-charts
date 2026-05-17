"""Image platform for MAVIS Aviation Charts."""
from __future__ import annotations

import logging
from datetime import datetime

import aiofiles

from homeassistant.components.image import ImageEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, CHART_DEFINITIONS
from .coordinator import MavisChartsCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up MAVIS chart image entities from a config entry."""
    coordinator: MavisChartsCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities = [
        MavisChartImageEntity(coordinator, entry, chart_key)
        for chart_key in coordinator.charts
        if chart_key in CHART_DEFINITIONS
        and CHART_DEFINITIONS[chart_key][3] != "rps"  # RPS has no image
    ]

    async_add_entities(entities)


class MavisChartImageEntity(CoordinatorEntity[MavisChartsCoordinator], ImageEntity):
    """Image entity showing the PNG render of a MAVIS aviation chart."""

    _attr_has_entity_name = True
    _attr_attribution = "Data provided by the Met Office MAVIS Aeronautical Visualisation Service"
    @property
    def content_type(self) -> str:
        """Return content type based on what was downloaded."""
        data = self._chart_data
        if data and data.get("png_url", "").endswith(".gif"):
            return "image/gif"
        return "image/png"

    def __init__(
        self,
        coordinator: MavisChartsCoordinator,
        entry: ConfigEntry,
        chart_key: str,
    ) -> None:
        """Initialise the entity."""
        super().__init__(coordinator)
        ImageEntity.__init__(self, coordinator.hass)

        self._chart_key = chart_key
        chart_name, _, _, _, _ = CHART_DEFINITIONS[chart_key]

        self._attr_name = chart_name
        self._attr_unique_id = f"{entry.entry_id}_{chart_key}_image"

        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": "MAVIS Aviation Charts",
            "manufacturer": "Met Office",
            "model": "MAVIS Aeronautical Visualisation Service",
            "entry_type": "service",
        }

    @property
    def _chart_data(self) -> dict | None:
        if self.coordinator.data:
            return self.coordinator.data.get(self._chart_key)
        return None

    @property
    def image_last_updated(self) -> datetime | None:
        data = self._chart_data
        return data.get("downloaded_at") if data else None

    async def async_image(self) -> bytes | None:
        """Return PNG bytes read from disk."""
        data = self._chart_data
        if not data or not data.get("png_ok") or not data.get("png_path"):
            return None
        try:
            async with aiofiles.open(data["png_path"], "rb") as f:
                return await f.read()
        except OSError as err:
            _LOGGER.error("Could not read PNG for %s: %s", self._chart_key, err)
            return None

    @property
    def available(self) -> bool:
        data = self._chart_data
        return (
            self.coordinator.last_update_success
            and data is not None
            and data.get("png_ok", False)
        )
