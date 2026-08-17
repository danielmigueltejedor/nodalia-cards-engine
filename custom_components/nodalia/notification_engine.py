"""Pure notification policy helpers used by the Nodalia backend."""

from __future__ import annotations

from datetime import datetime
import re
from typing import Any

SEVERITY_SCORE = {"info": 1, "success": 2, "warning": 3, "critical": 4}
INACTIVE_ERROR_STATES = {"", "0", "none", "ok", "unknown", "unavailable"}

DEFAULT_THRESHOLDS = {
    "hot_temperature": 27.0,
    "cold_temperature": 17.0,
    "humidity_high": 70.0,
    "humidity_low": 30.0,
    "battery_low": 20.0,
    "humidifier_fill_low": 20.0,
    "humidifier_fill_full": 90.0,
    "ink_low": 15.0,
    "rain_probability": 50.0,
    "rain_lookahead_hours": 6.0,
    "media_absence_minutes": 10.0,
}

DEFAULT_COPY = {
    "door": ("Door open", "{source} has been opened.", "warning"),
    "window": ("Window open", "{source} has been opened.", "warning"),
    "motion": ("Motion detected", "Motion detected by {source}.", "info"),
    "vacuum": ("Vacuum needs attention", "{source}: {value}", "critical"),
    "hot": ("High temperature", "{source} is at {value}.", "warning"),
    "cold": ("Low temperature", "{source} is at {value}.", "info"),
    "humidity_high": ("High humidity", "{source} is at {value}.", "warning"),
    "humidity_low": ("Low humidity", "{source} is at {value}.", "warning"),
    "battery_low": ("Low battery", "{source} is at {value}.", "warning"),
    "humidifier_fill_low": ("Humidifier needs water", "{source} is at {value}.", "warning"),
    "humidifier_fill_full": ("Humidifier tank full", "{source} is at {value}.", "warning"),
    "ink_low": ("Low ink", "{source} is at {value}.", "warning"),
    "rain": ("Rain expected", "{source} reports a {value} chance of rain.", "warning"),
    "outdoor_hot": ("Hot outside", "{source} is at {value}.", "warning"),
    "outdoor_cold": ("Cold outside", "{source} is at {value}.", "warning"),
    "media_absence": ("Playback stopped", "{source} stopped playing.", "info"),
}

