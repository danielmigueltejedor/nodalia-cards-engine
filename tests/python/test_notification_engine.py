"""Unit tests for the dependency-free background notification engine."""

from __future__ import annotations

import importlib.util
from datetime import datetime
from pathlib import Path
import unittest


def _load_module(name: str):
    path = Path(__file__).parents[2] / "custom_components" / "nodalia" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


engine = _load_module("notification_engine")


class NotificationEngineTests(unittest.TestCase):
    def _profile(self, extra=None):
        source = {
            "enabled": True,
            "notify": {"enabled": True, "entities": ["notify.phone"], "min_severity": "warning"},
            "entities": {"temperature": ["sensor.room_temperature"]},
            "thresholds": {"hot_temperature": 27},
        }
        if extra:
            source.update(extra)
        return engine.normalize_profile(source)

    def test_threshold_only_fires_when_crossed(self) -> None:
        profile = self._profile()
        alerts = engine.evaluate_transition(profile, "sensor.room_temperature", "26.9", "27.1", {"friendly_name": "Room", "unit_of_measurement": "°C"})
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0]["kind"], "hot")
        self.assertEqual(engine.evaluate_transition(profile, "sensor.room_temperature", "27.1", "28", {}), [])

    def test_explicit_push_bypasses_minimum_severity(self) -> None:
        profile = self._profile({
            "custom": [{
                "id": "presence",
                "entity": "binary_sensor.presence",
                "condition": "on",
                "title": "Presence",
                "message": "Detected",
                "severity": "info",
                "mobile": "push",
            }],
        })
        alerts = engine.evaluate_transition(profile, "binary_sensor.presence", "off", "on", {})
        self.assertEqual(len(alerts), 1)
        profile["notify"]["enabled"] = False
        self.assertTrue(engine.delivery_allowed(profile, alerts[0]))

    def test_quiet_hours_allow_critical_and_equal_times_are_disabled(self) -> None:
        profile = self._profile({"context": {"quiet_hours": {"enabled": True, "start": "22:00", "end": "07:00", "allow_critical": True}}})
        self.assertTrue(engine.is_within_quiet_hours(profile, datetime.fromisoformat("2026-07-29T23:00:00+02:00")))
        equal = self._profile({"context": {"quiet_hours": {"enabled": True, "start": "08:00", "end": "08:00"}}})
        self.assertFalse(engine.is_within_quiet_hours(equal, datetime.fromisoformat("2026-07-29T08:00:00+02:00")))

    def test_missing_override_policy_keeps_inherit(self) -> None:
        profile = self._profile({"overrides": {"sensor.room_temperature": {"title": "Warm"}}})
        self.assertEqual(profile["overrides"]["sensor.room_temperature"]["mobile"], "inherit")

    def test_untrusted_profile_text_and_collections_are_bounded(self) -> None:
        profile = engine.normalize_profile({
            "smart": {f"kind-{index}": {"message": "x" * 3000} for index in range(80)},
            "overrides": {
                f"sensor.entity_{index}": {"title": "y" * 300}
                for index in range(520)
            },
            "custom": [{
                "id": "z" * 200,
                "entity": "sensor.custom",
                "title": "t" * 300,
                "message": "m" * 3000,
            }],
        })
        self.assertEqual(len(profile["smart"]), engine.MAX_SMART_RULES)
        self.assertEqual(len(profile["overrides"]), engine.MAX_ENTITY_OVERRIDES)
        self.assertEqual(len(profile["custom"][0]["id"]), engine.MAX_RULE_ID_LENGTH)
        self.assertEqual(len(profile["custom"][0]["title"]), engine.MAX_TITLE_LENGTH)
        self.assertEqual(len(profile["custom"][0]["message"]), engine.MAX_MESSAGE_LENGTH)

    def test_profile_v2_keeps_safe_actions_external_alerts_and_template_entities(self) -> None:
        profile = engine.normalize_profile({
            "enabled": True,
            "smart_recommendations": False,
            "smart": {
                "hot": {
                    "title": "Warm {sensor.outdoor_temperature}",
                    "tap_action": {"action": "navigate", "navigation_path": "/lovelace/climate"},
                },
            },
            "custom": [{
                "id": "door",
                "entity": "binary_sensor.door",
                "title": "At {sensor.outdoor_temperature}",
                "tap_action": {"action": "url", "url_path": "https://example.com"},
            }],
            "external_alerts": [{"id": "camera", "title": "Camera", "mobile": "push"}],
        })
        self.assertEqual(profile["version"], 2)
        self.assertFalse(profile["smart_recommendations"])
        self.assertEqual(profile["smart"]["hot"]["tap_action"]["action"], "navigate")
        self.assertEqual(profile["custom"][0]["tap_action"]["action"], "url")
        self.assertEqual(profile["external_alerts"][0]["id"], "camera")
        self.assertIn("sensor.outdoor_temperature", engine.watched_entities(profile))

    def test_presence_constraint_without_entity_matches_card_fallback(self) -> None:
        profile = engine.normalize_profile({
            "context": {"only_when_away": True, "presence_entity": ""},
        })
        self.assertTrue(engine.passes_presence_context(profile, None))

    def test_disabling_smart_recommendations_keeps_custom_rules_only(self) -> None:
        profile = self._profile({
            "smart_recommendations": False,
            "custom": [{
                "id": "temperature-change",
                "entity": "sensor.room_temperature",
                "condition": "changed",
                "title": "Changed",
                "message": "{sensor.outdoor_temperature}",
                "mobile": "push",
            }],
        })
        alerts = engine.evaluate_transition(
            profile,
            "sensor.room_temperature",
            "26.9",
            "27.1",
            {},
            {},
            {"sensor.outdoor_temperature": "12°C"},
        )
        self.assertEqual([alert["kind"] for alert in alerts], ["custom"])
        self.assertEqual(alerts[0]["message"], "12°C")

    def test_protocol_relative_navigation_is_rejected(self) -> None:
        action = engine.normalize_tap_action({"action": "navigate", "navigation_path": "//evil.example"})
        self.assertEqual(action, {"action": "none"})


if __name__ == "__main__":
    unittest.main()
