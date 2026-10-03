"""Optional v3 operations: previews and bounded persistent user state, no device execution."""
from __future__ import annotations

import asyncio
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
import math
from typing import Any
from zoneinfo import ZoneInfo

from .climate_engine import effective_slot, next_timer_at, normalize_schedule, parse_until
from .notification_engine import evaluate_transition, normalize_profile, watched_entities, delivery_allowed, is_within_quiet_hours, passes_presence_context


class RevisionConflict(ValueError):
    """The client tried to overwrite a newer saved selection."""


def normalize_session(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict) or len(json.dumps(raw, allow_nan=False).encode()) > 16384:
        raise ValueError("Session must be an object under 16 KiB")
    mode = raw.get("activeMode", "rooms")
    if mode not in {"rooms", "zone", "goto", "smart", "routines"}:
        raise ValueError("Invalid cleaning mode")
    repeats = raw.get("repeats", 1)
    if isinstance(repeats, bool) or not isinstance(repeats, int) or not 1 <= repeats <= 10:
        raise ValueError("Repeats must be an integer from 1 to 10")
    result = {"activeMode": mode, "repeats": repeats}
    for key in ("selectedRoomIds", "selectedPredefinedZoneIds"):
        values = raw.get(key, [])
        if not isinstance(values, list) or len(values) > 100 or any(not isinstance(value, str) or not value or len(value) > 128 for value in values):
            raise ValueError("Invalid selection ids")
        result[key] = list(dict.fromkeys(values))
    zones = raw.get("manualZones", [])
    if not isinstance(zones, list) or len(zones) > 32:
        raise ValueError("At most 32 manual zones are supported")
    result["manualZones"] = []
    for zone in zones:
        if not isinstance(zone, dict) or any(isinstance(zone.get(key), bool) or not isinstance(zone.get(key), (int, float)) or not math.isfinite(zone[key]) or abs(zone[key]) > 10000000 for key in ("x1", "y1", "x2", "y2")):
            raise ValueError("Zone coordinates must be finite numbers")
        if zone["x2"] <= zone["x1"] or zone["y2"] <= zone["y1"]:
            raise ValueError("Zone rectangle must have positive dimensions")
        result["manualZones"].append({key: zone[key] for key in ("x1", "y1", "x2", "y2")})
    return result


