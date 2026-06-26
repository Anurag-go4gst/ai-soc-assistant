from __future__ import annotations

from app.chat.evidence_planner import plan_evidence
from app.chat.intent_classifier import build_query_to_intent
from app.coverage.promotion_lifecycle import (
    AUTHORITY_READY_EFFECTIVE,
    DEMOTED_THIS_TURN,
    can_skip_llm_for_t0,
    effective_promotion_status,
    promotion_gate_decision,
)
from app.query_understanding.parser import understand_query


def test_promotion_requires_reviewed_pack_and_passing_golden() -> None:
    blocked = promotion_gate_decision(
        stored_promotion_status="not_in_manifest",
        reviewed_pack_loaded=False,
        golden_passed=True,
        s3_authority_ready=True,
    )
    allowed = promotion_gate_decision(
        stored_promotion_status="not_in_manifest",
        reviewed_pack_loaded=True,
        golden_passed=True,
        s3_authority_ready=True,
    )

    assert blocked["promotion_allowed"] is False
    assert "reviewed_answer_pack_required" in blocked["blockers"]
    assert allowed["promotion_allowed"] is True


def test_demotion_on_environment_mapping_drift() -> None:
    summary = effective_promotion_status(
        stored_promotion_status="in_manifest",
        row_authority_summary={"s3_authority_ready": True, "row_authority_status": "exact_known_authority_ready"},
        source_profile_binding_summary={"source_profile_bindings_missing": [{"slot": "index"}]},
    )

    assert summary["effective_promotion_status"] == DEMOTED_THIS_TURN
    assert summary["stored_status_mutated"] is False
    assert "environment_mapping_drift" in summary["demotion_reasons"]


def test_demotion_on_failed_golden() -> None:
    summary = effective_promotion_status(
        stored_promotion_status="in_manifest",
        row_authority_summary={"s3_authority_ready": True, "row_authority_status": "exact_known_authority_ready"},
        golden_passed=False,
    )

    assert summary["effective_promotion_status"] == DEMOTED_THIS_TURN
    assert "golden_test_failed" in summary["demotion_reasons"]


def test_demotion_on_mitre_validation_conflict() -> None:
    summary = effective_promotion_status(
        stored_promotion_status="in_manifest",
        row_authority_summary={"s3_authority_ready": True, "row_authority_status": "exact_known_authority_ready"},
        mitre_validation_conflict=True,
    )

    assert summary["effective_promotion_status"] == DEMOTED_THIS_TURN
    assert "mitre_validation_conflict" in summary["demotion_reasons"]


def test_t0_promoted_row_skips_llm_only_after_authority_ready() -> None:
    ready = effective_promotion_status(
        stored_promotion_status="in_manifest",
        row_authority_summary={"s3_authority_ready": True, "row_authority_status": "exact_known_authority_ready"},
    )
    weak = effective_promotion_status(
        stored_promotion_status="in_manifest",
        row_authority_summary={
            "s3_authority_ready": False,
            "row_authority_status": "exact_known_needs_detection_binding",
        },
    )

    assert ready["effective_promotion_status"] == AUTHORITY_READY_EFFECTIVE
    assert can_skip_llm_for_t0(ready) is True
    assert can_skip_llm_for_t0(weak) is False


def test_runtime_demotion_is_non_destructive_to_stored_promotion_status() -> None:
    summary = effective_promotion_status(
        stored_promotion_status="in_manifest",
        row_authority_summary={"s3_authority_ready": False, "row_authority_status": "exact_known_needs_lookup"},
    )

    assert summary["stored_promotion_status"] == "in_manifest"
    assert summary["effective_promotion_status"] == DEMOTED_THIS_TURN
    assert summary["stored_status_mutated"] is False


def test_evidence_plan_carries_runtime_demotion_trace() -> None:
    query = "Which users have excessive failed logins?"
    understanding = understand_query(query)
    q2i = build_query_to_intent(query=query, query_understanding=understanding)

    plan = plan_evidence(
        q2i.intent_classification,
        query_to_intent=q2i.model_dump(),
        routed={},
        query_understanding=understanding,
    )

    assert plan.promotion_lifecycle_summary is not None
    assert plan.promotion_lifecycle_summary["stored_status_mutated"] is False
    assert plan.promotion_lifecycle_summary["stored_promotion_status"] == "in_manifest"
