from __future__ import annotations

from typing import Any

from app.chat.contracts.evidence_plan import EvidencePlan
from app.chat.contracts.intent_classification import IntentClassification

_VALID_FAMILIES: frozenset[str] = frozenset(
    {
        "policy_knowledge",
        "live_investigation",
        "spl_generation_only",
        "spl_generation_and_run",
        "hybrid_investigation_plus_policy",
        "hybrid_alert_review",
        "mitre_mapping",
        "mitre_explanation",
        "knowledge_only",
        "clarification_required",
        "sop_or_playbook",
        "guided_investigation",
        "alert_summary",
        "github_investigation",
        "cve_investigation",
        "reference_knowledge",
    }
)
from app.chat.query_signals import is_live_data_request
from app.chat.spl_authoring_intent import (
    is_explicit_review_only_spl_authoring,
    is_universal_utility_spl_authoring,
)
from app.config import settings
from app.planner.resource_plan_authority import apply_test_resource_plan_shadow_if_allowed
from app.chat.planning_decision import _apply_completeness_floor
from app.chat.multi_leg_evidence import compose_multi_leg_evidence
from app.chat.t2_review_checklist import query_resolves_t2_source_profile
from app.coverage.question_runtime_map import question_runtime_entry
from app.coverage.promotion_lifecycle import effective_promotion_status
from app.coverage.row_authority import classify_runtime_row_authority, project_s3_authority_ready
from app.spl.slot_constraint_projection import projection_from_bindings
from app.spl.source_profile_bindings import build_source_profile_binding_slots
from app.spl.user_constraint_bindings import build_user_constraint_bindings
from app.use_cases.answer_packs import answer_pack_summary, reviewed_answer_pack
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
        "edr_suspicious_process",
        "email_phishing_header_review",
        "net_vpn_login_anomaly",
        "endpoint_ransomware_impact_review",
    }
)


def _deterministic_match_path_from_inputs(
    query_understanding: Any | None,
    query_to_intent: dict[str, Any] | None,
) -> str | None:
    """Resolve catalogue match path when available; None when unknown."""
    if query_understanding is not None:
        path = getattr(query_understanding, "deterministic_match_path", None)
        if isinstance(path, str) and path.strip():
            return path.strip()
        if isinstance(query_understanding, dict):
            path = query_understanding.get("deterministic_match_path")
            if isinstance(path, str) and path.strip():
                return path.strip()
    if isinstance(query_to_intent, dict):
        qu = query_to_intent.get("query_understanding")
        if isinstance(qu, dict):
            path = qu.get("deterministic_match_path")
            if isinstance(path, str) and path.strip():
                return path.strip()
        prov = query_to_intent.get("routing_provenance")
        if isinstance(prov, dict):
            path = prov.get("deterministic_match_path")
            if isinstance(path, str) and path.strip():
                return path.strip()
    return None


