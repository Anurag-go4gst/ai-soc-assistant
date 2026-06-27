"""Batch D — final synthesis narration skip uses T0 authority-readiness policy."""

from __future__ import annotations

import pytest

from app.actions.capability_policy import action_capability_for
from app.coverage.promotion_lifecycle import AUTHORITY_READY_EFFECTIVE, DEMOTED_THIS_TURN, effective_promotion_status
from app.synthesis.lab_runner import run_governed_synthesis_lab
from app.tests.test_p6_guarded_synthesis_lab import _source_evidence, _structured_context, _sufficiency_ready


class _StubClient:
    def __init__(self) -> None:
        self.calls = 0

    def generate(self, *, system_prompt: str, user_prompt: str, max_tokens: int, temperature: float):
        self.calls += 1
        from app.llm.clients import ChatResult
        return ChatResult(text="Narrated prose only.", model="stub", latency_ms=1, usage={})


def _run(monkeypatch: pytest.MonkeyPatch, *, lifecycle: dict, client: _StubClient):
    for attr, value in (
        ("ai_soc_llm_final_synthesis_enabled", True),
        ("ai_soc_llm_live_synthesis_enabled", True),
        ("ai_soc_llm_require_context_sufficiency", True),
        ("control_plane_enabled", False),
    ):
        monkeypatch.setattr(f"app.synthesis.lab_runner.settings.{attr}", value)
    return run_governed_synthesis_lab(
        structured_context=_structured_context(),
        source_evidence=_source_evidence(),
        context_sufficiency=_sufficiency_ready(),
        mitre_mappings=[],
        action_capability=action_capability_for("attack_discovery", "P2 - High"),
        severity_label="P2 - High",
        spl_validation=None,
        human_review=None,
        synthesis_client=client,
        match_path="exact_105_question",
        promotion_lifecycle_summary=lifecycle,
    )


def test_authority_ready_t0_skips_final_synthesis_narration(monkeypatch: pytest.MonkeyPatch) -> None:
    lifecycle = effective_promotion_status(
        stored_promotion_status="in_manifest",
        row_authority_summary={
            "s3_authority_ready": True,
            "row_authority_status": "exact_known_authority_ready",
        },
    )
    assert lifecycle["effective_promotion_status"] == AUTHORITY_READY_EFFECTIVE
    client = _StubClient()
    result = _run(monkeypatch, lifecycle=lifecycle, client=client)
    assert client.calls == 0
    assert result.status.provider == "deterministic_lab"
    assert "skipped" in (result.status.reason or "").lower()
    assert result.draft.get("final_synthesis_skip_reason") == "deterministic_exact_match_t0"


def test_weak_demoted_row_does_not_skip_final_synthesis(monkeypatch: pytest.MonkeyPatch) -> None:
    lifecycle = effective_promotion_status(
        stored_promotion_status="in_manifest",
        row_authority_summary={
            "s3_authority_ready": False,
            "row_authority_status": "exact_known_weak_needs_enrichment",
        },
    )
    assert lifecycle["effective_promotion_status"] == DEMOTED_THIS_TURN
    client = _StubClient()
    result = _run(monkeypatch, lifecycle=lifecycle, client=client)
    assert client.calls == 1
    assert result.status.provider == "local_model"
    assert result.draft.get("final_synthesis_skip_reason") is None
