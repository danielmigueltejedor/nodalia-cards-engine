# Nodalia Engine API v3

This protocol is independent of the Engine and Cards release numbers. The
unreleased implementation supports API 1–3; published Engine 3.0.0 supports
API 1–2. Cards discovers the server using `nodalia/status` with API 2 and
chooses the highest shared version (3 or 2). Status discovery must remain
available before negotiation. A capability is usable only when advertised;
the new endpoints below require API 3 and return `unsupported_api_version`
for another generation. Existing endpoints and storage version 1 remain valid.

## Rain templates and measurements

New profiles explicitly use `template_version: 3`. API 3 profile writes and
notification previews select that template version. For rain alerts:

- `{value}` and `{precipitation_probability}` contain the formatted probability,
  including `%`. Probability is a finite number between 0 and 100.
- `{temperature}` is the **current** numeric weather temperature, without its
  unit; `{temperature_unit}` contains the unit. A real zero remains `0`.
- Missing or invalid values are empty strings; the unit of a missing temperature
  is empty. Forecast temperatures never replace the current reading.
- `{time}` is the expected rain time for forecast alerts.

Prefer this explicit copy in both foreground and background configuration:

```yaml
message: "Probabilidad de lluvia: {precipitation_probability}."
```

For a temperature message, use `Fuera hacen {temperature}{temperature_unit}.`
Do not keep `Fuera hacen {value}.` in a migrated rain profile. Saved profiles
without `template_version: 3` retain Engine 3.0.0's legacy temperature meaning
of `{value}` until the client explicitly migrates them. Default rain copy
continues to report probability regardless of that legacy alias.

Rain alerts and inbox entries add structured `measurements` without changing
existing title/message fields:

```json
{"precipitation_probability":{"value":80,"unit":"%"},"temperature":{"value":0,"unit":"°C"}}
```

Absent readings use `null`; absent temperature units use `""`. Clients should
use these numeric fields for calculations and the existing localized message
for display. No template executes Jinja, Python or JavaScript.

## New operations

All requests include the usual Home Assistant message `id`, `type`, and
`api_version: 3`. Home Assistant authenticates the connection. Errors retain
Home Assistant's existing `success: false` / `error: {code, message}` envelope.
Do not retry mutations automatically after a connection loss.

| Capability | Command | Additional request fields | Permissions |
|---|---|---|---|
| `notifications_preview` | `nodalia/notifications/preview` | `profile`, optional `profile_id` (default `default`) | Administrator |
| `notifications_snooze` | `nodalia/notifications/snooze` | `alert_id`, `until`, optional `profile_id` | Administrator |
| `climate_schedule_preview` | `nodalia/climate/schedule/preview` | `entity_id`, `schedule`, `at` | Administrator |
| `vacuum_sessions` | `nodalia/vacuum/session/get` | `entity_id` | Authenticated user, read permission for this vacuum |
| `vacuum_sessions` | `nodalia/vacuum/session/set` | `entity_id`, `session`, `expected_revision` | Authenticated user, control permission for this vacuum |

### Notification preview

Response: `profile_id`, normalized `profile`, `alerts`, `missing_entities`,
`dry_run: true`. Evaluates current watched entity states, using authoritative
HA readings and the existing notification policies. It does not fabricate
playback-stop transitions, query forecasts, change profiles, advance cooldowns,
write inbox entries or send notifications. `delivery_eligible` is advisory:
`blocked_reason` can be `delivery_policy`, `quiet_hours`, `presence`, `dismissed`
or `snoozed`; an actual send still evaluates cooldowns and platform availability.
At most 512 watched entities/returned alerts are supported.

### Notification snooze

Response: `profile_id`, `alert_id`, normalized ISO `until`. The profile must
already exist. The timezone-aware expiry must be future and no more than seven
days away. Snoozes are persisted across restarts and suppress automatic
background delivery without dismissing the alert. They are shared by the
explicit notification profile. At most 250 active snoozes per profile are
retained; expired rows are removed when saving another snooze. A deliberate
administrator test notification remains a test and bypasses automatic policy.

### Climate schedule preview

Response: `entity_id`, `at`, `time_zone`, normalized `schedule`, `effective_slot`,
`next_change`, `ignored_slots`, `dry_run: true`. `at` must include a timezone;
the evaluator converts it into HA's configured timezone and uses the same
weekly/overnight/override rules as actual execution. It never saves a schedule
or calls a climate service. `ignored_slots` identifies invalid/excess rows
removed by normalization. Absence of an effective slot/boundary is `null`.

### Vacuum selection sessions

Response: `entity_id`, `revision`, `session`. An unsaved session has revision
`0` and `session: null`. The server derives ownership from the authenticated
user; the client cannot supply another user's id. State is scoped to that user
and vacuum. Saving requires the revision returned by the latest get. A stale
write returns `conflict`; reload and ask the user to reconcile their selection.
The check and write are serialized, so simultaneous dashboards cannot silently
overwrite each other.

`session` contains `activeMode` (`rooms`, `zone`, `goto`, `smart`, `routines`),
`repeats` (integer 1–10), `selectedRoomIds`, `selectedPredefinedZoneIds` and
`manualZones` (`x1`, `y1`, `x2`, `y2` in vacuum coordinates). These are saved
selection drafts, not instructions to resume a robot automatically. No session
endpoint executes a vacuum command. Limits: 16 KiB request session, 100 ids per
selection list, 32 positive finite rectangles and 128 stored user/vacuum pairs.
Other fields are not persisted. Update an existing pair when the store is full.

## Background forecast alerts

`weather_forecast_alerts` advertises server-side forecast delivery while the
dashboard is closed. Enabled profiles are queried on startup/profile save and
every 15 minutes using native `weather.get_forecasts`, preferring hourly and
falling back to daily/twice-daily when advertised by the weather entity. One
query per shared entity serves its profiles. Calls time out after 15 seconds;
failures wait for the normal refresh. Overlapping refreshes are suppressed and
owned startup work is cancelled on unload.

The earliest rainy forecast within the configured lookahead is evaluated
(maximum 72 hours). A rainy condition may trigger without a numeric probability;
that default message mentions expected rain without inventing a percentage.
Alerts carry `forecast_at` and an identity specific to the forecast instant.
Successful delivered inbox identities prevent repeated polling/restart pushes
while that identity remains in the bounded inbox. Severity, quiet hours,
presence, dismissals, snoozes and cooldowns still apply. Current weather
probability transitions remain supported; forecast data is not an entity state.

## Cards bridge

Cards exposes `previewNotificationProfile`, `snoozeNotification`,
`previewClimateSchedule`, `getVacuumSession` and `setVacuumSession` on
`window.NodaliaBackend`. These methods negotiate status and fail locally with
`unsupported_capability` when the server has no matching API/capability. Their
presence alone does not add new UI controls to existing cards. Integrate them
with the visual editors/live controls as a separate frontend change, preserving
local/helper fallbacks and clearing deferred work on connection/user changes.

References: [HA weather forecasts](https://developers.home-assistant.io/docs/core/entity/weather/),
[authenticated WebSocket permissions](https://developers.home-assistant.io/docs/auth_permissions/).
