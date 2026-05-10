"""Constants for the Met Office Charts integration."""
from __future__ import annotations

DOMAIN = "metoffice_charts"

# Service names
SERVICE_REFRESH_ORDER = "refresh_order"
SERVICE_REFRESH_ALL = "refresh_all"

# Config/Options keys
CONF_API_KEY = "api_key"
CONF_ORDER_ID = "order_id"
CONF_SCAN_INTERVAL = "scan_interval"

# Default values
DEFAULT_SCAN_INTERVAL = 60
MIN_SCAN_INTERVAL = 5
MAX_SCAN_INTERVAL = 1440

# Storage
STORAGE_DIR = "www/metoffice_charts"

# DataHub API
DATAHUB_BASE_URL = "https://data.hub.api.metoffice.gov.uk/map-images/1.0.0"

# Attribution
ATTRIBUTION = "Data provided by Met Office DataHub"
