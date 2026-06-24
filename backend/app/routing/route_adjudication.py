"""Control-plane route adjudication (Phase 4): intent + evidence plan over registry candidates."""

from __future__ import annotations

from typing import Any

from app.chat.contracts.evidence_plan import EvidencePlan
from app.chat.contracts.intent_classification import IntentClassification
from app.chat.contracts.route_adjudication import RouteAdjudication
from app.config import settings
from app.routing.route_authority_allowlist import (
    ALLOWLISTABLE_COVERAGE_IDS,
    BLOCKED_AUTHORITY_COVERAGE_IDS,
    parse_route_authority_coverage_allowlist,
)

_POLICY_INTENT_FAMILIES = frozenset({"policy_knowledge", "sop_or_playbook", "knowledge_only"})
_EXACT_105_MATCH_PATHS = frozenset(
    {
        "exact_105_question",
        "exact_105_plus_use_case_catalog",
    }
)
_INTENT_COMPATIBLE_WITH_EXACT_105 = frozenset(
    {
        "live_investigation",
        "spl_generation_only",
        "hybrid_investigation_plus_policy",
        "hybrid_alert_review",
        "mitre_mapping",
    }
)


def adjudicate_route(
    *,
    deterministic_route: str,
    llm_advisory: dict[str, Any] | None = None,
    route_plan_shadow: dict[str, Any] | None = None,
    evidence_plan: dict[str, Any] | EvidencePlan | None = None,
    intent_classification: dict[str, Any] | IntentClassification,
    query_understanding: Any | None = None,
    message: str = "",
    query_to_intent: dict[str, Any] | None = None,
) -> RouteAdjudication:
    """Apply §3.2 tie-breaker precedence; never re-classify intent from raw keywords."""
    _ = message  # trace-only per plan; intent/evidence carry authority
    intent = (
        intent_classification
        if isinstance(intent_classification, IntentClassification)
        else IntentClassification.model_validate(intent_classification)
    )
    plan = _coerce_evidence_plan(evidence_plan)
    shadow = route_plan_shadow if isinstance(route_plan_shadow, dict) else {}
    mappings = _candidate_mappings(query_to_intent, query_understanding)
    llm_route = _llm_suggested_route(llm_advisory, shadow)
    shadow_status = _shadow_plan_status(shadow)

    if intent.requires_clarification:
        return _result(
            deterministic_route=deterministic_route,
            llm_suggested_route=llm_route,
            shadow_plan_status=shadow_status,
            final_route="knowledge_recall",
            final_use_case_id=_first_use_case_id(mappings),
            authority_source="intent_clarification",
            reason="Intent requires clarification or human review before tool execution.",
        )

    if intent.intent_family == "github_investigation":
        return _result(
            deterministic_route=deterministic_route,
            llm_suggested_route=llm_route,
            shadow_plan_status=shadow_status,
            final_route="guided_investigation",
            final_use_case_id=_first_use_case_id(mappings),
            authority_source="github_investigation_intent",
            reason="GitHub investigation intent preserves governed guided route with GitHub-native evidence contract.",
        )

    if intent.intent_family == "guided_investigation":
        return _result(
            deterministic_route=deterministic_route,
            llm_suggested_route=llm_route,
            shadow_plan_status=shadow_status,
            final_route="guided_investigation",
            final_use_case_id=_first_use_case_id(mappings),
            authority_source="guided_investigation_rescue",
            reason="Out-of-registry SOC investigation shape preserves the governed guided route.",
        )

    if intent.intent_family == "alert_summary":
        return _result(
            deterministic_route=deterministic_route,
            llm_suggested_route=llm_route,
            shadow_plan_status=shadow_status,
            final_route="alert_summary",
            final_use_case_id=_first_use_case_id(mappings),
            authority_source="alert_summary_intent",
            reason="Summary-output intent preserves the alert-summary route without SPL.",
        )

    if plan is not None and (
        plan.answer_mode == "rag_only"
        or (
            not plan.spl_allowed
            and not plan.mcp_allowed
            and not plan.needs_mitre
            and not plan.needs_spl
        )
    ):
        return _result(
            deterministic_route=deterministic_route,
            llm_suggested_route=llm_route,
            shadow_plan_status=shadow_status,
            final_route="knowledge_recall",
            final_use_case_id=_first_use_case_id(mappings),
            authority_source="evidence_plan_rag_only",
            reason="Evidence plan blocks SPL/MCP; knowledge recall path only.",
        )

    if (
        intent.intent_family in _POLICY_INTENT_FAMILIES
        and intent.confidence_band == "high"
    ):
        return _result(
            deterministic_route=deterministic_route,
            llm_suggested_route=llm_route,
            shadow_plan_status=shadow_status,
            final_route="knowledge_recall",
            final_use_case_id=_policy_use_case_id(mappings, query_understanding),
            authority_source="intent_over_exact_105",
            reason=(
                "High-confidence policy or knowledge intent overrides analytics registry "
                "and exact-105 skill hints."
            ),
        )

    match_path = str(mappings.get("match_path") or "")
    if (
        match_path in _EXACT_105_MATCH_PATHS
        and intent.intent_family in _INTENT_COMPATIBLE_WITH_EXACT_105
        and _exact_105_authority_permitted(shadow, mappings)
    ):
        skill = _registry_skill_for_exact_105(mappings, query_understanding, deterministic_route)
        return _result(
            deterministic_route=deterministic_route,
            llm_suggested_route=llm_route,
            shadow_plan_status=shadow_status,
            final_route=skill,
            final_use_case_id=_first_use_case_id(mappings),
            authority_source="exact_105_registry",
            reason="Exact 105 mapping with compatible intent and allowlisted registry authority.",
        )

    if plan is not None and plan.answer_mode in {"hybrid", "live_investigation"}:
        skill = _skill_for_intent_family(intent.intent_family, deterministic_route)
        return _result(
            deterministic_route=deterministic_route,
            llm_suggested_route=llm_route,
            shadow_plan_status=shadow_status,
            final_route=skill,
            final_use_case_id=_first_use_case_id(mappings),
            authority_source="evidence_plan_live_or_hybrid",
            reason="Evidence plan requires live investigation and/or hybrid guidance path.",
        )

    final_route = deterministic_route.strip() or "knowledge_recall"
    return _result(
        deterministic_route=deterministic_route,
        llm_suggested_route=llm_route,
        shadow_plan_status=shadow_status,
        final_route=final_route,
        final_use_case_id=_first_use_case_id(mappings),
        authority_source="deterministic_route_default",
        reason="Default to deterministic route with shadow enrichment context.",
    )


