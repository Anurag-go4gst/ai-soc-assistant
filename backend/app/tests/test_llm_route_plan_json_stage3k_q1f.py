"""Stage 3K-Q1F route-plan candidate JSON extraction from wrappers."""

from __future__ import annotations

import json

from app.routing.llm_route_plan_json import extract_route_plan_candidate_json


def _minimal_route_plan_payload() -> dict:
    return {
        "primary_skill": "aggregate_and_rank",
        "operation_type": "top_n",
        "source_class": "okta_authentication_logs",
        "evidence_needs": {
            "datamodel": "Authentication",
            "group_by": ["user"],
            "metric": {"type": "count", "field": "failed_login_count"},
        },
        "time_window": None,
        "limit": 10,
        "clarification_questions": [],
        "rationale": "Top failed logins by user.",
    }


def test_extracts_pure_json_without_warnings() -> None:
    payload = _minimal_route_plan_payload()
    result = extract_route_plan_candidate_json(json.dumps(payload))

    assert result.parsed_ok is True
    assert result.payload == payload
    assert result.warnings == []


def test_extracts_json_from_markdown_fence_wrapper() -> None:
    payload = _minimal_route_plan_payload()
    raw = f"```json\n{json.dumps(payload, indent=2)}\n```"
    result = extract_route_plan_candidate_json(raw)

    assert result.parsed_ok is True
    assert result.payload == payload
    assert "json_extracted_from_markdown_fence" in result.warnings


def test_extracts_json_from_prose_and_fence_wrapper() -> None:
    payload = _minimal_route_plan_payload()
    raw = (
        "Here is the route plan candidate:\n\n"
        f"```json\n{json.dumps(payload)}\n```\n\n"
        "Let me know if you need changes."
    )
    result = extract_route_plan_candidate_json(raw)

    assert result.parsed_ok is True
    assert result.payload == payload
    assert "prose_before_json_ignored" in result.warnings
    assert "prose_after_json_ignored" in result.warnings


def test_extracts_json_from_prose_wrapper_without_fence() -> None:
    payload = _minimal_route_plan_payload()
    raw = f"Route plan:\n{json.dumps(payload)}\nDone."
    result = extract_route_plan_candidate_json(raw)

    assert result.parsed_ok is True
    assert result.payload == payload


def test_rejects_malformed_json_inside_wrapper() -> None:
    raw = '```json\n{"primary_skill": }\n```'
    result = extract_route_plan_candidate_json(raw)

    assert result.parsed_ok is False
    assert "malformed_json" in result.errors


def test_first_valid_object_used_when_multiple_present() -> None:
    first = {"primary_skill": "aggregate_and_rank", "marker": "first"}
    second = {"primary_skill": "knowledge_recall", "marker": "second"}
    raw = json.dumps(first) + "\n" + json.dumps(second)
    result = extract_route_plan_candidate_json(raw)

    assert result.parsed_ok is True
    assert result.payload == first
    assert "multiple_json_objects_first_used" in result.warnings


def test_rejects_truncated_json_without_semantic_repair() -> None:
    result = extract_route_plan_candidate_json('{"primary_skill": "aggregate_and_rank", "rationale": "x"')

    assert result.parsed_ok is False
    assert result.errors == ["no_balanced_json_object"]
    assert result.payload is None


def test_rejects_json_array_without_object() -> None:
    result = extract_route_plan_candidate_json(json.dumps(["only", "strings"]))

    assert result.parsed_ok is False
    assert "no_balanced_json_object" in result.errors


def test_first_object_inside_array_wrapper_is_extracted_verbatim() -> None:
    """Extraction finds the first balanced object; schema validation owns top-level contract."""
    inner = {"primary_skill": "aggregate_and_rank", "marker": "inner"}
    result = extract_route_plan_candidate_json(json.dumps([inner]))

    assert result.parsed_ok is True
    assert result.payload == inner


def test_extracts_valid_json_even_when_rationale_contains_spl_like_text() -> None:
    """Extraction is verbatim; SPL forbiddance is enforced later in the candidate pipeline."""
    payload = _minimal_route_plan_payload()
    payload["rationale"] = '| tstats count from datamodel=Authentication'
    result = extract_route_plan_candidate_json(json.dumps(payload))

    assert result.parsed_ok is True
    assert result.payload == payload