def plan_evidence(
    intent_classification: dict[str, Any] | IntentClassification,
    query_to_intent: dict[str, Any] | None = None,
    routed: dict[str, Any] | None = None,
    query_understanding: Any = None,
    selected_use_case: Any = None,
    user_query: str | None = None,
) -> EvidencePlan:
    """Plan evidence paths from intent only.

    `query_to_intent` and `routed` are accepted for future trace/HIL hints; this
    phase deliberately avoids re-reading user text or legacy route keywords.
    `user_query` is accepted solely for guided_investigation signal-class resolution
    so the checklist/investigation_workflow carry query-specific items.
    """
    intent_raw = (
        intent_classification
        if isinstance(intent_classification, dict)
        else intent_classification.model_dump()
    )
    family_raw = str(intent_raw.get("intent_family") or "")
    if family_raw not in _VALID_FAMILIES:
        return EvidencePlan(
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
            action_mode="hil_required",
            reasons=["unknown_intent_family_fail_closed"],
        )
    intent = (
        intent_classification
        if isinstance(intent_classification, IntentClassification)
        else IntentClassification.model_validate(intent_raw)
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
        enriched = _apply_reviewed_answer_pack(
            enriched,
            use_case_id=selected_use_case_id,
            query_understanding=query_understanding,
        )
        raw_query = str(getattr(query_understanding, "raw_query", "") or "")
        if not query_resolves_t2_source_profile(raw_query):
            multi_leg = compose_multi_leg_evidence(raw_query)
            if multi_leg:
                enriched = enriched.model_copy(update=multi_leg)
        enriched = _attach_canonical_handoff_summaries(
            enriched,
            query_to_intent=query_to_intent,
            query_understanding=query_understanding,
        )
        return apply_test_resource_plan_shadow_if_allowed(
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

    if family == "alert_summary":
        return with_enrichment(
            EvidencePlan(
                answer_mode="rag_only",
                rag_phase="rag_only",
                needs_rag=False,
                needs_spl=False,
                needs_mcp=False,
                needs_mitre=False,
                spl_allowed=False,
                mcp_allowed=False,
                policy_context_required=False,
                policy_context_recommended=False,
                requires_hil=False,
                action_mode="recommend_only",
                rag_no_match_behavior="general_guidance_allowed",
                reasons=["alert_summary_no_spl"],
            )
        )

    if family == "reference_knowledge":
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
                requires_hil=False,
                action_mode="recommend_only",
                rag_no_match_behavior="general_guidance_allowed",
                reasons=["reference_taxonomy_lookup"],
                required_evidence_keys=["reference_dataset"],
                required_sources=["reference_registry"],
                unsupported_claims_avoid=[
                    "live environment exposure",
                    "confirmed exploitation",
                    "confirmed alert mapping",
                ],
                evidence_plan_reason="reference_taxonomy_lookup",
            )
        )

    if family == "github_investigation":
        return with_enrichment(
            EvidencePlan(
                answer_mode="guided_investigation",
                rag_phase="rag_only",
                needs_rag=True,
                needs_spl=False,
                needs_mcp=False,
                needs_mitre=False,
                spl_allowed=False,
                mcp_allowed=False,
                policy_context_required=False,
                policy_context_recommended=True,
                requires_hil=True,
                needs_hil=True,
                needs_clarification=False,
                action_mode="recommend_only",
                rag_no_match_behavior="general_guidance_allowed",
                reasons=["github_investigation_review_only"],
                limitations=[
                    "No live GitHub API query or Splunk search was performed in this turn.",
                    "Conclusions are candidate-only until PAT, commit, workflow, and audit evidence is collected.",
                    "No confirmed MITRE technique or incident severity is asserted.",
                ],
                checklist=[
                    "Actor / username: tie the PAT or OAuth identity to GitHub org/repo membership.",
                    "Token type / PAT provenance: scope, creation, last use, rotation/revocation status.",
                    "Commit SHA / timeline: commits, authors, and push times in the requested window.",
                    "Workflow file / diff: changed .github/workflows paths, jobs, and secret references.",
                    "Audit log events: repo.push, workflow_dispatch, oauth_access, git.push for the actor.",
                ],
                investigation_workflow=[
                    "Scope repos, workflows, and identities in the observation window.",
                    "Collect GitHub audit log and token metadata before containment decisions.",
                    "Test leaked-PAT, compromised-maintainer, and legitimate-automation hypotheses.",
                    "Have an analyst validate before revoking tokens or disabling workflows.",
                ],
                required_sources=["github_audit_log", "github_token_metadata", "workflow_history"],
                optional_sources=["siem_auth_events", "secret_scanner", "idp_signin_logs"],
                unsupported_claims_avoid=[
                    "confirmed compromise",
                    "confirmed MITRE technique",
                    "execution_eligible",
                ],
                evidence_plan_reason="github_investigation_review_only",
            )
        )

    if family == "cve_investigation":
        return with_enrichment(
            EvidencePlan(
                answer_mode="guided_investigation",
                rag_phase="rag_only",
                needs_rag=True,
                needs_spl=False,
                needs_mcp=False,
                needs_mitre=False,
                spl_allowed=False,
                mcp_allowed=False,
                policy_context_required=False,
                policy_context_recommended=True,
                requires_hil=True,
                needs_hil=True,
                needs_clarification=False,
                action_mode="recommend_only",
                rag_no_match_behavior="general_guidance_allowed",
                reasons=["cve_investigation_review_only"],
                limitations=[
                    "No live vulnerability scan or Splunk search was performed in this turn.",
                    "Conclusions are candidate-only until inventory, version, and exposure evidence is collected.",
                ],
                checklist=[
                    "Installed package/version mapping for affected software on in-scope hosts.",
                    "Exposure signals: services, auth events, and changes near the advisory window.",
                    "vulnerability_source snapshot/onboarding status before unpatched claims.",
                    "Missing scanner/CMDB proof and exploit-attempt telemetry explicitly listed.",
                ],
                investigation_workflow=[
                    "Confirm CVE scope and affected products from the advisory.",
                    "Correlate local inventory and logs without live scanning.",
                    "List missing evidence before severity or patch-priority claims.",
                ],
                required_evidence_keys=["vulnerability_source"],
                required_sources=["asset_inventory", "package_versions", "vulnerability_source"],
                optional_sources=["scanner_output", "auth_logs", "change_tickets"],
                unsupported_claims_avoid=[
                    "confirmed exploitation",
                    "confirmed patch gap without inventory proof",
                    "execution_eligible",
                ],
                evidence_plan_reason="cve_investigation_review_only",
            )
        )

    if family == "guided_investigation":
        hybrid_enabled = bool(
            True
            and settings.ai_soc_guided_hybrid_investigation_enabled
        )
        composable = bool(settings.ai_soc_guided_composable_planning_enabled)
        # Resolve signal-class-specific hypotheses and evidence items from the query.
        # These flow into the AnswerContract (analyst_checklist_safe / investigation_steps)
        # so the synthesis LLM narrates specific items instead of a generic fallback.
        _query_for_signal = user_query or (
            getattr(query_understanding, "normalized_query", None)
            if query_understanding is not None and not isinstance(query_understanding, dict)
            else (query_understanding or {}).get("normalized_query")
            if isinstance(query_understanding, dict)
            else None
        )
        _sc_checklist: list[str] = []
        _sc_workflow: list[str] = []
        if _query_for_signal:
            from app.chat.signal_class_guidance import _TEMPLATES, classify_signal_class
            _sc = classify_signal_class(_query_for_signal)
            _tmpl = _TEMPLATES.get(_sc) or {}
            _sc_checklist = [str(h) for h in (_tmpl.get("hypotheses") or []) if h]
            _sc_workflow = [str(e) for e in (_tmpl.get("evidence") or []) if e]
        guided_plan = EvidencePlan(
            answer_mode="guided_investigation",
            rag_phase="pre_mcp" if composable else "rag_only",
            needs_rag=True,
            needs_spl=bool(composable),
            needs_mcp=bool(composable),
            needs_mitre=False,
            spl_allowed=bool(composable),
            mcp_allowed=bool(composable),
            policy_context_required=False,
            policy_context_recommended=True,
            requires_hil=True,
            needs_hil=True,
            needs_clarification=False,
            action_mode="recommend_only",
            rag_no_match_behavior="general_guidance_allowed",
            reasons=[
                "out_of_registry_guided_investigation",
                *(["guided_composable_planning_enabled"] if composable else []),
            ],
            limitations=[
                "This question is outside the approved 105-question and use-case registries.",
                (
                    "Composable planning may include governed SPL/MCP reads after approval;"
                    " writes remain blocked."
                    if composable
                    else "No live query was performed; validate the checklist against local telemetry and playbooks."
                ),
                "No MITRE technique or incident severity is asserted without evidence.",
            ],
            checklist=_sc_checklist or [
                "Confirm the asset owner, criticality, and expected communications.",
                "Review firewall, DNS, proxy, and endpoint telemetry for the destination.",
                "Compare first-seen time, periodicity, bytes, ports, and peer hosts against baseline.",
                "Validate vendor, maintenance, and approved remote-access activity.",
                "Document findings and escalate only after evidence is corroborated.",
            ],
            investigation_workflow=_sc_workflow or [
                "Scope the affected OT and IT assets and the observation window.",
                "Collect network and endpoint evidence without executing candidate SPL.",
                "Test benign, misconfiguration, compromise, and vendor-access hypotheses.",
                "Have an analyst validate conclusions and next actions.",
            ],
            required_sources=["firewall", "dns", "proxy", "endpoint"],
            optional_sources=["asset_inventory", "change_records", "vendor_access_records"],
            unsupported_claims_avoid=["confirmed compromise", "confirmed MITRE technique", "P1/P2 severity"],
            evidence_plan_reason=(
                "guided_composable_planning"
                if composable
                else "out_of_registry_guided_investigation"
            ),
        )
        _q2i_signals: dict[str, Any] = {}
        if isinstance(query_to_intent, dict):
            raw_signals = query_to_intent.get("query_signals")
            if isinstance(raw_signals, dict):
                _q2i_signals = raw_signals
        _hybrid_advisory = bool(
            (
                _q2i_signals.get("hybrid_advisory_source_health")
                or _q2i_signals.get("hybrid_advisory_process_aware_ot")
            )
            and not _q2i_signals.get("command_mode_active")
        )
        if _hybrid_advisory:
            # Analyst-visible planning for hybrid advisory shapes (not command spine).
            guided_plan = guided_plan.model_copy(
                update={
                    "discovery_allowed": True,
                    "spl_review_allowed": True,
                    "safe_spl_execution_allowed": False,
                    "freeform_spl_execution_allowed": False,
                    "mcp_action_allowed": False,
                    "requires_hil": True,
                    "needs_hil": True,
                    "reasons": [
                        *guided_plan.reasons,
                        "hybrid_advisory_evidence_plan",
                    ],
                    "limitations": [
                        *guided_plan.limitations,
                        "Review-only SPL may be prepared; live MCP search requires analyst approval.",
                    ],
                }
            )
        if hybrid_enabled:
            guided_plan = guided_plan.model_copy(
                update={
                    "discovery_allowed": True,
                    "investigation_planning_enabled": True,
                    "spl_review_allowed": True,
                    "safe_spl_execution_allowed": False,
                    "freeform_spl_execution_allowed": False,
                    "mcp_action_allowed": False,
                    "reasons": [
                        *guided_plan.reasons,
                        "guided_hybrid_investigation_enabled",
                    ],
                }
            )
        elif settings.ai_soc_guided_mcp_discovery_enabled and not _hybrid_advisory:
            guided_plan = guided_plan.model_copy(
                update={
                    "discovery_allowed": True,
                    "reasons": [
                        *guided_plan.reasons,
                        "guided_mcp_discovery_lane_enabled",
                    ],
                }
            )
        return with_enrichment(guided_plan)

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
        signals = (query_to_intent or {}).get("query_signals") if isinstance(query_to_intent, dict) else {}
        raw_query = str(getattr(query_understanding, "raw_query", "") or "")
        if isinstance(signals, dict) and is_universal_utility_spl_authoring(raw_query, signals):
            return with_enrichment(
                EvidencePlan(
                    answer_mode="spl_utility_authoring",
                    rag_phase="post_mcp",
                    needs_rag=False,
                    needs_spl=True,
                    needs_mcp=False,
                    needs_mitre=False,
                    spl_allowed=True,
                    mcp_allowed=False,
                    policy_context_required=False,
                    policy_context_recommended=False,
                    requires_hil=False,
                    action_mode="recommend_only",
                    reasons=["universal_spl_utility_authoring"],
                    answer_rules=[
                        "render_spl_first",
                        "governance_trace_only",
                        "no_source_profile_clarification_for_placeholder",
                    ],
                )
            )
        # Explicit review-only SPL authoring for out-of-catalogue Final RQCs only.
        # Catalogue-matched SPL artifact rows keep the existing live_investigation
        # path (MCP search eligibility pending validation). Live-data *interest*
        # alone must not convert an out-of-registry SPL ask into investigation
        # packaging when MCP/evidence is unavailable.
        if is_explicit_review_only_spl_authoring(signals if isinstance(signals, dict) else {}):
            from app.chat.lane_router import is_known_catalogue_match

            match_path = _deterministic_match_path_from_inputs(query_understanding, query_to_intent)
            # Only relabel explicit SPL authoring when match path is known and
            # out-of-catalogue. Unknown match path keeps prior live_investigation
            # planner shape (e.g. unit fixtures without query_understanding).
            if match_path is not None and not is_known_catalogue_match(match_path):
                live_interest = is_live_data_request(signals if isinstance(signals, dict) else {})
                return with_enrichment(
                    EvidencePlan(
                        answer_mode="spl_utility_authoring",
                        rag_phase="post_mcp",
                        needs_rag=False,
                        needs_spl=True,
                        needs_mcp=False,
                        needs_mitre=False,
                        spl_allowed=True,
                        mcp_allowed=False,
                        mcp_available=live_interest if live_interest else None,
                        policy_context_required=False,
                        policy_context_recommended=False,
                        requires_hil=False,
                        action_mode="recommend_only",
                        discovery_allowed=True,
                        reasons=[
                            "explicit_spl_authoring_review_only",
                            *(
                                ["live_data_interest_not_investigation_product"]
                                if live_interest
                                else []
                            ),
                        ],
                        answer_rules=[
                            "render_spl_first",
                            "governance_trace_only",
                            "no_source_profile_clarification_for_placeholder",
                        ],
                    )
                )
        live_data_request = is_live_data_request(signals if isinstance(signals, dict) else {})
        # Least privilege for out-of-catalogue work. The 2026-07 all-tier MCP grant was
        # written as `live_data_request and control_plane_enabled`; canonical cutover
        # was removed at the canonical cutover the conjunct collapsed to `and True`,
        # silently widening the grant so every out-of-catalogue live-data ask reported
        # mcp_allowed=true. Catalogue-matched asks (T1-T3) keep the grant they already had;
        # out-of-catalogue asks do not get authorisation from a routing default.
        # ``mcp_available`` still discloses that the system *could* search live data, so
        # capability stays visible while authorisation stays with the final planner and
        # governance for a specific committed ResourcePlan. Downstream gating (validated
        # normalized_spl, tool selection, per-call HIL confirmation at
        # evaluate_mcp_execution) is unchanged and still applies on top.
        from app.chat.lane_router import is_known_catalogue_match

        match_path = _deterministic_match_path_from_inputs(query_understanding, query_to_intent)
        catalogue_matched = bool(match_path and is_known_catalogue_match(match_path))
        mcp_authorised = live_data_request and catalogue_matched
        return with_enrichment(
            EvidencePlan(
                answer_mode="live_investigation",
                rag_phase="post_mcp",
                needs_rag=False,
                needs_spl=True,
                # ``needs_mcp`` stays descriptive (the answer wants live data);
                # ``mcp_allowed`` is the authorisation and the only execution gate.
                needs_mcp=live_data_request,
                needs_mitre=False,
                spl_allowed=True,
                mcp_allowed=mcp_authorised,
                mcp_available=live_data_request,
                policy_context_required=False,
                policy_context_recommended=False,
                discovery_allowed=True if True else None,
                reasons=[
                    "spl_artifact_requested",
                    *(
                        ["live_data_request_mcp_search_eligible_pending_validation"]
                        if mcp_authorised
                        else ["live_data_available_mcp_not_authorised_for_out_of_catalogue"]
                        if live_data_request
                        else []
                    ),
                ],
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

    if family == "live_investigation":
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
            action_mode="hil_required",
            reasons=["unknown_intent_family_fail_closed"],
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


def _attach_canonical_handoff_summaries(
    plan: EvidencePlan,
    *,
    query_to_intent: dict[str, Any] | None,
    query_understanding: Any,
) -> EvidencePlan:
    updates: dict[str, Any] = {}
    row_summary = _row_authority_summary(query_understanding)
    if row_summary is not None:
        updates["row_authority_summary"] = row_summary
    raw_query = str(getattr(query_understanding, "raw_query", "") or "")
    if raw_query:
        source_profile = build_source_profile_binding_slots(raw_query)
        source_profile_trace = source_profile.trace()
        updates["source_profile_binding_summary"] = {
            **source_profile_trace,
            "environment_kb_is_telemetry": False,
        }
        try:
            bindings = build_user_constraint_bindings(
                raw_query,
                llm_intent_advisory=(query_to_intent or {}).get("llm_intent_advisory"),
                query_understanding=query_understanding,
                extra_slots=source_profile.slots,
                source_profile_trace=source_profile_trace,
            )
            projection = projection_from_bindings(
                bindings,
                built_at_stage="evidence_planning",
                source_profile_defaults=dict(source_profile.slots),
            )
            updates["normalized_slot_summary"] = {
                "planning_snapshot": True,
                "normalized_slots": dict(bindings.normalized_slots),
                "slot_sources": dict(bindings.slot_sources),
                "validation_status": dict(bindings.validation_status),
                "unbound_constraints": list(projection.unbound_constraints),
                "shift_hour_binding_trace": dict(
                    (bindings.debug_trace or {}).get("shift_hour_binding_trace") or {}
                ),
            }
            updates["slot_constraint_projection_summary"] = {
                **projection.to_dict(),
                "planning_snapshot": True,
            }
            updates["handoff_drift_from_final_spl"] = False
        except Exception:
            updates["normalized_slot_summary"] = {
                "normalized_slots": {},
                "slot_sources": {},
                "validation_status": {},
                "unbound_constraints": [{"reason": "binding_summary_unavailable"}],
            }
    lifecycle = effective_promotion_status(
        stored_promotion_status=(row_summary or {}).get("promotion_status") if row_summary else None,
        row_authority_summary=row_summary,
        source_profile_binding_summary=updates.get("source_profile_binding_summary"),
        answer_pack_summary=plan.answer_pack_summary,
    )
    if lifecycle["stored_promotion_status"] or lifecycle["demotion_reasons"]:
        updates["promotion_lifecycle_summary"] = lifecycle
    return plan.model_copy(update=updates) if updates else plan


def _row_authority_summary(query_understanding: Any) -> dict[str, Any] | None:
    question_ref = getattr(query_understanding, "mapped_question_ref", None)
    if not isinstance(question_ref, str) or not question_ref.strip():
        return None
    entry = question_runtime_entry(question_ref)
    if entry is None:
        return None
    status, blockers = classify_runtime_row_authority(entry)
    return {
        "question_ref": str(entry.get("question_ref") or question_ref),
        "row_authority_status": status,
        "s3_authority_ready": project_s3_authority_ready(status),
        "promotion_status": entry.get("promotion_status"),
        "manifest_coverage_id": entry.get("manifest_coverage_id"),
        "manifest_readiness": entry.get("manifest_readiness"),
        "dependency_class": entry.get("dependency_class"),
        "route_blocked": bool(entry.get("route_blocked")),
        "blockers": blockers,
    }


def _apply_reviewed_answer_pack(
    plan: EvidencePlan,
    *,
    use_case_id: str | None,
    query_understanding: Any,
) -> EvidencePlan:
    question_ref = getattr(query_understanding, "mapped_question_ref", None)
    pack = reviewed_answer_pack(
        case_id=str(question_ref) if isinstance(question_ref, str) else None,
        use_case_id=use_case_id,
    )
    if pack is None:
        return plan
    updates: dict[str, Any] = {
        "answer_pack_summary": answer_pack_summary(pack),
        "reasons": list(dict.fromkeys([*plan.reasons, "reviewed_answer_pack_projection"])),
    }
    _merge_pack_list_field(updates, plan, pack, "required_evidence_keys", "required_evidence")
    _merge_pack_list_field(updates, plan, pack, "optional_evidence_keys", "optional_evidence")
    _merge_pack_list_field(updates, plan, pack, "required_sources", "source_needs")
    _merge_pack_list_field(updates, plan, pack, "limitations", "caveats")
    _merge_pack_list_field(updates, plan, pack, "unsupported_claims_avoid", "must_not_claim")
    _merge_pack_list_field(updates, plan, pack, "mitre_candidates_metadata_only", "mitre_candidates")
    _merge_pack_list_field(updates, plan, pack, "missing_required_evidence", "dependency_gaps")
    if not plan.evidence_plan_reason:
        updates["evidence_plan_reason"] = "reviewed_answer_pack_projection"
    return plan.model_copy(update=updates)


def _merge_pack_list_field(
    updates: dict[str, Any],
    plan: EvidencePlan,
    pack: dict[str, Any],
    plan_field: str,
    pack_field: str,
) -> None:
    incoming = [str(item) for item in pack.get(pack_field) or [] if str(item).strip()]
    if not incoming:
        return
    current = [str(item) for item in getattr(plan, plan_field, []) or [] if str(item).strip()]
    updates[plan_field] = list(dict.fromkeys([*current, *incoming]))


def _apply_curated_enrichment(
    plan: EvidencePlan,
    *,
    use_case_id: str | None,
    query_to_intent: dict[str, Any] | None,
    query_understanding: Any,
) -> EvidencePlan:
    if not use_case_id:
        return plan

    if not (
        settings.ai_soc_curated_enrichment_activation_enabled
        or settings.ai_soc_runtime_enrichment_enabled
    ):
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
