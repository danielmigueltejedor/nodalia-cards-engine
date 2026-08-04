"""Authenticated WebSocket bridge for Nodalia Cards."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant

from .const import (
    API_MAX_VERSION,
    API_MIN_VERSION,
    API_VERSION,
    CAPABILITIES,
    DATA_RUNTIME,
    DOMAIN,
    INTEGRATION_VERSION,
    MAX_CLIMATE_SCHEDULES,
    MAX_CLIMATE_SLOTS,
    MAX_NOTIFICATION_INBOX,
    MAX_NOTIFICATION_PROFILES,
    MAX_NOTIFICATION_TARGETS,
    MAX_NOTIFICATION_WATCHED_ENTITIES,
)
from .runtime import NodaliaRuntime

API_VERSION_FIELD = vol.Optional("api_version", default=API_VERSION)


def _runtime(hass: HomeAssistant) -> NodaliaRuntime | None:
    domain_data = hass.data.get(DOMAIN)
    if not isinstance(domain_data, dict):
        return None
    runtime = domain_data.get(DATA_RUNTIME)
    return runtime if isinstance(runtime, NodaliaRuntime) else None


def _send_runtime_missing(connection, msg: dict[str, Any]) -> None:
    connection.send_error(msg["id"], "not_loaded", "Nodalia is installed but its config entry is not loaded")


@websocket_api.websocket_command(
    {vol.Required("type"): "nodalia/status", API_VERSION_FIELD: vol.Coerce(int)}
)
@websocket_api.async_response
async def websocket_status(hass, connection, msg) -> None:
    runtime = _runtime(hass)
    connection.send_result(
        msg["id"],
        {
            "available": runtime is not None and runtime.started,
            "api_version": API_VERSION,
            "api_min_version": API_MIN_VERSION,
            "api_max_version": API_MAX_VERSION,
            "version": INTEGRATION_VERSION,
            "capabilities": [name for name, enabled in CAPABILITIES.items() if enabled],
            "limits": {
                "notification_profiles": MAX_NOTIFICATION_PROFILES,
                "notification_targets_per_profile": MAX_NOTIFICATION_TARGETS,
                "notification_watched_entities": MAX_NOTIFICATION_WATCHED_ENTITIES,
                "notification_inbox_per_profile": MAX_NOTIFICATION_INBOX,
                "climate_schedules": MAX_CLIMATE_SCHEDULES,
                "climate_slots_per_schedule": MAX_CLIMATE_SLOTS,
            },
            "health": _health(runtime),
        },
    )


def _health(runtime: NodaliaRuntime | None) -> dict[str, Any]:
    """Return privacy-safe counters; never entity ids or notification content."""
    if runtime is None:
        return {
            "profile_count": 0,
            "schedule_count": 0,
            "inbox_count": 0,
            "override_count": 0,
            "last_error": "",
        }
    notifications = runtime.notifications.diagnostics()
    climate = runtime.climate.diagnostics()
    return {
        "profile_count": notifications.get("profile_count", 0),
        "schedule_count": climate.get("schedule_count", 0),
        "inbox_count": notifications.get("inbox_count", 0),
        "override_count": climate.get("override_count", 0),
        "last_error": "",
    }


@websocket_api.websocket_command(
    {
        vol.Required("type"): "nodalia/notifications/get",
        API_VERSION_FIELD: vol.Coerce(int),
        vol.Optional("profile_id", default="default"): str,
    }
)
@websocket_api.async_response
async def websocket_notifications_get(hass, connection, msg) -> None:
    runtime = _runtime(hass)
    if runtime is None:
        _send_runtime_missing(connection, msg)
        return
    profile_id = msg.get("profile_id", "default")
    connection.send_result(
        msg["id"],
        {
            "profile_id": profile_id,
            "profile": runtime.notifications.get_profile(profile_id),
            "dismissed": runtime.notifications.dismissed(profile_id),
        },
    )


@websocket_api.websocket_command(
    {vol.Required("type"): "nodalia/notifications/list", API_VERSION_FIELD: vol.Coerce(int)}
)
@websocket_api.async_response
async def websocket_notifications_list(hass, connection, msg) -> None:
    runtime = _runtime(hass)
    if runtime is None:
        _send_runtime_missing(connection, msg)
        return
    profiles = [
        {
            "id": profile_id,
            "enabled": (runtime.notifications.get_profile(profile_id) or {}).get("enabled") is True,
        }
        for profile_id in runtime.notifications.profile_ids()
    ]
    connection.send_result(msg["id"], {"profiles": profiles})


@websocket_api.websocket_command(
    {
        vol.Required("type"): "nodalia/notifications/inbox/list",
        API_VERSION_FIELD: vol.Coerce(int),
        vol.Optional("profile_id", default="default"): str,
    }
)
@websocket_api.async_response
async def websocket_notifications_inbox_list(hass, connection, msg) -> None:
    runtime = _runtime(hass)
    if runtime is None:
        _send_runtime_missing(connection, msg)
        return
    profile_id = msg.get("profile_id", "default")
    connection.send_result(
        msg["id"],
        {"profile_id": profile_id, "inbox": runtime.notifications.list_inbox(profile_id)},
    )


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "nodalia/notifications/inbox/clear",
        API_VERSION_FIELD: vol.Coerce(int),
        vol.Optional("profile_id", default="default"): str,
    }
)
@websocket_api.async_response
async def websocket_notifications_inbox_clear(hass, connection, msg) -> None:
    runtime = _runtime(hass)
    if runtime is None:
        _send_runtime_missing(connection, msg)
        return
    cleared = await runtime.notifications.async_clear_inbox(msg.get("profile_id", "default"))
    connection.send_result(msg["id"], {"cleared": cleared})


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "nodalia/notifications/set",
        API_VERSION_FIELD: vol.Coerce(int),
        vol.Optional("profile_id", default="default"): str,
        vol.Required("profile"): dict,
    }
)
@websocket_api.async_response
async def websocket_notifications_set(hass, connection, msg) -> None:
    runtime = _runtime(hass)
    if runtime is None:
        _send_runtime_missing(connection, msg)
        return
    try:
        profile = await runtime.notifications.async_set_profile(msg.get("profile_id", "default"), msg["profile"])
    except ValueError as err:
        connection.send_error(msg["id"], "invalid_format", str(err))
        return
    profile_id = msg.get("profile_id", "default")
    connection.send_result(
        msg["id"],
        {"profile": profile, "dismissed": runtime.notifications.dismissed(profile_id)},
    )


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "nodalia/notifications/delete",
        API_VERSION_FIELD: vol.Coerce(int),
        vol.Optional("profile_id", default="default"): str,
    }
)
@websocket_api.async_response
async def websocket_notifications_delete(hass, connection, msg) -> None:
    runtime = _runtime(hass)
    if runtime is None:
        _send_runtime_missing(connection, msg)
        return
    deleted = await runtime.notifications.async_delete_profile(msg.get("profile_id", "default"))
    connection.send_result(msg["id"], {"deleted": deleted})


@websocket_api.websocket_command(
    {
        vol.Required("type"): "nodalia/notifications/dismiss",
        API_VERSION_FIELD: vol.Coerce(int),
        vol.Optional("profile_id", default="default"): str,
        vol.Required("alert_id"): str,
    }
)
@websocket_api.async_response
async def websocket_notifications_dismiss(hass, connection, msg) -> None:
    runtime = _runtime(hass)
    if runtime is None:
        _send_runtime_missing(connection, msg)
        return
    try:
        await runtime.notifications.async_dismiss(msg.get("profile_id", "default"), msg["alert_id"])
    except ValueError as err:
        connection.send_error(msg["id"], "invalid_format", str(err))
        return
    connection.send_result(msg["id"], {"dismissed": True})


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "nodalia/notifications/test",
        API_VERSION_FIELD: vol.Coerce(int),
        vol.Optional("profile_id", default="default"): str,
        vol.Optional("title", default="Nodalia"): str,
        vol.Optional("message", default="Background notifications are ready."): str,
    }
)
@websocket_api.async_response
async def websocket_notifications_test(hass, connection, msg) -> None:
    runtime = _runtime(hass)
    if runtime is None:
        _send_runtime_missing(connection, msg)
        return
    try:
        delivered = await runtime.notifications.async_send_test(
            msg.get("profile_id", "default"), msg.get("title"), msg.get("message")
        )
    except ValueError as err:
        connection.send_error(msg["id"], "invalid_format", str(err))
        return
    connection.send_result(msg["id"], {"delivered": delivered})


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "nodalia/notifications/send_external",
        API_VERSION_FIELD: vol.Coerce(int),
        vol.Optional("profile_id", default="default"): str,
        vol.Required("alert_id"): str,
    }
)
@websocket_api.async_response
async def websocket_notifications_send_external(hass, connection, msg) -> None:
    runtime = _runtime(hass)
    if runtime is None:
        _send_runtime_missing(connection, msg)
        return
    try:
        delivered = await runtime.notifications.async_send_external(
            msg.get("profile_id", "default"), msg["alert_id"]
        )
    except ValueError as err:
        connection.send_error(msg["id"], "invalid_format", str(err))
        return
    connection.send_result(msg["id"], {"delivered": delivered})


@websocket_api.websocket_command(
    {
        vol.Required("type"): "nodalia/climate/schedule/get",
        API_VERSION_FIELD: vol.Coerce(int),
        vol.Required("entity_id"): str,
    }
)
@websocket_api.async_response
async def websocket_climate_schedule_get(hass, connection, msg) -> None:
    runtime = _runtime(hass)
    if runtime is None:
        _send_runtime_missing(connection, msg)
        return
    connection.send_result(
        msg["id"],
        {"schedule": runtime.climate.get_schedule(msg["entity_id"])},
    )


@websocket_api.websocket_command(
    {vol.Required("type"): "nodalia/climate/schedule/list", API_VERSION_FIELD: vol.Coerce(int)}
)
@websocket_api.async_response
async def websocket_climate_schedule_list(hass, connection, msg) -> None:
    runtime = _runtime(hass)
    if runtime is None:
        _send_runtime_missing(connection, msg)
        return
    connection.send_result(msg["id"], {"schedules": runtime.climate.list_schedules()})


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "nodalia/climate/override/set",
        API_VERSION_FIELD: vol.Coerce(int),
        vol.Required("entity_id"): str,
        vol.Required("override"): dict,
    }
)
@websocket_api.async_response
async def websocket_climate_override_set(hass, connection, msg) -> None:
    runtime = _runtime(hass)
    if runtime is None:
        _send_runtime_missing(connection, msg)
        return
    try:
        schedule = await runtime.climate.async_set_override(msg["entity_id"], msg["override"])
    except ValueError as err:
        connection.send_error(msg["id"], "invalid_format", str(err))
        return
    connection.send_result(msg["id"], {"schedule": schedule})


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "nodalia/climate/override/clear",
        API_VERSION_FIELD: vol.Coerce(int),
        vol.Required("entity_id"): str,
    }
)
@websocket_api.async_response
async def websocket_climate_override_clear(hass, connection, msg) -> None:
    runtime = _runtime(hass)
    if runtime is None:
        _send_runtime_missing(connection, msg)
        return
    cleared = await runtime.climate.async_clear_override(msg["entity_id"])
    connection.send_result(msg["id"], {"cleared": cleared})


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "nodalia/climate/schedule/set",
        API_VERSION_FIELD: vol.Coerce(int),
        vol.Required("entity_id"): str,
        vol.Required("schedule"): dict,
    }
)
@websocket_api.async_response
async def websocket_climate_schedule_set(hass, connection, msg) -> None:
    runtime = _runtime(hass)
    if runtime is None:
        _send_runtime_missing(connection, msg)
        return
    try:
        schedule = await runtime.climate.async_set_schedule(msg["entity_id"], msg["schedule"])
    except ValueError as err:
        connection.send_error(msg["id"], "invalid_format", str(err))
        return
    connection.send_result(msg["id"], {"schedule": schedule})


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "nodalia/climate/schedule/delete",
        API_VERSION_FIELD: vol.Coerce(int),
        vol.Required("entity_id"): str,
    }
)
@websocket_api.async_response
async def websocket_climate_schedule_delete(hass, connection, msg) -> None:
    runtime = _runtime(hass)
    if runtime is None:
        _send_runtime_missing(connection, msg)
        return
    deleted = await runtime.climate.async_delete_schedule(msg["entity_id"])
    connection.send_result(msg["id"], {"deleted": deleted})


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "nodalia/climate/schedule/apply",
        API_VERSION_FIELD: vol.Coerce(int),
        vol.Required("entity_id"): str,
    }
)
@websocket_api.async_response
async def websocket_climate_schedule_apply(hass, connection, msg) -> None:
    runtime = _runtime(hass)
    if runtime is None:
        _send_runtime_missing(connection, msg)
        return
    try:
        applied = await runtime.climate.async_apply_schedule(msg["entity_id"])
    except ValueError as err:
        connection.send_error(msg["id"], "invalid_format", str(err))
        return
    connection.send_result(msg["id"], {"applied": applied})


@websocket_api.require_admin
@websocket_api.websocket_command(
    {vol.Required("type"): "nodalia/diagnostics", API_VERSION_FIELD: vol.Coerce(int)}
)
@websocket_api.async_response
async def websocket_diagnostics(hass, connection, msg) -> None:
    runtime = _runtime(hass)
    if runtime is None:
        _send_runtime_missing(connection, msg)
        return
    connection.send_result(msg["id"], runtime.diagnostics())


def async_register(hass: HomeAssistant) -> None:
    """Register the stable v1/v2 frontend protocol exactly once."""
    for command in (
        websocket_status,
        websocket_notifications_get,
        websocket_notifications_list,
        websocket_notifications_set,
        websocket_notifications_delete,
        websocket_notifications_dismiss,
        websocket_notifications_test,
        websocket_notifications_send_external,
        websocket_notifications_inbox_list,
        websocket_notifications_inbox_clear,
        websocket_climate_schedule_get,
        websocket_climate_schedule_list,
        websocket_climate_schedule_set,
        websocket_climate_schedule_delete,
        websocket_climate_schedule_apply,
        websocket_climate_override_set,
        websocket_climate_override_clear,
        websocket_diagnostics,
    ):
        websocket_api.async_register_command(hass, command)
