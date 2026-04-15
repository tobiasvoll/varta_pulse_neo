# Varta Pulse Neo

Custom Home Assistant integration for the Varta Pulse Neo battery system via Modbus TCP.

## Features

- Config flow support
- Local polling via Modbus TCP
- Directional power sensors for charge/discharge and grid feed-in/consumption
- Device information and battery status sensors
- Local brand assets for the integration card

## Installation

### HACS

1. Open HACS.
2. Add this repository as a custom repository:
   `https://github.com/tobiasvoll/varta_pulse_neo`
3. Select the category `Integration`.
4. Install `Varta Pulse Neo`.
5. Restart Home Assistant.
6. Add the integration under `Settings` -> `Devices & services`.

### Manual

1. Copy `custom_components/varta_pulse_neo` into your Home Assistant `custom_components` directory.
2. Restart Home Assistant.
3. Add the integration under `Settings` -> `Devices & services`.

## Configuration

The config flow asks for:

- `host`
- `port`
- `slave_id`
- `name`

The manufacturer documentation recommends Modbus unit ID `255`.

## Notes

- Communication is local only (`iot_class: local_polling`).
- The integration uses block reads and applies internal scale factors where required.

## Support

- Issues: https://github.com/tobiasvoll/varta_pulse_neo/issues

