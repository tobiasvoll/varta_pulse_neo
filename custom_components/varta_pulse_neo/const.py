from __future__ import annotations

from datetime import timedelta

DOMAIN = "varta_pulse_neo"
CONF_SLAVE_ID = "slave_id"
DEFAULT_NAME = "Varta Pulse Neo"
DEFAULT_PORT = 502
DEFAULT_SLAVE_ID = 255
SCAN_INTERVAL = timedelta(seconds=30)
# Scale factors rarely change; re-read them every hour.
SCALE_FACTOR_REFRESH = timedelta(hours=1)
# The device resets power limits 120 s after the last write.
CONTROL_REFRESH = timedelta(seconds=60)
# Slider maximum when the device does not report its rated power.
DEFAULT_MAX_POWER = 4000
