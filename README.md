# Varta Pulse Neo

Custom Home Assistant integration for the Varta Pulse Neo battery system via Modbus TCP.

## Features

- Set up from the UI (config flow); the device is identified by its serial number
- Local polling every 30 seconds over one persistent Modbus TCP connection (pymodbus)
- Energy dashboard support: charged energy from the device counter, discharged energy integrated from the discharge power
- Battery state as an enum sensor with translated values
- English and German translations
- Diagnostics download (host and serial number removed) for bug reports
- Register map checked against the official VARTA Modbus documentation v13.4 and a real pulse neo 6 ([docs/registers.md](docs/registers.md))

## Entities

| Entity | Unit | Notes |
| --- | --- | --- |
| State | | Busy, Ready, Charging, Discharging, Standby, Error, Passive (service), Islanding |
| Battery | % | State of charge |
| Charge power / Discharge power | W | Split from the signed battery power (register 1066) |
| Grid feed-in / Grid consumption | W | Split from the signed grid power (register 1078) |
| Charged energy | kWh | Device counter, `total_increasing`, use it as "Energy going in to the battery" |
| Discharged energy | kWh | Integrated by Home Assistant from the discharge power, use it as "Energy coming out of the battery", see below |
| Installed capacity, Usable energy for charging / discharging | kWh | |
| Available AC charging / discharging power | W | |
| Grid frequency | Hz | |
| PV sensor power | W | Only meaningful with a VARTA PV sensor |
| Installed battery modules | | |
| EMS, ENS and inverter software versions | | Diagnostic |
| Charge/discharge apparent power, reactive power, Modbus table version, serial number | | Disabled by default |

### Discharged energy

The device has no counter for discharged energy. The integration integrates the
discharge power over time (trapezoid rule) and restores the value after a restart.
It starts at 0 when first installed. Gaps longer than 5 minutes (for example while
the battery is unreachable) are not integrated, so the value can be slightly lower
than the real discharged energy.

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
- The device allows at most one Modbus request per second; the integration spaces its requests accordingly.
- Values are read in blocks and the scale factor registers (2066-2086) are applied. They are re-read every hour and never written.
- Requires Home Assistant with pymodbus 3.11.2 or newer.

## Tools

- `tools/varta_control_test.py`: supervised write test for the undocumented control registers 1074/1075. It writes to the battery, only use it if you know what you are doing; results in [docs/registers.md](docs/registers.md).
- `tools/varta_probe.py`: read-only register dump of a device (Python standard library only). Useful for bug reports: `python3 tools/varta_probe.py <host>`. The output contains the serial number, remove it before posting.

## Development

```bash
pip install -r requirements_test.txt ruff
ruff check custom_components tests && ruff format --check custom_components tests
pytest
```

## Support

- Issues: https://github.com/tobiasvoll/varta_pulse_neo/issues
- Please attach the diagnostics file: `Settings` -> `Devices & services` -> `Varta Pulse Neo` -> menu -> `Download diagnostics`. Host and serial number are removed.

