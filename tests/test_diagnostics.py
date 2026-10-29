from __future__ import annotations

from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.components.diagnostics import get_diagnostics_for_config_entry
from pytest_homeassistant_custom_component.typing import ClientSessionGenerator


async def test_diagnostics(hass: HomeAssistant, hass_client: ClientSessionGenerator, fake_client, config_entry) -> None:
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    result = await get_diagnostics_for_config_entry(hass, hass_client, config_entry)
    assert result["entry"]["data"]["host"] == "**REDACTED**"
    assert result["entry"]["unique_id"] == "**REDACTED**"
    assert result["device_info"]["serial"] == "**REDACTED**"
    assert result["device_info"]["ems_version"] == "2.60.6"
    assert result["data"]["soc"] == 42
    assert "123456789" not in str(result)
