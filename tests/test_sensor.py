from __future__ import annotations

from datetime import timedelta

from freezegun.api import FrozenDateTimeFactory
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
import pytest
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from custom_components.varta_pulse_neo.const import DOMAIN, SCAN_INTERVAL
from custom_components.varta_pulse_neo.sensor import COUNTER_REBASE_READINGS

CHARGED = 23 * 65536 + 47038  # Wh in the register dump


def _state(hass: HomeAssistant, entry, key: str):
    registry = er.async_get(hass)
    entity_id = registry.async_get_entity_id("sensor", "varta_pulse_neo", f"{entry.entry_id}_{key}")
    return hass.states.get(entity_id)


async def test_sensors(hass: HomeAssistant, fake_client, config_entry) -> None:
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.LOADED

    assert _state(hass, config_entry, "soc").state == "42"
    assert _state(hass, config_entry, "state").state == "standby"
    assert float(_state(hass, config_entry, "active_power_discharge").state) == 200
    assert float(_state(hass, config_entry, "active_power_charge").state) == 0
    assert float(_state(hass, config_entry, "grid_power_consumption").state) == 8
    assert _state(hass, config_entry, "ems").state == "2.60.6"
    assert float(_state(hass, config_entry, "active_power").state) == -200
    assert _state(hass, config_entry, "error_code").state == "0"

    charged = _state(hass, config_entry, "energy_counter_ac_to_dc")
    assert charged.attributes["state_class"] == "total_increasing"
    assert charged.attributes["unit_of_measurement"] == "kWh"
    assert float(charged.state) == 1554.366


async def test_discharged_energy(
    hass: HomeAssistant, fake_client, config_entry, freezer: FrozenDateTimeFactory
) -> None:
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert float(_state(hass, config_entry, "energy_discharged").state) == 0

    # 200 W for 30 s = 1.667 Wh
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert float(_state(hass, config_entry, "energy_discharged").state) == 0.0

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert float(_state(hass, config_entry, "energy_discharged").state) == pytest.approx(200 * 30 / 3600 / 1000)


async def test_unavailable_on_error(hass: HomeAssistant, fake_client, config_entry, freezer) -> None:
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    fake_client.fail = True
    fake_client.connected = False
    freezer.tick(SCAN_INTERVAL + timedelta(seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert _state(hass, config_entry, "soc").state == STATE_UNAVAILABLE


async def _poll(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


def _set_counter(fake_client, wh: int) -> None:
    fake_client.registers[1069] = wh & 0xFFFF
    fake_client.registers[1070] = wh >> 16


def _charged(hass: HomeAssistant, entry) -> float:
    return float(_state(hass, entry, "energy_counter_ac_to_dc").state) * 1000


async def test_charged_energy_ignores_bad_readings(
    hass: HomeAssistant, fake_client, config_entry, freezer: FrozenDateTimeFactory
) -> None:
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert _charged(hass, config_entry) == pytest.approx(CHARGED)

    # A single 0 is discarded.
    _set_counter(fake_client, 0)
    await _poll(hass, freezer)
    assert _charged(hass, config_entry) == pytest.approx(CHARGED)

    # So is a jump far beyond the maximum charge power.
    _set_counter(fake_client, CHARGED + 100_000)
    await _poll(hass, freezer)
    assert _charged(hass, config_entry) == pytest.approx(CHARGED)

    # Normal charging is accepted again.
    _set_counter(fake_client, CHARGED + 20)
    await _poll(hass, freezer)
    assert _charged(hass, config_entry) == pytest.approx(CHARGED + 20)


async def test_charged_energy_accepts_reset(
    hass: HomeAssistant, fake_client, config_entry, freezer: FrozenDateTimeFactory
) -> None:
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    _set_counter(fake_client, 500)
    for _ in range(COUNTER_REBASE_READINGS - 1):
        await _poll(hass, freezer)
    assert _charged(hass, config_entry) == pytest.approx(CHARGED)
    await _poll(hass, freezer)
    assert _charged(hass, config_entry) == pytest.approx(500)


async def test_removed_apparent_power_sensors(hass: HomeAssistant, fake_client, config_entry) -> None:
    config_entry.add_to_hass(hass)
    registry = er.async_get(hass)
    old = registry.async_get_or_create(
        "sensor", DOMAIN, f"{config_entry.entry_id}_apparent_power_charge", config_entry=config_entry
    )
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert registry.async_get(old.entity_id) is None
