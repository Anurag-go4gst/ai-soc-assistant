from __future__ import annotations

import json

from app.actions.capability_policy import action_capability_for
from app.api.routes_chat import chat
from app.llm.adapter.json_extractor import extract_first_json_object
from app.llm.adapter.role_registry import ROLE_SCHEMA_REGISTRY, validate_role_registry
from app.llm.adapter.role_results import adapt_llm_output
from app.llm.registry_settings import ROLE_DEFAULTS
from app.schemas.requests import ChatRequest


def _query_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "raw_query": "Map this alert to MITRE",
        "primary_intent": "knowledge_recall",
        "requested_output_type": "mitre_mapping",
        "entities": {},
        "candidate_use_case_id": "soc_map_alert_mitre",
        "selected_skill": "knowledge_recall",
        "routable_skills": ["knowledge_recall"],
        "pipeline_stages": ["query_understanding", "context_sufficiency"],
        "required_sources": ["rag:sop"],
        "optional_sources": [],
        "clarification_needed": True,
        "clarification_question": "Share alert context.",
        "confidence": 0.3,
    }
    payload.update(overrides)
    return payload


def _analyst_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "severity_label": "P3 Medium",
        "finding_title": "Failed login spike",
        "analyst_summary": "Repeated authentication failures require validation.",
        "splunk_results_table": [],
        "mitre_mappings": [{"technique_id": "T1110.001", "name": "Password Guessing", "status": "supported"}],
        "retrieved_playbook": {"title": "Auth SOP", "source_refs": ["coe_auth_sop_sample.md#AUTH-001"]},
        "foundation_sec_analysis": "Advisory only.",
        "recommended_actions": ["summarize", "block_ip"],
        "missing_evidence": [],
        "blocked_actions": ["block_ip"],
    }
    payload.update(overrides)
    return payload


def test_json_extractor_accepts_pure_json() -> None:
    result = extract_first_json_object('{"ok": true}')

    assert result.parsed_ok is True
    assert result.payload == {"ok": True}
    assert result.warnings == []


def test_json_extractor_warns_for_prose_before_json() -> None:
    result = extract_first_json_object('Here is JSON: {"ok": true}')

    assert result.parsed_ok is True
    assert "prose_before_json_ignored" in result.warnings


def test_json_extractor_warns_for_prose_after_json() -> None:
    result = extract_first_json_object('{"ok": true} done')

    assert result.parsed_ok is True
    assert "prose_after_json_ignored" in result.warnings


def test_json_extractor_warns_for_markdown_fenced_json() -> None:
    result = extract_first_json_object('```json\n{"ok": true}\n```')

    assert result.parsed_ok is True
    assert "json_extracted_from_markdown_fence" in result.warnings


def test_json_extractor_rejects_malformed_json() -> None:
    result = extract_first_json_object('{"ok": }')

    assert result.parsed_ok is False
    assert "malformed_json" in result.errors


def test_json_extractor_warns_for_multiple_objects() -> None:
    result = extract_first_json_object('{"first": true} {"second": true}')

    assert result.parsed_ok is True
    assert result.payload == {"first": True}
    assert "multiple_json_objects_first_used" in result.warnings


def test_json_extractor_rejects_empty_output() -> None:
    result = extract_first_json_object("  ")

    assert result.parsed_ok is False
    assert "empty_output" in result.errors


def test_role_to_schema_registry_matches_existing_llm_roles() -> None:
    configured_roles = {item["role"] for item in ROLE_DEFAULTS}

    assert validate_role_registry() == []
    assert set(ROLE_SCHEMA_REGISTRY).issubset(configured_roles)
    assert ROLE_SCHEMA_REGISTRY["intent_shadow_classifier"].__name__ == "QueryUnderstandingCandidate"
    assert ROLE_SCHEMA_REGISTRY["analyst_response_drafter"].__name__ == "AnalystResponseDraft"
    assert ROLE_SCHEMA_REGISTRY["spl_advisory_generator"].__name__ == "SplAdvisoryCandidate"


