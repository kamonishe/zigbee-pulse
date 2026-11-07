"""Configuration defaults for Zigbee Pulse."""
DOMAIN = "zigbee_pulse"

# Keep these limits shared by the config flow, dashboard WebSocket, and frontend.
MIN_TIMEOUT_MINUTES = 1
MAX_TIMEOUT_MINUTES = 10080
MAX_STARTUP_GRACE_MINUTES = 120


OFFLINE_TEMPLATE = "🔴 Zigbee Device Offline\n\nNewly stale:\n{newly_stale}\n\nCurrently stale: {stale_count} device(s)\n\n{stale_list}"
RECOVERY_TEMPLATE = "🟢 Zigbee Device Online\n\nCommunication restored:\n\n{recovered_list}\n\nStill stale: {stale_count} device(s)"


def validate_minutes(value, *, minimum, maximum):
    """Return an integer minute value or reject malformed input."""
    if isinstance(value, bool):
        raise ValueError("Boolean values are not valid minute values")
    if isinstance(value, float) and not value.is_integer():
        raise ValueError("Minute values must be whole numbers")
    try:
        value = int(value)
    except (TypeError, ValueError, OverflowError) as err:
        raise ValueError("Minute values must be whole numbers") from err
    if not minimum <= value <= maximum:
        raise ValueError(f"Minute value must be between {minimum} and {maximum}")
    return value


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
