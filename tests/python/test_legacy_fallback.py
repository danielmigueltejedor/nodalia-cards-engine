"""Unit tests for legacy notification package failover."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest


def _load_module():
    path = (
        Path(__file__).parents[2]
        / "custom_components"
        / "nodalia"
        / "legacy_fallback.py"
    )
    spec = importlib.util.spec_from_file_location("legacy_fallback", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


legacy = _load_module()


class _State:
    def __init__(self, state: str) -> None:
        self.state = state


class _States:
    def __init__(self, initial: str | None) -> None:
        self.value = _State(initial) if initial is not None else None

    def get(self, _entity_id: str):
        return self.value


class _Services:
    def __init__(self, states: _States) -> None:
        self.states = states
        self.calls: list[tuple[str, str, dict, bool]] = []

    def has_service(self, domain: str, service: str) -> bool:
        return domain == "input_boolean" and service in {"turn_on", "turn_off"}

    async def async_call(
        self,
        domain: str,
        service: str,
        data: dict,
        *,
        blocking: bool,
    ) -> None:
        self.calls.append((domain, service, data, blocking))
        assert self.states.value is not None
        self.states.value.state = "on" if service == "turn_on" else "off"


class _Hass:
    def __init__(self, initial: str | None) -> None:
        self.states = _States(initial)
        self.services = _Services(self.states)


class LegacyNotificationFallbackTests(unittest.IsolatedAsyncioTestCase):
    async def test_engine_pauses_and_restores_an_active_legacy_package(self) -> None:
        hass = _Hass("on")
        fallback = legacy.LegacyNotificationFallback(hass)

        self.assertTrue(await fallback.async_suppress())
        self.assertTrue(fallback.suppressed)
        self.assertEqual(hass.states.value.state, "off")

        self.assertTrue(await fallback.async_restore())
        self.assertFalse(fallback.suppressed)
        self.assertEqual(hass.states.value.state, "on")
        self.assertEqual(
            [call[1] for call in hass.services.calls],
            ["turn_off", "turn_on"],
        )

    async def test_engine_does_not_reactivate_a_package_it_did_not_pause(self) -> None:
        hass = _Hass("off")
        fallback = legacy.LegacyNotificationFallback(hass)

        self.assertFalse(await fallback.async_suppress())
        self.assertFalse(await fallback.async_restore())
        self.assertEqual(hass.services.calls, [])

    async def test_missing_legacy_helper_is_a_noop(self) -> None:
        hass = _Hass(None)
        fallback = legacy.LegacyNotificationFallback(hass)

        self.assertFalse(await fallback.async_suppress())
        self.assertFalse(await fallback.async_restore())
        self.assertEqual(hass.services.calls, [])


if __name__ == "__main__":
    unittest.main()
