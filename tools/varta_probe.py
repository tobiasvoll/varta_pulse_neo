#!/usr/bin/env python3
"""Read-only Modbus TCP probe for VARTA storage systems (pulse neo, element, ...).

Dumps the raw holding registers 1000-1110 and 2000-2110 so the register map
used by the integration can be checked against a real device. The script only
uses function code 0x03 (read holding registers) and never writes anything.

Usage:
    python3 varta_probe.py 192.168.1.50
    python3 varta_probe.py 192.168.1.50 --unit 255 --samples 10 --interval 3

The result is printed as a table and saved as JSON (default: varta_probe.json).
Only the Python standard library is required.
"""

from __future__ import annotations

import argparse
import json
import socket
import struct
import sys
import time
from datetime import datetime, timezone

RANGES = ((1000, 111), (2000, 111))
DYNAMIC_RANGE = (1065, 40)
MAX_BLOCK = 100

# Community knowledge, see docs/registers.md. "?" marks unverified entries.
KNOWN = {
    1000: "EMS software version (string, 17 reg)",
    1017: "ENS software version (string, 17 reg)",
    1034: "Inverter software version (string, 17 reg)",
    1051: "Table version",
    1052: "Timestamp (uint32, word swapped?)",
    1054: "Serial number (string, 10 reg)",
    1064: "Installed battery modules",
    1065: "State",
    1066: "Active power (int16, + charge / - discharge)",
    1067: "Apparent power (int16)",
    1068: "State of charge (%)",
    1069: "Energy counter AC->DC low word?",
    1070: "Energy counter AC->DC high word?",
    1071: "Installed capacity (x10 Wh?)",
    1072: "Error code",
    1073: "Control timer (counts down after write to 1074/1075)",
    1074: "Max discharge power (int16, writable, default -4000)",
    1075: "Max charge power (int16, writable, default 4000)",
    1078: "Grid power (int16, + feed-in / - consumption?)",
    1082: "Grid frequency (x0.01 Hz)",
    1083: "Available AC charging power",
    1084: "Available AC discharging power",
    1085: "Usable energy for charging",
    1086: "Usable energy for discharging",
    1087: "Reactive power (int16)",
    1088: "PV sensor power? (older sources)",
    1102: "PV sensor power (newer sources)",
    2066: "Scale factor active power",
    2067: "Scale factor apparent power",
    2069: "Scale factor energy counter",
    2071: "Scale factor capacity",
    2078: "Scale factor grid power",
    2083: "Scale factor available AC charging power",
    2084: "Scale factor available AC discharging power",
    2085: "Scale factor usable energy for charging",
    2086: "Scale factor usable energy for discharging",
}

STRINGS = {1000: 17, 1017: 17, 1034: 17, 1054: 10}


class ModbusError(Exception):
    """Raised for Modbus exception responses."""


class ModbusTcp:
    def __init__(self, host: str, port: int, unit: int, timeout: float) -> None:
        self._sock = socket.create_connection((host, port), timeout=timeout)
        self._unit = unit
        self._tid = 0

    def close(self) -> None:
        self._sock.close()

    def _recv_exact(self, size: int) -> bytes:
        data = b""
        while len(data) < size:
            chunk = self._sock.recv(size - len(data))
            if not chunk:
                raise ConnectionError("connection closed by device")
            data += chunk
        return data

    def read_holding(self, address: int, count: int) -> list[int]:
        self._tid = (self._tid + 1) & 0xFFFF
        pdu = struct.pack(">BHH", 3, address, count)
        self._sock.sendall(struct.pack(">HHHB", self._tid, 0, len(pdu) + 1, self._unit) + pdu)
        while True:
            tid, _, length, _ = struct.unpack(">HHHB", self._recv_exact(7))
            body = self._recv_exact(length - 1)
            if tid == self._tid:
                break
        if body[0] == 0x83:
            raise ModbusError(f"exception code {body[1]}")
        byte_count = body[1]
        payload = body[2 : 2 + byte_count]
        return [int.from_bytes(payload[i : i + 2], "big") for i in range(0, byte_count, 2)]


