from __future__ import annotations

from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.varta_pulse_neo.const import CONF_SLAVE_ID, DOMAIN

USER_INPUT = {CONF_HOST: "1.2.3.4", CONF_PORT: 502, CONF_SLAVE_ID: 255}


async def test_user_flow(hass: HomeAssistant, fake_client) -> None:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(result["flow_id"], USER_INPUT)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Varta Pulse Neo"
    assert result["result"].unique_id == "123456789"


async def test_cannot_connect(hass: HomeAssistant, fake_client) -> None:
    fake_client.fail = True
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], USER_INPUT)
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    fake_client.fail = False
    result = await hass.config_entries.flow.async_configure(result["flow_id"], USER_INPUT)
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_already_configured(hass: HomeAssistant, fake_client, config_entry) -> None:
    config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], USER_INPUT)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reconfigure(hass: HomeAssistant, fake_client, config_entry) -> None:
    config_entry.add_to_hass(hass)
    result = await config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    new_input = {CONF_HOST: "5.6.7.8", CONF_PORT: 502, CONF_SLAVE_ID: 1}
    result = await hass.config_entries.flow.async_configure(result["flow_id"], new_input)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert config_entry.data[CONF_HOST] == "5.6.7.8"
    assert config_entry.data[CONF_SLAVE_ID] == 1


async def test_reconfigure_wrong_device(hass: HomeAssistant, fake_client, config_entry) -> None:
    config_entry.add_to_hass(hass)
    for address, char in enumerate("987654321", 1054):
        fake_client.registers[address] = ord(char)
    result = await config_entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "5.6.7.8", CONF_PORT: 502, CONF_SLAVE_ID: 255}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "wrong_device"
    assert config_entry.data[CONF_HOST] == "1.2.3.4"


async def test_reconfigure_cannot_connect(hass: HomeAssistant, fake_client, config_entry) -> None:
    config_entry.add_to_hass(hass)
    fake_client.fail = True
    result = await config_entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "5.6.7.8", CONF_PORT: 502, CONF_SLAVE_ID: 255}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}
