"""Data update coordinator for Met Office Charts."""
from __future__ import annotations

from datetime import timedelta
import logging
import os
from typing import Any
from urllib.parse import quote

import aiofiles
import aiohttp

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import DATAHUB_BASE_URL, DOMAIN, STORAGE_DIR

_LOGGER = logging.getLogger(__name__)


class MetOfficeChartsCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Class to manage fetching Met Office chart data from DataHub."""

    def __init__(
        self,
        hass: HomeAssistant,
        session: aiohttp.ClientSession,
        api_key: str,
        order_id: str,
        scan_interval: int,
    ) -> None:
        """Initialize the coordinator."""
        self.session = session
        self.api_key = api_key
        self.order_id = order_id
        self.headers = {"apikey": api_key}

        # Create storage directory
        self.storage_path = hass.config.path(STORAGE_DIR)
        os.makedirs(self.storage_path, exist_ok=True)

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=scan_interval),
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from Met Office DataHub API."""
        data: dict[str, Any] = {}

        try:
            # Get the latest files list for this order
            files_url = f"{DATAHUB_BASE_URL}/orders/{self.order_id}/latest"

            async with self.session.get(
                files_url,
                headers=self.headers,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as response:
                if response.status != 200:
                    raise UpdateFailed(
                        f"Failed to fetch files list: HTTP {response.status}"
                    )

                files_data = await response.json()

                # Extract file information - files are nested in orderDetails
                order_details = files_data.get("orderDetails", {})
                files = order_details.get("files", [])
                
                # Store order metadata for attribution
                order_info = order_details.get("order", {})
                data["_order_metadata"] = {
                    "order_id": order_info.get("orderId", self.order_id),
                    "model_id": order_info.get("modelId", ""),
                    "format": order_info.get("format", "PNG"),
                }

                if not files:
                    _LOGGER.warning("No files available in order %s", self.order_id)
                    return data

                _LOGGER.debug(
                    "Found %d chart files for order %s", len(files), self.order_id
                )

                # Group files by parameter (each parameter has multiple timesteps)
                # We'll take just the first timestep (ts0) for each parameter
                params_seen = set()

                # Download each file
                for file_info in files:
                    file_id = file_info.get("fileId")
                    run_time = file_info.get("runDateTime")
                    
                    if not file_id:
                        continue
                    
                    # Extract parameter name from fileId
                    # Format: cloud_amount_total_ts0_+00 or pressure_msl_ts1_2026051000
                    # We want: cloud_amount_total, pressure_msl, etc.
                    parts = file_id.split("_ts")
                    if len(parts) < 2:
                        continue
                    
                    param_name = parts[0]  # e.g., "cloud_amount_total"
                    
                    # Only process first timestep for each parameter (avoid duplicates)
                    if param_name in params_seen:
                        continue
                    params_seen.add(param_name)
                    
                    # Construct download URL (per Met Office official example)
                    # Format: https://data.hub.api.metoffice.gov.uk/map-images/1.0.0/orders/{orderId}/latest/{fileId}/data
                    # Note: fileId must be URL encoded (+ becomes %2B)
                    encoded_file_id = quote(file_id, safe='')
                    file_url = f"{DATAHUB_BASE_URL}/orders/{self.order_id}/latest/{encoded_file_id}/data"

                    try:
                        await self._download_file(
                            param_name, file_url, run_time, None, data
                        )
                    except Exception as err:  # pylint: disable=broad-except
                        _LOGGER.error("Error downloading %s: %s", file_id, err)
                        continue

        except aiohttp.ClientError as err:
            raise UpdateFailed(f"Error fetching data from DataHub: {err}") from err
        except Exception as err:  # pylint: disable=broad-except
            raise UpdateFailed(f"Unexpected error: {err}") from err

        if not data:
            raise UpdateFailed("No charts were successfully fetched")

        _LOGGER.info(
            "Successfully fetched %d chart(s) for order %s",
            len([k for k in data.keys() if k.endswith("_bytes")]),
            self.order_id,
        )

        return data

    async def _download_file(
        self,
        param_name: str,
        file_url: str,
        run_time: str | None,
        forecast_period: int | None,
        data: dict[str, Any],
    ) -> None:
        """Download and save a chart image."""
        # Add Accept header for image downloads (per Met Office example)
        download_headers = {**self.headers, "Accept": "image/png"}
        
        async with self.session.get(
            file_url,
            headers=download_headers,
            timeout=aiohttp.ClientTimeout(total=60),
        ) as response:
            if response.status == 200:
                image_bytes = await response.read()

                # Determine file extension
                content_type = response.headers.get("Content-Type", "image/png")
                ext = "png" if "png" in content_type else "jpg"

                # Save to disk
                filename = f"{param_name}.{ext}"
                filepath = os.path.join(self.storage_path, filename)

                async with aiofiles.open(filepath, "wb") as f:
                    await f.write(image_bytes)

                # Store data
                timestamp = dt_util.now()
                data[f"{param_name}_bytes"] = image_bytes
                data[f"{param_name}_timestamp"] = timestamp
                data[f"{param_name}_path"] = filepath
                data[f"{param_name}_url"] = f"/local/metoffice_charts/{filename}"
                data[f"{param_name}_content_type"] = content_type
                data[f"{param_name}_run_time"] = run_time
                data[f"{param_name}_forecast_period"] = forecast_period

                _LOGGER.debug(
                    "Successfully fetched %s (%d bytes)", param_name, len(image_bytes)
                )
            else:
                _LOGGER.warning(
                    "Failed to download %s: HTTP %d", param_name, response.status
                )
