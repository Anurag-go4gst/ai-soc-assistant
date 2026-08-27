"""OPTIONAL_PHASE_S S6 — bounded optimization LLM role."""

from __future__ import annotations

import json

import pytest

from app.config import settings
from app.spl.spl_optimization_llm import apply_optimization_llm

_V1 = (
    "search index=<idx> sourcetype=<st> earliest=-24h latest=now "
    "action=fail | stats count by src_ip | head 100"
)


def test_skipped_when_classification_not_required() -> None:
    result = apply_optimization_llm(_V1, classification="PASS")
    assert result.outcome == "SKIPPED"
    assert result.skip_reason


def test_skipped_when_flag_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_spl_optimization_llm_enabled", False)
    result = apply_optimization_llm(_V1, classification="OPTIMIZATION_LLM_REQUIRED")
    assert result.outcome == "SKIPPED"
    assert result.skip_reason == "optimization_llm_disabled"


def test_no_safe_optimization_from_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_spl_optimization_llm_enabled", True)

    def _provider() -> str:
        return json.dumps({"status": "NO_SAFE_OPTIMIZATION", "candidate_spl": _V1})

    result = apply_optimization_llm(
        _V1,
        classification="OPTIMIZATION_LLM_REQUIRED",
        llm_raw_output_provider=_provider,
    )
    assert result.outcome == "NO_SAFE_OPTIMIZATION"
    assert result.candidate_spl_v2 is None


def test_optimized_passes_guard(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_spl_optimization_llm_enabled", True)
    v2 = (
        "search index=<idx> sourcetype=<st> earliest=-24h latest=now action=fail "
        "| fields src_ip action | stats count by src_ip | head 100"
    )

    def _provider() -> str:
        return json.dumps({"status": "OPTIMIZED", "candidate_spl": v2})

    result = apply_optimization_llm(
        _V1,
        classification="OPTIMIZATION_LLM_REQUIRED",
        llm_raw_output_provider=_provider,
    )
    assert result.outcome == "OPTIMIZED"
    assert result.candidate_spl_v2 == v2


def test_at_most_one_call_enforced_by_api(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_spl_optimization_llm_enabled", True)
    calls = 0

    def _provider() -> str:
        nonlocal calls
        calls += 1
        return json.dumps({"status": "NO_SAFE_OPTIMIZATION", "candidate_spl": _V1})

    apply_optimization_llm(
        _V1,
        classification="OPTIMIZATION_LLM_REQUIRED",
        llm_raw_output_provider=_provider,
    )
    assert calls == 1
