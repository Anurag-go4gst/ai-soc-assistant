from __future__ import annotations

import re

from app.config import settings
from app.detections.detection_binder import preflight_detection_requirements
from app.detections.detection_models import DetectionBindingResult
from app.intel.ioc_lookup import BLOCK_CANNOT_ROUTE_LOOKUP_STALE, BLOCK_LOOKUP_STALE, preflight_ioc_requirements
from app.intel.ioc_models import IocLookupResult
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
    if lookup_name:
        if lookup_name in ctx.configured_lookups:
            pass
        elif settings.ioc_registry_enabled:
            ioc_block = preflight_ioc_requirements(
                lookup_required=True,
                ioc_values=_extract_ioc_values(normalized),
                legacy_lookup_name=lookup_name,
            )
            if ioc_block is not None and not ioc_block.match:
                return _preflight_from_ioc_block(ioc_block, lookup_name)
        else:
            return RoutePlanPreflightResult(
                route_status=RouteStatus.CANNOT_ROUTE_MISSING_LOOKUP,
                missing_slots=["lookup_ref"],
                blocking_findings=[f"missing_configured_lookup:{lookup_name}"],
            )

    route_plan_block = _preflight_route_plan_lookup_dependency(ctx.route_plan)
    if route_plan_block is not None:
        return route_plan_block

    detection_block = _preflight_route_plan_detection_dependency(ctx.route_plan)
    if detection_block is not None:
        return detection_block

    detection_name = _required_detection(normalized)
    if detection_name:
        if detection_name in ctx.configured_detections:
            pass
        elif settings.detection_registry_enabled:
            detection_preflight = preflight_detection_requirements(
                detection_required=True,
                family=detection_name,
            )
            if detection_preflight is not None:
                return _preflight_from_detection_block(detection_preflight, detection_name)
        else:
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


_IPV4_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
_DOMAIN_RE = re.compile(r"\b(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,}\b")
_HASH_RE = re.compile(r"\b[a-f0-9]{32,64}\b")


def _extract_ioc_values(normalized: str) -> list[str]:
    values: list[str] = []
    values.extend(_IPV4_RE.findall(normalized))
    values.extend(_DOMAIN_RE.findall(normalized))
    values.extend(_HASH_RE.findall(normalized))
    return sorted(set(values))


def _preflight_from_ioc_block(block: IocLookupResult, lookup_name: str | None) -> RoutePlanPreflightResult:
    reason = block.blocking_reason or BLOCK_CANNOT_ROUTE_LOOKUP_STALE
    findings = [reason]
    if reason == BLOCK_CANNOT_ROUTE_LOOKUP_STALE:
        findings.append(BLOCK_LOOKUP_STALE)
        findings.append("lookup_stale")
    elif reason.startswith("missing_configured_lookup"):
        findings.append(f"missing_configured_lookup:{lookup_name or 'ioc'}")
    return RoutePlanPreflightResult(
        route_status=RouteStatus.CANNOT_ROUTE_MISSING_LOOKUP,
        missing_slots=["lookup_ref"],
        blocking_findings=sorted(set(findings)),
    )


def _preflight_from_detection_block(
    block: DetectionBindingResult,
    detection_name: str | None,
) -> RoutePlanPreflightResult:
    reason = block.unbound_reason or "missing_vetted_detection"
    findings = list(block.reasons) if block.reasons else [reason]
    if reason == "missing_configured_detection":
        findings.append(f"missing_vetted_detection:{detection_name or 'detection'}")
    else:
        findings.append(f"missing_vetted_detection:{detection_name or block.family or 'detection'}")
    return RoutePlanPreflightResult(
        route_status=RouteStatus.CANNOT_ROUTE_MISSING_DETECTION,
        missing_slots=["detection_ref"],
        blocking_findings=sorted(set(findings)),
    )


def _preflight_route_plan_detection_dependency(route_plan: dict | None) -> RoutePlanPreflightResult | None:
    if not isinstance(route_plan, dict):
        return None
    evidence = route_plan.get("evidence_needs")
    detection_required = isinstance(evidence, dict) and evidence.get("detection_required")
    parameters = route_plan.get("parameters")
    detection_family = None
    if isinstance(evidence, dict):
        detection_family = evidence.get("detection_family")
    if not detection_family and isinstance(parameters, dict):
        detection_family = parameters.get("detection_family")
    if not detection_required and not detection_family:
        if not (isinstance(parameters, dict) and parameters.get("detection_ref")):
            return None
    if not settings.detection_registry_enabled:
        if detection_required or detection_family or (isinstance(parameters, dict) and parameters.get("detection_ref")):
            return RoutePlanPreflightResult(
                route_status=RouteStatus.CANNOT_ROUTE_MISSING_DETECTION,
                missing_slots=["detection_ref"],
                blocking_findings=["missing_configured_detection"],
            )
        return None
    block = preflight_detection_requirements(
        detection_required=bool(detection_required or (isinstance(parameters, dict) and parameters.get("detection_ref"))),
        family=str(detection_family) if detection_family else _infer_detection_family_from_plan(route_plan),
    )
    if block is not None:
        return _preflight_from_detection_block(block, str(detection_family) if detection_family else None)
    return None


def _infer_detection_family_from_plan(route_plan: dict) -> str | None:
    parameters = route_plan.get("parameters")
    if isinstance(parameters, dict):
        family = parameters.get("detection_family")
        if isinstance(family, str) and family.strip():
            return family.strip().lower()
    primary_skill = route_plan.get("primary_skill")
    if primary_skill == "behavioral_detection_binding":
        return "impossible_travel"
    return None


def _preflight_route_plan_lookup_dependency(route_plan: dict | None) -> RoutePlanPreflightResult | None:
    if not isinstance(route_plan, dict):
        return None
    evidence = route_plan.get("evidence_needs")
    if not isinstance(evidence, dict) or not evidence.get("lookup_required"):
        parameters = route_plan.get("parameters")
        if not isinstance(parameters, dict) or not parameters.get("lookup_ref"):
            return None
    ioc_block = preflight_ioc_requirements(lookup_required=True)
    if ioc_block is not None and not ioc_block.match:
        return _preflight_from_ioc_block(ioc_block, "ioc")
    return None
