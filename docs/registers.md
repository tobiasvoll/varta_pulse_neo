# VARTA Modbus register map

VARTA does not publish its Modbus documentation openly. This map is compiled
from public sources and compared with what the integration currently reads.
Entries marked **unverified** need confirmation on a real device with
[`tools/varta_probe.py`](../tools/varta_probe.py).

## Connection

| Item | Value | Source |
|---|---|---|
| Protocol | Modbus TCP, port 502 | all sources |
| Unit id | 255 (some setups answer on 1) | evcc template, HA community |
| Function | 0x03 read holding registers, 0x06 write single register | evcc template |
| Word order of 32-bit values | low word first (word swapped) | vartastorage, HA community |

## Registers

All registers are holding registers. "R" read only, "RW" writable.

| Addr | Name | Type | Unit / scale | Access | Integration today | Notes |
|---|---|---|---|---|---|---|
| 1000 | EMS software version | string ×17 | | R | ✓ | |
| 1017 | ENS software version | string ×17 | | R | ✓ | |
| 1034 | Inverter software version | string ×17 | | R | ✓ | |
| 1051 | Table version | uint16 | | R | ✓ | |
| 1052 | Timestamp | uint32 sw | | R | – | reported as not working |
| 1054 | Serial number | string ×10 | | R | ✓ | |
| 1064 | Installed battery modules | uint16 | | R | ✓ | |
| 1065 | State | uint16 | enum 0–7 | R | ✓ | 0 Busy, 1 Run, 2 Charge, 3 Discharge, 4 Standby, 5 Error, 6 Passive (service), 7 Islanding |
| 1066 | Active power | int16 | W, SF 2066 | R | ✓ | + charge, − discharge |
| 1067 | Apparent power | int16 | VA, SF 2067 | R | ✓ | |
| 1068 | State of charge | uint16 | % | R | ✓ | |
| 1069 | Energy counter AC→DC (charged) | uint32 sw | Wh, SF 2069 | R | ✓ | total increasing; no discharge counter exists |
| 1071 | Installed capacity | uint16 | ×10 Wh, SF 2071 | R | ✓ | **unverified**: code applies ×10 *and* SF 2071 |
| 1072 | Error code | uint16 | | R | – | |
| 1073 | Control timer | int16 | s | R | – | set to 120 after a write to 1074/1075, counts down |
| 1074 | Max discharge power | int16 | W | RW | – | default −4000, 0 blocks discharge, resets after timer |
| 1075 | Max charge power | int16 | W | RW | – | default 4000, 0 blocks charge, resets after timer |
| 1078 | Grid power | int16 | W, SF 2078 | R | ✓ | + feed-in, − consumption |
| 1082 | Grid frequency | uint16 | ×0.01 Hz | R | ✓ | |
| 1083 | Available AC charging power | uint16 | W, SF 2083 | R | ✓ | |
| 1084 | Available AC discharging power | uint16 | W, SF 2084 | R | ✓ | |
| 1085 | Usable energy for charging | uint16 | Wh, SF 2085 | R | ✓ | |
| 1086 | Usable energy for discharging | uint16 | Wh, SF 2086 | R | ✓ | |
| 1087 | Reactive power | int16 | var | R | ✓ | |
| 1088 | PV sensor power | uint16 | W | R | – | **unverified**: older sources use 1088, newer 1102 |
| 1102 | PV sensor power | uint16 | W | R | ✓ | only with external PV sensor |
| 2066–2086 | Scale factors | int16 | 10^n | R | ✓ | **unverified** whether any are non-zero |

Unknown but present: 1076, 1077, 1079–1081, 1089–1101 (1100 and 1101 are
writable on an element, purpose unknown).

## Control behaviour (1073–1075)

Writing 1074 or 1075 starts a 120 s countdown in 1073. When it reaches 0 the
register falls back to its default (−4000 / 4000), so a limit has to be
rewritten before the timer expires (evcc rewrites every 60 s). Reported on
pulse neo 6 and element S4/S5. Values between 0 and about −500 W other than 0
were rejected on some devices. Writes through a UNIEQ LAN box had no effect.
VARTA confirmed these registers to evcc users but has not documented them yet.

## Findings for the current code

1. **Capacity may be scaled twice** (`const.py`, key `capacity`): fixed `scale=10`
   plus SF 2071. If SF 2071 is 1 the value is 100× too high.
2. **Energy counter** is the only counter VARTA provides. Discharged energy has
   to be integrated from the discharge power inside the integration.
3. **Apparent power split** into charge/discharge sensors makes little sense;
   one signed sensor is enough.
4. **Error code (1072)** and the **control registers (1073–1075)** are not exposed.
5. **PV sensor address** 1088 vs 1102 needs checking.
6. Sign conventions of 1066 and 1078 used by the code match all sources.

## Sources

- evcc VARTA template: <https://github.com/evcc-io/evcc/blob/master/templates/definition/meter/varta.yaml>
- evcc discussion on discharge lock: <https://github.com/evcc-io/evcc/discussions/19631>
- vartastorage library: <https://github.com/Vip0r/vartastorage>
- HA community thread: <https://community.home-assistant.io/t/varta-storage-modbus-workaround/600316>
- ioBroker thread: <https://forum.iobroker.net/topic/46256/modbus-varta-pulse-neo-register-illegal-data-address>
