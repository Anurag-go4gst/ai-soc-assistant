"""End-to-end /chat regressions for the live T1 SPL-native (T2) path.

Exercises the real pipeline entrypoint so the review-only SPL draft, runtime
source-profile validation, rendering, and safety invariants are covered together.
"""
from __future__ import annotations

from app.api.routes_chat import chat
from app.schemas.requests import ChatRequest

_SCADA = (
    "Provide a complete SPL query for index=scada_perf using earliest=-30d to compute "
    "eventstats stdev baseline by rtu_id and filter anomalies in last 24h using "
    "transmission_error_count"
)
_ASA = (
    "Generate SPL to correlate power_sector_iocs.csv indicator_ip with Cisco ASA traffic "
    "in index=cisco_asa against dest_ip for last 24h"
)


def _chat(message: str):
    return chat(ChatRequest(message=message))


def test_scada_threshold_anomaly_live_review_only() -> None:
    response = _chat(_SCADA)
    assert response.selected_skill == "spl_generation"
    # A review-only draft is a review state, not a clarification.
    assert response.response_mode == "review_required"
    assert response.human_review is not None
    assert response.human_review.review_type == "spl_review_required"
    cs = response.candidate_spl
    assert cs is not None
    assert cs.generation_mode == "t2_spl_native_review"
    assert cs.execution_eligible is False
    # T2 artifact fields are carried on the envelope.
    t2 = cs.t2_spl_native
    assert t2 is not None
    assert t2["runtime_operation"] == "threshold_anomaly"
    assert t2["source_profile"] == "scada_perf"
    assert "rtu_id" in t2["entity_fields"]
    assert "transmission_error_count" in t2["metric_fields"]
    assert t2["execution_eligible"] is False
    assert t2["review_required"] is True
    # Review-only SPL is rendered even though MCP execution is blocked.
    assert "index=scada_perf" in response.message
    # No false DNS relevance rejection appears for a SCADA performance query.
    assert "dns" not in (cs.candidate_spl or "").lower()
    # Runtime source profile wired into the validator: index is not falsely rejected.
    sv = response.spl_validation
    assert sv is not None
    assert "disallowed_index" not in (sv.reject_reasons or [])
    # Never executable.
    assert sv.approved is False
    assert sv.normalized_spl is None


def test_asa_ioc_lookup_live_review_only() -> None:
    response = _chat(_ASA)
    cs = response.candidate_spl
    assert cs is not None
    assert cs.generation_mode == "t2_spl_native_review"
    t2 = cs.t2_spl_native
    assert t2 is not None
    assert t2["runtime_operation"] == "lookup_correlation"
    assert t2["source_profile"] == "cisco_asa"
    spl = cs.candidate_spl or ""
    assert "lookup power_sector_iocs.csv indicator_ip as dest_ip" in spl
    assert "table src_ip dest_ip actions event_count matched_ioc" in spl
    assert cs.execution_eligible is False
    sv = response.spl_validation
    assert sv is not None and sv.approved is False and sv.normalized_spl is None
    assert "disallowed_index" not in (sv.reject_reasons or [])


def test_review_only_spl_rendered_when_mcp_blocked() -> None:
    response = _chat(_SCADA)
    # MCP execution stays blocked, but the draft is still shown.
    if response.execution is not None:
        assert response.execution.executed_spl is None
    assert "index=scada_perf" in response.message
    assert "Not executed" in response.message or "not executed" in response.message.lower()


_SCADA_REVIEW_ONLY = (
    "Provide a complete review-only SPL query for index=scada_perf using earliest=-30d to "
    "compute an eventstats stdev baseline by rtu_id and filter anomalies in the last 24h "
    "using transmission_error_count."
)


def test_scada_review_only_phrasing_routes_t2_not_guided_investigation() -> None:
    # Regression: the "review-only SPL" + index/metric/entity/time-window phrasing
    # must land on the T1/T2 SPL-native path — not guided investigation, not an
    # IT-to-OT boundary review, not a P3 severity, not MITRE/missing-evidence.
    response = _chat(_SCADA_REVIEW_ONLY)
    assert response.selected_skill == "spl_generation"
    cs = response.candidate_spl
    assert cs is not None and cs.generation_mode == "t2_spl_native_review"
    t2 = cs.t2_spl_native
    assert t2 is not None
    assert t2["runtime_operation"] == "threshold_anomaly"
    assert t2["source_profile"] == "scada_perf"
    assert "rtu_id" in t2["entity_fields"]
    assert "transmission_error_count" in t2["metric_fields"]
    assert t2["baseline_window"] == "30d"
    assert t2["detection_window"] == "24h"
    assert cs.execution_eligible is False

    msg = response.message or ""
    # Review-only SPL artifact is rendered.
    assert "index=scada_perf" in msg
    assert "Review-only SPL draft" in msg
    # No severity assignment, no IT-to-OT boundary framing, no guided investigation.
    assert "Severity: Not assigned from this question alone" in msg
    assert "IT-to-OT" not in msg
    assert "investigation plan" not in msg.lower()
    assert "guided" not in (response.selected_skill or "").lower()
    # No MITRE mapping, no privileged-account / MFA missing-evidence leakage.
    assert not (response.mitre_mappings or [])
    low = msg.lower()
    assert "privileged account" not in low
    assert "mfa" not in low


def test_exact_105_preserved_no_t2_hijack() -> None:
    # A canonical exact-105 question must keep its deterministic route and must
    # not be turned into a T2 SPL-native review draft.
    response = _chat("Which users have excessive failed logins?")
    cs = response.candidate_spl
    if cs is not None:
        assert cs.generation_mode != "t2_spl_native_review"
        assert cs.t2_spl_native is None


def test_t2_never_execution_eligible_or_mcp_allowed() -> None:
    for message in (_SCADA, _ASA):
        response = _chat(message)
        cs = response.candidate_spl
        assert cs is not None and cs.execution_eligible is False
        if response.execution is not None:
            assert response.execution.executed_spl is None
        # The evidence plan must not authorise MCP execution for a review-only draft.
        if response.evidence_plan is not None:
            assert response.evidence_plan.get("mcp_allowed") in (False, None)