class NodaliaCapabilities:
    """Compose existing engines; previews never save or send anything."""

    def __init__(self, hass, storage, notifications) -> None:
        self.hass = hass
        self.storage = storage
        self.notifications = notifications
        self._session_lock = asyncio.Lock()

    def preview_notifications(self, raw: Any, profile_id: str = "default") -> dict[str, Any]:
        if not isinstance(raw, dict):
            raise ValueError("Profile must be an object")
        profile = normalize_profile({**raw, "template_version": 3})
        alerts, missing = [], []
        entities = watched_entities(profile)
        if len(entities) > 512:
            raise ValueError("At most 512 watched entities are supported")
        now = datetime.now(ZoneInfo(self.hass.config.time_zone))
        presence_id = profile.get("context", {}).get("presence_entity", "")
        presence = self.hass.states.get(presence_id) if presence_id else None
        for entity_id in sorted(entities):
            state = self.hass.states.get(entity_id)
            if state is None:
                missing.append(entity_id)
                continue
            for alert in evaluate_transition(profile, entity_id, None, state.state, state.attributes, template_values=self.notifications._template_values(profile, entity_id), language=profile.get("language") or getattr(self.hass.config, "language", "en")):
                reason = ""
                if not delivery_allowed(profile, alert):
                    reason = "delivery_policy"
                elif is_within_quiet_hours(profile, now) and not (alert.get("severity") == "critical" and profile.get("context", {}).get("quiet_hours", {}).get("allow_critical") is True):
                    reason = "quiet_hours"
                elif presence_id and not passes_presence_context(profile, getattr(presence, "state", None)):
                    reason = "presence"
                elif alert["id"] in self.notifications.dismissed(profile_id):
                    reason = "dismissed"
                elif self.notifications.is_snoozed(profile_id, alert["id"]):
                    reason = "snoozed"
                alerts.append({**alert, "blocked_reason": reason, "delivery_eligible": not reason})
        return {"profile_id": profile_id, "profile": profile, "alerts": alerts[:512], "missing_entities": missing, "dry_run": True}

    async def snooze(self, profile_id: str, alert_id: str, until: str) -> dict[str, Any]:
        profile_id = self.notifications._normalize_profile_id(profile_id)
        if self.notifications.get_profile(profile_id) is None or not alert_id.strip() or len(alert_id) > 240:
            raise ValueError("An existing profile and alert id are required")
        expiry = parse_until(until)
        now = datetime.now(timezone.utc)
        if expiry is None or expiry.tzinfo is None or not now < expiry <= now + timedelta(days=7):
            raise ValueError("Snooze expiry must be timezone-aware, future and within seven days")
        root = self.storage.get("notification_runtime", "snoozed", {})
        root = root if isinstance(root, dict) else {}
        rows = root.get(profile_id, {})
        rows = {key: value for key, value in rows.items() if isinstance(value, (int, float)) and value > now.timestamp()} if isinstance(rows, dict) else {}
        if alert_id not in rows and len(rows) >= 250:
            raise ValueError("At most 250 active snoozes per profile are supported")
        rows[alert_id] = expiry.timestamp()
        root[profile_id] = rows
        await self.storage.async_set("notification_runtime", "snoozed", root)
        return {"profile_id": profile_id, "alert_id": alert_id, "until": expiry.isoformat()}

    def preview_climate(self, entity_id: str, raw: Any, at: str) -> dict[str, Any]:
        if not entity_id.startswith("climate.") or self.hass.states.get(entity_id) is None or not isinstance(raw, dict):
            raise ValueError("An existing climate entity and schedule are required")
        when = parse_until(at)
        if when is None or when.tzinfo is None:
            raise ValueError("Preview time must include a timezone")
        when = when.astimezone(ZoneInfo(self.hass.config.time_zone))
        schedule = normalize_schedule(entity_id, raw)
        boundary = next_timer_at(schedule, when)
        return {"entity_id": entity_id, "at": when.isoformat(), "time_zone": self.hass.config.time_zone, "schedule": schedule, "effective_slot": effective_slot(schedule, when), "next_change": boundary.isoformat() if boundary else None, "dry_run": True, "ignored_slots": max(0, len(raw.get("slots", [])) - len(schedule["slots"])) if isinstance(raw.get("slots"), list) else 0}

    def get_session(self, user_id: str, entity_id: str) -> dict[str, Any]:
        if not user_id or not entity_id.startswith("vacuum.") or self.hass.states.get(entity_id) is None:
            raise ValueError("An existing vacuum entity and authenticated user are required")
        row = self.storage.get("vacuum_sessions", f"{user_id}:{entity_id}", {})
        row = row if isinstance(row, dict) else {}
        return {"entity_id": entity_id, "revision": row.get("revision", 0), "session": deepcopy(row.get("session"))}

    async def set_session(self, user_id: str, entity_id: str, raw: Any, expected_revision: int) -> dict[str, Any]:
        session = normalize_session(raw)
        if isinstance(expected_revision, bool) or not isinstance(expected_revision, int) or expected_revision < 0:
            raise ValueError("Expected revision must be a nonnegative integer")
        async with self._session_lock:
            current = self.get_session(user_id, entity_id)
            if current["revision"] != expected_revision:
                raise RevisionConflict("Session changed; reload before saving")
            key = f"{user_id}:{entity_id}"
            rows = self.storage.get_section("vacuum_sessions")
            if key not in rows and len(rows) >= 128:
                raise ValueError("At most 128 saved vacuum sessions are supported")
            result = {"entity_id": entity_id, "revision": expected_revision + 1, "session": session}
            await self.storage.async_set("vacuum_sessions", key, result)
            return deepcopy(result)
