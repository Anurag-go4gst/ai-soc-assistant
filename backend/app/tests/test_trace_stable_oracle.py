"""P1 T3: stable trace oracle is factual, versioned, and diagnostics-free."""

from __future__ import annotations

from app.chat.control_plane_trace import build_control_plane_trace


def test_run_shape_transition_names_the_factual_context_decision_site() -> None:
    trace = build_control_plane_trace(
        {
            "planning_decision": {"answer_mode": "rag_only"},
            "evidence_plan": {"answer_mode": "rag_only", "reasons": ["plan_reason"]},
        },
        context_sufficiency={"answer_mode": "abstain", "reason_codes": ["missing_evidence"]},
    )
    transition = trace["run_shape_transition"]
    assert transition["schema_version"] == "run_shape_transition_v2"
    assert transition["initial_decision_site"] == "planning_decision"
    assert transition["final_decision_site"] == "context_sufficiency"
    assert transition["authority"] == "context_sufficiency"
    assert transition["change_reasons"] == ["missing_evidence"]


def test_run_shape_transition_names_evidence_plan_when_it_supplies_final() -> None:
    trace = build_control_plane_trace(
        {
            "query_to_intent": {"answer_mode": "rag_only"},
            "evidence_plan": {"answer_mode": "hybrid", "reasons": ["live_data_required"]},
        }
    )
    transition = trace["run_shape_transition"]
    assert transition["initial_decision_site"] == "query_to_intent"
    assert transition["final_decision_site"] == "evidence_plan"
    assert transition["change_reasons"] == ["live_data_required"]


def test_stable_oracle_separates_artifact_review_from_execution_hil() -> None:
    trace = build_control_plane_trace(
        {
            "candidate_spl": {
                "candidate_spl": "index=main | head 10",
                "selected_candidate_spl_provider": "diagnostic_provider",
                "candidate_provider_reason": "diagnostic_reason",
            },
            "spl_validation": {"approved": False, "review_required_reason": "diagnostic_reason"},
            "run_contract": {"effective_hil_required": False},
            "final_evidence_gate": {"effective_hil_required": True},
            "evidence_state": {
                "schema_version": "minimal_evidence_state_v2",
                "required": ["mcp"],
                "obtained": [],
                "missing": ["mcp"],
                "stale": [],
                "invalidated": [],
                "blocked": [],
                "empty": ["mcp"],
                "diagnostic": ["execution_status"],
            },
            "execution": {"status": "blocked", "latency_ms": 417},
        }
    )
    oracle = trace["trace_oracle"]
    assert set(oracle) == {
        "schema_version",
        "llm_lifecycle",
        "spl_artifact",
        "execution_review",
        "run_shape_transition",
        "evidence_state",
    }
    assert set(oracle["llm_lifecycle"]) == {"schema_version", "states"}
    assert set(oracle["spl_artifact"]) == {"artifact_present", "artifact_review_required"}
    assert oracle["spl_artifact"] == {
        "artifact_present": True,
        "artifact_review_required": True,
    }
    assert oracle["execution_review"] == {
        "execution_hil_required": False,
        "decision_site": "run_contract",
    }
    assert set(oracle["run_shape_transition"]) == {
        "schema_version",
        "initial_run_shape",
        "final_run_shape",
        "changed",
        "initial_decision_site",
        "final_decision_site",
    }
    assert oracle["evidence_state"]["empty"] == ["mcp"]
    assert "diagnostic" not in oracle["evidence_state"]
    assert trace["evidence_state"]["diagnostic"] == ["execution_status"]
    assert "provider" not in str(oracle)
    assert "reason" not in str(oracle)
    assert "latency" not in str(oracle)


def test_execution_hil_can_be_true_without_artifact_review() -> None:
    trace = build_control_plane_trace(
        {
            "run_contract": {"effective_hil_required": True},
        }
    )
    oracle = trace["trace_oracle"]
    assert oracle["spl_artifact"]["artifact_review_required"] is False
    assert oracle["execution_review"]["execution_hil_required"] is True
