from __future__ import annotations

from datetime import timedelta

from freezegun.api import FrozenDateTimeFactory
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
import pytest
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from custom_components.varta_pulse_neo.const import SCAN_INTERVAL


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
