"""The TCL Soundbar integration."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN  # noqa: F401

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