def read_range(client: ModbusTcp, start: int, count: int) -> tuple[dict[int, int], dict[int, str]]:
    values: dict[int, int] = {}
    errors: dict[int, str] = {}
    for block_start in range(start, start + count, MAX_BLOCK):
        block_count = min(MAX_BLOCK, start + count - block_start)
        try:
            for i, reg in enumerate(client.read_holding(block_start, block_count)):
                values[block_start + i] = reg
            continue
        except ModbusError:
            pass
        # Block read refused: fall back to single registers to find the gaps.
        for address in range(block_start, block_start + block_count):
            try:
                values[address] = client.read_holding(address, 1)[0]
            except ModbusError as err:
                errors[address] = str(err)
    return values, errors


def to_int16(value: int) -> int:
    return value - 0x10000 if value > 0x7FFF else value


def decode_string(values: dict[int, int], start: int, count: int) -> str | None:
    regs = [values.get(a) for a in range(start, start + count)]
    if any(r is None for r in regs):
        return None
    raw = b"".join(r.to_bytes(2, "big") for r in regs)
    return raw.replace(b"\x00", b"").decode("ascii", errors="replace").strip()


def find_unit(args) -> int:
    candidates = [args.unit] if args.unit is not None else [255, 1, 0]
    for unit in candidates:
        try:
            client = ModbusTcp(args.host, args.port, unit, args.timeout)
            try:
                client.read_holding(1065, 1)
                return unit
            finally:
                client.close()
        except (OSError, ModbusError) as err:
            print(f"unit {unit}: no answer ({err})", file=sys.stderr)
    sys.exit("No unit id answered. Check host, port and that Modbus TCP is enabled.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("host")
    parser.add_argument("--port", type=int, default=502)
    parser.add_argument("--unit", type=int, default=None, help="Modbus unit id (default: try 255, 1, 0)")
    parser.add_argument("--timeout", type=float, default=5.0)
    parser.add_argument("--samples", type=int, default=5, help="samples of the live registers 1065-1104")
    parser.add_argument("--interval", type=float, default=5.0, help="seconds between samples")
    parser.add_argument("--output", default="varta_probe.json")
    args = parser.parse_args()

    unit = find_unit(args)
    print(f"Using unit id {unit}")

    client = ModbusTcp(args.host, args.port, unit, args.timeout)
    values: dict[int, int] = {}
    errors: dict[int, str] = {}
    try:
        for start, count in RANGES:
            v, e = read_range(client, start, count)
            values.update(v)
            errors.update(e)

        samples = []
        for n in range(args.samples):
            if n:
                time.sleep(args.interval)
            v, _ = read_range(client, *DYNAMIC_RANGE)
            samples.append({"time": datetime.now(timezone.utc).isoformat(), "registers": v})
            print(
                f"sample {n + 1}/{args.samples}: state={v.get(1065)} "
                f"active={to_int16(v.get(1066, 0))} soc={v.get(1068)} grid={to_int16(v.get(1078, 0))}"
            )
    finally:
        client.close()

    print(f"\n{'addr':>5} {'hex':>6} {'uint16':>6} {'int16':>6}  meaning")
    for address in sorted(set(values) | set(errors)):
        if address in errors:
            print(f"{address:>5} {'-':>6} {'-':>6} {'-':>6}  {errors[address]}  {KNOWN.get(address, '')}")
            continue
        value = values[address]
        if value == 0 and address not in KNOWN:
            continue
        print(f"{address:>5} {value:#06x} {value:>6} {to_int16(value):>6}  {KNOWN.get(address, '')}")

    strings = {str(a): decode_string(values, a, c) for a, c in STRINGS.items()}
    print("\nStrings:")
    for address, text in strings.items():
        print(f"  {address}: {text!r}")

    result = {
        "probe_version": 1,
        "time": datetime.now(timezone.utc).isoformat(),
        "port": args.port,
        "unit": unit,
        "registers": {str(a): v for a, v in sorted(values.items())},
        "errors": {str(a): e for a, e in sorted(errors.items())},
        "strings": strings,
        "samples": [{"time": s["time"], "registers": {str(a): v for a, v in s["registers"].items()}} for s in samples],
    }
    with open(args.output, "w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=1)
    print(f"\nSaved to {args.output}. Note: the serial number is included, remove it before sharing publicly.")


if __name__ == "__main__":
    main()
