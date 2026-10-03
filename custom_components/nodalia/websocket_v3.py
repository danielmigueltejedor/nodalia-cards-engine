"""API v3 commands; existing v1/v2 endpoints remain wire compatible."""
from __future__ import annotations

import voluptuous as vol
from homeassistant.auth.permissions.const import POLICY_READ, POLICY_CONTROL
from homeassistant.components import websocket_api

from .capabilities import RevisionConflict
from .const import DATA_RUNTIME, DOMAIN


def _runtime(hass, connection, msg):
    if msg.get("api_version") != 3:
        connection.send_error(msg["id"], "unsupported_api_version", "This command requires API v3")
        return None
    runtime = hass.data.get(DOMAIN, {}).get(DATA_RUNTIME)
    if runtime is None or not runtime.started:
        connection.send_error(msg["id"], "not_loaded", "Nodalia is not loaded")
        return None
    return runtime


def _entity_allowed(connection, msg, policy):
    user = connection.user
    if user is None or not user.permissions.check_entity(msg["entity_id"], policy):
        connection.send_error(msg["id"], "unauthorized", "Entity access denied")
        return False
    return True


@websocket_api.require_admin
@websocket_api.websocket_command({vol.Required("type"): "nodalia/notifications/preview", vol.Required("api_version"): int, vol.Optional("profile_id", default="default"): str, vol.Required("profile"): dict})
@websocket_api.async_response
async def notifications_preview(hass, connection, msg):
    runtime = _runtime(hass, connection, msg)
    if runtime is None:
        return
    try:
        result = runtime.capabilities.preview_notifications(msg["profile"], msg["profile_id"])
    except ValueError as err:
        connection.send_error(msg["id"], "invalid_format", str(err))
        return
    connection.send_result(msg["id"], result)


@websocket_api.require_admin
@websocket_api.websocket_command({vol.Required("type"): "nodalia/notifications/snooze", vol.Required("api_version"): int, vol.Optional("profile_id", default="default"): str, vol.Required("alert_id"): str, vol.Required("until"): str})
@websocket_api.async_response
async def notifications_snooze(hass, connection, msg):
    runtime = _runtime(hass, connection, msg)
    if runtime is None:
        return
    try:
        result = await runtime.capabilities.snooze(msg["profile_id"], msg["alert_id"], msg["until"])
    except ValueError as err:
        connection.send_error(msg["id"], "invalid_format", str(err))
        return
    connection.send_result(msg["id"], result)


@websocket_api.require_admin
@websocket_api.websocket_command({vol.Required("type"): "nodalia/climate/schedule/preview", vol.Required("api_version"): int, vol.Required("entity_id"): str, vol.Required("schedule"): dict, vol.Required("at"): str})
@websocket_api.async_response
async def climate_preview(hass, connection, msg):
    runtime = _runtime(hass, connection, msg)
    if runtime is None:
        return
    try:
        result = runtime.capabilities.preview_climate(msg["entity_id"], msg["schedule"], msg["at"])
    except ValueError as err:
        connection.send_error(msg["id"], "invalid_format", str(err))
        return
    connection.send_result(msg["id"], result)


@websocket_api.websocket_command({vol.Required("type"): "nodalia/vacuum/session/get", vol.Required("api_version"): int, vol.Required("entity_id"): str})
@websocket_api.async_response
async def vacuum_get(hass, connection, msg):
    runtime = _runtime(hass, connection, msg)
    if runtime is None or not _entity_allowed(connection, msg, POLICY_READ):
        return
    try:
        result = runtime.capabilities.get_session(connection.user.id, msg["entity_id"])
    except ValueError as err:
        connection.send_error(msg["id"], "invalid_format", str(err))
        return
    connection.send_result(msg["id"], result)


@websocket_api.websocket_command({vol.Required("type"): "nodalia/vacuum/session/set", vol.Required("api_version"): int, vol.Required("entity_id"): str, vol.Required("session"): dict, vol.Required("expected_revision"): int})
@websocket_api.async_response
async def vacuum_set(hass, connection, msg):
    runtime = _runtime(hass, connection, msg)
    if runtime is None or not _entity_allowed(connection, msg, POLICY_CONTROL):
        return
    try:
        result = await runtime.capabilities.set_session(connection.user.id, msg["entity_id"], msg["session"], msg["expected_revision"])
    except RevisionConflict as err:
        connection.send_error(msg["id"], "conflict", str(err))
        return
    except ValueError as err:
        connection.send_error(msg["id"], "invalid_format", str(err))
        return
    connection.send_result(msg["id"], result)


def async_register(hass):
    for command in (notifications_preview, notifications_snooze, climate_preview, vacuum_get, vacuum_set):
        websocket_api.async_register_command(hass, command)
