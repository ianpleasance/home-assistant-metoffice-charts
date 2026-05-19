"""Image platform for Met Office Charts."""
from __future__ import annotations

from datetime import datetime
import logging
from typing import Any

from homeassistant.components.image import ImageEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTRIBUTION, CONF_ORDER_ID, DOMAIN
from .coordinator import MetOfficeChartsCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Met Office Charts image entities."""
    coordinator: MetOfficeChartsCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]

    # Wait for first refresh to know what parameters we have
    if not coordinator.data:
        return

    # Extract parameter names from coordinator data
    parameters = set()
    for key in coordinator.data.keys():
        if key.endswith("_bytes"):
            param_name = key.replace("_bytes", "")
            parameters.add(param_name)

    entities = [
        MetOfficeChartImage(coordinator, param_name, entry.data[CONF_ORDER_ID])
        for param_name in parameters
    ]

    async_add_entities(entities)

    _LOGGER.info(
        "Created %d image entities for order %s",
        len(entities),
        entry.data[CONF_ORDER_ID],
    )


class MetOfficeChartImage(CoordinatorEntity[MetOfficeChartsCoordinator], ImageEntity):
    """Representation of a Met Office chart image."""

    _attr_attribution = ATTRIBUTION
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: MetOfficeChartsCoordinator,
        param_name: str,
        order_id: str,
    ) -> None:
        """Initialize the image entity."""
        super().__init__(coordinator)
        ImageEntity.__init__(self, coordinator.hass)

        self._param_name = param_name
        self._order_id = order_id
        self._attr_name = f"Met Office {param_name.replace('_', ' ').title()}"
        self._attr_unique_id = f"{DOMAIN}_{order_id}_{param_name}"

    @property
    def image_last_updated(self) -> datetime | None:
        """Return the timestamp of when the image was last updated."""
        return self.coordinator.data.get(f"{self._param_name}_timestamp")

    async def async_image(self) -> bytes | None:
        """Return bytes of image."""
        return self.coordinator.data.get(f"{self._param_name}_bytes")

    @property
    def content_type(self) -> str:
        """Return the content type of the image."""
        return self.coordinator.data.get(
            f"{self._param_name}_content_type", "image/png"
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return entity specific state attributes."""
        attrs = {
            "parameter": self._param_name,
            "order_id": self._order_id,
            "file_url": self.coordinator.data.get(f"{self._param_name}_url"),
            "file_path": self.coordinator.data.get(f"{self._param_name}_path"),
            "last_updated": self.image_last_updated,
            "run_time": self.coordinator.data.get(f"{self._param_name}_run_time"),
            "forecast_period": self.coordinator.data.get(
                f"{self._param_name}_forecast_period"
            ),
            "attribution": ATTRIBUTION,
        }
        
        # Add order metadata if available
        metadata = self.coordinator.data.get("_order_metadata", {})
        if metadata:
            attrs["model_id"] = metadata.get("model_id")
            attrs["data_format"] = metadata.get("format")
            
        return attrs

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return (
            self.coordinator.last_update_success
            and f"{self._param_name}_bytes" in self.coordinator.data
        )
