"""A diagnostic button for sending a test message."""
from homeassistant.components.button import ButtonEntity
from homeassistant.const import EntityCategory


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([TestNotificationButton(entry)])


class TestNotificationButton(ButtonEntity):
    _attr_should_poll = False
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:message-check"

    def __init__(self, entry):
        self._coordinator = entry.runtime_data
        self._attr_unique_id = f"{entry.entry_id}_test"
        self._attr_name = f"{entry.title} test notification"

    async def async_press(self):
        await self._coordinator.send(
            f"Test notification: {self._coordinator.settings['name']}",
            self._coordinator.settings["recipient"],
        )
