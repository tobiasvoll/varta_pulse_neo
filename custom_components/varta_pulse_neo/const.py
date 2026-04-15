from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from homeassistant.components.sensor import SensorEntityDescription
from homeassistant.const import PERCENTAGE
from homeassistant.helpers.entity import EntityCategory

DOMAIN = "varta_pulse_neo"
CONF_SLAVE_ID = "slave_id"
DEFAULT_NAME = "Varta Pulse Neo"
DEFAULT_PORT = 502
DEFAULT_SLAVE_ID = 255
SCAN_INTERVAL = timedelta(seconds=30)
PLATFORMS = ["sensor"]


@dataclass
class VartaSensorEntityDescription(SensorEntityDescription):
    address: int = 0
    slave: int = 1
    data_type: str = "uint16"
    count: int = 1
    scale: float = 1.0
    scale_factor_key: str | None = None
    value_map: dict[int, str] | None = None
    derived_from: str | None = None
    derived_mode: str | None = None


STATE_MAP = {
    0: "Busy",
    1: "Run",
    2: "Charge",
    3: "Discharge",
    4: "Standby",
    5: "Error",
    6: "Passive (Service)",
    7: "Islanding",
}


SCALE_FACTOR_ADDRESSES = {
    "active_power_scale_factor": 2066,
    "apparent_power_scale_factor": 2067,
    "energy_counter_scale_factor": 2069,
    "capacity_scale_factor": 2071,
    "grid_power_scale_factor": 2078,
    "available_ac_charging_power_scale_factor": 2083,
    "available_ac_discharging_power_scale_factor": 2084,
    "usable_energy_for_charging_scale_factor": 2085,
    "usable_energy_for_discharging_scale_factor": 2086,
}


SENSOR_TYPES = (
    VartaSensorEntityDescription(
        key="ems",
        name="EMS",
        address=1000,
        count=17,
        data_type="string",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    VartaSensorEntityDescription(
        key="ens",
        name="ENS",
        address=1017,
        count=17,
        data_type="string",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    VartaSensorEntityDescription(
        key="software",
        name="Inverter software version",
        address=1034,
        count=17,
        data_type="string",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    VartaSensorEntityDescription(
        key="table_version",
        name="Table version",
        address=1051,
        data_type="uint16",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    VartaSensorEntityDescription(
        key="serial",
        name="Serial",
        address=1054,
        count=10,
        data_type="string",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    VartaSensorEntityDescription(
        key="installed_batteries",
        name="Installed batteries",
        address=1064,
        data_type="uint16",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    VartaSensorEntityDescription(
        key="state",
        name="State",
        address=1065,
        data_type="uint16",
        value_map=STATE_MAP,
    ),
    VartaSensorEntityDescription(
        key="active_power_charge",
        name="Charge power",
        derived_from="active_power",
        derived_mode="positive",
        native_unit_of_measurement="W",
        device_class="power",
    ),
    VartaSensorEntityDescription(
        key="active_power_discharge",
        name="Discharge power",
        derived_from="active_power",
        derived_mode="negative_abs",
        native_unit_of_measurement="W",
        device_class="power",
    ),
    VartaSensorEntityDescription(
        key="apparent_power_charge",
        name="Charge apparent power",
        derived_from="apparent_power",
        derived_mode="positive",
        native_unit_of_measurement="VA",
        device_class="apparent_power",
    ),
    VartaSensorEntityDescription(
        key="apparent_power_discharge",
        name="Discharge apparent power",
        derived_from="apparent_power",
        derived_mode="negative_abs",
        native_unit_of_measurement="VA",
        device_class="apparent_power",
    ),
    VartaSensorEntityDescription(
        key="soc",
        name="State of charge",
        address=1068,
        data_type="uint16",
        native_unit_of_measurement=PERCENTAGE,
        device_class="battery",
    ),
    VartaSensorEntityDescription(
        key="energy_counter_ac_to_dc",
        name="Energy counter AC to DC",
        address=1069,
        count=2,
        data_type="uint32sw",
        scale_factor_key="energy_counter_scale_factor",
        native_unit_of_measurement="Wh",
        device_class="energy",
    ),
    VartaSensorEntityDescription(
        key="capacity",
        name="Installed capacity",
        address=1071,
        data_type="uint16",
        scale=10,
        scale_factor_key="capacity_scale_factor",
        native_unit_of_measurement="Wh",
        device_class="energy",
    ),
    VartaSensorEntityDescription(
        key="grid_power_backfeed",
        name="Grid feed-in",
        derived_from="grid_power",
        derived_mode="positive",
        native_unit_of_measurement="W",
        device_class="power",
    ),
    VartaSensorEntityDescription(
        key="grid_power_consumption",
        name="Grid consumption",
        derived_from="grid_power",
        derived_mode="negative_abs",
        native_unit_of_measurement="W",
        device_class="power",
    ),
    VartaSensorEntityDescription(
        key="grid_frequency",
        name="Grid frequency",
        address=1082,
        data_type="uint16",
        scale=0.01,
        native_unit_of_measurement="Hz",
        device_class="frequency",
    ),
    VartaSensorEntityDescription(
        key="available_ac_charging_power",
        name="Available AC charging power",
        address=1083,
        data_type="uint16",
        scale_factor_key="available_ac_charging_power_scale_factor",
        native_unit_of_measurement="W",
        device_class="power",
    ),
    VartaSensorEntityDescription(
        key="available_ac_discharging_power",
        name="Available AC discharging power",
        address=1084,
        data_type="uint16",
        scale_factor_key="available_ac_discharging_power_scale_factor",
        native_unit_of_measurement="W",
        device_class="power",
    ),
    VartaSensorEntityDescription(
        key="usable_energy_for_charging",
        name="Usable energy for charging",
        address=1085,
        data_type="uint16",
        scale_factor_key="usable_energy_for_charging_scale_factor",
        native_unit_of_measurement="Wh",
        device_class="energy",
    ),
    VartaSensorEntityDescription(
        key="usable_energy_for_discharging",
        name="Usable energy for discharging",
        address=1086,
        data_type="uint16",
        scale_factor_key="usable_energy_for_discharging_scale_factor",
        native_unit_of_measurement="Wh",
        device_class="energy",
    ),
    VartaSensorEntityDescription(
        key="reactive_power",
        name="Reactive power",
        address=1087,
        data_type="int16",
        native_unit_of_measurement="var",
    ),
    VartaSensorEntityDescription(
        key="pv_sensor_power",
        name="PV sensor power",
        address=1102,
        data_type="uint16",
        native_unit_of_measurement="W",
        device_class="power",
    ),
)


READ_BLOCKS = (
    (1000, 88),
    (1102, 1),
    (2066, 21),
)
