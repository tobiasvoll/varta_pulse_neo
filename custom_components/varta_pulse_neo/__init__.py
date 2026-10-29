from __future__ import annotations

from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr

from .api import VartaClient
from .const import CONF_SLAVE_ID, DOMAIN
from .coordinator import VartaConfigEntry, VartaCoordinator

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)
PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: VartaConfigEntry) -> bool:
    client = VartaClient(entry.data[CONF_HOST], entry.data[CONF_PORT], entry.data[CONF_SLAVE_ID])
    coordinator = VartaCoordinator(hass, entry, client)
    try:
        await coordinator.async_config_entry_first_refresh()
    except Exception:
        await client.close()
        raise
    entry.runtime_data = coordinator
    _async_migrate_device(hass, entry, coordinator.device_info.serial)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: VartaConfigEntry) -> bool:
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        await entry.runtime_data.client.close()
    return unload_ok


@callback
def _async_migrate_device(hass: HomeAssistant, entry: VartaConfigEntry, serial: str) -> None:
    """Identify the device by its serial number instead of host and unit id (1.0)."""
    if entry.unique_id is None and hass.config_entries.async_entry_for_domain_unique_id(DOMAIN, serial) is None:
        hass.config_entries.async_update_entry(entry, unique_id=serial)
    registry = dr.async_get(hass)
    identifiers = {(DOMAIN, serial)}
    if registry.async_get_device(identifiers=identifiers) is None and (
        devices := dr.async_entries_for_config_entry(registry, entry.entry_id)
    ):
        registry.async_update_device(devices[0].id, new_identifiers=identifiers)
