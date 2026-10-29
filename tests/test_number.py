from __future__ import annotations

from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import HomeAssistant, State
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
import pytest
from pytest_homeassistant_custom_component.common import async_fire_time_changed, mock_restore_cache_with_extra_data

from custom_components.varta_pulse_neo.const import CONTROL_REFRESH


def _entity_id(hass: HomeAssistant, entry, key: str) -> str:
    return er.async_get(hass).async_get_entity_id("number", "varta_pulse_neo", f"{entry.entry_id}_{key}")


async def _setup(hass: HomeAssistant, entry) -> None:
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


async def _set(hass: HomeAssistant, entity_id: str, value: float) -> None:
    await hass.services.async_call("number", "set_value", {"entity_id": entity_id, "value": value}, blocking=True)


async def test_no_writes_by_default(
    hass: HomeAssistant, fake_client, config_entry, freezer: FrozenDateTimeFactory
) -> None:
    await _setup(hass, config_entry)
    state = hass.states.get(_entity_id(hass, config_entry, "charge_power_limit"))
    assert float(state.state) == 2500
    assert state.attributes["max"] == 2500
    freezer.tick(CONTROL_REFRESH)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert fake_client.writes == []


async def test_limit_written_and_refreshed(
    hass: HomeAssistant, fake_client, config_entry, freezer: FrozenDateTimeFactory
) -> None:
    await _setup(hass, config_entry)
    entity_id = _entity_id(hass, config_entry, "discharge_power_limit")
    await _set(hass, entity_id, 0)
    assert fake_client.writes == [(1074, 0)]
    assert float(hass.states.get(entity_id).state) == 0

    fake_client.writes.clear()
    freezer.tick(CONTROL_REFRESH)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert fake_client.writes == [(1074, 0)]

    # Back to the maximum releases the limit: written once, then no more.
    fake_client.writes.clear()
    await _set(hass, entity_id, 2500)
    assert fake_client.writes == [(1074, 0x10000 - 2500)]
    fake_client.writes.clear()
    freezer.tick(CONTROL_REFRESH)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert fake_client.writes == []


async def test_write_failure(hass: HomeAssistant, fake_client, config_entry) -> None:
    await _setup(hass, config_entry)
    entity_id = _entity_id(hass, config_entry, "charge_power_limit")
    fake_client.fail = True
    fake_client.connected = False
    with pytest.raises(HomeAssistantError):
        await _set(hass, entity_id, 500)


async def test_limit_restored(hass: HomeAssistant, fake_client, config_entry) -> None:
    registry = er.async_get(hass)
    config_entry.add_to_hass(hass)
    entity = registry.async_get_or_create(
        "number", "varta_pulse_neo", f"{config_entry.entry_id}_charge_power_limit", config_entry=config_entry
    )
    mock_restore_cache_with_extra_data(
        hass,
        [
            (
                State(entity.entity_id, "300"),
                {
                    "native_value": 300,
                    "native_unit_of_measurement": "W",
                    "native_min_value": 0,
                    "native_max_value": 2500,
                    "native_step": 50,
                },
            )
        ],
    )
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert float(hass.states.get(entity.entity_id).state) == 300
    assert fake_client.writes == [(1075, 300)]
