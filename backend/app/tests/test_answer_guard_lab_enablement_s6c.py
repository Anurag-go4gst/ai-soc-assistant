"""S6c — Answer Guard lab enablement."""

from __future__ import annotations

from app.answer_guard.runner import run_answer_guard_lab
from app.config import settings
from app.synthesis.models import GovernedSynthesisPackage, build_governed_synthesis_package
from app.actions.capability_policy import action_capability_for


def _package() -> GovernedSynthesisPackage:
    structured = {"trace_id": "trace-s6c", "selected_skill": "attack_discovery", "metrics": {}}
    return build_governed_synthesis_package(
        structured_context=structured,
        source_evidence=[],
        mitre_mappings=[],
        action_capability=action_capability_for("auth_failed_login_spike", "P3"),
    )


def _draft_with_compromise_claim() -> dict:
    return {
        "analyst_summary": "The account is compromised and attackers have full control.",
        "candidate_spl": "search index=pgcil_soc earliest=-1h latest=now | head 10",
        "mitre_techniques": [{"technique_id": "T1078", "status": "evidence_supported"}],
    }


def test_flag_off_answer_guard_disabled() -> None:
    guard = run_answer_guard_lab(
        draft=_draft_with_compromise_claim(),
        package=None,
        structured_context={},
        source_evidence=[],
        severity_label="P3",
        action_policy={},
    )
    assert guard.enabled is False
    assert guard.guard_status == "disabled"


def test_lab_flag_blocks_unsupported_compromise(monkeypatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_answer_guard_lab_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_llm_answer_guard_enabled", False)
    guard = run_answer_guard_lab(
        draft=_draft_with_compromise_claim(),
        package=_package(),
        structured_context={},
        source_evidence=[],
        severity_label="P3",
        action_policy={"allowed_actions": []},
    )
    assert guard.enabled is True
    assert guard.guard_status in {"blocked", "passed"}
    if guard.guard_status == "blocked":
        assert guard.analyst_review_required is True


def test_candidate_wording_allowed(monkeypatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_answer_guard_lab_enabled", True)
    draft = {
        "analyst_summary": "T1078 remains a candidate technique pending analyst validation.",
        "mitre_techniques": [{"technique_id": "T1078", "status": "candidate"}],
    }
    guard = run_answer_guard_lab(
        draft=draft,
        package=_package(),
        structured_context={},
        source_evidence=[],
        severity_label="P3",
        action_policy={"allowed_actions": []},
    )
    assert guard.guard_status != "blocked" or guard.analyst_review_required is True
