"""Tests for ``backend/app/tests/support/canonical_flow.py``."""

from __future__ import annotations

import pytest

from app.chat.canonical_handoff_store import clear_all_handoffs_for_tests
from app.chat.contracts.evidence_plan import EvidencePlan
from app.chat.planning_telemetry import reset_planning_telemetry_for_tests
from app.config import settings
from app.tests.support.canonical_flow import run_canonical_flow


@pytest.fixture(autouse=True)
def _canonical_test_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_curated_enrichment_activation_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_session_context_enabled", True)
    reset_planning_telemetry_for_tests()
    clear_all_handoffs_for_tests()


def test_planned_known_path_commits_resource_plan() -> None:
    result = run_canonical_flow(
        "Investigate failed login spike for user:alice host:APP-01 from 10.0.0.8 in the last 24 hours",
        use_case_id="auth_failed_login_spike",
    )
    assert result.outcome is not None
    assert result.outcome.status == "planned"
    assert result.canonical_planning_input is not None
    assert result.evidence_plan is not None
    EvidencePlan.model_validate(result.evidence_plan)
    assert result.resource_plan is not None
    assert result.committed is True


def test_clarification_produces_typed_outcome_without_evidence_plan() -> None:
    result = run_canonical_flow("What happened with that alert?")
    assert result.outcome is not None
    assert result.outcome.status == "clarification_required"
    assert result.evidence_plan is None
    assert result.resource_plan is None
    assert result.committed is False


def test_t0_reference_resolves_with_committed_plan() -> None:
    result = run_canonical_flow("What is CVE-2026-12345?")
    assert result.outcome is not None
    assert result.outcome.status == "planned"
    assert result.state.get("resolved_tier") == "T0"
    assert result.committed is True
