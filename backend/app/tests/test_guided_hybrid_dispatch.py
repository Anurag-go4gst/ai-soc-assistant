"""REV4 batch 1 P8 — guided hybrid dispatch rail."""

from __future__ import annotations

import pytest

from app.chat.guided_handoff_trace import build_guided_handoff_trace
from app.chat.guided_hybrid_dispatch import uses_guided_hybrid_dispatch_from_state
from app.chat.guided_investigation_planner import validate_investigation_plan
from app.chat.guided_capability_validator import validate_guided_resource_plan
from app.chat.investigation_plan_builder import build_deterministic_investigation_plan
from app.chat.pipeline import build_live_chat_response
from app.config import settings
from app.planner.composer import compose_guided_resource_plan
from app.schemas.requests import ChatRequest
from app.chat.contracts.evidence_plan import EvidencePlan

SAMPLE_QUERY = (
    "How should I investigate unusual outbound traffic from an OT host overnight?"
)


@pytest.fixture(autouse=True)
def _hybrid_on(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "control_plane_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_guided_hybrid_investigation_enabled", True)
    monkeypatch.setattr(settings, "legacy_selected_skill_authority_enabled", False)
    monkeypatch.setattr(settings, "telemetry_mode", "none")
    monkeypatch.setattr(settings, "ai_soc_telemetry_sink", "none")


def test_uses_guided_hybrid_dispatch_from_state() -> None:
    enabled = {
        "planning_decision": {"path_type": "guided_investigation"},
        "evidence_plan": {
            "answer_mode": "guided_investigation",
            "investigation_planning_enabled": True,
        },
    }
    assert uses_guided_hybrid_dispatch_from_state(enabled) is True
    missing_capability = {
        "planning_decision": {"path_type": "guided_investigation"},
        "evidence_plan": {"answer_mode": "guided_investigation"},
    }
    assert uses_guided_hybrid_dispatch_from_state(missing_capability) is False


def test_guided_handoff_trace_segments() -> None:
    evidence = EvidencePlan(
        answer_mode="guided_investigation",
        rag_phase="rag_only",
        needs_rag=True,
        needs_spl=False,
        needs_mcp=False,
        needs_mitre=False,
        spl_allowed=False,
        mcp_allowed=False,
        policy_context_required=False,
        policy_context_recommended=True,
        discovery_allowed=True,
        spl_review_allowed=True,
        safe_spl_execution_allowed=True,
    )
    baseline = build_deterministic_investigation_plan(query=SAMPLE_QUERY)
    validated = validate_investigation_plan(baseline)
    pre = compose_guided_resource_plan(evidence, validated)
    post = validate_guided_resource_plan(evidence, pre)
    trace = build_guided_handoff_trace(
        investigation_plan_validated=validated,
        resource_plan_pre_validation=pre,
        resource_plan_validated=post.validated_resource_plan,
        blocked_resources=[],
    )
    for key in (
        "investigation_plan_validated",
        "resource_plan_pre_validation",
        "resource_plan_validated",
        "blocked_resources",
        "safe_spl_template_ids",
        "mcp_tool_ids",
        "evidence_planned",
        "evidence_collected",
    ):
        assert key in trace
    assert trace["investigation_plan_raw_llm"] is None
    assert trace["evidence_collected"] == 0


def test_flag_on_live_pipeline_uses_hybrid_dispatch() -> None:
    response = build_live_chat_response(ChatRequest(message=SAMPLE_QUERY))
    trace = response.control_plane_trace or {}
    dispatch = trace.get("plan_dispatch") or {}
    assert dispatch.get("dispatch_source") == "guided_hybrid_dispatch"
    schedule = dispatch.get("dispatch_schedule") or []
    assert "validator_a" in schedule or "guided_baseline" in schedule
    assert "execution" not in schedule
    assert "guided_handoff" in trace
    assert response.execution.status == "skipped"


def test_flag_off_remains_p1_baseline(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_guided_hybrid_investigation_enabled", False)
    response = build_live_chat_response(ChatRequest(message=SAMPLE_QUERY))
    trace = response.control_plane_trace or {}
    assert "guided_handoff" not in trace
    dispatch = trace.get("plan_dispatch") or {}
    assert dispatch.get("dispatch_schedule") == ["prepare_rag_only", "rag_early"]
