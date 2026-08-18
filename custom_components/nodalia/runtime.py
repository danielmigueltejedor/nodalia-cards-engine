"""Top-level Nodalia runtime."""

from __future__ import annotations

from homeassistant.core import HomeAssistant

from .climate import NodaliaClimateManager
from .legacy_fallback import LegacyNotificationFallback
from .notifications import NodaliaNotificationManager
from .storage import NodaliaStorage


class NodaliaRuntime:
    """Coordinate storage and optional card capabilities."""

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass
        self.storage = NodaliaStorage(hass)
        self.notifications = NodaliaNotificationManager(hass, self.storage)
        self.climate = NodaliaClimateManager(hass, self.storage)
        self.legacy_fallback = LegacyNotificationFallback(hass)
        self.started = False

    async def async_start(self) -> None:
        await self.storage.async_load()
        await self.notifications.async_start()
        await self.climate.async_start()
        self.started = True
        await self.legacy_fallback.async_suppress()

    async def async_stop(self) -> None:
        self.started = False
        await self.climate.async_stop()
        await self.notifications.async_stop()
        await self.legacy_fallback.async_restore()

    def diagnostics(self) -> dict:
        return {
            "started": self.started,
            "legacy_fallback_suppressed": self.legacy_fallback.suppressed,
            "notifications": self.notifications.diagnostics(),
            "climate": self.climate.diagnostics(),
        }