# Keep titles/messages aligned with the Nodalia Cards runtime locales for background delivery.
LOCALIZED_DEFAULT_COPY: dict[str, dict[str, tuple[str, str, str]]] = {
    "es": {
        "door": ("Puerta abierta", "{source} se ha abierto.", "warning"),
        "window": ("Ventana abierta", "{source} se ha abierto.", "warning"),
        "motion": ("Movimiento detectado", "Movimiento detectado por {source}.", "info"),
        "vacuum": ("Robot necesita atención", "{source}: {value}", "critical"),
        "hot": ("Hace calor", "{source} marca {value}.", "warning"),
        "cold": ("Temperatura baja", "{source} marca {value}.", "info"),
        "humidity_high": ("Humedad alta", "{source} está al {value}.", "warning"),
        "humidity_low": ("Humedad baja", "{source} queda en {value}.", "warning"),
        "battery_low": ("Batería baja", "{source} queda en {value}.", "warning"),
        "humidifier_fill_low": ("Depósito bajo", "{source} queda en {value}.", "warning"),
        "humidifier_fill_full": ("Depósito lleno", "{source} está al {value}.", "warning"),
        "ink_low": ("Tinta baja", "{source} queda en {value}.", "warning"),
        "rain": ("Se espera lluvia", "{source} indica un {value} de probabilidad de lluvia.", "warning"),
        "outdoor_hot": ("Calor en el exterior", "{source} marca {value}.", "warning"),
        "outdoor_cold": ("Frío en el exterior", "{source} marca {value}.", "warning"),
        "media_absence": ("Reproducción detenida", "{source} ha dejado de reproducir.", "info"),
    },
    "pt": {
        "door": ("Porta aberta", "{source} foi aberta.", "warning"),
        "window": ("Janela aberta", "{source} foi aberta.", "warning"),
        "motion": ("Movimento detetado", "Movimento detetado por {source}.", "info"),
        "vacuum": ("Robô precisa de atenção", "{source}: {value}", "critical"),
        "hot": ("Está quente", "{source} marca {value}.", "warning"),
        "cold": ("Temperatura baixa", "{source} marca {value}.", "info"),
        "humidity_high": ("Humidade alta", "{source} está em {value}.", "warning"),
        "humidity_low": ("Humidade baixa", "{source} está em {value}.", "warning"),
        "battery_low": ("Bateria fraca", "{source} está em {value}.", "warning"),
        "humidifier_fill_low": ("Depósito baixo", "{source} está em {value}.", "warning"),
        "humidifier_fill_full": ("Depósito cheio", "{source} está em {value}.", "warning"),
        "ink_low": ("Pouca tinta", "{source} está em {value}.", "warning"),
        "rain": ("Chuva prevista", "{source} indica {value} de probabilidade de chuva.", "warning"),
        "outdoor_hot": ("Calor lá fora", "{source} marca {value}.", "warning"),
        "outdoor_cold": ("Frio lá fora", "{source} marca {value}.", "warning"),
        "media_absence": ("Reprodução parada", "{source} deixou de reproduzir.", "info"),
    },
    "fr": {
        "door": ("Porte ouverte", "{source} a été ouverte.", "warning"),
        "window": ("Fenêtre ouverte", "{source} a été ouverte.", "warning"),
        "motion": ("Mouvement détecté", "Mouvement détecté par {source}.", "info"),
        "vacuum": ("Robot nécessite une attention", "{source}: {value}", "critical"),
        "hot": ("Il fait chaud", "{source} indique {value}.", "warning"),
        "cold": ("Température basse", "{source} indique {value}.", "info"),
        "humidity_high": ("Humidité élevée", "{source} est à {value}.", "warning"),
        "humidity_low": ("Humidité basse", "{source} est à {value}.", "warning"),
        "battery_low": ("Batterie faible", "{source} est à {value}.", "warning"),
        "humidifier_fill_low": ("Réservoir bas", "{source} est à {value}.", "warning"),
        "humidifier_fill_full": ("Réservoir plein", "{source} est à {value}.", "warning"),
        "ink_low": ("Encre faible", "{source} est à {value}.", "warning"),
        "rain": ("Pluie prévue", "{source} indique {value} de probabilité de pluie.", "warning"),
        "outdoor_hot": ("Il fait chaud dehors", "{source} indique {value}.", "warning"),
        "outdoor_cold": ("Il fait froid dehors", "{source} indique {value}.", "warning"),
        "media_absence": ("Lecture arrêtée", "{source} a arrêté la lecture.", "info"),
    },
    "de": {
        "door": ("Tür offen", "{source} wurde geöffnet.", "warning"),
        "window": ("Fenster offen", "{source} wurde geöffnet.", "warning"),
        "motion": ("Bewegung erkannt", "Bewegung erkannt von {source}.", "info"),
        "vacuum": ("Roboter braucht Aufmerksamkeit", "{source}: {value}", "critical"),
        "hot": ("Es ist heiß", "{source} zeigt {value}.", "warning"),
        "cold": ("Niedrige Temperatur", "{source} zeigt {value}.", "info"),
        "humidity_high": ("Hohe Luftfeuchtigkeit", "{source} liegt bei {value}.", "warning"),
        "humidity_low": ("Niedrige Luftfeuchtigkeit", "{source} liegt bei {value}.", "warning"),
        "battery_low": ("Niedriger Batteriestand", "{source} liegt bei {value}.", "warning"),
        "humidifier_fill_low": ("Tank niedrig", "{source} liegt bei {value}.", "warning"),
        "humidifier_fill_full": ("Tank voll", "{source} liegt bei {value}.", "warning"),
        "ink_low": ("Wenig Tinte", "{source} liegt bei {value}.", "warning"),
        "rain": ("Regen erwartet", "{source} meldet {value} Regenwahrscheinlichkeit.", "warning"),
        "outdoor_hot": ("Draußen ist es heiß", "{source} zeigt {value}.", "warning"),
        "outdoor_cold": ("Draußen ist es kalt", "{source} zeigt {value}.", "warning"),
        "media_absence": ("Wiedergabe gestoppt", "{source} spielt nicht mehr ab.", "info"),
    },
    "it": {
        "door": ("Porta aperta", "{source} è stata aperta.", "warning"),
        "window": ("Finestra aperta", "{source} è stata aperta.", "warning"),
        "motion": ("Movimento rilevato", "Movimento rilevato da {source}.", "info"),
        "vacuum": ("Il robot richiede attenzione", "{source}: {value}", "critical"),
        "hot": ("Fa caldo", "{source} indica {value}.", "warning"),
        "cold": ("Temperatura bassa", "{source} indica {value}.", "info"),
        "humidity_high": ("Umidità alta", "{source} è a {value}.", "warning"),
        "humidity_low": ("Umidità bassa", "{source} è a {value}.", "warning"),
        "battery_low": ("Batteria scarica", "{source} è a {value}.", "warning"),
        "humidifier_fill_low": ("Serbatoio basso", "{source} è a {value}.", "warning"),
        "humidifier_fill_full": ("Serbatoio pieno", "{source} è a {value}.", "warning"),
        "ink_low": ("Inchiostro basso", "{source} è a {value}.", "warning"),
        "rain": ("Pioggia prevista", "{source} indica {value} di probabilità di pioggia.", "warning"),
        "outdoor_hot": ("Fa caldo fuori", "{source} indica {value}.", "warning"),
        "outdoor_cold": ("Fa freddo fuori", "{source} indica {value}.", "warning"),
        "media_absence": ("Riproduzione interrotta", "{source} ha smesso di riprodurre.", "info"),
    },
}