def _coerce_evidence_plan(
    evidence_plan: dict[str, Any] | EvidencePlan | None,
) -> EvidencePlan | None:
    if evidence_plan is None:
        return None
    if isinstance(evidence_plan, EvidencePlan):
        return evidence_plan
    if isinstance(evidence_plan, dict) and evidence_plan:
        return EvidencePlan.model_validate(evidence_plan)
    return None


def _candidate_mappings(
    query_to_intent: dict[str, Any] | None,
    query_understanding: Any | None,
) -> dict[str, Any]:
    if isinstance(query_to_intent, dict):
        nested = query_to_intent.get("candidate_mappings")
        if isinstance(nested, dict):
            return dict(nested)
    if query_understanding is not None:
        return {
            "question_ref": getattr(query_understanding, "mapped_question_ref", None),
            "use_case_ids": list(getattr(query_understanding, "mapped_use_case_ids", None) or []),
            "match_path": getattr(query_understanding, "deterministic_match_path", None),
            "legacy_skill_hint": getattr(query_understanding, "mapped_primary_skill", None),
        }
    return {}


def _llm_suggested_route(
    llm_advisory: dict[str, Any] | None,
    shadow: dict[str, Any],
) -> str | None:
    if isinstance(llm_advisory, dict):
        skill = llm_advisory.get("skill")
        if isinstance(skill, str) and skill.strip():
            return skill.strip()
    for key in ("llm_shadow_skill", "advisory_skill"):
        value = shadow.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _shadow_plan_status(shadow: dict[str, Any]) -> str | None:
    for key in ("route_status", "candidate_reason", "shadow_plan_status"):
        value = shadow.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    if shadow.get("normalized_plan_available"):
        return "normalized_plan_available"
    if shadow.get("candidate_available"):
        return "candidate_available"
    return None


def _first_use_case_id(mappings: dict[str, Any]) -> str | None:
    ids = mappings.get("use_case_ids")
    if isinstance(ids, list) and ids:
        first = ids[0]
        if isinstance(first, str) and first.strip():
            return first.strip()
    return None


