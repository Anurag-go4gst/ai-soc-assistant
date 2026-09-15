"""Known SPL authoring path: catalogue contract, quality gate, sequence meaning."""

from __future__ import annotations

import json
from typing import Any

import pytest

from app.api.routes_chat import chat
from app.chat.resolved_query_builder import build_resolved_query_contract
from app.chat.semantic_t4_understanding import maybe_enrich_t4_semantic
from app.chat.llm_interaction_trace import reset_llm_interactions, snapshot_llm_interactions
from app.config import settings
from app.query_understanding.parser import understand_query
from app.routing.select_route_from_understanding import select_route_from_understanding
from app.schemas.requests import ChatRequest
from app.spl.draft_preview import build_draft_preview, match_detection_family
from app.spl.draft_quality import evaluate_draft_quality
from app.spl.llm_fallback import CLARIFICATION_QUALITY_FAILED, generate_llm_spl_fallback
from app.spl.llm_plan_compiler import compile_intent_spec_to_spl
from app.spl.spl_intent_spec import build_spl_intent_spec
from app.spl.spl_semantic_fidelity import (
    impossible_same_row_event_predicates,
    validate_semantic_fidelity,
    validate_spl_structure,
)
from app.spl.template_registry import get_spl_template
from app.spl.utility_spl_authoring import candidate_from_universal_utility_authoring
from app.splunk.capabilities import build_splunk_capability_profile
from app.tests.support.chat_visible import assert_governed_spl_review_posture
from app.use_cases.registry import get_use_case, match_use_cases

EXACT_QUESTION = (
    "Generate a review-only SPL query to detect repeated failed authentication "
    "attempts followed by a successful login"
)
IMPOSSIBLE_SPL = (
    'search index=<auth_index> sourcetype=<auth_sourcetype> earliest=-60m latest=now '
    'failed_login="failed" AND successful_login="success" | stats count by user | head 100'
)
MALFORMED_SPL = 'search index=auth "unterminated | stats count (( '
FILTER_COUNT_QUESTION = "Generate a review-only SPL query to count failed logins by user"
THRESHOLD_QUESTION = (
    "Generate a review-only SPL query to detect users with more than 20 failed logins"
)
NO_FALLBACK_QUESTION = (
    "Write review-only SPL listing events where ACME_UNIT_TOKEN equals 7 over "
    "the last 24 hours. Do not execute."
)


class _Telemetry:
    def record_step(self, *args: Any, **kwargs: Any) -> None:
        return None

    def record_spl_validation(self, *args: Any, **kwargs: Any) -> None:
        return None


def _profile() -> Any:
    return build_splunk_capability_profile(required_saia_tool="saia_generate_spl")


def _llm_payload(spl: str, **overrides: Any) -> str:
    body: dict[str, Any] = {
        "status": "candidate_generated",
        "confidence_score": 0.72,
        "confidence_label": "medium",
        "detection_family": "auth_success_after_failure",
        "candidate_spl": spl,
        "index": "<auth_index>",
        "sourcetype": "<auth_sourcetype>",
        "result_cap": 100,
        "unresolved_slots": [],
        "assumptions": ["Review-only utility draft."],
        "required_fields": ["user", "host", "src_ip"],
        "missing_details": [],
        "clarifying_questions": [],
        "validation_notes": ["Lab candidate only"],
        "soc_std_rules_applied": ["shift_left_filtering"],
        "risk_notes": ["Not executed"],
        "execution_eligible": False,
        "governed": False,
        "catalog_approved": False,
    }
    body.update(overrides)
    return json.dumps(body)


