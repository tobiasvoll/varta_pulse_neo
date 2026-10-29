#!/usr/bin/env python3
"""Supervised write test for the undocumented VARTA control registers.

Writes one power limit to 1074 (max discharge power, written negative) and/or
1075 (max charge power), then reads 1065-1075 every 5 seconds to see whether
the device accepts the value, starts the countdown in 1073 and falls back to
its default afterwards. Nothing is written again after the first write.

Usage:
    python3 varta_control_test.py 192.168.1.50 --limit 1000
    python3 varta_control_test.py 192.168.1.50 --limit 1000 --only discharge
    python3 varta_control_test.py 192.168.1.50 --discharge 2500 --charge 200 --restore

--discharge/--charge set each register on its own (1074 is written first).
--restore writes the values read before the test back at the end.

Stop at any time with Ctrl+C. The result is saved as JSON
(default: varta_control_test.json). Only the Python standard library is used.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import struct
import sys
import time

from varta_probe import ModbusError, ModbusTcp, to_int16

WATCH = (1065, 11)  # state ... max charge power


class WritableModbusTcp(ModbusTcp):
    def write_single(self, address: int, value: int) -> None:
        wait = self._last_request + 1.0 - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        self._last_request = time.monotonic()
        self._tid = (self._tid + 1) & 0xFFFF
        pdu = struct.pack(">BHH", 6, address, value & 0xFFFF)
        self._sock.sendall(struct.pack(">HHHB", self._tid, 0, len(pdu) + 1, self._unit) + pdu)
        while True:
            tid, _, length, _ = struct.unpack(">HHHB", self._recv_exact(7))
            body = self._recv_exact(length - 1)
            if tid == self._tid:
                break
        if body[0] == 0x86:
            raise ModbusError(f"write refused, exception code {body[1]}")


def snapshot(client: WritableModbusTcp) -> dict[str, int]:
    regs = client.read_holding(*WATCH)
    values = dict(zip(range(WATCH[0], WATCH[0] + WATCH[1]), regs, strict=True))
    return {
        "state": values[1065],
        "active_power": to_int16(values[1066]),
        "soc": values[1068],
        "timer_1073": to_int16(values[1073]),
        "max_discharge_1074": to_int16(values[1074]),
        "max_charge_1075": to_int16(values[1075]),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("host")
    parser.add_argument("--port", type=int, default=502)
    parser.add_argument("--unit", type=int, default=255)
    parser.add_argument("--limit", type=int, default=1000, help="power limit in W (100-2500)")
    parser.add_argument("--only", choices=("discharge", "charge"))
    parser.add_argument("--discharge", type=int, help="discharge limit in W, overrides --limit/--only")
    parser.add_argument("--charge", type=int, help="charge limit in W, overrides --limit/--only")
    parser.add_argument("--restore", action="store_true", help="write the original values back at the end")
    parser.add_argument("--duration", type=int, default=150, help="seconds to watch after the write")
    parser.add_argument("--output", default="varta_control_test.json")
    args = parser.parse_args()
    if not 100 <= args.limit <= 2500:
        sys.exit("--limit must be between 100 and 2500 W")

    writes = []
    if args.discharge is not None or args.charge is not None:
        for name, value in (("discharge", args.discharge), ("charge", args.charge)):
            if value is not None and not 0 <= value <= 2500:
                sys.exit(f"--{name} must be between 0 and 2500 W")
        if args.discharge is not None:
            writes.append((1074, -args.discharge))
        if args.charge is not None:
            writes.append((1075, args.charge))
    else:
        if args.only != "charge":
            writes.append((1074, -args.limit))
        if args.only != "discharge":
            writes.append((1075, args.limit))

    client = WritableModbusTcp(args.host, args.port, args.unit, 5.0)
    log: list[dict] = []

    def record(event: str) -> None:
        entry = {"time": datetime.now(timezone.utc).isoformat(), "event": event, **snapshot(client)}
        log.append(entry)
        print(
            f"{entry['time'][11:19]} {event:<14} state={entry['state']} power={entry['active_power']:>6} "
            f"soc={entry['soc']:>3} timer={entry['timer_1073']:>4} "
            f"1074={entry['max_discharge_1074']:>6} 1075={entry['max_charge_1075']:>6}"
        )

    try:
        record("before")
        for address, value in writes:
            try:
                client.write_single(address, value)
                record(f"wrote {address}")
            except ModbusError as err:
                print(f"write {address}={value} failed: {err}")
                log.append({"event": f"write {address} failed", "error": str(err)})
        end = time.monotonic() + args.duration
        while time.monotonic() < end:
            time.sleep(5)
            record("watch")
    except KeyboardInterrupt:
        print("stopped")
    finally:
        if args.restore and log and "max_charge_1075" in log[0]:
            original = {1074: log[0]["max_discharge_1074"], 1075: log[0]["max_charge_1075"]}
            for address, _ in writes:
                try:
                    client.write_single(address, original[address])
                    record(f"restored {address}")
                except (ModbusError, OSError) as err:
                    print(f"restoring {address} failed: {err}")
        client.close()
        with open(args.output, "w", encoding="utf-8") as fh:
            json.dump({"writes": writes, "log": log}, fh, indent=1)
        print(f"Saved to {args.output}")


if __name__ == "__main__":
    main()
