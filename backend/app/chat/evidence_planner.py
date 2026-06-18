from __future__ import annotations

from typing import Any

from app.chat.contracts.evidence_plan import EvidencePlan
from app.chat.contracts.intent_classification import IntentClassification
from app.config import settings
from app.chat.planning_decision import _apply_completeness_floor
from app.use_cases.content_enrichment import (
    CuratedEnrichmentContext,
    get_content_enrichment,
    get_runtime_curated_enrichment,
    resolve_use_case_activation,
)

_COMPLETENESS_FLOOR_REASON = "completeness_floor_escalated_thin_in_catalog_under_route"

_CATALOG_PROJECTION_WHEN_INACTIVE = frozenset(
    {
        "auth_failed_login_spike",
        "auth_success_after_failure",
        "edr_powershell_suspicious_command",
        "dns_beaconing_candidate",
        "critical_notable_mitre_review",
        "dns_tunneling_candidate",
        "dns_unusual_query_volume",
        "edr_suspicious_process",
        "email_phishing_header_review",
        "net_vpn_login_anomaly",
        "endpoint_ransomware_impact_review",
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
        plan = _maybe_apply_completeness_floor_to_plan(
            plan,
            intent=intent,
            use_case_id=selected_use_case_id,
            query_understanding=query_understanding,
        )
        enriched = _apply_curated_enrichment(
            plan,
            use_case_id=selected_use_case_id,
            query_to_intent=query_to_intent,
            query_understanding=query_understanding,
        )
        return _attach_resource_plan(
            enriched,
            intent=intent,
            use_case_id=selected_use_case_id,
            query_understanding=query_understanding,
            routed_skill=str((routed or {}).get("skill") or "") or None,
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

    if family == "guided_investigation":
        return with_enrichment(
            EvidencePlan(
                answer_mode="guided_investigation",
                rag_phase="rag_only",
                needs_rag=True,
                needs_spl=False,
                needs_mcp=False,
                needs_mitre=False,
                spl_allowed=True,
                mcp_allowed=False,
                policy_context_required=False,
                policy_context_recommended=True,
                requires_hil=True,
                needs_hil=True,
                needs_clarification=False,
                action_mode="recommend_only",
                rag_no_match_behavior="general_guidance_allowed",
                reasons=["out_of_registry_guided_investigation"],
                limitations=[
                    "This question is outside the approved 105-question and use-case registries.",
                    "No live query was executed; validate the checklist against local telemetry and playbooks.",
                    "No MITRE technique or incident severity is asserted without evidence.",
                ],
                checklist=[
                    "Confirm the asset owner, criticality, and expected communications.",
                    "Review firewall, DNS, proxy, and endpoint telemetry for the destination.",
                    "Compare first-seen time, periodicity, bytes, ports, and peer hosts against baseline.",
                    "Validate vendor, maintenance, and approved remote-access activity.",
                    "Document findings and escalate only after evidence is corroborated.",
                ],
                investigation_workflow=[
                    "Scope the affected OT and IT assets and the observation window.",
                    "Collect network and endpoint evidence without executing candidate SPL.",
                    "Test benign, misconfiguration, compromise, and vendor-access hypotheses.",
                    "Have an analyst validate conclusions and next actions.",
                ],
                required_sources=["firewall", "dns", "proxy", "endpoint"],
                optional_sources=["asset_inventory", "change_records", "vendor_access_records"],
                unsupported_claims_avoid=["confirmed compromise", "confirmed MITRE technique", "P1/P2 severity"],
                evidence_plan_reason="out_of_registry_guided_investigation",
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


def _evidence_plan_path_type_for_completeness(plan: EvidencePlan) -> str | None:
    """Map an evidence plan to a planning path_type for completeness-floor checks."""
    if plan.answer_mode == "rag_only":
        return "rag_only"
    if plan.answer_mode == "live_investigation" and not plan.needs_spl and not plan.needs_mcp:
        return "generic_soc_guidance"
    return None


def _maybe_apply_completeness_floor_to_plan(
    plan: EvidencePlan,
    *,
    intent: IntentClassification,
    use_case_id: str | None,
    query_understanding: Any,
) -> EvidencePlan:
    """Escalate thin in-catalog under-routes so route_adjudication sees SPL/hybrid."""
    path_type = _evidence_plan_path_type_for_completeness(plan)
    if path_type is None:
        return plan
    curated = get_runtime_curated_enrichment(use_case_id) if use_case_id else None
    escalated_path, applied = _apply_completeness_floor(
        path_type,
        intent.model_dump(),
        curated,
        query_understanding,
    )
    if not applied or escalated_path != "hybrid_investigation":
        return plan
    reasons = list(plan.reasons or [])
    if _COMPLETENESS_FLOOR_REASON not in reasons:
        reasons.append(_COMPLETENESS_FLOOR_REASON)
    return plan.model_copy(
        update={
            "answer_mode": "hybrid",
            "rag_phase": "pre_mcp",
            "needs_rag": True,
            "needs_spl": True,
            "needs_mcp": False,
            "needs_mitre": True,
            "spl_allowed": True,
            "mcp_allowed": False,
            "policy_context_recommended": True,
            "reasons": reasons,
        }
    )


def _attach_resource_plan(
    plan: EvidencePlan,
    *,
    intent: IntentClassification,
    use_case_id: str | None,
    query_understanding: Any,
    routed_skill: str | None = None,
) -> EvidencePlan:
    """Attach the composed step plan (WS0 T0.3). Booleans stay authoritative;
    composition failure must never break evidence planning."""
    from app.planner.composer import compose_resource_plan
    from app.planner.llm_plan_bridge import bridge_enabled, bridge_trigger_match

    match_path = getattr(query_understanding, "deterministic_match_path", None)
    try:
        composed = compose_resource_plan(
            plan,
            intent_family=intent.intent_family,
            use_case_id=use_case_id or plan.use_case_id,
            match_path=match_path,
            skill_id=routed_skill,
        )
        # T0.5 (revised after PowerGrid latency diagnosis 2026-06-11): the LLM
        # plan bridge is never called inline — a blocking model call on the
        # live path added flat latency while never changing dispatch. Unmatched
        # questions are marked for off-path proposal (scorecard/async use).
        if bridge_trigger_match(match_path) and bridge_enabled():
            composed.provenance["llm_bridge"] = "deferred_not_inline"
    except Exception:
        return plan
    return plan.model_copy(update={"resource_plan": composed.model_dump()})


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
        if _should_catalog_project_when_enrichment_blocked(use_case_id, activation):
            return _apply_catalog_projection(
                plan,
                use_case_id=use_case_id,
                query_to_intent=query_to_intent,
                query_understanding=query_understanding,
                runtime_support_status=activation.runtime_support_status,
                evidence_plan_reason="curated_enrichment_not_runtime_active",
            )
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
            "investigation_workflow": list(context.investigation_workflow),
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


def _should_catalog_project_when_enrichment_blocked(use_case_id: str, activation: Any) -> bool:
    if use_case_id not in _CATALOG_PROJECTION_WHEN_INACTIVE:
        return False
    if get_content_enrichment(use_case_id) is None:
        return False
    if activation.runtime_support_status in {"metadata_only", "unsupported"}:
        return False
    return True


def _evidence_plan_has_guidance(plan: dict[str, Any] | None) -> bool:
    if not isinstance(plan, dict):
        return False
    return bool(
        plan.get("checklist")
        or plan.get("investigation_workflow")
        or plan.get("required_evidence_keys")
        or plan.get("limitations")
    )


def _merge_catalog_evidence_plan(base: dict[str, Any], catalog: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key in (
        "required_evidence_keys",
        "optional_evidence_keys",
        "present_evidence_keys",
        "missing_required_evidence",
        "checklist",
        "investigation_workflow",
        "answer_rules",
        "limitations",
        "unsupported_claims_avoid",
        "mitre_candidates_metadata_only",
        "required_sources",
        "optional_sources",
        "recommended_pivots",
    ):
        if not merged.get(key) and catalog.get(key):
            merged[key] = catalog[key]
    if _evidence_plan_has_guidance(catalog) and merged.get("evidence_plan_reason") in {
        "curated_enrichment_not_runtime_active",
        "curated_enrichment_context_unavailable",
    }:
        merged["evidence_plan_reason"] = catalog.get("evidence_plan_reason") or merged.get(
            "evidence_plan_reason"
        )
    return merged


def resolve_analyst_evidence_plan(
    evidence_plan: dict[str, Any] | EvidencePlan | None,
    *,
    use_case_id: str | None,
    intent_classification: dict[str, Any] | None = None,
    query_to_intent: dict[str, Any] | None = None,
    query_understanding: Any = None,
) -> dict[str, Any] | None:
    """Ensure analyst-facing evidence plans include catalog guidance when enrichment is blocked."""
    plan_dict = (
        evidence_plan.model_dump()
        if isinstance(evidence_plan, EvidencePlan)
        else (evidence_plan if isinstance(evidence_plan, dict) else None)
    )
    if plan_dict and _evidence_plan_has_guidance(plan_dict):
        return plan_dict
    catalog = build_catalog_display_evidence_plan(
        use_case_id=use_case_id,
        intent_classification=intent_classification,
        query_to_intent=query_to_intent,
        query_understanding=query_understanding,
    )
    if catalog and plan_dict:
        return _merge_catalog_evidence_plan(plan_dict, catalog)
    return catalog or plan_dict


def build_catalog_display_evidence_plan(
    *,
    use_case_id: str | None,
    intent_classification: dict[str, Any] | None = None,
    query_to_intent: dict[str, Any] | None = None,
    query_understanding: Any = None,
) -> dict[str, Any] | None:
    """Project catalog enrichment for analyst-card display when control plane is off."""
    if not use_case_id or use_case_id not in _CATALOG_PROJECTION_WHEN_INACTIVE:
        return None
    if get_content_enrichment(use_case_id) is None:
        return None

    intent = intent_classification if isinstance(intent_classification, dict) else {}
    if not intent and isinstance(query_to_intent, dict):
        nested = query_to_intent.get("intent_classification")
        intent = nested if isinstance(nested, dict) else {}
    family = str(intent.get("intent_family") or "hybrid_alert_review")
    if family in {"policy_knowledge", "sop_or_playbook", "knowledge_only", "mitre_explanation"}:
        answer_mode = "rag_only"
        rag_phase = "rag_only"
        needs_rag = True
        needs_spl = False
        needs_mitre = family != "knowledge_only"
    elif family == "hybrid_investigation_plus_policy":
        answer_mode = "hybrid"
        rag_phase = "pre_mcp"
        needs_rag = True
        needs_spl = True
        needs_mitre = "mitre_mapping" in (intent.get("answer_goal") or [])
    else:
        answer_mode = "live_investigation"
        rag_phase = "post_mcp"
        needs_rag = False
        needs_spl = True
        needs_mitre = True

    base = EvidencePlan(
        answer_mode=answer_mode,
        rag_phase=rag_phase,
        needs_rag=needs_rag,
        needs_spl=needs_spl,
        needs_mcp=False,
        needs_mitre=needs_mitre,
        spl_allowed=answer_mode != "rag_only",
        mcp_allowed=False,
        policy_context_required=family in {"policy_knowledge", "sop_or_playbook"},
        policy_context_recommended=family in {"knowledge_only", "mitre_explanation"},
        reasons=["legacy_display_catalog_projection"],
    )
    plan = _apply_catalog_projection(
        base,
        use_case_id=use_case_id,
        query_to_intent=query_to_intent,
        query_understanding=query_understanding,
        evidence_plan_reason="legacy_display_catalog_projection",
    )
    if not (
        plan.checklist
        or plan.investigation_workflow
        or plan.required_evidence_keys
        or plan.limitations
    ):
        return None
    return plan.model_dump()


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
            "investigation_workflow": [str(item) for item in record.get("investigation_workflow") or [] if item],
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
