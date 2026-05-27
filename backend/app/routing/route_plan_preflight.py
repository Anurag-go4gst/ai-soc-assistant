from __future__ import annotations

import re

from app.routing.route_plan_models import PreflightContext, RoutePlanPreflightResult, RouteStatus


CONTEXTUAL_REFERENCE_SLOTS: tuple[tuple[str, str], ...] = (
    ("this user", "user"),
    ("this host", "host"),
    ("this notable", "notable_id"),
    ("this alert", "notable_id"),
    ("this incident", "notable_id"),
    ("this event", "event_id"),
    ("this entity", "entity_param"),
    ("current alert", "notable_id"),
    ("current notable", "notable_id"),
)
LOOKUP_TRIGGERS = ("known malicious", " ioc", "known bad ip", "known bad domain", "suspicious hash from lookup")
DETECTION_TRIGGERS: tuple[tuple[str, str], ...] = (
    ("dga", "dga"),
    ("beaconing", "beaconing"),
    ("c2 beaconing", "beaconing"),
    ("impossible travel", "impossible_travel"),
    ("lateral movement", "lateral_movement"),
    ("encoded powershell", "encoded_powershell"),
    ("scheduled task creation", "scheduled_task_creation"),
    ("persistence", "persistence"),
    ("webshell", "webshell"),
)
THRESHOLD_TRIGGERS = ("excessive", "spike", "unusually high", "large", "many")
SOURCE_HINTS: tuple[tuple[str, str], ...] = (
    ("okta", "okta_authentication_logs"),
    ("dns", "dns_logs"),
    ("powershell", "powershell_logs"),
    ("windows", "windows_event_logs"),
    ("firewall", "firewall_logs"),
)


def preflight_route_plan(query: str, context: PreflightContext | None = None) -> RoutePlanPreflightResult:
    ctx = context or PreflightContext()
    normalized = _normalize(query)

    missing_context = _missing_contextual_slots(normalized, ctx)
    if missing_context:
        return RoutePlanPreflightResult(
            route_status=RouteStatus.CLARIFICATION_REQUIRED,
            missing_slots=missing_context,
            blocking_findings=["missing_contextual_reference"],
        )

    entity_slot = _missing_entity_specific_slot(normalized, ctx)
    if entity_slot:
        return RoutePlanPreflightResult(
            route_status=RouteStatus.CLARIFICATION_REQUIRED,
            missing_slots=[entity_slot],
            blocking_findings=["missing_entity_for_entity_specific_query"],
        )

    lookup_name = _required_lookup(normalized)
    if lookup_name and lookup_name not in ctx.configured_lookups:
        return RoutePlanPreflightResult(
            route_status=RouteStatus.CANNOT_ROUTE_MISSING_LOOKUP,
            missing_slots=["lookup_ref"],
            blocking_findings=[f"missing_configured_lookup:{lookup_name}"],
        )

    detection_name = _required_detection(normalized)
    if detection_name and detection_name not in ctx.configured_detections:
        return RoutePlanPreflightResult(
            route_status=RouteStatus.CANNOT_ROUTE_MISSING_DETECTION,
            missing_slots=["detection_ref"],
            blocking_findings=[f"missing_vetted_detection:{detection_name}"],
        )

    unavailable_source = _unavailable_required_source(normalized, ctx)
    if unavailable_source:
        return RoutePlanPreflightResult(
            route_status=RouteStatus.CANNOT_ROUTE_MISSING_SOURCE,
            missing_slots=["source_class"],
            blocking_findings=[f"missing_source:{unavailable_source}"],
        )

    if any(trigger in normalized for trigger in THRESHOLD_TRIGGERS) and not (
        ctx.threshold_policy_configured or ctx.baseline_policy_configured
    ):
        return RoutePlanPreflightResult(
            route_status=RouteStatus.CLARIFICATION_REQUIRED,
            missing_slots=["threshold_ref", "baseline_ref"],
            blocking_findings=["missing_threshold_or_baseline_policy"],
        )

    if _underspecified_suspicious_query(normalized):
        return RoutePlanPreflightResult(
            route_status=RouteStatus.CLARIFICATION_REQUIRED,
            missing_slots=["detection_ref", "metric", "time_window"],
            blocking_findings=["underspecified_suspicious_query"],
        )

    return RoutePlanPreflightResult(route_status=None)


def _normalize(query: str) -> str:
    return f" {' '.join(query.lower().split())} "


def _missing_contextual_slots(normalized: str, ctx: PreflightContext) -> list[str]:
    if ctx.has_prior_context:
        return []
    missing: list[str] = []
    for phrase, slot in CONTEXTUAL_REFERENCE_SLOTS:
        if phrase in normalized and slot not in ctx.explicit_entities:
            missing.append(slot)
    return sorted(set(missing))


def _missing_entity_specific_slot(normalized: str, ctx: PreflightContext) -> str | None:
    if re.search(r"\bis\s+this\s+user\s+privileged\b", normalized) and "user" not in ctx.explicit_entities:
        return "user"
    if re.search(r"\bis\s+this\s+host\s+critical\b", normalized) and "host" not in ctx.explicit_entities:
        return "host"
    if "what happened for this notable" in normalized and "notable_id" not in ctx.explicit_entities:
        return "notable_id"
    return None


def _required_lookup(normalized: str) -> str | None:
    if "known malicious" in normalized or " ioc" in normalized:
        return "ioc"
    if "known bad ip" in normalized:
        return "known_bad_ip"
    if "known bad domain" in normalized:
        return "known_bad_domain"
    if "suspicious hash from lookup" in normalized:
        return "suspicious_hash"
    return None


def _required_detection(normalized: str) -> str | None:
    for phrase, detection in DETECTION_TRIGGERS:
        if phrase in normalized:
            return detection
    return None


def _unavailable_required_source(normalized: str, ctx: PreflightContext) -> str | None:
    for phrase, source in SOURCE_HINTS:
        if phrase in normalized and source in ctx.unavailable_sources:
            return source
    return None


def _underspecified_suspicious_query(normalized: str) -> bool:
    return " suspicious " in normalized and not any(
        marker in normalized for marker in (" last ", " today ", " detection", " by ", " count", " metric", " threshold")
    )
