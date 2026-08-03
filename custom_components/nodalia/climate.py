"""Native climate schedule runtime for Nodalia."""

from __future__ import annotations

import logging
from collections.abc import Callable
from copy import deepcopy
from typing import Any

from homeassistant.core import Event, HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.event import async_track_point_in_time, async_track_state_change_event
from homeassistant.helpers.start import async_at_started
from homeassistant.util import dt as dt_util

from .climate_engine import active_slot, next_slot_start, normalize_schedule
from .const import MAX_CLIMATE_SCHEDULES, MAX_CLIMATE_SLOTS
from .storage import NodaliaStorage

_LOGGER = logging.getLogger(__name__)


class NodaliaClimateManager:
    """Store and execute weekly schedules without helpers or automations."""

    def __init__(self, hass: HomeAssistant, storage: NodaliaStorage) -> None:
        self.hass = hass
        self.storage = storage
        self._schedules: dict[str, dict[str, Any]] = {}
        self._unsub_timer: Callable[[], None] | None = None
        self._unsub_start: Callable[[], None] | None = None
        self._unsub_state_listener: Callable[[], None] | None = None
        self._started = False

    async def async_start(self) -> None:
        raw_schedules = self.storage.get_section("climate_schedules")
        self._schedules = {
            entity_id: normalize_schedule(entity_id, value, MAX_CLIMATE_SLOTS)
            for entity_id, value in raw_schedules.items()
            if str(entity_id).startswith("climate.")
        }
        self._unsub_start = async_at_started(self.hass, self._async_home_assistant_started)
        self._rebuild_state_listener()

    async def _async_home_assistant_started(self, _hass: HomeAssistant) -> None:
        self._started = True
        await self._async_apply_all()
        self._reschedule()

    async def async_stop(self) -> None:
        if self._unsub_timer is not None:
            self._unsub_timer()
            self._unsub_timer = None
        if self._unsub_start is not None:
            self._unsub_start()
            self._unsub_start = None
        if self._unsub_state_listener is not None:
            self._unsub_state_listener()
            self._unsub_state_listener = None
        self._started = False

    def schedule_ids(self) -> list[str]:
        return sorted(self._schedules)

    def get_schedule(self, entity_id: str) -> dict[str, Any] | None:
        schedule = self._schedules.get(str(entity_id or "").strip())
        return deepcopy(schedule) if schedule is not None else None

    async def async_set_schedule(self, entity_id: str, raw_schedule: Any) -> dict[str, Any]:
        entity = str(entity_id or "").strip()
        if not entity.startswith("climate."):
            raise ValueError("A climate entity_id is required")
        if entity not in self._schedules and len(self._schedules) >= MAX_CLIMATE_SCHEDULES:
            raise ValueError(f"At most {MAX_CLIMATE_SCHEDULES} climate schedules are supported")
        schedule = normalize_schedule(entity, raw_schedule, MAX_CLIMATE_SLOTS)
        self._schedules[entity] = schedule
        await self.storage.async_set("climate_schedules", entity, schedule)
        self._rebuild_state_listener()
        if self._started:
            await self._async_apply_schedule(schedule)
            self._reschedule()
        return deepcopy(schedule)

    async def async_delete_schedule(self, entity_id: str) -> bool:
        entity = str(entity_id or "").strip()
        if entity not in self._schedules:
            return False
        del self._schedules[entity]
        deleted = await self.storage.async_delete("climate_schedules", entity)
        self._rebuild_state_listener()
        self._reschedule()
        return deleted

    async def async_apply_schedule(self, entity_id: str) -> bool:
        """Apply the active slot now, primarily for testing and recovery."""
        entity = str(entity_id or "").strip()
        schedule = self._schedules.get(entity)
        if schedule is None:
            raise ValueError("Climate schedule not found")
        return await self._async_apply_schedule(schedule)

    def diagnostics(self) -> dict[str, Any]:
        now = dt_util.now()
        next_starts = {
            entity_id: next_slot_start(schedule, now)
            for entity_id, schedule in self._schedules.items()
        }
        return {
            "schedule_count": len(self._schedules),
            "schedules": {
                entity_id: {
                    "enabled": schedule.get("enabled") is not False,
                    "slot_count": len(schedule.get("slots", [])),
                    "active_slot": (active_slot(schedule, now) or {}).get("id"),
                    "next_start": next_starts[entity_id].isoformat()
                    if next_starts[entity_id] is not None
                    else None,
                }
                for entity_id, schedule in self._schedules.items()
            },
        }

    async def _async_apply_all(self) -> None:
        for schedule in tuple(self._schedules.values()):
            await self._async_apply_schedule(schedule)

    async def _async_apply_schedule(self, schedule: dict[str, Any]) -> bool:
        slot = active_slot(schedule, dt_util.now())
        if slot is None:
            return False
        entity_id = str(schedule.get("entity_id") or "")
        state = self.hass.states.get(entity_id)
        if state is None or str(state.state).lower() in {"unavailable", "unknown"}:
            return False
        try:
            hvac_mode = str(slot.get("hvac_mode") or "").strip()
            if hvac_mode and str(state.state) != hvac_mode:
                await self.hass.services.async_call(
                    "climate",
                    "set_hvac_mode",
                    {"hvac_mode": hvac_mode},
                    blocking=True,
                    target={"entity_id": [entity_id]},
                )
            if hvac_mode != "off":
                temperature_data = self._temperature_service_data(slot)
                if temperature_data and not self._temperature_matches(state.attributes, temperature_data):
                    await self.hass.services.async_call(
                        "climate",
                        "set_temperature",
                        temperature_data,
                        blocking=True,
                        target={"entity_id": [entity_id]},
                    )
            for attribute, service, field in (
                ("preset_mode", "set_preset_mode", "preset_mode"),
                ("fan_mode", "set_fan_mode", "fan_mode"),
            ):
                value = str(slot.get(attribute) or "").strip()
                if value and str(state.attributes.get(attribute) or "") != value:
                    await self.hass.services.async_call(
                        "climate",
                        service,
                        {field: value},
                        blocking=True,
                        target={"entity_id": [entity_id]},
                    )
            return True
        except HomeAssistantError as err:
            _LOGGER.warning("Nodalia could not apply climate schedule to %s: %s", entity_id, err)
            return False

    @staticmethod
    def _temperature_service_data(slot: dict[str, Any]) -> dict[str, float]:
        if "target_temp_low" in slot and "target_temp_high" in slot:
            return {
                "target_temp_low": float(slot["target_temp_low"]),
                "target_temp_high": float(slot["target_temp_high"]),
            }
        return {"temperature": float(slot["temperature"])} if "temperature" in slot else {}

    @staticmethod
    def _temperature_matches(attributes: dict[str, Any], expected: dict[str, float]) -> bool:
        try:
            return all(
                attributes.get(key) is not None
                and abs(float(attributes[key]) - value) < 0.01
                for key, value in expected.items()
            )
        except (TypeError, ValueError):
            return False

    def _rebuild_state_listener(self) -> None:
        if self._unsub_state_listener is not None:
            self._unsub_state_listener()
            self._unsub_state_listener = None
        if self._schedules:
            self._unsub_state_listener = async_track_state_change_event(
                self.hass,
                sorted(self._schedules),
                self._async_climate_state_changed,
            )

    async def _async_climate_state_changed(self, event: Event) -> None:
        """Apply a schedule when its thermostat becomes available after startup."""
        entity_id = str(event.data.get("entity_id") or "")
        schedule = self._schedules.get(entity_id)
        if schedule is None or not self._started:
            return
        old_state = event.data.get("old_state")
        new_state = event.data.get("new_state")
        old_value = str(getattr(old_state, "state", "unavailable") or "unavailable").lower()
        new_value = str(getattr(new_state, "state", "unavailable") or "unavailable").lower()
        if old_value in {"unknown", "unavailable"} and new_value not in {"unknown", "unavailable"}:
            await self._async_apply_schedule(schedule)

    def _reschedule(self) -> None:
        if self._unsub_timer is not None:
            self._unsub_timer()
            self._unsub_timer = None
        if not self._started:
            return
        now = dt_util.now()
        candidates = [
            candidate
            for schedule in self._schedules.values()
            if (candidate := next_slot_start(schedule, now)) is not None
        ]
        if not candidates:
            return
        self._unsub_timer = async_track_point_in_time(
            self.hass,
            self._async_schedule_boundary,
            min(candidates),
        )

    async def _async_schedule_boundary(self, _now) -> None:
        self._unsub_timer = None
        await self._async_apply_all()
        self._reschedule()
