from __future__ import annotations

from homeassistant.components.number import NumberDeviceClass, NumberMode, RestoreNumber
from homeassistant.const import UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DEFAULT_MAX_POWER
from .coordinator import VartaConfigEntry, VartaCoordinator
from .sensor import VartaEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: VartaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    info = coordinator.device_info
    async_add_entities(
        [
            VartaPowerLimit(coordinator, "charge", info.rated_charge_power or DEFAULT_MAX_POWER),
            VartaPowerLimit(coordinator, "discharge", info.rated_discharge_power or DEFAULT_MAX_POWER),
        ]
    )


class VartaPowerLimit(VartaEntity, RestoreNumber):
    """Maximum charge or discharge power.

    The maximum means "no limit": the integration then stops writing and the
    device runs on its own. Any lower value is written again every 60 s.
    """

    _attr_device_class = NumberDeviceClass.POWER
    _attr_native_unit_of_measurement = UnitOfPower.WATT
    _attr_native_min_value = 0
    _attr_native_step = 50
    _attr_mode = NumberMode.BOX

    def __init__(self, coordinator: VartaCoordinator, direction: str, max_power: int) -> None:
        super().__init__(coordinator, f"{direction}_power_limit")
        self._direction = direction
        self._attr_translation_key = f"{direction}_power_limit"
        self._attr_native_max_value = max_power
        self._attr_native_value = max_power

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last = await self.async_get_last_number_data()
        if last is None or last.native_value is None or last.native_value >= self.native_max_value:
            return
        self._attr_native_value = last.native_value
        self.coordinator.limits[self._direction] = int(last.native_value)
        self.hass.async_create_task(self.coordinator.async_refresh_limits())

    async def async_set_native_value(self, value: float) -> None:
        limit = None if value >= self.native_max_value else int(value)
        await self.coordinator.async_set_limit(self._direction, limit, int(self.native_max_value))
        self._attr_native_value = value
        self.async_write_ha_state()
