"""Top-level Nodalia runtime."""

from __future__ import annotations

from homeassistant.core import HomeAssistant

from .capabilities import NodaliaCapabilities
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
        self.capabilities = NodaliaCapabilities(hass, self.storage, self.notifications)
        self.legacy_fallback = LegacyNotificationFallback(hass)
        self.started = False

    async def async_start(self) -> None:
        await self.storage.async_load()
        await self.notifications.async_start()
        await self.climate.async_start()
        await self.legacy_fallback.async_suppress()
        self.started = True
        self.notifications._queue_forecast_refresh()

    async def async_stop(self) -> None:
        self.started = False
        await self.notifications.async_stop()
        await self.climate.async_stop()
        await self.legacy_fallback.async_restore()

    def diagnostics(self) -> dict:
        return {
            "started": self.started,
            "legacy_fallback_suppressed": self.legacy_fallback.suppressed,
            "notifications": self.notifications.diagnostics(),
            "climate": self.climate.diagnostics(),
        }
