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
        self.assertEqual(alerts[0]["title"], "High temperature")
        self.assertIn("27.1°C", alerts[0]["message"])
        self.assertEqual(engine.evaluate_transition(profile, "sensor.room_temperature", "27.1", "28", {}), [])

    def test_percent_kinds_default_unit_and_localized_copy(self) -> None:
        profile = engine.normalize_profile({
            "enabled": True,
            "notify": {"enabled": True, "entities": ["notify.phone"], "min_severity": "info"},
            "entities": {"ink": ["sensor.color_ink"]},
            "thresholds": {"ink_low": 15},
            "smart": {
                "ink_low": {
                    "title": "",
                    "message": "Queda un {value} de tinta de color.",
                    "mobile": "push",
                }
            },
        })
        alerts = engine.evaluate_transition(
            profile,
            "sensor.color_ink",
            "18",
            "10",
            {"friendly_name": "Tinta color"},
            language="es",
        )
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0]["title"], "Tinta baja")
        self.assertEqual(alerts[0]["message"], "Queda un 10% de tinta de color.")

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

    def test_outdoor_temperature_uses_dedicated_kinds(self) -> None:
        profile = engine.normalize_profile({
            "enabled": True,
            "notify": {"enabled": True, "entities": ["notify.phone"], "min_severity": "info"},
            "entities": {"outdoor_temperature": ["sensor.outdoor"]},
            "thresholds": {"hot_temperature": 27, "cold_temperature": 5},
        })
        hot = engine.evaluate_transition(profile, "sensor.outdoor", "26", "28", {"friendly_name": "Outdoor", "unit_of_measurement": "°C"})
        self.assertEqual([alert["kind"] for alert in hot], ["outdoor_hot"])
        self.assertEqual(hot[0]["title"], "Hot outside")
        self.assertIn("28°C", hot[0]["message"])
        cold = engine.evaluate_transition(profile, "sensor.outdoor", "6", "4", {"friendly_name": "Outdoor"})
        self.assertEqual([alert["kind"] for alert in cold], ["outdoor_cold"])

    def test_outdoor_humidity_reuses_humidity_kinds(self) -> None:
        profile = engine.normalize_profile({
            "enabled": True,
            "notify": {"enabled": True, "entities": ["notify.phone"], "min_severity": "info"},
            "entities": {"outdoor_humidity": ["sensor.outdoor_humidity"]},
            "thresholds": {"humidity_high": 70, "humidity_low": 30},
        })
        high = engine.evaluate_transition(profile, "sensor.outdoor_humidity", "65", "75", {})
        self.assertEqual([alert["kind"] for alert in high], ["humidity_high"])
        low = engine.evaluate_transition(profile, "sensor.outdoor_humidity", "35", "25", {})
        self.assertEqual([alert["kind"] for alert in low], ["humidity_low"])
        self.assertIn("25%", low[0]["message"])

    def test_weather_rain_probability_crossing_fires_once(self) -> None:
        profile = engine.normalize_profile({
            "enabled": True,
            "notify": {"enabled": True, "entities": ["notify.phone"], "min_severity": "info"},
            "entities": {"weather": ["weather.home"]},
            "thresholds": {"rain_probability": 50},
        })
        alerts = engine.evaluate_transition(
            profile,
            "weather.home",
            "cloudy",
            "rainy",
            {"friendly_name": "Home", "precipitation_probability": 80},
            {"friendly_name": "Home", "precipitation_probability": 20},
        )
        self.assertEqual([alert["kind"] for alert in alerts], ["rain"])
        self.assertEqual(alerts[0]["title"], "Rain expected")
        self.assertIn("80%", alerts[0]["message"])
        self.assertEqual(
            engine.evaluate_transition(
                profile,
                "weather.home",
                "rainy",
                "pouring",
                {"precipitation_probability": 90},
                {"precipitation_probability": 80},
            ),
            [],
        )

    def test_weather_rain_falls_back_to_the_first_forecast_entry(self) -> None:
        profile = engine.normalize_profile({
            "enabled": True,
            "notify": {"enabled": True, "entities": ["notify.phone"], "min_severity": "info"},
            "entities": {"weather": ["weather.home"]},
            "thresholds": {"rain_probability": 50},
        })
        alerts = engine.evaluate_transition(
            profile,
            "weather.home",
            "cloudy",
            "cloudy",
            {"forecast": [{"precip_probability": 70}]},
            {"forecast": [{"precip_probability": 10}]},
        )
        self.assertEqual([alert["kind"] for alert in alerts], ["rain"])

    def test_media_player_absence_only_fires_from_an_active_state(self) -> None:
        profile = engine.normalize_profile({
            "enabled": True,
            "notify": {"enabled": True, "entities": ["notify.phone"], "min_severity": "info"},
            "entities": {"media_player": ["media_player.salon"]},
        })
        alerts = engine.evaluate_transition(profile, "media_player.salon", "playing", "idle", {"friendly_name": "Salon"})
        self.assertEqual([alert["kind"] for alert in alerts], ["media_absence"])
        self.assertEqual(alerts[0]["message"], "Salon stopped playing.")
        self.assertEqual(engine.evaluate_transition(profile, "media_player.salon", "idle", "off", {}), [])

    def test_new_smart_groups_are_watched(self) -> None:
        profile = engine.normalize_profile({
            "entities": {
                "weather": ["weather.home"],
                "media_player": ["media_player.salon"],
                "outdoor_temperature": ["sensor.outdoor"],
                "outdoor_humidity": ["sensor.outdoor_humidity"],
            },
        })
        self.assertLessEqual(
            {"weather.home", "media_player.salon", "sensor.outdoor", "sensor.outdoor_humidity"},
            engine.watched_entities(profile),
        )

    def test_new_kinds_have_localized_copy_in_every_language(self) -> None:
        for language, pack in engine.LOCALIZED_DEFAULT_COPY.items():
            for kind in ("rain", "outdoor_hot", "outdoor_cold", "media_absence"):
                with self.subTest(language=language, kind=kind):
                    self.assertIn(kind, pack)
                    self.assertNotEqual(engine.default_copy_for(kind, language), engine.DEFAULT_COPY[kind])

    def test_protocol_relative_navigation_is_rejected(self) -> None:
        action = engine.normalize_tap_action({"action": "navigate", "navigation_path": "//evil.example"})
        self.assertEqual(action, {"action": "none"})


if __name__ == "__main__":
    unittest.main()
