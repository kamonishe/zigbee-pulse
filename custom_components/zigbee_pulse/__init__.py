"""Zigbee2MQTT health notifications and sidebar dashboard."""
from pathlib import Path
from time import monotonic

from homeassistant.components import frontend, panel_custom
from homeassistant.const import Platform
from homeassistant.core import callback
from homeassistant.helpers.start import async_at_started
from homeassistant.components.http import StaticPathConfig

from .const import DEFAULTS, DOMAIN
from .coordinator import HealthCoordinator
from .websocket import async_register as async_register_websocket

PLATFORMS = [Platform.SENSOR, Platform.BUTTON]
PANEL_PATH = f"/{DOMAIN}_panel"


def _settings(entry):
    return DEFAULTS | dict(entry.data) | dict(entry.options)


async def _sync_sidebar(hass):
    """Show the sidebar panel when at least one entry enables it."""
    show_sidebar = any(
        _settings(entry).get("show_sidebar", True)
        for entry in hass.config_entries.async_entries(DOMAIN)
    )
    if not show_sidebar:
        frontend.async_remove_panel(hass, DOMAIN, warn_if_unknown=False)
        return
    if frontend.async_panel_exists(hass, DOMAIN):
        return
    await panel_custom.async_register_panel(
        hass,
        webcomponent_name="zigbee-pulse-panel",
        frontend_url_path=DOMAIN,
        sidebar_title="Zigbee Pulse",
        sidebar_icon="mdi:zigbee",
        module_url=f"{PANEL_PATH}/zigbee-pulse-panel.js",
        embed_iframe=False,
        require_admin=True,
        config_panel_domain=DOMAIN,
    )


async def async_setup(hass, config):
    """Register static panel assets and the authenticated API."""
    await hass.http.async_register_static_paths([
        StaticPathConfig(PANEL_PATH, str(Path(__file__).parent / "frontend"), cache_headers=False)
    ])
    async_register_websocket(hass)
    return True


async def async_setup_entry(hass, entry):
    await _sync_sidebar(hass)
    coordinator = HealthCoordinator(hass, entry)
    entry.runtime_data = coordinator

    @callback
    def started(_hass):
        coordinator.started_at = monotonic()

    if not hass.is_running:
        entry.async_on_unload(async_at_started(hass, started))
    await coordinator.async_config_entry_first_refresh()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    return True


async def async_reload_entry(hass, entry):
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass, entry):
    result = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    await _sync_sidebar(hass)
    return result
