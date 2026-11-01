"""Configuration defaults for Zigbee Pulse."""
DOMAIN = "zigbee_pulse"
DEFAULTS = {
    "name": "Zigbee Pulse",
    "enabled": True,
    "show_sidebar": True,
    "recipient": "",
    "default_timeout": 360,
    "mains_timeout": 30,
    "temperature_timeout": 30,
    "startup_grace": 10,
    "device_rules": {},
}
MAINS_SUFFIXES = (
    "_socket_last_seen", "_light_switch_last_seen", "_gate_switch_last_seen",
    "_lamp_last_seen", "_router_last_seen", "_air_compressor_last_seen",
)
DEVICE_DEFAULTS = {
    "enabled": True,
    "offline": True,
    "recovery": True,
    "timeout": 0,
    "recipient": "",
}
