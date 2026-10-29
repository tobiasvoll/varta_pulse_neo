from __future__ import annotations

from collections.abc import Generator
from unittest.mock import MagicMock, patch

from homeassistant.const import CONF_HOST, CONF_PORT
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.varta_pulse_neo.const import CONF_SLAVE_ID, DOMAIN


def _chars(text: str, count: int) -> list[int]:
    return [ord(c) for c in text] + [0] * (count - len(text))


# Register dump of a pulse neo 6 (serial replaced).
REGISTERS: dict[int, int] = {
    **dict(enumerate(_chars("2.60.6", 17), 1000)),
    **dict(enumerate(_chars("0.0.0.", 17), 1017)),
    **dict(enumerate(_chars("1.5.4", 17), 1034)),
    1051: 13,
    1052: 8823,
    1053: 27363,
    **dict(enumerate(_chars("123456789", 10), 1054)),
    1064: 1,
    1065: 4,
    1066: 0xFF38,
    1067: 0xFF38,
    1068: 42,
    1069: 47038,
    1070: 23,
    1071: 586,
    1072: 0,
    1073: 0,
    1074: 32768,
    1075: 65535,
    1076: 24980,
    1077: 0,
    1078: 65528,
    1079: 38822,
    1080: 2181,
    1081: 11876,
    1082: 5002,
    1083: 2500,
    1084: 1557,
    1085: 5809,
    1086: 58,
    1087: 0,
    1102: 0,
    **{a: 0 for a in (2066, 2067, 2069, 2071, 2074, 2075, 2077, 2078, 2083, 2084, 2085, 2086)},
    **{a: 65535 for a in (2072, 2073, 2076, 2079, 2080, 2081, 2082)},
}
# Refused when read on their own; blocks are refused when they start or end on one.
REFUSED = {2068, 2070, *range(1088, 1102)}


class FakeModbusClient:
    """Mimics pymodbus' AsyncModbusTcpClient against REGISTERS."""

    def __init__(self, *args, **kwargs) -> None:
        self.connected = False
        self.registers = dict(REGISTERS)
        self.refused = set(REFUSED)
        self.strict = False  # refuse any block containing a refused address
        self.fail = False
        self.requests: list[tuple[int, int]] = []
        self.comm_params = MagicMock(host="1.2.3.4")

    async def connect(self) -> bool:
        self.connected = not self.fail
        return self.connected

    def close(self) -> None:
        self.connected = False

    async def read_holding_registers(self, address: int, *, count: int, device_id: int):
        self.requests.append((address, count))
        addresses = range(address, address + count)
        if self.strict:
            refused = any(a in self.refused for a in addresses)
        else:
            refused = address in self.refused or addresses[-1] in self.refused
        refused = refused or any(a not in self.registers and a not in self.refused for a in addresses)
        result = MagicMock()
        result.isError.return_value = refused
        result.registers = [] if refused else [self.registers.get(a, 0) for a in addresses]
        return result


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield


@pytest.fixture(autouse=True)
def no_request_delay() -> Generator[None]:
    with patch("custom_components.varta_pulse_neo.api.MIN_REQUEST_INTERVAL", 0):
        yield


@pytest.fixture
def fake_client() -> Generator[FakeModbusClient]:
    client = FakeModbusClient()
    with patch("custom_components.varta_pulse_neo.api.AsyncModbusTcpClient", return_value=client):
        yield client


@pytest.fixture
def config_entry() -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        title="Varta Pulse Neo",
        data={CONF_HOST: "1.2.3.4", CONF_PORT: 502, CONF_SLAVE_ID: 255},
        unique_id="123456789",
    )
