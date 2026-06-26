"""Unit tests for explainability.debug_summary builder."""

from __future__ import annotations

from app.chat.debug_summary import build_debug_summary, llm_live_calls_from_payload, routing_list_fields


def _scada_like_payload() -> dict:
    return {
        "selected_skill": "spl_generation",
        "selected_use_case": {
            "use_case_id": "soc_generate_spl",
            "matched_patterns": ["spl query"],
        },
        "candidate_spl": {
            "generation_mode": "llm_spl_advisory_fallback",
            "candidate_spl_generated": True,
            "llm_fallback_status": "clarification_required",
        },
        "spl_validation": {
            "approved": False,
            "reject_reasons": ["disallowed_index", "disallowed_sourcetype"],
            "llm_supported": True,
            "llm_fallback_used": False,
        },
        "execution": {
            "status": "skipped",
            "block_reason": "mcp_not_allowed_by_evidence_plan",
        },
        "human_review": {
            "required": True,
            "review_type": "intent_clarification",
        },
        "run_contract": {
            "mcp_allowed": False,
            "effective_hil_required": True,
            "spl_block_reason": "spl_validation_failed",
            "routing": {"path_type": "use_case_catalog", "intent_family": "spl_generation_only"},
        },
        "control_plane_trace": {
            "routing_provenance": {
                "deterministic_match_path": "use_case_catalog",
                "use_case_id": "soc_generate_spl",
                "catalog_bundle": {"matched_patterns": ["spl query"]},
            },
            "query_to_intent": {
                "intent_family": "spl_generation_only",
                "candidate_mappings": {
                    "match_path": "use_case_catalog",
                    "use_case_ids": ["soc_generate_spl"],
                    "question_ref": None,
                },
                "llm_intent_assist_status": "skipped",
            },
            "hybrid_role_graph": {
                "roles": [
                    {
                        "role_id": "intent_shadow_classifier",
                        "enabled": False,
                        "skip_reason": "deterministic_exact_match_t0",
                    },
                    {
                        "role_id": "governed_composer",
                        "enabled": False,
                        "skip_reason": "draft_spl_preview_active",
                    },
                    {
                        "role_id": "route_plan_candidate_generator",
                        "enabled": False,
                        "skip_reason": "draft_spl_preview_active",
                    },
                ]
            },
            "llm_composer": {
                "llm_composer_used": False,
                "llm_blocked_reason": "draft_spl_preview_active",
            },
            "llm_turn_budget": {
                "records": [
                    {"role": "spl_t2_producer", "outcome": "dropped", "kind": "sidecar"},
                ]
            },
        },
    }


def test_build_debug_summary_scada_catalog_steal() -> None:
    summary = build_debug_summary(payload=_scada_like_payload())

    assert summary["routing"]["match_path"] == "use_case_catalog"
    assert summary["routing"]["use_case_id"] == "soc_generate_spl"
    assert summary["routing"]["matched_patterns"] == ["spl query"]
    assert summary["routing"]["intent_family"] == "spl_generation_only"

    assert summary["llm"]["live_calls"] == 0
    assert summary["llm"]["spl_path"] == "llm_spl_advisory_fallback"
    assert summary["llm"]["spl_live_called"] is False
    assert summary["llm"]["spl_outcome"] == "clarification_required"
    assert len(summary["llm"]["skipped_roles"]) == 3
    assert summary["llm"]["composer_skipped_reason"] == "draft_spl_preview_active"

    assert summary["spl"]["approved"] is False
    assert "disallowed_index" in summary["spl"]["reject_reasons"]

    assert summary["mcp"]["allowed"] is False
    assert summary["mcp"]["block_reason"] == "mcp_not_allowed_by_evidence_plan"

    assert summary["hil"]["required"] is True
    assert summary["hil"]["kind"] == "intent_clarification"


def test_llm_live_calls_counts_completed_only() -> None:
    payload = {
        "control_plane_trace": {
            "llm_turn_budget": {
                "records": [
                    {"outcome": "completed", "role": "intent_shadow_classifier"},
                    {"outcome": "dropped", "role": "spl_t2_producer"},
                ]
            }
        },
        "spl_validation": {"llm_supported": True},
    }
    assert llm_live_calls_from_payload(payload) == 1


def test_routing_list_fields_for_trace_row() -> None:
    summary = build_debug_summary(payload=_scada_like_payload())
    row = routing_list_fields(summary)
    assert row["match_path"] == "use_case_catalog"
    assert row["use_case_id"] == "soc_generate_spl"
    assert row["matched_pattern"] == "spl query"
    assert row["spl_path"] == "llm_spl_advisory_fallback"
