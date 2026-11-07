# Zigbee Pulse

Home Assistant integration for Zigbee2MQTT device connection monitoring with per-device Telegram alerts, mains and battery timeouts, and a live dashboard.

<!-- ha-marketplace:exclude-start -->
## Installation with Home Assistant Marketplace

[![Open Zigbee Pulse in Home Assistant Marketplace](https://my.home-assistant.io/badges/marketplace_repository.svg)](https://my.home-assistant.io/redirect/marketplace_repository/?owner=kamonishe&repository=zigbee-pulse&category=integration)

On Home Assistant **2026.11 and newer**:

1. Open **Settings → Marketplace**.
2. Search for **Zigbee Pulse**.
3. Select **Install**.
4. Complete the integration setup when Home Assistant opens it.

The Marketplace is built into Home Assistant and installs Zigbee Pulse under `custom_components/zigbee_pulse/`.

## Older Home Assistant versions

On versions before **2026.11**, install Zigbee Pulse through HACS:

1. Open **HACS** in Home Assistant.
2. Search for **Zigbee Pulse**.
3. Open the integration and choose **Download**.
4. Restart Home Assistant.
5. Go to **Settings → Devices & services → Add integration**, search for **Zigbee Pulse**, and complete the setup.

## Manual installation

Copy `custom_components/zigbee_pulse` into the `custom_components` directory in your Home Assistant configuration, restart Home Assistant, and add **Zigbee Pulse** from **Settings → Devices & services**.

<!-- ha-marketplace:exclude-end -->

## Configuration

Zigbee Pulse requires the Home Assistant **MQTT** and **Telegram Bot** integrations. During setup, select the Telegram notify entity that should receive alerts. The integration discovers enabled Zigbee2MQTT `last_seen` sensors whenever the device picker opens, so newly paired devices can be added without editing YAML.

The sidebar dashboard provides separate mains and battery timeouts, per-device monitoring and notification rules, Telegram message templates with live previews, and a sidebar visibility toggle. A device timeout of `0` inherits the effective global timeout.

The integration establishes a baseline during the startup grace period, then sends grouped offline and recovery messages. It uses the existing Telegram Bot service and does not store a bot token.

## Manual installation

Copy `custom_components/zigbee_pulse` into the `custom_components` directory in your Home Assistant configuration, restart Home Assistant, and add **Zigbee Pulse** from **Settings → Devices & services**.
