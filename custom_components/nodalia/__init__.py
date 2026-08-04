"""Nodalia Cards Engine backend for Home Assistant."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.typing import ConfigType

from .const import DATA_RUNTIME, DATA_WEBSOCKET_REGISTERED, DOMAIN
from .runtime import NodaliaRuntime
from .websocket_api import async_register as async_register_websocket

SERVICE_TEST_NOTIFICATION = "test_notification"
SERVICE_SEND_EXTERNAL_ALERT = "send_external_alert"
SERVICE_APPLY_CLIMATE_SCHEDULE = "apply_climate_schedule"


async def _async_require_admin(hass: HomeAssistant, call: ServiceCall) -> None:
    if call.context.user_id is None:
        return
    user = await hass.auth.async_get_user(call.context.user_id)
    if user is None or not user.is_admin:
        raise ServiceValidationError("Only Home Assistant administrators can run this Nodalia action")


def _runtime_or_raise(hass: HomeAssistant) -> NodaliaRuntime:
    runtime = hass.data.get(DOMAIN, {}).get(DATA_RUNTIME)
    if not isinstance(runtime, NodaliaRuntime) or not runtime.started:
        raise HomeAssistantError("Nodalia is not configured or loaded")
    return runtime


def _service_text(call: ServiceCall, key: str, default: str = "") -> str:
    """Read one Action/UI field while ignoring nested null placeholders."""
    value = call.data.get(key, default)
    if value is None:
        return default
    return str(value).strip() or default


@callback
def _async_register_services(hass: HomeAssistant) -> None:
    """Register or refresh actions so schema changes apply after updates."""

    async def async_test_notification(call: ServiceCall) -> None:
        await _async_require_admin(hass, call)
        runtime = _runtime_or_raise(hass)
        delivered = await runtime.notifications.async_send_test(
            _service_text(call, "profile_id", "default"),
            _service_text(call, "title", "Nodalia"),
            _service_text(call, "message", "Background notifications are ready."),
        )
        if delivered < 1:
            raise HomeAssistantError("No configured notification target accepted the test")

    async def async_send_external_alert(call: ServiceCall) -> None:
        await _async_require_admin(hass, call)
        runtime = _runtime_or_raise(hass)
        alert_id = _service_text(call, "alert_id")
        if not alert_id:
            raise ServiceValidationError("alert_id is required")
        delivered = await runtime.notifications.async_send_external(
            _service_text(call, "profile_id", "default"),
            alert_id,
        )
        if delivered < 1:
            raise HomeAssistantError("The external alert was blocked by policy or had no available target")

    async def async_apply_climate_schedule(call: ServiceCall) -> None:
        await _async_require_admin(hass, call)
        runtime = _runtime_or_raise(hass)
        entity_id = _service_text(call, "entity_id")
        if not entity_id.startswith("climate."):
            raise ServiceValidationError("entity_id must be a climate entity")
        applied = await runtime.climate.async_apply_schedule(entity_id)
        if not applied:
            raise HomeAssistantError("No active Climate schedule slot could be applied")

    hass.services.async_register(DOMAIN, SERVICE_TEST_NOTIFICATION, async_test_notification)
    hass.services.async_register(DOMAIN, SERVICE_SEND_EXTERNAL_ALERT, async_send_external_alert)
    hass.services.async_register(DOMAIN, SERVICE_APPLY_CLIMATE_SCHEDULE, async_apply_climate_schedule)


async def async_setup(hass: HomeAssistant, _config: ConfigType) -> bool:
    """Register global APIs and actions once."""
    domain_data = hass.data.setdefault(DOMAIN, {})
    if not domain_data.get(DATA_WEBSOCKET_REGISTERED):
        async_register_websocket(hass)
        domain_data[DATA_WEBSOCKET_REGISTERED] = True
    _async_register_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, _entry: ConfigEntry) -> bool:
    """Start the persistent runtime."""
    domain_data = hass.data.setdefault(DOMAIN, {})
    runtime = NodaliaRuntime(hass)
    await runtime.async_start()
    domain_data[DATA_RUNTIME] = runtime
    # Refresh action handlers after HACS updates without requiring a second restart path.
    _async_register_services(hass)
    return True


async def async_unload_entry(hass: HomeAssistant, _entry: ConfigEntry) -> bool:
    """Cleanly detach every listener and timer."""
    domain_data = hass.data.get(DOMAIN, {})
    runtime = domain_data.pop(DATA_RUNTIME, None)
    if isinstance(runtime, NodaliaRuntime):
        await runtime.async_stop()
    return True
