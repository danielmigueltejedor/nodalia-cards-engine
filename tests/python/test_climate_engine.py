"""Unit tests for the dependency-free climate schedule engine."""

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


engine = _load_module("climate_engine")


class ClimateEngineTests(unittest.TestCase):
    def test_active_slot_and_next_boundary(self) -> None:
        schedule = engine.normalize_schedule(
            "climate.salon",
            {
                "enabled": True,
                "slots": [
                    {"id": "morning", "day": "mon", "start": "07:00", "end": "09:00", "temperature": 21},
                    {"id": "evening", "day": "mon", "start": "18:30", "end": "22:00", "temperature": 20},
                ],
            },
        )
        now = datetime.fromisoformat("2026-07-27T08:00:00+02:00")
        self.assertEqual(engine.active_slot(schedule, now)["id"], "morning")
        self.assertEqual(engine.next_slot_start(schedule, now).isoformat(), "2026-07-27T18:30:00+02:00")

    def test_overnight_slot_uses_previous_day(self) -> None:
        schedule = engine.normalize_schedule(
            "climate.salon",
            {"slots": [{"id": "night", "day": "mon", "start": "22:00", "end": "06:00", "temperature": 18}]},
        )
        now = datetime.fromisoformat("2026-07-28T01:00:00+02:00")
        self.assertEqual(engine.active_slot(schedule, now)["id"], "night")

    def test_invalid_rows_are_rejected(self) -> None:
        schedule = engine.normalize_schedule(
            "climate.salon",
            {"slots": [{"start": "99:00", "end": "10:00", "temperature": 21}]},
        )
        self.assertEqual(schedule["slots"], [])

    def test_schedule_preserves_optional_native_climate_controls(self) -> None:
        schedule = engine.normalize_schedule(
            "climate.salon",
            {
                "slots": [{
                    "day": "mon",
                    "start": "08:00",
                    "end": "12:00",
                    "temperature": 21,
                    "hvac_mode": "heat",
                    "fan_mode": "auto",
                    "preset_mode": "comfort",
                    "target_temp_low": 19,
                    "target_temp_high": 23,
                }],
            },
        )
        slot = schedule["slots"][0]
        self.assertEqual(slot["hvac_mode"], "heat")
        self.assertEqual(slot["fan_mode"], "auto")
        self.assertEqual(slot["preset_mode"], "comfort")
        self.assertEqual(slot["target_temp_low"], 19)
        self.assertEqual(slot["target_temp_high"], 23)

    def test_unknown_hvac_mode_is_dropped(self) -> None:
        schedule = engine.normalize_schedule(
            "climate.salon",
            {"slots": [{"day": "mon", "start": "08:00", "end": "12:00", "temperature": 21, "hvac_mode": "boost"}]},
        )
        self.assertNotIn("hvac_mode", schedule["slots"][0])

    def test_override_requires_until_and_bounds_optional_fields(self) -> None:
        self.assertIsNone(engine.normalize_override({"temperature": 22}))
        self.assertIsNone(engine.normalize_override({"until": "not-a-date"}))
        override = engine.normalize_override({
            "until": "2026-07-27T10:00:00+02:00",
            "temperature": 22.5,
            "hvac_mode": "heat",
            "fan_mode": "auto",
            "preset_mode": "comfort",
            "target_temp_low": 19,
            "target_temp_high": 23,
        })
        self.assertEqual(override["until"], "2026-07-27T10:00:00+02:00")
        self.assertEqual(override["temperature"], 22.5)
        self.assertEqual(override["hvac_mode"], "heat")
        self.assertEqual(override["fan_mode"], "auto")
        self.assertEqual(override["preset_mode"], "comfort")
        self.assertEqual(override["target_temp_low"], 19)
        self.assertEqual(override["target_temp_high"], 23)

    def test_out_of_range_override_values_are_dropped(self) -> None:
        override = engine.normalize_override({
            "until": "2026-07-27T10:00:00+02:00",
            "temperature": 60,
            "hvac_mode": "boost",
            "target_temp_low": 30,
            "target_temp_high": 25,
        })
        self.assertEqual(list(override), ["until"])

    def test_normalize_schedule_keeps_a_valid_override(self) -> None:
        schedule = engine.normalize_schedule(
            "climate.salon",
            {
                "slots": [{"day": "mon", "start": "07:00", "end": "09:00", "temperature": 21}],
                "override": {"until": "2026-07-27T10:00:00+02:00", "temperature": 24},
            },
        )
        self.assertEqual(schedule["override"]["temperature"], 24)
        self.assertNotIn(
            "override",
            engine.normalize_schedule("climate.salon", {"override": {"temperature": 24}}),
        )

    def _override_schedule(self, until: str):
        return engine.normalize_schedule(
            "climate.salon",
            {
                "slots": [
                    {"id": "morning", "day": "mon", "start": "07:00", "end": "09:00", "temperature": 21},
                    {"id": "evening", "day": "mon", "start": "18:30", "end": "22:00", "temperature": 20},
                ],
                "override": {"until": until, "temperature": 24, "hvac_mode": "heat"},
            },
        )

    def test_active_override_wins_over_the_weekly_slot(self) -> None:
        schedule = self._override_schedule("2026-07-27T10:00:00+02:00")
        now = datetime.fromisoformat("2026-07-27T08:00:00+02:00")
        slot = engine.effective_slot(schedule, now)
        self.assertTrue(slot["override"])
        self.assertEqual(slot["temperature"], 24)
        self.assertEqual(slot["hvac_mode"], "heat")

    def test_expired_override_falls_back_to_the_weekly_slot(self) -> None:
        schedule = self._override_schedule("2026-07-27T07:30:00+02:00")
        now = datetime.fromisoformat("2026-07-27T08:00:00+02:00")
        self.assertEqual(engine.effective_slot(schedule, now)["id"], "morning")

    def test_next_timer_at_includes_override_expiry(self) -> None:
        now = datetime.fromisoformat("2026-07-27T08:00:00+02:00")
        schedule = self._override_schedule("2026-07-27T10:00:00+02:00")
        self.assertEqual(
            engine.next_timer_at(schedule, now).isoformat(),
            "2026-07-27T10:00:00+02:00",
        )
        expired = self._override_schedule("2026-07-27T07:30:00+02:00")
        self.assertEqual(
            engine.next_timer_at(expired, now).isoformat(),
            "2026-07-27T18:30:00+02:00",
        )

    def test_override_without_offset_uses_the_reference_timezone(self) -> None:
        schedule = self._override_schedule("2026-07-27T10:00:00")
        now = datetime.fromisoformat("2026-07-27T08:00:00+02:00")
        self.assertTrue(engine.effective_slot(schedule, now)["override"])


if __name__ == "__main__":
    unittest.main()
