# Zigbee Pulse

Home Assistant custom integration for Zigbee2MQTT health notifications through the built-in Telegram Bot integration.

Install `custom_components/zigbee_pulse` under Home Assistant's `/config/custom_components/` directory, restart Home Assistant, then add **Zigbee Pulse** from Settings → Devices & services.

The options flow discovers enabled MQTT `*_last_seen` entities from the entity registry each time the device picker opens. Newly paired Zigbee2MQTT devices therefore appear without editing YAML. Select a device to configure monitoring, offline alerts, recovery alerts, a per-device timeout, and its Telegram chat. A timeout of `0` uses the global category timeout.

The integration establishes a baseline during the startup grace period, then sends grouped offline and recovery messages. It uses the existing Telegram Bot service and does not store a bot token.
