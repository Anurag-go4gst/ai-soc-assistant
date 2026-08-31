"""SPL utility-authoring reliability + semantic fidelity (injected, no live LLM)."""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

import pytest

from app.chat.review_only_spl_renderer import (
    SPL_AUTHORING_ABSTENTION_MESSAGE,
    apply_review_only_spl_render,
    render_review_only_spl_answer,
)
from app.config import settings
from app.spl.llm_fallback import (
    SPL_ADVISORY_JSON_SCHEMA,
    generate_llm_spl_fallback,
)
from app.spl.llm_plan_compiler import compile_intent_spec_to_spl
from app.spl.spl_intent_spec import build_spl_intent_spec
from app.spl.spl_semantic_fidelity import validate_semantic_fidelity
from app.spl.utility_spl_authoring import candidate_from_universal_utility_authoring

# Structured authoring samples — not production hardcodes.
P1_AUTH_BASELINE = (
    "Write an SPL query to find successful Windows logons (EventCode=4624) by "
    "accounts matching admin-* or svc-* during the last 7 days. Compare them with "
    "a separate preceding 30-day history for the same account and flag destination "
    "hosts that the account had not previously accessed. Group results into "
    "one-hour windows and return the user, new host, source IP, and distinct count "
    "of new hosts. Do not execute the query."
)
P2_FAILED_THEN_SUCCESS = (
    "Write review-only SPL to identify accounts with more than 20 failed logins "
    "within 15 minutes followed by a successful login from the same source IP. "
    "Return user, source IP, destination host, failure count and success time. "
    "Do not execute."
)
P3_PARENT_CHILD = (
    "Write review-only SPL to find powershell.exe launched by winword.exe or "
    "excel.exe, grouped by host and user, returning parent process, child process, "
    "command line and first/last seen. Do not execute."
)
P4_FIRST_SEEN_DOMAIN = (
    "Write review-only SPL to find destination domains contacted in the last "
    "24 hours that were not seen for the same host during the preceding 14 days. "
    "Return host, destination domain, source IP and first-seen time. Do not execute."
)
N1_UNRESOLVED_FIELD = (
    "Write review-only SPL listing events where ACME_UNIT_TOKEN equals 7 over "
    "the last 24 hours. Do not execute."
)


class _Telemetry:
    def record_step(self, *args: Any, **kwargs: Any) -> None:
        return None

    def record_spl_validation(self, *args: Any, **kwargs: Any) -> None:
        return None


def _profile() -> Any:
    return __import__(
        "app.splunk.capabilities", fromlist=["build_splunk_capability_profile"]
    ).build_splunk_capability_profile(required_saia_tool="saia_generate_spl")


