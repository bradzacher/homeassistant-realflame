"""Constants for Real Flame local TCP integration."""

from __future__ import annotations

DOMAIN = "real_flame"

DEFAULT_PORT = 3000
DEFAULT_NAME = "Real Flame Fireplace"
DEFAULT_POLL_INTERVAL = 45
DEFAULT_AUTO_OFF_HOURS = 3.0

CONF_HOST = "host"
CONF_PORT = "port"
CONF_NAME = "name"
CONF_POLL_INTERVAL = "poll_interval"
CONF_AUTO_OFF_HOURS = "auto_off_hours"
CONF_BLOCK_TURN_ON = "block_turn_on"

# Modes from ModulatingValve / AppSettings
MODE_MANUAL_TEMP = 0
MODE_MANUAL_FLAME = 1
MODE_AUTO_TIMER = 2
MODE_EX_MANAGED = 3
MODE_OFF = 4

MODE_LABELS = {
    MODE_MANUAL_TEMP: "manual_temperature",
    MODE_MANUAL_FLAME: "manual_flame",
    MODE_AUTO_TIMER: "auto",
    MODE_EX_MANAGED: "external",
    MODE_OFF: "off",
}

TEMP_MIN = 10
TEMP_MAX = 35
FLAME_MIN = 1
FLAME_MAX = 7

CMD_STATUS = "MWIL10"
CMD_CONTROL_PREFIX = "MWIL20"

CONNECT_TIMEOUT = 5.0
READ_TIMEOUT = 2.0
