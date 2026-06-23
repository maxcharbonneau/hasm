"""Constants for the HASM integration."""

from __future__ import annotations

from homeassistant.const import Platform

DOMAIN = "hasm"

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.SENSOR,
    Platform.UPDATE,
    Platform.BUTTON,
]
# Grows across milestones: UPDATE (M5), BUTTON (M6) added later.

# Configuration keys (config entry data / options)
CONF_VERIFY_SSL = "verify_ssl"  # bool, default True
CONF_SCAN_INTERVAL = "scan_interval"  # seconds (options), default DEFAULT_SCAN_INTERVAL

DEFAULT_SCAN_INTERVAL = 120  # seconds
DEFAULT_TIMEOUT = 10.0  # seconds per request

CONF_MAX_UPDATE_ENTITIES = "max_update_entities"
DEFAULT_MAX_UPDATE_ENTITIES = (
    250  # cap on mirror update entities per instance (loop guard), configurable
)
MIN_MAX_UPDATE_ENTITIES = 10
MAX_MAX_UPDATE_ENTITIES = 2000

# Generic passthrough service
SERVICE_CALL_REMOTE = "call_remote_service"
ATTR_DOMAIN = "remote_domain"
ATTR_SERVICE = "remote_service"
ATTR_SERVICE_DATA = "service_data"