PERCENT_KINDS = {
    "humidity_high",
    "humidity_low",
    "battery_low",
    "humidifier_fill_low",
    "humidifier_fill_full",
    "ink_low",
    "rain",
}

ENTITY_GROUP_KINDS = {
    "vacuum": "vacuum",
    "vacuum_error": "vacuum",
    "door": "door",
    "window": "window",
    "motion": "motion",
    "temperature": "temperature",
    "humidity": "humidity",
    "battery": "battery",
    "humidifier_fill": "humidifier_fill",
    "humidifier_full": "humidifier_full",
    "ink": "ink",
    "outdoor_temperature": "outdoor_temperature",
    "outdoor_humidity": "outdoor_humidity",
    "weather": "weather",
    "media_player": "media_player",
}
CONTEXT_ENTITY_GROUPS = (
    "calendar",
    "fan",
    "climate",
    "humidifier",
)

RAIN_PROBABILITY_ATTRIBUTES = ("precipitation_probability", "precip_probability")
MEDIA_ACTIVE_STATES = {"playing", "on"}
MEDIA_ABSENT_STATES = {"idle", "off", "paused", "standby"}

MAX_SMART_RULES = 64
MAX_ENTITY_OVERRIDES = 512
MAX_CUSTOM_RULES = 100
MAX_ENTITY_ID_LENGTH = 255
MAX_RULE_ID_LENGTH = 100
MAX_ATTRIBUTE_LENGTH = 128
MAX_CONDITION_LENGTH = 32
MAX_EXPECTED_VALUE_LENGTH = 255
MAX_TITLE_LENGTH = 160
MAX_MESSAGE_LENGTH = 2000
MAX_URL_LENGTH = 2048
MAX_ACTION_LABEL_LENGTH = 100
MAX_EXTERNAL_ALERTS = 100

