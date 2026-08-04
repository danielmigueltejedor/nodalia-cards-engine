"""Persistent background notification runtime for Nodalia."""

from __future__ import annotations

import logging
import json
from collections.abc import Callable
from copy import deepcopy
from typing import Any

from homeassistant.core import Event, HomeAssistant
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.util import dt as dt_util

from .const import (
    DEFAULT_NOTIFICATION_PROFILE,
    MAX_NOTIFICATION_PROFILES,
    MAX_NOTIFICATION_WATCHED_ENTITIES,
)
from .notification_engine import (
    cooldown_identity,
    delivery_allowed,
    evaluate_transition,
    is_within_quiet_hours,
    normalize_profile,
    passes_presence_context,
    referenced_template_tokens,
    resolve_alert_url,
    watched_entities,
)
from .storage import NodaliaStorage

_LOGGER = logging.getLogger(__name__)


class NodaliaNotificationManager:
    """Own notification profiles and indexed Home Assistant listeners."""

    def __init__(self, hass: HomeAssistant, storage: NodaliaStorage) -> None:
        self.hass = hass
        self.storage = storage
        self._profiles: dict[str, dict[str, Any]] = {}
        self._profiles_by_entity: dict[str, set[str]] = {}
        self._unsub_state_listener: Callable[[], None] | None = None

    async def async_start(self) -> None:
        """Load profiles and start their shared indexed listener."""
        raw_profiles = self.storage.get_section("notifications")
        profiles: dict[str, dict[str, Any]] = {}
        watched: set[str] = set()
        for profile_id, value in raw_profiles.items():
            normalized_id = self._normalize_profile_id(profile_id)
            if not normalized_id or len(profiles) >= MAX_NOTIFICATION_PROFILES:
                continue
            profile = normalize_profile(value)
            candidate_watched = watched | watched_entities(profile)
            if len(candidate_watched) > MAX_NOTIFICATION_WATCHED_ENTITIES:
                _LOGGER.warning(
                    "Nodalia skipped notification profile %s because the combined entity limit is %s",
                    normalized_id,
                    MAX_NOTIFICATION_WATCHED_ENTITIES,
                )
                continue
            profiles[normalized_id] = profile
            watched = candidate_watched
        self._profiles = profiles
        self._rebuild_listener()

    async def async_stop(self) -> None:
        """Detach listeners and flush runtime state."""
        if self._unsub_state_listener is not None:
            self._unsub_state_listener()
            self._unsub_state_listener = None
        self._profiles_by_entity.clear()
        await self.storage.async_flush()

    def profile_ids(self) -> list[str]:
        return sorted(self._profiles)

    def get_profile(self, profile_id: str = DEFAULT_NOTIFICATION_PROFILE) -> dict[str, Any] | None:
        profile = self._profiles.get(self._normalize_profile_id(profile_id))
        return deepcopy(profile) if profile is not None else None

    async def async_set_profile(self, profile_id: str, raw_profile: Any) -> dict[str, Any]:
        """Validate, persist and activate one notification profile."""
        normalized_id = self._normalize_profile_id(profile_id)
        if not normalized_id:
            raise ValueError("Invalid profile id")
        if normalized_id not in self._profiles and len(self._profiles) >= MAX_NOTIFICATION_PROFILES:
            raise ValueError(f"At most {MAX_NOTIFICATION_PROFILES} notification profiles are supported")
        profile = normalize_profile(raw_profile)
        candidate_profiles = dict(self._profiles)
        candidate_profiles[normalized_id] = profile
        combined_watched = set().union(
            *(watched_entities(candidate) for candidate in candidate_profiles.values())
        )
        if len(combined_watched) > MAX_NOTIFICATION_WATCHED_ENTITIES:
            raise ValueError(
                f"Notification profiles watch {len(combined_watched)} entities; "
                f"combined maximum is {MAX_NOTIFICATION_WATCHED_ENTITIES}"
            )
        if self._profiles.get(normalized_id) == profile:
            return deepcopy(profile)
        self._profiles[normalized_id] = profile
        await self.storage.async_set("notifications", normalized_id, profile)
        self._rebuild_listener()
        return deepcopy(profile)

    async def async_delete_profile(self, profile_id: str) -> bool:
        normalized_id = self._normalize_profile_id(profile_id)
        if normalized_id not in self._profiles:
            return False
        del self._profiles[normalized_id]
        deleted = await self.storage.async_delete("notifications", normalized_id)
        self._rebuild_listener()
        return deleted

    async def async_dismiss(self, profile_id: str, alert_id: str) -> None:
        """Share dismissals between all dashboards without a helper entity."""
        profile = self._normalize_profile_id(profile_id)
        identity = str(alert_id or "").strip()[:240]
        if not profile or not identity:
            raise ValueError("Profile and alert id are required")
        dismissed_root = self.storage.get("notification_runtime", "dismissed", {})
        if not isinstance(dismissed_root, dict):
            dismissed_root = {}
        rows = dismissed_root.get(profile, [])
        normalized_rows = [str(value) for value in rows if str(value).strip()] if isinstance(rows, list) else []
        normalized_rows = [value for value in normalized_rows if value != identity]
        normalized_rows.append(identity)
        dismissed_root[profile] = normalized_rows[-250:]
        self.storage.set_delayed("notification_runtime", "dismissed", dismissed_root)

    def dismissed(self, profile_id: str) -> list[str]:
        root = self.storage.get("notification_runtime", "dismissed", {})
        rows = root.get(self._normalize_profile_id(profile_id), []) if isinstance(root, dict) else []
        return [str(value) for value in rows] if isinstance(rows, list) else []

    async def async_send_test(
        self,
        profile_id: str = DEFAULT_NOTIFICATION_PROFILE,
        title: str = "Nodalia",
        message: str = "Background notifications are ready.",
    ) -> int:
        profile = self._profiles.get(self._normalize_profile_id(profile_id))
        if profile is None:
            raise ValueError("Notification profile not found")
        return await self._async_send(
            profile,
            {
                "id": "test:nodalia",
                "kind": "test",
                "entity_id": "",
                "title": str(title or "Nodalia")[:160],
                "message": str(message or "Background notifications are ready.")[:2000],
                "severity": "info",
                "mobile": "push",
            },
        )

    async def async_send_external(self, profile_id: str, alert_id: str) -> int:
        """Deliver one administrator-configured external alert by id."""
        normalized_id = self._normalize_profile_id(profile_id)
        profile = self._profiles.get(normalized_id)
        if profile is None:
            raise ValueError("Notification profile not found")
        identity = str(alert_id or "").strip()
        configured = next(
            (
                row
                for row in profile.get("external_alerts", [])
                if isinstance(row, dict) and str(row.get("id") or "") == identity
            ),
            None,
        )
        if configured is None:
            raise ValueError("External alert not found in the notification profile")
        entity_id = str(configured.get("entity") or "")
        values = self._template_values(profile, entity_id)
        alert = {
            "id": f"external:{identity}",
            "kind": str(configured.get("type") or "external_alert"),
            "entity_id": entity_id,
            "title": self._render(configured.get("title"), values),
            "message": self._render(configured.get("message"), values),
            "severity": str(configured.get("severity") or "info"),
            "mobile": str(configured.get("mobile") or "auto"),
            "url": resolve_alert_url(configured),
            "action_label": str(configured.get("action_label") or ""),
        }
        return await self._async_deliver_if_allowed(normalized_id, profile, alert)

    def diagnostics(self) -> dict[str, Any]:
        return {
            "profile_count": len(self._profiles),
            "watched_entity_count": len(self._profiles_by_entity),
            "profiles": {
                profile_id: {
                    "enabled": profile.get("enabled") is True,
                    "watched_entity_count": len(watched_entities(profile)),
                    "target_count": len(profile.get("notify", {}).get("entities", []))
                    + len(profile.get("notify", {}).get("services", [])),
                }
                for profile_id, profile in self._profiles.items()
            },
        }

    def _normalize_profile_id(self, value: Any) -> str:
        raw = str(value or DEFAULT_NOTIFICATION_PROFILE).strip().lower()
        normalized = "".join(char if char.isalnum() or char in {"_", "-"} else "_" for char in raw)
        return normalized.strip("_")[:64]

    def _rebuild_listener(self) -> None:
        if self._unsub_state_listener is not None:
            self._unsub_state_listener()
            self._unsub_state_listener = None
        by_entity: dict[str, set[str]] = {}
        for profile_id, profile in self._profiles.items():
            for entity_id in watched_entities(profile):
                by_entity.setdefault(entity_id, set()).add(profile_id)
        self._profiles_by_entity = by_entity
        if by_entity:
            self._unsub_state_listener = async_track_state_change_event(
                self.hass,
                sorted(by_entity),
                self._async_state_changed,
            )

    async def _async_state_changed(self, event: Event) -> None:
        entity_id = str(event.data.get("entity_id") or "")
        if not entity_id:
            return
        new_state = event.data.get("new_state")
        old_state = event.data.get("old_state")
        for profile_id in tuple(self._profiles_by_entity.get(entity_id, ())):
            profile = self._profiles.get(profile_id)
            if profile is None:
                continue
            self._clear_dismissals_for_entity(profile_id, profile, entity_id)
            alerts = evaluate_transition(
                profile,
                entity_id,
                getattr(old_state, "state", None),
                getattr(new_state, "state", None),
                getattr(new_state, "attributes", None),
                getattr(old_state, "attributes", None),
                self._template_values(profile, entity_id),
                language=getattr(self.hass.config, "language", "en"),
            )
            for alert in alerts:
                await self._async_deliver_if_allowed(profile_id, profile, alert)

    def _clear_dismissals_for_entity(
        self,
        profile_id: str,
        profile: dict[str, Any],
        entity_id: str,
    ) -> None:
        """Expire a visual dismissal when its source entity changes again."""
        root = self.storage.get("notification_runtime", "dismissed", {})
        if not isinstance(root, dict):
            return
        current = root.get(profile_id, [])
        if not isinstance(current, list) or not current:
            return
        identities = {
            f"{kind}:{entity_id}"
            for kind in (
                "door",
                "window",
                "motion",
                "vacuum",
                "hot",
                "cold",
                "humidity_high",
                "humidity_low",
                "battery_low",
                "humidifier_fill_low",
                "humidifier_fill_full",
                "ink_low",
            )
        }
        for row in profile.get("custom", []):
            if isinstance(row, dict) and row.get("entity") == entity_id:
                identities.add(f"custom:{row.get('id')}")
        filtered = [
            value
            for value in current
            if str(value) not in identities
            and not any(str(value).startswith(identity + ":") for identity in identities)
        ]
        if len(filtered) == len(current):
            return
        root[profile_id] = filtered
        self.storage.set_delayed("notification_runtime", "dismissed", root)

    async def _async_deliver_if_allowed(
        self,
        profile_id: str,
        profile: dict[str, Any],
        alert: dict[str, Any],
    ) -> int:
        if not delivery_allowed(profile, alert):
            return 0
        now = dt_util.now()
        if is_within_quiet_hours(profile, now):
            quiet = profile.get("context", {}).get("quiet_hours", {})
            if alert.get("severity") != "critical" or quiet.get("allow_critical") is not True:
                return 0
        context = profile.get("context", {})
        presence_entity = str(context.get("presence_entity") or "")
        presence_state = self.hass.states.get(presence_entity) if presence_entity else None
        if presence_entity and not passes_presence_context(profile, getattr(presence_state, "state", None)):
            return 0
        if str(alert.get("id") or "") in self.dismissed(profile_id):
            return 0

        notify = profile.get("notify", {})
        identity = cooldown_identity(profile, alert)
        cooldown_seconds = float(notify.get("cooldown_minutes") or 0) * 60
        cooldown_root = self.storage.get("notification_runtime", "cooldowns", {})
        if not isinstance(cooldown_root, dict):
            cooldown_root = {}
        profile_cooldowns = cooldown_root.get(profile_id, {})
        if not isinstance(profile_cooldowns, dict):
            profile_cooldowns = {}
        now_timestamp = dt_util.utcnow().timestamp()
        last_timestamp = float(profile_cooldowns.get(identity) or 0)
        if cooldown_seconds > 0 and now_timestamp - last_timestamp < cooldown_seconds:
            return 0

        delivered = await self._async_send(profile, alert)
        if delivered:
            profile_cooldowns[identity] = now_timestamp
            cutoff = now_timestamp - max(cooldown_seconds * 4, 86400)
            profile_cooldowns = {
                key: timestamp
                for key, timestamp in profile_cooldowns.items()
                if float(timestamp or 0) >= cutoff
            }
            cooldown_root[profile_id] = profile_cooldowns
            self.storage.set_delayed("notification_runtime", "cooldowns", cooldown_root)
        return delivered

    async def _async_send(self, profile: dict[str, Any], alert: dict[str, Any]) -> int:
        notify = profile.get("notify", {})
        title = str(alert.get("title") or "Nodalia")[:160]
        message = str(alert.get("message") or "")[:2000]
        if not message:
            return 0
        # Legacy notify.<service> accepts optional data; notify.send_message does not.
        legacy_payload: dict[str, Any] = {"title": title, "message": message}
        entity_payload: dict[str, Any] = {"title": title, "message": message}
        notification_data: dict[str, Any] = {}
        alert_id = str(alert.get("id") or "").strip()[:240]
        if alert_id:
            notification_data["tag"] = f"nodalia:{alert_id}"
        url = str(alert.get("url") or "").strip()[:2048]
        if (
            (url.startswith("/") and not url.startswith("//") and "\\" not in url)
            or url.startswith(("https://", "http://"))
        ):
            notification_data["url"] = url
            notification_data["clickAction"] = url
            action_label = str(alert.get("action_label") or "").strip()[:100]
            if action_label:
                notification_data["actions"] = [{"action": "URI", "title": action_label, "uri": url}]
        if alert.get("severity") == "critical" and notify.get("critical_alerts") is True:
            notification_data.update({
                "ttl": 0,
                "priority": "high",
                "push": {"sound": {"name": "default", "critical": 1, "volume": 1.0}},
            })
        if notification_data:
            legacy_payload["data"] = notification_data

        delivered = 0
        modern_targets = []
        for entity_id in notify.get("entities", []):
            target = str(entity_id or "").strip()
            if target.startswith("notify.") and target not in modern_targets:
                modern_targets.append(target)
        if modern_targets and self.hass.services.has_service("notify", "send_message"):
            for target in modern_targets:
                try:
                    await self.hass.services.async_call(
                        "notify",
                        "send_message",
                        entity_payload,
                        blocking=True,
                        target={"entity_id": [target]},
                    )
                    delivered += 1
                except Exception as err:  # noqa: BLE001 - notify platforms raise mixed errors
                    _LOGGER.warning("Nodalia notification target %s failed: %s", target, err)

        seen_services: set[str] = set()
        for service_name in notify.get("services", []):
            service = str(service_name or "").strip().lower()
            if not service.startswith("notify.") or service in seen_services:
                continue
            seen_services.add(service)
            service_part = service.split(".", 1)[1]
            if not self.hass.services.has_service("notify", service_part):
                continue
            try:
                await self.hass.services.async_call(
                    "notify",
                    service_part,
                    legacy_payload,
                    blocking=True,
                )
                delivered += 1
            except Exception as err:  # noqa: BLE001 - notify platforms raise mixed errors
                _LOGGER.warning("Nodalia notification service %s failed: %s", service, err)
        return delivered

    def _template_values(self, profile: dict[str, Any], source_entity_id: str) -> dict[str, str]:
        """Resolve the card's bounded, non-executable placeholder language."""
        values: dict[str, str] = {}
        source = self.hass.states.get(source_entity_id)
        if source is not None:
            for key, value in source.attributes.items():
                if isinstance(key, str) and len(key) <= 128:
                    values[key] = self._stringify_template_value(value)
            values["source"] = str(source.attributes.get("friendly_name") or source_entity_id)
            values["state"] = str(source.state or "")
            values["time"] = source.last_changed.astimezone().strftime("%H:%M")

        for token in referenced_template_tokens(profile):
            entity_id, separator, attribute = token.rpartition(".")
            if not separator or "." not in entity_id:
                entity_id, attribute = token, ""
            state = self.hass.states.get(entity_id)
            if state is None:
                values[token] = ""
                continue
            if attribute == "state":
                raw: Any = state.state
            elif attribute:
                raw = state.attributes.get(attribute)
            else:
                domain = entity_id.split(".", 1)[0]
                if domain == "media_player":
                    raw = state.attributes.get("friendly_name") or entity_id
                elif domain == "calendar":
                    raw = (
                        state.attributes.get("message")
                        or state.attributes.get("summary")
                        or state.attributes.get("friendly_name")
                        or state.state
                    )
                else:
                    raw = state.state
                    unit = str(state.attributes.get("unit_of_measurement") or "")
                    if unit:
                        raw = f"{raw}{unit}"
            values[token] = self._stringify_template_value(raw)
        return values

    @staticmethod
    def _render(template: Any, values: dict[str, str]) -> str:
        rendered = str(template or "")
        for key, value in values.items():
            rendered = rendered.replace("{" + key + "}", value)
        return rendered

    @staticmethod
    def _stringify_template_value(value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, (dict, list)):
            try:
                return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
            except (TypeError, ValueError):
                return str(value)
        return str(value)
