from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import VartaClient, VartaData, VartaDeviceInfo, VartaError
from .const import CONTROL_REFRESH, DOMAIN, SCALE_FACTOR_REFRESH, SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)

type VartaConfigEntry = ConfigEntry[VartaCoordinator]


class VartaCoordinator(DataUpdateCoordinator[VartaData]):
    """Polls the storage system over one Modbus TCP connection."""

    config_entry: VartaConfigEntry
    device_info: VartaDeviceInfo

    def __init__(self, hass: HomeAssistant, entry: VartaConfigEntry, client: VartaClient) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        self.client = client
        # Active power limits in W, None when not limited.
        self.limits: dict[str, int | None] = {"charge": None, "discharge": None}

    async def _async_setup(self) -> None:
        try:
            self.device_info = await self.client.async_get_device_info()
        except VartaError as err:
            raise UpdateFailed(str(err)) from err
        self.config_entry.async_on_unload(
            async_track_time_interval(
                self.hass, lambda _now: self.client.invalidate_scale_factors(), SCALE_FACTOR_REFRESH
            )
        )
        self.config_entry.async_on_unload(
            async_track_time_interval(self.hass, self.async_refresh_limits, CONTROL_REFRESH)
        )

    async def async_set_limit(self, direction: str, limit: int | None, release_value: int) -> None:
        """Set or clear the charge or discharge limit and write it right away.

        Clearing writes release_value once so the old limit does not linger
        until the device timer runs out.
        """
        self.limits[direction] = limit
        value = release_value if limit is None else limit
        try:
            await self.client.async_set_power_limits(**{direction: value})
        except VartaError as err:
            raise HomeAssistantError(f"Cannot set {direction} limit: {err}") from err

    async def async_refresh_limits(self, _now=None) -> None:
        """Write the active limits again before the device resets them."""
        charge, discharge = self.limits["charge"], self.limits["discharge"]
        if charge is None and discharge is None:
            return
        try:
            await self.client.async_set_power_limits(charge=charge, discharge=discharge)
        except VartaError as err:
            _LOGGER.warning("Refreshing power limits failed: %s", err)

    async def _async_update_data(self) -> VartaData:
        try:
            return await self.client.async_get_data()
        except VartaError as err:
            raise UpdateFailed(str(err)) from err
