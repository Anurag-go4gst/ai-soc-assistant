"""Canonical SPL intent spec — reuse pre-parse + user bindings, no duplicate planner.

Final RQC remains semantic request authority. This module evolves the existing
dict contract returned by ``build_spl_intent_spec()``; call sites keep receiving
a plain ``dict``. Typed helpers below are serialization internals, not a second
semantic-authority system.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Mapping

from app.spl.t2_pre_parse import pre_parse_spl_tokens
from app.spl.user_constraint_bindings import build_user_constraint_bindings

SPL_SEMANTIC_CONTRACT_VERSION = "spl_semantic_v2"

SUPPORTED_ANALYSIS_SHAPES: tuple[str, ...] = (
    "raw",
    "aggregation",
    "ranking",
    "trend",
    "rolling",
    "sequence",
)
UNSUPPORTED_ANALYSIS_SHAPES: tuple[str, ...] = ("comparison",)

ANALYTICAL_WINDOW_KINDS: tuple[str, ...] = ("fixed", "rolling", "sequence")
ENTITY_ROLE_NAMES: tuple[str, ...] = (
    "subject",
    "target",
    "correlate_by",
    "group_by",
    "distinct_by",
)

_FIREWALL_RE = re.compile(r"\bfirewall\b", re.I)
# Do NOT match bare "block" — "SPL block" / "code block" are authoring nouns, not deny actions.
_DENIED_RE = re.compile(
    r"\b(denied|deny|blocked|drop|reject)\b|"
    r"\bblock\s+(?:all|this|the|ip|user|account|traffic|source|suspicious|firewall)\b",
    re.I,
)
_SRC_IP_RE = re.compile(r"\b(source\s+ips?|src[_\s]?ips?|by\s+src|one\s+source(?:\s+ip)?)\b", re.I)
_DEST_IP_RE = re.compile(r"\b(dest(?:ination)?\s+ips?|dst[_\s]?ips?|target\s+ips?)\b", re.I)
_TOP_RE = re.compile(r"\btop\b|\bhighest\b|\brank(?:ed|ing)?\b", re.I)
_ALL_LOGS_RE = re.compile(r"\ball\b.*\b(logs?|events?|traffic)\b", re.I)
_REVIEW_ONLY_RE = re.compile(r"\b(review[\s-]?only|do not execute|don't execute|not execute)\b", re.I)
_SPL_ONLY_RE = re.compile(r"\b(only\s+(an?\s+)?spl|spl\s+(query|command|only))\b", re.I)
_TREND_RE = re.compile(r"\b(trend|time[\s-]?series|over\s+time|histogram)\b", re.I)
_ROLLING_RE = re.compile(
    r"\b(?:rolling|sliding)\b.{0,32}?(\d+)\s*-?\s*(seconds?|sec|minutes?|mins?|min|hours?|hrs?|hr|days?|[smhd])\b"
    r"|\b(\d+)\s*-?\s*(seconds?|sec|minutes?|mins?|min|hours?|hrs?|hr|days?|[smhd])\s+"
    r"(?:rolling|sliding)\s+window\b",
    re.I,
)
_GRAIN_RE = re.compile(
    r"\b(hourly|daily|weekly|minutely)\b|"
    r"\b(?:every|per|by|each)\s+(\d+)?\s*(seconds?|minutes?|hours?|days?|hour|minute|day)\b|"
    r"\bspan\s*=\s*(\d+[smhd])\b",
    re.I,
)
_SEQUENCE_GAP_RE = re.compile(
    r"\b(?:within|inside|in)\s+(\d+)\s*-?\s*(seconds?|sec|minutes?|mins?|min|hours?|hrs?|hr|[smhd])\b",
    re.I,
)
_SEQUENCE_SPLIT_RE = re.compile(
    r"\bfollowed\s+by\b|\bthen\b|\bafter\s+(?:which|that)\b|\bbefore\b",
    re.I,
)
_COMPARISON_RE = re.compile(
    r"\b(?:same|versus|vs\.?|compared\s+to|compared\s+with|relative\s+to)\b.+"
    r"\b(?:last\s+(?:month|week|year|quarter)|previous\s+(?:month|week|year|period)|baseline|campaign)\b|"
    r"\bsame\s+campaign\b",
    re.I,
)
_DISTINCT_ENTITY_RE = re.compile(
    r"\b(?:distinct|unique|different|multiple)\s+"
    r"(accounts?|users?|usernames?|hosts?|hostnames?|ips?|destinations?|targets?)\b",
    re.I,
)
_COUNT_RE = re.compile(r"\b(how\s+many|count\s+of|number\s+of|volume)\b", re.I)
_THRESHOLD_RE = re.compile(
    r"\b(?:at\s+least|more\s+than|greater\s+than|over|threshold(?:\s+of)?|at\s+least)\s+(\d+)\b",
    re.I,
)
_DURATION_UNIT = {
    "s": "s",
    "sec": "s",
    "secs": "s",
    "second": "s",
    "seconds": "s",
    "m": "m",
    "min": "m",
    "mins": "m",
    "minute": "m",
    "minutes": "m",
    "h": "h",
    "hr": "h",
    "hrs": "h",
    "hour": "h",
    "hours": "h",
    "d": "d",
    "day": "d",
    "days": "d",
}

_EVENT_TYPE_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\b(failed[\s-]?log(?:in|on)s?|log(?:in|on)\s+fail(?:ure|ed)s?|authentication\s+fail(?:ure|ed)|4625)\b", re.I), "failed_login"),
    (re.compile(r"\b(successful[\s-]?log(?:in|on)s?|log(?:in|on)\s+success(?:ful|es)?|4624)\b", re.I), "successful_login"),
    (re.compile(r"\b(password[\s-]?change|password[\s-]?reset|password[\s-]?modif(?:y|ication)|4723|4724)\b", re.I), "password_change"),
    (re.compile(r"\b(account\s+lockouts?|4740)\b", re.I), "account_lockout"),
    (re.compile(r"\b(privilege(?:d)?\s+(?:group\s+)?change|4728|4732|4756)\b", re.I), "privilege_change"),
    (re.compile(r"\b(denied|blocked|drop(?:ped)?)\s+(?:traffic|connections?|packets?)\b", re.I), "denied_traffic"),
)

_ENTITY_ALIAS = {
    "account": "user",
    "accounts": "user",
    "user": "user",
    "users": "user",
    "username": "user",
    "usernames": "user",
    "host": "host",
    "hosts": "host",
    "hostname": "host",
    "hostnames": "host",
    "ip": "src_ip",
    "ips": "src_ip",
    "destination": "dest_ip",
    "destinations": "dest_ip",
    "target": "dest_ip",
    "targets": "dest_ip",
}

_USER_NORM_ALIASES = ("user", "username", "src_user", "Account_Name", "TargetUserName")
_SRC_IP_NORM_ALIASES = ("src_ip", "src", "source", "source_ip", "Source_Network_Address")
_DEST_IP_NORM_ALIASES = ("dest_ip", "dest", "destination", "dst")


@dataclass
class _AnalyticalWindow:
    kind: str
    size: str | None = None
    provenance: str = "query_token"

    def to_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "size": self.size, "provenance": self.provenance}


@dataclass
class _EntityRoles:
    subject: list[str] = field(default_factory=list)
    target: list[str] = field(default_factory=list)
    correlate_by: list[str] = field(default_factory=list)
    group_by: list[str] = field(default_factory=list)
    distinct_by: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, list[str]]:
        return {
            "subject": list(self.subject),
            "target": list(self.target),
            "correlate_by": list(self.correlate_by),
            "group_by": list(self.group_by),
            "distinct_by": list(self.distinct_by),
        }


def _duration_token(amount: str | int, unit: str) -> str | None:
    suffix = _DURATION_UNIT.get(str(unit or "").strip().lower())
    if not suffix:
        return None
    try:
        value = int(amount)
    except (TypeError, ValueError):
        return None
    if value <= 0:
        return None
    return f"{value}{suffix}"


def _parse_time_scope_to_window(value: str | None) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    if "earliest=" in text.lower():
        return text
    lowered = text.lower().lstrip("-")
    match = re.fullmatch(r"(\d+)\s*([smhdwy]|seconds?|minutes?|hours?|days?|weeks?)", lowered)
    if match:
        token = _duration_token(match.group(1), match.group(2))
        if token:
            return f"earliest=-{token} latest=now"
    relative = re.search(
        r"\b(?:last|past|previous)\s+(\d+)\s*(seconds?|minutes?|hours?|days?|weeks?|[smhdw])\b",
        text,
        re.I,
    )
    if relative:
        token = _duration_token(relative.group(1), relative.group(2))
        if token:
            return f"earliest=-{token} latest=now"
    return text


def _time_window_from_tokens(tokens: Any, bindings: Any) -> str | None:
    if bindings.explicit_time_window:
        return str(bindings.explicit_time_window)
    if tokens.earliest:
        latest = tokens.latest or "now"
        return f"earliest={tokens.earliest} latest={latest}"
    if tokens.relative_windows:
        window = tokens.relative_windows[0]
        return f"earliest=-{window} latest=now"
    slots = bindings.normalized_slots or {}
    earliest = str(slots.get("earliest") or "").strip()
    latest = str(slots.get("latest") or "now").strip()
    if earliest:
        return f"earliest={earliest} latest={latest}"
    time_window = str(slots.get("time_window") or "").strip()
    return time_window or None


def _event_domain(query: str, tokens: Any) -> str | None:
    lowered = (query or "").lower()
    if _FIREWALL_RE.search(lowered):
        return "firewall"
    if any(token in lowered for token in ("dns", "domain name")):
        return "dns"
    if any(token in lowered for token in ("auth", "login", "logon", "password", "account")):
        return "authentication"
    if any(token in lowered for token in ("vpn", "remote access")):
        return "vpn"
    if "endpoint" in lowered or "edr" in lowered:
        return "endpoint"
    if tokens.operation_hints:
        return str(tokens.operation_hints[0])
    return None


def _rolling_window(query: str) -> str | None:
    match = _ROLLING_RE.search(query or "")
    if not match:
        return None
    amount = match.group(1) or match.group(3)
    unit = match.group(2) or match.group(4)
    return _duration_token(amount, unit)


def _temporal_grain(query: str) -> str | None:
    match = _GRAIN_RE.search(query or "")
    if not match:
        return None
    named = (match.group(1) or "").lower()
    if named == "hourly":
        return "1h"
    if named == "daily":
        return "1d"
    if named == "weekly":
        return "1w"
    if named == "minutely":
        return "1m"
    span = match.group(4)
    if span:
        return span.lower()
    amount = match.group(2) or "1"
    unit = match.group(3) or ""
    return _duration_token(amount, unit)


def _sequence_gap(query: str) -> str | None:
    match = _SEQUENCE_GAP_RE.search(query or "")
    if not match:
        return None
    return _duration_token(match.group(1), match.group(2))


def _required_event_sets(query: str) -> list[str]:
    found: list[str] = []
    for pattern, name in _EVENT_TYPE_PATTERNS:
        if pattern.search(query or "") and name not in found:
            found.append(name)
    return found


def _ordered_sequence(query: str, event_sets: list[str]) -> list[str]:
    if not _SEQUENCE_SPLIT_RE.search(query or ""):
        return []
    parts = _SEQUENCE_SPLIT_RE.split(query or "", maxsplit=1)
    if len(parts) < 2:
        return list(event_sets)
    left = _required_event_sets(parts[0])
    right = _required_event_sets(parts[1])
    ordered: list[str] = []
    for item in [*left, *right]:
        if item not in ordered:
            ordered.append(item)
    return ordered or list(event_sets)


def _is_comparison(query: str) -> bool:
    return bool(_COMPARISON_RE.search(query or ""))


def _analysis_shape(
    query: str,
    *,
    tokens: Any,
    rolling: str | None,
    grain: str | None,
    sequence_events: list[str],
    aggregations: list[str],
    filters: list[str],
) -> str:
    if _is_comparison(query):
        return "comparison"
    if sequence_events or "sequence_detection" in (tokens.operation_hints or []):
        return "sequence"
    if rolling:
        return "rolling"
    if grain or _TREND_RE.search(query or ""):
        return "trend"
    if _TOP_RE.search(query or "") or "aggregate_and_rank" in (tokens.operation_hints or []):
        return "ranking"
    if aggregations or _COUNT_RE.search(query or ""):
        return "aggregation"
    if "all_events_no_action_filter" in filters or _ALL_LOGS_RE.search(query or ""):
        return "raw"
    return "raw"


def _output_shape_for(analysis_shape: str) -> str:
    return {
        "raw": "events",
        "aggregation": "aggregate_table",
        "ranking": "ranked_table",
        "trend": "time_series",
        "rolling": "windowed_table",
        "sequence": "sequence_matches",
        "comparison": "comparison_table",
    }.get(analysis_shape, "events")


def _append_unique(items: list[str], value: str | None) -> None:
    token = str(value or "").strip()
    if token and token not in items:
        items.append(token)


def _entity_roles(
    query: str,
    *,
    tokens: Any,
    group_by: list[str],
) -> _EntityRoles:
    roles = _EntityRoles(group_by=list(group_by))
    if _SRC_IP_RE.search(query or "") or "src_ip" in group_by:
        _append_unique(roles.subject, "src_ip")
        _append_unique(roles.group_by, "src_ip")
        _append_unique(roles.correlate_by, "src_ip")
    if _DEST_IP_RE.search(query or ""):
        _append_unique(roles.target, "dest_ip")
    distinct = _DISTINCT_ENTITY_RE.search(query or "")
    if distinct:
        entity = _ENTITY_ALIAS.get(distinct.group(1).lower(), distinct.group(1).lower())
        _append_unique(roles.distinct_by, entity)
        if entity not in roles.subject:
            _append_unique(roles.target, entity)
    for field_name in tokens.fields:
        if field_name in {"user", "src_ip", "dest_ip", "host"} and field_name not in roles.group_by:
            _append_unique(roles.group_by, field_name)
    return roles


def _relationships(roles: _EntityRoles, analysis_shape: str) -> list[dict[str, str]]:
    rels: list[dict[str, str]] = []
    if roles.subject and roles.distinct_by:
        rels.append(
            {
                "type": "distinct_count",
                "subject": roles.subject[0],
                "object": roles.distinct_by[0],
                "measure": f"dc({roles.distinct_by[0]})",
            }
        )
    if analysis_shape == "sequence" and roles.correlate_by:
        rels.append(
            {
                "type": "ordered_sequence",
                "subject": roles.correlate_by[0],
                "object": "event_sequence",
                "measure": "sequence_match",
            }
        )
    return rels


def _measures(
    *,
    analysis_shape: str,
    aggregations: list[str],
    roles: _EntityRoles,
    event_sets: list[str],
) -> list[dict[str, str]]:
    measures: list[dict[str, str]] = []
    if roles.distinct_by:
        for entity in roles.distinct_by:
            measures.append({"name": f"distinct_{entity}", "fn": "dc", "field": entity})
    if analysis_shape in {"aggregation", "ranking", "trend"} or aggregations:
        target = event_sets[0] if event_sets else "event"
        measures.append({"name": f"{target}_count", "fn": "count", "field": "_time"})
    if analysis_shape == "sequence":
        measures.append({"name": "sequence_match", "fn": "transaction_or_join", "field": "_time"})
    return measures


def _normalization_for(roles: _EntityRoles) -> tuple[list[dict[str, Any]], list[str]]:
    requirements: list[dict[str, Any]] = []
    consumers: list[str] = []
    needed = set(roles.group_by + roles.distinct_by + roles.subject + roles.correlate_by)
    if "user" in needed:
        requirements.append(
            {
                "alias": "user_norm",
                "expression": "lower(coalesce(user, username, src_user, Account_Name, TargetUserName, \"unknown\"))",
                "source_fields": list(_USER_NORM_ALIASES),
            }
        )
        consumers.extend(["filter", "grouping", "distinct", "correlation", "sequence"])
    if "src_ip" in needed:
        requirements.append(
            {
                "alias": "src_ip_norm",
                "expression": "coalesce(src_ip, src, source, source_ip, Source_Network_Address, \"unknown\")",
                "source_fields": list(_SRC_IP_NORM_ALIASES),
            }
        )
        consumers.extend(["filter", "grouping", "correlation"])
    if "dest_ip" in needed:
        requirements.append(
            {
                "alias": "dest_ip_norm",
                "expression": "coalesce(dest_ip, dest, destination, dst, \"unknown\")",
                "source_fields": list(_DEST_IP_NORM_ALIASES),
            }
        )
        consumers.extend(["filter", "grouping"])
    # Unique preserve order
    seen: set[str] = set()
    unique_consumers: list[str] = []
    for item in consumers:
        if item not in seen:
            seen.add(item)
            unique_consumers.append(item)
    return requirements, unique_consumers


def _prohibitions(
    *,
    analysis_shape: str,
    result_limit: int | None,
    search_horizon: str | None,
    explicit_threshold: bool,
    filters: list[str] | None = None,
) -> list[str]:
    bans: list[str] = []
    all_events = "all_events_no_action_filter" in (filters or [])
    if result_limit is None and (
        analysis_shape in {"trend", "rolling", "sequence"} or all_events
    ):
        bans.append("arbitrary_head_100")
        bans.append("arbitrary_truncation")
    if analysis_shape == "raw":
        bans.append("mandatory_aggregation")
    if analysis_shape in {"trend", "rolling"}:
        bans.append("time_series_truncation")
    if analysis_shape == "rolling":
        bans.append("rolling_window_loss")
    if analysis_shape == "sequence":
        bans.append("sequence_ordering_loss")
        bans.append("sequence_gap_loss")
    if analysis_shape == "trend":
        bans.append("temporal_grain_loss")
        bans.append("implicit_default_24h_overwrite")
    if search_horizon:
        bans.append("implicit_default_24h_overwrite")
    if not explicit_threshold:
        bans.append("unexpected_threshold_invention")
    if analysis_shape != "ranking":
        bans.append("alert_template_bias")
    bans.append("normalized_field_unused")
    bans.append("placeholder_despite_governed_mapping")
    bans.append("generic_coalesce_ignoring_source_profile")
    return bans


def _as_mapping(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if hasattr(value, "model_dump"):
        dumped = value.model_dump()
        return dumped if isinstance(dumped, dict) else {}
    if hasattr(value, "to_dict"):
        dumped = value.to_dict()
        return dumped if isinstance(dumped, dict) else {}
    if isinstance(value, Mapping):
        return dict(value)
    return {}


def _fill_blank(
    target: dict[str, Any],
    key: str,
    value: Any,
    provenance: dict[str, str],
    source: str,
    *,
    provenance_key: str | None = None,
) -> None:
    if value in (None, "", [], {}):
        return
    current = target.get(key)
    if current in (None, "", [], {}):
        target[key] = value
        provenance[provenance_key or key] = source


def _locked_rqc_fields(rqc: dict[str, Any]) -> dict[str, Any]:
    locked = rqc.get("locked_fields")
    return dict(locked) if isinstance(locked, dict) else {}


def build_spl_intent_spec(
    user_query: str,
    *,
    resolved_query_contract: Mapping[str, Any] | Any | None = None,
    explicit_constraints: Mapping[str, Any] | Any | None = None,
    source_mappings: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Project analyst SPL semantics for LLM prompts and fidelity validation.

    Precedence (deterministic): locked Final RQC > explicit user constraints >
    query tokens > governed source mappings filling blanks only. Raw query text
    never independently overrides locked RQC semantics.
    """
    query = str(user_query or "").strip()
    tokens = pre_parse_spl_tokens(query)
    bindings = build_user_constraint_bindings(query)
    rqc = _as_mapping(resolved_query_contract)
    explicit = _as_mapping(explicit_constraints)
    sources = _as_mapping(source_mappings)
    provenance: dict[str, str] = {}
    locked = _locked_rqc_fields(rqc)

    filters: list[str] = []
    if _DENIED_RE.search(query):
        filters.append("denied_traffic")
    if bindings.explicit_action_semantics:
        filters.extend(str(item) for item in bindings.explicit_action_semantics)
    if _ALL_LOGS_RE.search(query) and not filters:
        filters.append("all_events_no_action_filter")

    group_by: list[str] = []
    if _SRC_IP_RE.search(query):
        group_by.append("src_ip")
        provenance["group_by.src_ip"] = "query_token"
    for field_name in tokens.fields:
        if field_name not in group_by:
            group_by.append(field_name)
            provenance.setdefault(f"group_by.{field_name}", "query_token")

    aggregations: list[str] = []
    ordering: list[str] = []
    ranking: dict[str, Any] | None = None
    if tokens.operation_hints and "aggregate_and_rank" in tokens.operation_hints:
        aggregations.append("count")
        ordering.append("descending")
        ranking = {"direction": "desc", "metric": "count"}
    elif _TOP_RE.search(query):
        aggregations.append("count")
        ordering.append("descending")
        ranking = {"direction": "desc", "metric": "count"}

    result_limit: int | None = None
    if bindings.normalized_slots.get("result_limit"):
        try:
            result_limit = int(str(bindings.normalized_slots["result_limit"]))
        except ValueError:
            result_limit = None
    elif _ALL_LOGS_RE.search(query) and not _TOP_RE.search(query):
        result_limit = None  # analyst did not ask to truncate

    execution_posture = "review_only"
    if _REVIEW_ONLY_RE.search(query) or _SPL_ONLY_RE.search(query):
        execution_posture = "review_only_no_execution"

    analyst_constraints: list[str] = []
    if _REVIEW_ONLY_RE.search(query):
        analyst_constraints.append("do_not_execute")
    if _SPL_ONLY_RE.search(query):
        analyst_constraints.append("spl_artifact_only")

    query_time_window = _time_window_from_tokens(tokens, bindings)
    rolling = _rolling_window(query)
    grain = _temporal_grain(query)
    event_sets = _required_event_sets(query)
    sequence_events = _ordered_sequence(query, event_sets)
    sequence_gap = _sequence_gap(query) if sequence_events or "sequence_detection" in (tokens.operation_hints or []) else None

    rqc_time = _parse_time_scope_to_window(
        str(locked.get("time_scope") or rqc.get("time_scope") or "").strip() or None
    )
    explicit_time = _parse_time_scope_to_window(
        str(explicit.get("time_window") or explicit.get("time_scope") or "").strip() or None
    )
    if rqc_time:
        search_horizon = rqc_time
        provenance["search_horizon"] = "rqc_locked" if locked.get("time_scope") or "time_scope" in locked else "rqc"
    elif explicit_time:
        search_horizon = explicit_time
        provenance["search_horizon"] = "explicit_constraint"
    elif query_time_window:
        search_horizon = query_time_window
        provenance["search_horizon"] = "query_token"
    else:
        search_horizon = None

    # Locked RQC time must not be overwritten by a competing query window.
    if rqc_time and query_time_window and rqc_time != query_time_window:
        search_horizon = rqc_time

    analysis_shape = _analysis_shape(
        query,
        tokens=tokens,
        rolling=rolling,
        grain=grain,
        sequence_events=sequence_events,
        aggregations=aggregations,
        filters=filters,
    )
    if analysis_shape == "comparison":
        support_status = "unsupported"
        degrade_reason = "unsupported_comparison_semantics"
    elif analysis_shape in SUPPORTED_ANALYSIS_SHAPES:
        support_status = "supported"
        degrade_reason = None
    else:
        support_status = "unsupported"
        degrade_reason = f"unsupported_analysis_shape:{analysis_shape}"

    if analysis_shape == "rolling" and rolling:
        analytical_window = _AnalyticalWindow(kind="rolling", size=rolling, provenance="query_token")
    elif analysis_shape == "sequence":
        analytical_window = _AnalyticalWindow(kind="sequence", size=sequence_gap, provenance="query_token")
    elif search_horizon:
        analytical_window = _AnalyticalWindow(kind="fixed", size=None, provenance=provenance.get("search_horizon", "query_token"))
    else:
        analytical_window = None

    roles = _entity_roles(query, tokens=tokens, group_by=group_by)
    if roles.distinct_by:
        for entity in roles.distinct_by:
            _append_unique(group_by, roles.subject[0] if roles.subject else entity)
    relationships = _relationships(roles, analysis_shape)
    measures = _measures(
        analysis_shape=analysis_shape,
        aggregations=aggregations,
        roles=roles,
        event_sets=event_sets,
    )
    if roles.distinct_by and "dc" not in aggregations and "distinct_count" not in aggregations:
        aggregations.append("distinct_count")

    norm_requirements, norm_consumers = _normalization_for(roles)
    explicit_threshold = bool(bindings.explicit_thresholds) or bool(_THRESHOLD_RE.search(query))
    prohibitions = _prohibitions(
        analysis_shape=analysis_shape,
        result_limit=result_limit,
        search_horizon=search_horizon,
        explicit_threshold=explicit_threshold,
        filters=filters,
    )

    source_constraints: dict[str, Any] = {}
    if bindings.explicit_indexes:
        source_constraints["index"] = bindings.explicit_indexes[0]
        provenance["source_constraints.index"] = "explicit_constraint"
    elif bindings.normalized_slots.get("index"):
        source_constraints["index"] = bindings.normalized_slots["index"]
        provenance["source_constraints.index"] = "query_token"
    if bindings.explicit_sourcetypes:
        source_constraints["sourcetype"] = bindings.explicit_sourcetypes[0]
        provenance["source_constraints.sourcetype"] = "explicit_constraint"
    elif bindings.normalized_slots.get("sourcetype"):
        source_constraints["sourcetype"] = bindings.normalized_slots["sourcetype"]
        provenance["source_constraints.sourcetype"] = "query_token"

    # Source mappings fill blanks only.
    _fill_blank(
        source_constraints,
        "index",
        sources.get("index"),
        provenance,
        "source_mapping",
        provenance_key="source_constraints.index",
    )
    _fill_blank(
        source_constraints,
        "sourcetype",
        sources.get("sourcetype"),
        provenance,
        "source_mapping",
        provenance_key="source_constraints.sourcetype",
    )
    for key, value in sources.items():
        if key in {"index", "sourcetype"}:
            continue
        _fill_blank(
            source_constraints,
            str(key),
            value,
            provenance,
            "source_mapping",
            provenance_key=f"source_constraints.{key}",
        )

    rqc_entities = rqc.get("entities") if isinstance(rqc.get("entities"), dict) else {}
    if isinstance(rqc_entities, dict):
        if rqc_entities.get("source_ip") or rqc_entities.get("src_ip"):
            _append_unique(roles.subject, "src_ip")
            provenance.setdefault("entity_roles.subject", "rqc")
        if rqc_entities.get("user"):
            _append_unique(roles.target, "user")
            provenance.setdefault("entity_roles.target", "rqc")
        if rqc_entities.get("host"):
            _append_unique(roles.group_by, "host")

    objective = str(rqc.get("normalized_goal") or "").strip() or (query[:500] if query else "")
    if rqc.get("normalized_goal"):
        provenance["objective"] = "rqc"

    spec: dict[str, Any] = {
        "contract_version": SPL_SEMANTIC_CONTRACT_VERSION,
        "objective": objective,
        "event_domain": _event_domain(query, tokens),
        "filters": filters,
        "group_by": group_by,
        "aggregations": aggregations,
        "ordering": ordering,
        "time_window": search_horizon,
        "search_horizon": search_horizon,
        "analytical_window": analytical_window.to_dict() if analytical_window else None,
        "required_event_sets": event_sets,
        "entity_roles": roles.to_dict(),
        "relationships": relationships,
        "measures": measures,
        "distinct_by": list(roles.distinct_by),
        "ranking": ranking,
        "temporal_grain": grain,
        "ordered_sequence": sequence_events,
        "sequence_max_gap": sequence_gap,
        "analysis_shape": analysis_shape,
        "output_shape": _output_shape_for(analysis_shape),
        "normalization_requirements": norm_requirements,
        "normalization_consumers": norm_consumers,
        "source_constraints": source_constraints,
        "prohibitions": prohibitions,
        "field_provenance": provenance,
        "support_status": support_status,
        "degrade_reason": degrade_reason,
        "field_requirements": list(tokens.fields),
        "result_limit": result_limit,
        "explicit_literals": {
            "indexes": list(tokens.indexes),
            "sourcetypes": list(tokens.sourcetypes),
        },
        "execution_posture": execution_posture,
        "analyst_constraints": analyst_constraints,
        "operation_hints": list(tokens.operation_hints),
        "semantic_constraints": list(bindings.semantic_constraints or tokens.semantic_constraints),
        "relative_windows": list(tokens.relative_windows),
        "rqc_locked_fields": locked,
        "explicit_threshold_present": explicit_threshold,
    }
    return spec