def test_schema_validation_accepts_known_query_candidate_and_drops_unknown_fields() -> None:
    result = adapt_llm_output(
        role="intent_shadow_classifier",
        raw_output=json.dumps(_query_payload(extra_field="drop-me")),
    )

    assert result.accepted is True
    assert result.parsed_ok is True
    assert result.schema_valid is True
    assert result.normalized_payload is not None
    assert result.normalized_payload["candidate_use_case_id"] == "soc_map_alert_mitre"
    assert "extra_field" in result.dropped_fields
    assert "extra_field" not in result.normalized_payload


def test_malformed_output_rejected_without_throwing() -> None:
    result = adapt_llm_output(role="intent_shadow_classifier", raw_output='{"raw_query": }')

    assert result.accepted is False
    assert result.normalized_payload is None
    assert "malformed_json" in result.errors


def test_prose_preamble_extracts_with_warning() -> None:
    result = adapt_llm_output(role="intent_shadow_classifier", raw_output="Analysis first.\n" + json.dumps(_query_payload()))

    assert result.accepted is True
    assert "prose_before_json_ignored" in result.warnings


def test_unknown_use_case_id_rejected() -> None:
    result = adapt_llm_output(
        role="intent_shadow_classifier",
        raw_output=json.dumps(_query_payload(candidate_use_case_id="not_a_use_case")),
    )

    assert result.accepted is False
    assert result.schema_valid is False
    assert any("invalid use_case_id" in error for error in result.errors)


def test_invalid_skill_rejected() -> None:
    result = adapt_llm_output(
        role="intent_shadow_classifier",
        raw_output=json.dumps(_query_payload(selected_skill="remediate_everything")),
    )

    assert result.accepted is False
    assert any("Invalid AI-SOC skill" in error for error in result.errors)


def test_confidence_ignored_as_clarification_gate_even_when_high() -> None:
    result = adapt_llm_output(
        role="intent_shadow_classifier",
        raw_output=json.dumps(_query_payload(clarification_needed=False, clarification_question=None, confidence=0.99)),
        deterministic_context={"clarification": {"question": "Share the alert title or notable ID."}},
    )

    assert result.accepted is True
    assert result.normalized_payload is not None
    assert result.normalized_payload["confidence"] == 0.99
    assert result.normalized_payload["clarification_needed"] is True
    assert result.normalized_payload["clarification_question"] == "Share the alert title or notable ID."
    assert "llm_clarification_overridden" in result.warnings


def test_low_confidence_does_not_auto_fail_valid_schema() -> None:
    result = adapt_llm_output(
        role="intent_shadow_classifier",
        raw_output=json.dumps(_query_payload(confidence=0.0)),
    )

    assert result.accepted is True
    assert result.normalized_payload is not None
    assert result.normalized_payload["confidence"] == 0.0


def test_spl_execution_eligible_forced_false() -> None:
    result = adapt_llm_output(
        role="spl_advisory_generator",
        raw_output=json.dumps(
            {
                "candidate_spl": "search index=pgcil_soc sourcetype=pgcil:auth | head 10",
                "assumptions": [],
                "required_fields": ["user"],
                "validation_notes": [],
                "execution_eligible": True,
            }
        ),
    )

    assert result.accepted is True
    assert result.normalized_payload is not None
    assert result.normalized_payload["execution_eligible"] is False
    assert "llm_execution_eligibility_ignored" in result.warnings


def test_severity_override_ignored_for_drafter_and_rationale_roles() -> None:
    drafter = adapt_llm_output(
        role="analyst_response_drafter",
        raw_output=json.dumps(_analyst_payload(severity_label="P1 Critical")),
        deterministic_context={"severity_label": "P3 Medium"},
    )
    rationale = adapt_llm_output(
        role="risk_rationale_reasoner",
        raw_output=json.dumps(
            {
                "selected_severity": "P1 Critical",
                "why_selected": ["LLM says so"],
                "why_not_higher": [],
                "missing_evidence_for_higher": [],
                "escalate_if": [],
                "recommended_validation_steps": [],
                "confidence": 0.99,
            }
        ),
        deterministic_context={"severity_label": "P3 Medium"},
    )

    assert drafter.normalized_payload is not None
    assert drafter.normalized_payload["severity_label"] == "P3 Medium"
    assert "llm_severity_ignored" in drafter.warnings
    assert rationale.normalized_payload is not None
    assert rationale.normalized_payload["selected_severity"] == "P3 Medium"
    assert "llm_severity_ignored" in rationale.warnings


