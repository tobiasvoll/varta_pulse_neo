from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from .coordinator import VartaConfigEntry

TO_REDACT = {CONF_HOST, "serial", "unique_id"}
# Serial number registers (1054-1063).
SERIAL_REGISTERS = range(1054, 1064)


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: VartaConfigEntry) -> dict[str, Any]:
    coordinator = entry.runtime_data
    data = asdict(coordinator.data) if coordinator.data else {}
    data["raw"] = {str(a): v for a, v in data.get("raw", {}).items() if a not in SERIAL_REGISTERS}
    return {
        "entry": async_redact_data({**entry.as_dict(), "data": dict(entry.data)}, TO_REDACT),
        "device_info": async_redact_data(asdict(coordinator.device_info), TO_REDACT),
        "data": data,
        "last_update_success": coordinator.last_update_success,
    }
