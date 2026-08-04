# Changelog

## [2.0.0-alpha.64] - 2026-08-04

### Fixed

- Background and test delivery no longer pass `data` to `notify.send_message`, which Home Assistant 2026.7 rejects. Legacy `notify.<service>` calls still receive mobile `data` payloads.

## [2.0.0-alpha.63] - 2026-08-04

### Fixed

- `nodalia.test_notification` and the other actions no longer use a strict Voluptuous service schema, so the Home Assistant Actions UI `data: null` payload no longer blocks the call. Handlers re-register on config entry setup after updates.

## [2.0.0-alpha.62] - 2026-08-04

### Fixed

- Service schemas strip unexpected Action UI keys such as `data: null`, so `nodalia.test_notification` no longer fails with `extra keys not allowed @ data['data']`.

## [2.0.0-alpha.61] - 2026-08-04

### Fixed

- Admin-gated WebSocket commands now use `@websocket_api.require_admin` instead of the non-existent `connection.require_admin()`, which caused `unknown_error` on Home Assistant 2026.7 when saving notification profiles or Climate schedules.

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
