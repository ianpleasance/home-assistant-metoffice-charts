"""Sensor platform for MAVIS Aviation Charts."""
from __future__ import annotations

import logging
from datetime import datetime

from homeassistant.components.sensor import SensorEntity, SensorDeviceClass
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
    """Set up MAVIS chart sensor entities from a config entry."""
    coordinator: MavisChartsCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities = [
        MavisChartSensorEntity(coordinator, entry, chart_key)
        for chart_key in coordinator.charts
        if chart_key in CHART_DEFINITIONS
    ]

    async_add_entities(entities)


class MavisChartSensorEntity(CoordinatorEntity[MavisChartsCoordinator], SensorEntity):
    """Sensor entity exposing metadata for a single MAVIS aviation chart."""

    _attr_has_entity_name = True
    _attr_attribution = "Data provided by the Met Office MAVIS Aeronautical Visualisation Service"
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_icon = "mdi:file-chart"

    def __init__(
        self,
        coordinator: MavisChartsCoordinator,
        entry: ConfigEntry,
        chart_key: str,
    ) -> None:
        """Initialise the entity."""
        super().__init__(coordinator)

        self._chart_key = chart_key
        chart_name, description, _, _, _ = CHART_DEFINITIONS[chart_key]

        self._attr_name = chart_name
        self._attr_unique_id = f"{entry.entry_id}_{chart_key}_sensor"

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
    def native_value(self) -> datetime | None:
        """State is the issue time of the chart as a timestamp."""
        data = self._chart_data
        if not data:
            return None
        issue_time = data.get("issue_time")
        if not issue_time:
            return None
        try:
            from datetime import timezone
            # Parse ISO 8601 UTC string e.g. 2026-05-13T06:00:00Z
            return datetime.fromisoformat(
                issue_time.replace("Z", "+00:00")
            )
        except ValueError:
            return None

    @property
    def extra_state_attributes(self) -> dict:
        data = self._chart_data
        if not data:
            return {}

        _, description, _, ext, _ = CHART_DEFINITIONS[self._chart_key]

        base = {
            "description": description,
            "downloaded_at": (
                data["downloaded_at"].isoformat()
                if data.get("downloaded_at") else None
            ),
            "issue_time": data.get("issue_time"),
        }

        if ext == "rps":
            # Regional pressure: expose each region as attributes
            regions = data.get("regions", {})
            for region, values in sorted(regions.items()):
                base[f"{region}_current_hpa"] = values.get("current_hpa")
                base[f"{region}_next_hpa"] = values.get("next_hpa")
        else:
            base.update({
                "pdf_path": data.get("pdf_path"),
                "pdf_url": data.get("pdf_url"),
                "png_path": data.get("png_path"),
                "png_url": data.get("png_url"),
                "size_bytes": data.get("size_bytes"),
                "png_available": data.get("png_ok", False),
            })

        return base

    @property
    def available(self) -> bool:
        return (
            self.coordinator.last_update_success
            and self._chart_data is not None
        )
