"""Deterministic intent classification for the chat control plane (Stage 1A)."""

from __future__ import annotations

from typing import Any

from app.chat.contracts.intent_classification import (
    ActionMode,
    AnswerGoal,
    ConfidenceBand,
    IntentClassification,
    LlmIntentAssistStatus,
    QueryToIntentResult,
)
from app.chat.contracts.llm_intent_advisory import LLMIntentAdvisory
from app.chat.llm_intent_advisor import adjudicate_llm_intent_advisory, apply_advisory_promotion
from app.chat.query_signals import extract_query_signals
from app.query_understanding.models import QueryUnderstandingResult


_CATALOG_MATCH_PATHS = frozenset({"use_case_catalog", "exact_105_plus_use_case_catalog"})


def _effective_match_path(
    query_understanding: QueryUnderstandingResult,
    *,
    routed_skill: str | None = None,
    routing_provenance: dict[str, Any] | None = None,
) -> str:
    path = query_understanding.deterministic_match_path or "out_of_registry"
    if isinstance(routing_provenance, dict):
        rescued = routing_provenance.get("deterministic_match_path")
        if isinstance(rescued, str) and rescued:
            return rescued
    if (
        routed_skill == "guided_investigation"
        and query_understanding.route_skill_candidate == "guided_investigation"
        and path in _CATALOG_MATCH_PATHS
    ):
        return "out_of_registry"
    return path


