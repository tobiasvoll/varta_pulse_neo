from __future__ import annotations

import pytest

from custom_components.varta_pulse_neo.api import VartaClient, VartaRefused


async def test_device_info(fake_client) -> None:
    info = await VartaClient("1.2.3.4", 502, 255).async_get_device_info()
    assert info.serial == "123456789"
    assert info.ems_version == "2.60.6"
    assert info.inverter_version == "1.5.4"
    assert info.table_version == 13


async def test_decode(fake_client) -> None:
    data = await VartaClient("1.2.3.4", 502, 255).async_get_data()
    assert data.state == "standby"
    assert data.soc == 42
    assert data.active_power == -200
    assert data.charged_energy == 23 * 65536 + 47038
    assert data.capacity == 5860
    assert data.grid_power == -8
    assert data.grid_frequency == 50.02
    assert data.usable_charge_energy == 5809
    assert data.pv_power == 0


async def test_one_request_per_block(fake_client) -> None:
    client = VartaClient("1.2.3.4", 502, 255)
    await client.async_get_data()
    assert fake_client.requests == [(2066, 21), (1064, 24), (1102, 1)]
    fake_client.requests.clear()
    await client.async_get_data()
    # Scale factors are cached.
    assert fake_client.requests == [(1064, 24), (1102, 1)]


async def test_fallback_to_documented_blocks(fake_client) -> None:
    fake_client.strict = True
    fake_client.refused |= set(range(1072, 1078)) | set(range(1079, 1082))
    client = VartaClient("1.2.3.4", 502, 255)
    data = await client.async_get_data()
    assert data.capacity == 5860
    assert data.grid_power == -8
    assert data.usable_discharge_energy == 58
    fake_client.requests.clear()
    await client.async_get_data()
    # The fallback is remembered, the big block is not tried again.
    assert fake_client.requests == [(1064, 8), (1078, 1), (1082, 6), (1102, 1)]


async def test_optional_registers_missing(fake_client) -> None:
    """Older pulse neo firmware does not provide 1082-1087 and 1102."""
    fake_client.strict = True
    fake_client.refused |= (set(range(1072, 1088)) - {1078}) | {1102}
    client = VartaClient("1.2.3.4", 502, 255)
    data = await client.async_get_data()
    assert data.soc == 42
    assert data.grid_frequency is None
    assert data.pv_power is None
    fake_client.requests.clear()
    await client.async_get_data()
    assert fake_client.requests == [(1064, 8), (1078, 1)]


async def test_required_register_missing(fake_client) -> None:
    fake_client.strict = True
    fake_client.refused |= {1066}
    with pytest.raises(VartaRefused):
        await VartaClient("1.2.3.4", 502, 255).async_get_data()


async def test_scale_factor_applied(fake_client) -> None:
    fake_client.registers[2066] = 1
    fake_client.registers[2071] = 0xFFFF  # -1
    data = await VartaClient("1.2.3.4", 502, 255).async_get_data()
    assert data.active_power == -2000
    assert data.capacity == pytest.approx(586)
