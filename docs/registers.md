# VARTA Modbus register map

The primary source is VARTA's public *Modbus TCP documentation*, version 13.4
(2021-01-11, table version 13). Version 13.1 (2020-05-04) was compared as well.
Registers VARTA does not document come from community sources and are marked
as such. Values still to be confirmed on a real device can be checked with
[`tools/varta_probe.py`](../tools/varta_probe.py).

## Connection (official)

| Item | Value |
|---|---|
| Protocol | Modbus TCP, port 502, all registers 16 bit holding registers |
| Unit id | any unit id is accepted, 255 is recommended |
| Request interval | at most 1 request per second (VARTA link: 1 per 5 s) |
| 32-bit values | split into two registers, lower word first |
| Strings | one character per register |

## Registers

"R" read only, "WR" writable. "neo" is the support for the pulse neo as stated
in v13.4. "Code" is whether the integration reads the register today.

| Addr | Name | Type | Unit | Access | neo | Code | Notes |
|---|---|---|---|---|---|---|---|
| 1000 | Software version EMS | STRING17 | | R | ✔ | ✓ | |
| 1017 | Software version ENS | STRING17 | | R | ✔ | ✓ | |
| 1034 | Software version inverter | STRING17 | | R | ✔ | ✓ | |
| 1051 | Table version | UINT16 | | R | ✔ | ✓ | 13 for this document |
| 1052 | Timestamp, lower word | UINT16 | | R | ✔ | – | 32-bit Unix timestamp |
| 1053 | Timestamp, higher word | UINT16 | | R | ✔ | – | |
| 1054 | Serial number | STRING10 | | R | ✔ | ✓ | 9 digits |
| 1064 | Installed battery modules | UINT16 | | R | ✔ | ✓ | |
| 1065 | State | UINT16 | | R | ✔ | ✓ | 0 Busy, 1 Run, 2 Charge, 3 Discharge, 4 Standby, 5 Error, 6 Passive (service), 7 Islanding |
| 1066 | Active power | SINT16 | 1 W | R | ✔ | ✓ | + charge, − discharge; SF 2066 |
| 1067 | Apparent power | SINT16 | 1 VA | R | ✔ | ✓ | + charge, − discharge; SF 2067 |
| 1068 | State of charge | UINT16 | 1 % | R | ✔ | ✓ | |
| 1069 | Energy counter AC→DC, lower word | UINT16 | 1 Wh | R | ✔ | ✓ | total charged energy; SF 2069 |
| 1070 | Energy counter AC→DC, higher word | UINT16 | 1 Wh | R | ✔ | ✓ | |
| 1071 | Installed capacity | UINT16 | 10 Wh | R | ✔ | ✓ | SF 2071 |
| 1078 | Grid power | SINT16 | 1 W | R | ✔ | ✓ | + feed-in, − consumption; SF 2078 |
| 1082 | Grid frequency | UINT16 | 0.01 Hz | R | ✔ | ✓ | |
| 1083 | Available AC charging power | UINT16 | 1 W | R | ✔ | ✓ | SF 2083 |
| 1084 | Available AC discharging power | UINT16 | 1 W | R | ✔ | ✓ | SF 2084 |
| 1085 | Usable energy for charging | UINT16 | 1 Wh | R | ✔ | ✓ | SF 2085 |
| 1086 | Usable energy for discharging | UINT16 | 1 Wh | R | ✔ | ✓ | SF 2086 |
| 1087 | Reactive power | SINT16 | 1 var | R | ✔ | ✓ | UINT16 in v13.1 |
| 1102 | PV sensor power | UINT16 | 1 W | R | ✔ | ✓ | only with VARTA PV sensor |
| 2066 | Active power SF | SINT16 | exponent | WR | ✔ | ✓ | value × 10^SF |
| 2067 | Apparent power SF | SINT16 | exponent | WR | ✔ | ✓ | |
| 2069 | Energy counter SF | SINT16 | exponent | WR | ✔ | ✓ | |
| 2071 | Capacity SF | SINT16 | exponent | WR | ✔ | ✓ | |
| 2078 | Grid power SF | SINT16 | exponent | WR | ✔ | ✓ | |
| 2083 | Available AC charging power SF | SINT16 | exponent | WR | ✔ | ✓ | new in v13.4 |
| 2084 | Available AC discharging power SF | SINT16 | exponent | WR | ✔ | ✓ | new in v13.4 |
| 2085 | Usable energy for charging SF | SINT16 | exponent | WR | ✔ | ✓ | new in v13.4 |
| 2086 | Usable energy for discharging SF | SINT16 | exponent | WR | ✔ | ✓ | new in v13.4 |

