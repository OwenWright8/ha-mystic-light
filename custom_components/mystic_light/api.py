"""Client for the Mystic Light bridge running on the Windows PC."""

from __future__ import annotations

import asyncio
from typing import Any
from urllib.parse import quote

import aiohttp


class MysticLightError(Exception):
    """Bridge unreachable or returned an error."""


class MysticLightAuthError(MysticLightError):
    """Bridge rejected the token."""


class MysticLightApi:
    """Talks to the bridge's small JSON API."""

    def __init__(self, session: aiohttp.ClientSession, host: str, port: int, token: str) -> None:
        self._session = session
        self._base = f"http://{host}:{port}"
        self._headers = {"Authorization": f"Bearer {token}"} if token else {}

    async def _request(self, method: str, path: str, json: dict | None = None) -> Any:
        try:
            async with self._session.request(
                method,
                f"{self._base}{path}",
                json=json,
                headers=self._headers,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                data = await resp.json(content_type=None)
                if resp.status == 401:
                    raise MysticLightAuthError("Invalid token")
                if resp.status != 200:
                    raise MysticLightError(data.get("error", f"HTTP {resp.status}"))
                return data
        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as err:
            raise MysticLightError(f"Cannot reach bridge: {err}") from err

    async def get_leds(self) -> list[dict[str, Any]]:
        """Return every LED area the SDK reports."""
        return await self._request("GET", "/api/leds")

    async def set_led(self, led_type: str, index: int, payload: dict[str, Any]) -> dict[str, Any]:
        """Change style and/or colour of one LED area; returns its new state."""
        return await self._request("POST", f"/api/leds/{quote(led_type, safe='')}/{index}", payload)
