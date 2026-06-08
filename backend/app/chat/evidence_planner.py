from __future__ import annotations

from typing import Any

from app.chat.contracts.evidence_plan import EvidencePlan
from app.chat.contracts.intent_classification import IntentClassification
from app.config import settings
from app.use_cases.content_enrichment import (
    CuratedEnrichmentContext,
    get_content_enrichment,
    get_runtime_curated_enrichment,
    resolve_use_case_activation,
)

_CATALOG_PROJECTION_WHEN_INACTIVE = frozenset(
    {
        "edr_powershell_suspicious_command",
        "dns_beaconing_candidate",
        "dns_tunneling_candidate",
        "dns_unusual_query_volume",
        "edr_suspicious_process",
        "email_phishing_header_review",
    }
)


def plan_evidence(
    intent_classification: dict[str, Any] | IntentClassification,
    query_to_intent: dict[str, Any] | None = None,
    routed: dict[str, Any] | None = None,
    query_understanding: Any = None,
    selected_use_case: Any = None,
) -> EvidencePlan:
    """Plan evidence paths from intent only.

    `query_to_intent` and `routed` are accepted for future trace/HIL hints; this
    phase deliberately avoids re-reading user text or legacy route keywords.
    """
    intent = (
        intent_classification
        if isinstance(intent_classification, IntentClassification)
        else IntentClassification.model_validate(intent_classification)
    )
    family = intent.intent_family
    selected_use_case_id = _use_case_id(selected_use_case, query_understanding, query_to_intent, routed)

    def with_enrichment(plan: EvidencePlan) -> EvidencePlan:
        return _apply_curated_enrichment(
            plan,
            use_case_id=selected_use_case_id,
            query_to_intent=query_to_intent,
            query_understanding=query_understanding,
        )

    if intent.requires_clarification or family == "clarification_required":
        return with_enrichment(
            EvidencePlan(
                answer_mode="clarification",
                rag_phase="rag_only",
                needs_rag=False,
                needs_spl=False,
                needs_mcp=False,
                needs_mitre=False,
                spl_allowed=False,
                mcp_allowed=False,
                policy_context_required=False,
                policy_context_recommended=False,
                requires_hil=True,
                action_mode=intent.action_mode or "hil_required",
                reasons=["intent_requires_clarification"],
            )
        )

    if family in {"policy_knowledge", "sop_or_playbook"}:
        return with_enrichment(
            EvidencePlan(
                answer_mode="rag_only",
                rag_phase="rag_only",
                needs_rag=True,
                needs_spl=False,
                needs_mcp=False,
                needs_mitre=False,
                spl_allowed=False,
                mcp_allowed=False,
                policy_context_required=True,
                policy_context_recommended=False,
                rag_no_match_behavior="insufficient_policy_context",
                reasons=["policy_context_required"],
            )
        )

    if family == "knowledge_only":
        return with_enrichment(
            EvidencePlan(
                answer_mode="rag_only",
                rag_phase="rag_only",
                needs_rag=True,
                needs_spl=False,
                needs_mcp=False,
                needs_mitre=False,
                spl_allowed=False,
                mcp_allowed=False,
                policy_context_required=False,
                policy_context_recommended=True,
                rag_no_match_behavior="general_guidance_allowed",
                reasons=["knowledge_context_recommended"],
            )
        )

    if family == "spl_generation_only":
        return with_enrichment(
            EvidencePlan(
                answer_mode="live_investigation",
                rag_phase="post_mcp",
                needs_rag=False,
                needs_spl=True,
                needs_mcp=False,
                needs_mitre=False,
                spl_allowed=True,
                mcp_allowed=False,
                policy_context_required=False,
                policy_context_recommended=False,
                reasons=["spl_artifact_requested"],
            )
        )

    if family == "spl_generation_and_run":
        return with_enrichment(
            EvidencePlan(
                answer_mode="live_investigation",
                rag_phase="post_mcp",
                needs_rag=False,
                needs_spl=True,
                needs_mcp=True,
                needs_mitre=False,
                spl_allowed=True,
                mcp_allowed=True,
                policy_context_required=False,
                policy_context_recommended=False,
                requires_hil=intent.requires_hil,
                action_mode=intent.action_mode or "recommend_only",
                reasons=["spl_artifact_and_scoped_execution_requested"],
            )
        )

    if family == "hybrid_investigation_plus_policy":
        return with_enrichment(
            EvidencePlan(
                answer_mode="hybrid",
                rag_phase="pre_mcp",
                needs_rag=True,
                needs_spl=True,
                needs_mcp=True,
                needs_mitre="mitre_mapping" in intent.answer_goal,
                spl_allowed=True,
                mcp_allowed=True,
                policy_context_required=False,
                policy_context_recommended=True,
                requires_hil=intent.requires_hil,
                action_mode=intent.action_mode or "recommend_only",
                reasons=["hybrid_live_results_with_guidance"],
            )
        )

    if family == "hybrid_alert_review":
        return with_enrichment(
            EvidencePlan(
                answer_mode="live_investigation",
                rag_phase="post_mcp",
                needs_rag=False,
                needs_spl=True,
                needs_mcp=False,
                needs_mitre=True,
                spl_allowed=True,
                mcp_allowed=False,
                policy_context_required=False,
                policy_context_recommended=False,
                requires_hil=intent.requires_hil,
                action_mode=intent.action_mode or "recommend_only",
                reasons=["hybrid_alert_review_severity_mitre_spl"],
            )
        )

    if family == "mitre_mapping":
        return with_enrichment(
            EvidencePlan(
                answer_mode="live_investigation",
                rag_phase="post_mcp",
                needs_rag=False,
                needs_spl=False,
                needs_mcp=False,
                needs_mitre=True,
                spl_allowed=False,
                mcp_allowed=False,
                policy_context_required=False,
                policy_context_recommended=False,
                requires_hil=intent.requires_hil,
                action_mode=intent.action_mode or "recommend_only",
                reasons=["mitre_mapping_requires_grounding"],
            )
        )

    if family == "mitre_explanation":
        return with_enrichment(
            EvidencePlan(
                answer_mode="rag_only",
                rag_phase="rag_only",
                needs_rag=True,
                needs_spl=False,
                needs_mcp=False,
                needs_mitre=True,
                spl_allowed=False,
                mcp_allowed=False,
                policy_context_required=False,
                policy_context_recommended=True,
                rag_no_match_behavior="general_guidance_allowed",
                reasons=["mitre_explanation_knowledge"],
            )
        )

    return with_enrichment(
        EvidencePlan(
            answer_mode="live_investigation",
            rag_phase="post_mcp",
            needs_rag=False,
            needs_spl=True,
            needs_mcp=True,
            needs_mitre=False,
            spl_allowed=True,
            mcp_allowed=True,
            policy_context_required=False,
            policy_context_recommended=False,
            requires_hil=intent.requires_hil,
            action_mode=intent.action_mode or "recommend_only",
            reasons=["live_investigation"],
        )
    )


