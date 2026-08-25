"""Item 2.2 — evidence loop reachable for all tiers (discovery-only grants).

Scope, grounded against the actual architecture (not the plan's original
draft text): `mcp_tool_playbook.json`'s chronology and `deterministic_default_
chronology` are already shape-agnostic — there is no per-answer-shape
chronology, and none was needed. Discovery-before-search is already
guaranteed generically (`splunk_run_query` only enters the chronology when
`spl_approved=True`). The real, concrete gap was `_mcp_evidence_loop_enabled`
in `pipeline.py`: its discovery-only admission branch was hardcoded to
`answer_mode == "guided_investigation"`, so item 2.1's new discovery-only
grant for `spl_generation_only` (no live-data ask) could never reach the
loop. See the plan's Drift log for the full trail.
"""

from __future__ import annotations

from app.chat.pipeline import _mcp_evidence_loop_enabled
from app.config import settings


def _plan(**overrides) -> dict:
    base = {
        "answer_mode": "live_investigation",
        "discovery_allowed": True,
        "mcp_allowed": False,
        "needs_spl": True,
    }
    base.update(overrides)
    return base


def test_discovery_only_grant_admits_non_guided_families(monkeypatch) -> None:
    plan = _plan()
    assert _mcp_evidence_loop_enabled({"evidence_plan": plan}, plan) is True


def test_rag_only_shape_still_excluded(monkeypatch) -> None:
    plan = _plan(answer_mode="rag_only", needs_spl=False, needs_rag=True)
    assert _mcp_evidence_loop_enabled({"evidence_plan": plan}, plan) is False


def test_guided_investigation_unconditional_admission_unchanged(monkeypatch) -> None:
    plan = _plan(answer_mode="guided_investigation", needs_spl=False)
    assert _mcp_evidence_loop_enabled({"evidence_plan": plan}, plan) is True


def test_neither_grant_stays_excluded(monkeypatch) -> None:
    plan = _plan(discovery_allowed=False, mcp_allowed=False)
    assert _mcp_evidence_loop_enabled({"evidence_plan": plan}, plan) is False


def test_explicit_spl_authoring_stays_review_only_in_mock_mode(monkeypatch) -> None:
    """An explicit SPL artifact request cannot acquire MCP authority from live-data interest."""
    monkeypatch.setattr(settings, "langgraph_orchestration_enabled", False)
    monkeypatch.setattr(settings, "mcp_mode", "mock")
    monkeypatch.setattr(settings, "mcp_global_execution_enabled", True)
    monkeypatch.setattr(settings, "mcp_server_mock_execution_enabled", True)

    from app.api.routes_chat import chat
    from app.schemas.requests import ChatRequest

    response = chat(
        ChatRequest(message="Write SPL to determine who made modifications to any AWS security groups")
    )

    assert response.evidence_plan.get("answer_mode") == "spl_utility_authoring"
    assert response.evidence_plan.get("mcp_allowed") is False
    assert response.evidence_plan.get("discovery_allowed") in (False, None)

    trace = response.control_plane_trace or {}
    mcp_execution = trace.get("mcp_execution") or {}
    assert mcp_execution.get("status") == "skipped"
    if response.execution is not None:
        assert response.execution.executed_spl is None
