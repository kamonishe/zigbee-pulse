"""Pure health monitoring and Telegram formatting helpers."""
from dataclasses import dataclass
from datetime import datetime, timezone
import math

from .const import MAINS_SUFFIXES


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


def messages(newly_stale, recovered, devices):
    """Return separate offline and recovery summaries."""
    stale = sorted((d for d in devices.values() if d.stale),
                   key=lambda d: (d.age if d.age is not None else float("inf"), d.name))
    offline = online = None
    if newly_stale:
        names = "\n".join(f"• {devices[e].name}" for e in sorted(newly_stale))
        listing = "\n".join(f"{i}. {d.name} — {elapsed(d.age)}" for i, d in enumerate(stale, 1))
        offline = (f"🔴 Zigbee Device Offline\n\nNewly stale:\n{names}"
                   f"\n\nCurrently stale: {len(stale)} device(s)\n\n{listing}")
    if recovered:
        listing = "\n".join(f"{i}. {devices[e].name}" for i, e in enumerate(sorted(recovered), 1))
        online = (f"🟢 Zigbee Device Online\n\nCommunication restored:\n\n{listing}"
                  f"\n\nStill stale: {len(stale)} device(s)")
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
