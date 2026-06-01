"""Media player platform for TCL Soundbar."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from bleak import BleakClient
from bleak.exc import BleakError

from homeassistant.components.media_player import (
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CMD_REPORT_POWER,
    CMD_REPORT_SOURCE,
    CMD_REPORT_VOLUME,
    DOMAIN,
    SERVICE_UUID,
    SOURCE_MAP,
    SOURCE_MAP_REVERSE,
)
from .protocol import TCLSoundbarProtocol, TDataMerger

_LOGGER = logging.getLogger(__name__)

# BLE connection constants
MAX_CONNECT_ATTEMPTS = 3
CONNECT_RETRY_DELAY = 2.0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up TCL Soundbar media player from a config entry."""
    address = entry.data["address"]
    _LOGGER.debug("Setting up TCL Soundbar media player at %s", address)

    entity = TCLSoundbarMediaPlayer(entry, address)
    async_add_entities([entity])


class TCLSoundbarMediaPlayer(MediaPlayerEntity):
    """Representation of a TCL Soundbar as a media player."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_supported_features = (
        MediaPlayerEntityFeature.TURN_ON
        | MediaPlayerEntityFeature.TURN_OFF
        | MediaPlayerEntityFeature.VOLUME_SET
        | MediaPlayerEntityFeature.VOLUME_STEP
        | MediaPlayerEntityFeature.VOLUME_MUTE
        | MediaPlayerEntityFeature.SELECT_SOURCE
    )

    def __init__(self, entry: ConfigEntry, address: str) -> None:
        """Initialize the TCL Soundbar media player."""
        self._entry = entry
        self._address = address
        self._client: BleakClient | None = None
        self._write_characteristic: Any = None
        self._notify_characteristic: Any = None
        self._data_merger = TDataMerger()

        # State attributes
        self._attr_state: MediaPlayerState | None = None
        self._attr_volume_level: float | None = None
        self._attr_is_volume_muted: bool | None = None
        self._attr_source: str | None = None
        self._attr_source_list: list[str] = list(SOURCE_MAP.keys())

        # Entity identifiers
        self._attr_unique_id = f"{DOMAIN}_{address.replace(':', '_')}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, address)},
            "name": entry.title,
            "manufacturer": "TCL",
            "model": "S55HE Soundbar",
        }

        self._connected = False
        self._connecting = False

    async def async_added_to_hass(self) -> None:
        """Run when entity is added to hass."""
        _LOGGER.debug("TCL Soundbar entity added to hass: %s", self._address)

    async def async_will_remove_from_hass(self) -> None:
        """Run when entity is removed from hass."""
        await self._disconnect()

    async def _ensure_connected(self) -> bool:
        """Ensure BLE connection is established.

        Returns:
            True if connected, False otherwise.
        """
        if self._connected and self._client and self._client.is_connected:
            return True

        if self._connecting:
            _LOGGER.debug("Already attempting to connect")
            return False

        self._connecting = True
        try:
            for attempt in range(1, MAX_CONNECT_ATTEMPTS + 1):
                try:
                    _LOGGER.debug(
                        "Connecting to %s (attempt %d/%d)",
                        self._address,
                        attempt,
                        MAX_CONNECT_ATTEMPTS,
                    )
                    self._client = BleakClient(self._address)
                    await self._client.connect()
                    await self._discover_characteristics()
                    await self._start_notifications()
                    self._connected = True
                    _LOGGER.debug("Connected to %s", self._address)
                    return True
                except (BleakError, asyncio.TimeoutError, OSError) as err:
                    _LOGGER.warning(
                        "Connection attempt %d failed: %s", attempt, err
                    )
                    if attempt < MAX_CONNECT_ATTEMPTS:
                        await asyncio.sleep(CONNECT_RETRY_DELAY * attempt)
                    else:
                        _LOGGER.error(
                            "Failed to connect to %s after %d attempts",
                            self._address,
                            MAX_CONNECT_ATTEMPTS,
                        )
                        self._attr_state = None
                        self.async_write_ha_state()
                        return False
        finally:
            self._connecting = False

        return False

    async def _discover_characteristics(self) -> None:
        """Discover write and notify characteristics within the FFF6 service."""
        assert self._client is not None

        for service in self._client.services:
            if SERVICE_UUID in service.uuid.lower():
                for char in service.characteristics:
                    if "write" in char.properties:
                        self._write_characteristic = char
                        _LOGGER.debug(
                            "Found write characteristic: %s", char.uuid
                        )
                    if "notify" in char.properties or "indicate" in char.properties:
                        self._notify_characteristic = char
                        _LOGGER.debug(
                            "Found notify characteristic: %s", char.uuid
                        )
                break

        if not self._write_characteristic:
            _LOGGER.error("Write characteristic not found")
        if not self._notify_characteristic:
            _LOGGER.error("Notify characteristic not found")

    async def _start_notifications(self) -> None:
        """Start listening for notifications from the device."""
        if self._client and self._notify_characteristic:
            await self._client.start_notify(
                self._notify_characteristic, self._notification_callback
            )
            _LOGGER.debug("Started notifications")

    def _notification_callback(
        self, _sender: Any, data: bytearray
    ) -> None:
        """Handle incoming BLE notifications."""
        _LOGGER.debug("Received notification: %s", data.hex())

        complete_frame = self._data_merger.add_data(bytes(data))
        if complete_frame is None:
            return

        parsed = TCLSoundbarProtocol.parse_frame(complete_frame)
        if parsed is None:
            _LOGGER.warning("Failed to parse frame: %s", complete_frame.hex())
            return

        command, payload = parsed
        self._handle_report(command, payload)

    def _handle_report(self, command: int, payload: bytes) -> None:
        """Handle a parsed report from the device."""
        if command == CMD_REPORT_VOLUME:
            if payload:
                volume = payload[0]
                self._attr_volume_level = volume / 100.0
                self._attr_is_volume_muted = volume == 0
                _LOGGER.debug("Volume report: %d%%", volume)

        elif command == CMD_REPORT_POWER:
            if payload:
                power_on = payload[0] != 0
                if power_on:
                    self._attr_state = MediaPlayerState.ON
                else:
                    self._attr_state = MediaPlayerState.OFF
                _LOGGER.debug("Power report: %s", "ON" if power_on else "OFF")

        elif command == CMD_REPORT_SOURCE:
            if payload:
                source_id = payload[0]
                source_name = SOURCE_MAP_REVERSE.get(source_id)
                if source_name:
                    self._attr_source = source_name
                    _LOGGER.debug("Source report: %s (ID=%d)", source_name, source_id)
                else:
                    _LOGGER.warning("Unknown source ID: %d", source_id)

        else:
            _LOGGER.debug("Unhandled report command: 0x%02X", command)

        self.async_write_ha_state()

    async def _disconnect(self) -> None:
        """Disconnect from the device."""
        if self._client and self._client.is_connected:
            try:
                await self._client.disconnect()
            except BleakError as err:
                _LOGGER.debug("Error during disconnect: %s", err)
        self._connected = False
        self._client = None
        self._write_characteristic = None
        self._notify_characteristic = None

    async def _send_command(self, frame: bytes) -> None:
        """Send a command frame to the device."""
        if not await self._ensure_connected():
            _LOGGER.error("Cannot send command: not connected")
            return

        assert self._client is not None
        assert self._write_characteristic is not None

        try:
            _LOGGER.debug("Sending command: %s", frame.hex())
            await self._client.write_gatt_char(
                self._write_characteristic, frame
            )
        except (BleakError, asyncio.TimeoutError, OSError) as err:
            _LOGGER.error("Failed to send command: %s", err)
            self._connected = False
            # Try one reconnect and resend
            if await self._ensure_connected():
                try:
                    await self._client.write_gatt_char(
                        self._write_characteristic, frame
                    )
                except (BleakError, asyncio.TimeoutError, OSError) as retry_err:
                    _LOGGER.error("Retry also failed: %s", retry_err)

    async def async_turn_on(self) -> None:
        """Turn the soundbar on."""
        _LOGGER.debug("Turning on TCL Soundbar")
        frame = TCLSoundbarProtocol.build_set_power(on=True)
        await self._send_command(frame)
        self._attr_state = MediaPlayerState.ON
        self.async_write_ha_state()

    async def async_turn_off(self) -> None:
        """Turn the soundbar off."""
        _LOGGER.debug("Turning off TCL Soundbar")
        frame = TCLSoundbarProtocol.build_set_power(on=False)
        await self._send_command(frame)
        self._attr_state = MediaPlayerState.OFF
        self.async_write_ha_state()

    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume level (0.0 to 1.0)."""
        level = int(volume * 100)
        _LOGGER.debug("Setting volume to %d%%", level)
        frame = TCLSoundbarProtocol.build_set_volume(level)
        await self._send_command(frame)
        self._attr_volume_level = volume
        self.async_write_ha_state()

    async def async_volume_up(self) -> None:
        """Turn volume up."""
        current = self._attr_volume_level or 0.0
        new_level = min(1.0, current + 0.05)
        await self.async_set_volume_level(new_level)

    async def async_volume_down(self) -> None:
        """Turn volume down."""
        current = self._attr_volume_level or 0.0
        new_level = max(0.0, current - 0.05)
        await self.async_set_volume_level(new_level)

    async def async_mute_volume(self, mute: bool) -> None:
        """Mute or unmute the soundbar."""
        _LOGGER.debug("Setting mute to %s", mute)
        frame = TCLSoundbarProtocol.build_set_mute(mute)
        await self._send_command(frame)
        self._attr_is_volume_muted = mute
        self.async_write_ha_state()

    async def async_select_source(self, source: str) -> None:
        """Select input source."""
        source_id = SOURCE_MAP.get(source)
        if source_id is None:
            _LOGGER.error("Unknown source: %s", source)
            return

        _LOGGER.debug("Selecting source: %s (ID=%d)", source, source_id)
        frame = TCLSoundbarProtocol.build_set_source(source_id)
        await self._send_command(frame)
        self._attr_source = source
        self.async_write_ha_state()
