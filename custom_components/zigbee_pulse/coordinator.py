"""Discover Zigbee2MQTT last_seen sensors and monitor communication."""
from collections import defaultdict
from datetime import timedelta
import logging
from time import monotonic, time

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DEFAULTS, DEVICE_DEFAULTS
from .rules import DeviceHealth, age_seconds, messages, split_message, timeout_for

_LOGGER = logging.getLogger(__name__)


def is_last_seen(entity):
    return (entity.platform == "mqtt" and entity.domain == "sensor"
            and not entity.disabled_by
            and (entity.unique_id.endswith("_last_seen_zigbee2mqtt")
                 or (entity.entity_id.endswith("_last_seen")
                     and "zigbee2mqtt" in entity.unique_id)))


class HealthCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, entry):
        super().__init__(hass, _LOGGER, name="Zigbee Pulse",
                         update_interval=timedelta(minutes=1), config_entry=entry)
        self.settings = DEFAULTS | dict(entry.data) | dict(entry.options)
        self.started_at = monotonic() if hass.is_running else None
        self.known_stale = None
        self.last_notification_error = None

    @property
    def notifications_ready(self):
        return (self.settings["enabled"] and self.started_at is not None
                and monotonic() - self.started_at >= self.settings["startup_grace"] * 60)

    def rule_for(self, entity_id):
        return DEVICE_DEFAULTS | {"recipient": self.settings["recipient"]} | self.settings.get("device_rules", {}).get(entity_id, {})

    def discover(self):
        registry = er.async_get(self.hass)
        devices = dr.async_get(self.hass)
        battery_devices = set()
        for entity in registry.entities.values():
            state = self.hass.states.get(entity.entity_id)
            if entity.device_id and (
                entity.device_class == "battery" or entity.original_device_class == "battery"
                or entity.entity_id.endswith("_battery")
                or (state and state.attributes.get("device_class") == "battery")
            ):
                battery_devices.add(entity.device_id)
        result = {}
        now = time()
        for entity in registry.entities.values():
            if not is_last_seen(entity):
                continue
            rule = self.rule_for(entity.entity_id)
            if not rule["enabled"]:
                continue
            state = self.hass.states.get(entity.entity_id)
            if state is None:
                continue
            device = devices.async_get(entity.device_id) if entity.device_id else None
            name = ((device.name_by_user or device.name) if device else None) or state.name
            timeout = rule["timeout"] * 60 or timeout_for(entity.entity_id, entity.device_id in battery_devices, self.settings)
            result[entity.entity_id] = DeviceHealth(
                entity.entity_id, name, age_seconds(state.state, now), timeout,
            )
        return result

    async def send(self, message, recipient):
        for chunk in split_message(message):
            await self.hass.services.async_call(
                "telegram_bot", "send_message",
                {"entity_id": recipient, "message": chunk, "parse_mode": "plain_text"}, blocking=True,
            )

    async def _send_changes(self, changed, kind, devices):
        groups = defaultdict(set)
        for entity_id in changed:
            rule = self.rule_for(entity_id)
            if rule[kind]:
                groups[rule["recipient"]].add(entity_id)
        for recipient, selected in groups.items():
            scope = {key: value for key, value in devices.items()
                     if self.rule_for(key)["recipient"] == recipient}
            offline = selected if kind == "offline" else set()
            recovery = selected if kind == "recovery" else set()
            offline_message, recovery_message = messages(offline, recovery, scope)
            message = offline_message or recovery_message
            if message:
                await self.send(message, recipient)

    async def _async_update_data(self):
        devices = self.discover()
        current = {key for key, device in devices.items() if device.stale}
        if self.known_stale is None or not self.notifications_ready:
            self.known_stale = current
            return devices
        self.known_stale.intersection_update(devices)
        newly_stale = current - self.known_stale
        recovered = self.known_stale - current
        self.last_notification_error = None
        try:
            await self._send_changes(newly_stale, "offline", devices)
            await self._send_changes(recovered, "recovery", devices)
        except HomeAssistantError:
            self.last_notification_error = "Telegram delivery failed; retrying next minute"
            _LOGGER.exception("Zigbee Pulse notification failed")
            return devices
        self.known_stale.update(newly_stale)
        self.known_stale.difference_update(recovered)
        return devices
