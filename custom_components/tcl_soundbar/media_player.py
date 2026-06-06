"""Media player platform for TCL Soundbar.

This module implements the Home Assistant media player entity for TCL soundbars
that communicate over BLE. The soundbar uses a custom GATT protocol where
commands are sent as framed byte sequences to a write characteristic, and
state reports are received via BLE notifications on a separate characteristic.

Key design decisions:
- The device advertises with service UUID FFF6 but uses different UUIDs for
  actual GATT communication after connection. We look up characteristics
  directly by their known UUIDs rather than searching by service.
- BLE connections are established lazily (on first command) if the device
  isn't available at startup. The device must be powered on and advertising
  for a connection to succeed.
- Notifications from the device may arrive in multiple BLE packets for a
  single logical frame, so we use TDataMerger to reassemble them.
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from bleak import BleakClient
from bleak.exc import BleakError
from bleak_retry_connector import establish_connection

from homeassistant.components.bluetooth import async_ble_device_from_address
from homeassistant.components.media_player import (
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CMD_REPORT_POWER,
    CMD_REPORT_SOURCE,
    CMD_REPORT_VOLUME,
    DOMAIN,
    GATT_NOTIFY_CHAR_UUID,
    GATT_SERVICE_UUID,
    GATT_WRITE_CHAR_UUID,
    SOURCE_MAP,
    SOURCE_MAP_REVERSE,
)
from .protocol import TCLSoundbarProtocol, TDataMerger

_LOGGER = logging.getLogger(__name__)


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
    """Representation of a TCL Soundbar as a media player.

    Communicates with the soundbar over BLE using a custom protocol.
    Supports power on/off, volume control, mute, and source selection.
    """

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
        self._address = address
        self._client: BleakClient | None = None
        self._write_characteristic: Any = None
        self._notify_characteristic: Any = None
        # TDataMerger reassembles multi-packet BLE notifications into
        # complete protocol frames before parsing.
        self._data_merger = TDataMerger()

        # Track when we last sent a command and what it was.
        # Used to log timing context on disconnect so we can observe
        # whether the device disconnects after commands (and how quickly).
        self._last_command_time: float = 0.0
        self._last_command_hex: str = ""

        # State attributes
        self._attr_state: MediaPlayerState | None = MediaPlayerState.OFF
        self._attr_volume_level: float | None = None
        self._attr_is_volume_muted: bool | None = None
        self._attr_source: str | None = None
        self._attr_source_list: list[str] = list(SOURCE_MAP.keys())

        # Entity identifiers
        self._attr_unique_id = f"{DOMAIN}_{address.replace(':', '_')}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, address)},
            name=entry.title,
            manufacturer="TCL",
            model="S55HE Soundbar",
        )

    async def async_added_to_hass(self) -> None:
        """Run when entity is added to hass."""
        _LOGGER.debug("TCL Soundbar entity added to hass: %s", self._address)
        # Attempt initial connection to get device state.
        # If the device is asleep/not advertising, this will silently fail
        # and the connection will be retried on the first user command.
        await self._connect_and_poll()

    async def async_will_remove_from_hass(self) -> None:
        """Run when entity is removed from hass."""
        await self._disconnect()

    async def _connect_and_poll(self) -> None:
        """Establish BLE connection and poll for initial device state.

        This is a best-effort operation: if the device is not available
        (e.g. powered off / not advertising), we log at debug level and
        defer connection to the first user-initiated command.
        """
        try:
            ble_device = async_ble_device_from_address(
                self.hass, self._address, connectable=True
            )
            if ble_device is None:
                _LOGGER.debug(
                    "BLE device %s not yet available, will connect on first command",
                    self._address,
                )
                return

            _LOGGER.debug("Initial connect to %s", self._address)
            self._client = await establish_connection(
                BleakClient,
                ble_device,
                self._address,
                disconnected_callback=lambda _client: self._handle_disconnect(),
            )
            await self._discover_characteristics()
            await self._start_notifications()
            await self._poll_initial_state()
            _LOGGER.debug("Initial connection established for %s", self._address)
        except (BleakError, TimeoutError, OSError) as err:
            _LOGGER.debug(
                "Initial connection to %s failed (will retry on command): %s",
                self._address,
                err,
            )
            self._client = None

    async def _poll_initial_state(self) -> None:
        """Send a get-status command to request current state from device.

        After connecting, we ask the soundbar to report its current power,
        volume, and source state so the HA entity shows accurate info
        without waiting for a user interaction.
        """
        if self._client and self._write_characteristic:
            try:
                frame = TCLSoundbarProtocol.build_get_status()
                _LOGGER.debug("Polling initial state: %s", frame.hex())
                await self._client.write_gatt_char(
                    self._write_characteristic, frame, response=True
                )
                self._last_command_time = time.monotonic()
                self._last_command_hex = frame.hex()
            except (BleakError, TimeoutError, OSError) as err:
                _LOGGER.warning("Failed to poll initial state: %s", err)

    async def _discover_characteristics(self) -> None:
        """Look up the write and notify GATT characteristics by service + UUID.

        The TCL soundbar advertises with service UUID FFF6, but once connected
        the actual data characteristics live under a different service
        (e49a25f8-...). The device exposes duplicate characteristic UUIDs
        across multiple services (e49a25f8-... and 0000f500-...), so we must
        look them up within the specific service to avoid bleak raising
        "Multiple Characteristics with this UUID".

        These UUIDs were determined empirically by connecting to the device and
        enumerating its GATT table (see the discover_characteristics action).
        """
        assert self._client is not None

        self._write_characteristic = None
        self._notify_characteristic = None

        # Find characteristics within our target service to avoid the
        # "Multiple Characteristics with this UUID" error that occurs when
        # the same char UUID exists under multiple services.
        target_service = None
        for service in self._client.services:
            if service.uuid == GATT_SERVICE_UUID:
                target_service = service
                break

        if target_service:
            for char in target_service.characteristics:
                if char.uuid == GATT_WRITE_CHAR_UUID:
                    self._write_characteristic = char
                elif char.uuid == GATT_NOTIFY_CHAR_UUID:
                    self._notify_characteristic = char
        else:
            _LOGGER.warning(
                "Target GATT service %s not found; "
                "falling back to handle-based lookup across all services",
                GATT_SERVICE_UUID,
            )
            # Fallback: iterate all services and pick the first match,
            # using the characteristic object (which carries its handle)
            # to avoid the ambiguous UUID lookup.
            for service in self._client.services:
                for char in service.characteristics:
                    if char.uuid == GATT_WRITE_CHAR_UUID and self._write_characteristic is None:
                        self._write_characteristic = char
                    elif char.uuid == GATT_NOTIFY_CHAR_UUID and self._notify_characteristic is None:
                        self._notify_characteristic = char

        if self._write_characteristic:
            _LOGGER.debug(
                "Found write characteristic: %s (handle=%d)",
                GATT_WRITE_CHAR_UUID,
                self._write_characteristic.handle,
            )
        else:
            _LOGGER.warning(
                "Write characteristic %s not found in services",
                GATT_WRITE_CHAR_UUID,
            )

        if self._notify_characteristic:
            _LOGGER.debug(
                "Found notify characteristic: %s (handle=%d)",
                GATT_NOTIFY_CHAR_UUID,
                self._notify_characteristic.handle,
            )
        else:
            _LOGGER.warning(
                "Notify characteristic %s not found in services",
                GATT_NOTIFY_CHAR_UUID,
            )

    async def _start_notifications(self) -> None:
        """Subscribe to BLE notifications from the soundbar.

        The device sends state reports (volume changes, power state, source
        changes) as notifications on the notify characteristic. We subscribe
        here so that any change — whether from HA or the physical remote —
        gets reflected in the entity state.
        """
        if self._client and self._notify_characteristic:
            await self._client.start_notify(
                self._notify_characteristic, self._notification_callback
            )
            _LOGGER.debug("Started notifications")

    def _handle_disconnect(self) -> None:
        """Handle device disconnection.

        Called by bleak when the BLE connection drops. Logs the elapsed time
        since the last command so we can observe whether the device initiates
        disconnect after processing commands. This helps confirm device
        behavior without making assumptions in the code.
        """
        if self._last_command_time > 0:
            elapsed = time.monotonic() - self._last_command_time
            _LOGGER.info(
                "Device %s disconnected %.2fs after last command (%s)",
                self._address,
                elapsed,
                self._last_command_hex,
            )
        else:
            _LOGGER.warning(
                "Device %s disconnected (no commands had been sent this session)",
                self._address,
            )

        self._client = None
        self._write_characteristic = None
        self._notify_characteristic = None
        self.async_write_ha_state()

    def _notification_callback(
        self, _sender: Any, data: bytearray
    ) -> None:
        """Handle incoming BLE notifications.

        BLE notifications may arrive as partial frames (due to MTU limits),
        so we feed them into TDataMerger which buffers and reassembles them.
        Once a complete frame is received, we parse and handle it.

        In Home Assistant, bleak notification callbacks run on the event loop
        via the HA bluetooth integration.
        """
        _LOGGER.debug("Received notification: %s", data.hex())

        complete_frame = self._data_merger.add_data(bytes(data))
        if complete_frame is None:
            # Partial frame — waiting for more data
            return

        parsed = TCLSoundbarProtocol.parse_frame(complete_frame)
        if parsed is None:
            _LOGGER.warning("Failed to parse frame: %s", complete_frame.hex())
            return

        command, payload = parsed
        self._handle_report(command, payload)

    def _handle_report(self, command: int, payload: bytes) -> None:
        """Handle a parsed report from the device.

        The soundbar sends unsolicited reports when its state changes (e.g.
        volume adjusted via remote, source switched, powered off). We update
        our internal state to match and notify HA.
        """
        if command == CMD_REPORT_VOLUME:
            if payload:
                # Volume is reported as 0-100 integer, we normalize to 0.0-1.0
                volume = payload[0]
                self._attr_volume_level = volume / 100.0
                _LOGGER.debug("Volume report: %d%%", volume)

        elif command == CMD_REPORT_POWER:
            if payload:
                # Power state: 0 = off, non-zero = on
                power_on = payload[0] != 0
                if power_on:
                    self._attr_state = MediaPlayerState.ON
                else:
                    self._attr_state = MediaPlayerState.OFF
                _LOGGER.debug("Power report: %s", "ON" if power_on else "OFF")

        elif command == CMD_REPORT_SOURCE:
            if payload:
                # Source ID maps to a human-readable name via SOURCE_MAP_REVERSE
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
        """Disconnect from the device and clear connection state."""
        if self._client and self._client.is_connected:
            try:
                await self._client.disconnect()
            except BleakError as err:
                _LOGGER.debug("Error during disconnect: %s", err)
        self._client = None
        self._write_characteristic = None
        self._notify_characteristic = None

    async def _send_command(self, frame: bytes) -> bool:
        """Send a command frame to the device.

        Handles the full connection lifecycle:
        1. If not connected, establishes a new BLE connection
        2. Discovers characteristics and starts notifications
        3. Writes the command frame to the write characteristic
        4. On failure, invalidates the connection so next call reconnects

        Returns:
            True if the command was sent successfully, False otherwise.
        """
        # Reconnect if we don't have an active connection
        if not (self._client and self._client.is_connected):
            try:
                ble_device = async_ble_device_from_address(
                    self.hass, self._address, connectable=True
                )
                if ble_device is None:
                    _LOGGER.error(
                        "Could not find BLE device for address %s", self._address
                    )
                    return False

                _LOGGER.debug("Connecting to %s", self._address)
                self._client = await establish_connection(
                    BleakClient,
                    ble_device,
                    self._address,
                    disconnected_callback=lambda _client: self._handle_disconnect(),
                )
                await self._discover_characteristics()

                if not self._write_characteristic:
                    _LOGGER.error(
                        "Service discovery failed for %s; "
                        "write characteristic not found",
                        self._address,
                    )
                    await self._disconnect()
                    return False

                await self._start_notifications()
                _LOGGER.debug("Connected to %s", self._address)

                # Poll state after reconnecting so we have up-to-date info
                await self._poll_initial_state()
            except (BleakError, TimeoutError, OSError) as err:
                _LOGGER.error("Failed to connect to %s: %s", self._address, err)
                self._client = None
                self._attr_state = None
                self.async_write_ha_state()
                return False

        if not self._write_characteristic:
            _LOGGER.error(
                "Write characteristic not available for %s; "
                "cannot send command",
                self._address,
            )
            return False

        try:
            _LOGGER.debug("Sending command: %s", frame.hex())
            # Use response=True (BLE Write Request) so bleak waits for
            # the device to ACK at the ATT layer. Without this, bleak uses
            # Write Without Response (fire-and-forget) which returns as soon
            # as the data is buffered locally -- the device may never process it.
            await self._client.write_gatt_char(
                self._write_characteristic, frame, response=True
            )
            self._last_command_time = time.monotonic()
            self._last_command_hex = frame.hex()
            _LOGGER.debug("Command acknowledged by device: %s", frame.hex())
            # Brief pause to let the device process before we return.
            await asyncio.sleep(0.2)
            return True
        except (BleakError, TimeoutError, OSError) as err:
            # Invalidate connection so next command triggers a reconnect
            _LOGGER.error("Failed to send command: %s", err)
            self._client = None
            return False

    # --- Media player action implementations ---
    # Each action builds a protocol frame and sends it. On success, we
    # optimistically update local state for immediate UI feedback. The
    # device will also send a notification confirming the change.

    async def async_turn_on(self) -> None:
        """Turn the soundbar on."""
        _LOGGER.debug("Turning on TCL Soundbar")
        frame = TCLSoundbarProtocol.build_set_power(on=True)
        if await self._send_command(frame):
            self._attr_state = MediaPlayerState.ON
            self.async_write_ha_state()

    async def async_turn_off(self) -> None:
        """Turn the soundbar off."""
        _LOGGER.debug("Turning off TCL Soundbar")
        frame = TCLSoundbarProtocol.build_set_power(on=False)
        if await self._send_command(frame):
            self._attr_state = MediaPlayerState.OFF
            self.async_write_ha_state()

    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume level (0.0 to 1.0)."""
        # Convert HA's 0.0-1.0 float to the device's 0-100 integer range
        level = int(volume * 100)
        _LOGGER.debug("Setting volume to %d%%", level)
        frame = TCLSoundbarProtocol.build_set_volume(level)
        if await self._send_command(frame):
            self._attr_volume_level = volume
            self.async_write_ha_state()

    async def async_volume_up(self) -> None:
        """Turn volume up by 5%."""
        current = self._attr_volume_level or 0.0
        new_level = min(1.0, current + 0.05)
        await self.async_set_volume_level(new_level)

    async def async_volume_down(self) -> None:
        """Turn volume down by 5%."""
        current = self._attr_volume_level or 0.0
        new_level = max(0.0, current - 0.05)
        await self.async_set_volume_level(new_level)

    async def async_mute_volume(self, mute: bool) -> None:
        """Mute or unmute the soundbar."""
        _LOGGER.debug("Setting mute to %s", mute)
        frame = TCLSoundbarProtocol.build_set_mute(mute)
        if await self._send_command(frame):
            self._attr_is_volume_muted = mute
            self.async_write_ha_state()

    async def async_select_source(self, source: str) -> None:
        """Select input source by name (e.g. 'HDMI', 'Bluetooth')."""
        source_id = SOURCE_MAP.get(source)
        if source_id is None:
            _LOGGER.error("Unknown source: %s", source)
            return

        _LOGGER.debug("Selecting source: %s (ID=%d)", source, source_id)
        frame = TCLSoundbarProtocol.build_set_source(source_id)
        if await self._send_command(frame):
            self._attr_source = source
            self.async_write_ha_state()
