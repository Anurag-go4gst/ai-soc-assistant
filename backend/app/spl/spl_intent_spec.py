"""Canonical SPL intent spec — reuse pre-parse + user bindings, no duplicate planner."""

from __future__ import annotations

import re
from typing import Any

from app.spl.t2_pre_parse import pre_parse_spl_tokens
from app.spl.user_constraint_bindings import build_user_constraint_bindings

_FIREWALL_RE = re.compile(r"\bfirewall\b", re.I)
# Do NOT match bare "block" — "SPL block" / "code block" are authoring nouns, not deny actions.
_DENIED_RE = re.compile(
    r"\b(denied|deny|blocked|drop|reject)\b|"
    r"\bblock\s+(?:all|this|the|ip|user|account|traffic|source|suspicious|firewall)\b",
    re.I,
)
_SRC_IP_RE = re.compile(r"\b(source\s+ips?|src[_\s]?ips?|by\s+src)\b", re.I)
_TOP_RE = re.compile(r"\btop\b", re.I)
_ALL_LOGS_RE = re.compile(r"\ball\b.*\b(logs?|events?|traffic)\b", re.I)
_REVIEW_ONLY_RE = re.compile(r"\b(review[\s-]?only|do not execute|don't execute|not execute)\b", re.I)
_SPL_ONLY_RE = re.compile(r"\b(only\s+(an?\s+)?spl|spl\s+(query|command|only))\b", re.I)


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
    if any(token in lowered for token in ("auth", "login", "logon")):
        return "authentication"
    if any(token in lowered for token in ("vpn", "remote access")):
        return "vpn"
    if "endpoint" in lowered or "edr" in lowered:
        return "endpoint"
    if tokens.operation_hints:
        return str(tokens.operation_hints[0])
    return None


def build_spl_intent_spec(user_query: str) -> dict[str, Any]:
    """Project analyst SPL semantics for LLM prompts and fidelity validation."""
    query = str(user_query or "").strip()
    tokens = pre_parse_spl_tokens(query)
    bindings = build_user_constraint_bindings(query)

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
    for field in tokens.fields:
        if field not in group_by:
            group_by.append(field)

    aggregations: list[str] = []
    ordering: list[str] = []
    if tokens.operation_hints and "aggregate_and_rank" in tokens.operation_hints:
        aggregations.append("count")
        ordering.append("descending")
    elif _TOP_RE.search(query):
        aggregations.append("count")
        ordering.append("descending")

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

    time_window = _time_window_from_tokens(tokens, bindings)
    source_constraints: dict[str, Any] = {}
    if bindings.explicit_indexes:
        source_constraints["index"] = bindings.explicit_indexes[0]
    elif bindings.normalized_slots.get("index"):
        source_constraints["index"] = bindings.normalized_slots["index"]
    if bindings.explicit_sourcetypes:
        source_constraints["sourcetype"] = bindings.explicit_sourcetypes[0]
    elif bindings.normalized_slots.get("sourcetype"):
        source_constraints["sourcetype"] = bindings.normalized_slots["sourcetype"]

    objective = query[:500] if query else ""
    return {
        "objective": objective,
        "event_domain": _event_domain(query, tokens),
        "filters": filters,
        "group_by": group_by,
        "aggregations": aggregations,
        "ordering": ordering,
        "time_window": time_window,
        "source_constraints": source_constraints,
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
    }


def spl_intent_spec_for_prompt(spec: dict[str, Any]) -> str:
    """Human-readable block for SPL advisory prompts."""
    lines = ["Analyst goal:", str(spec.get("objective") or "")]
    lines.append("")
    lines.append("Semantic requirements (preserve in candidate_spl — do not drop):")
    if spec.get("event_domain"):
        lines.append(f"- event_domain: {spec['event_domain']}")
    for key in ("filters", "group_by", "aggregations", "ordering", "field_requirements", "analyst_constraints"):
        values = spec.get(key) or []
        if values:
            lines.append(f"- {key}: {', '.join(str(v) for v in values)}")
    if spec.get("time_window"):
        lines.append(f"- time_window: {spec['time_window']}")
    if spec.get("result_limit") is not None:
        lines.append(f"- result_limit: {spec['result_limit']}")
    elif spec.get("filters") and "all_events_no_action_filter" in (spec.get("filters") or []):
        lines.append("- result_limit: none requested — do not add head 100 unless policy requires")
    source = spec.get("source_constraints") or {}
    if source:
        lines.append("- source_constraints: " + ", ".join(f"{k}={v}" for k, v in source.items()))
    if spec.get("execution_posture"):
        lines.append(f"- execution_posture: {spec['execution_posture']}")
    return "\n".join(lines)