def build_candidate_mappings(
    query_understanding: QueryUnderstandingResult | None,
    *,
    routed_skill: str | None = None,
    routing_provenance: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if query_understanding is None:
        return {
            "question_ref": None,
            "use_case_ids": [],
            "match_path": "out_of_registry",
            "legacy_skill_hint": routed_skill,
        }
    return {
        "question_ref": query_understanding.mapped_question_ref,
        "use_case_ids": list(query_understanding.mapped_use_case_ids or []),
        "match_path": _effective_match_path(
            query_understanding,
            routed_skill=routed_skill,
            routing_provenance=routing_provenance,
        ),
        "legacy_skill_hint": routed_skill or query_understanding.mapped_primary_skill,
    }


def classify_intent(
    *,
    query: str,
    signals: dict[str, Any],
    candidate_mappings: dict[str, Any],
    query_understanding: QueryUnderstandingResult | None = None,
) -> IntentClassification:
    if signals.get("explicit_run_spl"):
        return _build_classification(
            intent_family="clarification_required",
            primary_intent="human_review",
            query_type="ask_for_next_action",
            answer_goal=["clarification", "analyst_action_guidance"],
            confidence=0.9,
            requires_clarification=True,
            requires_hil=True,
            action_mode="recommend_only",
            reason="Direct SPL execution and live-results request requires human review; execution is blocked.",
            requested_output_type="ACTION_PLAN",
        )

    if signals.get("block_or_contain"):
        return _build_classification(
            intent_family="clarification_required",
            primary_intent="human_review",
            query_type="ask_for_next_action",
            answer_goal=["clarification", "analyst_action_guidance"],
            confidence=0.82,
            requires_clarification=True,
            requires_hil=True,
            action_mode="recommend_only",
            reason="Destructive or containment action requires human review and overrides SPL generation.",
            requested_output_type="ACTION_PLAN",
        )

    if (
        (
            signals.get("investigation_hypothesis_guidance")
            or (
                signals.get("soc_investigation_shaped")
                and str(candidate_mappings.get("match_path") or "") == "out_of_registry"
            )
        )
        and str(candidate_mappings.get("legacy_skill_hint") or "") == "guided_investigation"
        and not signals.get("block_or_contain")
        and not signals.get("explicit_run_spl")
        and not signals.get("spl_generation")
    ):
        return _build_classification(
            intent_family="guided_investigation",
            primary_intent="investigation_guidance",
            query_type="investigation_with_guidance",
            answer_goal=["procedural_steps", "analyst_action_guidance"],
            confidence=0.52,
            requires_clarification=False,
            requires_hil=True,
            action_mode="recommend_only",
            reason="Investigation-guidance request receives governed, review-only hunt guidance instead of catalog SPL.",
            requested_output_type="INVESTIGATION",
        )

    if (
        signals.get("soc_investigation_shaped")
        and str(candidate_mappings.get("match_path") or "") == "out_of_registry"
        and not signals.get("block_or_contain")
        and not signals.get("explicit_run_spl")
    ):
        return _build_classification(
            intent_family="guided_investigation",
            primary_intent="investigation_guidance",
            query_type="investigation_with_guidance",
            answer_goal=["procedural_steps", "analyst_action_guidance"],
            confidence=0.52,
            requires_clarification=False,
            requires_hil=True,
            action_mode="recommend_only",
            reason="Out-of-registry SOC investigation request receives governed, review-only hunt guidance.",
            requested_output_type="INVESTIGATION",
        )

    if signals.get("conceptual_mitre_judgment"):
        return _build_classification(
            intent_family="mitre_explanation",
            primary_intent="mitre_explanation",
            secondary_intents=["analyst_action_guidance"],
            query_type="ask_for_mapping",
            answer_goal=["mitre_explanation", "analyst_action_guidance"],
            confidence=0.9,
            requires_clarification=False,
            action_mode="recommend_only",
            reason=(
                "Conceptual MITRE judgment requires a direct not-enough-to-confirm answer, "
                "candidate-only framing, and evidence preconditions without alert logs."
            ),
            requested_output_type="INVESTIGATION",
        )

    if signals.get("mitre_evidence_threshold"):
        return _build_classification(
            intent_family="hybrid_alert_review",
            primary_intent="attack_discovery",
            secondary_intents=["mitre_mapping"],
            query_type="ask_for_mapping",
            answer_goal=["procedural_steps", "mitre_explanation", "analyst_action_guidance"],
            confidence=0.9,
            requires_clarification=False,
            action_mode="recommend_only",
            reason=(
                "MITRE evidence-threshold question requires checklist, required evidence, "
                "and candidate-only framing without declaration."
            ),
            requested_output_type="INVESTIGATION",
        )

    if signals.get("spl_generation") and signals.get("run_execution"):
        return _build_classification(
            intent_family="spl_generation_and_run",
            primary_intent="spl_generation",
            secondary_intents=["live_investigation"],
            query_type="ask_for_query_generation_and_execution",
            answer_goal=["spl_artifact", "live_results"],
            confidence=0.88 if signals.get("has_specific_scope") else 0.84,
            requires_clarification=False,
            reason=(
                "User requested governed SPL generation and scoped MCP execution."
                if signals.get("has_specific_scope")
                else "User requested governed SPL generation and MCP execution; template defaults apply when scope is omitted."
            ),
            requested_output_type="INVESTIGATION",
        )

    if signals.get("use_case_review_guidance"):
        return _build_classification(
            intent_family="hybrid_alert_review",
            primary_intent="attack_discovery",
            secondary_intents=["mitre_mapping", "spl_generation"],
            query_type="ask_for_mapping",
            answer_goal=["severity_assessment", "mitre_mapping", "spl_artifact", "procedural_steps"],
            confidence=0.9,
            requires_clarification=False,
            action_mode="recommend_only",
            reason=(
                "Use-case investigation guidance with checklist, evidence requirements, "
                "candidate MITRE status, and review-only governed SPL without alert context."
            ),
            requested_output_type="INVESTIGATION",
        )

    if signals.get("spl_generation") and not signals.get("run_execution"):
        if signals.get("success_after_failure"):
            return _build_classification(
                intent_family="hybrid_alert_review",
                primary_intent="attack_discovery",
                secondary_intents=["mitre_mapping", "spl_generation"],
                query_type="ask_for_mapping",
                answer_goal=["severity_assessment", "mitre_mapping", "spl_artifact", "procedural_steps"],
                confidence=0.9,
                requires_clarification=False,
                action_mode="recommend_only",
                reason=(
                    "Success-after-failure search request with review-only SPL, "
                    "candidate MITRE status, and analyst guidance without execution."
                ),
                requested_output_type="INVESTIGATION",
            )
        return _build_classification(
            intent_family="spl_generation_only",
            primary_intent="spl_generation",
            query_type="ask_for_query_generation",
            answer_goal=["spl_artifact"],
            confidence=0.9,
            requires_clarification=False,
            reason="User requested SPL generation.",
            requested_output_type="SPL",
        )

    if signals.get("hybrid_alert_review"):
        return _build_classification(
            intent_family="hybrid_alert_review",
            primary_intent="attack_discovery",
            secondary_intents=["mitre_mapping", "spl_generation"],
            query_type="ask_for_mapping",
            answer_goal=["severity_assessment", "mitre_mapping", "spl_artifact"],
            confidence=0.9,
            requires_clarification=False,
            action_mode="recommend_only",
            reason=(
                "Alert review request combining severity assessment, MITRE mapping, "
                "and review-only governed SPL without execution."
            ),
            requested_output_type="INVESTIGATION",
        )

    if signals.get("mitre_explain"):
        return _build_classification(
            intent_family="mitre_explanation",
            primary_intent="mitre_explanation",
            query_type="ask_for_explanation",
            answer_goal=["mitre_explanation"],
            confidence=0.88,
            requires_clarification=False,
            reason="User asked for MITRE technique explanation.",
            requested_output_type="MITRE_MAPPING",
        )

    if signals.get("mitre_map"):
        needs_clarification = bool(signals.get("mitre_requires_alert_context"))
        return _build_classification(
            intent_family="mitre_mapping",
            primary_intent="mitre_mapping",
            query_type="ask_for_mapping",
            answer_goal=["mitre_mapping"] if not needs_clarification else ["clarification"],
            confidence=0.75 if needs_clarification else 0.85,
            requires_clarification=needs_clarification,
            reason="MITRE mapping request without sufficient alert context."
            if needs_clarification
            else "User requested MITRE mapping.",
            requested_output_type="MITRE_MAPPING",
        )

    normalized_query = str(signals.get("normalized_query") or query.lower())
    explicit_sop_only = (
        normalized_query.startswith(("show sop", "show runbook", "what is the playbook", "what is the sop"))
        or "show me the sop" in normalized_query
        or "show me the playbook" in normalized_query
        or "show me the runbook" in normalized_query
        or ("show me the" in normalized_query and "playbook" in normalized_query)
        or bool(signals.get("sop_show_request"))
    )
    if signals.get("playbook_procedure") and (
        explicit_sop_only or signals.get("spl_suppressed")
    ) and not any(
        signals.get(key)
        for key in ("spl_generation", "run_execution", "analyst_action", "time_window_24h")
    ):
        return _build_classification(
            intent_family="sop_or_playbook",
            primary_intent="knowledge_recall",
            query_type="sop_or_playbook",
            answer_goal=["procedural_steps", "policy_citation"],
            confidence=0.86,
            requires_clarification=False,
            reason="User asked for SOP/playbook/runbook guidance.",
            requested_output_type="SOP",
        )

    if signals.get("dns_beaconing") and signals.get("procedural_investigation") and not signals.get("live_investigation_verbs"):
        return _build_classification(
            intent_family="knowledge_only",
            primary_intent="knowledge_recall",
            secondary_intents=["mitre_mapping", "spl_generation"],
            query_type="ask_for_explanation",
            answer_goal=["procedural_steps", "mitre_mapping", "spl_artifact"],
            confidence=0.88,
            requires_clarification=False,
            reason="DNS beaconing investigation guidance without live alert context.",
            requested_output_type="INVESTIGATION",
        )

    if signals.get("procedural_investigation") and not signals.get("live_investigation_verbs"):
        return _build_classification(
            intent_family="knowledge_only",
            primary_intent="knowledge_recall",
            query_type="ask_for_explanation",
            answer_goal=["procedural_steps"],
            confidence=0.86,
            requires_clarification=False,
            reason="User asked for procedural investigation guidance.",
            requested_output_type="INVESTIGATION",
        )

    if signals.get("playbook_procedure") and not signals.get("live_investigation_verbs"):
        return _build_classification(
            intent_family="sop_or_playbook",
            primary_intent="knowledge_recall",
            query_type="sop_or_playbook",
            answer_goal=["procedural_steps", "policy_citation"],
            confidence=0.86,
            requires_clarification=False,
            reason="User asked for SOP/playbook/runbook guidance.",
            requested_output_type="SOP",
        )

    policy_intent = signals.get("policy_terms") or signals.get("escalation_without_policy_word")
    live_data_intent = signals.get("live_investigation_verbs") and (
        signals.get("failed_login") or signals.get("time_window_24h") or "investigate" in signals.get("normalized_query", "")
    )

    if policy_intent and not live_data_intent:
        return _build_classification(
            intent_family="policy_knowledge",
            primary_intent="knowledge_recall",
            query_type="ask_for_policy",
            answer_goal=["policy_citation"],
            confidence=0.88,
            requires_clarification=False,
            reason="User asked for escalation/policy knowledge without a live investigation request.",
            requested_output_type="SOP",
        )

    if signals.get("knowledge_definition") and not signals.get("live_investigation_verbs") and not policy_intent:
        return _build_classification(
            intent_family="knowledge_only",
            primary_intent="knowledge_recall",
            query_type="ask_for_explanation",
            answer_goal=["procedural_steps"],
            confidence=0.84,
            requires_clarification=False,
            reason="Definitional knowledge question.",
            requested_output_type="INVESTIGATION",
        )

    hybrid_markers = (
        live_data_intent
        and (signals.get("analyst_action") or signals.get("playbook_procedure") or signals.get("dga"))
    )
    if hybrid_markers:
        goals: list[AnswerGoal] = ["live_results"]
        if signals.get("analyst_action"):
            goals.append("analyst_action_guidance")
        if signals.get("playbook_procedure"):
            goals.append("procedural_steps")
        return _build_classification(
            intent_family="hybrid_investigation_plus_policy",
            primary_intent="live_investigation",
            secondary_intents=["analyst_action_guidance"] if signals.get("analyst_action") else [],
            query_type="investigation_with_guidance",
            answer_goal=goals,
            confidence=0.87,
            requires_clarification=False,
            reason="Live investigation combined with analyst guidance or procedural playbook context.",
            requested_output_type="INVESTIGATION",
        )

    if live_data_intent:
        return _build_classification(
            intent_family="live_investigation",
            primary_intent="attack_discovery",
            query_type="ask_for_live_results",
            answer_goal=["live_results"],
            confidence=0.86,
            requires_clarification=False,
            reason="User requested live investigative results.",
            requested_output_type="INVESTIGATION",
        )

    if signals.get("explicit_search_intent") and not signals.get("run_execution"):
        goals: list[AnswerGoal] = ["spl_artifact"]
        if signals.get("investigation_triage_guidance") or signals.get("procedural_investigation"):
            goals.append("procedural_steps")
        if signals.get("analyst_action"):
            goals.append("analyst_action_guidance")
        return _build_classification(
            intent_family="spl_generation_only",
            primary_intent="spl_generation",
            query_type="ask_for_query_generation",
            answer_goal=goals,
            confidence=0.9,
            requires_clarification=False,
            reason="User requested explicit log search or review-only SPL drafting.",
            requested_output_type="SPL",
        )

    # Exact-105 analytics bridge: registry metadata is authoritative; the
    # analytics_aggregation phrasing signal is only a paraphrase fallback.
    # Sits below all knowledge/SOP/MITRE/unsafe branches so a 105 question
    # phrased as SOP/MITRE/containment keeps its existing path; this branch
    # rescues queries that would otherwise die in clarification.
    exact_match = str(candidate_mappings.get("match_path") or "") in {
        "exact_105_question",
        "exact_105_plus_use_case_catalog",
    }
    registry_analytics = bool(signals.get("exact_105_analytics")) and exact_match
    registry_hunt = bool(signals.get("exact_105_hunt_spl")) and exact_match
    if (registry_analytics or registry_hunt or signals.get("analytics_aggregation")) and not (
        signals.get("block_or_contain") or signals.get("explicit_run_spl")
    ):
        if registry_analytics:
            reason = (
                "Exact 105-question analytics match (top-N aggregation) inherited from the "
                "question registry; review-only SPL drafting path, execution disabled."
            )
        elif registry_hunt:
            reason = (
                "Exact 105-question hunt/detection match inherited from the question "
                "registry; review-only SPL drafting path, execution disabled."
            )
        else:
            reason = "Analytics/ranking question detected; review-only SPL drafting path, execution disabled."
        return _build_classification(
            intent_family="spl_generation_only",
            primary_intent="spl_generation",
            query_type="ask_for_query_generation",
            answer_goal=["spl_artifact"],
            confidence=0.9 if (registry_analytics or registry_hunt) else 0.82,
            requires_clarification=False,
            reason=reason,
            requested_output_type="SPL",
        )

    # Registry use-case catalog rescue: a query that maps to a known SOC use case
    # (a real catalog/near/semantic registry match, not just exact-105) must route
    # to its skill — not die in clarification. Without this, every non-exact
    # phrasing of an in-catalog question collapsed to clarification_required, which
    # the route adjudicator then forced to knowledge_recall. This is the population
    # that lets the product handle real, variably-phrased SOC questions.
    catalog_match = str(candidate_mappings.get("match_path") or "") in {
        "use_case_catalog",
        "exact_105_plus_use_case_catalog",
        "near_105_question",
        "semantic_105_question",
    }
    has_use_case = bool(candidate_mappings.get("use_case_ids"))
    if (
        catalog_match
        and has_use_case
        and not signals.get("block_or_contain")
        and not signals.get("explicit_run_spl")
    ):
        use_case_ids = [str(item).lower() for item in (candidate_mappings.get("use_case_ids") or [])]
        skill_hint = str(candidate_mappings.get("legacy_skill_hint") or "").lower()
        # Note: explicit_mitre_context is NOT a knowledge signal — failed-login and
        # other alert queries carry MITRE context too. Use the conceptual-judgment
        # signal and knowledge-shaped use-case ids only.
        knowledge_shaped = (
            signals.get("conceptual_mitre_judgment")
            or skill_hint in {"knowledge_recall", "retrieve_approved_context"}
            or any(
                tok in uc
                for uc in use_case_ids
                for tok in ("mitre", "map_alert", "sop", "policy", "knowledge")
            )
        )
        spl_shaped = (
            signals.get("analytics_aggregation")
            or skill_hint in {"spl_search", "spl_generation", "aggregate_and_rank", "threshold_anomaly"}
        )
        if knowledge_shaped:
            return _build_classification(
                intent_family="knowledge_only",
                primary_intent="knowledge_recall",
                query_type="ask_for_explanation",
                answer_goal=["analyst_action_guidance"],
                confidence=0.82,
                requires_clarification=False,
                reason="Maps to a catalog knowledge/MITRE/policy use case; governed knowledge-recall path.",
                requested_output_type=None,
            )
        if spl_shaped:
            return _build_classification(
                intent_family="spl_generation_only",
                primary_intent="spl_generation",
                query_type="ask_for_query_generation",
                answer_goal=["spl_artifact"],
                confidence=0.78,
                requires_clarification=False,
                reason="Maps to a catalog analytics/search use case; review-only SPL drafting, execution disabled.",
                requested_output_type="SPL",
            )
        if signals.get("alert_summary_shaped") or signals.get("alert_context_present"):
            return _build_classification(
                intent_family="hybrid_alert_review",
                primary_intent="attack_discovery",
                query_type="investigation_with_guidance",
                answer_goal=["procedural_steps", "analyst_action_guidance"],
                confidence=0.72,
                requires_clarification=False,
                action_mode="recommend_only",
                reason="Maps to a catalog alert/review use case; route to the registry skill (review-only).",
                requested_output_type="INVESTIGATION",
            )
        return _build_classification(
            intent_family="live_investigation",
            primary_intent="attack_discovery",
            query_type="investigation_with_guidance",
            answer_goal=["procedural_steps", "analyst_action_guidance"],
            confidence=0.72,
            requires_clarification=False,
            action_mode="recommend_only",
            reason="Maps to a catalog SOC use case; route to the registry skill (review-only, execution disabled).",
            requested_output_type="INVESTIGATION",
        )

    # Terminal floor (Batch 0 — intent cascade hardening). This sits AFTER every
    # match rung above (incl. the catalog rescue) and AFTER Engine 1/2; Engine 3
    # advisory promotion runs later in build_query_to_intent and can still upgrade
    # the family. The 3-way decision replaces the old generic clarification dump:
    #   * off-topic / non-SOC                -> honest clarification (out of scope)
    #   * SOC-shaped, actionable, unmatched  -> guided_investigation (review-only)
    #   * everything else (genuine ambiguity) -> diagnosed clarification
    # The genuine-ambiguity branch preserves clarification sentinels such as
    # pg.clar.001 ("Check if this alert is serious."), which carries no
    # security/telemetry subject and so is not an actionable hunt.
    if signals.get("non_soc_or_out_of_scope"):
        return _build_classification(
            intent_family="clarification_required",
            primary_intent="knowledge_recall",
            query_type="ask_for_explanation",
            answer_goal=["clarification"],
            confidence=0.45,
            requires_clarification=True,
            reason="Request is out of SOC scope; clarification recommended.",
            requested_output_type=None,
        )

    if signals.get("soc_actionable_hunt"):
        return _build_classification(
            intent_family="guided_investigation",
            primary_intent="investigation_guidance",
            query_type="investigation_with_guidance",
            answer_goal=["procedural_steps", "analyst_action_guidance"],
            confidence=0.52,
            requires_clarification=False,
            requires_hil=True,
            action_mode="recommend_only",
            reason=(
                "SOC-shaped, actionable hunt with no registry match; governed, "
                "review-only guided investigation instead of a clarification dump."
            ),
            requested_output_type="INVESTIGATION",
        )

    return _build_classification(
        intent_family="clarification_required",
        primary_intent="knowledge_recall",
        query_type="ask_for_explanation",
        answer_goal=["clarification"],
        confidence=0.45,
        requires_clarification=True,
        reason="Insufficient deterministic intent signals; clarification recommended.",
        requested_output_type=None,
    )


def build_query_to_intent(
    *,
    query: str,
    query_understanding: QueryUnderstandingResult | None = None,
    routed_skill: str | None = None,
    routing_provenance: dict[str, Any] | None = None,
    llm_intent_advisory: LLMIntentAdvisory | None = None,
) -> QueryToIntentResult:
    signals = extract_query_signals(query, query_understanding)
    candidate_mappings = build_candidate_mappings(
        query_understanding,
        routed_skill=routed_skill,
        routing_provenance=routing_provenance,
    )
    intent = classify_intent(
        query=query,
        signals=signals,
        candidate_mappings=candidate_mappings,
        query_understanding=query_understanding,
    )
    conflicts = _intent_conflicts(intent, candidate_mappings, query_understanding)
    adjudicated_advisory = adjudicate_llm_intent_advisory(
        llm_intent_advisory,
        query_understanding=query_understanding,
        candidate_mappings=candidate_mappings,
    )
    # WS1 T1.3: out_of_registry intake may adopt a registry-validated advisory
    # candidate; deterministic rungs and unsafe/clarification outcomes always win.
    # Veto scope: explicit human-review outcomes (unsafe action, run-SPL
    # demand) always win. The default insufficient-signals clarification does
    # NOT veto — those queries are exactly the population promotion rescues.
    explicit_review = bool(intent.requires_hil or intent.primary_intent == "human_review")
    candidate_mappings, adjudicated_advisory = apply_advisory_promotion(
        advisory=adjudicated_advisory,
        candidate_mappings=candidate_mappings,
        intent_requires_clarification=explicit_review,
        intent_requires_hil=explicit_review,
        query=query,
    )
    # MANDATORY post-promotion reconcile (§10.2 gap): apply_advisory_promotion
    # upgrades candidate_mappings.match_path only; intent_classification is still
    # the pre-promotion (often clarification) result, so planning/evidence never
    # see the upgrade. When promotion succeeded, re-derive intent_family from the
    # promoted registry ref/use-case so the upgrade reaches evidence_plan/path_type.
    # Deterministic-wins precedence is preserved: explicit human-review/unsafe
    # outcomes (explicit_review) are never overridden.
    intent = _reconcile_intent_after_promotion(
        intent=intent,
        candidate_mappings=candidate_mappings,
        explicit_review=explicit_review,
    )
    llm_status = _llm_intent_assist_status(
        query_understanding,
        candidate_mappings,
        adjudicated_advisory,
    )
    return QueryToIntentResult(
        query_signals=signals,
        candidate_mappings=candidate_mappings,
        intent_classification=intent,
        intent_conflicts=conflicts,
        llm_intent_assist_status=llm_status,
        llm_intent_advisory=adjudicated_advisory,
    )


def _family_from_promoted_skill(skill: str | None, pattern_type: str | None) -> str:
    """Map a promoted registry skill / pattern_type to an actionable intent_family.

    Mirrors the deterministic exact-105 / catalog-rescue mappings already used in
    classify_intent so the promoted route lands on the same family it would have
    if the registry had matched directly. Defaults to the review-only
    live_investigation family for unknown SOC skills.
    """
    skill_norm = (skill or "").strip().lower()
    pattern_norm = (pattern_type or "").strip().lower()
    knowledge_skills = {"knowledge_recall", "retrieve_approved_context"}
    spl_skills = {
        "spl_search",
        "spl_generation",
        "aggregate_and_rank",
        "threshold_anomaly",
    }
    if skill_norm in knowledge_skills:
        return "knowledge_only"
    if skill_norm in spl_skills or pattern_norm in (
        "top_n_aggregation",
        "threshold_anomaly",
    ):
        return "spl_generation_only"
    # attack_discovery and any other unmatched SOC skill -> review-only live path.
    return "live_investigation"


def _reconcile_intent_after_promotion(
    *,
    intent: IntentClassification,
    candidate_mappings: dict[str, Any],
    explicit_review: bool,
) -> IntentClassification:
    """Re-derive intent_family from a promoted registry ref/use-case (§10.2).

    Only acts when (a) Engine-3 promotion actually fired
    (match_path == "llm_promoted_with_registry_validation") and (b) the
    pre-promotion intent was the default clarification (not an explicit
    human-review/unsafe outcome and not an already-actionable family). This keeps
    deterministic-wins precedence: a query the deterministic rungs already routed
    to a real family is left untouched.
    """
    if explicit_review:
        return intent
    if str(candidate_mappings.get("match_path") or "") != "llm_promoted_with_registry_validation":
        return intent
    if intent.intent_family != "clarification_required":
        return intent

    question_ref = candidate_mappings.get("question_ref")
    use_case_ids = candidate_mappings.get("use_case_ids") or []
    skill: str | None = None
    pattern_type: str | None = None

    if question_ref:
        from app.coverage.question_runtime_map import question_runtime_entry

        entry = question_runtime_entry(str(question_ref))
        if entry:
            skill = entry.get("proposed_primary_skill") or entry.get("legacy_router_intent_hint")
            pattern_type = entry.get("pattern_type")
    elif use_case_ids:
        from app.use_cases.registry import load_use_case_catalog

        catalog = {item.use_case_id: item for item in load_use_case_catalog()}
        item = catalog.get(str(use_case_ids[0]))
        if item is not None:
            skill = getattr(item, "primary_skill", None)

    if skill is None and pattern_type is None:
        # Could not resolve metadata; leave clarification rather than guess.
        return intent

    family = _family_from_promoted_skill(skill, pattern_type)
    requested_output = "SPL" if family == "spl_generation_only" else "INVESTIGATION"
    if family == "knowledge_only":
        requested_output = None
    return _build_classification(
        intent_family=family,
        primary_intent="spl_generation" if family == "spl_generation_only" else "attack_discovery",
        query_type="ask_for_query_generation"
        if family == "spl_generation_only"
        else "investigation_with_guidance",
        answer_goal=["spl_artifact"]
        if family == "spl_generation_only"
        else ["procedural_steps", "analyst_action_guidance"],
        confidence=0.7,
        requires_clarification=False,
        action_mode=None if family == "spl_generation_only" else "recommend_only",
        reason=(
            "Engine-3 LLM advisory promoted an out-of-registry query to a "
            "registry-validated route; intent reconciled to the promoted family "
            "(review-only, execution disabled)."
        ),
        requested_output_type=requested_output,
    )


def _build_classification(
    *,
    intent_family: str,
    primary_intent: str,
    query_type: str,
    answer_goal: list[AnswerGoal],
    confidence: float,
    requires_clarification: bool,
    reason: str,
    requested_output_type: str | None = None,
    secondary_intents: list[str] | None = None,
    requires_hil: bool = False,
    action_mode: ActionMode | None = None,
) -> IntentClassification:
    return IntentClassification(
        intent_family=intent_family,  # type: ignore[arg-type]
        primary_intent=primary_intent,
        secondary_intents=list(secondary_intents or []),
        query_type=query_type,  # type: ignore[arg-type]
        answer_goal=answer_goal,
        requested_output_type=requested_output_type,
        confidence=confidence,
        confidence_band=_confidence_band(confidence),
        requires_clarification=requires_clarification,
        requires_hil=requires_hil,
        action_mode=action_mode,
        reason=reason,
    )


def _confidence_band(score: float) -> ConfidenceBand:
    if score >= 0.8:
        return "high"
    if score >= 0.55:
        return "medium"
    return "low"


def _intent_conflicts(
    intent: IntentClassification,
    candidate_mappings: dict[str, Any],
    query_understanding: QueryUnderstandingResult | None,
) -> list[dict[str, Any]]:
    if not query_understanding:
        return []
    warnings = list(query_understanding.registry_warnings or [])
    conflicts: list[dict[str, Any]] = []
    if "question_registry_use_case_skill_conflict" in warnings:
        conflicts.append(
            {
                "type": "registry_skill_conflict",
                "registry_skill": candidate_mappings.get("legacy_skill_hint"),
                "intent_family": intent.intent_family,
            }
        )
    legacy = candidate_mappings.get("legacy_skill_hint")
    if legacy == "attack_discovery" and intent.intent_family in {"policy_knowledge", "sop_or_playbook", "knowledge_only"}:
        conflicts.append(
            {
                "type": "intent_over_legacy_skill_hint",
                "legacy_skill_hint": legacy,
                "intent_family": intent.intent_family,
            }
        )
    return conflicts


def _llm_intent_assist_status(
    query_understanding: QueryUnderstandingResult | None,
    candidate_mappings: dict[str, Any],
    llm_intent_advisory: LLMIntentAdvisory | None = None,
) -> LlmIntentAssistStatus:
    if llm_intent_advisory is not None and llm_intent_advisory.adjudication_status != "skipped":
        return llm_intent_advisory.adjudication_status
    if query_understanding is None:
        return "skipped"
    match_path = candidate_mappings.get("match_path")
    if match_path in {"near_105_question", "exact_105_question", "exact_105_plus_use_case_catalog"}:
        if query_understanding.llm_advisory_recommended or match_path == "near_105_question":
            return "accepted"
    if query_understanding.llm_advisory_recommended:
        return "attempted"
    return "skipped"
