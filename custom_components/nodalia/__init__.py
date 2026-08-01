"""Nodalia Cards Engine backend for Home Assistant."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import DATA_RUNTIME, DATA_WEBSOCKET_REGISTERED, DOMAIN
from .runtime import NodaliaRuntime
from .websocket_api import async_register as async_register_websocket

SERVICE_TEST_NOTIFICATION = "test_notification"
SERVICE_TEST_NOTIFICATION_SCHEMA = vol.Schema(
    {
        vol.Optional("profile_id", default="default"): cv.string,
        vol.Optional("title", default="Nodalia"): cv.string,
        vol.Optional("message", default="Background notifications are ready."): cv.string,
    }
)


async def async_setup(hass: HomeAssistant, _config: ConfigType) -> bool:
    """Register global APIs and actions once."""
    domain_data = hass.data.setdefault(DOMAIN, {})
    if not domain_data.get(DATA_WEBSOCKET_REGISTERED):
        async_register_websocket(hass)
        domain_data[DATA_WEBSOCKET_REGISTERED] = True

    async def async_test_notification(call: ServiceCall) -> None:
        if call.context.user_id is not None:
            user = await hass.auth.async_get_user(call.context.user_id)
            if user is None or not user.is_admin:
                raise ServiceValidationError(
                    "Only Home Assistant administrators can send Nodalia test notifications"
                )
        runtime = hass.data.get(DOMAIN, {}).get(DATA_RUNTIME)
        if not isinstance(runtime, NodaliaRuntime) or not runtime.started:
            raise HomeAssistantError("Nodalia is not configured or loaded")
        delivered = await runtime.notifications.async_send_test(
            call.data["profile_id"], call.data["title"], call.data["message"]
        )
        if delivered < 1:
            raise HomeAssistantError("No configured notification target accepted the test")

    if not hass.services.has_service(DOMAIN, SERVICE_TEST_NOTIFICATION):
        hass.services.async_register(
            DOMAIN,
            SERVICE_TEST_NOTIFICATION,
            async_test_notification,
            schema=SERVICE_TEST_NOTIFICATION_SCHEMA,
        )
    return True


async def async_setup_entry(hass: HomeAssistant, _entry: ConfigEntry) -> bool:
    """Start the persistent runtime."""
    domain_data = hass.data.setdefault(DOMAIN, {})
    runtime = NodaliaRuntime(hass)
    await runtime.async_start()
    domain_data[DATA_RUNTIME] = runtime

    return True


async def async_unload_entry(hass: HomeAssistant, _entry: ConfigEntry) -> bool:
    """Cleanly detach every listener and timer."""
    domain_data = hass.data.get(DOMAIN, {})
    runtime = domain_data.pop(DATA_RUNTIME, None)
    if isinstance(runtime, NodaliaRuntime):
        await runtime.async_stop()
    return True
