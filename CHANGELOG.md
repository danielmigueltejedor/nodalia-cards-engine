# Changelog

## [Unreleased]

### Changed

- Replace the README header with the supplied Nodalia Cards Engine wordmark and the integration brand icon with its matching PNG, including a high-density variant. Preserve transparency and trim excess outer margins.

### Fixed

- Re-evaluate a weekly climate schedule when the active slot ends and a different enabled slot takes over, including a shorter slot that was covering an overnight slot from the previous day. A slot end that leaves no other slot active still waits for the next start.

## [3.0.0] - 2026-10-03

Stable Engine release with WebSocket API v3, native forecast alerts and persistent advanced card capabilities. Companion frontend: Nodalia Cards `3.0.0-alpha.5`.

### Added

- Notification preview without sending or saving. Preview reports missing entities and the policy that blocks an alert; delivery eligibility remains advisory.
- Persistent per-profile notification snoozes, with timezone-aware expiry up to seven days and automatic resumption after expiry.
- Climate schedule preview using the Home Assistant timezone and the same weekly, overnight and override rules as execution, without changing the thermostat.
- Private vacuum selection drafts per authenticated user and entity. Read/control permissions, revision conflicts and bounded storage prevent unauthorized access and silent concurrent overwrites; saving a draft never starts a robot.
- Native background rain forecasts while the dashboard is closed. Queries run at startup, profile save and every 15 minutes, with bounded lookahead, query timeouts, shared entity requests and delivered-identity deduplication across restarts.
- Typed rain measurements and explicit current-temperature template fields, preserving real zero readings and representing missing data without inventing a value.
- Capability-gated API v3 commands and advertised resource limits. The Cards bridge exposes the new operations; additional editor controls can be integrated separately.

### Fixed

- Rain `{value}` retains the probability meaning of published Engine 2.0.2, including `%`. Default messages report probability; forecasts without a numeric probability use coherent expected-rain copy.
- Current temperature uses `{temperature}{temperature_unit}`; forecast temperature never replaces it. Custom copy such as `Fuera hacen {value}.` must use the explicit temperature fields. The temporary temperature alias in the unpublished 3.0.0 preparation is removed.
- Forecast delivery starts after the legacy notification package enters standby, respects severity, quiet hours, presence, dismissals, snoozes and cooldowns, and cancels owned work on unload.

### Compatibility and upgrade

- API range `1`–`3`; existing API 1/2 commands remain available. Cards `3.0.0-alpha.5` negotiates API 3 and falls back to API 2 with older Engines.
- Storage version remains `1`. Existing profiles, inbox entries, shared dismissals, weekly schedules and overrides require no storage migration.
- Configuration writes and previews require an administrator. Vacuum drafts use the authenticated user's entity permissions.
- Update the HACS Integration and restart Home Assistant. Reload the browser, confirm **Engine active**, then verify a real background alert and schedule before removing fallback packages or helpers.

### Validation

- 53 functional tests and six repository contracts, including the actual background manager and API v3 handlers against Home Assistant transport boundaries.
- Integration compilation, HACS, Hassfest and CodeQL validation. No live Home Assistant installation is exercised by these automated tests.

## [2.0.2] - 2026-08-18

### Fixed

- Pause an installed legacy background notification package while the Engine is running, preventing duplicate mobile delivery.
- Restore the legacy helper on a clean unload only when the Engine originally paused it.

## [2.0.1] - 2026-08-17

Patch release for localized Engine-first notification delivery alongside Nodalia Cards `2.2.0-alpha.2`.

### Changed

- Notification profiles persist the resolved language supplied by the Notifications Card.
- Background smart-alert evaluation prefers the profile language and retains the Home Assistant system language as a fallback for older profiles.

### Fixed

- Engine-generated default titles and messages no longer fall back to English when the active Home Assistant user/card language differs from the server-wide language.
- Complements the Cards-side package standby/failover flow that prevents Engine and legacy YAML delivery from notifying the same target simultaneously.

### Validation

- Repository, notification-engine and climate-engine test suites pass, including a Spanish temperature-copy regression.

## [2.0.0] - 2026-08-04

Second stable Engine release. Raises the WebSocket protocol to **API `2`** while still accepting API `1` clients (`api_min_version: 1`, `api_max_version: 2`).

### Added

- **Notification inbox.** Delivered alerts are stored per profile (newest first, up to 100 entries) and exposed through `nodalia/notifications/inbox/list`. Administrators can empty it with `nodalia/notifications/inbox/clear`, and dismissing an alert marks its inbox entry as dismissed.
- **Climate overrides.** A temporary manual override with an ISO 8601 `until` wins over the weekly slots and can carry `temperature`, `hvac_mode`, `fan_mode`, `preset_mode` or a `target_temp_low`/`target_temp_high` pair. Set it with `nodalia/climate/override/set` and drop it with `nodalia/climate/override/clear`; the Engine re-arms its timer for the expiry and reapplies the schedule when the override lapses.
- **Smart alerts.** New rain, outdoor temperature and media-absence recommendations with localized copy in every supported language. Weather entities are evaluated against their precipitation probability, outdoor sensors get their own `outdoor_hot`/`outdoor_cold` kinds, and media players report when playback stops.
- **Discovery commands.** `nodalia/notifications/list` and `nodalia/climate/schedule/list` let cards enumerate stored profiles and schedules without fetching each one.
- **Status health block.** `nodalia/status` now reports privacy-safe `profile_count`, `schedule_count`, `inbox_count`, `override_count` and `last_error` counters.

### Changed

- Capability negotiation advertises `notifications_inbox` and `climate_overrides`.
- Diagnostics include the inbox and active override counts.

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
