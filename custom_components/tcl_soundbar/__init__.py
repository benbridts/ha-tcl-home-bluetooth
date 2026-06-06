"""The TCL Soundbar integration.

This integration communicates with TCL soundbars over Bluetooth Low Energy (BLE).
It uses the HA bluetooth component for device discovery and bleak for GATT
communication.

The soundbar advertises with service UUID FFF6 (used in manifest.json for
HA bluetooth discovery), but after connection exposes characteristics under
a different service UUID (e49a25f8-f69a-11e8-8eb2-f2801f1b9fd1). This was
determined by connecting to the device and enumerating its GATT table.
"""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN  # noqa: F401  # Required by HA for config flow domain resolution

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.MEDIA_PLAYER]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up TCL Soundbar from a config entry."""
    _LOGGER.debug("Setting up TCL Soundbar integration for %s", entry.title)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a TCL Soundbar config entry."""
    _LOGGER.debug("Unloading TCL Soundbar integration for %s", entry.title)

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
