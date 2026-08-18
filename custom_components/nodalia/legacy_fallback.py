"""Coordinate the legacy YAML notification package with the native Engine."""

from __future__ import annotations

import logging
from typing import Any

_LOGGER = logging.getLogger(__name__)

LEGACY_BACKGROUND_MOBILE_TOGGLE = (
    "input_boolean.nodalia_background_mobile_notifications"
)


class LegacyNotificationFallback:
    """Pause the legacy package while Engine owns background delivery."""

    def __init__(self, hass: Any) -> None:
        self.hass = hass
        self._restore_on_stop = False

    @property
    def suppressed(self) -> bool:
        """Return whether this runtime paused an active legacy package."""
        return self._restore_on_stop

    async def async_suppress(self) -> bool:
        """Pause an installed legacy package and remember that Engine did it."""
        state = self.hass.states.get(LEGACY_BACKGROUND_MOBILE_TOGGLE)
        if state is None or str(state.state).lower() != "on":
            return False
        if not self.hass.services.has_service("input_boolean", "turn_off"):
            return False
        try:
            await self.hass.services.async_call(
                "input_boolean",
                "turn_off",
                {"entity_id": LEGACY_BACKGROUND_MOBILE_TOGGLE},
                blocking=True,
            )
        except Exception as err:  # noqa: BLE001 - HA services expose mixed failures
            _LOGGER.warning("Nodalia could not pause the legacy notification package: %s", err)
            return False
        self._restore_on_stop = True
        return True

    async def async_restore(self) -> bool:
        """Reactivate the legacy package only when this runtime paused it."""
        if not self._restore_on_stop:
            return False
        state = self.hass.states.get(LEGACY_BACKGROUND_MOBILE_TOGGLE)
        if state is None:
            self._restore_on_stop = False
            return False
        if str(state.state).lower() == "on":
            self._restore_on_stop = False
            return True
        if not self.hass.services.has_service("input_boolean", "turn_on"):
            return False
        try:
            await self.hass.services.async_call(
                "input_boolean",
                "turn_on",
                {"entity_id": LEGACY_BACKGROUND_MOBILE_TOGGLE},
                blocking=True,
            )
        except Exception as err:  # noqa: BLE001 - HA services expose mixed failures
            _LOGGER.warning("Nodalia could not reactivate the legacy notification package: %s", err)
            return False
        self._restore_on_stop = False
        return True
