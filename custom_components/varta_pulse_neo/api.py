"""Modbus TCP client for VARTA storage systems.

Register map: docs/registers.md (VARTA Modbus TCP documentation v13.4).
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
import logging
import time

from pymodbus.client import AsyncModbusTcpClient
from pymodbus.exceptions import ModbusException

_LOGGER = logging.getLogger(__name__)

# VARTA allows at most one request per second.
MIN_REQUEST_INTERVAL = 1.0
TIMEOUT = 5.0

STATIC_BLOCK = (1000, 64)  # software versions, table version, timestamp, serial
# The device accepts blocks spanning undocumented registers as long as the
# first and last address are documented. If it does not, fall back to the
# documented sub-blocks. Blocks marked optional may be missing on older
# firmware and only disable their own values.
LIVE_BLOCK = (1064, 24)
LIVE_FALLBACK = ((1064, 8, False), (1078, 1, False), (1082, 6, True))
PV_BLOCK = (1102, 1)
SF_BLOCK = (2066, 21)
SF_FALLBACK = ((2066, 2, False), (2069, 1, False), (2071, 1, False), (2078, 1, False), (2083, 4, True))

STATES = {
    0: "busy",
    1: "run",
    2: "charge",
    3: "discharge",
    4: "standby",
    5: "error",
    6: "passive",
    7: "islanding",
}


class VartaError(Exception):
    """Communication with the storage system failed."""


class VartaRefused(VartaError):
    """The device answered with a Modbus exception (e.g. illegal address)."""

    def __init__(self, address: int, count: int) -> None:
        super().__init__(f"Device refused {count} registers at {address}")
        self.address = address


@dataclass
class VartaDeviceInfo:
    """Static information read once per connection."""

    serial: str
    ems_version: str
    ens_version: str
    inverter_version: str
    table_version: int


@dataclass
class VartaData:
    """One poll of the storage system."""

    state: str | None = None
    modules: int | None = None
    active_power: float | None = None
    apparent_power: float | None = None
    soc: int | None = None
    charged_energy: float | None = None
    capacity: float | None = None
    grid_power: float | None = None
    grid_frequency: float | None = None
    available_charge_power: float | None = None
    available_discharge_power: float | None = None
    usable_charge_energy: float | None = None
    usable_discharge_energy: float | None = None
    reactive_power: float | None = None
    pv_power: float | None = None
    raw: dict[int, int] = field(default_factory=dict)


def to_int16(value: int) -> int:
    return value - 0x10000 if value > 0x7FFF else value


def decode_string(registers: list[int]) -> str:
    # One character per register, in the low byte.
    return bytes(r & 0xFF for r in registers).replace(b"\x00", b"").decode("ascii", errors="ignore").strip()


def scaled(value: int, exponent: int | None) -> float:
    if exponent is None or not -6 <= exponent <= 6:
        return float(value)
    return float(value * 10**exponent)


class VartaClient:
    """Keeps one Modbus TCP connection and reads the documented registers."""

    def __init__(self, host: str, port: int, unit_id: int) -> None:
        self._client = AsyncModbusTcpClient(host, port=port, timeout=TIMEOUT, retries=1)
        self._unit_id = unit_id
        self._lock = asyncio.Lock()
        self._last_request = 0.0
        self._live_fallback = False
        self._sf_fallback = False
        self._skip: set[int] = set()
        self._scale_factors: dict[int, int] | None = None

    async def close(self) -> None:
        self._client.close()

    async def _read(self, address: int, count: int) -> list[int]:
        """Read holding registers, honouring the request interval."""
        if not self._client.connected:
            if not await self._client.connect():
                raise VartaError(f"Cannot connect to {self._client.comm_params.host}")
        wait = self._last_request + MIN_REQUEST_INTERVAL - time.monotonic()
        if wait > 0:
            await asyncio.sleep(wait)
        self._last_request = time.monotonic()
        try:
            result = await self._client.read_holding_registers(address, count=count, device_id=self._unit_id)
        except ModbusException as err:
            self._client.close()
            raise VartaError(f"Reading {count} registers at {address} failed: {err}") from err
        if result.isError():
            raise VartaRefused(address, count)
        return list(result.registers)

    async def _read_blocks(
        self, block: tuple[int, int], fallback: tuple[tuple[int, int, bool], ...], use_fallback: bool
    ) -> tuple[dict[int, int], bool]:
        regs: dict[int, int] = {}
        if not use_fallback:
            try:
                values = await self._read(*block)
            except VartaRefused:
                _LOGGER.debug("Block %s refused, switching to documented sub-blocks", block)
            else:
                return dict(enumerate(values, block[0])), False
        for start, count, optional in fallback:
            if start in self._skip:
                continue
            try:
                regs.update(enumerate(await self._read(start, count), start))
            except VartaRefused:
                if not optional:
                    raise
                _LOGGER.info("Registers %s-%s not supported by this device", start, start + count - 1)
                self._skip.add(start)
        return regs, True

    async def async_get_device_info(self) -> VartaDeviceInfo:
        async with self._lock:
            regs = await self._read(*STATIC_BLOCK)
        return VartaDeviceInfo(
            ems_version=decode_string(regs[0:17]),
            ens_version=decode_string(regs[17:34]),
            inverter_version=decode_string(regs[34:51]),
            table_version=regs[51],
            serial=decode_string(regs[54:64]),
        )

    async def async_get_data(self) -> VartaData:
        async with self._lock:
            if self._scale_factors is None:
                regs, self._sf_fallback = await self._read_blocks(SF_BLOCK, SF_FALLBACK, self._sf_fallback)
                self._scale_factors = {a: to_int16(v) for a, v in regs.items()}
            regs, self._live_fallback = await self._read_blocks(LIVE_BLOCK, LIVE_FALLBACK, self._live_fallback)
            if PV_BLOCK[0] not in self._skip:
                try:
                    regs.update(enumerate(await self._read(*PV_BLOCK), PV_BLOCK[0]))
                except VartaRefused:
                    self._skip.add(PV_BLOCK[0])
        return self._decode(regs, self._scale_factors)

    def invalidate_scale_factors(self) -> None:
        """Re-read the scale factors with the next poll."""
        self._scale_factors = None

    @staticmethod
    def _decode(regs: dict[int, int], sf: dict[int, int]) -> VartaData:
        def get(address: int) -> int | None:
            return regs.get(address)

        data = VartaData(raw=regs)
        if (state := get(1065)) is not None:
            data.state = STATES.get(state, "unknown")
        data.modules = get(1064)
        if (v := get(1066)) is not None:
            data.active_power = scaled(to_int16(v), sf.get(2066))
        if (v := get(1067)) is not None:
            data.apparent_power = scaled(to_int16(v), sf.get(2067))
        data.soc = get(1068)
        if (low := get(1069)) is not None and (high := get(1070)) is not None:
            data.charged_energy = scaled((high << 16) | low, sf.get(2069))
        if (v := get(1071)) is not None:
            data.capacity = scaled(v, sf.get(2071)) * 10
        if (v := get(1078)) is not None:
            data.grid_power = scaled(to_int16(v), sf.get(2078))
        if (v := get(1082)) is not None:
            data.grid_frequency = v / 100
        if (v := get(1083)) is not None:
            data.available_charge_power = scaled(v, sf.get(2083))
        if (v := get(1084)) is not None:
            data.available_discharge_power = scaled(v, sf.get(2084))
        if (v := get(1085)) is not None:
            data.usable_charge_energy = scaled(v, sf.get(2085))
        if (v := get(1086)) is not None:
            data.usable_discharge_energy = scaled(v, sf.get(2086))
        if (v := get(1087)) is not None:
            data.reactive_power = float(to_int16(v))
        if (v := get(1102)) is not None:
            data.pv_power = float(v)
        return data