def test_mitre_status_override_ignored() -> None:
    result = adapt_llm_output(
        role="analyst_response_drafter",
        raw_output=json.dumps(_analyst_payload(mitre_mappings=[{"technique_id": "T1078", "name": "Valid Accounts", "status": "supported"}])),
        deterministic_context={"mitre_mappings": [{"technique_id": "T1078", "status": "candidate"}]},
    )

    assert result.normalized_payload is not None
    assert result.normalized_payload["mitre_mappings"][0]["status"] == "candidate"
    assert "llm_mitre_status_ignored" in result.warnings


def test_sop_citation_override_ignored() -> None:
    result = adapt_llm_output(
        role="analyst_response_drafter",
        raw_output=json.dumps(_analyst_payload(retrieved_playbook={"title": "Fake SOP", "source_refs": ["fake.md#SOP"]})),
        deterministic_context={"sop_source_refs": ["coe_auth_sop_sample.md#AUTH-001"]},
    )

    assert result.normalized_payload is not None
    assert result.normalized_payload["retrieved_playbook"]["source_refs"] == ["coe_auth_sop_sample.md#AUTH-001"]
    assert "llm_sop_citation_ignored" in result.warnings


def test_blocked_action_warns_and_is_dropped() -> None:
    capability = action_capability_for("auth_failed_login_spike", "P3 Medium")
    result = adapt_llm_output(
        role="analyst_response_drafter",
        raw_output=json.dumps(_analyst_payload(recommended_actions=["summarize", "disable_user"], blocked_actions=[])),
        deterministic_context={
            "allowed_actions": capability.allowed_actions,
            "unavailable_actions": capability.unavailable_actions,
        },
    )

    assert result.normalized_payload is not None
    assert result.normalized_payload["recommended_actions"] == ["summarize"]
    assert "llm_action_not_allowed" in result.warnings


def test_default_result_does_not_include_raw_output_or_secret() -> None:
    raw = json.dumps({**_query_payload(), "token": "secret-token-value"})
    result = adapt_llm_output(role="intent_shadow_classifier", raw_output=raw)

    assert result.raw_output_hash
    assert result.raw_output_redacted is None
    assert "secret-token-value" not in result.model_dump_json()


def test_debug_raw_output_is_redacted_when_explicitly_requested() -> None:
    raw = json.dumps(_query_payload()) + "\napi_key=abc123"
    result = adapt_llm_output(role="intent_shadow_classifier", raw_output=raw, include_raw_output_redacted=True)

    assert result.raw_output_redacted is not None
    assert "api_key=<redacted>" in result.raw_output_redacted
    assert "abc123" not in result.raw_output_redacted


def test_adapter_is_dormant_for_chat(monkeypatch) -> None:
    def _raise_if_called(*args: object, **kwargs: object) -> None:
        raise AssertionError("LLM adapter must stay dormant for /chat in Stage 3J-I.1")

    monkeypatch.setattr("app.llm.adapter.role_results.adapt_llm_output", _raise_if_called)
    response = chat(ChatRequest(message="Show SOP for brute-force investigation"))

    assert response.synthesis_status is not None
    assert response.synthesis_status.enabled is False
    assert response.answer_guard is not None
    assert response.answer_guard.enabled is False
    assert response.candidate_spl is None
    assert response.spl_validation is None


def test_stage_safety_invariants_remain_in_chat() -> None:
    response = chat(ChatRequest(message="Generate SPL for failed login spike"))

    assert response.synthesis_status is not None
    assert response.synthesis_status.enabled is False
    assert response.answer_guard is not None
    assert response.answer_guard.enabled is False
    assert response.candidate_spl is not None
    assert response.candidate_spl.execution_eligible is False
    assert response.execution is not None
    assert response.execution.status in {"blocked", "not_required", "requires_human_review", "skipped"}
    assert response.execution.executed_spl is None
    assert response.workflow_plan is not None
    assert response.workflow_plan.execution_enabled is False
    assert response.spl_validation is not None
    assert response.spl_validation.saia_available is not None