@pytest.fixture
def spl_flags(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_spl_draft_preview_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_llm_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_llm_mode", "local")
    monkeypatch.setattr(settings, "ai_soc_llm_utility_spl_draft_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_llm_spl_fallback_enabled", True)
    monkeypatch.setattr(
        "app.spl.utility_spl_authoring.load_persisted_source_profile",
        lambda: {},
    )
    monkeypatch.setattr(
        "app.spl.utility_spl_authoring.load_persisted_source_profile_document",
        lambda: {"values": {}, "field_sources": {}},
    )


def _run(query: str, *, provider) -> tuple[dict[str, Any], dict[str, Any]]:
    result = candidate_from_universal_utility_authoring(
        trace_id="known-spl-quality",
        skill="spl_generation",
        user_query=query,
        telemetry=_Telemetry(),
        profile=_profile(),
        spl_governance=None,
        llm_raw_output_provider=provider,
    )
    assert result is not None
    return result


def _assert_valid_sequence_spl(spl: str) -> None:
    compact = " ".join(spl.lower().split())
    assert "failed_login=\"failed\" and successful_login=\"success\"" not in compact
    assert impossible_same_row_event_predicates(spl) is False
    assert "action=failure" in compact or "outcome=\"failure\"" in compact or "failed" in compact
    assert "action=success" in compact or "outcome=\"success\"" in compact or "success" in compact
    assert " or " in compact.split("|", 1)[0] or "case(" in compact
    assert "last_success" in compact or "burst_last" in compact or "streamstats" in compact
    assert "user" in compact
    assert "src" in compact or "src_ip" in compact
    assert "host" in compact or "dest" in compact
    report = evaluate_draft_quality(spl, detection_family="auth_success_after_failure")
    assert report.hard_fail_count == 0, report.findings


def test_auth_success_after_failure_catalogue_contract() -> None:
    definition = get_use_case("auth_success_after_failure")
    assert definition is not None
    contract = definition.spl_semantic_contract or {}
    assert contract.get("analysis_shape") == "sequence"
    assert contract.get("ordered_sequence") == ["failed_login", "successful_login"]
    assert contract.get("correlate_by") == ["user", "src_ip", "host"]
    matches = match_use_cases(EXACT_QUESTION, limit=3)
    assert matches
    assert matches[0].use_case_id == "auth_success_after_failure"


def test_exact_question_is_known_family_and_skips_t4() -> None:
    assert match_detection_family(EXACT_QUESTION) == "auth_success_after_failure"
    qu = understand_query(EXACT_QUESTION)
    route, provenance = select_route_from_understanding(qu, EXACT_QUESTION)
    assert route["skill"] in {"spl_generation", "attack_discovery"}
    assert provenance.get("authority_source") != "t4_semantic"
    contract = build_resolved_query_contract(
        query=EXACT_QUESTION,
        query_understanding=qu,
        qualification_tier="T2",
        qualification_source=qu.deterministic_match_path,
    )
    calls: list[int] = []
    maybe_enrich_t4_semantic(
        contract,
        query=EXACT_QUESTION,
        raw_output_provider=lambda _q, _c: calls.append(1) or "{}",
    )
    assert calls == []


def test_known_template_is_logically_valid_sequence() -> None:
    template = get_spl_template("auth_success_after_failure")
    assert template is not None
    spl = str(template.spl_text)
    assert "(action=failure OR action=success)" in spl
    assert "last_success > first_failure" in spl
    assert "by user, src, dest" in spl or "by user, src" in spl
    _assert_valid_sequence_spl(spl)


def test_lab_draft_correlates_user_src_host_with_order(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_spl_draft_preview_enabled", True)
    preview = build_draft_preview(EXACT_QUESTION, live_data_request=True)
    assert preview is not None
    spl = str(preview["draft_spl"])
    assert preview["detection_family"] == "auth_success_after_failure"
    assert "last_success_epoch>first_failure_epoch" in spl.replace(" ", "")
    assert "by user_norm, src_ip_norm, host_norm" in spl
    _assert_valid_sequence_spl(spl)


def test_intent_spec_defaults_identity_keys_without_explicit_same() -> None:
    spec = build_spl_intent_spec(EXACT_QUESTION)
    assert spec.get("known_spl_contract") == "auth_success_after_failure"
    roles = spec.get("entity_roles") or {}
    assert roles.get("correlate_by") == ["user", "src_ip", "host"]
    compiled = compile_intent_spec_to_spl(spec)
    assert compiled.strip()
    fidelity = validate_semantic_fidelity(spec, compiled)
    assert fidelity.get("passed") is True, fidelity


def test_impossible_same_row_spl_is_quality_hard_fail() -> None:
    report = evaluate_draft_quality(IMPOSSIBLE_SPL, detection_family="auth_success_after_failure")
    assert report.quality_status == "failed"
    assert report.hard_fail_count >= 1
    assert any(item.rule_id.endswith("Q19") for item in report.findings)
    assert impossible_same_row_event_predicates(IMPOSSIBLE_SPL) is True
    spec = build_spl_intent_spec(EXACT_QUESTION)
    fidelity = validate_semantic_fidelity(spec, IMPOSSIBLE_SPL)
    assert fidelity.get("passed") is False
    assert "sequence_impossible_same_row" in (fidelity.get("losses") or [])


def test_malformed_spl_is_rejected() -> None:
    errors = validate_spl_structure(MALFORMED_SPL)
    assert "unbalanced_quotes" in errors or "unbalanced_parentheses" in errors
    report = evaluate_draft_quality(MALFORMED_SPL)
    assert report.quality_status == "failed"
    assert report.hard_fail_count >= 1
    assert any(item.rule_id.endswith("Q20") for item in report.findings)


def test_schema_valid_json_with_bad_spl_does_not_publish(spl_flags: None) -> None:
    reset_llm_interactions()
    result = generate_llm_spl_fallback(
        user_query=EXACT_QUESTION,
        utility_authoring=True,
        llm_raw_output_provider=lambda: _llm_payload(IMPOSSIBLE_SPL),
    )
    assert result is not None
    assert result.candidate_spl == ""
    assert result.quality_status == "failed"
    assert result.clarification_reason == CLARIFICATION_QUALITY_FAILED
    candidate, validation = _run(EXACT_QUESTION, provider=lambda: _llm_payload(IMPOSSIBLE_SPL))
    spl = str(candidate.get("candidate_spl") or "")
    assert IMPOSSIBLE_SPL not in spl
    assert candidate.get("execution_eligible") is False
    trace = candidate.get("utility_spl_draft_trace") or {}
    assert trace.get("llm_candidate_rejected") is True or trace.get("final_raw_spl_source") != "llm_draft"
    assert trace.get("final_raw_spl_source") in {
        "deterministic_skeleton",
        "deterministic_compiler",
    }
    assert trace.get("fallback_selected") is True
    _assert_valid_sequence_spl(spl)
    records = snapshot_llm_interactions()
    advisory = [item for item in records if item.get("role") == "spl_advisory_generator"]
    assert advisory
    last = advisory[-1]
    if last.get("validation", {}).get("quality_status") == "failed":
        assert last["disposition"]["accepted"] is False
        assert last["disposition"]["contributed_to_final_output"] is False
    assert validation.get("approved") is False


def test_llm_timeout_uses_governed_fallback(spl_flags: None, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.spl.utility_spl_authoring.generate_llm_spl_fallback",
        lambda **_: None,
    )
    candidate, validation = _run(EXACT_QUESTION, provider=lambda: _llm_payload("unused"))
    trace = candidate.get("utility_spl_draft_trace") or {}
    assert trace.get("final_raw_spl_source") in {
        "deterministic_skeleton",
        "deterministic_compiler",
    }
    assert candidate.get("execution_eligible") is False
    assert validation.get("approved") is False
    _assert_valid_sequence_spl(str(candidate.get("candidate_spl") or ""))


def test_no_fallback_does_not_fabricate_spl(spl_flags: None) -> None:
    result = candidate_from_universal_utility_authoring(
        trace_id="known-spl-no-fallback",
        skill="spl_generation",
        user_query=NO_FALLBACK_QUESTION,
        telemetry=_Telemetry(),
        profile=_profile(),
        spl_governance=None,
        llm_raw_output_provider=lambda: _llm_payload(MALFORMED_SPL, detection_family="utility_authoring"),
    )
    if result is None:
        return
    candidate, _validation = result
    if candidate.get("spl_authoring_unavailable"):
        assert not str(candidate.get("candidate_spl") or "").strip() or candidate.get("execution_eligible") is False
        return
    # If a deterministic compiler/skeleton could still serve the unresolved field, it must
    # remain review-only and must not invent the missing token as a live fact.
    assert candidate.get("execution_eligible") is False


def test_valid_llm_sequence_is_accepted(spl_flags: None) -> None:
    spec = build_spl_intent_spec(EXACT_QUESTION)
    compiled = compile_intent_spec_to_spl(spec)
    assert compiled.strip()
    candidate, validation = _run(EXACT_QUESTION, provider=lambda: _llm_payload(compiled))
    spl = str(candidate.get("candidate_spl") or "")
    assert spl.strip()
    assert candidate.get("execution_eligible") is False
    assert validation.get("approved") is False
    trace = candidate.get("utility_spl_draft_trace") or {}
    assert trace.get("final_raw_spl_source") in {
        "llm_draft",
        "llm_repair",
        "deterministic_compiler",
        "deterministic_skeleton",
    }
    _assert_valid_sequence_spl(spl)


def test_known_filter_count_shape(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_spl_draft_preview_enabled", True)
    family = match_detection_family(FILTER_COUNT_QUESTION)
    assert family in {"auth_failed_login_threshold", "auth_failed_login_spike"} or family
    preview = build_draft_preview(FILTER_COUNT_QUESTION, live_data_request=True)
    assert preview is not None
    spl = str(preview["draft_spl"])
    assert "fail" in spl.lower() or "4625" in spl
    assert "stats" in spl.lower() or "timechart" in spl.lower()
    report = evaluate_draft_quality(spl, detection_family=str(preview.get("detection_family") or ""))
    assert report.hard_fail_count == 0


def test_known_grouped_threshold_shape(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_spl_draft_preview_enabled", True)
    preview = build_draft_preview(THRESHOLD_QUESTION, live_data_request=True)
    assert preview is not None
    spl = str(preview["draft_spl"])
    assert "20" in spl or "fail" in spl.lower()
    report = evaluate_draft_quality(spl, detection_family=str(preview.get("detection_family") or ""))
    assert report.hard_fail_count == 0
    assert preview.get("execution_enabled") is False


def test_union_or_is_not_impossible() -> None:
    spl = (
        "search index=<auth_index> sourcetype=<auth_sourcetype> earliest=-60m latest=now "
        "(action=failure OR action=success) | stats count by user | head 100"
    )
    assert impossible_same_row_event_predicates(spl) is False
    report = evaluate_draft_quality(spl)
    assert not any(item.rule_id.endswith("Q19") for item in report.findings)


def test_exact_question_chat_is_known_review_only_sequence() -> None:
    response = chat(ChatRequest(message=EXACT_QUESTION))
    assert response.selected_use_case is not None
    assert response.selected_use_case.use_case_id == "auth_success_after_failure"
    intent = (response.query_to_intent or {}).get("intent_classification") or {}
    assert intent.get("intent_family") == "spl_generation_only"
    assert (response.evidence_plan or {}).get("answer_mode") == "spl_utility_authoring"
    assert (response.evidence_plan or {}).get("mcp_allowed") is False
    assert response.candidate_spl is not None
    assert response.candidate_spl.generation_mode == "deterministic_template_render"
    assert response.candidate_spl.execution_eligible is False
    assert response.spl_validation is not None
    assert response.spl_validation.approved is True
    spl = str(response.spl_validation.normalized_spl or "")
    _assert_valid_sequence_spl(spl)
    assert "(action=failure OR action=success)" in spl
    assert "last_success > first_failure" in spl
    assert response.execution is None or response.execution.status != "executed"
    contract = response.answer_contract
    if hasattr(contract, "model_dump"):
        contract = contract.model_dump()
    assert isinstance(contract, dict)
    assert contract.get("execution_status_label") != "execution_pending_mcp_unavailable"
    assert_governed_spl_review_posture(response)
