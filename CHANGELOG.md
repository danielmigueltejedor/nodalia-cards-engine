# Changelog

## [2.0.0-alpha.60] - 2026-08-04

### Fixed

- Config flow import now uses `ConfigFlowResult` from `homeassistant.config_entries`, so Home Assistant can load **Add integration → Nodalia Cards Engine** instead of failing with `Invalid handler specified`.

### Added

- `nodalia.send_external_alert` and `nodalia.apply_climate_schedule` actions, plus matching WebSocket commands for external notification alerts and immediate climate schedule application.
- Capability flags for external alerts, safe templates, deep links, climate schedule apply and climate schedule modes.

## [2.0.0-alpha.59] - 2026-08-01

Initial public alpha of the optional Nodalia Cards Engine.

- Native background notification profiles and shared dismissals.
- Native persistent Climate schedules.
- Authenticated Home Assistant WebSocket bridge and privacy-safe diagnostics.
- Independent HACS Integration packaging alongside the existing Nodalia Cards Dashboard plugin.
- Administrator-only test delivery, bounded persistent profiles and combined watched-entity limits.
- HACS, Hassfest, CodeQL and release validation prepared for the independent repository.
