from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import VartaClient, VartaData, VartaDeviceInfo, VartaError
from .const import DOMAIN, SCALE_FACTOR_REFRESH, SCAN_INTERVAL

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

    async def _async_update_data(self) -> VartaData:
        try:
            return await self.client.async_get_data()
        except VartaError as err:
            raise UpdateFailed(str(err)) from err
