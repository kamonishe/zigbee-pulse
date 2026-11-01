"""Configuration defaults for Zigbee Pulse."""
DOMAIN = "zigbee_pulse"
OFFLINE_TEMPLATE = "🔴 Zigbee Device Offline\n\nNewly stale:\n{newly_stale}\n\nCurrently stale: {stale_count} device(s)\n\n{stale_list}"
RECOVERY_TEMPLATE = "🟢 Zigbee Device Online\n\nCommunication restored:\n\n{recovered_list}\n\nStill stale: {stale_count} device(s)"
TEMPLATE_FIELDS = frozenset({
    "monitor_name", "event", "status", "device_name", "entity_id", "timestamp",
    "newly_stale", "stale_count", "stale_list", "recovered_count", "recovered_list",
})

DEFAULTS = {
    "name": "Zigbee Pulse",
    "enabled": True,
    "show_sidebar": True,
    "recipient": "",
    "default_timeout": 360,
    "mains_timeout": 30,
    "temperature_timeout": 30,
    "startup_grace": 10,
    "offline_template": OFFLINE_TEMPLATE,
    "recovery_template": RECOVERY_TEMPLATE,
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