def spl_intent_spec_for_prompt(spec: dict[str, Any]) -> str:
    """Human-readable block for SPL advisory prompts — semantic contract only."""
    lines = [
        "Immutable semantic SPL contract (preserve exactly — do not reinterpret the request):",
        f"- contract_version: {spec.get('contract_version') or SPL_SEMANTIC_CONTRACT_VERSION}",
        f"- analysis_shape: {spec.get('analysis_shape') or 'raw'}",
        f"- output_shape: {spec.get('output_shape') or 'events'}",
        f"- support_status: {spec.get('support_status') or 'supported'}",
    ]
    if spec.get("degrade_reason"):
        lines.append(f"- degrade_reason: {spec['degrade_reason']}")
    lines.append("Analyst goal:")
    lines.append(str(spec.get("objective") or ""))
    lines.append("")
    lines.append("Semantic requirements (preserve in candidate_spl — do not drop):")
    if spec.get("event_domain"):
        lines.append(f"- event_domain: {spec['event_domain']}")
    for key in ("filters", "group_by", "distinct_by", "aggregations", "ordering", "field_requirements", "analyst_constraints", "required_event_sets", "ordered_sequence", "prohibitions"):
        values = spec.get(key) or []
        if values:
            lines.append(f"- {key}: {', '.join(str(v) for v in values)}")
    roles = spec.get("entity_roles") if isinstance(spec.get("entity_roles"), dict) else {}
    if roles:
        rendered = ", ".join(f"{k}={','.join(v)}" for k, v in roles.items() if v)
        if rendered:
            lines.append(f"- entity_roles: {rendered}")
    if spec.get("search_horizon"):
        lines.append(f"- search_horizon: {spec['search_horizon']}")
    window = spec.get("analytical_window") if isinstance(spec.get("analytical_window"), dict) else None
    if window:
        lines.append(f"- analytical_window: kind={window.get('kind')} size={window.get('size')}")
    if spec.get("temporal_grain"):
        lines.append(f"- temporal_grain: {spec['temporal_grain']}")
    if spec.get("sequence_max_gap"):
        lines.append(f"- sequence_max_gap: {spec['sequence_max_gap']}")
    if spec.get("time_window") and spec.get("time_window") != spec.get("search_horizon"):
        lines.append(f"- time_window: {spec['time_window']}")
    if spec.get("result_limit") is not None:
        lines.append(f"- result_limit: {spec['result_limit']}")
    elif spec.get("filters") and "all_events_no_action_filter" in (spec.get("filters") or []):
        lines.append("- result_limit: none requested — do not add head 100 unless policy requires")
    elif "arbitrary_head_100" in (spec.get("prohibitions") or []):
        lines.append("- result_limit: none requested — do not add head 100; do not truncate time-series/rolling/sequence output")
    measures = spec.get("measures") or []
    if measures:
        lines.append(
            "- measures: "
            + ", ".join(f"{item.get('fn')}({item.get('field')})" for item in measures if isinstance(item, dict))
        )
    ranking = spec.get("ranking")
    if isinstance(ranking, dict) and ranking:
        lines.append(f"- ranking: {ranking.get('direction')} by {ranking.get('metric')}")
    relationships = spec.get("relationships") or []
    if relationships:
        lines.append(
            "- relationships: "
            + "; ".join(
                f"{item.get('type')}:{item.get('subject')}->{item.get('object')}"
                for item in relationships
                if isinstance(item, dict)
            )
        )
    norms = spec.get("normalization_requirements") or []
    if norms:
        aliases = [str(item.get("alias")) for item in norms if isinstance(item, dict) and item.get("alias")]
        lines.append(f"- normalization_aliases: {', '.join(aliases)} (MUST be consumed by grouping/distinct/correlation/sequence)")
    if spec.get("normalization_consumers"):
        lines.append(f"- normalization_consumers: {', '.join(str(v) for v in spec['normalization_consumers'])}")
    source = spec.get("source_constraints") or {}
    if source:
        lines.append("- source_constraints: " + ", ".join(f"{k}={v}" for k, v in source.items()))
    if spec.get("execution_posture"):
        lines.append(f"- execution_posture: {spec['execution_posture']}")
    lines.append("")
    lines.append("Do not invent thresholds, indexes, sourcetypes, or time windows that are not in this contract.")
    lines.append("Do not apply unrelated MITRE, remediation, routing, MCP, or alert-template instructions.")
    return "\n".join(lines)
