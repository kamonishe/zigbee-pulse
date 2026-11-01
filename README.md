# Zigbee Pulse

Zigbee Pulse is a Home Assistant custom integration for Zigbee2MQTT device health notifications through the built-in Telegram Bot integration. It discovers Zigbee2MQTT `last_seen` sensors, monitors device availability, and provides a sidebar dashboard for per-device notification rules and Telegram message templates.

## Installation with HACS

The GitHub repository must be public because HACS cannot use private repositories. After the repository is public:

1. Open **HACS** in Home Assistant.
2. Open the three-dot menu and choose **Custom repositories**.
3. Enter `https://github.com/kamonishe/zigbee-pulse`.
4. Select **Integration** as the repository type and choose **Add**.
5. Open **Zigbee Pulse** in HACS and choose **Download**.
6. Restart Home Assistant.
7. Go to **Settings → Devices & services → Add integration**, search for **Zigbee Pulse**, and complete the setup.

HACS installs the integration under Home Assistant’s `custom_components/zigbee_pulse/` directory.

## Configuration

Zigbee Pulse requires the Home Assistant **MQTT** and **Telegram Bot** integrations. During setup, select the Telegram notify entity that should receive alerts. The integration discovers enabled Zigbee2MQTT `last_seen` sensors whenever the device picker opens, so newly paired devices can be added without editing YAML.

The sidebar dashboard provides global timeouts, per-device monitoring and notification rules, Telegram message templates with live previews, and a sidebar visibility toggle. A device timeout of `0` inherits the effective global timeout.

The integration establishes a baseline during the startup grace period, then sends grouped offline and recovery messages. It uses the existing Telegram Bot service and does not store a bot token.

## Manual installation

Copy `custom_components/zigbee_pulse` into the `custom_components` directory in your Home Assistant configuration, restart Home Assistant, and add **Zigbee Pulse** from **Settings → Devices & services**.

