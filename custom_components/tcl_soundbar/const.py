"""Constants for the TCL Soundbar integration."""
from __future__ import annotations

DOMAIN = "tcl_soundbar"

# --- BLE UUIDs ---
# The TCL soundbar advertises with service UUID FFF6 so Home Assistant's
# bluetooth integration can discover it. However, once connected, the actual
# GATT services use different UUIDs. This was determined by connecting to the
# device and enumerating its services (see the discover_characteristics action).

# UUID the device advertises (used in manifest.json for HA bluetooth discovery)
ADVERTISED_SERVICE_UUID = "0000fff6-0000-1000-8000-00805f9b34fb"

# UUIDs exposed after BLE connection (used for actual communication)
# The device exposes these under service e49a25f8-... and also under 0000f500-...
# (both contain the same characteristic UUIDs).
GATT_SERVICE_UUID = "e49a25f8-f69a-11e8-8eb2-f2801f1b9fd1"
GATT_WRITE_CHAR_UUID = "e49a25e0-f69a-11e8-8eb2-f2801f1b9fd1"
GATT_NOTIFY_CHAR_UUID = "e49a28e1-f69a-11e8-8eb2-f2801f1b9fd1"

# --- Frame format ---
# All commands use a simple framing protocol starting with 0xAA header byte
FRAME_HEADER = 0xAA

# --- SET command bytes (sent to device) ---
# These are the command IDs used when sending instructions to the soundbar.
CMD_SET_VOLUME = 0x02
CMD_SET_POWER = 0x06
CMD_SET_MUTE = 0x0E
CMD_SET_SOURCE = 0x0F
CMD_GET_VERSION = 0x18

# --- REPORT command bytes (received from device) ---
# These are the command IDs the soundbar uses when reporting state back
# via BLE notifications. The IDs are offset from the SET commands (typically
# SET + 0x82 for the corresponding report).
CMD_REPORT_VOLUME = 0x84
CMD_REPORT_POWER = 0x88
CMD_REPORT_SOURCE = 0x91

# --- Source mapping ---
# Maps human-readable source names to the byte IDs used in the BLE protocol.
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

# Reverse source mapping (ID -> name) for decoding device reports
SOURCE_MAP_REVERSE: dict[int, str] = {v: k for k, v in SOURCE_MAP.items()}