TEMPLATE_TOKEN_PATTERN = re.compile(r"\{([^{}]+)\}")
TEMPLATE_ENTITY_PATTERN = re.compile(
    r"^([a-zA-Z0-9_]+\.[a-zA-Z0-9_]+)(?:\.([a-zA-Z0-9_]+))?$"
)


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _rows(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _strings(value: Any, limit: int = 512) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in _rows(value):
        text = str(item or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
        if len(result) >= limit:
            break
    return result


def _number(value: Any, fallback: float) -> float:
    try:
        text = str(value).strip().replace("%", "")
        return float(text)
    except (TypeError, ValueError):
        return fallback


def _text(value: Any, limit: int, fallback: str = "") -> str:
    """Normalize one persisted text value and cap its storage footprint."""
    return str(value or fallback).strip()[:limit]


def optional_number(value: Any) -> float | None:
    """Parse common Home Assistant numeric state strings."""
    try:
        text = str(value).strip().replace("%", "")
        if text.lower() in {"", "none", "unknown", "unavailable"}:
            return None
        return float(text)
    except (TypeError, ValueError):
        return None


def normalize_profile(raw: Any) -> dict[str, Any]:
    """Normalize an untrusted profile before persistence or evaluation."""
    source = _mapping(raw)
    notify_source = _mapping(source.get("notify"))
    context_source = _mapping(source.get("context"))
    quiet_source = _mapping(context_source.get("quiet_hours"))
    entities_source = _mapping(source.get("entities"))
    threshold_source = _mapping(source.get("thresholds"))

    thresholds = {
        key: _number(threshold_source.get(key), fallback)
        for key, fallback in DEFAULT_THRESHOLDS.items()
    }
    entities = {
        key: _strings(entities_source.get(key))
        for key in ENTITY_GROUP_KINDS
    }
    for key in CONTEXT_ENTITY_GROUPS:
        entities[key] = _strings(entities_source.get(key))

    smart: dict[str, dict[str, str]] = {}
    for key, value in list(_mapping(source.get("smart")).items())[:MAX_SMART_RULES]:
        row = _mapping(value)
        rule_key = _text(key, MAX_RULE_ID_LENGTH)
        if not rule_key:
            continue
        smart[rule_key] = {
            "title": _text(row.get("title"), MAX_TITLE_LENGTH),
            "message": _text(row.get("message"), MAX_MESSAGE_LENGTH),
            "mobile": normalize_mobile_policy(row.get("mobile")),
            "url": _text(row.get("url"), MAX_URL_LENGTH),
            "action_label": _text(row.get("action_label"), MAX_ACTION_LABEL_LENGTH),
            "tap_action": normalize_tap_action(row.get("tap_action")),
        }

    overrides: dict[str, dict[str, str]] = {}
    for entity_id, value in list(_mapping(source.get("overrides")).items())[:MAX_ENTITY_OVERRIDES]:
        entity = _text(entity_id, MAX_ENTITY_ID_LENGTH)
        if not entity:
            continue
        row = _mapping(value)
        overrides[entity] = {
            "title": _text(row.get("title"), MAX_TITLE_LENGTH),
            "message": _text(row.get("message"), MAX_MESSAGE_LENGTH),
            "mobile": normalize_mobile_policy(row.get("mobile"), allow_inherit=True),
            "url": _text(row.get("url"), MAX_URL_LENGTH),
            "action_label": _text(row.get("action_label"), MAX_ACTION_LABEL_LENGTH),
            "tap_action": normalize_tap_action(row.get("tap_action")),
        }

    custom: list[dict[str, Any]] = []
    for index, value in enumerate(_rows(source.get("custom"))[:MAX_CUSTOM_RULES]):
        row = _mapping(value)
        entity = _text(row.get("entity"), MAX_ENTITY_ID_LENGTH)
        if not entity:
            continue
        custom.append(
            {
                "id": _text(row.get("id"), MAX_RULE_ID_LENGTH, f"custom-{index}"),
                "entity": entity,
                "attribute": _text(row.get("attribute"), MAX_ATTRIBUTE_LENGTH),
                "condition": _text(row.get("condition"), MAX_CONDITION_LENGTH, "changed").lower(),
                "value": _text(row.get("value"), MAX_EXPECTED_VALUE_LENGTH),
                "title": _text(row.get("title"), MAX_TITLE_LENGTH, "Notification"),
                "message": _text(row.get("message"), MAX_MESSAGE_LENGTH, "{name}: {value}"),
                "severity": normalize_severity(row.get("severity")),
                "mobile": normalize_mobile_policy(row.get("mobile")),
                "url": _text(row.get("url"), MAX_URL_LENGTH),
                "action_label": _text(row.get("action_label"), MAX_ACTION_LABEL_LENGTH),
                "tap_action": normalize_tap_action(row.get("tap_action")),
            }
        )

    external_alerts: list[dict[str, Any]] = []
    for value in _rows(source.get("external_alerts"))[:MAX_EXTERNAL_ALERTS]:
        row = _mapping(value)
        alert_id = _text(row.get("id"), MAX_RULE_ID_LENGTH)
        if not alert_id:
            continue
        external_alerts.append(
            {
                "id": alert_id,
                "type": _text(row.get("type"), MAX_CONDITION_LENGTH, "external_alert"),
                "title": _text(row.get("title"), MAX_TITLE_LENGTH, "Notification"),
                "message": _text(row.get("message"), MAX_MESSAGE_LENGTH),
                "severity": normalize_severity(row.get("severity")),
                "entity": _text(row.get("entity"), MAX_ENTITY_ID_LENGTH),
                "source": _text(row.get("source"), MAX_TITLE_LENGTH),
                "mobile": normalize_mobile_policy(row.get("mobile")),
                "url": _text(row.get("url"), MAX_URL_LENGTH),
                "action_label": _text(row.get("action_label"), MAX_ACTION_LABEL_LENGTH),
                "tap_action": normalize_tap_action(row.get("tap_action")),
            }
        )

    return {
        "version": 2,
        "source": _text(source.get("source"), 100, "nodalia-notifications-card"),
        "card_version": _text(source.get("card_version"), 64),
        "language": (
            normalize_language(source.get("language"))
            if _text(source.get("language"), 16)
            else ""
        ),
        "enabled": source.get("enabled") is True,
        "smart_recommendations": source.get("smart_recommendations") is not False,
        "notify": {
            "enabled": notify_source.get("enabled") is True,
            "entities": _strings(notify_source.get("entities"), 32),
            "services": _strings(notify_source.get("services"), 32),
            "min_severity": normalize_severity(notify_source.get("min_severity"), "warning"),
            "critical_alerts": notify_source.get("critical_alerts") is True,
            "default_policy": normalize_mobile_policy(notify_source.get("default_policy")),
            "cooldown_minutes": max(0.0, min(1440.0, _number(notify_source.get("cooldown_minutes"), 30.0))),
            "group_similar": notify_source.get("group_similar") is not False,
        },
        "context": {
            "presence_entity": _text(context_source.get("presence_entity"), MAX_ENTITY_ID_LENGTH),
            "only_when_away": context_source.get("only_when_away") is True,
            "only_when_home": context_source.get("only_when_home") is True,
            "quiet_hours": {
                "enabled": quiet_source.get("enabled") is True,
                "start": normalize_clock(quiet_source.get("start"), "22:00"),
                "end": normalize_clock(quiet_source.get("end"), "07:00"),
                "allow_critical": quiet_source.get("allow_critical") is not False,
            },
        },
        "smart": smart,
        "custom": custom,
        "external_alerts": external_alerts,
        "thresholds": thresholds,
        "entities": entities,
        "overrides": overrides,
    }


def normalize_tap_action(value: Any) -> dict[str, Any]:
    """Keep only navigation actions that mobile apps can execute safely."""
    source = _mapping(value)
    action = _text(source.get("action"), 32, "none").lower().replace("_", "-")
    if action == "navigate":
        path = _text(source.get("navigation_path"), MAX_URL_LENGTH)
        return {"action": "navigate", "navigation_path": path} if _safe_url(path, local_only=True) else {"action": "none"}
    if action == "url":
        url = _text(source.get("url_path"), MAX_URL_LENGTH)
        if _safe_url(url):
            return {"action": "url", "url_path": url, "new_tab": source.get("new_tab") is True}
    return {"action": "none"}


def normalize_mobile_policy(value: Any, allow_inherit: bool = False) -> str:
    """Normalize mobile delivery policy names shared with the card."""
    if allow_inherit and (value is None or not str(value).strip()):
        return "inherit"
    policy = str(value or "auto").strip().lower().replace("-", "_")
    if allow_inherit and policy in {"", "inherit"}:
        return "inherit"
    aliases = {"on": "push", "enabled": "push", "card": "card_only", "false": "off"}
    policy = aliases.get(policy, policy)
    return policy if policy in {"auto", "push", "card_only", "off"} else "auto"


def normalize_severity(value: Any, fallback: str = "info") -> str:
    severity = str(value or fallback).strip().lower()
    return severity if severity in SEVERITY_SCORE else fallback


def normalize_clock(value: Any, fallback: str) -> str:
    text = str(value or "").strip()
    parts = text.split(":")
    if len(parts) != 2:
        return fallback
    try:
        hour, minute = int(parts[0]), int(parts[1])
    except ValueError:
        return fallback
    if not 0 <= hour <= 23 or not 0 <= minute <= 59:
        return fallback
    return f"{hour:02d}:{minute:02d}"


def watched_entities(profile: dict[str, Any]) -> set[str]:
    """Return the exact entities that need indexed state listeners."""
    watched: set[str] = set()
    entity_groups = _mapping(profile.get("entities"))
    for key in ENTITY_GROUP_KINDS:
        watched.update(_strings(entity_groups.get(key)))
    for row in _rows(profile.get("custom")):
        entity = str(_mapping(row).get("entity") or "").strip()
        if entity:
            watched.add(entity)
    presence = str(_mapping(profile.get("context")).get("presence_entity") or "").strip()
    if presence:
        watched.add(presence)
    watched.update(referenced_template_entities(profile))
    return watched


def referenced_template_entities(profile: dict[str, Any]) -> set[str]:
    """Extract Home Assistant entity references used by safe placeholders."""
    templates: list[str] = []
    for section in ("smart", "overrides"):
        for row in _mapping(profile.get(section)).values():
            templates.extend((str(_mapping(row).get("title") or ""), str(_mapping(row).get("message") or "")))
    for section in ("custom", "external_alerts"):
        for row in _rows(profile.get(section)):
            templates.extend((str(_mapping(row).get("title") or ""), str(_mapping(row).get("message") or "")))
    entities: set[str] = set()
    for template in templates:
        for token in TEMPLATE_TOKEN_PATTERN.findall(template):
            match = TEMPLATE_ENTITY_PATTERN.fullmatch(str(token).strip())
            if match:
                entities.add(match.group(1))
    return entities


def referenced_template_tokens(profile: dict[str, Any]) -> set[str]:
    """Return exact entity placeholder tokens used by a profile."""
    tokens: set[str] = set()
    templates: list[str] = []
    for section in ("smart", "overrides"):
        for row in _mapping(profile.get(section)).values():
            templates.extend((str(_mapping(row).get("title") or ""), str(_mapping(row).get("message") or "")))
    for section in ("custom", "external_alerts"):
        for row in _rows(profile.get(section)):
            templates.extend((str(_mapping(row).get("title") or ""), str(_mapping(row).get("message") or "")))
    for template in templates:
        for token in TEMPLATE_TOKEN_PATTERN.findall(template):
            normalized = str(token).strip()
            if TEMPLATE_ENTITY_PATTERN.fullmatch(normalized):
                tokens.add(normalized)
    return tokens


def is_within_quiet_hours(profile: dict[str, Any], now: datetime) -> bool:
    quiet = _mapping(_mapping(profile.get("context")).get("quiet_hours"))
    if quiet.get("enabled") is not True:
        return False
    start = clock_minutes(quiet.get("start"), 22 * 60)
    end = clock_minutes(quiet.get("end"), 7 * 60)
    current = now.hour * 60 + now.minute
    if start == end:
        return False
    return start <= current < end if start < end else current >= start or current < end


def clock_minutes(value: Any, fallback: int = 0) -> int:
    normalized = normalize_clock(value, "")
    if not normalized:
        return fallback
    hour, minute = normalized.split(":")
    return int(hour) * 60 + int(minute)


def passes_presence_context(profile: dict[str, Any], presence_state: str | None) -> bool:
    context = _mapping(profile.get("context"))
    if context.get("only_when_away") is not True and context.get("only_when_home") is not True:
        return True
    if not str(context.get("presence_entity") or "").strip():
        return True
    normalized = str(presence_state or "").strip().lower()
    if normalized in {"", "unknown", "unavailable", "none"}:
        return False
    is_home = normalized in {"home", "on", "occupied", "present", "detected"}
    if context.get("only_when_away") is True and is_home:
        return False
    if context.get("only_when_home") is True and not is_home:
        return False
    return True


def normalize_language(value: Any) -> str:
    """Normalize Home Assistant language codes to a supported copy pack."""
    language = str(value or "en").strip().lower().replace("_", "-")
    if not language:
        return "en"
    if language in LOCALIZED_DEFAULT_COPY:
        return language
    primary = language.split("-", 1)[0]
    return primary if primary in LOCALIZED_DEFAULT_COPY else "en"


def default_copy_for(kind: str, language: str = "en") -> tuple[str, str, str]:
    """Return localized fallback title/message/severity for one smart kind."""
    pack = LOCALIZED_DEFAULT_COPY.get(normalize_language(language), {})
    if kind in pack:
        return pack[kind]
    return DEFAULT_COPY.get(kind, ("Notification", "{source}: {value}", "info"))


def format_measurement(value: Any, unit: str = "", *, kind: str = "") -> tuple[str, str]:
    """Format a sensor reading the same way the Notifications Card does."""
    resolved_unit = str(unit or "").strip()
    if not resolved_unit and kind in PERCENT_KINDS:
        resolved_unit = "%"
    number = optional_number(value)
    if number is None:
        text = str(value if value is not None else "").strip()
        return text, resolved_unit
    if float(number).is_integer():
        text = str(int(number))
    else:
        text = f"{number:.1f}".rstrip("0").rstrip(".")
    return f"{text}{resolved_unit}", resolved_unit


def evaluate_transition(
    profile: dict[str, Any],
    entity_id: str,
    old_value: Any,
    new_value: Any,
    attributes: dict[str, Any] | None = None,
    old_attributes: dict[str, Any] | None = None,
    template_values: dict[str, str] | None = None,
    language: str = "en",
) -> list[dict[str, Any]]:
    """Build zero or more backend alerts for one state transition."""
    attrs = _mapping(attributes)
    old_attrs = _mapping(old_attributes)
    friendly = str(attrs.get("friendly_name") or entity_id)
    unit = str(attrs.get("unit_of_measurement") or "")
    old_text = str(old_value if old_value is not None else "").strip()
    new_text = str(new_value if new_value is not None else "").strip()
    if old_text == new_text and attrs == old_attrs:
        return []

    alerts: list[dict[str, Any]] = []
    for row in _rows(profile.get("custom")):
        custom = _mapping(row)
        if custom.get("entity") != entity_id:
            continue
        attribute = str(custom.get("attribute") or "").strip()
        current = attrs.get(attribute) if attribute else new_value
        previous = old_attrs.get(attribute) if attribute else old_value
        if custom_condition_matches(custom.get("condition"), previous, current, custom.get("value")):
            alerts.append(
                build_alert(
                    profile,
                    kind="custom",
                    entity_id=entity_id,
                    value=current,
                    friendly=friendly,
                    unit=unit,
                    custom=custom,
                    template_values=template_values,
                    language=language,
                )
            )

    if profile.get("smart_recommendations") is False:
        return [alert for alert in alerts if alert_passes_minimum(profile, alert)]

    entities = _mapping(profile.get("entities"))
    thresholds = _mapping(profile.get("thresholds"))
    kind = ""
    new_lower = new_text.lower()
    old_lower = old_text.lower()
    new_number = optional_number(new_value)
    old_number = optional_number(old_value)

    if entity_id in _strings(entities.get("door")) and new_lower == "on" and old_lower != "on":
        kind = "door"
    elif entity_id in _strings(entities.get("window")) and new_lower == "on" and old_lower != "on":
        kind = "window"
    elif entity_id in _strings(entities.get("motion")) and new_lower == "on" and old_lower != "on":
        kind = "motion"
    elif entity_id in _strings(entities.get("vacuum")) and new_lower in {"error", "unavailable"} and old_lower != new_lower:
        kind = "vacuum"
    elif entity_id in _strings(entities.get("vacuum_error")) and new_lower not in INACTIVE_ERROR_STATES and old_lower != new_lower:
        kind = "vacuum"
    elif crossed_high(entity_id, entities.get("temperature"), new_number, old_number, thresholds.get("hot_temperature")):
        kind = "hot"
    elif crossed_low(entity_id, entities.get("temperature"), new_number, old_number, thresholds.get("cold_temperature")):
        kind = "cold"
    elif crossed_high(entity_id, entities.get("humidity"), new_number, old_number, thresholds.get("humidity_high")):
        kind = "humidity_high"
    elif crossed_low(entity_id, entities.get("humidity"), new_number, old_number, thresholds.get("humidity_low")):
        kind = "humidity_low"
    elif crossed_low(entity_id, entities.get("battery"), new_number, old_number, thresholds.get("battery_low")):
        kind = "battery_low"
    elif crossed_low(entity_id, entities.get("humidifier_fill"), new_number, old_number, thresholds.get("humidifier_fill_low")):
        kind = "humidifier_fill_low"
    elif crossed_high(entity_id, entities.get("humidifier_full"), new_number, old_number, thresholds.get("humidifier_fill_full")):
        kind = "humidifier_fill_full"
    elif crossed_low(entity_id, entities.get("ink"), new_number, old_number, thresholds.get("ink_low")):
        kind = "ink_low"
    elif crossed_high(entity_id, entities.get("outdoor_temperature"), new_number, old_number, thresholds.get("hot_temperature")):
        kind = "outdoor_hot"
    elif crossed_low(entity_id, entities.get("outdoor_temperature"), new_number, old_number, thresholds.get("cold_temperature")):
        kind = "outdoor_cold"
    elif crossed_high(entity_id, entities.get("outdoor_humidity"), new_number, old_number, thresholds.get("humidity_high")):
        kind = "humidity_high"
    elif crossed_low(entity_id, entities.get("outdoor_humidity"), new_number, old_number, thresholds.get("humidity_low")):
        kind = "humidity_low"

    alert_value: Any = new_value
    if not kind and entity_id in _strings(entities.get("weather")):
        new_probability = rain_probability(attrs)
        old_probability = rain_probability(old_attrs)
        if crossed_threshold(new_probability, old_probability, thresholds.get("rain_probability")):
            kind = "rain"
            alert_value = new_probability
    if not kind and entity_id in _strings(entities.get("media_player")):
        if new_lower in MEDIA_ABSENT_STATES and old_lower in MEDIA_ACTIVE_STATES:
            kind = "media_absence"

    if kind:
        alerts.append(
            build_alert(
                profile,
                kind=kind,
                entity_id=entity_id,
                value=alert_value,
                friendly=friendly,
                unit=unit,
                template_values=template_values,
                language=language,
            )
        )
    return [alert for alert in alerts if alert_passes_minimum(profile, alert)]


def rain_probability(attributes: dict[str, Any]) -> float | None:
    """Read the rain chance a weather entity exposes on its own state."""
    attrs = _mapping(attributes)
    for key in RAIN_PROBABILITY_ATTRIBUTES:
        value = optional_number(attrs.get(key))
        if value is not None:
            return value
    forecast = _rows(attrs.get("forecast"))
    first = _mapping(forecast[0]) if forecast else {}
    for key in RAIN_PROBABILITY_ATTRIBUTES:
        value = optional_number(first.get(key))
        if value is not None:
            return value
    return None


def crossed_threshold(new: float | None, old: float | None, threshold: Any) -> bool:
    """Return whether a value entered the at-or-above band since the last state."""
    limit = optional_number(threshold)
    return new is not None and limit is not None and new >= limit and (old is None or old < limit)


def crossed_high(entity_id: str, rows: Any, new: float | None, old: float | None, threshold: Any) -> bool:
    limit = optional_number(threshold)
    return entity_id in _strings(rows) and new is not None and limit is not None and new >= limit and (old is None or old < limit)


def crossed_low(entity_id: str, rows: Any, new: float | None, old: float | None, threshold: Any) -> bool:
    limit = optional_number(threshold)
    return entity_id in _strings(rows) and new is not None and limit is not None and new <= limit and (old is None or old > limit)


def custom_condition_matches(condition: Any, old_value: Any, new_value: Any, expected: Any) -> bool:
    condition_key = str(condition or "changed").strip().lower()
    old_text = str(old_value if old_value is not None else "").strip().lower()
    new_text = str(new_value if new_value is not None else "").strip().lower()
    expected_text = str(expected if expected is not None else "").strip().lower()
    if condition_key in {"always", "changed"}:
        return old_text != new_text
    if condition_key in {"equals", "eq", "is"}:
        return new_text == expected_text and old_text != new_text
    if condition_key in {"not_equals", "neq", "is_not"}:
        return new_text != expected_text and old_text != new_text
    if condition_key in {"on", "active"}:
        return new_text == "on" and old_text != "on"
    if condition_key in {"off", "inactive"}:
        return new_text == "off" and old_text != "off"
    if condition_key == "unavailable":
        return new_text in {"unknown", "unavailable"} and old_text != new_text
    if condition_key == "missing":
        return new_value is None and old_value is not None
    new_number = optional_number(new_value)
    old_number = optional_number(old_value)
    expected_number = optional_number(expected)
    if new_number is None or expected_number is None:
        return False
    if condition_key in {"above", "greater_than", "gt"}:
        return new_number > expected_number and (old_number is None or old_number <= expected_number)
    if condition_key in {"below", "less_than", "lt"}:
        return new_number < expected_number and (old_number is None or old_number >= expected_number)
    return False


def build_alert(
    profile: dict[str, Any],
    *,
    kind: str,
    entity_id: str,
    value: Any,
    friendly: str,
    unit: str,
    custom: dict[str, Any] | None = None,
    template_values: dict[str, str] | None = None,
    language: str = "en",
) -> dict[str, Any]:
    custom_row = _mapping(custom)
    default_title, default_message, default_severity = default_copy_for(kind, language)
    smart = _mapping(_mapping(profile.get("smart")).get(kind))
    override = _mapping(_mapping(profile.get("overrides")).get(entity_id))
    title = str(custom_row.get("title") or override.get("title") or smart.get("title") or default_title)
    message = str(custom_row.get("message") or override.get("message") or smart.get("message") or default_message)
    severity = normalize_severity(custom_row.get("severity"), default_severity)
    notify = _mapping(profile.get("notify"))
    policy = normalize_mobile_policy(custom_row.get("mobile") or smart.get("mobile") or notify.get("default_policy"))
    override_policy = normalize_mobile_policy(override.get("mobile"), allow_inherit=True)
    if override_policy != "inherit":
        policy = override_policy
    formatted_value, resolved_unit = format_measurement(value, unit, kind=kind)
    values = {
        **(template_values or {}),
        "entity": entity_id,
        "entity_id": entity_id,
        "name": friendly,
        "friendly": friendly,
        "source": friendly,
        "value": formatted_value,
        "state": formatted_value,
        "unit": resolved_unit,
        "kind": kind,
    }
    identity_suffix = str(custom_row.get("id") or entity_id)
    return {
        "id": f"{kind}:{identity_suffix}",
        "kind": kind,
        "entity_id": entity_id,
        "title": render_template(title, values),
        "message": render_template(message, values),
        "severity": severity,
        "mobile": policy,
        "url": resolve_alert_url(custom_row, override, smart),
        "action_label": str(
            custom_row.get("action_label")
            or override.get("action_label")
            or smart.get("action_label")
            or ""
        )[:MAX_ACTION_LABEL_LENGTH],
    }


def resolve_alert_url(*sources: dict[str, Any]) -> str:
    """Resolve the first safe dashboard or web URL from an alert policy."""
    for source in sources:
        row = _mapping(source)
        tap_action = _mapping(row.get("tap_action"))
        action = tap_action.get("action")
        candidate = tap_action.get("navigation_path") if action == "navigate" else tap_action.get("url_path")
        candidate = str(candidate or row.get("url") or "").strip()[:MAX_URL_LENGTH]
        if _safe_url(candidate):
            return candidate
    return ""


def _safe_url(value: Any, local_only: bool = False) -> bool:
    candidate = str(value or "").strip()
    if candidate.startswith("/") and not candidate.startswith("//") and "\\" not in candidate:
        return True
    return not local_only and candidate.startswith(("https://", "http://"))


def render_template(template: str, values: dict[str, str]) -> str:
    """Replace the small, non-executable placeholder language used by cards."""
    rendered = str(template or "")
    for key, value in values.items():
        rendered = rendered.replace("{" + key + "}", str(value))
    return rendered


def alert_passes_minimum(profile: dict[str, Any], alert: dict[str, Any]) -> bool:
    notify = _mapping(profile.get("notify"))
    if normalize_mobile_policy(alert.get("mobile")) == "push":
        return True
    minimum = normalize_severity(notify.get("min_severity"), "warning")
    severity = normalize_severity(alert.get("severity"))
    return SEVERITY_SCORE[severity] >= SEVERITY_SCORE[minimum]


def delivery_allowed(profile: dict[str, Any], alert: dict[str, Any]) -> bool:
    """Resolve static delivery flags; runtime context is checked separately."""
    notify = _mapping(profile.get("notify"))
    if profile.get("enabled") is not True:
        return False
    policy = normalize_mobile_policy(alert.get("mobile"))
    if policy not in {"auto", "push"}:
        return False
    return notify.get("enabled") is True or policy == "push"


def cooldown_identity(profile: dict[str, Any], alert: dict[str, Any]) -> str:
    notify = _mapping(profile.get("notify"))
    if notify.get("group_similar") is False:
        return str(alert.get("id") or "")
    return str(alert.get("kind") or alert.get("id") or "")
