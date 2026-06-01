from __future__ import annotations

import pytest

from app.actions.capability_policy import action_capability_for
from app.answer_guard.runner import run_answer_guard_lab
from app.api.routes_chat import chat
from app.config import settings
from app.schemas.requests import ChatRequest
from app.synthesis.lab_runner import run_governed_synthesis_lab
from app.synthesis.models import build_governed_synthesis_package
from app.tests.test_route_plan_stage3k_r2 import _patch_common_chat_dependencies


def _structured_context() -> dict:
    return {
        "trace_id": "trace-p6",
        "selected_skill": "attack_discovery",
        "metrics": {"collected_evidence_count": 1, "total_result_count": 2},
        "missing_evidence": ["success_after_failure"],
        "structured_facts": [
            {
                "fact_id": "fact-001",
                "statement": "Repeated failed authentication observed from multiple source IPs.",
                "source_refs": ["ev-1"],
            }
        ],
    }


def _source_evidence() -> list[dict]:
    return [
        {
            "evidence_id": "ev-1",
            "source_type": "splunk_mcp",
            "collection_status": "collected",
            "preview_rows": [
                {"host": "APP-01", "src": "10.0.0.1", "failed_logins": 40, "distinct_users": 6},
            ],
        }
    ]


def _sufficiency_ready() -> dict:
    return {
        "status": "partial_answer",
        "synthesis_readiness": True,
        "synthesis_allowed": False,
        "reasons": ["evidence_collected"],
        "missing_evidence": [],
        "human_review": None,
    }


def _patch_synthesis_flags(monkeypatch: pytest.MonkeyPatch, *, synthesis: bool, guard: bool) -> None:
    for target in ("app.config.settings", "app.chat.pipeline.settings", "app.synthesis.lab_runner.settings", "app.answer_guard.runner.settings"):
        monkeypatch.setattr(f"{target}.ai_soc_llm_final_synthesis_enabled", synthesis)
        monkeypatch.setattr(f"{target}.ai_soc_llm_answer_guard_enabled", guard)


def test_p6_flags_off_parity_with_prior_chat_surface(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_synthesis_flags(monkeypatch, synthesis=False, guard=False)
    _patch_common_chat_dependencies(monkeypatch, skill="attack_discovery")

    response = chat(ChatRequest(message="Top source IPs by failed login count in the last hour."))

    assert response.synthesis_status is not None
    assert response.synthesis_status.enabled is False
    assert response.synthesis_status.status == "disabled"
    assert response.answer_guard is not None
    assert response.answer_guard.enabled is False
    assert response.analyst_summary is None
    assert response.message == "SPL validation complete. MCP execution is disabled."


def test_p6_synthesis_on_produces_deterministic_summary_when_ready(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_synthesis_flags(monkeypatch, synthesis=True, guard=False)
    _patch_common_chat_dependencies(monkeypatch, skill="attack_discovery")

    response = chat(ChatRequest(message="Top source IPs by failed login count in the last hour."))

    assert response.synthesis_status is not None
    assert response.synthesis_status.enabled is True
    assert response.synthesis_status.status in {"completed", "blocked"}
    if response.synthesis_status.status == "completed":
        assert response.analyst_summary
        assert "MITRE" in response.analyst_summary or "authentication" in response.analyst_summary.lower()
        assert response.context_sufficiency is not None
        assert response.context_sufficiency.synthesis_allowed is True


def test_p6_answer_guard_blocks_aggregate_overclaim(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_synthesis_flags(monkeypatch, synthesis=True, guard=True)
    package = build_governed_synthesis_package(
        structured_context=_structured_context(),
        source_evidence=_source_evidence(),
        mitre_mappings=[],
        action_capability=action_capability_for(None, "P3 Medium"),
    )
    draft = {
        "analyst_summary": "14 targeted accounts were observed across the environment.",
        "affected_accounts_count": 14,
        "mitre_mappings": [],
        "splunk_results_table": _source_evidence()[0]["preview_rows"],
        "execution_eligible": False,
    }
    guard = run_answer_guard_lab(
        draft=draft,
        package=package,
        structured_context=_structured_context(),
        source_evidence=_source_evidence(),
        severity_label="P3 Medium",
        action_policy={"allowed_actions": ["review_logs"], "current_tier": 1},
    )
    assert guard.enabled is True
    assert guard.guard_status == "blocked"
    assert "guard.aggregate_overclaim" in guard.failed_checks


def test_synthesis_lab_blocked_when_sufficiency_not_ready(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_llm_final_synthesis_enabled", True)
    result = run_governed_synthesis_lab(
        structured_context=_structured_context(),
        source_evidence=_source_evidence(),
        context_sufficiency={
            "status": "insufficient_evidence",
            "synthesis_readiness": False,
            "synthesis_allowed": False,
            "reasons": [],
            "missing_evidence": [],
            "human_review": None,
        },
        mitre_mappings=[],
        action_capability=action_capability_for(None, "P3 Medium"),
        severity_label="P3 Medium",
        spl_validation={"approved": True, "normalized_spl": "index=okta | stats count"},
        human_review=None,
    )
    assert result.status.enabled is True
    assert result.status.status == "blocked"
    assert result.analyst_summary is None


def test_synthesis_lab_completes_when_ready(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_llm_final_synthesis_enabled", True)
    result = run_governed_synthesis_lab(
        structured_context=_structured_context(),
        source_evidence=_source_evidence(),
        context_sufficiency=_sufficiency_ready(),
        mitre_mappings=[],
        action_capability=action_capability_for(None, "P3 Medium"),
        severity_label="P3 Medium",
        spl_validation={"approved": True, "normalized_spl": "index=okta | stats count"},
        human_review=None,
    )
    assert result.status.status == "completed"
    assert result.draft is not None
    assert result.draft.get("execution_eligible") is False
    assert result.analyst_summary
