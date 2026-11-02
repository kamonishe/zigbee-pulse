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
    "battery_timeout": 360,
    "mains_timeout": 30,
    "startup_grace": 10,
    "offline_template": OFFLINE_TEMPLATE,
    "recovery_template": RECOVERY_TEMPLATE,
    "device_rules": {},
}
def merged_settings(*sources):
    """Merge settings and migrate the pre-1.0.1 timeout names."""
    merged = dict(DEFAULTS)
    legacy_battery_timeout = None
    has_battery_timeout = False
    for source in sources:
        if not source:
            continue
        source = dict(source)
        if "battery_timeout" in source:
            has_battery_timeout = True
        if "default_timeout" in source:
            legacy_battery_timeout = source["default_timeout"]
        merged.update(source)
    if not has_battery_timeout and legacy_battery_timeout is not None:
        merged["battery_timeout"] = legacy_battery_timeout
    merged.pop("default_timeout", None)
    merged.pop("temperature_timeout", None)
    return merged

DEVICE_DEFAULTS = {
    "enabled": True,
    "offline": True,
    "recovery": True,
    "timeout": 0,
    "recipient": "",
}
