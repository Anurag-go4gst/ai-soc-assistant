"""Pre-render SPL template slot validation and escaping.

Validates dynamic slot values before ``customize_template_spl`` or
``render_template`` substitution. Fail closed on injection or type mismatch.
"""

from __future__ import annotations

import ipaddress
import re
from dataclasses import dataclass, field
from typing import Any

from app.spl.policy import SplValidationPolicy, load_spl_policy
from app.spl.template_registry import SplTemplateDefinition, get_spl_template

POLICY_VERSION = "2026-06-spl-slot-binding-v2"

SLOT_TYPES = frozenset(
    {
        "host",
        "user",
        "src_ip",
        "dest_ip",
        "index",
        "indexes",
        "sourcetype",
        "time_window",
        "threshold",
        "threshold_comparison",
        "port",
        "cidr",
        "zone",
        "src_zone",
        "dest_zone",
        "rule_name",
        "country",
        "application_protocol",
        "protocol",
        "protocols",
        "function_code",
        "event_code",
        "service",
        "lookup",
        "substation_mapping_lookup",
        "approved_destination_lookup",
        "approved_source_cidr",
        "approved_destination_cidr",
        "src_ip_field",
        "dest_ip_field",
        "function_code_field",
        "action_semantic",
        "unexpected_ip_direction",
        "allowlist_semantic",
        "src_scope",
        "dest_scope",
        "aggregation_subject",
        "alert_id",
        "result_limit",
        "earliest",
        "latest",
    }
)

_LLM_SLOT_KEY_ALIASES: dict[str, str] = {
    "event_id": "event_code",
    "eventid": "event_code",
    "account": "user",
    "username": "user",
    "source_index": "index",
    "data_source": "index",
    "src_subnet": "src_scope",
    "source_subnet": "src_scope",
    "dest_subnet": "dest_scope",
    "destination_subnet": "dest_scope",
}


def canonical_slot_key(slot: str) -> str:
    """Map slot aliases (event_id, account, etc.) to canonical binding keys."""
    return _LLM_SLOT_KEY_ALIASES.get(str(slot).strip().lower(), str(slot).strip().lower())


def normalize_slot_key_aliases(slots: dict[str, Any]) -> dict[str, Any]:
    """Rename known LLM / NL slot aliases to canonical keys before validation."""
    normalized: dict[str, Any] = {}
    for key, value in slots.items():
        canonical = _LLM_SLOT_KEY_ALIASES.get(str(key).strip().lower(), key)
        if canonical not in normalized or normalized[canonical] in (None, "", []):
            normalized[canonical] = value
    return normalized

_INJECTION_PATTERN = re.compile(
    r'["\\`]|[\[\]]|(?:\||;)|\b(?:search|tstats|delete|stats|where|inputlookup|outputlookup|map|rest)\b',
    re.IGNORECASE,
)
_HOST_PATTERN = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9._:-]{0,253}[A-Za-z0-9])?$")
_USER_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._@$-]{0,127}$")
_ALERT_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,63}$")
_INDEX_PATTERN = re.compile(r"^[a-z0-9_][a-z0-9_*-]{0,63}$", re.IGNORECASE)
_SOURCETYPE_PATTERN = re.compile(r"^[a-z0-9_:][a-z0-9_:*-]{0,127}$", re.IGNORECASE)
_ZONE_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 _.-]{0,63}$")
_RULE_APP_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 _./:-]{0,127}$")
_FIELD_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_.:-]{0,127}$")
_COUNTRY_PATTERN = re.compile(r"^[A-Za-z]{2,3}$")
_TIME_TOKEN_PATTERN = re.compile(r"^(?:earliest|latest)=", re.IGNORECASE)
_RELATIVE_TIME_PATTERN = re.compile(r"^-\d+[smhdw]$", re.IGNORECASE)
_EARLIEST_LATEST_PAIR = re.compile(
    r"^earliest=-\d+[smhdw]\s+latest=(?:now|-\d+[smhdw])$",
    re.IGNORECASE,
)

