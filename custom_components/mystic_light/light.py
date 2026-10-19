"""Light entities for each Mystic Light LED area (fan headers, onboard zones...)."""

from __future__ import annotations

from typing import Any

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_EFFECT,
    ATTR_RGB_COLOR,
    ColorMode,
    LightEntity,
    LightEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import MysticLightConfigEntry
from .api import MysticLightError
from .const import CONF_MAX_POWER, DEFAULT_MAX_POWER, DOMAIN, SOLID_STYLES
from .coordinator import MysticLightCoordinator

OFF = "off"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MysticLightConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(MysticLight(coordinator, led_id) for led_id in coordinator.data)


class MysticLight(CoordinatorEntity[MysticLightCoordinator], LightEntity):
    """One LED area. Brightness is applied by scaling the RGB value."""

    _attr_has_entity_name = True
    _attr_color_mode = ColorMode.RGB
    _attr_supported_color_modes = {ColorMode.RGB}
    _attr_supported_features = LightEntityFeature.EFFECT

    def __init__(self, coordinator: MysticLightCoordinator, led_id: str) -> None:
        super().__init__(coordinator)
        self._led_id = led_id
        led = coordinator.data[led_id]
        entry_id = coordinator.config_entry.entry_id
        self._attr_unique_id = f"{entry_id}_{led_id}"
        self._attr_name = led["name"]
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry_id}_{led['type']}")},
            name=led["device_name"] or led["type"],
            manufacturer="MSI",
            model=led["type"],
        )
        self._last_rgb: tuple[int, int, int] = (255, 255, 255)
        self._last_brightness = 255
        # (rgb sent to the bridge, requested rgb, requested brightness): lets us report
        # what the user asked for even when the power cap dimmed the output.
        self._commanded: tuple[tuple[int, ...], tuple[int, ...], int] | None = None

    @property
    def _requested(self) -> tuple[tuple[int, ...], int] | None:
        """Requested colour/brightness if the LED still shows what we last sent."""
        if self._commanded and self._led and tuple(self._led["rgb"]) == self._commanded[0]:
            return self._commanded[1], self._commanded[2]
        return None

    def _apply_power_cap(self, rgb: list[int]) -> list[int]:
        """Scale down colours whose total draw exceeds the configured share of full white."""
        options = self.coordinator.config_entry.options
        limit = 765 * options.get(CONF_MAX_POWER, DEFAULT_MAX_POWER) / 100
        total = sum(rgb)
        if total <= limit:
            return rgb
        return [int(c * limit / total) for c in rgb]

    @property
    def _led(self) -> dict[str, Any] | None:
        return self.coordinator.data.get(self._led_id)

    @property
    def available(self) -> bool:
        return super().available and self._led is not None

    @property
    def _styles(self) -> list[str]:
        return list(self._led["styles"]) if self._led else []

    @property
    def is_on(self) -> bool:
        led = self._led
        return bool(led) and led["style"].lower() != OFF and any(led["rgb"])

    @property
    def brightness(self) -> int | None:
        if not self.is_on:
            return None
        requested = self._requested
        return requested[1] if requested else max(self._led["rgb"])

    @property
    def rgb_color(self) -> tuple[int, int, int] | None:
        if not self.is_on:
            return self._last_rgb
        requested = self._requested
        if requested:
            return requested[0]
        r, g, b = self._led["rgb"]
        peak = max(r, g, b)
        return (round(r * 255 / peak), round(g * 255 / peak), round(b * 255 / peak))

    @property
    def effect_list(self) -> list[str]:
        return [s for s in self._styles if s.lower() != OFF]

    @property
    def effect(self) -> str | None:
        return self._led["style"] if self.is_on else None

    def _solid_style(self) -> str | None:
        lower = {s.lower(): s for s in self._styles}
        return next((lower[s.lower()] for s in SOLID_STYLES if s.lower() in lower), None)

    async def async_turn_on(self, **kwargs: Any) -> None:
        led = self._led
        rgb = kwargs.get(ATTR_RGB_COLOR) or self.rgb_color or self._last_rgb
        brightness = kwargs.get(ATTR_BRIGHTNESS) or (self.brightness if self.is_on else self._last_brightness)
        output = self._apply_power_cap([round(c * brightness / 255) for c in rgb])
        payload: dict[str, Any] = {"rgb": output}
        if ATTR_EFFECT in kwargs:
            payload["style"] = kwargs[ATTR_EFFECT]
        else:
            solid = self._solid_style()
            if led["style"].lower() == OFF or led["style"] not in self.effect_list:
                payload["style"] = solid
            elif ATTR_RGB_COLOR in kwargs:
                # Picking a colour while on e.g. Rainbow switches to a solid style.
                payload["fallback_style"] = solid
        self._last_rgb, self._last_brightness = tuple(rgb), brightness
        self._commanded = (tuple(output), tuple(rgb), brightness)
        await self._send(payload)

    async def async_turn_off(self, **kwargs: Any) -> None:
        if self.is_on:
            self._last_rgb, self._last_brightness = self.rgb_color, self.brightness
        has_off = any(s.lower() == OFF for s in self._styles)
        payload = {"style": next(s for s in self._styles if s.lower() == OFF)} if has_off else {"rgb": [0, 0, 0]}
        await self._send(payload)

    async def _send(self, payload: dict[str, Any]) -> None:
        payload = {k: v for k, v in payload.items() if v is not None}
        led = self._led
        try:
            new_state = await self.coordinator.api.set_led(led["type"], led["index"], payload)
        except MysticLightError as err:
            raise HomeAssistantError(f"Mystic Light: {err}") from err
        # The bridge echoes the new state; keep the device-level name from the last poll.
        new_state["device_name"] = led["device_name"]
        self.coordinator.data[self._led_id] = new_state
        self.async_write_ha_state()
