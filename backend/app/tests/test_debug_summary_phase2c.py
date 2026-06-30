"""Phase 2C — debug_summary output/intent/dispatch blocks."""

from __future__ import annotations

from app.chat.debug_summary import build_debug_summary


def test_debug_summary_includes_output_intent_dispatch_blocks() -> None:
    payload = {
        "message": "Outbound spike: review the candidate SPL before execution.",
        "analyst_summary": "Summary for analysts.",
        "selected_skill": "spl_generation",
        "intent_dispatch": {
            "call_2c_llm": True,
            "prompt_mode": "spl_slot_extraction",
            "skip_reasons": [],
        },
        "pipeline_dispatch": {
            "decision": {
                "request_mode": "spl_authoring",
                "stage_schedule": ["workflow_spl", "spl_postprocessor", "spl_source_resolve"],
                "llm_hops": ["spl_plan_compiler"],
                "dispatch_reasons": ["request_mode:spl_authoring"],
            },
            "runtime_context": {"dispatch_cursor": None},
        },
        "llm_intent_advisory": {
            "intent_family_candidate": "spl_generation_only",
            "entity_slots_candidate": {"index": "firewall"},
        },
        "query_to_intent": {"llm_intent_assist_status": "completed"},
        "candidate_spl": {
            "review_only_spl_postprocessor_trace": {
                "postprocessor_evaluated": True,
                "postprocessor_applied": True,
                "spl_raw_hash": "abc",
                "spl_post_hash": "def",
            },
            "detection_plan": {
                "index": "firewall",
                "data_domain": "network",
                "raw_query_echo": "should not surface",
            },
        },
        "spl_validation": {"approved": False},
        "control_plane_trace": {},
    }
    summary = build_debug_summary(payload=payload)

    assert summary["output"]["message"].startswith("Outbound spike")
    assert summary["intent"]["prompt_mode"] == "spl_slot_extraction"
    assert summary["intent"]["entity_slots"]["index"] == "firewall"
    assert summary["dispatch"]["request_mode"] == "spl_authoring"
    assert "spl_plan_compiler" in summary["dispatch"]["llm_hops"]
    assert summary["spl"]["postprocessor_evaluated"] is True
    assert summary["spl"]["spl_raw_hash"] == "abc"
    assert summary["spl"]["detection_plan"]["index"] == "firewall"
    assert "raw_query_echo" not in (summary["spl"].get("detection_plan") or {})
