"""MSI Mystic Light integration: controls PC RGB through a bridge on the Windows host."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_TOKEN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import MysticLightApi
from .coordinator import MysticLightCoordinator

PLATFORMS = [Platform.LIGHT]

type MysticLightConfigEntry = ConfigEntry[MysticLightCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: MysticLightConfigEntry) -> bool:
    api = MysticLightApi(
        async_get_clientsession(hass),
        entry.data[CONF_HOST],
        entry.data[CONF_PORT],
        entry.data.get(CONF_TOKEN, ""),
    )
    coordinator = MysticLightCoordinator(hass, entry, api)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: MysticLightConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
