"""Unit tests for the TCL Soundbar BLE protocol module."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

# Stub out homeassistant so we can import protocol without a full HA install
sys.modules.setdefault("homeassistant", MagicMock())
sys.modules.setdefault("homeassistant.config_entries", MagicMock())
sys.modules.setdefault("homeassistant.const", MagicMock())
sys.modules.setdefault("homeassistant.core", MagicMock())
sys.modules.setdefault("homeassistant.components", MagicMock())
sys.modules.setdefault("homeassistant.components.bluetooth", MagicMock())
sys.modules.setdefault("homeassistant.components.media_player", MagicMock())
sys.modules.setdefault("homeassistant.helpers", MagicMock())
sys.modules.setdefault("homeassistant.helpers.device_registry", MagicMock())
sys.modules.setdefault("homeassistant.helpers.entity_platform", MagicMock())
sys.modules.setdefault("homeassistant.data_entry_flow", MagicMock())

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from custom_components.tcl_soundbar.const import (
    CMD_SET_MUTE,
    CMD_SET_POWER,
    CMD_SET_SOURCE,
    CMD_SET_VOLUME,
    FRAME_HEADER,
)
from custom_components.tcl_soundbar.protocol import (
    build_frame,
    build_get_status,
    build_set_mute,
    build_set_power,
    build_set_source,
    build_set_volume,
    calculate_checksum,
    parse_frame,
    TDataMerger,
)


# --- Frame building tests ---


class TestBuildFrame:
    """Tests for build_frame."""

    def test_build_frame_basic(self):
        """Build a frame with no data, verify header, correct length, command, XOR checksum."""
        command = 0x18
        frame = build_frame(command)

        assert frame[0] == FRAME_HEADER
        # Length = 1(header) + 2(length) + 1(cmd) + 0(data) + 1(checksum) = 5
        expected_length = 5
        length_in_frame = (frame[1] << 8) | frame[2]
        assert length_in_frame == expected_length
        assert frame[3] == command
        # Checksum is XOR of all bytes except checksum itself
        expected_checksum = calculate_checksum(frame[:-1])
        assert frame[-1] == expected_checksum

    def test_build_frame_with_data(self):
        """Build a frame with payload data, verify all bytes correct."""
        command = 0x02
        data = bytes([0x32])
        frame = build_frame(command, data)

        assert frame[0] == FRAME_HEADER
        # Length = 1 + 2 + 1 + 1 + 1 = 6
        length_in_frame = (frame[1] << 8) | frame[2]
        assert length_in_frame == 6
        assert frame[3] == command
        assert frame[4] == 0x32
        expected_checksum = calculate_checksum(frame[:-1])
        assert frame[-1] == expected_checksum

    def test_build_frame_length_calculation(self):
        """Verify length field = 1(header) + 2(length) + 1(cmd) + len(data) + 1(checksum)."""
        data = bytes([0x01, 0x02, 0x03, 0x04, 0x05])
        frame = build_frame(0x10, data)

        expected_length = 1 + 2 + 1 + len(data) + 1  # = 10
        length_in_frame = (frame[1] << 8) | frame[2]
        assert length_in_frame == expected_length
        assert len(frame) == expected_length


# --- Checksum tests ---


class TestChecksum:
    """Tests for checksum calculation."""

    def test_calculate_checksum(self):
        """Verify XOR of known byte sequences."""
        # XOR of [0x01, 0x02, 0x03] = 0x01 ^ 0x02 ^ 0x03 = 0x00
        assert calculate_checksum(bytes([0x01, 0x02, 0x03])) == 0x00
        # XOR of [0xFF] = 0xFF
        assert calculate_checksum(bytes([0xFF])) == 0xFF
        # XOR of [0xAA, 0x00, 0x05, 0x02] = 0xAA ^ 0x00 ^ 0x05 ^ 0x02 = 0xAD
        assert calculate_checksum(bytes([0xAA, 0x00, 0x05, 0x02])) == 0xAD

    def test_checksum_roundtrip(self):
        """Build a frame and verify parse_frame accepts it (checksum is valid)."""
        frame = build_frame(0x06, bytes([0x01]))
        result = parse_frame(frame)
        assert result is not None
        command, data = result
        assert command == 0x06
        assert data == bytes([0x01])


# --- Frame parsing tests ---


class TestParseFrame:
    """Tests for parse_frame."""

    def test_parse_frame_valid(self):
        """Build a frame, then parse it, verify command and data match."""
        original_command = 0x0F
        original_data = bytes([0x03])
        frame = build_frame(original_command, original_data)

        result = parse_frame(frame)
        assert result is not None
        command, data = result
        assert command == original_command
        assert data == original_data

    def test_parse_frame_too_short(self):
        """Frames < 5 bytes return None."""
        assert parse_frame(bytes([0xAA, 0x00, 0x05])) is None
        assert parse_frame(bytes([0xAA])) is None
        assert parse_frame(b"") is None

    def test_parse_frame_invalid_header(self):
        """First byte not 0xAA returns None."""
        frame = build_frame(0x02, bytes([0x32]))
        # Corrupt the header
        bad_frame = bytes([0xBB]) + frame[1:]
        assert parse_frame(bad_frame) is None

    def test_parse_frame_bad_checksum(self):
        """Corrupt last byte, verify returns None."""
        frame = build_frame(0x02, bytes([0x32]))
        # Corrupt the checksum (last byte)
        bad_frame = frame[:-1] + bytes([frame[-1] ^ 0xFF])
        assert parse_frame(bad_frame) is None

    def test_parse_frame_incomplete_length(self):
        """Frame shorter than declared length returns None."""
        frame = build_frame(0x02, bytes([0x01, 0x02, 0x03]))
        # Truncate the frame (remove last 2 bytes so it's shorter than declared)
        truncated = frame[:-2]
        assert parse_frame(truncated) is None


# --- Helper method tests ---


class TestHelperMethods:
    """Tests for convenience frame building functions."""

    def test_build_set_volume(self):
        """Verify volume command byte is CMD_SET_VOLUME, data is the volume level."""
        frame = build_set_volume(50)
        result = parse_frame(frame)
        assert result is not None
        command, data = result
        assert command == CMD_SET_VOLUME
        assert data == bytes([50])

    def test_build_set_volume_clamped(self):
        """Volume >100 clamped to 100, <0 clamped to 0."""
        frame_high = build_set_volume(150)
        result_high = parse_frame(frame_high)
        assert result_high is not None
        _, data_high = result_high
        assert data_high == bytes([100])

        frame_low = build_set_volume(-10)
        result_low = parse_frame(frame_low)
        assert result_low is not None
        _, data_low = result_low
        assert data_low == bytes([0])

    def test_build_set_power_on(self):
        """Power command byte is CMD_SET_POWER, data is 0x01 for on."""
        frame = build_set_power(True)
        result = parse_frame(frame)
        assert result is not None
        command, data = result
        assert command == CMD_SET_POWER
        assert data == bytes([0x01])

    def test_build_set_power_off(self):
        """Power command byte is CMD_SET_POWER, data is 0x00 for off."""
        frame = build_set_power(False)
        result = parse_frame(frame)
        assert result is not None
        command, data = result
        assert command == CMD_SET_POWER
        assert data == bytes([0x00])

    def test_build_set_mute_on(self):
        """Mute command byte is CMD_SET_MUTE, data is 0x01."""
        frame = build_set_mute(True)
        result = parse_frame(frame)
        assert result is not None
        command, data = result
        assert command == CMD_SET_MUTE
        assert data == bytes([0x01])

    def test_build_set_mute_off(self):
        """Mute command byte is CMD_SET_MUTE, data is 0x00."""
        frame = build_set_mute(False)
        result = parse_frame(frame)
        assert result is not None
        command, data = result
        assert command == CMD_SET_MUTE
        assert data == bytes([0x00])

    def test_build_set_source(self):
        """Source command byte is CMD_SET_SOURCE, data is the source_id."""
        source_id = 5  # AUX
        frame = build_set_source(source_id)
        result = parse_frame(frame)
        assert result is not None
        command, data = result
        assert command == CMD_SET_SOURCE
        assert data == bytes([source_id])


# --- TDataMerger tests ---


class TestTDataMerger:
    """Tests for TDataMerger multi-packet reassembly."""

    def test_merger_single_packet(self):
        """Complete frame in one packet returns it immediately."""
        merger = TDataMerger()
        frame = build_frame(0x84, bytes([0x32]))
        result = merger.add_data(frame)
        assert result == frame

    def test_merger_multi_packet(self):
        """Split a frame across 2-3 packets, verify only last add_data returns the complete frame."""
        merger = TDataMerger()
        frame = build_frame(0x02, bytes([0x01, 0x02, 0x03, 0x04, 0x05]))

        # Split into 3 parts
        part1 = frame[:3]
        part2 = frame[3:6]
        part3 = frame[6:]

        assert merger.add_data(part1) is None
        assert merger.add_data(part2) is None
        result = merger.add_data(part3)
        assert result == frame

    def test_merger_reset(self):
        """After reset, merger starts fresh."""
        merger = TDataMerger()
        frame = build_frame(0x02, bytes([0x50]))

        # Add partial data
        merger.add_data(frame[:3])
        # Reset
        merger.reset()
        # Now add a complete frame - should work from scratch
        result = merger.add_data(frame)
        assert result == frame

    def test_merger_invalid_header(self):
        """First packet with wrong header returns None and resets."""
        merger = TDataMerger()
        bad_data = bytes([0xBB, 0x00, 0x05, 0x02, 0x32])
        result = merger.add_data(bad_data)
        assert result is None

        # Merger should be reset - verify by adding a valid frame
        frame = build_frame(0x06, bytes([0x01]))
        result = merger.add_data(frame)
        assert result == frame

    def test_merger_empty_data(self):
        """Empty bytes return None."""
        merger = TDataMerger()
        assert merger.add_data(b"") is None
