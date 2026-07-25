"""Batch A — T2 intent binding closure: renderer governance, LLM matrix, /chat smoke."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.chat.pipeline import build_live_chat_response
from app.chat.review_only_spl_renderer import render_review_only_spl_answer
from app.config import settings
from app.chat.contracts.llm_intent_advisory import LLMIntentAdvisory
from app.schemas.requests import ChatRequest
from app.spl.draft_preview import build_draft_preview
from app.spl.user_constraint_bindings import build_user_constraint_bindings

_WINEVENT_OFF_SHIFT = (
    "Run a Splunk search on the wineventlog index for Event ID 4624 (Successful Logon) "
    "originating from substation subnets outside normal shift hours."
)
_ASA_IOC = (
    "Generate a review-only SPL query to correlate power_sector_iocs.csv indicator_ip with Cisco ASA traffic "
    "in index=cisco_asa against dest_ip for the last 24h. Show src_ip, dest_ip, matched IOC, action, and count."
)
_SCADA_THRESHOLD = (
    "Provide a complete review-only SPL query for index=scada_perf using earliest=-30d to "
    "compute an eventstats stdev baseline by rtu_id and filter anomalies in the last 24h "
    "using transmission_error_count."
)

_T2_PROBES = (
    pytest.param(_WINEVENT_OFF_SHIFT, id="winevent_off_shift"),
    pytest.param(_ASA_IOC, id="cisco_asa_ioc"),
    pytest.param(_SCADA_THRESHOLD, id="scada_threshold"),
)

_FORBIDDEN_LIVE = (
    "currently showing",
    "we found in splunk",
    "observed in splunk",
    "execution: executed",
    "mock mcp execution complete",
    "live-backed",
)

_GATE_FIELDS = (
    "collected_evidence_count",
    "allow_severity_assessment",
    "allow_results_table",
    "allow_mitre_mapping",
    "allow_live_result_language",
    "execution_authorized",
)


@pytest.fixture(autouse=True)
def _draft_preview_on(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_spl_draft_preview_enabled", True)


@pytest.fixture(autouse=True)
def _control_plane_on(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "legacy_selected_skill_authority_enabled", False)


def _minimal_analyst() -> SimpleNamespace:
    return SimpleNamespace(
        severity_label=None,
        finding_title="Review-only SPL draft",
        scenario_label=None,
        analyst_checklist=[],
        draft_spl_code="",
        limitations=[],
    )


def _assert_renderer_governance(answer: str) -> None:
    low = answer.lower()
    assert "execution: not executed" in low or "not executed" in low
    assert "severity: not assigned from this question alone" in low
    assert "review-only" in low
    for phrase in _FORBIDDEN_LIVE:
        assert phrase not in low, f"forbidden live wording: {phrase!r}"
    assert "p1 —" not in low and "p2 —" not in low


def _assert_chat_gate_review_only(payload: dict) -> None:
    gate = (payload.get("structured_context") or {}).get("final_evidence_gate") or {}
    contract = payload.get("run_contract") or {}
    assert gate and contract
    for field in _GATE_FIELDS:
        if field in gate and field in contract:
            assert gate[field] == contract[field], field
    collected = int(contract.get("collected_evidence_count") or 0)
    if collected == 0:
        assert contract.get("allow_live_result_language") is False
        assert contract.get("execution_authorized") is False
        assert contract.get("allow_results_table") is False
    if not contract.get("allow_severity_assessment"):
        severity = payload.get("severity_decision") or {}
        label = str(severity.get("severity_label") or "")
        assert not label.startswith("P1") and not label.startswith("P2")
    routing = contract.get("routing") or {}
    assert routing.get("authority_holder") == "canonical_run_contract"
    assert payload.get("selected_skill") == routing.get("canonical_skill")
    if contract.get("mcp_allowed") is False:
        posture = contract.get("mcp_posture") or {}
        assert posture.get("execution_authorized") is False


@pytest.mark.parametrize("query", _T2_PROBES)
def test_t2_probe_renderer_governance_from_draft_preview(query: str) -> None:
    preview = build_draft_preview(
        query,
        spl_validation={"spl_template_status": "missing"},
        live_data_request=True,
    )
    assert preview is not None
    assert preview.get("execution_enabled") is False
    answer = render_review_only_spl_answer(
        analyst_response=_minimal_analyst(),
        draft_preview=preview,
    )
    _assert_renderer_governance(answer)
    spl = str(preview.get("draft_spl") or "")
    assert spl
    assert "<index>" not in spl


@pytest.mark.parametrize("query", _T2_PROBES)
def test_t2_probe_chat_run_contract_final_gate_smoke(query: str) -> None:
    payload = build_live_chat_response(ChatRequest(message=query)).model_dump(mode="json")
    _assert_chat_gate_review_only(payload)
    cs = payload.get("candidate_spl") or {}
    if cs:
        assert cs.get("execution_eligible") is False
    plan = payload.get("evidence_plan") or {}
    if plan.get("needs_mcp"):
        steps = (plan.get("resource_plan") or {}).get("steps") or []
        mcp_steps = [s for s in steps if isinstance(s, dict) and s.get("step_id") == "mcp"]
        assert mcp_steps, "needs_mcp without MCP ResourcePlan step"


@pytest.mark.parametrize(
    ("mode", "advisory"),
    [
        ("disabled", None),
        (
            "mock_advisory",
            LLMIntentAdvisory(
                entity_slots_candidate={
                    "user": "extra_user",
                    "dest_zone": "OT DMZ",
                    "threshold": "99",
                }
            ),
        ),
        (
            "alias_slots",
            LLMIntentAdvisory(
                entity_slots_candidate={
                    "event_id": "4624",
                    "account": "jsmith",
                    "src_subnet": "substation_subnet",
                }
            ),
        ),
        (
            "conflicting_slot",
            LLMIntentAdvisory(
                entity_slots_candidate={"index": "wrong_index", "event_id": "9999"},
            ),
        ),
    ],
)
@pytest.mark.parametrize("query", _T2_PROBES)
def test_t2_probe_llm_matrix_bindings_stay_review_only(
    query: str,
    mode: str,
    advisory: LLMIntentAdvisory | None,
) -> None:
    bindings = build_user_constraint_bindings(query, llm_intent_advisory=advisory)
    if mode == "conflicting_slot" and "wineventlog" in query.lower():
        assert bindings.normalized_slots.get("index") == "wineventlog"
        assert bindings.normalized_slots.get("event_code") == "4624"
    if mode == "alias_slots" and "wineventlog" in query.lower():
        assert bindings.normalized_slots.get("event_code") == "4624"
        assert bindings.normalized_slots.get("user") == "jsmith"
        assert bindings.normalized_slots.get("src_scope") == "substation_subnet"
    preview = build_draft_preview(
        query,
        spl_validation={"spl_template_status": "missing"},
        live_data_request=True,
        llm_intent_advisory=advisory,
    )
    assert preview is not None
    assert preview.get("execution_enabled") is False
    answer = render_review_only_spl_answer(
        analyst_response=_minimal_analyst(),
        draft_preview=preview,
    )
    _assert_renderer_governance(answer)


def test_aggregation_subject_lives_in_normalized_slots_not_top_level_accessor() -> None:
    """Phase 1: normalized_slots['aggregation_subject'] is canonical; no parallel field required."""
    bindings = build_user_constraint_bindings(
        "Find users with more than 10 failed logins in 30 minutes."
    )
    assert not hasattr(bindings, "explicit_aggregation_subject")
    subject = bindings.normalized_slots.get("aggregation_subject")
    assert subject in {"user", None} or "user" in str(subject or "")
