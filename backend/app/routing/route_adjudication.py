"""Control-plane route adjudication (Phase 4): intent + evidence plan over registry candidates."""

from __future__ import annotations

from typing import Any

from app.chat.contracts.evidence_plan import EvidencePlan
from app.chat.contracts.intent_classification import IntentClassification
from app.chat.contracts.route_adjudication import RouteAdjudication
from app.config import settings
from app.coverage.row_authority import AUTHORITY_READY
from app.routing.route_authority_allowlist import (
    ALLOWLISTABLE_COVERAGE_IDS,
    BLOCKED_AUTHORITY_COVERAGE_IDS,
    parse_route_authority_coverage_allowlist,
)
from app.use_cases.routing_authority import catalog_authority_row

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
_ROW_AUTHORITY_BLOCKS_EXACT_REGISTRY = frozenset(
    {
        "exact_known_weak_needs_enrichment",
        "exact_known_needs_lookup",
        "exact_known_needs_detection_binding",
        "exact_known_needs_context_binding",
        "exact_known_needs_clarification",
        "exact_known_unsupported",
    }
)
_OUT_OF_REGISTRY_MATCH_PATHS = frozenset(
    {
        "out_of_registry",
        "near_105_question",
        "semantic_105_question",
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
    """Apply tie-breaker precedence; never re-classify intent from raw keywords."""
    _ = message
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
    match_path = str(mappings.get("match_path") or "")
    row_trace = _row_authority_trace(plan, mappings, match_path=match_path)
    if match_path in _EXACT_105_MATCH_PATHS and settings.route_authority_operation_authoritative_enabled:
        row_trace["row_authority_applied"] = True

    def finish(**kwargs: Any) -> RouteAdjudication:
        return _result(
            deterministic_route=deterministic_route,
            llm_suggested_route=llm_route,
            shadow_plan_status=shadow_status,
            **row_trace,
            **kwargs,
        )

    if intent.requires_clarification:
        return finish(
            final_route="knowledge_recall",
            final_use_case_id=_first_use_case_id(mappings),
            authority_source="intent_clarification",
            reason="Intent requires clarification or human review before tool execution.",
        )

    if intent.intent_family == "github_investigation":
        return finish(
            final_route="guided_investigation",
            final_use_case_id=_first_use_case_id(mappings),
            authority_source="github_investigation_intent",
            reason="GitHub investigation intent preserves governed guided route with GitHub-native evidence contract.",
        )

    if intent.intent_family == "cve_investigation":
        return finish(
            final_route="guided_investigation",
            final_use_case_id=_first_use_case_id(mappings),
            authority_source="cve_investigation_intent",
            reason="CVE advisory review preserves governed guided route with vulnerability_source contract.",
        )

    if intent.intent_family == "guided_investigation":
        return finish(
            final_route="guided_investigation",
            final_use_case_id=_first_use_case_id(mappings),
            authority_source="guided_investigation_rescue",
            reason="Out-of-registry SOC investigation shape preserves the governed guided route.",
        )

    if intent.intent_family == "alert_summary":
        return finish(
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
        return finish(
            final_route="knowledge_recall",
            final_use_case_id=_first_use_case_id(mappings),
            authority_source="evidence_plan_rag_only",
            reason="Evidence plan blocks SPL/MCP; knowledge recall path only.",
        )

    if (
        intent.intent_family in _POLICY_INTENT_FAMILIES
        and intent.confidence_band == "high"
    ):
        return finish(
            final_route="knowledge_recall",
            final_use_case_id=_policy_use_case_id(mappings, query_understanding),
            authority_source="intent_over_exact_105",
            reason=(
                "High-confidence policy or knowledge intent overrides analytics registry "
                "and exact-105 skill hints."
            ),
        )

    if (
        match_path in _EXACT_105_MATCH_PATHS
        and intent.intent_family in _INTENT_COMPATIBLE_WITH_EXACT_105
        and _exact_105_authority_permitted(shadow, mappings)
        and _row_authority_permits_exact_registry(row_trace)
    ):
        skill = _registry_skill_for_exact_105(mappings, query_understanding, deterministic_route)
        return finish(
            final_route=skill,
            final_use_case_id=_first_use_case_id(mappings),
            authority_source="exact_105_registry",
            reason="Exact 105 mapping with compatible intent and allowlisted registry authority.",
        )

    if plan is not None and plan.answer_mode in {"hybrid", "live_investigation"}:
        skill = _skill_for_intent_family(intent.intent_family, deterministic_route)
        return finish(
            final_route=skill,
            final_use_case_id=_first_use_case_id(mappings),
            authority_source="evidence_plan_live_or_hybrid",
            reason="Evidence plan requires live investigation and/or hybrid guidance path.",
        )

    final_route = deterministic_route.strip() or "knowledge_recall"
    return finish(
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


def _row_authority_advisory_assessment(
    plan: EvidencePlan | None,
    mappings: dict[str, Any],
    *,
    match_path: str,
) -> tuple[str, str | None, str | None]:
    """Trace-only assessment; does not change route adjudication decisions."""
    use_case_id = _first_use_case_id(mappings)

    if match_path in _OUT_OF_REGISTRY_MATCH_PATHS:
        return (
            "out_of_registry",
            None,
            "Out-of-registry or near-match path; row authority is advisory only.",
        )

    catalog = catalog_authority_row(use_case_id)
    if catalog is not None:
        tier = str(catalog.get("registry_tier") or "")
        if tier == "t1_spl_native" or use_case_id in {"soc_generate_spl", "soc_optimize_spl"}:
            return (
                "catalog_t1_spl_native",
                "catalog_t1_spl_native",
                "Catalogue row is T1 SPL-native/meta (e.g. soc_generate_spl); not T0 exact authority.",
            )
        if catalog.get("t0_exact_authority") is False:
            return (
                "catalog_advisory_not_t0",
                "catalog_t0_exact_authority_false",
                "Catalogue row did not opt into T0 exact authority; advisory-eligible.",
            )

    summary = plan.row_authority_summary if plan is not None else None
    if not isinstance(summary, dict) or not summary:
        return (
            "no_row_authority_summary",
            None,
            "No runtime row authority summary on EvidencePlan for this turn.",
        )

    status = str(summary.get("row_authority_status") or "").strip()
    if not status:
        return (
            "no_row_authority_status",
            None,
            "EvidencePlan row_authority_summary present but status is empty.",
        )

    if status == AUTHORITY_READY and summary.get("s3_authority_ready") is True:
        return (
            "exact_known_authority_ready",
            None,
            "Runtime row is authority-ready (trace only; route adjudication unchanged).",
        )

    if status in _ROW_AUTHORITY_BLOCKS_EXACT_REGISTRY:
        return (
            "would_withhold_exact_registry",
            status,
            f"Row authority status {status!r} would withhold exact-105 registry if enforced (trace only).",
        )

    return (
        "row_authority_observed",
        status,
        f"Row authority status {status!r} recorded for trace (route adjudication unchanged).",
    )


def _row_authority_trace(
    plan: EvidencePlan | None,
    mappings: dict[str, Any],
    *,
    match_path: str,
) -> dict[str, Any]:
    decision, fallback, note = _row_authority_advisory_assessment(
        plan, mappings, match_path=match_path
    )
    summary = plan.row_authority_summary if plan is not None else None
    status: str | None = None
    if isinstance(summary, dict):
        raw = summary.get("row_authority_status")
        if isinstance(raw, str) and raw.strip():
            status = raw.strip()
    return {
        "row_authority_status": status,
        "row_authority_decision": decision,
        "row_authority_applied": False,
        "row_authority_note": note,
        "row_authority_fallback_reason": fallback,
    }


def _row_authority_permits_exact_registry(row_trace: dict[str, Any]) -> bool:
    if not settings.route_authority_operation_authoritative_enabled:
        return True
    return row_trace.get("row_authority_decision") == "exact_known_authority_ready"


def _result(
    *,
    deterministic_route: str,
    llm_suggested_route: str | None,
    shadow_plan_status: str | None,
    final_route: str,
    final_use_case_id: str | None,
    authority_source: str,
    reason: str,
    row_authority_status: str | None = None,
    row_authority_decision: str | None = None,
    row_authority_applied: bool = False,
    row_authority_note: str | None = None,
    row_authority_fallback_reason: str | None = None,
) -> RouteAdjudication:
    return RouteAdjudication(
        deterministic_route=deterministic_route,
        llm_suggested_route=llm_suggested_route,
        shadow_plan_status=shadow_plan_status,
        final_route=final_route,
        final_use_case_id=final_use_case_id,
        authority_source=authority_source,
        reason=reason,
        row_authority_status=row_authority_status,
        row_authority_decision=row_authority_decision,
        row_authority_applied=row_authority_applied,
        row_authority_note=row_authority_note,
        row_authority_fallback_reason=row_authority_fallback_reason,
    )