_HOST_SLOT_RE = re.compile(
    r'\bhost=(?:"([^"]+)"|\'([^\']+)\'|([A-Za-z0-9_.:-]+))',
    re.IGNORECASE,
)
_USER_SLOT_RE = re.compile(
    r'\buser=(?:"([^"]+)"|\'([^\']+)\'|([A-Za-z0-9._@$-]+))',
    re.IGNORECASE,
)
_INDEX_SLOT_RE = re.compile(r"\bindex=([A-Za-z0-9_*:-]+)", re.IGNORECASE)
_SOURCETYPE_SLOT_RE = re.compile(r"\bsourcetype=([A-Za-z0-9_:.-]+)", re.IGNORECASE)
_IP_SLOT_RE = re.compile(
    r"\b(?:src_ip|dest_ip|src|dest)=(?:(\"[^\"]+\")|('[^']+')|([0-9a-fA-F:.]+))",
    re.IGNORECASE,
)
_CIDR_SLOT_RE = re.compile(r"\bcidrmatch\(\s*\"([^\"]+)\"", re.IGNORECASE)
_PORT_SLOT_RE = re.compile(r"\bdest_port=(\d{1,5})\b", re.IGNORECASE)
_THRESHOLD_RE = re.compile(r"\b(?:threshold|>=)\s*(\d+)\b", re.IGNORECASE)
_TOP_N_RE = re.compile(r"\b(?:top|first|head|limit)\s+(\d+)\b", re.IGNORECASE)
_ALERT_ID_RE = re.compile(
    r"\b(?:alert_id|alert|alt)[\s:=]+([A-Za-z0-9][\w.-]*)",
    re.IGNORECASE,
)


@dataclass
class SlotValidationOutcome:
    valid: bool
    normalized_slots: dict[str, str] = field(default_factory=dict)
    reject_reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    policy_version: str = POLICY_VERSION


def load_slot_binding_policy() -> SplValidationPolicy:
    return load_spl_policy()