def _llm_payload(spl: str, **overrides: Any) -> str:
    body: dict[str, Any] = {
        "status": "candidate_generated",
        "confidence_score": 0.72,
        "confidence_label": "medium",
        "detection_family": "utility_authoring",
        "candidate_spl": spl,
        "index": "<auth_index>",
        "sourcetype": "<auth_sourcetype>",
        "result_cap": 100,
        "unresolved_slots": [],
        "assumptions": ["Review-only utility draft; placeholders are not environment facts."],
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
    monkeypatch.setattr(
        "app.spl.utility_spl_authoring.load_persisted_source_profile",
        lambda: {},
    )
    monkeypatch.setattr(
        "app.spl.utility_spl_authoring.load_persisted_source_profile_document",
        lambda: {"values": {}, "field_sources": {}},
    )


def _run(
    query: str,
    *,
    provider,
) -> tuple[dict[str, Any], dict[str, Any]]:
    result = candidate_from_universal_utility_authoring(
        trace_id="authoring-fidelity",
        skill="spl_generation",
        user_query=query,
        telemetry=_Telemetry(),
        profile=_profile(),
        spl_governance=None,
        llm_raw_output_provider=provider,
    )
    assert result is not None
    return result


def _faithful_p1_spl() -> str:
    spec = build_spl_intent_spec(P1_AUTH_BASELINE)
    spl = compile_intent_spec_to_spl(spec)
    assert spl.strip(), spec
    return spl


def _assert_no_execution(candidate: dict[str, Any], validation: dict[str, Any]) -> None:
    assert candidate.get("execution_eligible") is False
    assert candidate.get("execution_enabled") is False
    assert validation.get("approved") is False
    assert validation.get("normalized_spl") in (None, "")


# ---------------------------------------------------------------------------
# Defect B — schema alignment
# ---------------------------------------------------------------------------


def test_schema_status_enum_and_required_arrays() -> None:
    status = SPL_ADVISORY_JSON_SCHEMA["properties"]["status"]
    assert status.get("enum") == ["candidate_generated", "needs_clarification", "blocked"]
    assumptions = SPL_ADVISORY_JSON_SCHEMA["properties"]["assumptions"]
    required_fields = SPL_ADVISORY_JSON_SCHEMA["properties"]["required_fields"]
    assert assumptions.get("minItems") == 1
    assert required_fields.get("minItems") == 1
    required = set(SPL_ADVISORY_JSON_SCHEMA["required"])
    assert "assumptions" in required
    assert "required_fields" in required
    result_cap = SPL_ADVISORY_JSON_SCHEMA["properties"]["result_cap"]
    cap_type = result_cap.get("type")
    assert cap_type == ["integer", "null"] or (
        isinstance(cap_type, list) and "null" in cap_type and "integer" in cap_type
    )


# ---------------------------------------------------------------------------
# Defect A — observability
# ---------------------------------------------------------------------------


def test_observability_json_parse_stage_not_opaque(spl_flags: None, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_llm_spl_fallback_enabled", True)
    result = generate_llm_spl_fallback(
        user_query=P1_AUTH_BASELINE,
        utility_authoring=True,
        llm_raw_output_provider=lambda: "not-json {",
    )
    assert result is not None
    assert result.clarification_required is True
    assert result.authoring_failure_stage == "json_parse"
    assert result.authoring_failure_code
    assert "llm_spl_fallback_schema_invalid" != result.authoring_failure_stage
    assert not (result.candidate_spl or "").strip()


def test_observability_content_validation_empty_candidate(spl_flags: None, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_llm_spl_fallback_enabled", True)
    payload = _llm_payload("", status="candidate_generated")
    result = generate_llm_spl_fallback(
        user_query=P1_AUTH_BASELINE,
        utility_authoring=True,
        llm_raw_output_provider=lambda: payload,
    )
    assert result is not None
    assert result.authoring_failure_stage == "content_validation"
    assert result.authoring_failure_code


def test_n2_malformed_json_no_generic_skeleton(spl_flags: None) -> None:
    candidate, validation = _run(P1_AUTH_BASELINE, provider=lambda: "{{{{not json")
    trace = candidate.get("utility_spl_draft_trace") or {}
    assert trace.get("authoring_failure_stage") == "json_parse"
    assert candidate.get("spl_authoring_unavailable") is True
    assert not (candidate.get("candidate_spl") or "").strip()
    _assert_no_execution(candidate, validation)
    spl_text = str(candidate.get("candidate_spl") or "")
    assert "EventCode=4624" not in spl_text


# ---------------------------------------------------------------------------
# Defect D — intent spec reuse (no DetectionSpec)
# ---------------------------------------------------------------------------


def test_p1_intent_spec_preserves_dual_windows_and_actors() -> None:
    spec = build_spl_intent_spec(P1_AUTH_BASELINE)
    assert spec["contract_version"] == "spl_semantic_v2"
    assert spec["analysis_shape"] == "first_seen"
    assert spec["support_status"] == "supported"
    assert "successful_login" in (spec.get("required_event_sets") or [])
    actors = {str(item).lower() for item in (spec.get("actor_patterns") or [])}
    assert any(item.startswith("admin-") for item in actors)
    assert any(item.startswith("svc-") for item in actors)
    assert "7d" in str(spec.get("observation_window") or spec.get("search_horizon") or "")
    baseline = str(spec.get("baseline_window") or "")
    assert "30d" in baseline
    rels = spec.get("relationships") or []
    assert any(item.get("type") == "first_seen" for item in rels if isinstance(item, dict))
    outputs = {str(item) for item in (spec.get("required_outputs") or [])}
    assert "user" in outputs
    assert "host" in outputs or "dest_host" in outputs
    assert "src_ip" in outputs
    assert spec.get("temporal_grain") == "1h"


# ---------------------------------------------------------------------------
# Defect C — unfaithful fallback abstains
# ---------------------------------------------------------------------------


def test_n3_empty_candidate_typed_abstention(spl_flags: None) -> None:
    candidate, validation = _run(P1_AUTH_BASELINE, provider=lambda: _llm_payload(""))
    assert candidate.get("spl_authoring_unavailable") is True
    assert not (candidate.get("candidate_spl") or "").strip()
    _assert_no_execution(candidate, validation)


def test_n4_dropped_baseline_blocked(spl_flags: None) -> None:
    dropped = (
        "search index=<auth_index> sourcetype=<auth_sourcetype> earliest=-7d latest=now "
        "EventCode=4624 (user=admin-* OR user=svc-*) "
        "| stats count by user, dest, src_ip | bin _time span=1h"
    )
    spec = build_spl_intent_spec(P1_AUTH_BASELINE)
    fidelity = validate_semantic_fidelity(spec, dropped)
    assert fidelity["passed"] is False
    assert any("baseline" in str(item) or "first_seen" in str(item) for item in fidelity["losses"])
    candidate, validation = _run(P1_AUTH_BASELINE, provider=lambda: _llm_payload(dropped))
    assert candidate.get("spl_authoring_unavailable") is True
    assert not (candidate.get("candidate_spl") or "").strip()
    _assert_no_execution(candidate, validation)


def test_n5_actor_semantics_narrowed_blocked(spl_flags: None) -> None:
    narrowed = (
        "search index=<auth_index> sourcetype=<auth_sourcetype> earliest=-37d latest=now "
        "EventCode=4624 user=admin-* "
        '| eval period=if(_time>=relative_time(now(), "-7d"), "observation", "baseline") '
        "| stats values(dest) as hosts by user"
    )
    spec = build_spl_intent_spec(P1_AUTH_BASELINE)
    fidelity = validate_semantic_fidelity(spec, narrowed)
    assert fidelity["passed"] is False
    assert any("actor" in str(item) for item in fidelity["losses"])
    candidate, validation = _run(P1_AUTH_BASELINE, provider=lambda: _llm_payload(narrowed))
    assert candidate.get("spl_authoring_unavailable") is True
    assert not (candidate.get("candidate_spl") or "").strip()


def test_invalid_llm_does_not_emit_unfaithful_generic_skeleton(spl_flags: None) -> None:
    candidate, validation = _run(P1_AUTH_BASELINE, provider=lambda: "not-json")
    spl = str(candidate.get("candidate_spl") or "")
    if spl.strip():
        spec = build_spl_intent_spec(P1_AUTH_BASELINE)
        assert validate_semantic_fidelity(spec, spl)["passed"] is True
    else:
        assert candidate.get("spl_authoring_unavailable") is True
    _assert_no_execution(candidate, validation)
    if "EventCode=4624" in spl:
        spec = build_spl_intent_spec(P1_AUTH_BASELINE)
        assert validate_semantic_fidelity(spec, spl)["passed"] is True


# ---------------------------------------------------------------------------
# Defect E — analyst vs operator
# ---------------------------------------------------------------------------


def test_analyst_abstention_hides_internal_codes(spl_flags: None) -> None:
    candidate, _validation = _run(P1_AUTH_BASELINE, provider=lambda: "not-json")
    preview = {
        "detection_family": "universal_timestamp_spl",
        "draft_spl": "search index=<your_index> EventCode=4624 | stats count | head 100",
        "generation_mode": "deterministic_lab_draft",
    }
    analyst = SimpleNamespace(
        severity_label="should-not-leak",
        analyst_checklist=["internal"],
        draft_spl_code=preview["draft_spl"],
    )
    run_contract = SimpleNamespace(answer_mode="spl_utility_authoring", spl_status="review_required")
    from app.chat.review_only_spl_renderer import is_review_only_spl_answer

    if not is_review_only_spl_answer(run_contract):
        rendered = render_review_only_spl_answer(
            analyst_response=analyst,
            draft_preview=preview,
            candidate_spl=candidate,
        )
        text = rendered
    else:
        updated, text = apply_review_only_spl_render(
            run_contract=run_contract,
            analyst_response=analyst,
            message=preview["draft_spl"],
            draft_preview=preview,
            candidate_spl=candidate,
        )
        text = text or render_review_only_spl_answer(
            analyst_response=updated,
            draft_preview=preview,
            candidate_spl=candidate,
        )
    assert SPL_AUTHORING_ABSTENTION_MESSAGE in text
    assert "llm_spl_fallback_schema_invalid" not in text
    assert "schema_validation" not in text
    assert "adapter_error" not in text.lower()
    assert "EventCode=4624" not in text


# ---------------------------------------------------------------------------
# Positive capability — compiled / injected faithful drafts
# ---------------------------------------------------------------------------


def test_p1_compiled_or_injected_faithful_draft(spl_flags: None) -> None:
    spec = build_spl_intent_spec(P1_AUTH_BASELINE)
    compiled = compile_intent_spec_to_spl(spec)
    assert compiled.strip()
    fidelity = validate_semantic_fidelity(spec, compiled)
    assert fidelity["passed"] is True, fidelity
    lowered = compiled.lower()
    assert "4624" in compiled or "action=success" in lowered
    assert "admin-" in lowered
    assert "svc-" in lowered
    assert "7d" in lowered.replace(" ", "")
    assert "30d" in lowered or "baseline" in lowered
    assert "1h" in lowered or "span=1h" in lowered
    candidate, validation = _run(P1_AUTH_BASELINE, provider=lambda: _llm_payload(compiled))
    assert candidate.get("spl_authoring_unavailable") is False
    assert (candidate.get("candidate_spl") or "").strip()
    final_fid = (candidate.get("utility_spl_draft_trace") or {}).get("semantic_fidelity_final") or {}
    assert final_fid.get("passed") is True
    _assert_no_execution(candidate, validation)


def test_p2_injected_faithful_sequence(spl_flags: None) -> None:
    spec = build_spl_intent_spec(P2_FAILED_THEN_SUCCESS)
    spl = compile_intent_spec_to_spl(spec)
    fidelity = validate_semantic_fidelity(spec, spl)
    assert spl.strip()
    assert fidelity.get("passed") is True, fidelity
    lowered = spl.lower()
    assert "4625" in spl or "failure" in lowered
    assert "4624" in spl or "success" in lowered
    assert "20" in spl
    assert "15m" in lowered or "900" in spl
    candidate, validation = _run(P2_FAILED_THEN_SUCCESS, provider=lambda: _llm_payload(spl))
    _assert_no_execution(candidate, validation)
    assert candidate.get("spl_authoring_unavailable") is False
    final = str(candidate.get("candidate_spl") or "")
    assert "4625" in final or "failure" in final.lower()
    assert "4624" in final or "success" in final.lower()


def test_p3_process_constraints_in_spec(spl_flags: None) -> None:
    spec = build_spl_intent_spec(P3_PARENT_CHILD)
    child = {str(item).lower() for item in ((spec.get("process_constraints") or {}).get("child") or [])}
    parent = {str(item).lower() for item in ((spec.get("process_constraints") or {}).get("parent") or [])}
    assert any("powershell" in item for item in child)
    assert any("winword" in item for item in parent)
    assert any("excel" in item for item in parent)
    compiled = compile_intent_spec_to_spl(spec)
    assert compiled.strip()
    result = validate_semantic_fidelity(spec, compiled)
    assert result["passed"] is True, result
    lowered = compiled.lower()
    assert "powershell" in lowered
    assert "winword" in lowered
    assert "excel" in lowered
    assert "command_line" in lowered
    candidate, validation = _run(P3_PARENT_CHILD, provider=lambda: _llm_payload(compiled))
    _assert_no_execution(candidate, validation)
    assert candidate.get("spl_authoring_unavailable") is False


def test_p4_first_seen_domain_spec_and_fidelity() -> None:
    spec = build_spl_intent_spec(P4_FIRST_SEEN_DOMAIN)
    assert spec["analysis_shape"] == "first_seen"
    assert "24h" in str(spec.get("observation_window") or "")
    assert "14d" in str(spec.get("baseline_window") or "")
    compiled = compile_intent_spec_to_spl(spec)
    assert compiled.strip()
    result = validate_semantic_fidelity(spec, compiled)
    assert result["passed"] is True, result


def test_n1_unresolved_org_field_does_not_invent_mapping(spl_flags: None) -> None:
    spec = build_spl_intent_spec(N1_UNRESOLVED_FIELD)
    unresolved = spec.get("unresolved_required_fields") or []
    assert any("ACME_UNIT_TOKEN" in str(item) for item in unresolved)
    invented = (
        "search index=<index> sourcetype=<sourcetype> earliest=-24h latest=now "
        "src_ip=7 | stats count by src_ip | head 100"
    )
    fidelity = validate_semantic_fidelity(spec, invented)
    assert fidelity["passed"] is False
    candidate, validation = _run(N1_UNRESOLVED_FIELD, provider=lambda: _llm_payload(invented))
    assert candidate.get("spl_authoring_unavailable") is True
    assert "src_ip=7" not in str(candidate.get("candidate_spl") or "")
    _assert_no_execution(candidate, validation)


def test_no_detectionspec_module_added() -> None:
    import app.spl.spl_intent_spec as spec_mod

    assert not hasattr(spec_mod, "DetectionSpec")
    assert spec_mod.SPL_SEMANTIC_CONTRACT_VERSION == "spl_semantic_v2"
