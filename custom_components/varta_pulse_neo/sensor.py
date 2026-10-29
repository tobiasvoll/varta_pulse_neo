from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
import logging

from homeassistant.components.sensor import (
    RestoreSensor,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    CONF_HOST,
    PERCENTAGE,
    EntityCategory,
    Platform,
    UnitOfApparentPower,
    UnitOfEnergy,
    UnitOfFrequency,
    UnitOfPower,
    UnitOfReactivePower,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .api import STATES, VartaData, VartaDeviceInfo
from .const import DOMAIN
from .coordinator import VartaConfigEntry, VartaCoordinator

_LOGGER = logging.getLogger(__name__)

# Gaps longer than this (e.g. while the device was unreachable) are not integrated.
MAX_INTEGRATION_GAP = 300
# Readings of the charge counter that imply more than this power are discarded.
MAX_CHARGE_POWER = 10000  # W
COUNTER_TOLERANCE = 10  # Wh
# A discarded reading is accepted as the new counter value when this many
# consecutive readings agree with it (e.g. after the counter was reset).
COUNTER_REBASE_READINGS = 10


def _positive(value: float | None) -> float | None:
    return None if value is None else max(value, 0.0)


def _negative_abs(value: float | None) -> float | None:
    return None if value is None else abs(min(value, 0.0))


@dataclass(frozen=True, kw_only=True)
class VartaSensorEntityDescription(SensorEntityDescription):
    value_fn: Callable[[VartaData], float | int | str | datetime | None]


@dataclass(frozen=True, kw_only=True)
class VartaInfoSensorEntityDescription(SensorEntityDescription):
    value_fn: Callable[[VartaDeviceInfo], str | int]


POWER = {
    "native_unit_of_measurement": UnitOfPower.WATT,
    "device_class": SensorDeviceClass.POWER,
    "state_class": SensorStateClass.MEASUREMENT,
}
STORED_ENERGY = {
    "native_unit_of_measurement": UnitOfEnergy.WATT_HOUR,
    "suggested_unit_of_measurement": UnitOfEnergy.KILO_WATT_HOUR,
    "device_class": SensorDeviceClass.ENERGY_STORAGE,
    "state_class": SensorStateClass.MEASUREMENT,
}

# Keys are part of the unique ids and must not change.
SENSORS: tuple[VartaSensorEntityDescription, ...] = (
    VartaSensorEntityDescription(
        key="state",
        translation_key="state",
        device_class=SensorDeviceClass.ENUM,
        options=[*STATES.values(), "unknown"],
        value_fn=lambda d: d.state,
    ),
    VartaSensorEntityDescription(
        key="soc",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.soc,
    ),
    VartaSensorEntityDescription(
        key="active_power_charge",
        translation_key="charge_power",
        value_fn=lambda d: _positive(d.active_power),
        **POWER,
    ),
    VartaSensorEntityDescription(
        key="active_power_discharge",
        translation_key="discharge_power",
        value_fn=lambda d: _negative_abs(d.active_power),
        **POWER,
    ),
    VartaSensorEntityDescription(
        key="active_power",
        translation_key="battery_power",
        value_fn=lambda d: d.active_power,
        **POWER,
    ),
    VartaSensorEntityDescription(
        key="apparent_power",
        native_unit_of_measurement=UnitOfApparentPower.VOLT_AMPERE,
        device_class=SensorDeviceClass.APPARENT_POWER,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        # VARTA signs it like the active power; apparent power is a magnitude.
        value_fn=lambda d: None if d.apparent_power is None else abs(d.apparent_power),
    ),
    VartaSensorEntityDescription(
        key="grid_power_backfeed",
        translation_key="grid_feed_in",
        value_fn=lambda d: _positive(d.grid_power),
        **POWER,
    ),
    VartaSensorEntityDescription(
        key="grid_power_consumption",
        translation_key="grid_consumption",
        value_fn=lambda d: _negative_abs(d.grid_power),
        **POWER,
    ),
    VartaSensorEntityDescription(
        key="capacity",
        translation_key="capacity",
        value_fn=lambda d: d.capacity,
        **STORED_ENERGY,
    ),
    VartaSensorEntityDescription(
        key="usable_energy_for_charging",
        translation_key="usable_charge_energy",
        value_fn=lambda d: d.usable_charge_energy,
        **STORED_ENERGY,
    ),
    VartaSensorEntityDescription(
        key="usable_energy_for_discharging",
        translation_key="usable_discharge_energy",
        value_fn=lambda d: d.usable_discharge_energy,
        **STORED_ENERGY,
    ),
    VartaSensorEntityDescription(
        key="available_ac_charging_power",
        translation_key="available_charge_power",
        value_fn=lambda d: d.available_charge_power,
        **POWER,
    ),
    VartaSensorEntityDescription(
        key="available_ac_discharging_power",
        translation_key="available_discharge_power",
        value_fn=lambda d: d.available_discharge_power,
        **POWER,
    ),
    VartaSensorEntityDescription(
        key="grid_frequency",
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        device_class=SensorDeviceClass.FREQUENCY,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.grid_frequency,
    ),
    VartaSensorEntityDescription(
        key="reactive_power",
        native_unit_of_measurement=UnitOfReactivePower.VOLT_AMPERE_REACTIVE,
        device_class=SensorDeviceClass.REACTIVE_POWER,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda d: d.reactive_power,
    ),
    VartaSensorEntityDescription(
        key="pv_sensor_power",
        translation_key="pv_power",
        value_fn=lambda d: d.pv_power,
        **POWER,
    ),
    VartaSensorEntityDescription(
        key="installed_batteries",
        translation_key="installed_batteries",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.modules,
    ),
    VartaSensorEntityDescription(
        key="error_code",
        translation_key="error_code",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.error_code,
    ),
    VartaSensorEntityDescription(
        key="device_time",
        translation_key="device_time",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda d: d.device_time,
    ),
)

# Sensors of earlier versions that no longer exist.
REMOVED_KEYS = ("apparent_power_charge", "apparent_power_discharge")

INFO_SENSORS: tuple[VartaInfoSensorEntityDescription, ...] = (
    VartaInfoSensorEntityDescription(
        key="ems",
        translation_key="ems_version",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda i: i.ems_version,
    ),
    VartaInfoSensorEntityDescription(
        key="ens",
        translation_key="ens_version",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda i: i.ens_version,
    ),
    VartaInfoSensorEntityDescription(
        key="software",
        translation_key="inverter_version",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda i: i.inverter_version,
    ),
    VartaInfoSensorEntityDescription(
        key="table_version",
        translation_key="table_version",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda i: i.table_version,
    ),
    VartaInfoSensorEntityDescription(
        key="serial",
        translation_key="serial",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda i: i.serial,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: VartaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    registry = er.async_get(hass)
    for key in REMOVED_KEYS:
        if entity_id := registry.async_get_entity_id(Platform.SENSOR, DOMAIN, f"{entry.entry_id}_{key}"):
            registry.async_remove(entity_id)
    entities: list[SensorEntity] = [VartaSensor(coordinator, d) for d in SENSORS]
    entities += [VartaInfoSensor(coordinator, d) for d in INFO_SENSORS]
    entities.append(VartaChargedEnergySensor(coordinator))
    entities.append(VartaDischargedEnergySensor(coordinator))
    async_add_entities(entities)


class VartaEntity(CoordinatorEntity[VartaCoordinator]):
    _attr_has_entity_name = True

    def __init__(self, coordinator: VartaCoordinator, key: str) -> None:
        super().__init__(coordinator)
        entry = coordinator.config_entry
        info = coordinator.device_info
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, info.serial)},
            name=entry.title,
            manufacturer="VARTA",
            model="pulse neo",
            serial_number=info.serial,
            sw_version=info.ems_version,
            configuration_url=f"http://{entry.data[CONF_HOST]}",
        )