def _apply_curated_enrichment(
    plan: EvidencePlan,
    *,
    use_case_id: str | None,
    query_to_intent: dict[str, Any] | None,
    query_understanding: Any,
) -> EvidencePlan:
    if not use_case_id:
        return plan

    if not settings.ai_soc_curated_enrichment_activation_enabled:
        if use_case_id in _CATALOG_PROJECTION_WHEN_INACTIVE:
            return _apply_catalog_projection(
                plan,
                use_case_id=use_case_id,
                query_to_intent=query_to_intent,
                query_understanding=query_understanding,
                evidence_plan_reason="curated_enrichment_activation_disabled",
            )
        return plan

    activation = resolve_use_case_activation(use_case_id)
    if not activation.governed_enrichment_load_allowed:
        return plan.model_copy(
            update={
                "use_case_id": use_case_id,
                "runtime_support_status": activation.runtime_support_status,
                "evidence_plan_reason": "curated_enrichment_not_runtime_active",
            }
        )

    context = get_runtime_curated_enrichment(use_case_id)
    if context is None:
        return plan.model_copy(
            update={
                "use_case_id": use_case_id,
                "evidence_plan_reason": "curated_enrichment_context_unavailable",
            }
        )

    present = _present_evidence_keys(query_to_intent=query_to_intent, query_understanding=query_understanding)
    required = list(dict.fromkeys(context.evidence_requirements))
    missing = [key for key in required if key not in present]
    needs_review = bool(missing) and plan.answer_mode in {"live_investigation", "hybrid"}
    reasons = list(plan.reasons)
    reasons.append("curated_enrichment_evidence_requirements")
    if missing:
        reasons.append("missing_required_curated_evidence")

    return plan.model_copy(
        update={
            "required_evidence_keys": required,
            "optional_evidence_keys": _optional_evidence_keys(context, required),
            "present_evidence_keys": sorted(present),
            "missing_required_evidence": missing,
            "enrichment_driven": True,
            "checklist": list(context.analyst_checklist),
            "answer_rules": list(context.answer_rules),
            "required_sources": list(context.required_sources),
            "optional_sources": list(context.optional_sources),
            "limitations": list(context.limitations),
            "recommended_pivots": list(context.recommended_pivots),
            "unsupported_claims_avoid": list(context.not_claimed_defaults),
            "needs_hil": bool(plan.requires_hil or needs_review),
            "needs_clarification": bool(plan.answer_mode == "clarification" or needs_review),
            "requires_hil": bool(plan.requires_hil or needs_review),
            "evidence_plan_reason": "curated_enrichment_required_evidence_missing"
            if missing
            else "curated_enrichment_required_evidence_available",
            "use_case_id": context.use_case_id,
            "runtime_support_status": context.runtime_support_status,
            "mitre_candidates_metadata_only": list(context.mitre_candidates),
            "reasons": list(dict.fromkeys(reasons)),
        }
    )


