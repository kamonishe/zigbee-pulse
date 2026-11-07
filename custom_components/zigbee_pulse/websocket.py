"""Authenticated WebSocket API used by the Zigbee Pulse sidebar panel."""
from __future__ import annotations

from homeassistant.components import websocket_api
from homeassistant.helpers import device_registry as dr, entity_registry as er
import voluptuous as vol

from .const import (
    DEVICE_DEFAULTS,
    DOMAIN,
    MAX_STARTUP_GRACE_MINUTES,
    MAX_TIMEOUT_MINUTES,
    MIN_TIMEOUT_MINUTES,
    merged_settings,
    validate_minutes,
)
from .coordinator import is_last_seen
from .rules import timeout_minutes_for, unknown_template_fields

GET = {vol.Required("type"): "zigbee_pulse/get_config"}
UPDATE = {
    vol.Required("type"): "zigbee_pulse/update_config",
    vol.Required("entry_id"): str,
    vol.Required("scope"): vol.In(["global", "device"]),
    vol.Optional("entity_id"): str,
    vol.Optional("settings"): dict,
}


def _recipients(hass):
    registry = er.async_get(hass)
    return [
        {"entity_id": entity.entity_id, "name": entity.name or entity.entity_id}
        for entity in registry.entities.values()
        if entity.domain == "notify" and entity.platform == "telegram_bot" and not entity.disabled_by
    ]


def _devices(hass, settings):
    entities = er.async_get(hass)
    devices = dr.async_get(hass)
    battery_devices = set()
    for entity in entities.entities.values():
        state = hass.states.get(entity.entity_id)
        if entity.device_id and (
            entity.device_class == "battery"
            or entity.original_device_class == "battery"
            or entity.entity_id.endswith("_battery")
            or (state and state.attributes.get("device_class") == "battery")
        ):
            battery_devices.add(entity.device_id)
    result = []
    for entity in entities.entities.values():
        if not is_last_seen(entity):
            continue
        device = devices.async_get(entity.device_id) if entity.device_id else None
        name = ((device.name_by_user or device.name) if device else None) or entity.entity_id
        state = hass.states.get(entity.entity_id)
        rule = DEVICE_DEFAULTS | {"recipient": settings["recipient"]} | settings.get("device_rules", {}).get(entity.entity_id, {})
        global_timeout = timeout_minutes_for(
            entity.entity_id, entity.device_id in battery_devices, settings)
        timeout = rule["timeout"] or global_timeout
        result.append({
            "entity_id": entity.entity_id,
            "name": name,
            "state": state.state if state else "unknown",
            "power_source": "battery" if entity.device_id in battery_devices else "mains",
            "rule": rule,
            "timeout": timeout,
            "global_timeout": global_timeout,
        })
    return sorted(result, key=lambda item: item["name"].lower())


@websocket_api.require_admin
@websocket_api.async_response
@websocket_api.websocket_command(GET)
async def ws_get_config(hass, connection, msg):
    entries = hass.config_entries.async_entries(DOMAIN)
    payload = []
    for entry in entries:
        settings = merged_settings(entry.data, entry.options)
        payload.append({
            "entry_id": entry.entry_id,
            "title": entry.title,
            "settings": {key: value for key, value in settings.items() if key != "device_rules"},
            "devices": _devices(hass, settings),
        })
    connection.send_result(msg["id"], {"entries": payload, "recipients": _recipients(hass)})


@websocket_api.require_admin
@websocket_api.async_response
@websocket_api.websocket_command(UPDATE)
async def ws_update_config(hass, connection, msg):
    entry = hass.config_entries.async_get_entry(msg["entry_id"])
    if entry is None:
        connection.send_error(msg["id"], "not_found", "Zigbee Pulse entry not found")
        return
    settings = merged_settings(entry.data, entry.options)
    incoming = msg.get("settings") or {}
    if msg["scope"] == "global":
        allowed = {"name", "recipient", "mains_timeout", "battery_timeout", "startup_grace", "enabled", "show_sidebar", "offline_template", "recovery_template"}
        for template_key in ("offline_template", "recovery_template"):
            if template_key in incoming:
                template = incoming[template_key]
                if not isinstance(template, str) or not template.strip():
                    connection.send_error(msg["id"], "invalid_template", "Message templates cannot be empty")
                    return
                unknown = unknown_template_fields(template)
                if unknown:
                    connection.send_error(msg["id"], "invalid_template", f"Unknown template variable(s): {', '.join(unknown)}")
                    return
        merged = settings | {key: incoming[key] for key in allowed if key in incoming}
        minute_ranges = {
            "mains_timeout": (MIN_TIMEOUT_MINUTES, MAX_TIMEOUT_MINUTES),
            "battery_timeout": (MIN_TIMEOUT_MINUTES, MAX_TIMEOUT_MINUTES),
            "startup_grace": (0, MAX_STARTUP_GRACE_MINUTES),
        }
        try:
            for key, (minimum, maximum) in minute_ranges.items():
                merged[key] = validate_minutes(
                    merged[key], minimum=minimum, maximum=maximum)
        except ValueError:
            connection.send_error(
                msg["id"],
                "invalid_timeout",
                "Timeouts must be whole minutes; mains and battery values must be "
                f"between {MIN_TIMEOUT_MINUTES} and {MAX_TIMEOUT_MINUTES}, and "
                f"startup grace must be between 0 and {MAX_STARTUP_GRACE_MINUTES}",
            )
            return
        if (
            not isinstance(merged.get("name"), str)
            or not merged["name"].strip()
            or not isinstance(merged.get("recipient"), str)
            or not merged["recipient"]
        ):
            connection.send_error(msg["id"], "invalid", "Name and Telegram recipient are required")
            return
        hass.config_entries.async_update_entry(entry, title=merged["name"], options=merged)
    else:
        entity_id = msg.get("entity_id")
        if not entity_id or not any(item["entity_id"] == entity_id for item in _devices(hass, settings)):
            connection.send_error(msg["id"], "invalid", "Unknown Zigbee2MQTT last_seen entity")
            return
        allowed = {"enabled", "offline", "recovery", "timeout", "recipient"}
        rule = DEVICE_DEFAULTS | {"recipient": settings["recipient"]} | settings.get("device_rules", {}).get(entity_id, {})
        rule.update({key: incoming[key] for key in allowed if key in incoming})
        try:
            rule["timeout"] = validate_minutes(
                rule["timeout"], minimum=0, maximum=MAX_TIMEOUT_MINUTES)
        except ValueError:
            connection.send_error(
                msg["id"],
                "invalid_timeout",
                f"Device timeout must be 0 (inherit global) or between "
                f"{MIN_TIMEOUT_MINUTES} and {MAX_TIMEOUT_MINUTES} minutes",
            )
            return
        rules = dict(settings.get("device_rules", {}))
        rules[entity_id] = rule
        settings["device_rules"] = rules
        hass.config_entries.async_update_entry(entry, options=settings)
    await hass.config_entries.async_reload(entry.entry_id)
    connection.send_result(msg["id"], {"ok": True})


def async_register(hass):
    websocket_api.async_register_command(hass, ws_get_config)
    websocket_api.async_register_command(hass, ws_update_config)
