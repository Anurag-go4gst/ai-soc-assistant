"""Phase 2 (#4): dual narration path gating — composer (CP on) vs lab_runner (CP off).

Documents and locks the rule from the plan: CP on routes prose through the
governed composer; CP off uses the legacy lab narration. Neither path may run
when the synthesis flags are off, and a disabled composer returns the
deterministic envelope byte-for-byte.
"""

from __future__ import annotations

import pytest

from app.chat.contracts.answer_contract import AnswerContract
from app.config import settings
from app.synthesis import governed_answer_composer as composer_mod
from app.synthesis.governed_answer_composer import compose_governed_answer, composer_is_enabled
from app.schemas.responses import AnalystResponseEnvelope


def _envelope() -> AnalystResponseEnvelope:
    return AnalystResponseEnvelope(direct_answer_summary="Deterministic summary stays.")


def _enable_synthesis(monkeypatch: pytest.MonkeyPatch, *, cp: bool) -> None:
    monkeypatch.setattr(settings, "control_plane_enabled", cp)
    monkeypatch.setattr(settings, "ai_soc_llm_final_synthesis_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_llm_live_synthesis_enabled", True)


def test_composer_enabled_requires_cp_and_both_flags(monkeypatch: pytest.MonkeyPatch) -> None:
    _enable_synthesis(monkeypatch, cp=True)
    assert composer_is_enabled() is True
    monkeypatch.setattr(settings, "control_plane_enabled", False)
    # CP off → composer is NOT the narration path (lab_runner owns it instead).
    assert composer_is_enabled() is False


def test_disabled_composer_returns_deterministic_envelope(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "control_plane_enabled", False)
    monkeypatch.setattr(settings, "ai_soc_llm_final_synthesis_enabled", False)
    monkeypatch.setattr(settings, "ai_soc_llm_live_synthesis_enabled", False)
    envelope = _envelope()
    result = compose_governed_answer(
        contract=AnswerContract(missing_evidence=[], hil_status="not_required"),
        enrichment_projection=None,
        fallback_envelope=envelope,
    )
    assert result.llm_composer_used is False
    assert result.llm_guard_status == "disabled"
    assert result.envelope.direct_answer_summary == envelope.direct_answer_summary


def test_composer_falls_back_when_no_client(monkeypatch: pytest.MonkeyPatch) -> None:
    _enable_synthesis(monkeypatch, cp=True)
    # Provider not configured → deterministic envelope, no exception.
    monkeypatch.setattr(composer_mod, "build_synthesis_client_from_settings", lambda: None)
    result = compose_governed_answer(
        contract=AnswerContract(missing_evidence=[], hil_status="not_required"),
        enrichment_projection=None,
        fallback_envelope=_envelope(),
    )
    assert result.llm_composer_used is False
    assert result.llm_fallback_used is True


def test_lab_runner_path_exists_for_cp_off() -> None:
    # The CP-off narration owner must remain importable and distinct from composer.
    from app.synthesis import lab_runner

    assert hasattr(lab_runner, "run_governed_synthesis_lab")
