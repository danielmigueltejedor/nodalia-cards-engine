# Changelog

## [1.0.0] - 2026-08-04

First stable release of the independent Nodalia Cards Engine HACS Integration.

Promotes the completed `2.0.0-alpha.59`–`2.0.0-alpha.65` cycle and starts Engine versioning at **`1.0.0`**, separate from the Nodalia Cards Dashboard plugin line.

### Highlights

- Background notification profiles with presence, quiet-hours, severity and cooldown policies.
- Shared notification dismissals stored in Home Assistant.
- Persistent weekly Climate schedules applied at native time boundaries.
- Authenticated WebSocket bridge with capability negotiation for Nodalia Cards `2.0.2`+.
- Localized default alert copy and percentage formatting aligned with the Notifications Card.
- Compatible with Home Assistant `2025.1.0`+ (verified through `2026.7`).

### Fixed since public alpha

- Config flow handler import, admin WebSocket gating, Action UI service schemas and `notify.send_message` payload shape for HA 2026.7.
- Background notification titles/messages follow the Home Assistant language and append `%` for percentage-like values when entities omit a unit.

## [2.0.0-alpha.65] - 2026-08-04

### Fixed

- Background notification copy follows the Home Assistant language for default titles/messages and formats percentage-like values with `%` when the entity has no unit, matching the Notifications Card.

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
