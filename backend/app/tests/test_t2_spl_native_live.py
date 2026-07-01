"""End-to-end /chat regressions for the live T1 SPL-native (T2) path.

Exercises the real pipeline entrypoint so the review-only SPL draft, runtime
source-profile validation, rendering, and safety invariants are covered together.
"""
from __future__ import annotations

import pytest

from app.api.routes_chat import chat
from app.config import settings
from app.schemas.requests import ChatRequest
from app.tests.support.chat_visible import spl_visible_text, visible_chat_prose

_SCADA = (
    "Provide a complete SPL query for index=scada_perf using earliest=-30d to compute "
    "eventstats stdev baseline by rtu_id and filter anomalies in last 24h using "
    "transmission_error_count"
)
_ASA = (
    "Generate a review-only SPL query to correlate power_sector_iocs.csv indicator_ip with Cisco ASA traffic "
    "in index=cisco_asa against dest_ip for the last 24h. Show src_ip, dest_ip, matched IOC, action, and count."
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
    spl_blob = spl_visible_text(response)
    assert "index=scada_perf" in spl_blob
    # No false DNS relevance rejection appears for a SCADA performance query.
    assert "dns" not in (cs.candidate_spl or "").lower()
    # Runtime source profile wired into the validator: index is not falsely rejected.
    sv = response.spl_validation
    assert sv is not None
    assert "disallowed_index" not in (sv.reject_reasons or [])

    # Never executable.
    assert sv.approved is False
    assert sv.normalized_spl is None


@pytest.fixture(autouse=True)
def _enable_draft_preview(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_spl_draft_preview_enabled", True)


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

    assert response.selected_skill == "spl_generation"
    assert response.response_mode == "review_required"
    assert t2["lookup_name"] == "power_sector_iocs.csv"
    assert t2["lookup_match_field"] == "indicator_ip"
    assert t2["log_match_field"] == "dest_ip"
    assert "src_ip" in t2["entity_fields"]
    assert "dest_ip" in t2["entity_fields"]
    assert t2["detection_window"] == "24h"
    assert t2["review_required"] is True
    assert "where isnotnull(matched_ioc)" in spl
    assert "asset_name" not in spl
    assert "where isnull(asset_name)" not in spl
    assert "pgcil_soc" not in spl
    assert "cisco:firepower" not in spl
    msg = spl_visible_text(response)
    assert "lookup power_sector_iocs.csv indicator_ip as dest_ip" in msg
    assert "asset_name" not in msg
    assert "inventory lookup" not in msg.lower()


def test_review_only_spl_rendered_when_mcp_blocked() -> None:
    response = _chat(_SCADA)
    # MCP execution stays blocked, but the draft is still shown.
    if response.execution is not None:
        assert response.execution.executed_spl is None
    spl_blob = spl_visible_text(response)
    assert "index=scada_perf" in spl_blob
    spl_blob = spl_visible_text(response)
    assert "Not executed" in spl_blob or "not executed" in spl_blob.lower() or "not performed" in spl_blob.lower()


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

    msg = visible_chat_prose(response)
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
    ar = response.analyst_response
    assert ar is not None
    lim = " ".join(ar.limitations or []).lower()
    checklist = " ".join(ar.analyst_checklist or []).lower()
    for bad in ("privileged account", "mfa status", "post-login", "post login"):
        assert bad not in lim
    assert "metric field validation missing" in lim
    assert "rtu asset cohort missing" in lim
    assert "z-score/threshold policy missing" in lim
    assert "not threshold alert" not in checklist
    assert "baseline and threshold" in checklist



def test_asa_ioc_lookup_checklist_is_operation_aware() -> None:
    response = _chat(_ASA)
    ar = response.analyst_response
    assert ar is not None
    checklist = " ".join(ar.analyst_checklist or []).lower()
    combined = (checklist + " " + visible_chat_prose(response)).lower()
    for token in (
        "cisco_asa",
        "power_sector_iocs.csv",
        "indicator_ip",
        "dest_ip",
        "investigation lead",
    ):
        assert token in combined
    for bad in (
        "dns",
        "user correlation",
        "8h",
        "asset inventory",
        "asset_name",
        "asset_ip",
        "privileged account",
        "mfa",
    ):
        assert bad not in combined


def test_scada_checklist_excludes_unrelated_families() -> None:
    response = _chat(_SCADA_REVIEW_ONLY)
    ar = response.analyst_response
    assert ar is not None
    checklist = " ".join(ar.analyst_checklist or []).lower()
    for bad in ("dns beacon", "user correlation", "mfa", "privileged account", "post-login", "post login", "cisco_asa"):
        assert bad not in checklist
    for token in ("scada_perf", "transmission_error_count", "rtu_id", "baseline"):
        assert token in checklist


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

def test_guided_investigation_spl_rescue_still_produces_scada_draft() -> None:
    """Defense in depth: guided skill still builds T2 draft when SPL is required."""
    from app.chat.pipeline import _candidate_spl_stage

    candidate_spl, spl_validation = _candidate_spl_stage(
        "test-trace",
        skill="guided_investigation",
        user_query=_SCADA_REVIEW_ONLY,
        spl_allowed=True,
    )
    assert candidate_spl is not None
    assert candidate_spl.get("generation_mode") == "t2_spl_native_review"
    assert spl_validation is not None and spl_validation.get("approved") is False
    assert "index=scada_perf" in str(candidate_spl.get("candidate_spl") or "")

