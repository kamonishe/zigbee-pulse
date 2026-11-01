"""Authenticated WebSocket API used by the Zigbee Pulse sidebar panel."""
from __future__ import annotations

from homeassistant.components import websocket_api
from homeassistant.helpers import device_registry as dr, entity_registry as er
import voluptuous as vol

from .const import DEFAULTS, DEVICE_DEFAULTS, DOMAIN
from .coordinator import is_last_seen
from .rules import timeout_minutes_for

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
        timeout = rule["timeout"] or timeout_minutes_for(
            entity.entity_id, entity.device_id in battery_devices, settings)
        result.append({
            "entity_id": entity.entity_id,
            "name": name,
            "state": state.state if state else "unknown",
            "rule": rule,
            "timeout": timeout,
        })
    return sorted(result, key=lambda item: item["name"].lower())


@websocket_api.require_admin
@websocket_api.async_response
@websocket_api.websocket_command(GET)
async def ws_get_config(hass, connection, msg):
    entries = hass.config_entries.async_entries(DOMAIN)
    payload = []
    for entry in entries:
        settings = DEFAULTS | dict(entry.data) | dict(entry.options)
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
    settings = DEFAULTS | dict(entry.data) | dict(entry.options)
    incoming = msg.get("settings") or {}
    if msg["scope"] == "global":
        allowed = {"name", "recipient", "default_timeout", "mains_timeout", "temperature_timeout", "startup_grace", "enabled", "show_sidebar"}
        merged = settings | {key: incoming[key] for key in allowed if key in incoming}
        if not merged["name"].strip() or not merged["recipient"]:
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
        rules = dict(settings.get("device_rules", {}))
        rules[entity_id] = rule
        settings["device_rules"] = rules
        hass.config_entries.async_update_entry(entry, options=settings)
    await hass.config_entries.async_reload(entry.entry_id)
    connection.send_result(msg["id"], {"ok": True})


def async_register(hass):
    websocket_api.async_register_command(hass, ws_get_config)
    websocket_api.async_register_command(hass, ws_update_config)
