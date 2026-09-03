"""STANDARD reviewer export: compaction, canonical ES, LLM counts, no heavy dupes."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.chat.debug_summary import build_debug_summary
from app.chat.final_output_trace import build_final_output_trace
from app.chat.llm_interaction_trace import build_llm_interaction_record
from app.chat.reviewer_trace import assemble_forensic_bundle, build_reviewer_trace, compact_timeline_event
from app.chat.trace_effective_state import build_effective_state_projection

_FIXTURE = Path(__file__).parent / "fixtures" / "trace_consistency" / "p2_review_only_spl_payload.json"


def _p2_payload() -> dict[str, Any]:
    return json.loads(_FIXTURE.read_text())


def _p2_interactions() -> list[dict[str, Any]]:
    return [
        build_llm_interaction_record(
            role="spl_advisory_generator",
            provider_label="foundation-sec-instruct",
            system_prompt="Return detection plan JSON.",
            user_prompt="Investigation request:\nP2",
            response_schema={"type": "json_schema"},
            temperature=0.0,
            max_tokens=800,
            raw_text='{"data_domain":"auth"}',
            parsed_payload={"data_domain": "auth"},
            finish_reason="stop",
            transport_status="completed",
            parse_status="parsed",
            schema_status="valid",
            quality_status="failed",
            reject_reasons=["missing_aggregation"],
            accepted=False,
            contributed_to_final_output=False,
            latency_ms=1314,
        ),
        build_llm_interaction_record(
            role="review_only_spl_synthesis",
            stage="synthesis",
            system_prompt="Explain the SPL.",
            user_prompt="SYNTHESIS_INPUT_JSON: {}",
            temperature=0.0,
            max_tokens=400,
            raw_text="not balanced",
            finish_reason="stop",
            transport_status="completed",
            parse_status="failed",
            reject_reasons=["no_balanced_json_object"],
            accepted=False,
            fallback_selected=True,
            fallback_reason="no_balanced_json_object",
            latency_ms=1376,
        ),
    ]


def _p2_forensic(*, with_llm: bool = True) -> dict[str, Any]:
    payload = _p2_payload()
    summary = build_debug_summary(payload=payload)
    effective = summary.get("effective_state") or build_effective_state_projection(payload)
    interactions = _p2_interactions() if with_llm else []
    events = [
        {
            "kind": "rag_retrieval",
            "created_at": "2026-09-03T00:00:00+00:00",
            "event": {
                "evidence_origin": "stub_rag",
                "retrieval_workflow_stage": "spl_source_resolve",
                "status": "retrieved",
                "result_count": 5,
            },
        },
        {
            "kind": "llm_call",
            "created_at": "2026-09-03T00:00:01+00:00",
            "event": {**interactions[0], "schema_version": "llm_interaction_v1", "forensic": {"request": interactions[0]["request"], "response": interactions[0]["response"]}}
            if with_llm
            else {},
        },
        {
            "kind": "llm_call",
            "created_at": "2026-09-03T00:00:02+00:00",
            "event": {**interactions[1], "schema_version": "llm_interaction_v1", "forensic": {"request": interactions[1]["request"], "response": interactions[1]["response"]}}
            if with_llm
            else {},
        },
        {
            "kind": "step",
            "step_name": "node.finalize_response",
            "status": "human_review",
            "created_at": "2026-09-03T00:00:03+00:00",
            "event": {
                "hil_required": True,
                "answer_mode": "spl_utility_authoring",
                "message": payload.get("message") or payload.get("analyst_summary") or "preview",
            },
        },
    ]
    metadata = {
        "debug_summary": {**summary, "effective_state": {"$ref": "run.metadata.effective_state"}},
        "effective_state": effective,
        "control_plane_trace": payload.get("control_plane_trace"),
        "final_output": build_final_output_trace(payload),
        "llm_interactions": interactions,
        "answer_mode": payload.get("answer_mode"),
        "use_case_id": "auth_success_after_failure",
    }
    return assemble_forensic_bundle(
        trace_id="fd675e88-88ec-4be9-94e2-c9b7bcdc8bb7",
        run={
            "trace_id": "fd675e88-88ec-4be9-94e2-c9b7bcdc8bb7",
            "status": "human_review",
            "metadata": metadata,
            "duration_ms": 4000,
            "answer_mode": payload.get("answer_mode"),
        },
        events=events,
    )


def test_forensic_explainability_effective_state_is_canonical_and_non_null() -> None:
    forensic = _p2_forensic()
    es = forensic["explainability"]["effective_state"]
    assert es
    assert es["schema_version"] == "trace_effective_state_v1"
    nested = forensic["explainability"]["debug_summary"]["effective_state"]
    assert nested == {"$ref": "run.metadata.effective_state"}
    assert es["source_profile"]["slots"]["index"]["resolved_value"] == "pgcil_soc"


def test_reviewer_has_no_duplicated_heavy_snapshots() -> None:
    forensic = _p2_forensic()
    reviewer = build_reviewer_trace(forensic)
    dumped = json.dumps(reviewer)
    assert reviewer["schema_version"] == "reviewer_trace_v2"
    assert reviewer["explainability"]["debug_summary"] is None
    assert reviewer["explainability"]["control_plane_trace"] is None
    assert reviewer["effective_state"] == {"$ref": "artifact:effective_state"}
    assert dumped.count('"schema_version": "trace_effective_state_v1"') == 0
    assert dumped.count('"query_to_intent"') == 0
    assert dumped.count("utility_spl_draft_trace") == 0
    spl = (forensic["run"]["metadata"].get("final_output") or {}).get("message") or ""
    if len(spl) > 80:
        assert dumped.count(spl) <= 1


def test_reviewer_is_smaller_than_forensic() -> None:
    forensic = _p2_forensic()
    reviewer = build_reviewer_trace(forensic)
    before = json.dumps(forensic)
    after = json.dumps(reviewer)
    assert len(after.encode()) < len(before.encode())
    assert after.count("\n") <= before.count("\n") or len(after) < len(before)


def test_p2_llm_story_on_reviewer_export() -> None:
    reviewer = build_reviewer_trace(_p2_forensic())
    llm = reviewer["llm"]
    assert llm["interactions_attempted"] == 2
    assert llm["interactions_completed"] == 2
    assert llm["interactions_accepted"] == 0
    assert llm["interactions_contributing_to_final_output"] == 0
    assert llm["llm_used_in_final_answer"] is False
    assert llm["llm_sidecar_attempt_count"] == 1
    assert llm["llm_synthesis_attempt_count"] == 1
    assert llm["accepted_llm_roles"] == []
    assert "spl_advisory_generator" in llm["rejected_roles"]
    assert "review_only_spl_synthesis" in llm["rejected_roles"]
    assert "spl_advisory_generator" in llm["dropped_llm_roles"]
    assert reviewer["synthesis"]["synthesis_source"] == "DETERMINISTIC_SYNTHESIS_FALLBACK"
    assert "interactions" not in reviewer["synthesis"]
    assert reviewer["execution"]["execution_requested"] is False
    assert reviewer["execution"]["execution_performed"] is False
    assert reviewer["execution"]["execution_authorized"] is False
    assert reviewer["execution"]["mcp_calls"] == 0
    assert reviewer["execution"]["splunk_calls"] == 0


def test_reviewer_validator_headlines_distinguish_layers() -> None:
    reviewer = build_reviewer_trace(_p2_forensic())
    spl = reviewer["spl"]
    assert spl["authoring_fidelity_status"] == "passed"
    assert spl["llm_candidate_status"] == "rejected"
    assert spl["llm_candidate_reason"] == "missing_aggregation"
    assert spl["candidate_spl_validation_status"] == "withheld_review_only"
    assert spl["execution_promotion_status"] == "not_applicable_review_only"
    assert spl["execution_validation_status"] == "not_applicable_review_only"
    assert spl["candidate_execution_eligible"] is False
    assert spl["execution_eligible"] is False
    assert spl["execution_performed"] is False
    assert spl["final_answer_safety_status"] == "passed"
    assert spl["normalized_spl_available"] is False
    assert "legacy_validator_status" not in spl


def test_reviewer_source_binding_resolved_with_intentional_placeholder() -> None:
    reviewer = build_reviewer_trace(_p2_forensic())
    dumped = json.dumps(reviewer)
    assert "pgcil_soc" not in dumped
    assert '"index_resolution_source": "placeholder"' not in dumped
    binding = reviewer["source_binding"]
    assert binding["runtime_binding_resolved"] is True
    assert binding["runtime_value_source"] == "coe_store"
    assert binding["review_draft_display_value"] == "<your_index>"
    assert binding["review_draft_display_reason"] == "review_only_placeholder_policy"
    assert binding["intentional_display_placeholder"] is True
    index = binding["slots"]["index"]
    assert index["runtime_binding_resolved"] is True
    assert index["runtime_value_source"] == "coe_store"
    assert index["review_draft_display_value"] == "<your_index>"
    assert index["intentional_display_placeholder"] is True
    assert "resolved_value" not in index
    sourcetype = binding["slots"]["sourcetype"]
    assert sourcetype["runtime_binding_resolved"] is True
    assert sourcetype["review_draft_display_value"] == "pgcil:auth"
    assert sourcetype["intentional_display_placeholder"] is False


def test_reviewer_review_decision_is_completed_review_only() -> None:
    reviewer = build_reviewer_trace(_p2_forensic())
    decision = reviewer["review_decision"]
    assert decision["run_outcome"] == "completed_review_only"
    assert decision["artifact_ready_for_review"] is True
    assert decision["current_turn_requires_user_input"] is False
    assert decision["current_turn_blocked_for_hil"] is False
    assert decision["execution_permitted"] is False
    assert decision["execution_requires_approval_if_requested"] is True
    assert "Review-only SPL artifact delivered" in decision["reason"]
    assert reviewer["summary"]["legacy_run_status"] == "human_review"
    assert reviewer["summary"]["review_outcome"] == "completed_review_only"


def test_reviewer_connectors_cannot_contradict() -> None:
    reviewer = build_reviewer_trace(_p2_forensic())
    connectors = reviewer["connectors"]
    actual = connectors["actual_connector_usage"]
    required = connectors["runtime_required_connectors"]
    potential = connectors["potential_connectors"]
    assert "llm" in potential
    assert required["mcp"] is False
    assert required["splunk"] is False
    assert actual["llm_interactions"] == 2
    assert actual["mcp_calls"] == 0
    assert actual["splunk_calls"] == 0
    assert connectors["mcp_required_this_turn"] is False
    assert connectors["mcp_executed"] is False
    if actual["mcp_calls"] > 0:
        assert required["mcp"] is True or "mcp" in potential
    if not required["mcp"] and actual["mcp_calls"] == 0:
        assert connectors["mcp_executed"] is False
        assert "failed" not in json.dumps(connectors).lower()


def test_reviewer_contains_no_raw_llm_bodies_or_duplicate_payloads() -> None:
    forensic = _p2_forensic()
    reviewer = build_reviewer_trace(forensic)
    dumped = json.dumps(reviewer)
    assert "Return detection plan JSON" not in dumped
    assert "SYNTHESIS_INPUT_JSON" not in dumped
    assert "not balanced" not in dumped
    assert "system_prompt" not in dumped
    assert "raw_text" not in dumped
    assert "pgcil_soc" not in dumped
    interactions = reviewer["llm"]["interactions"]
    assert len(interactions) == 2
    blob = json.dumps(reviewer, sort_keys=True)
    for item in interactions:
        assert blob.count(json.dumps(item, sort_keys=True)) == 1
    synth_refs = reviewer["synthesis"]["interaction_refs"]
    assert len(synth_refs) == 1
    assert synth_refs[0]["role"] == "review_only_spl_synthesis"
    assert synth_refs[0]["reject_reason"] == "no_balanced_json_object"
    assert reviewer["evidence"]["evidence_plan_ref"] == "artifact:evidence_plan"
    assert reviewer["evidence"]["resource_plan_ref"] == "artifact:resource_plan"
    assert dumped.count('"schema_version": "trace_effective_state_v1"') == 0


def test_reviewer_timeline_does_not_repeat_full_question() -> None:
    event = {
        "kind": "routing_disagreement",
        "event": {
            "query": "Write a review-only SPL query to identify users with more than 20 failed authentication attempts.",
            "disagreement": True,
        },
    }
    compact = compact_timeline_event(event)
    body = compact["event"]
    assert "query" not in body
    assert body["question_preview"]
    assert len(body["question_preview"]) <= 240
    assert body["question_hash"]
    assert "more than 20 failed" in body["question_preview"]


def test_forensic_keeps_legacy_debug_summary_for_existing_consumers() -> None:
    forensic = _p2_forensic()
    assert forensic["explainability"]["debug_summary"]["routing"]
    assert forensic["explainability"]["control_plane_trace"]
    assert forensic["explainability"]["final_output"]


def test_reviewer_final_answer_is_referenced_not_repeated_on_finalize() -> None:
    reviewer = build_reviewer_trace(_p2_forensic())
    finalize = [item for item in reviewer["timeline"] if item.get("step_name") == "node.finalize_response"][0]
    assert finalize["event"]["final_answer_ref"] == "artifact:final_answer"
    assert "hil_required_legacy" in finalize["event"]
    assert finalize["event"]["current_turn_hil_required"] is False


def test_forensic_llm_records_contain_exact_redacted_prompt_and_response() -> None:
    forensic = _p2_forensic()
    interactions = forensic["explainability"]["llm_interactions"]
    assert len(interactions) == 2
    advisory = next(item for item in interactions if item["role"] == "spl_advisory_generator")
    synthesis = next(item for item in interactions if item["role"] == "review_only_spl_synthesis")
    assert "Return detection plan JSON" in advisory["request"]["system_prompt"]
    assert advisory["response"]["raw_text"] == '{"data_domain":"auth"}'
    assert advisory["response"]["parsed_payload"] == {"data_domain": "auth"}
    assert advisory["response"]["finish_reason"] == "stop"
    assert advisory["validation"]["reject_reasons"] == ["missing_aggregation"]
    assert advisory["prompt_hash"]
    assert advisory["response_hash"]
    assert "Explain the SPL" in synthesis["request"]["system_prompt"]
    assert synthesis["response"]["raw_text"] == "not balanced"
    assert synthesis["disposition"]["fallback_reason"] == "no_balanced_json_object"
    compact = json.dumps(build_reviewer_trace(forensic)["llm"]["interactions"])
    assert "Return detection plan JSON" not in compact
    assert "not balanced" not in compact
