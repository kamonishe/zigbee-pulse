"""Stale-device count and diagnostic attributes."""
from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([StaleDevicesSensor(entry)])


class StaleDevicesSensor(CoordinatorEntity, SensorEntity):
    _attr_icon = "mdi:zigbee"
    _attr_native_unit_of_measurement = "devices"

    def __init__(self, entry):
        super().__init__(entry.runtime_data)
        self._attr_unique_id = f"{entry.entry_id}_stale_devices"
        self._attr_name = f"{entry.title} stale devices"

    @property
    def native_value(self):
        return sum(device.stale for device in (self.coordinator.data or {}).values())

    @property
    def extra_state_attributes(self):
        devices = self.coordinator.data or {}
        return {
            "monitored_count": len(devices),
            "stale_devices": sorted(key for key, value in devices.items() if value.stale),
            "notifications_ready": self.coordinator.notifications_ready,
            "last_notification_error": self.coordinator.last_notification_error,
            "devices": {key: {"name": value.name, "silence_seconds": int(value.age) if value.age is not None else None,
                              "timeout_minutes": value.timeout / 60, "stale": value.stale}
                        for key, value in devices.items()},
        }