The scale factor registers are writable. The integration must never write them.

### Undocumented registers (community sources)

| Addr | Name | Type | Access | Notes |
|---|---|---|---|---|
| 1072 | Error code | UINT16 | R | used by vartastorage |
| 1073 | Control timer | SINT16 | R | set to 120 after a write to 1074/1075, counts down in seconds |
| 1074 | Max discharge power | SINT16 W | WR | default −4000, 0 blocks discharge |
| 1075 | Max charge power | SINT16 W | WR | default 4000, 0 blocks charge |
| 1100, 1101 | unknown | | WR | seen on an element, purpose unknown |
| 1088 | "PV sensor power" | | | listed by older forum posts; not in the VARTA document, 1102 is correct |

Writing 1074 or 1075 starts the 120 s countdown in 1073. When it reaches 0 the
register falls back to its default, so a limit has to be rewritten before the
timer expires (evcc rewrites every 60 s). Reported working on pulse neo 6 and
element S4/S5, not through a UNIEQ LAN box. VARTA confirmed these registers to
evcc users but has not published them yet.

## Differences between v13.1 and v13.4

- Registers 1082–1087 and 1102 were marked "pulse only" in v13.1 and are
  available on the pulse neo from v13.4. Older pulse neo firmware may answer
  them with an exception.
- Scale factors 2083–2086 are new in v13.4.
- 1087 changed from UINT16 to SINT16.
- Flex storage lost ENS/inverter versions and the module count, and gained
  1082–1086.

## Findings for the current code

1. **Capacity scaling matches the document.** Raw × 10 Wh × 10^SF2071 is what
   VARTA specifies. It is only wrong if the device reports a non-zero SF in
   addition to already scaled values; the probe will show this.
2. **Block reads cover undocumented registers.** The integration reads
   1000–1087 and 2066–2086 in single blocks, which include undocumented
   addresses (1072–1081, 2068, 2070, 2072–2077, 2079–2082). If the device
   refuses any of them, or older firmware refuses 1082–1087, every sensor
   becomes unavailable. Blocks should follow the documented ranges, with a
   fallback for optional registers.
3. **Strings are one character per register.** The current decoder takes two
   bytes per register and drops the null bytes, which gives the right result,
   but it should decode the low byte only.
4. **Only a charge counter exists.** Discharged energy has to be integrated from
   the discharge power inside the integration.
5. **Apparent power** is split into charge/discharge sensors, which adds little;
   one signed sensor is enough.
6. **Timestamp (1052/1053)**, **error code (1072)** and the **control registers
   (1073–1075)** are not exposed.
7. Sign conventions of 1066 and 1078, the unit id default 255, the PV sensor at
   1102 and the 30 s poll interval all match the document.

## Sources

- VARTA *Modbus TCP documentation* v13.4 public (2021-01-11) and v13.1 public (2020-05-04), not redistributed here
- evcc VARTA template: <https://github.com/evcc-io/evcc/blob/master/templates/definition/meter/varta.yaml>
- evcc discussion on discharge lock: <https://github.com/evcc-io/evcc/discussions/19631>
- vartastorage library: <https://github.com/Vip0r/vartastorage>
- HA community thread: <https://community.home-assistant.io/t/varta-storage-modbus-workaround/600316>
- ioBroker thread: <https://forum.iobroker.net/topic/46256/modbus-varta-pulse-neo-register-illegal-data-address>
