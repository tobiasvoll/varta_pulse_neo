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

### Write test on a pulse neo 6 (2026-10-29)

`tools/varta_control_test.py` wrote 1074 = −1000 and 1075 = 1000 once and then
read 1065–1075 every 5 s:

- Both writes (function code 6) were accepted without a Modbus exception and
  read back immediately.
- 1073 jumped to 119 after the first write, stayed at 119 after the second one
  (each write restarts it) and counted down one per second.
- At 0 the device restored 1074 = −32768 and 1075 = −1 on its own, so
  "no limit" reads as −32768/−1 on this device, not −4000/4000.
- The battery was charging with about 460 W, below the 1000 W limit, so this
  run did not show whether the limit takes effect.

Second run, 1075 = 200 only: accepted, but the timer stayed at 0 and the value
was **not** reset (it still read 200 minutes later). Charging continued at
460–635 W. Writing 1075 alone does not start the watchdog.

Third run, 1074 = −2500 then 1075 = 200: the timer started, both values were
reset at 0 as before, but charging stayed at 500–640 W the whole time. **The
charge limit has no visible effect** on this device (EMS 2.60.6). The discharge
limit (1074 = 0 blocks discharging, used by evcc) could not be checked because
the battery was charging during all runs. Writing the defaults back
(−32768/−1) restarts the timer harmlessly.

## Differences between v13.1 and v13.4

- Registers 1082–1087 and 1102 were marked "pulse only" in v13.1 and are
  available on the pulse neo from v13.4. Older pulse neo firmware may answer
  them with an exception.
- Scale factors 2083–2086 are new in v13.4.
- 1087 changed from UINT16 to SINT16.
- Flex storage lost ENS/inverter versions and the module count, and gained
  1082–1086.

## Measured on a pulse neo 6 (2026-10-29)

EMS 2.60.6, inverter 1.5.4, table version 13, one battery module, unit id 255.
Battery at 1 % SoC, state switching between 4 (standby) and 0 (busy).

| Addr | Value | Reading |
|---|---|---|
| 1000–1050 | one ASCII char per register | confirms the document; ENS reads "0.0.0." |
| 1052/1053 | 8823 / 27363 | valid Unix time (lower word first), works |
| 1069/1070 | 47038 / 23 | 1 554 366 Wh charged in total |
| 1071 | 586, sometimes 279 | 5860 Wh or 2790 Wh: **not constant** |
| 1085/1086 | 5809 / 58, then 2763 / 27 | follow 1071 (capacity × (1 − SoC) and × SoC) |
| 1083/1084 | 2500 / 1557 in standby, 0 / 0 while busy | |
| 1078 | −106 … −129 | grid consumption, sign as documented |
| 1082 | 5002–5005 | 50.02 Hz, fixed ×0.01 |
| 1102 | 0 | no PV sensor installed |
| 1074 / 1075 | −32768 / −1 | **not** the −4000 / 4000 defaults reported by evcc users |
| 1073 | 0 | no control timer running |
| 1090 / 1091 | 2500 / 2500 | undocumented; likely the nominal 2.5 kW charge/discharge power |
| 1076, 1079–1081, 1088, 1089 | 24980, 38822, 2181, 11876, 278, 1001 | undocumented, meaning unknown |
| 2066–2086 (documented) | all 0 | no scaling on this device |
| 2072, 2073, 2076, 2079–2082 | −1 | undocumented; 2082 must **not** be applied to the frequency |

Refused with exception 2 (illegal address) when read on their own: 1092–1099,
1103–1110, 2000–2065, 2068, 2070, 2087–2099, 2102–2110.

Block reads behave differently: the integration's block 2066–2086 is accepted
(confirmed in Home Assistant, all sensors deliver values), although it contains
2068 and 2070. Blocks that started or ended on a refused address (2068–2070,
1000–1099, 2000–2099) were rejected. The device apparently only checks the
first and last address of a block.

## Findings for the current code

1. **Capacity scaling matches the document.** Raw × 10 Wh × 10^SF2071 is what
   VARTA specifies, and SF 2071 is 0 on the measured device. The value is not
   constant though (5860 / 2790 Wh), so it must not be treated as a fixed
   device property.
2. **Block reads depend on undocumented behaviour.** The integration reads
   2066–2086 as one block although 2068 and 2070 are refused on their own. It
   works on the measured device because only the block boundaries seem to be
   checked, but VARTA does not promise this, and older pulse neo firmware may
   refuse 1082–1087. Blocks should start and end on documented registers, with
   a fallback for optional registers, so one refused read does not make every
   sensor unavailable.
3. **Strings are one character per register.** The current decoder takes two
   bytes per register and drops the null bytes, which gives the right result,
   but it should decode the low byte only.
4. **Only a charge counter exists.** Discharged energy has to be integrated from
   the discharge power inside the integration.
5. **Apparent power** is split into charge/discharge sensors, which adds little;
   one signed sensor is enough.
6. **Timestamp (1052/1053)**, **error code (1072)** and the **control registers
   (1073–1075)** are not exposed. Control was dropped for now after the write
   tests above: the charge limit had no effect, the discharge limit is untested.
7. Sign conventions of 1066 and 1078, the unit id default 255, the PV sensor at
   1102 and the 30 s poll interval all match the document and the device.
8. **Control registers need a careful test.** 1074/1075 read −32768/−1 on this
   device instead of the −4000/4000 reported elsewhere, so their behaviour has
   to be confirmed with a supervised write before step 3 relies on them.

## Sources

- VARTA *Modbus TCP documentation* v13.4 public (2021-01-11) and v13.1 public (2020-05-04), not redistributed here
- evcc VARTA template: <https://github.com/evcc-io/evcc/blob/master/templates/definition/meter/varta.yaml>
- evcc discussion on discharge lock: <https://github.com/evcc-io/evcc/discussions/19631>
- vartastorage library: <https://github.com/Vip0r/vartastorage>
- HA community thread: <https://community.home-assistant.io/t/varta-storage-modbus-workaround/600316>
- ioBroker thread: <https://forum.iobroker.net/topic/46256/modbus-varta-pulse-neo-register-illegal-data-address>