def _apply_catalog_projection(
    plan: EvidencePlan,
    *,
    use_case_id: str,
    query_to_intent: dict[str, Any] | None,
    query_understanding: Any,
    runtime_support_status: str | None = None,
    evidence_plan_reason: str = "catalog_enrichment_projection",
) -> EvidencePlan:
    """Attach catalog enrichment metadata without runtime activation gates."""
    record = get_content_enrichment(use_case_id)
    if record is None:
        update: dict[str, Any] = {"use_case_id": use_case_id, "evidence_plan_reason": evidence_plan_reason}
        if runtime_support_status:
            update["runtime_support_status"] = runtime_support_status
        return plan.model_copy(update=update)

    present = _present_evidence_keys(query_to_intent=query_to_intent, query_understanding=query_understanding)
    required = [str(item) for item in record.get("evidence_requirements") or [] if item]
    missing = [key for key in required if key not in present]
    reasons = list(dict.fromkeys([*plan.reasons, evidence_plan_reason, "catalog_enrichment_projection"]))
    if missing:
        reasons.append("missing_required_catalog_evidence")

    return plan.model_copy(
        update={
            "use_case_id": use_case_id,
            "required_evidence_keys": required,
            "optional_evidence_keys": [str(item) for item in record.get("optional_sources") or [] if item],
            "present_evidence_keys": sorted(present),
            "missing_required_evidence": missing,
            "checklist": [str(item) for item in record.get("analyst_checklist") or [] if item],
            "answer_rules": [str(item) for item in record.get("answer_rules") or [] if item],
            "limitations": [str(item) for item in record.get("limitations") or [] if item],
            "unsupported_claims_avoid": [str(item) for item in record.get("not_claimed_defaults") or [] if item],
            "mitre_candidates_metadata_only": [str(item) for item in record.get("mitre_candidates") or [] if item],
            "runtime_support_status": runtime_support_status,
            "evidence_plan_reason": evidence_plan_reason,
            "reasons": reasons,
        }
    )