class VartaSensor(VartaEntity, SensorEntity):
    entity_description: VartaSensorEntityDescription

    def __init__(self, coordinator: VartaCoordinator, description: VartaSensorEntityDescription) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> float | int | str | datetime | None:
        return self.entity_description.value_fn(self.coordinator.data)


class VartaInfoSensor(VartaEntity, SensorEntity):
    entity_description: VartaInfoSensorEntityDescription

    def __init__(self, coordinator: VartaCoordinator, description: VartaInfoSensorEntityDescription) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> str | int:
        return self.entity_description.value_fn(self.coordinator.device_info)


def _plausible(old: float, new: float, seconds: float | None) -> bool:
    """Whether the charge counter may go from old to new within seconds."""
    if new < old:
        return False
    if seconds is None:
        return True
    return new - old <= MAX_CHARGE_POWER * seconds / 3600 + COUNTER_TOLERANCE


class VartaChargedEnergySensor(VartaEntity, RestoreSensor):
    """Charged energy from the device counter (register 1069).

    A single wrong reading, such as 0 while the EMS restarts, would count as a
    meter reset in the statistics, so readings that go backwards or jump are
    discarded until enough consecutive readings confirm them.
    """

    _attr_translation_key = "charged_energy"
    _attr_native_unit_of_measurement = UnitOfEnergy.WATT_HOUR
    _attr_suggested_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING

    def __init__(self, coordinator: VartaCoordinator) -> None:
        super().__init__(coordinator, "energy_counter_ac_to_dc")
        self._last_time: datetime | None = None
        self._candidate: float | None = None
        self._candidate_time: datetime | None = None
        self._candidate_count = 0

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if (last := await self.async_get_last_sensor_data()) is not None and isinstance(
            last.native_value, (int, float)
        ):
            self._attr_native_value = float(last.native_value)
        if self.coordinator.data is not None:
            self._update(self.coordinator.data.charged_energy)

    @callback
    def _handle_coordinator_update(self) -> None:
        if self.coordinator.last_update_success:
            self._update(self.coordinator.data.charged_energy)
        super()._handle_coordinator_update()

    def _update(self, value: float | None) -> None:
        if value is None:
            return
        now = dt_util.utcnow()
        current = self._attr_native_value
        if current is None or _plausible(float(current), value, self._seconds_since(self._last_time, now)):
            self._accept(value, now)
            return
        if self._candidate is not None and _plausible(
            self._candidate, value, self._seconds_since(self._candidate_time, now)
        ):
            self._candidate_count += 1
        else:
            _LOGGER.debug("Discarding charged energy reading %s Wh (last %s Wh)", value, current)
            self._candidate_count = 1
        self._candidate = value
        self._candidate_time = now
        if self._candidate_count >= COUNTER_REBASE_READINGS:
            _LOGGER.warning("Charged energy counter changed from %s Wh to %s Wh, accepting it", current, value)
            self._accept(value, now)

    def _accept(self, value: float, now: datetime) -> None:
        self._attr_native_value = value
        self._last_time = now
        self._candidate = None
        self._candidate_time = None
        self._candidate_count = 0

    @staticmethod
    def _seconds_since(then: datetime | None, now: datetime) -> float | None:
        return None if then is None else (now - then).total_seconds()


