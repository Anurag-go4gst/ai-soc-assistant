"""Focused 105-question path-honoring tests (q0.q010 SMB top talkers + guards).

Exact 105 analytics matches must influence intent/path/answer shape while every
safety gate (unsafe block, MITRE tiers, execution-disabled posture) stays intact.
"""

from __future__ import annotations

import pytest

from app.chat.evidence_planner import plan_evidence
from app.chat.intent_classifier import build_query_to_intent
from app.chat.network_boundary_display import (
    analytics_traffic_label,
    is_firewall_boundary_query,
    resolve_analyst_use_case_label,
)
from app.chat.planning_decision import plan_path_and_tools
from app.config import settings
from app.query_understanding.parser import understand_query
from app.risk.severity_policy import (
    ANALYTICS_SEVERITY_NOT_ASSIGNED_LABEL,
    apply_analytics_severity_guard,
    decide_severity,
)
from app.spl.draft_preview import build_draft_preview, match_detection_family

SMB_TOP_HOSTS_QUERY = "Which hosts are generating the most SMB traffic?"
ESP_IT_TO_OT_QUERY = (
    "Look at our electronic security perimeter firewall logs and find any successful connections "
    "originating from the corporate IT network directly to the OT control center network."
)

_ROUTED_STUB = {"skill": "attack_discovery", "tool_plan": ["generate_spl", "validate_spl"]}


def _query_to_intent(query: str):
    return build_query_to_intent(query=query, query_understanding=understand_query(query))


def _smb_result():
    return _query_to_intent(SMB_TOP_HOSTS_QUERY)


def test_exact_105_smb_top_hosts_preserves_analytics_intent() -> None:
    understanding = understand_query(SMB_TOP_HOSTS_QUERY)
    assert understanding.deterministic_match_path == "exact_105_question"
    assert understanding.mapped_question_ref == "q0.q010"
    assert understanding.mapped_pattern_type == "top_n_aggregation"

    result = _smb_result()
    intent = result.intent_classification
    assert intent.intent_family == "spl_generation_only"
    assert intent.primary_intent == "spl_generation"
    assert intent.requested_output_type == "SPL"
    assert result.query_signals["exact_105_analytics"] is True


def test_exact_105_smb_top_hosts_does_not_fall_to_clarification() -> None:
    intent = _smb_result().intent_classification
    assert intent.intent_family != "clarification_required"
    assert intent.requires_clarification is False
    assert intent.confidence >= 0.85


def test_exact_105_smb_top_hosts_sets_needs_spl_true() -> None:
    result = _smb_result()
    understanding = understand_query(SMB_TOP_HOSTS_QUERY)
    plan = plan_evidence(
        result.intent_classification,
        query_to_intent=result.model_dump(),
        query_understanding=understanding,
    )
    assert plan.needs_spl is True
    assert plan.spl_allowed is True
    assert plan.needs_mcp is True
    assert plan.mcp_allowed is False
    decision = plan_path_and_tools(
        intent_classification=result.intent_classification.model_dump(),
        evidence_plan=plan.model_dump(),
        routed=_ROUTED_STUB,
        query_understanding=understanding,
    )
    assert decision.path_type == "spl_review"
    assert decision.execution_enabled is False


def test_exact_105_smb_top_hosts_does_not_assign_p3_default_severity() -> None:
    base = decide_severity(None, None, [])
    assert base.severity_label == "P3 Medium"  # baseline default this guard replaces
    guarded = apply_analytics_severity_guard(
        base, analytics_query=True, alert_context_present=False
    )
    assert guarded.severity_label == ANALYTICS_SEVERITY_NOT_ASSIGNED_LABEL
    assert not guarded.severity_label.startswith("P3")
    assert guarded.recommended_priority == "not_applicable"
    assert guarded.matched_rules == ["analytics_query_no_alert_evidence"]


def test_severity_guard_keeps_policy_and_alert_authority() -> None:
    base = decide_severity(None, None, [])
    with_alert = apply_analytics_severity_guard(
        base, analytics_query=True, alert_context_present=True
    )
    assert with_alert.severity_label == "P3 Medium"
    policy_decision = base.model_copy(update={"matched_rules": ["policy_rule_hit"]})
    with_policy = apply_analytics_severity_guard(
        policy_decision, analytics_query=True, alert_context_present=False
    )
    assert with_policy.matched_rules == ["policy_rule_hit"]


def test_exact_105_smb_top_hosts_label_not_it_to_ot_boundary() -> None:
    assert is_firewall_boundary_query(SMB_TOP_HOSTS_QUERY) is False
    label = resolve_analyst_use_case_label(
        use_case_id=None, catalog_label=None, user_query=SMB_TOP_HOSTS_QUERY
    )
    assert label == "SMB traffic analytics"
    assert label != "IT-to-OT network boundary traffic review"
    assert analytics_traffic_label(SMB_TOP_HOSTS_QUERY) == "SMB traffic analytics"


