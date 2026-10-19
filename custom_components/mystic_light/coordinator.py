"""Polling coordinator for the Mystic Light bridge."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import MysticLightApi, MysticLightAuthError, MysticLightError
from .const import DOMAIN, SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)


class MysticLightCoordinator(DataUpdateCoordinator[dict[str, dict[str, Any]]]):
    """Keeps LED state keyed by LED id (e.g. ``MSI_MB_0``)."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, api: MysticLightApi) -> None:
        super().__init__(
            hass, _LOGGER, config_entry=entry, name=DOMAIN, update_interval=SCAN_INTERVAL
        )
        self.api = api

    async def _async_update_data(self) -> dict[str, dict[str, Any]]:
        try:
            leds = await self.api.get_leds()
        except MysticLightAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except MysticLightError as err:
            raise UpdateFailed(str(err)) from err
        return {led["id"]: led for led in leds}
