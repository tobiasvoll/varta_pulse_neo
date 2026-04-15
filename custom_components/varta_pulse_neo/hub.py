from __future__ import annotations

import logging
import math
import socket
import struct
from datetime import UTC, datetime

from .const import READ_BLOCKS, SCALE_FACTOR_ADDRESSES, SENSOR_TYPES

INTERNAL_SENSOR_DEFINITIONS = (
    {"key": "active_power", "address": 1066, "count": 1, "data_type": "int16", "scale": 1.0, "scale_factor_key": "active_power_scale_factor"},
    {"key": "apparent_power", "address": 1067, "count": 1, "data_type": "int16", "scale": 1.0, "scale_factor_key": "apparent_power_scale_factor"},
    {"key": "grid_power", "address": 1078, "count": 1, "data_type": "int16", "scale": 1.0, "scale_factor_key": "grid_power_scale_factor"},
)

_LOGGER = logging.getLogger(__name__)


class VartaPulseNeoHub:
    def __init__(self, host: str, port: int = 502, slave_id: int = 1) -> None:
        self._host = host
        self._port = port
        self._slave_id = slave_id

    def read_data(self) -> dict[str, int | float | str | datetime]:
        blocks: dict[int, list[int]] = {}
        for start_address, count in READ_BLOCKS:
            registers = VartaPulseNeoHub._read_holding_registers(
                self._host,
                self._port,
                start_address,
                count,
                self._slave_id,
            )
            if registers is None:
                raise OSError(
                    f"Modbus read failed for address {start_address} unit {self._slave_id}"
                )
            if len(registers) < count:
                raise OSError(
                    f"Modbus read returned too few registers for address {start_address}: "
                    f"{len(registers)} < {count}"
                )
            blocks[start_address] = registers
            _LOGGER.debug(
                "Varta block read address=%s count=%s unit=%s registers=%s",
                start_address,
                count,
                self._slave_id,
                registers,
            )

        raw_values: dict[str, int | float | str | datetime] = {}
        for description in SENSOR_TYPES:
            if description.derived_from is not None:
                continue
            registers = self._slice_registers(blocks, description.address, description.count)
            raw_values[description.key] = self._decode_registers(registers, description)
            _LOGGER.debug(
                "Varta read key=%s address=%s unit=%s registers=%s decoded=%r",
                description.key,
                description.address,
                self._slave_id,
                registers,
                raw_values[description.key],
            )

        for key, address in SCALE_FACTOR_ADDRESSES.items():
            registers = self._slice_registers(blocks, address, 1)
            raw_values[key] = self._decode_int16(registers[0])
            _LOGGER.debug(
                "Varta internal scale factor key=%s address=%s unit=%s registers=%s decoded=%r",
                key,
                address,
                self._slave_id,
                registers,
                raw_values[key],
            )

        for definition in INTERNAL_SENSOR_DEFINITIONS:
            registers = self._slice_registers(blocks, definition["address"], definition["count"])
            raw_values[definition["key"]] = self._decode_internal_registers(registers, definition)
            _LOGGER.debug(
                "Varta internal base value key=%s address=%s unit=%s registers=%s decoded=%r",
                definition["key"],
                definition["address"],
                self._slave_id,
                registers,
                raw_values[definition["key"]],
            )

        values: dict[str, int | float | str | datetime] = {}
        for definition in INTERNAL_SENSOR_DEFINITIONS:
            values[definition["key"]] = self._apply_internal_scale_factor(raw_values, definition)
        for description in SENSOR_TYPES:
            if description.derived_from is not None:
                values[description.key] = self._derive_value(values, description)
            else:
                values[description.key] = self._apply_scale_factor(raw_values, description)

        return values

    @staticmethod
    def _slice_registers(
        blocks: dict[int, list[int]],
        address: int,
        count: int,
    ) -> list[int]:
        for block_start, registers in blocks.items():
            block_end = block_start + len(registers)
            if block_start <= address and address + count <= block_end:
                offset = address - block_start
                return registers[offset : offset + count]
        raise ValueError(f"No read block covers address {address} count {count}")

    @staticmethod
    def _decode_registers(registers: list[int], description) -> int | float | str:
        if description.data_type == "string":
            return VartaPulseNeoHub._decode_string(registers)

        raw_value = registers[0]
        if description.data_type == "uint32sw":
            raw_value = VartaPulseNeoHub._decode_uint32sw(registers)
        if description.data_type == "timestamp32sw":
            return VartaPulseNeoHub._decode_timestamp32sw(registers)
        if description.data_type == "int16":
            raw_value = VartaPulseNeoHub._decode_int16(raw_value)

        if description.value_map is not None:
            return description.value_map.get(raw_value, f"unknown_{raw_value}")

        scale = description.scale or 1
        if scale != 1:
            return raw_value * scale

        return raw_value

    @staticmethod
    def _apply_scale_factor(values: dict[str, int | float | str | datetime], description):
        value = values[description.key]
        if description.scale_factor_key is None:
            return value

        scale_factor = values.get(description.scale_factor_key)
        if not isinstance(value, (int, float)) or not isinstance(scale_factor, (int, float)):
            return value

        if scale_factor < -6 or scale_factor > 6:
            _LOGGER.warning(
                "Ignoring suspicious scale factor %s for %s",
                scale_factor,
                description.key,
            )
            return value

        return value * math.pow(10, scale_factor)

    @staticmethod
    def _apply_internal_scale_factor(values: dict[str, int | float | str | datetime], definition: dict):
        value = values[definition["key"]]
        scale_factor_key = definition.get("scale_factor_key")
        if scale_factor_key is None:
            return value

        scale_factor = values.get(scale_factor_key)
        if not isinstance(value, (int, float)) or not isinstance(scale_factor, (int, float)):
            return value

        if scale_factor < -6 or scale_factor > 6:
            _LOGGER.warning(
                "Ignoring suspicious scale factor %s for %s",
                scale_factor,
                definition["key"],
            )
            return value

        return value * math.pow(10, scale_factor)

    @staticmethod
    def _decode_internal_registers(registers: list[int], definition: dict) -> int | float:
        raw_value = registers[0]
        if definition["data_type"] == "int16":
            raw_value = VartaPulseNeoHub._decode_int16(raw_value)

        scale = definition.get("scale", 1.0) or 1.0
        if scale != 1:
            raw_value = raw_value * scale

        return raw_value

    @staticmethod
    def _derive_value(values: dict[str, int | float | str | datetime], description):
        source_value = values.get(description.derived_from)
        if not isinstance(source_value, (int, float)):
            return None

        if description.derived_mode == "positive":
            return max(source_value, 0)
        if description.derived_mode == "negative_abs":
            return abs(min(source_value, 0))

        return None

    @staticmethod
    def _decode_string(registers: list[int]) -> str:
        raw_bytes = b"".join(register.to_bytes(2, "big") for register in registers)
        return raw_bytes.replace(b"\x00", b"").decode("ascii", errors="ignore").strip()

    @staticmethod
    def _decode_int16(value: int) -> int:
        return value - 0x10000 if value > 0x7FFF else value

    @staticmethod
    def _decode_uint32sw(registers: list[int]) -> int:
        if len(registers) < 2:
            raise ValueError("uint32sw requires two registers")
        return (registers[1] << 16) | registers[0]

    @staticmethod
    def _decode_timestamp32sw(registers: list[int]) -> datetime:
        value = VartaPulseNeoHub._decode_uint32sw(registers)
        return datetime.fromtimestamp(value, UTC)

    @staticmethod
    def validate_connection(host: str, port: int, slave_id: int) -> bool:
        last_error = None
        for address in (1000, 1051, 1068, 1078):
            _LOGGER.warning("Varta validation: trying read on address %s slave=%s", address, slave_id)
            registers = VartaPulseNeoHub._read_holding_registers(host, port, address, 1, slave_id)
            _LOGGER.warning("Varta validation: registers for address %s: %s", address, registers)
            if registers is not None:
                _LOGGER.warning("Varta Pulse Neo validated using address %s", address)
                return True
            last_error = f"address={address} registers={registers}"

        _LOGGER.error("Varta validation failed for all test addresses, last=%s", last_error)
        raise OSError("Unable to read from Varta Pulse Neo")

    @staticmethod
    def _read_holding_registers(
        host: str,
        port: int,
        address: int,
        count: int,
        unit: int,
    ) -> list[int] | None:
        return VartaPulseNeoHub._send_modbus_tcp_request(host, port, unit, 3, address, count)

    @staticmethod
    def _send_modbus_tcp_request(
        host: str,
        port: int,
        unit: int,
        function_code: int,
        address: int,
        count: int,
    ) -> list[int] | None:
        try:
            with socket.create_connection((host, port), timeout=3) as sock:
                transaction_id = 0
                protocol_id = 0
                length = 6
                request_pdu = struct.pack(
                    ">BHH",
                    function_code,
                    address,
                    count,
                )
                packet = struct.pack(
                    ">HHHB",
                    transaction_id,
                    protocol_id,
                    length,
                    unit,
                ) + request_pdu
                sock.sendall(packet)
                response = sock.recv(1024)
        except (OSError, socket.timeout) as exc:
            _LOGGER.warning("Varta TCP/Modbus connection failed: %s", exc)
            return None

        if len(response) < 9:
            _LOGGER.warning("Varta Modbus response too short (%s bytes)", len(response))
            return None

        _, _, _, resp_unit = struct.unpack(
            ">HHHB",
            response[:7],
        )
        if resp_unit != unit:
            _LOGGER.warning(
                "Varta Modbus response unit mismatch %s != %s",
                resp_unit,
                unit,
            )
            return None

        function = response[7]
        if function == function_code + 0x80:
            exception_code = response[8]
            _LOGGER.warning(
                "Varta Modbus exception response function=%s code=%s",
                function,
                exception_code,
            )
            return None
        if function != function_code:
            _LOGGER.warning("Varta Modbus unexpected function code %s", function)
            return None

        byte_count = response[8]
        if byte_count % 2 != 0:
            _LOGGER.warning("Varta Modbus invalid byte count %s", byte_count)
            return None

        payload = response[9 : 9 + byte_count]
        if len(payload) < byte_count:
            _LOGGER.warning(
                "Varta Modbus payload shorter than expected %s < %s",
                len(payload),
                byte_count,
            )
            return None

        return [int.from_bytes(payload[i : i + 2], "big") for i in range(0, byte_count, 2)]
