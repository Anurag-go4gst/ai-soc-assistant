from __future__ import annotations

from app.chat.evidence_planner import plan_evidence
from app.chat.intent_classifier import IntentClassification, build_query_to_intent
from app.query_understanding.parser import understand_query


def _plan(query: str):
    understanding = understand_query(query)
    q2i = build_query_to_intent(query=query, query_understanding=understanding)
    return plan_evidence(q2i.intent_classification, q2i.model_dump(), routed={}, query_understanding=understanding)


def test_policy_knowledge_is_rag_only_with_policy_context_required() -> None:
    plan = _plan("What is the escalation policy for repeated failed login alerts?")
    assert plan.answer_mode == "rag_only"
    assert plan.policy_context_required is True
    assert plan.spl_allowed is False
    assert plan.mcp_allowed is False


def test_out_of_registry_live_data_allows_spl_not_mcp() -> None:
    plan = _plan("Find failed-login users in the last 24 hours")
    assert plan.answer_mode == "live_investigation"
    assert plan.needs_spl is True
    # MCP is *needed* for a live answer but never *allowed*/executed in this repo
    # (Gate 2: distinguish "MCP needed for live answer" from "MCP allowed/executed").
    assert plan.needs_mcp is True
    assert plan.spl_allowed is True
    assert plan.mcp_allowed is False


def test_spl_generation_allows_spl_but_not_mcp() -> None:
    plan = _plan("Generate SPL for failed logins")
    assert plan.needs_spl is True
    assert plan.answer_mode == "spl_utility_authoring"
    # Review-only SPL artifact asks are utility: SPL yes, MCP not needed/allowed.
    assert plan.needs_mcp is False
    assert plan.spl_allowed is True
    assert plan.mcp_allowed is False
    assert (
        "universal_spl_utility_authoring" in plan.reasons
        or "explicit_spl_authoring_review_only" in plan.reasons
    )


def test_hybrid_recommends_policy_context_and_allows_live_path() -> None:
    plan = _plan(
        "Find accounts failing login in the last 24 hours, exclude service accounts, "
        "and tell me what analyst action I should take"
    )
    assert plan.answer_mode == "hybrid"
    assert plan.rag_phase == "pre_mcp"
    assert plan.policy_context_recommended is True
    assert plan.spl_allowed is True
    assert plan.mcp_allowed is True


def test_knowledge_only_uses_optional_rag_without_spl_or_mcp() -> None:
    plan = _plan("What is a DGA domain?")
    assert plan.answer_mode == "rag_only"
    assert plan.policy_context_required is False
    assert plan.policy_context_recommended is True
    assert plan.spl_allowed is False
    assert plan.mcp_allowed is False


def test_mitre_mapping_clarification_skips_spl_and_mcp() -> None:
    plan = _plan("Map this to MITRE")
    assert plan.answer_mode == "clarification"
    assert plan.requires_hil is True
    assert plan.spl_allowed is False
    assert plan.mcp_allowed is False


def test_evidence_plan_carries_known_weak_status_for_q046() -> None:
    plan = _plan("Which users have excessive failed logins?")

    assert plan.row_authority_summary is not None
    assert plan.row_authority_summary["question_ref"] == "q0.q046"
    assert plan.row_authority_summary["row_authority_status"] == "exact_known_weak_needs_enrichment"
    assert plan.row_authority_summary["s3_authority_ready"] is False


def test_evidence_plan_environment_kb_is_not_collected_telemetry() -> None:
    plan = _plan("Show firewall traffic by src_zone and dest_zone on port 443")

    assert plan.source_profile_binding_summary is not None
    assert plan.source_profile_binding_summary["environment_kb_is_telemetry"] is False


def test_normalized_slots_preserve_user_explicit_index_before_source_profile() -> None:
    plan = _plan("Generate SPL for index=scada_perf by rtu_id over last 24h")

    assert plan.normalized_slot_summary is not None
    slots = plan.normalized_slot_summary["normalized_slots"]
    sources = plan.normalized_slot_summary["slot_sources"]
    assert slots["index"] == "scada_perf"
    assert sources["index"] == "user_explicit"


def test_answer_pack_raw_status_not_loaded_at_runtime(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.use_cases.answer_packs.load_answer_packs",
        lambda: {
            "q0.q046": {
                "case_id": "q0.q046",
                "review_status": "draft",
                "required_evidence": ["raw_llm_only_field"],
                "raw_llm_prose": "This prose must never become runtime authority.",
            }
        },
    )

    plan = _plan("Which users have excessive failed logins?")

    assert plan.answer_pack_summary is None
    assert "raw_llm_only_field" not in plan.required_evidence_keys


def test_answer_pack_reviewed_status_enriches_evidence_plan(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.use_cases.answer_packs.load_answer_packs",
        lambda: {
            "q0.q046": {
                "case_id": "q0.q046",
                "review_status": "reviewed",
                "required_evidence": ["failed_login_count", "user"],
                "dependency_gaps": ["lookup_dependency"],
                "mitre_candidates": ["T1110"],
                "must_not_claim": ["account_compromise_without_success"],
                "raw_llm_prose": "Ignored even after review.",
            }
        },
    )

    plan = _plan("Which users have excessive failed logins?")

    assert plan.answer_pack_summary is not None
    assert plan.answer_pack_summary["raw_llm_prose_loaded"] is False
    assert "reviewed_answer_pack_projection" in plan.reasons
    assert "failed_login_count" in plan.required_evidence_keys
    assert "lookup_dependency" in plan.missing_required_evidence
    assert "T1110" in plan.mitre_candidates_metadata_only
    assert "account_compromise_without_success" in plan.unsupported_claims_avoid


def test_answer_pack_cannot_override_environment_kb(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.chat.evidence_planner.reviewed_answer_pack",
        lambda **_kwargs: {
            "case_id": "q0.q046",
            "review_status": "reviewed",
            "source_profile_hints": {"index": "pack_index"},
        },
    )
    plan = _plan("Generate SPL for index=scada_perf by rtu_id over last 24h")

    assert plan.answer_pack_summary is not None
    assert plan.normalized_slot_summary is not None
    assert plan.normalized_slot_summary["normalized_slots"]["index"] == "scada_perf"
    assert plan.normalized_slot_summary["slot_sources"]["index"] == "user_explicit"


def test_reference_knowledge_claim_guard() -> None:
    intent = IntentClassification(
        intent_family="reference_knowledge",
        primary_intent="reference_knowledge",
        query_type="ask_for_explanation",
        answer_goal=["reference_lookup"],
        confidence=0.9,
        confidence_band="high",
        requires_clarification=False,
        action_mode="recommend_only",
        reason="reference taxonomy lookup",
        requested_output_type="MITRE_MAPPING",
    )
    plan = plan_evidence(intent, {}, routed={})
    assert plan.needs_spl is False
    assert plan.needs_mcp is False
    assert plan.spl_allowed is False
    assert plan.mcp_allowed is False
    assert "confirmed exploitation" in (plan.unsupported_claims_avoid or [])
