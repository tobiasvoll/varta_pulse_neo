from __future__ import annotations

import logging
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT

from .const import CONF_SLAVE_ID, DEFAULT_NAME, DEFAULT_PORT, DEFAULT_SLAVE_ID, DOMAIN
from .hub import VartaPulseNeoHub

_LOGGER = logging.getLogger(__name__)


class VartaPulseNeoConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        if user_input is not None:
            try:
                await self.hass.async_add_executor_job(
                    VartaPulseNeoHub.validate_connection,
                    user_input[CONF_HOST],
                    user_input[CONF_PORT],
                    user_input[CONF_SLAVE_ID],
                )
            except Exception as err:
                _LOGGER.error(
                    "Varta Pulse Neo connection failed: %s",
                    err,
                    exc_info=True,
                )
                return self.async_show_form(
                    step_id="user",
                    data_schema=self._get_schema(),
                    errors={"base": "cannot_connect"},
                )

            return self.async_create_entry(
                title=user_input[CONF_NAME] or DEFAULT_NAME,
                data=user_input,
            )

        return self.async_show_form(step_id="user", data_schema=self._get_schema())

    def _get_schema(self):
        return vol.Schema(
            {
                vol.Required(CONF_HOST): str,
                vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
                vol.Required(CONF_SLAVE_ID, default=DEFAULT_SLAVE_ID): int,
                vol.Optional(CONF_NAME, default=DEFAULT_NAME): str,
            }
        )