def _policy_use_case_id(mappings: dict[str, Any], query_understanding: Any | None) -> str | None:
    explicit = _first_use_case_id(mappings)
    if explicit and "soc_show" in explicit:
        return explicit
    if query_understanding is not None:
        ids = getattr(query_understanding, "mapped_use_case_ids", None) or []
        for item in ids:
            if isinstance(item, str) and "sop" in item.lower():
                return item
    return explicit


def _coverage_id_from_shadow(shadow: dict[str, Any], mappings: dict[str, Any]) -> str | None:
    runtime = shadow.get("question_runtime_map")
    if isinstance(runtime, dict):
        cov = runtime.get("manifest_coverage_id") or runtime.get("coverage_id")
        if isinstance(cov, str) and cov.strip():
            return cov.strip()
    compare = shadow.get("route_authority_compare")
    if isinstance(compare, dict):
        resolved = compare.get("coverage_id_resolved")
        if isinstance(resolved, str) and resolved.strip():
            return resolved.strip()
    manifest = mappings.get("manifest_coverage_id")
    if isinstance(manifest, str) and manifest.strip():
        return manifest.strip()
    return None


def _exact_105_authority_permitted(shadow: dict[str, Any], mappings: dict[str, Any]) -> bool:
    coverage_id = _coverage_id_from_shadow(shadow, mappings)
    if coverage_id in BLOCKED_AUTHORITY_COVERAGE_IDS:
        return False
    if not settings.route_authority_operation_authoritative_enabled:
        return True
    if not coverage_id:
        return False
    allowlist = parse_route_authority_coverage_allowlist(
        settings.route_authority_operation_coverage_allowlist
    )
    return coverage_id in allowlist and coverage_id in ALLOWLISTABLE_COVERAGE_IDS


def _registry_skill_for_exact_105(
    mappings: dict[str, Any],
    query_understanding: Any | None,
    fallback: str,
) -> str:
    hint = mappings.get("legacy_skill_hint")
    if isinstance(hint, str) and hint.strip():
        mirrored = _mirror_registry_skill(hint.strip())
        if mirrored:
            return mirrored
    if query_understanding is not None:
        skill = getattr(query_understanding, "mapped_primary_skill", None)
        if isinstance(skill, str) and skill.strip():
            mirrored = _mirror_registry_skill(skill.strip())
            if mirrored:
                return mirrored
    return _skill_for_intent_family("live_investigation", fallback)


def _mirror_registry_skill(registry_skill: str) -> str | None:
    """Map registry primary skills to legacy workflow skills when needed."""
    normalized = registry_skill.strip().lower()
    if normalized in {"aggregate_and_rank", "threshold_anomaly", "threshold_check"}:
        return "attack_discovery"
    if normalized == "spl_search" or normalized == "spl_generation":
        return "spl_generation"
    if normalized in {"knowledge_recall", "retrieve_approved_context"}:
        return "knowledge_recall"
    if normalized in {"attack_discovery", "spl_generation", "knowledge_recall", "alert_summary"}:
        return registry_skill.strip()
    return None


def _skill_for_intent_family(intent_family: str, fallback: str) -> str:
    if intent_family == "alert_summary":
        return "alert_summary"
    if intent_family == "github_investigation":
        return "guided_investigation"
    if intent_family == "spl_generation_only":
        return "spl_generation"
    if intent_family in _POLICY_INTENT_FAMILIES:
        return "knowledge_recall"
    if intent_family in {"mitre_explanation", "clarification_required"}:
        return "knowledge_recall"
    if fallback.strip() in {"attack_discovery", "spl_generation", "knowledge_recall", "alert_summary", "guided_investigation"}:
        return fallback.strip()
    return "attack_discovery"


def _result(
    *,
    deterministic_route: str,
    llm_suggested_route: str | None,
    shadow_plan_status: str | None,
    final_route: str,
    final_use_case_id: str | None,
    authority_source: str,
    reason: str,
) -> RouteAdjudication:
    return RouteAdjudication(
        deterministic_route=deterministic_route,
        llm_suggested_route=llm_suggested_route,
        shadow_plan_status=shadow_plan_status,
        final_route=final_route,
        final_use_case_id=final_use_case_id,
        authority_source=authority_source,
        reason=reason,
    )
