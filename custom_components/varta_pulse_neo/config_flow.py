from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT
import voluptuous as vol

from .api import VartaClient, VartaError
from .const import CONF_SLAVE_ID, DEFAULT_NAME, DEFAULT_PORT, DEFAULT_SLAVE_ID, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): vol.All(int, vol.Range(min=1, max=65535)),
        vol.Required(CONF_SLAVE_ID, default=DEFAULT_SLAVE_ID): vol.All(int, vol.Range(min=0, max=255)),
    }
)


class VartaPulseNeoConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            client = VartaClient(user_input[CONF_HOST], user_input[CONF_PORT], user_input[CONF_SLAVE_ID])
            try:
                info = await client.async_get_device_info()
            except VartaError as err:
                _LOGGER.debug("Connection test failed: %s", err)
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(info.serial)
                self._abort_if_unique_id_configured(updates={CONF_HOST: user_input[CONF_HOST]})
                return self.async_create_entry(title=DEFAULT_NAME, data=user_input)
            finally:
                await client.close()

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(STEP_USER_SCHEMA, user_input),
            errors=errors,
        )

    async def async_step_reconfigure(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Change host, port or unit id, e.g. after the device got a new IP address."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            client = VartaClient(user_input[CONF_HOST], user_input[CONF_PORT], user_input[CONF_SLAVE_ID])
            try:
                info = await client.async_get_device_info()
            except VartaError as err:
                _LOGGER.debug("Connection test failed: %s", err)
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(info.serial)
                self._abort_if_unique_id_mismatch(reason="wrong_device")
                return self.async_update_reload_and_abort(entry, data_updates=user_input)
            finally:
                await client.close()

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(STEP_USER_SCHEMA, user_input or entry.data),
            errors=errors,
        )
