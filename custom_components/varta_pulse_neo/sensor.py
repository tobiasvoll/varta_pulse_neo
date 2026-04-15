from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import slugify

from .const import CONF_SLAVE_ID, DOMAIN, SENSOR_TYPES


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    async_add_entities(
        VartaPulseNeoSensor(coordinator, entry, description)
        for description in SENSOR_TYPES
    )


class VartaPulseNeoSensor(CoordinatorEntity, SensorEntity):
    def __init__(self, coordinator, entry: ConfigEntry, description) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._entry = entry
        self._attr_has_entity_name = False
        self._attr_name = f"{entry.title} {description.name}"
        self._attr_suggested_object_id = f"{entry.title}_{description.key}"
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self.entity_id = f"sensor.{slugify(entry.title)}_{description.key}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"{entry.data[CONF_HOST]}_{entry.data[CONF_SLAVE_ID]}")},
            "name": entry.title,
            "manufacturer": "Varta",
            "model": "Pulse Neo",
            "configuration_url": f"http://{entry.data[CONF_HOST]}",
        }

    @property
    def native_value(self):
        return self.coordinator.data.get(self.entity_description.key)
