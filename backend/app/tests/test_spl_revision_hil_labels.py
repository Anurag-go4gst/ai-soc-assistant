"""HIL label polish for governed template review-only SPL drafts."""

from __future__ import annotations

from app.config import settings
from app.chat.pipeline import build_live_chat_response
from app.evals.sentinel_eval import sentinel_runtime
from app.graph.resource_planner_graph import run_chat_via_resource_planner_graph
from app.orchestration.mcp_execution_gate import _gate_review
from app.orchestration.spl_revision_hil import resolve_spl_revision_hil_reason
from app.schemas.requests import ChatRequest

_Q046 = "Which users have excessive failed logins?"


def test_resolve_template_review_for_governed_binding_gaps() -> None:
    reason = resolve_spl_revision_hil_reason(
        {
            "approved": False,
            "normalized_spl": None,
            "template_id": "auth_failed_login_spike",
            "selected_candidate_spl_provider": "deterministic_template_render",
            "reject_reasons": [
                "missing_binding:group_by_user",
                "user_constraints_not_encoded",
            ],
        },
        candidate_spl={
            "template_id": "auth_failed_login_spike",
            "generation_mode": "deterministic_template_render",
            "candidate_spl": "search index=pgcil_soc sourcetype=pgcil:auth earliest=-24h latest=now | stats count by user | head 100",
        },
    )
    assert reason == "template_review_required"


def test_resolve_hard_policy_failure_stays_validation_failed() -> None:
    reason = resolve_spl_revision_hil_reason(
        {
            "approved": False,
            "normalized_spl": None,
            "template_id": "auth_failed_login_spike",
            "selected_candidate_spl_provider": "deterministic_template_render",
            "reject_reasons": ["blocked_command:delete"],
        },
        candidate_spl={
            "template_id": "auth_failed_login_spike",
            "generation_mode": "deterministic_template_render",
            "candidate_spl": "search index=pgcil_soc | delete",
        },
    )
    assert reason == "spl_validation_failed"


def test_gate_review_uses_template_review_reason() -> None:
    review = _gate_review(
        selected_skill="attack_discovery",
        spl_validation={
            "approved": False,
            "normalized_spl": None,
            "template_id": "auth_failed_login_spike",
            "selected_candidate_spl_provider": "deterministic_template_render",
            "reject_reasons": ["missing_binding:group_by_user"],
        },
        selected_mcp_server="splunk_soc",
        selected_mcp_tool="splunk_run_query",
        registry=object(),
    )
    assert review["review_type"] == "spl_revision"
    assert review["reason"] == "template_review_required"


def test_q046_live_path_hil_reason_is_template_review(monkeypatch) -> None:
    monkeypatch.setattr(settings, "control_plane_enabled", True)
    monkeypatch.setattr(settings, "legacy_selected_skill_authority_enabled", False)
    monkeypatch.setattr(settings, "ai_soc_spl_draft_preview_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_spl_template_governance_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_llm_spl_fallback_enabled", False)

    payload = build_live_chat_response(ChatRequest(message=_Q046)).model_dump(mode="json")
    hr = payload.get("human_review") or {}
    sv = payload.get("spl_validation") or {}
    assert hr.get("review_type") == "spl_revision"
    assert hr.get("reason") == "template_review_required"
    assert sv.get("template_id") == "auth_failed_login_spike"
    assert sv.get("approved") is False
    assert sv.get("reject_reasons")
    rc = payload.get("run_contract") or {}
    assert rc.get("execution_authorized") is False
    assert rc.get("mcp_allowed") is False


def test_q046_resource_planner_hil_reason(monkeypatch) -> None:
    monkeypatch.setattr(settings, "control_plane_enabled", True)
    monkeypatch.setattr(settings, "legacy_selected_skill_authority_enabled", False)
    monkeypatch.setattr(settings, "ai_soc_spl_draft_preview_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_spl_template_governance_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_llm_spl_fallback_enabled", False)
    monkeypatch.setattr(settings, "langgraph_orchestration_enabled", True)

    request = ChatRequest(message=_Q046)
    with sentinel_runtime():
        response = run_chat_via_resource_planner_graph(request)

    hr = response.human_review
    assert hr is not None
    assert hr.review_type == "spl_revision"
    assert hr.reason == "template_review_required"
    assert response.candidate_spl is not None
    assert response.candidate_spl.template_id == "auth_failed_login_spike"
    assert len(str(response.candidate_spl.candidate_spl or "")) > 80
    rc = response.run_contract or {}
    assert rc.get("execution_authorized") is False
    assert rc.get("mcp_allowed") is False
    assert response.spl_validation is not None
    assert response.spl_validation.reject_reasons