def test_top_talkers_query_routes_to_analytics_spl_review() -> None:
    query = "Top talkers by outbound bytes over the past day"
    result = _query_to_intent(query)
    intent = result.intent_classification
    assert intent.intent_family == "spl_generation_only"
    plan = plan_evidence(intent)
    decision = plan_path_and_tools(
        intent_classification=intent.model_dump(),
        evidence_plan=plan.model_dump(),
        routed=_ROUTED_STUB,
    )
    assert decision.path_type == "spl_review"


def test_analytics_query_without_alert_has_severity_not_assigned() -> None:
    query = "Which users sent the largest uploads to external destinations?"
    result = _query_to_intent(query)
    signals = result.query_signals
    assert signals["analytics_aggregation"] is True
    assert not signals["alert_context_present"]
    guarded = apply_analytics_severity_guard(
        decide_severity(None, None, []),
        analytics_query=bool(signals["analytics_aggregation"]),
        alert_context_present=bool(signals["alert_context_present"]),
    )
    assert guarded.severity_label == ANALYTICS_SEVERITY_NOT_ASSIGNED_LABEL


SUBSTATION_REMOTE_ACCESS_QUERY = (
    "Show me all external connections or remote access sessions currently mapping to the substation networks."
)


def test_substation_remote_access_enumeration_routes_to_esp_it_to_ot_draft(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Show-me enumeration on OT boundary remote access must not collapse to generic guided."""
    from app.query_understanding.soc_investigation_shape import detect_spl_artifact_request
    from app.routing.select_route_from_understanding import select_route_from_understanding

    monkeypatch.setattr(settings, "ai_soc_spl_draft_preview_enabled", True)
    assert detect_spl_artifact_request(SUBSTATION_REMOTE_ACCESS_QUERY) is True
    assert match_detection_family(SUBSTATION_REMOTE_ACCESS_QUERY) == "esp_it_to_ot_connection"
    understanding = understand_query(SUBSTATION_REMOTE_ACCESS_QUERY)
    route, _ = select_route_from_understanding(understanding, SUBSTATION_REMOTE_ACCESS_QUERY)
    assert route["skill"] == "spl_generation"
    preview = build_draft_preview(
        SUBSTATION_REMOTE_ACCESS_QUERY,
        spl_validation={
            "approved": False,
            "normalized_spl": None,
            "reject_reasons": ["spl_template_missing"],
            "review_required_reason": "spl_template_missing",
            "spl_template_status": "unavailable",
        },
    )
    assert preview is not None
    assert preview["detection_family"] == "esp_it_to_ot_connection"
    assert preview["execution_eligible"] is False


def test_powergrid_it_to_ot_firewall_question_still_routes_to_boundary_review() -> None:
    assert is_firewall_boundary_query(ESP_IT_TO_OT_QUERY) is True
    label = resolve_analyst_use_case_label(
        use_case_id=None, catalog_label=None, user_query=ESP_IT_TO_OT_QUERY
    )
    assert label == "IT-to-OT network boundary traffic review"
    result = _query_to_intent(ESP_IT_TO_OT_QUERY)
    assert result.intent_classification.intent_family != "clarification_required"


def test_powergrid_50_manual_firewall_draft_still_passes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_spl_draft_preview_enabled", True)
    assert match_detection_family(ESP_IT_TO_OT_QUERY) == "esp_it_to_ot_connection"
    preview = build_draft_preview(
        ESP_IT_TO_OT_QUERY,
        spl_validation={
            "approved": False,
            "normalized_spl": None,
            "reject_reasons": ["spl_template_missing"],
            "review_required_reason": "spl_template_missing",
            "spl_template_status": "unavailable",
        },
    )
    assert preview is not None
    assert preview["detection_family"] == "esp_it_to_ot_connection"
    assert preview["draft_lint_status"] == "passed"
    assert preview["execution_eligible"] is False
    # OT-scoped SMB stays on the lateral-movement family, not top-talkers.
    assert (
        match_detection_family("Investigate SMB traffic between OT network segments")
        == "firewall_ot_smb_lateral"
    )


def test_smb_top_talkers_draft_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_spl_draft_preview_enabled", True)
    assert match_detection_family(SMB_TOP_HOSTS_QUERY) == "network_smb_top_talkers"
    preview = build_draft_preview(SMB_TOP_HOSTS_QUERY)
    assert preview is not None
    assert preview["detection_family"] == "network_smb_top_talkers"
    assert preview["draft_lint_status"] == "passed"
    assert preview["review_required"] is True
    assert preview["execution_enabled"] is False
    assert preview["execution_eligible"] is False
    assert preview["governed"] is False
    spl = preview["draft_spl"]
    for token in ("445", "139", "%smb%", "%cifs%", "%microsoft-ds%"):
        assert token in spl
    for token in (
        "connection_count",
        "total_bytes",
        "distinct_destinations",
        "dest_ports",
        "first_seen",
        "last_seen",
    ):
        assert token in spl
    for field in ("index", "sourcetype", "dest_port", "action", "_time"):
        assert field in preview["required_log_fields"]


def test_unsafe_action_still_overrides_exact_or_spl_intent() -> None:
    query = "Which hosts are generating the most SMB traffic? Block this IP 10.1.1.5 on the firewall."
    result = _query_to_intent(query)
    intent = result.intent_classification
    assert intent.intent_family == "clarification_required"
    assert intent.primary_intent == "human_review"
    assert intent.requires_hil is True
    decision = plan_path_and_tools(
        intent_classification=intent.model_dump(),
        evidence_plan=None,
        routed=_ROUTED_STUB,
        query_understanding=understand_query(query),
    )
    assert decision.path_type == "unsafe_blocked"
    # Unsafe enforcement suppresses the lab draft entirely.
    assert build_draft_preview(query, unsafe_enforcement=True) is None


def test_live_pipeline_no_p3_leak_for_unbound_105_questions(monkeypatch: pytest.MonkeyPatch) -> None:
    """Regression for the q0.q096 stale answer: exact-105 questions without an
    active use-case severity policy must never display the P3 default, and the
    loose alert_context regex ("alert network events") must not defeat the guard."""
    monkeypatch.setattr(settings, "control_plane_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_spl_draft_preview_enabled", True)
    from app.api.routes_chat import build_live_chat_response
    from app.schemas.requests import ChatRequest

    cases = {
        "Which users performed privileged actions from non-admin workstations?": (
            "windows_identity_privileged_activity"
        ),
        "What incident or alert network events are high or critical right now?": (
            "notable_risk_review"
        ),
        "Which logs are missing from key security sources?": "data_source_health_review",
    }
    for query, family in cases.items():
        response = build_live_chat_response(ChatRequest(message=query))
        analyst = response.analyst_response
        assert analyst is not None, query
        assert analyst.severity_label == ANALYTICS_SEVERITY_NOT_ASSIGNED_LABEL, (
            query,
            analyst.severity_label,
        )
        preview = analyst.spl_draft_preview or {}
        assert preview.get("detection_family") == family, (query, preview.get("detection_family"))
        assert preview.get("execution_eligible") is False


def test_use_case_severity_policy_still_wins(monkeypatch: pytest.MonkeyPatch) -> None:
    """Questions bound to a use case with an active severity policy keep their
    policy severity (the guard only replaces the no-policy default)."""
    monkeypatch.setattr(settings, "control_plane_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_spl_draft_preview_enabled", True)
    from app.api.routes_chat import build_live_chat_response
    from app.schemas.requests import ChatRequest

    response = build_live_chat_response(
        ChatRequest(message="Which users have excessive failed logins?")
    )
    analyst = response.analyst_response
    assert analyst is not None
    assert analyst.severity_label is not None
    assert analyst.severity_label != ANALYTICS_SEVERITY_NOT_ASSIGNED_LABEL


def test_composer_inputs_cannot_reintroduce_p3_for_analytics(monkeypatch: pytest.MonkeyPatch) -> None:
    """Deterministic authority: the analytics severity label and draft posture
    survive the readability/composer fallback path verbatim."""
    monkeypatch.setattr(settings, "ai_soc_spl_draft_preview_enabled", True)
    from app.chat.final_answer_readability import apply_draft_preview_readability
    from app.schemas.responses import AnalystResponseEnvelope

    preview = build_draft_preview(SMB_TOP_HOSTS_QUERY)
    assert preview is not None
    envelope = AnalystResponseEnvelope(
        severity_label=ANALYTICS_SEVERITY_NOT_ASSIGNED_LABEL,
        finding_title="SMB traffic analytics",
        draft_spl_code=preview["draft_spl"],
        spl_draft_preview=preview,
    )
    result = apply_draft_preview_readability(envelope)
    assert result.severity_label == ANALYTICS_SEVERITY_NOT_ASSIGNED_LABEL
    assert "P3" not in (result.severity_label or "")
    assert result.hil_status == "required"
    assert result.spl_status == "review_required"
    summary = result.direct_answer_summary or ""
    assert "review-only" in summary.lower() or "review only" in summary.lower()
    assert "p3" not in summary.lower()
