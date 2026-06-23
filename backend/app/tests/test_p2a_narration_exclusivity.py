"""P2-A gate: exactly one narration owner per turn (composer vs lab_runner)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.config import settings
from app.synthesis.governed_answer_composer import composer_is_enabled
from app.synthesis.lab_runner import run_governed_synthesis_lab


def _enable_synthesis(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_llm_final_synthesis_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_llm_live_synthesis_enabled", True)


def test_cp_on_enables_composer_not_lab_narration(monkeypatch: pytest.MonkeyPatch) -> None:
    _enable_synthesis(monkeypatch)
    monkeypatch.setattr(settings, "control_plane_enabled", True)
    assert composer_is_enabled() is True

    narrate = MagicMock()
    monkeypatch.setattr("app.synthesis.lab_runner._narrate_with_progress_and_timeout", narrate)
    monkeypatch.setattr("app.synthesis.lab_runner.build_synthesis_client_from_settings", lambda: MagicMock())

    run_governed_synthesis_lab(
        structured_context={},
        source_evidence=[],
        context_sufficiency={"status": "full_answer", "synthesis_readiness": True},
        mitre_mappings=[],
        action_capability=MagicMock(allowed_actions=[], current_tier=1),
        severity_label="P3",
        spl_validation=None,
        human_review=None,
    )
    narrate.assert_not_called()


def test_cp_off_allows_lab_narration_when_client_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    _enable_synthesis(monkeypatch)
    monkeypatch.setattr(settings, "control_plane_enabled", False)
    assert composer_is_enabled() is False

    narrate = MagicMock(return_value=(None, False))
    monkeypatch.setattr("app.synthesis.lab_runner._narrate_with_progress_and_timeout", narrate)
    monkeypatch.setattr("app.synthesis.lab_runner.build_synthesis_client_from_settings", lambda: MagicMock())

    run_governed_synthesis_lab(
        structured_context={},
        source_evidence=[],
        context_sufficiency={"status": "full_answer", "synthesis_readiness": True},
        mitre_mappings=[],
        action_capability=MagicMock(allowed_actions=[], current_tier=1),
        severity_label="P3",
        spl_validation=None,
        human_review=None,
    )
    narrate.assert_called_once()
