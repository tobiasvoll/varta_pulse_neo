from __future__ import annotations

from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.varta_pulse_neo.const import CONF_SLAVE_ID, DOMAIN


async def test_migrate_device_from_1_0(hass: HomeAssistant, fake_client) -> None:
    """1.0 entries had no unique id and a device identified by host and unit id."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Varta Pulse Neo",
        data={CONF_HOST: "1.2.3.4", CONF_PORT: 502, CONF_SLAVE_ID: 255},
    )
    entry.add_to_hass(hass)
    registry = dr.async_get(hass)
    old = registry.async_get_or_create(config_entry_id=entry.entry_id, identifiers={(DOMAIN, "1.2.3.4_255")})

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.unique_id == "123456789"
    device = registry.async_get(old.id)
    assert device.identifiers == {(DOMAIN, "123456789")}
    assert len(dr.async_entries_for_config_entry(registry, entry.entry_id)) == 1


async def test_device_identified_by_serial(hass: HomeAssistant, fake_client, config_entry) -> None:
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    device = dr.async_get(hass).async_get_device(identifiers={(DOMAIN, "123456789")})
    assert device is not None
    assert device.serial_number == "123456789"