def _use_case_id(
    selected_use_case: Any,
    query_understanding: Any,
    query_to_intent: dict[str, Any] | None,
    routed: dict[str, Any] | None,
) -> str | None:
    value = getattr(selected_use_case, "use_case_id", None)
    if isinstance(value, str) and value:
        return value
    mapped = getattr(query_understanding, "mapped_use_case_ids", None)
    if isinstance(mapped, list) and mapped:
        return str(mapped[0])
    candidates = (query_to_intent or {}).get("candidate_mappings")
    if isinstance(candidates, dict):
        mapped = candidates.get("mapped_use_case_ids")
        if isinstance(mapped, list) and mapped:
            return str(mapped[0])
    provenance = (routed or {}).get("routing_provenance")
    if isinstance(provenance, dict):
        mapped = provenance.get("mapped_use_case_ids")
        if isinstance(mapped, list) and mapped:
            return str(mapped[0])
    return None


def _present_evidence_keys(
    *,
    query_to_intent: dict[str, Any] | None,
    query_understanding: Any,
) -> set[str]:
    signals = (query_to_intent or {}).get("query_signals")
    signal_keys = _present_from_signals(signals if isinstance(signals, dict) else {})
    entity_keys = _present_from_entities(getattr(query_understanding, "entities", None))
    return signal_keys | entity_keys


def _present_from_entities(entities: Any) -> set[str]:
    if entities is None:
        return set()
    values: set[str] = set()
    entity_map = {
        "user": ("user",),
        "host": ("host", "asset", "affected_asset"),
        "source_ip": ("src", "source_ip", "source_ips"),
        "destination_ip": ("dest", "destination_ip", "destination"),
        "time_window": ("time_window",),
        "index": ("index",),
        "sourcetype": ("sourcetype",),
        "alert_id": ("alert_id", "current_status"),
        "event_type": ("alert_type", "event_id"),
    }
    for attr, evidence_names in entity_map.items():
        value = getattr(entities, attr, None)
        if isinstance(value, list) and value:
            values.update(evidence_names)
        elif isinstance(value, str) and value:
            values.update(evidence_names)
    return values


def _present_from_signals(signals: dict[str, Any]) -> set[str]:
    values: set[str] = set()
    signal_map = {
        "failed_login": ("fail_count", "first_failure", "last_failure", "failed_login_pattern"),
        "time_window_24h": ("time_window",),
        "success_after_failure": ("success_count", "last_success", "first_failure", "fail_count"),
        "positive_successful_login": ("success_count", "last_success"),
        "source_ip_novelty": ("source_ip_novelty",),
        "spray_breadth": ("spray_breadth",),
        "powershell_command_evidence": ("command_line", "script_block_text", "event_id", "process_evidence"),
        "encoded_command": ("encoded_command_flag",),
        "suspicious_parent_process": ("parent_process",),
        "endpoint_network_connection": ("network_connection",),
        "periodicity": ("periodicity",),
        "jitter_profile": ("jitter",),
        "byte_pattern": ("bytes_out",),
        "rare_domain": ("rare_domain_indicator", "domain"),
        "repeated_destination": ("dest", "domain"),
        "host_association": ("user_host_association", "host", "user"),
    }
    for signal, evidence_names in signal_map.items():
        if bool(signals.get(signal)):
            values.update(evidence_names)
    return values


def _optional_evidence_keys(context: CuratedEnrichmentContext, required: list[str]) -> list[str]:
    values: list[str] = []
    for key in context.not_claimed_defaults:
        if key not in required:
            values.append(key)
    return values
