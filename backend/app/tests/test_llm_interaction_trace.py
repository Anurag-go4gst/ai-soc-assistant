"""Canonical LLM interaction capture — one record per actual model call."""

from __future__ import annotations

import json

from app.chat.llm_interaction_trace import (
    capture_llm_interaction,
    compact_llm_call_index,
    count_interactions_by_role,
    reset_llm_interactions,
    snapshot_llm_interactions,
)
from app.spl.llm_plan_compiler import compile_intent_spec_to_spl, get_detection_plan
from app.spl.review_only_analyst_synthesis import (
    SYNTHESIS_SOURCE_DETERMINISTIC,
    synthesize_review_only_analyst_explanation,
)
from app.spl.spl_intent_spec import build_spl_intent_spec

P2 = (
    "Write a Splunk SPL query to detect successful logins that occur within 10 minutes "
    "after more than 20 failed logins from the same source IP and user in a 15-minute window."
)


def setup_function() -> None:
    reset_llm_interactions()


def test_capture_records_exact_redacted_prompt_and_response() -> None:
    record = capture_llm_interaction(
        role="spl_advisory_generator",
        system_prompt="Return JSON only.",
        user_prompt="Investigation request:\nfind failed then success",
        response_schema={"type": "json_schema"},
        temperature=0.0,
        max_tokens=512,
        raw_text='{"filters":[]}',
        parsed_payload={"filters": []},
        finish_reason="stop",
        usage={"completion_tokens": 12},
        transport_status="completed",
        parse_status="parsed",
        schema_status="valid",
        quality_status="failed",
        reject_reasons=["missing_aggregation"],
        accepted=False,
        latency_ms=1314,
    )
    assert record["request"]["system_prompt"] == "Return JSON only."
    assert "Investigation request" in record["request"]["user_prompt"]
    assert record["response"]["raw_text"] == '{"filters":[]}'
    assert record["response"]["parsed_payload"] == {"filters": []}
    assert record["response"]["finish_reason"] == "stop"
    assert record["prompt_hash"]
    assert record["response_hash"]
    assert record["validation"]["reject_reasons"] == ["missing_aggregation"]
    compact = compact_llm_call_index([record])[0]
    assert "Return JSON only" not in json.dumps(compact)
    assert compact["forensic_ref"].startswith("timeline:llm_call:")
    assert compact["reject_reason"] == "missing_aggregation"


def test_hydrate_lifts_forensic_nested_request_and_response() -> None:
    from app.chat.llm_interaction_trace import forensic_llm_call_event, hydrate_llm_interaction

    record = capture_llm_interaction(
        role="spl_advisory_generator",
        system_prompt="Return JSON only.",
        user_prompt="Investigation request:\nfind failed then success",
        raw_text='{"filters":[]}',
        parsed_payload={"filters": []},
        finish_reason="stop",
        reject_reasons=["missing_aggregation"],
        accepted=False,
        latency_ms=10,
    )
    event = forensic_llm_call_event(record)
    assert "request" not in event or event.get("request") is None
    hydrated = hydrate_llm_interaction(event)
    assert hydrated["request"]["system_prompt"] == "Return JSON only."
    assert hydrated["response"]["raw_text"] == '{"filters":[]}'
    assert hydrated["validation"]["reject_reasons"] == ["missing_aggregation"]


def test_get_detection_plan_captures_one_advisory_interaction() -> None:
    reset_llm_interactions()
    plan, errors = get_detection_plan(
        "count failed logins by user",
        llm_raw_output_provider=lambda: "not-json",
    )
    assert plan is None
    assert errors
    records = snapshot_llm_interactions()
    assert len(records) == 1
    assert records[0]["role"] == "spl_advisory_generator"
    assert records[0]["request"]["user_prompt"]
    assert records[0]["response"]["raw_text"] == "not-json"
    assert records[0]["disposition"]["accepted"] is False


def test_synthesis_fallback_captures_a_separate_interaction() -> None:
    reset_llm_interactions()
    spec = build_spl_intent_spec(P2)
    spl = compile_intent_spec_to_spl(spec)
    result = synthesize_review_only_analyst_explanation(
        original_user_request=P2,
        spec=spec,
        final_validated_spl=spl,
        llm_raw_output_provider=lambda: "not json",
    )
    assert result.source == SYNTHESIS_SOURCE_DETERMINISTIC
    records = snapshot_llm_interactions()
    assert len(records) == 1
    assert records[0]["role"] == "review_only_spl_synthesis"
    assert records[0]["response"]["raw_text"] == "not json"
    assert "no_balanced_json_object" in records[0]["validation"]["reject_reasons"]
    assert records[0]["disposition"]["accepted"] is False
    assert records[0]["disposition"]["fallback_reason"] == "no_balanced_json_object"


def test_p2_style_two_calls_count_as_two_attempts_and_zero_accepted() -> None:
    reset_llm_interactions()
    get_detection_plan("p2 query", llm_raw_output_provider=lambda: '{"broken":')
    spec = build_spl_intent_spec(P2)
    synthesize_review_only_analyst_explanation(
        original_user_request=P2,
        spec=spec,
        final_validated_spl=compile_intent_spec_to_spl(spec),
        llm_raw_output_provider=lambda: "not json",
    )
    records = snapshot_llm_interactions()
    counts = count_interactions_by_role(records)
    assert counts["total_attempts"] == 2
    assert counts["spl_advisory_attempt_count"] == 1
    assert counts["llm_synthesis_attempt_count"] == 1
    assert counts["llm_used_in_final_answer"] is False
    assert counts["accepted_llm_roles"] == []
    assert "spl_advisory_generator" in counts["dropped_llm_roles"]
    assert "review_only_spl_synthesis" in counts["dropped_llm_roles"]
