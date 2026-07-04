"""Candidate-constrained advisory prompt (plan 2026-07-04 item 1.2).

When the semantic index already has suggestions, promotion can only land one
of them — so the LLM hop becomes a constrained choice (pick one or abstain)
instead of open-vocabulary extraction. Same output schema; far fewer output
tokens on the slow dev model; candidate registry-valid by construction.
"""

from __future__ import annotations

import json

import pytest

import app.chat.llm_intent_advisor as advisor_mod
from app.chat.llm_intent_advisor import (
    _CONSTRAINED_ABSTAIN,
    _constrained_intent_prompt,
    generate_llm_intent_advisory,
)
from app.config import settings

_CANDIDATES = [
    {"question_ref": "q0.q012", "question": "Which users have excessive failed logins?"},
    {"question_ref": "q0.q046", "question": "Show critical notables with MITRE mapping."},
]


@pytest.fixture(autouse=True)
def _advisor_on(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "ai_soc_llm_intent_advisor_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_llm_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_llm_mode", "local")
    yield


def _run(monkeypatch: pytest.MonkeyPatch, *, match_path: str, semantic: list, reply: dict):
    captured: dict = {}

    def fake_invoke(*, role, user_prompt, max_tokens, timeout_seconds, temperature, allow_failover):
        captured["prompt"] = user_prompt
        captured["max_tokens"] = max_tokens
        return json.dumps(reply), False, "fake_provider"

    monkeypatch.setattr(advisor_mod, "invoke_sidecar_role", fake_invoke)
    import app.coverage.semantic_question_index as sqi

    monkeypatch.setattr(sqi, "semantic_candidates", lambda query, **kw: semantic)
    advisory = generate_llm_intent_advisory(
        "hunt failed logon spikes per account",
        candidate_mappings={"match_path": match_path},
    )
    return advisory, captured


def test_constrained_prompt_lists_refs_and_abstain() -> None:
    prompt = _constrained_intent_prompt(
        query="q", context_block="ctx", candidates=_CANDIDATES
    )
    assert "q0.q012" in prompt and "q0.q046" in prompt
    assert _CONSTRAINED_ABSTAIN in prompt


def test_choice_reply_carries_candidate_and_variant(monkeypatch: pytest.MonkeyPatch) -> None:
    advisory, captured = _run(
        monkeypatch,
        match_path="out_of_registry",
        semantic=_CANDIDATES,
        reply={
            "question_ref_candidate": "q0.q012",
            "confidence_metadata": {"confidence": 0.9},
            "spl_authoring_request": False,
        },
    )
    assert "q0.q012" in captured["prompt"]
    assert captured["max_tokens"] == 300
    assert advisory.question_ref_candidate == "q0.q012"
    assert advisory.confidence_metadata.get("prompt_variant") == "constrained_choice"
    assert advisory.confidence_metadata.get("confidence") == 0.9


def test_abstain_reply_clears_candidate(monkeypatch: pytest.MonkeyPatch) -> None:
    advisory, _ = _run(
        monkeypatch,
        match_path="out_of_registry",
        semantic=_CANDIDATES,
        reply={
            "question_ref_candidate": _CONSTRAINED_ABSTAIN,
            "confidence_metadata": {"confidence": 0.4},
            "spl_authoring_request": False,
        },
    )
    assert advisory.question_ref_candidate in (None, "")
    assert advisory.confidence_metadata.get("prompt_variant") == "constrained_choice"


def test_semantic_empty_uses_legacy_prompt(monkeypatch: pytest.MonkeyPatch) -> None:
    advisory, captured = _run(
        monkeypatch,
        match_path="out_of_registry",
        semantic=[],
        reply={
            "intent_family_candidate": "live_investigation",
            "confidence_metadata": {"confidence": 0.5},
        },
    )
    assert captured["max_tokens"] == 800
    assert _CONSTRAINED_ABSTAIN not in captured["prompt"]
    assert advisory.confidence_metadata.get("prompt_variant") is None


def test_non_out_of_registry_never_constrains(monkeypatch: pytest.MonkeyPatch) -> None:
    advisory, captured = _run(
        monkeypatch,
        match_path="use_case_catalog",
        semantic=_CANDIDATES,
        reply={"confidence_metadata": {"confidence": 0.5}},
    )
    assert captured["max_tokens"] == 800
    assert advisory.confidence_metadata.get("prompt_variant") is None
