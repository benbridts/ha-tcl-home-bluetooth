"""BLE protocol handler for TCL Soundbar."""
from __future__ import annotations

import logging

from .const import (
    CMD_GET_VERSION,
    CMD_SET_MUTE,
    CMD_SET_POWER,
    CMD_SET_SOURCE,
    CMD_SET_VOLUME,
    FRAME_HEADER,
)

_LOGGER = logging.getLogger(__name__)


class TCLSoundbarProtocol:
    """Protocol frame builder and parser for the TCL Soundbar BLE protocol."""

    @staticmethod
    def calculate_checksum(data: bytes) -> int:
        """Calculate XOR checksum of all bytes (used over the frame excluding checksum)."""
        result = 0
        for byte in data:
            result ^= byte
        return result

    @staticmethod
    def build_frame(command: int, data: bytes = b"") -> bytes:
        """Build a protocol frame.

        Frame format: [0xAA][length_high][length_low][command][data...][xor_checksum]
        Length = total frame length including header and checksum.

        Args:
            command: The command byte.
            data: Optional payload data.

        Returns:
            Complete frame as bytes.
        """
        # Length = header(1) + length(2) + command(1) + data(n) + checksum(1)
        length = 1 + 2 + 1 + len(data) + 1
        length_high = (length >> 8) & 0xFF
        length_low = length & 0xFF

        frame_without_checksum = bytes(
            [FRAME_HEADER, length_high, length_low, command]
        ) + data
        checksum = TCLSoundbarProtocol.calculate_checksum(frame_without_checksum)

        return frame_without_checksum + bytes([checksum])

    @staticmethod
    def parse_frame(raw: bytes) -> tuple[int, bytes] | None:
        """Parse a received frame and extract command and data.

        Args:
            raw: Raw bytes received from the device.

        Returns:
            Tuple of (command, data) or None if frame is invalid.
        """
        if len(raw) < 5:
            _LOGGER.debug("Frame too short: %d bytes", len(raw))
            return None

        if raw[0] != FRAME_HEADER:
            _LOGGER.debug("Invalid frame header: 0x%02X", raw[0])
            return None

        # Extract expected length
        expected_length = (raw[1] << 8) | raw[2]
        if len(raw) < expected_length:
            _LOGGER.debug(
                "Frame incomplete: expected %d, got %d",
                expected_length,
                len(raw),
            )
            return None

        # Verify checksum (XOR of all bytes except the last one)
        frame_data = raw[: expected_length - 1]
        expected_checksum = raw[expected_length - 1]
        actual_checksum = TCLSoundbarProtocol.calculate_checksum(frame_data)

        if actual_checksum != expected_checksum:
            _LOGGER.debug(
                "Checksum mismatch: expected 0x%02X, got 0x%02X",
                expected_checksum,
                actual_checksum,
            )
            return None

        command = raw[3]
        data = raw[4 : expected_length - 1]

        return (command, data)

    @staticmethod
    def build_set_volume(level: int) -> bytes:
        """Build a set volume command frame.

        Args:
            level: Volume level (0-100).

        Returns:
            Complete frame bytes.
        """
        level = max(0, min(100, level))
        return TCLSoundbarProtocol.build_frame(CMD_SET_VOLUME, bytes([level]))

    @staticmethod
    def build_set_power(on: bool) -> bytes:
        """Build a set power command frame.

        Args:
            on: True to power on, False to power off.

        Returns:
            Complete frame bytes.
        """
        return TCLSoundbarProtocol.build_frame(CMD_SET_POWER, bytes([0x01 if on else 0x00]))

    @staticmethod
    def build_set_mute(mute: bool) -> bytes:
        """Build a set mute command frame.

        Args:
            mute: True to mute, False to unmute.

        Returns:
            Complete frame bytes.
        """
        return TCLSoundbarProtocol.build_frame(CMD_SET_MUTE, bytes([0x01 if mute else 0x00]))

    @staticmethod
    def build_set_source(source_id: int) -> bytes:
        """Build a set source command frame.

        Args:
            source_id: Source ID from SOURCE_MAP.

        Returns:
            Complete frame bytes.
        """
        return TCLSoundbarProtocol.build_frame(CMD_SET_SOURCE, bytes([source_id]))

    @staticmethod
    def build_get_status() -> bytes:
        """Build a get status/version command frame.

        Returns:
            Complete frame bytes.
        """
        return TCLSoundbarProtocol.build_frame(CMD_GET_VERSION)


class TDataMerger:
    """Reassembles multi-packet BLE responses into complete frames.

    BLE has a maximum packet size (typically 20 bytes). Longer frames
    are split across multiple notifications. This class accumulates
    packets until the expected frame length is reached.
    """

    def __init__(self) -> None:
        """Initialize the data merger."""
        self._buffer: bytes = b""
        self._expected_length: int = 0

    def reset(self) -> None:
        """Clear the internal buffer."""
        self._buffer = b""
        self._expected_length = 0

    def add_data(self, data: bytes) -> bytes | None:
        """Add received BLE data and check if frame is complete.

        Args:
            data: Bytes received from a BLE notification.

        Returns:
            Complete frame bytes if all data received, None otherwise.
        """
        if not data:
            return None

        # If buffer is empty, this is the start of a new frame
        if not self._buffer:
            if len(data) < 3:
                _LOGGER.debug("Initial packet too short for header")
                self.reset()
                return None

            if data[0] != FRAME_HEADER:
                _LOGGER.debug("Invalid header in initial packet: 0x%02X", data[0])
                self.reset()
                return None

            # Read expected length from bytes 1-2
            self._expected_length = (data[1] << 8) | data[2]

        self._buffer += data

        if len(self._buffer) >= self._expected_length:
            complete_frame = self._buffer[: self._expected_length]
            self.reset()
            return complete_frame

        _LOGGER.debug(
            "Accumulating data: %d/%d bytes",
            len(self._buffer),
            self._expected_length,
        )
        return None
