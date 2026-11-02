"""Config flow with a dynamically discovered per-device editor."""
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er, selector

from .const import DEVICE_DEFAULTS, DOMAIN, merged_settings
from .coordinator import is_last_seen
from .rules import timeout_minutes_for


def _device_choices(hass):
    registry = er.async_get(hass)
    device_registry = dr.async_get(hass)
    choices = []
    for entity in registry.entities.values():
        if not is_last_seen(entity):
            continue
        device = device_registry.async_get(entity.device_id) if entity.device_id else None
        name = ((device.name_by_user or device.name) if device else None) or entity.entity_id
        choices.append({"value": entity.entity_id, "label": f"{name} ({entity.entity_id})"})
    return sorted(choices, key=lambda item: item["label"].lower())


def _telegram_selector():
    return selector.EntitySelector(selector.EntitySelectorConfig(
        integration="telegram_bot", domain="notify"))


def _global_schema(values):
    values = merged_settings(values)
    minutes = vol.All(vol.Coerce(int), vol.Range(min=1, max=10080))
    return vol.Schema({
        vol.Required("name", default=values["name"]): selector.TextSelector(),
        vol.Required("recipient", default=values["recipient"]): _telegram_selector(),
        vol.Required("mains_timeout", default=values["mains_timeout"]): minutes,
        vol.Required("battery_timeout", default=values["battery_timeout"]): minutes,
        vol.Required("startup_grace", default=values["startup_grace"]): vol.All(
            vol.Coerce(int), vol.Range(min=0, max=120)),
        vol.Required("enabled", default=values["enabled"]): selector.BooleanSelector(),
        vol.Required("show_sidebar", default=values["show_sidebar"]): selector.BooleanSelector(),
    })


def _device_timeout(hass, entity_id, settings):
    """Return the effective global timeout shown for an inherited rule."""
    registry = er.async_get(hass)
    battery_devices = set()
    for entity in registry.entities.values():
        state = hass.states.get(entity.entity_id)
        if entity.device_id and (
            entity.device_class == "battery"
            or entity.original_device_class == "battery"
            or entity.entity_id.endswith("_battery")
            or (state and state.attributes.get("device_class") == "battery")
        ):
            battery_devices.add(entity.device_id)
    entity = registry.async_get(entity_id)
    has_battery = bool(entity and entity.device_id in battery_devices)
    return timeout_minutes_for(entity_id, has_battery, settings)


def _device_schema(rule, recipient, inherited_timeout):
    rule = DEVICE_DEFAULTS | {"recipient": recipient} | rule
    timeout = rule["timeout"] or inherited_timeout
    return vol.Schema({
        vol.Required("enabled", default=rule["enabled"]): selector.BooleanSelector(),
        vol.Required("offline", default=rule["offline"]): selector.BooleanSelector(),
        vol.Required("recovery", default=rule["recovery"]): selector.BooleanSelector(),
        vol.Required("timeout", default=timeout): vol.All(
            vol.Coerce(int), vol.Range(min=0, max=10080)),
        vol.Required("recipient", default=rule["recipient"]): _telegram_selector(),
    })


def _validate_global(hass, data):
    if not data["name"].strip():
        return {"base": "invalid_name"}
    entity = er.async_get(hass).async_get(data["recipient"])
    if entity is None or entity.platform != "telegram_bot" or entity.domain != "notify" or entity.disabled_by:
        return {"base": "invalid_recipient"}
    return {}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            errors = _validate_global(self.hass, user_input)
            if not errors:
                await self.async_set_unique_id(user_input["recipient"])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=user_input["name"], data=user_input)
        return self.async_show_form(step_id="user", data_schema=_global_schema(user_input or {}), errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return OptionsFlow()


class OptionsFlow(config_entries.OptionsFlow):
    def _values(self):
        return merged_settings(self.config_entry.data, self.config_entry.options)

    def _save(self, values):
        self.hass.config_entries.async_update_entry(self.config_entry, title=values["name"])
        return self.async_create_entry(title="", data=values)

    async def async_step_init(self, user_input=None):
        return self.async_show_menu(step_id="init", menu_options=["settings", "devices"])

    async def async_step_settings(self, user_input=None):
        values = self._values()
        if user_input is not None:
            errors = _validate_global(self.hass, user_input)
            if not errors:
                return self._save(values | user_input)
        else:
            errors = {}
        return self.async_show_form(step_id="settings", data_schema=_global_schema(user_input or values), errors=errors)

    async def async_step_devices(self, user_input=None):
        # This is deliberately rebuilt on every visit, so newly paired devices appear.
        choices = _device_choices(self.hass)
        if not choices:
            return self.async_abort(reason="no_devices")
        if user_input is not None:
            self._selected_entity = user_input["entity_id"]
            return await self.async_step_device()
        return self.async_show_form(step_id="devices", data_schema=vol.Schema({
            vol.Required("entity_id"): selector.SelectSelector(selector.SelectSelectorConfig(
                options=choices, mode="dropdown")),
        }), description_placeholders={"count": str(len(choices))})

    async def async_step_device(self, user_input=None):
        values = self._values()
        entity_id = self._selected_entity
        rules = dict(values.get("device_rules", {}))
        if user_input is not None:
            inherited_timeout = _device_timeout(self.hass, entity_id, values)
            if (rules.get(entity_id, {}).get("timeout", 0) == 0
                    and user_input["timeout"] == inherited_timeout):
                user_input = user_input | {"timeout": 0}
            rules[entity_id] = user_input
            return self._save(values | {"device_rules": rules})
        inherited_timeout = _device_timeout(self.hass, entity_id, values)
        return self.async_show_form(
            step_id="device", data_schema=_device_schema(
                rules.get(entity_id, {}), values["recipient"], inherited_timeout),
            description_placeholders={
                "entity_id": entity_id,
                "global_timeout": str(inherited_timeout),
            },
        )
