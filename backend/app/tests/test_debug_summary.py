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


def test_build_debug_summary_includes_qualification_tier() -> None:
    payload = _scada_like_payload()
    payload["resolved_query_contract"] = {
        "qualification_tier": "T1",
        "intent_family": "spl_generation_only",
        "answer_goal": "spl_artifact",
        "required_capabilities": ["spl"],
        "prohibited_capabilities": [],
        "ambiguity_state": "unambiguous",
        "clarification_required": False,
        "understanding_source": "deterministic_qualification",
        "qualification_source": "catalogue_exact",
        "entities": {"user": "should-not-surface"},
        "normalized_goal": "raw query echo must not surface",
        "selected_skill": "must-not-appear",
        "execution_eligible": True,
    }
    summary = build_debug_summary(payload=payload)
    resolved = summary["resolved_query"]
    assert resolved["qualification_tier"] == "T1"
    assert resolved["intent_family"] == "spl_generation_only"
    assert resolved["answer_goal"] == "spl_artifact"
    assert resolved["required_capabilities"] == ["spl"]
    assert resolved["ambiguity_state"] == "unambiguous"
    assert resolved["understanding_source"] == "deterministic_qualification"
    assert "selected_skill" not in resolved
    assert "execution_eligible" not in resolved
    assert "entities" not in resolved
    assert "normalized_goal" not in resolved


def test_redact_resolved_query_includes_semantic_t4_status_only() -> None:
    payload = _scada_like_payload()
    payload["resolved_query_contract"] = {
        "qualification_tier": "T4",
        "intent_family": "guided_investigation",
        "answer_goal": "procedural_steps",
        "ambiguity_state": "unambiguous",
        "understanding_source": "deterministic_qualification",
        "qualification_source": "deterministic",
        "provenance": {
            "semantic_t4": {
                "invoked": True,
                "accepted": False,
                "timed_out": True,
                "elapsed_ms": 2004,
                "rejected_reasons": ["timed_out"],
                "notes": ["llm_assist_timed_out", "drop this secret-looking note"],
            }
        },
        "entities": {"host": "nope"},
    }
    resolved = build_debug_summary(payload=payload)["resolved_query"]
    t4 = resolved["semantic_t4"]
    assert t4["invoked"] is True
    assert t4["accepted"] is False
    assert t4["timed_out"] is True
    assert t4["elapsed_ms"] == 2004
    assert t4["rejected_reasons"] == ["timed_out"]
    assert t4["notes"] == ["llm_assist_timed_out"]
    assert "entities" not in resolved


def test_redact_resolved_query_is_idempotent_for_semantic_t4() -> None:
    payload = _scada_like_payload()
    payload["control_plane_trace"] = {
        **payload["control_plane_trace"],
        "resolved_query": {
            "qualification_tier": "T4",
            "intent_family": "clarification_required",
            "answer_goal": "clarification",
            "semantic_t4": {
                "invoked": True,
                "accepted": False,
                "timed_out": True,
                "elapsed_ms": 2000,
                "rejected_reasons": ["timed_out"],
                "notes": ["llm_assist_timed_out"],
            },
        },
    }
    resolved = build_debug_summary(payload=payload)["resolved_query"]
    assert resolved["semantic_t4"]["invoked"] is True
    assert resolved["semantic_t4"]["timed_out"] is True


def test_resolved_query_block_has_no_skill_or_execution_authority() -> None:
    summary = build_debug_summary(payload=_scada_like_payload())
    resolved = summary["resolved_query"]
    assert "skill" not in resolved
    assert "execution_eligible" not in resolved
    dumped = str(resolved)
    assert "execution_eligible" not in dumped


def test_rp_graph_invoke_survives_with_qualification_tier_on_debug_summary(
    monkeypatch,
) -> None:
    monkeypatch.setattr("app.config.settings.mcp_global_execution_enabled", False)
    monkeypatch.setattr("app.config.settings.langgraph_orchestration_enabled", True)
    monkeypatch.setattr("app.config.settings.telemetry_mode", "none")
    monkeypatch.setattr("app.config.settings.ai_soc_telemetry_sink", "none")
    from app.graph.resource_planner_graph import run_chat_via_resource_planner_graph
    from app.schemas.requests import ChatRequest

    response = run_chat_via_resource_planner_graph(
        ChatRequest(message="What is the playbook for ransomware response?")
    )
    payload = response.model_dump(mode="json")
    summary = build_debug_summary(payload=payload)
    assert summary["resolved_query"]["qualification_tier"]
    assert "selected_skill" not in summary["resolved_query"]
    assert "execution_eligible" not in summary["resolved_query"]
    assert "dispatch_schedule" in summary["schedule"]
    assert "degrade_reason" in summary["schedule"]


def test_schedule_flag_off_omits_phase_merge_keeps_planned_dispatch() -> None:
    payload = _scada_like_payload()
    payload["plan_dispatch_trace"] = {
        "dispatch_source": "resource_plan_step_walk",
        "dispatch_schedule": ["workflow_spl", "execution"],
    }
    payload["evidence_plan"] = {
        "resource_plan": {
            "provenance": {"resource_plan_id": "rp-1"},
            "steps": [{"step_id": "s1"}, {"step_id": "s2"}],
        }
    }
    summary = build_debug_summary(payload=payload)
    schedule = summary["schedule"]
    assert schedule["dispatch_schedule"] == ["workflow_spl", "execution"]
    assert schedule["resource_plan_id"] == "rp-1"
    assert schedule["resource_plan_fingerprint"]
    assert schedule["phase_names"] == []
    assert schedule["degrade_reason"] is None


def test_schedule_flag_on_records_merge_and_degrade_reason() -> None:
    payload = _scada_like_payload()
    payload["session_role"] = "demo_analyst"
    payload["plan_dispatch_trace"] = {
        "dispatch_source": "resource_plan_step_walk",
        "dispatch_schedule": ["workflow_spl", "spl_postprocessor", "execution"],
        "execution_order": {
            "active": True,
            "downgrade_reason": None,
            "phase_merge": {
                "phase_contract": {
                    "schema_version": "phase_contract_v1",
                    "phases": [
                        {"name": "workflow_spl", "removable": False},
                        {"name": "spl_postprocessor", "removable": False},
                    ],
                }
            },
        },
    }
    payload["node_trace"] = [
        {"node_name": "workflow_spl", "duration_ms": 12},
        {"node_name": "execution", "duration_ms": 4},
    ]
    summary = build_debug_summary(payload=payload)
    schedule = summary["schedule"]
    assert schedule["degrade_reason"] == "merge"
    assert schedule["phase_names"] == ["workflow_spl", "spl_postprocessor"]
    assert schedule["session_role"] == "demo_analyst"
    assert schedule["phase_duration_ms"]["workflow_spl"] == 12
    assert "candidate_spl" not in schedule
    assert schedule["dispatch_schedule"] == ["workflow_spl", "spl_postprocessor", "execution"]


def test_schedule_v2_wins_degrade_reason() -> None:
    payload = _scada_like_payload()
    payload["plan_dispatch_trace"] = {
        "dispatch_schedule": ["rag_early"],
        "execution_order": {
            "active": False,
            "downgrade_reason": "dispatch_v2_projected_schedule",
        },
    }
    summary = build_debug_summary(payload=payload)
    assert summary["schedule"]["degrade_reason"] == "dispatch_v2_projected_schedule"
