# TCL Home Soundbar

A Home Assistant custom integration for controlling TCL soundbars that use the TCL Home app via Bluetooth LE.

## Features

- Power on/off
- Volume control
- Mute
- Source selection

## Prerequisites

- A Bluetooth adapter on the Home Assistant host (built-in or USB)

## Installation

### HACS (Recommended)

1. Open HACS in your Home Assistant instance.
2. Go to **Integrations** and click the three-dot menu in the top right.
3. Select **Custom repositories**.
4. Add the repository URL: `https://github.com/benbridts/ha-tcl-home-bluetooth`
5. Set the category to **Integration**.
6. Click **Add**.
7. Search for "TCL Home Soundbar" in HACS and install it.
8. Restart Home Assistant.

### Manual Installation

1. Download or clone this repository.
2. Copy the `custom_components/tcl_soundbar` directory to your Home Assistant `config/custom_components/` directory.
3. Restart Home Assistant.

## Configuration

The integration auto-discovers TCL soundbars via Bluetooth. If your device is not discovered automatically, you can add it manually via **Settings > Devices & Services > Add Integration** and search for "TCL Home Soundbar".

## Supported Devices

### Known Compatible

- TCL S55HE Soundbar

### Other Devices

Other TCL soundbars that are compatible with the TCL Home app should also work. If you have a device that works (or does not work), please open an issue to help expand this list.