def escape_spl_quoted_string(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def validate_template_query_slots(
    template_id: str,
    user_query: str,
    *,
    template: SplTemplateDefinition | None = None,
    extra_slots: dict[str, Any] | None = None,
    slot_source: str = "user",
    policy: SplValidationPolicy | None = None,
) -> SlotValidationOutcome:
    """Validate slots extracted from a user/LLM query before template rendering."""
    resolved_template = template or get_spl_template(template_id)
    slots = extract_query_slots(user_query)
    for key, value in extract_natural_language_slots(user_query).items():
        if key not in slots:
            slots[key] = value
    if extra_slots:
        for key, value in extra_slots.items():
            if key not in slots:
                slots[key] = value
            elif slot_source == "llm" and key in slots:
                continue
    allowed_indexes = _template_allowed_indexes(resolved_template, policy)
    allowed_sourcetypes = _template_allowed_sourcetypes(resolved_template, policy)
    return validate_slot_map(
        slots,
        allowed_indexes=allowed_indexes,
        allowed_sourcetypes=allowed_sourcetypes,
        policy=policy,
        slot_source=slot_source,
    )



_NL_SEARCH_INDEX_RE = re.compile(
    r"\bsearch\s+([a-z0-9_*:-]+)\s+for\b",
    re.IGNORECASE,
)
_NL_INDEX_RE = re.compile(
    r"\b(?:search|in|across|from)\s+(?:the\s+)?([a-z0-9_*:-]+)\s+index\b|\b([a-z0-9_*:-]+)\s+index\b",
    re.IGNORECASE,
)
_NL_USER_RE = re.compile(
    r"\b(?:user|account)\s+([A-Za-z0-9][A-Za-z0-9._@$-]{0,127})\b",
    re.IGNORECASE,
)
_NL_HOST_RE = re.compile(
    r"\b(?:on|server|machine)\s+([A-Za-z0-9][A-Za-z0-9._:-]{0,253})\b",
    re.IGNORECASE,
)
_NL_IP_PAIR_RE = re.compile(
    r"\bfrom\s+((?:\d{1,3}\.){3}\d{1,3})\s+to\s+((?:\d{1,3}\.){3}\d{1,3})\b",
    re.IGNORECASE,
)
_NL_PORT_RE = re.compile(r"\b(?:on\s+)?port\s+(\d{1,5})\b", re.IGNORECASE)
_NL_EVENT_CODE_RE = re.compile(r"\b(?:event\s*(?:id|code)|eventcode)\s*[=:]?\s*(\d{3,5})\b", re.IGNORECASE)
_NL_FUNCTION_CODE_RE = re.compile(
    r"\b(?:modbus|dnp3)?\s*function\s+code(?:s)?\s+((?:\d+\s*(?:or|/|,)\s*)*\d+)\b",
    re.IGNORECASE,
)
_NL_THRESHOLD_RE = re.compile(r"\bmore\s+than\s+(\d+)\b", re.IGNORECASE)
_NL_MULTI_INDEX_RE = re.compile(
    r"\b(?:look\s+)?across\s+([a-z0-9_,\s*-]+?)(?:\s+for|\s+on|\s+from|\s+to|\s+over|\s+in\b|$)",
    re.IGNORECASE,
)
_NL_ZONE_PAIR_RE = re.compile(
    r"\bfrom\s+([A-Za-z0-9][A-Za-z0-9 _.-]{0,63}?)\s+to\s+([A-Za-z0-9][A-Za-z0-9 _.-]{0,63}?)(?:\s+on\s+port|\s+over|\s+in\b|$)",
    re.IGNORECASE,
)
_NL_LOOKUP_RE = re.compile(r"\b([A-Za-z0-9_.-]+\.csv)\b", re.IGNORECASE)
_NL_PROTOCOL_RE = re.compile(r"\b(modbus(?:\s+tcp)?|dnp3|smb|dns|http|https)\b", re.IGNORECASE)
_NL_SERVICE_RE = re.compile(r"\b(smb|ssh|rdp|dns|http|https)\s+traffic\b", re.IGNORECASE)


def extract_natural_language_slots(user_query: str) -> dict[str, Any]:
    normalized = " ".join(user_query.split())
    slots: dict[str, Any] = {}

    search_index = _NL_SEARCH_INDEX_RE.search(normalized)
    if search_index:
        slots.setdefault("index", search_index.group(1).lower())

    for match in _NL_INDEX_RE.finditer(normalized):
        index = match.group(1) or match.group(2)
        if index:
            slots.setdefault("index", index.lower())

    multi = _NL_MULTI_INDEX_RE.search(normalized)
    if multi:
        parts = [part.strip().lower() for part in re.split(r"\s+and\s+|,", multi.group(1)) if part.strip()]
        if len(parts) > 1:
            slots["indexes"] = parts
            slots["index"] = parts[0]

    user = _NL_USER_RE.search(normalized)
    if user and "user" not in slots:
        slots["user"] = user.group(1)

    host = _NL_HOST_RE.search(normalized)
    if host and "host" not in slots:
        candidate = host.group(1)
        if not candidate.lower().startswith(("port", "the", "last")):
            slots["host"] = candidate

    ip_pair = _NL_IP_PAIR_RE.search(normalized)
    if ip_pair:
        slots["src_ip"] = ip_pair.group(1)
        slots["dest_ip"] = ip_pair.group(2)

    port = _NL_PORT_RE.search(normalized)
    if port and "port" not in slots:
        slots["port"] = port.group(1)

    event = _NL_EVENT_CODE_RE.search(normalized)
    if event:
        slots["event_code"] = event.group(1)

    func = _NL_FUNCTION_CODE_RE.search(normalized)
    if func:
        codes = [int(part) for part in re.findall(r"\d+", func.group(1))]
        if codes:
            slots["function_code"] = codes if len(codes) > 1 else str(codes[0])
            slots["protocol"] = "modbus" if "modbus" in normalized.lower() else slots.get("protocol")

    threshold = _NL_THRESHOLD_RE.search(normalized)
    if threshold:
        slots["threshold"] = threshold.group(1)
        slots["threshold_comparison"] = "greater_than"

    zone_pair = _NL_ZONE_PAIR_RE.search(normalized)
    if zone_pair and not ip_pair:
        left, right = zone_pair.group(1), zone_pair.group(2)
        if not re.match(r"(?:\d{1,3}\.){3}\d{1,3}$", left):
            slots["src_zone"] = left
            slots["dest_zone"] = right

    lookup = _NL_LOOKUP_RE.search(normalized)
    if lookup:
        slots["lookup"] = lookup.group(1)

    protocols_found: list[str] = []
    if re.search(r"\bmodbus(?:\s+tcp)?\b", normalized, re.I):
        protocols_found.append("modbus")
    if re.search(r"\bdnp3\b", normalized, re.I):
        protocols_found.append("dnp3")
    if len(protocols_found) == 1:
        slots["protocol"] = protocols_found[0]
    elif len(protocols_found) > 1:
        slots["protocols"] = protocols_found

    service = _NL_SERVICE_RE.search(normalized)
    if service:
        slots["service"] = service.group(1).lower()

    if "unexpected" in normalized.lower() and "ip" in normalized.lower():
        if "destination" in normalized.lower() or "target" in normalized.lower():
            slots["unexpected_ip_direction"] = "destination"
        elif "source" in normalized.lower():
            slots["unexpected_ip_direction"] = "source"
        else:
            slots["unexpected_ip_direction"] = "destination"
        slots["allowlist_semantic"] = "unexpected_destination_ip"

    if re.search(r"\b(permits?|allow|allowed)\b", normalized, re.I):
        slots["action_semantic"] = "permit"

    if re.search(r"\bfailed\s+login", normalized, re.I):
        slots["action_semantic"] = slots.get("action_semantic", "failed_login")

    from app.query_understanding.time_window import normalize_time_window

    tw = normalize_time_window(normalized)
    if tw and "time_window" not in slots:
        slots["time_window"] = tw

    if re.search(r"\bfrom\s+substation\s+subnet", normalized, re.I):
        slots["src_scope"] = "substation_subnet"
    elif re.search(r"\bto\s+substation\s+subnet", normalized, re.I):
        slots["dest_scope"] = "substation_subnet"
    elif re.search(r"\bsubstation\s+subnet", normalized, re.I) and "src_scope" not in slots and "dest_scope" not in slots:
        if re.search(r"\bfrom\b", normalized, re.I):
            slots["src_scope"] = "substation_subnet"
        elif re.search(r"\bto\b", normalized, re.I):
            slots["dest_scope"] = "substation_subnet"

    if re.search(r"\busers?\s+with\b", normalized, re.I):
        slots.setdefault("aggregation_subject", "user")
    elif re.search(r"\bhosts?\s+with\b", normalized, re.I):
        slots.setdefault("aggregation_subject", "host")

    return slots


def extract_query_slots(user_query: str) -> dict[str, Any]:
    normalized = " ".join(user_query.split())
    slots: dict[str, Any] = {}

    host = _first_capture(_HOST_SLOT_RE.search(normalized))
    if host is not None:
        slots["host"] = host

    user = _first_capture(_USER_SLOT_RE.search(normalized))
    if user is not None:
        slots["user"] = user

    alert_id = _extract_alert_id(normalized)
    if alert_id is not None:
        slots["alert_id"] = alert_id

    index_match = _INDEX_SLOT_RE.search(normalized)
    if index_match:
        slots["index"] = index_match.group(1)

    sourcetype_match = _SOURCETYPE_SLOT_RE.search(normalized)
    if sourcetype_match:
        slots["sourcetype"] = sourcetype_match.group(1)

    ip_match = _IP_SLOT_RE.search(normalized)
    if ip_match:
        ip_value = _first_capture(ip_match)
        key = "src_ip" if re.search(r"\bsrc(?:_ip)?=", normalized, re.IGNORECASE) else "dest_ip"
        slots[key] = ip_value

    cidr_match = _CIDR_SLOT_RE.search(normalized)
    if cidr_match:
        slots["cidr"] = cidr_match.group(1)

    port_match = _PORT_SLOT_RE.search(normalized)
    if port_match:
        slots["port"] = port_match.group(1)

    threshold_match = _THRESHOLD_RE.search(normalized)
    if threshold_match:
        slots["threshold"] = threshold_match.group(1)

    top_n_match = _TOP_N_RE.search(normalized.lower())
    if top_n_match:
        slots["result_limit"] = top_n_match.group(1)

    if any(token in normalized.lower() for token in ("last 24 hours", "last 24h", "past 24 hours", "24 hours")):
        slots["time_window"] = "earliest=-24h latest=now"
    elif "last hour" in normalized.lower() or "last 1 hour" in normalized.lower():
        slots["time_window"] = "earliest=-1h latest=now"

    return slots


def validate_slot_map(
    slots: dict[str, Any],
    *,
    allowed_indexes: tuple[str, ...] | None = None,
    allowed_sourcetypes: tuple[str, ...] | None = None,
    policy: SplValidationPolicy | None = None,
    slot_source: str = "user",
) -> SlotValidationOutcome:
    policy = policy or load_slot_binding_policy()
    allowed_indexes = allowed_indexes or policy.allowed_indexes
    allowed_sourcetypes = allowed_sourcetypes or policy.allowed_sourcetypes
    reject_reasons: list[str] = []
    warnings: list[str] = []
    normalized: dict[str, str] = {}

    for slot_type, raw_value in slots.items():
        if slot_type not in SLOT_TYPES:
            reject_reasons.append(f"unsupported_slot:{slot_type}")
            continue
        if slot_type == "protocols" and isinstance(raw_value, list):
            normalized["protocols"] = ",".join(str(item).lower() for item in raw_value)
            continue
        if slot_type == "function_code" and isinstance(raw_value, list):
            normalized["function_code"] = ",".join(str(item) for item in raw_value)
            continue
        if slot_type == "indexes":
            raw_parts = raw_value if isinstance(raw_value, list) else [
                part.strip() for part in str(raw_value).split(",") if part.strip()
            ]
            accepted, index_errors = _validate_indexes_list(
                raw_parts,
                allowed_indexes=allowed_indexes,
            )
            if accepted:
                normalized["indexes"] = ",".join(accepted)
            if index_errors:
                reject_reasons.extend(index_errors)
            if not accepted:
                reject_reasons.append("slot_indexes_all_rejected")
            continue
        value, slot_errors = validate_slot_value(
            slot_type,
            raw_value,
            allowed_indexes=allowed_indexes,
            allowed_sourcetypes=allowed_sourcetypes,
            policy=policy,
        )
        if slot_errors:
            reject_reasons.extend(slot_errors)
            continue
        if value is None:
            reject_reasons.append(f"slot_validation_failed:{slot_type}")
            continue
        normalized[slot_type] = value

    if slot_source == "llm" and reject_reasons:
        reject_reasons.append("llm_slot_rejected")

    return SlotValidationOutcome(
        valid=not reject_reasons,
        normalized_slots=normalized,
        reject_reasons=sorted(set(reject_reasons)),
        warnings=sorted(set(warnings)),
    )




def _normalize_scope_label(text: str) -> str | None:
    lowered = str(text).strip().lower().replace(" ", "_")
    if lowered in {"substation_subnet", "substation_subnets"}:
        return "substation_subnet"
    if not _RULE_APP_PATTERN.fullmatch(lowered):
        return None
    return lowered

def validate_slot_value(
    slot_type: str,
    value: Any,
    *,
    allowed_indexes: tuple[str, ...],
    allowed_sourcetypes: tuple[str, ...],
    policy: SplValidationPolicy,
) -> tuple[str | None, list[str]]:
    if value is None:
        return None, [f"slot_empty:{slot_type}"]

    text = str(value).strip()
    if not text:
        return None, [f"slot_empty:{slot_type}"]
    if _INJECTION_PATTERN.search(text):
        return None, [f"slot_injection_blocked:{slot_type}"]

    if slot_type in {"host", "alert_id"}:
        pattern = _HOST_PATTERN if slot_type == "host" else _ALERT_ID_PATTERN
        if not pattern.fullmatch(text):
            return None, [f"slot_pattern_invalid:{slot_type}"]
        return escape_spl_quoted_string(text), []

    if slot_type == "user":
        if not _USER_PATTERN.fullmatch(text):
            return None, [f"slot_pattern_invalid:user"]
        return escape_spl_quoted_string(text), []

    if slot_type in {"src_ip", "dest_ip"}:
        if not _valid_ip(text):
            return None, [f"slot_ip_invalid:{slot_type}"]
        return text, []

    if slot_type in {"cidr", "approved_source_cidr", "approved_destination_cidr"}:
        if not _valid_cidr(text):
            return None, [f"slot_cidr_invalid:{slot_type}"]
        return text, []

    if slot_type == "index":
        lowered = text.lower()
        if not _INDEX_PATTERN.fullmatch(text) or lowered not in allowed_indexes:
            return None, ["slot_index_not_allowlisted"]
        return lowered, []

    if slot_type == "sourcetype":
        lowered = text.lower()
        if not _SOURCETYPE_PATTERN.fullmatch(text) or lowered not in allowed_sourcetypes:
            return None, ["slot_sourcetype_not_allowlisted"]
        return lowered, []

    if slot_type == "port":
        if not str(text).isdigit():
            return None, ["slot_port_not_numeric"]
        port = int(text)
        if port < 1 or port > 65535:
            return None, ["slot_port_out_of_range"]
        return str(port), []

    if slot_type in {"threshold", "result_limit"}:
        if not str(text).isdigit():
            return None, [f"slot_{slot_type}_not_numeric"]
        number = int(text)
        if number < 1:
            return None, [f"slot_{slot_type}_out_of_range"]
        if slot_type == "result_limit" and number > policy.max_result_limit:
            return None, ["slot_result_limit_exceeds_policy"]
        return str(number), []

    if slot_type == "time_window":
        normalized_window = _normalize_time_window(text)
        if normalized_window is None:
            return None, ["slot_time_window_unbounded"]
        return normalized_window, []

    if slot_type in {"earliest", "latest"}:
        token = text if _TIME_TOKEN_PATTERN.search(text) else f"{slot_type}={text}"
        if slot_type == "earliest" and not token.lower().startswith("earliest=-") and token.lower() != "earliest=0":
            if not _RELATIVE_TIME_PATTERN.fullmatch(text):
                return None, ["slot_time_window_unbounded"]
            token = f"earliest={text}"
        if slot_type == "latest" and not token.lower().startswith("latest="):
            token = f"latest={text}"
        if _INJECTION_PATTERN.search(token):
            return None, [f"slot_injection_blocked:{slot_type}"]
        return token, []

    if slot_type == "zone":
        if not _ZONE_PATTERN.fullmatch(text):
            return None, ["slot_pattern_invalid:zone"]
        return escape_spl_quoted_string(text), []

    if slot_type in {"rule_name", "application_protocol"}:
        if not _RULE_APP_PATTERN.fullmatch(text):
            return None, [f"slot_pattern_invalid:{slot_type}"]
        return escape_spl_quoted_string(text), []

    if slot_type == "country":
        if not _COUNTRY_PATTERN.fullmatch(text):
            return None, ["slot_pattern_invalid:country"]
        return text.upper(), []

    if slot_type in {"protocol",
        "protocols", "service", "action_semantic", "unexpected_ip_direction", "allowlist_semantic", "threshold_comparison"}:
        if not _RULE_APP_PATTERN.fullmatch(text.replace(" ", "_")):
            return escape_spl_quoted_string(text), []
        return text.lower(), []

    if slot_type in {"src_scope", "dest_scope", "aggregation_subject"}:
        normalized_scope = _normalize_scope_label(text)
        if normalized_scope is None:
            return escape_spl_quoted_string(text), []
        return normalized_scope, []

    if slot_type in {"src_zone", "dest_zone"}:
        if not _ZONE_PATTERN.fullmatch(text):
            return None, [f"slot_pattern_invalid:{slot_type}"]
        return escape_spl_quoted_string(text), []

    if slot_type == "event_code":
        if not str(text).isdigit():
            return None, ["slot_event_code_not_numeric"]
        return str(text), []

    if slot_type == "function_code":
        return str(text), []

    if slot_type in {"lookup", "approved_destination_lookup", "substation_mapping_lookup"}:
        if not re.fullmatch(r"[A-Za-z0-9_.-]+\.csv", text, re.I):
            return None, [f"slot_lookup_invalid:{slot_type}"]
        return text, []

    if slot_type in {"src_ip_field", "dest_ip_field", "function_code_field"}:
        if not _FIELD_PATTERN.fullmatch(text):
            return None, [f"slot_field_invalid:{slot_type}"]
        return text, []

    if slot_type == "indexes":
        return None, ["slot_indexes_must_be_validated_as_collection"]

    return None, [f"unsupported_slot:{slot_type}"]


def _validate_indexes_list(
    parts: list[Any],
    *,
    allowed_indexes: tuple[str, ...],
) -> tuple[list[str], list[str]]:
    accepted: list[str] = []
    errors: list[str] = []
    for part in parts:
        text = str(part).strip()
        if not text:
            continue
        lowered = text.lower()
        if not _INDEX_PATTERN.fullmatch(text):
            errors.append(f"slot_pattern_invalid:indexes:{lowered}")
            continue
        if lowered not in allowed_indexes:
            errors.append(f"slot_index_not_allowlisted:{lowered}")
            continue
        if lowered not in accepted:
            accepted.append(lowered)
    return accepted, errors


def validate_render_bindings(
    bindings: dict[str, Any],
    *,
    template: SplTemplateDefinition | None = None,
    policy: SplValidationPolicy | None = None,
) -> list[str]:
    """Validate renderer binding map; returns reject reason codes."""
    allowed_indexes = _template_allowed_indexes(template, policy)
    allowed_sourcetypes = _template_allowed_sourcetypes(template, policy)
    outcome = validate_slot_map(
        bindings,
        allowed_indexes=allowed_indexes,
        allowed_sourcetypes=allowed_sourcetypes,
        policy=policy,
    )
    if outcome.valid:
        return []
    return outcome.reject_reasons


def _template_allowed_indexes(
    template: SplTemplateDefinition | None,
    policy: SplValidationPolicy | None,
) -> tuple[str, ...]:
    policy = policy or load_slot_binding_policy()
    rules = template.validation_rules if template is not None else {}
    if isinstance(rules, dict):
        raw = rules.get("allowed_indexes")
        if isinstance(raw, list) and raw:
            return tuple(str(item).lower() for item in raw)
    return policy.allowed_indexes


def _template_allowed_sourcetypes(
    template: SplTemplateDefinition | None,
    policy: SplValidationPolicy | None,
) -> tuple[str, ...]:
    policy = policy or load_slot_binding_policy()
    rules = template.validation_rules if template is not None else {}
    if isinstance(rules, dict):
        raw = rules.get("allowed_sourcetypes")
        if isinstance(raw, list) and raw:
            return tuple(str(item).lower() for item in raw)
    return policy.allowed_sourcetypes


def _valid_ip(value: str) -> bool:
    try:
        ipaddress.ip_address(value)
        return True
    except ValueError:
        return False


def _valid_cidr(value: str) -> bool:
    try:
        ipaddress.ip_network(value, strict=False)
        return True
    except ValueError:
        return False


def _normalize_time_window(value: str) -> str | None:
    text = " ".join(value.split())
    lower = text.lower()
    if any(token in lower for token in ("last 24 hours", "last 24h", "past 24 hours", "24 hours")):
        return "earliest=-24h latest=now"
    if "last hour" in lower or "last 1 hour" in lower:
        return "earliest=-1h latest=now"
    if any(token in lower for token in ("last 7 days", "past 7 days", "7 days")):
        return "earliest=-7d latest=now"
    if any(token in lower for token in ("30 minutes", "last 30 minutes", "past 30 minutes")):
        return "earliest=-30m latest=now"
    if _EARLIEST_LATEST_PAIR.fullmatch(text):
        return text
    if text in {"earliest=-24h latest=now", "earliest=-1h latest=now", "earliest=-60m latest=now"}:
        return text
    if _RELATIVE_TIME_PATTERN.fullmatch(text):
        return f"earliest={text} latest=now"
    if lower in {"now", "all", "0", "earliest=0"}:
        return None
    return None


def _first_capture(match: re.Match[str] | None) -> str | None:
    if match is None:
        return None
    for group in match.groups():
        if group:
            return group.strip()
    return None


def _extract_alert_id(query: str) -> str | None:
    match = _ALERT_ID_RE.search(query)
    if not match:
        return None
    return match.group(1).strip()
