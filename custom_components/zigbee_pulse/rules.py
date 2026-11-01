"""Pure health monitoring and Telegram formatting helpers."""
from dataclasses import dataclass
from datetime import datetime, timezone
import math
import re

from .const import MAINS_SUFFIXES, OFFLINE_TEMPLATE, RECOVERY_TEMPLATE, TEMPLATE_FIELDS


@dataclass(frozen=True)
class DeviceHealth:
    entity_id: str
    name: str
    age: float | None
    timeout: float

    @property
    def stale(self):
        return self.age is None or self.age > self.timeout


def timeout_for(entity_id, has_battery, settings):
    if "temperature" in entity_id:
        return settings["temperature_timeout"] * 60
    if entity_id.endswith(MAINS_SUFFIXES) and not has_battery:
        return settings["mains_timeout"] * 60
    return settings["default_timeout"] * 60


def timeout_minutes_for(entity_id, has_battery, settings):
    """Return the configured timeout in minutes for a device."""
    return int(timeout_for(entity_id, has_battery, settings) / 60)


def age_seconds(value, now):
    """Accept ISO timestamps or Unix seconds/milliseconds; invalid means unknown."""
    try:
        timestamp = float(value)
        if timestamp > 100_000_000_000:
            timestamp /= 1000
    except (TypeError, ValueError):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            # Zigbee2MQTT should publish ISO_8601 (UTC), not ambiguous local time.
            if parsed.tzinfo is None:
                return None
            timestamp = parsed.astimezone(timezone.utc).timestamp()
        except (AttributeError, TypeError, ValueError, OverflowError):
            return None
    if not math.isfinite(timestamp) or timestamp <= 0:
        return None
    return max(0, now - timestamp)


def elapsed(age):
    if age is None:
        return "Unknown"
    minutes = int(age) // 60
    days, minutes = divmod(minutes, 1440)
    hours, minutes = divmod(minutes, 60)
    parts = [f"{n} {unit}{'' if n == 1 else 's'}"
             for n, unit in ((days, "day"), (hours, "hour"), (minutes, "minute"))
             if n or unit == "minute"]
    return " and ".join((" ".join(parts[:-1]), parts[-1])) if len(parts) > 1 else parts[0]


_TEMPLATE_FIELD_PATTERN = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)\}")


def unknown_template_fields(template):
    """Return placeholder names that Zigbee Pulse cannot render."""
    return sorted({
        field for field in _TEMPLATE_FIELD_PATTERN.findall(template)
        if field not in TEMPLATE_FIELDS
    })


def render_template(template, values):
    """Render known placeholders and leave escaped/unknown text untouched."""
    return _TEMPLATE_FIELD_PATTERN.sub(
        lambda match: str(values.get(match.group(1), match.group(0))), template)


def _message_values(kind, newly_stale, recovered, devices, settings):
    stale = sorted(
        (device for device in devices.values() if device.stale),
        key=lambda device: (device.age if device.age is not None else float("inf"), device.name),
    )
    selected = newly_stale if kind == "offline" else recovered
    selected_devices = [devices[entity_id] for entity_id in sorted(selected) if entity_id in devices]
    selected_names = [device.name for device in selected_devices]
    stale_names = [f"• {name}" for name in selected_names] if kind == "offline" else []
    stale_list = "\n".join(
        f"{index}. {device.name} — {elapsed(device.age)}"
        for index, device in enumerate(stale, 1)
    )
    recovered_list = "\n".join(
        f"{index}. {device.name}"
        for index, device in enumerate(selected_devices, 1)
    )
    first = selected_devices[0] if selected_devices else None
    event = "Device Offline" if kind == "offline" else "Device Online"
    return {
        "monitor_name": settings.get("name", "Zigbee Pulse"),
        "event": event,
        "status": "Offline" if kind == "offline" else "Online",
        "device_name": first.name if first else "",
        "entity_id": first.entity_id if first else "",
        "timestamp": datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %Z"),
        "newly_stale": "\n".join(stale_names),
        "stale_count": len(stale),
        "stale_list": stale_list,
        "recovered_count": len(recovered),
        "recovered_list": recovered_list,
    }


def messages(newly_stale, recovered, devices, settings=None):
    """Return formatted offline and recovery summaries."""
    settings = settings or {}
    offline = online = None
    if newly_stale:
        template = settings.get("offline_template", OFFLINE_TEMPLATE)
        offline = render_template(
            template, _message_values("offline", newly_stale, recovered, devices, settings))
    if recovered:
        template = settings.get("recovery_template", RECOVERY_TEMPLATE)
        online = render_template(
            template, _message_values("recovery", newly_stale, recovered, devices, settings))
    return offline, online

def split_message(message, limit=3500):
    """Split by UTF-16 units, preserving lines when possible (Telegram limit 4096)."""
    chunks, current, units = [], "", 0
    for char in message:
        size = len(char.encode("utf-16-le")) // 2
        if units + size > limit:
            split = current.rfind("\n")
            if split > 0:
                chunks.append(current[:split])
                current = current[split + 1:]
                units = len(current.encode("utf-16-le")) // 2
            else:
                chunks.append(current)
                current, units = "", 0
        current += char
        units += size
    if current:
        chunks.append(current)
    return chunks