class VartaDischargedEnergySensor(VartaEntity, RestoreSensor):
    """Discharged energy, integrated from the discharge power.

    VARTA only provides a counter for charged energy.
    """

    _attr_translation_key = "discharged_energy"
    _attr_native_unit_of_measurement = UnitOfEnergy.WATT_HOUR
    _attr_suggested_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING

    def __init__(self, coordinator: VartaCoordinator) -> None:
        super().__init__(coordinator, "energy_discharged")
        self._attr_native_value = 0.0
        self._last_power: float | None = None
        self._last_time: datetime | None = None

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if (last := await self.async_get_last_sensor_data()) is not None and isinstance(
            last.native_value, (int, float)
        ):
            self._attr_native_value = float(last.native_value)

    @callback
    def _handle_coordinator_update(self) -> None:
        if not self.coordinator.last_update_success:
            # Do not integrate stale values; the gap check skips the outage.
            super()._handle_coordinator_update()
            return
        power = _negative_abs(self.coordinator.data.active_power)
        now = dt_util.utcnow()
        if power is not None and self._last_power is not None and self._last_time is not None:
            seconds = (now - self._last_time).total_seconds()
            if 0 < seconds <= MAX_INTEGRATION_GAP:
                self._attr_native_value += (self._last_power + power) / 2 * seconds / 3600
        self._last_power = power
        self._last_time = now
        super()._handle_coordinator_update()

    @property
    def available(self) -> bool:
        # Keep the counter visible while the device is briefly unreachable.
        return True
