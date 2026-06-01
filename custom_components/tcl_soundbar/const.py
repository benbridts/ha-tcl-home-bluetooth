"""Constants for the TCL Soundbar integration."""
from __future__ import annotations

DOMAIN = "tcl_soundbar"

# BLE Service UUID (lowercase for HA bluetooth matching)
SERVICE_UUID = "0000fff6-0000-1000-8000-00805f9b34fb"

# Frame format
FRAME_HEADER = 0xAA

# SET command bytes (sent to device)
CMD_SET_VOLUME = 0x02
CMD_SET_BASS = 0x04
CMD_SET_TREBLE = 0x05
CMD_SET_POWER = 0x06
CMD_SET_MUTE = 0x0E
CMD_SET_SOURCE = 0x0F
CMD_SET_EQ_MODE = 0x11
CMD_GET_VERSION = 0x18

# REPORT command bytes (received from device)
CMD_REPORT_VOLUME = 0x84
CMD_REPORT_RC_INDEX = 0x85
CMD_REPORT_POWER = 0x88
CMD_REPORT_SOURCE = 0x91
CMD_REPORT_EQ_MODE = 0x93

# Source mapping (name -> ID)
SOURCE_MAP: dict[str, int] = {
    "HDMI": 0,
    "HDMI1": 1,
    "HDMI2": 2,
    "HDMI eARC": 3,
    "Optical": 4,
    "AUX": 5,
    "USB": 6,
    "WiFi": 7,
    "Bluetooth": 8,
}

# Reverse source mapping (ID -> name)
SOURCE_MAP_REVERSE: dict[int, str] = {v: k for k, v in SOURCE_MAP.items()}
