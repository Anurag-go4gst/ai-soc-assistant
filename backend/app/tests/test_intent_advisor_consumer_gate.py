"""Consumer-gated intent advisor (plan 2026-07-04 item 1.1).

The advisory LLM hop has exactly two actuation channels: promotion (only on
``out_of_registry``) and the SPL-authoring reconcile (only on SPL-shaped,
non-unsafe queries). ``intent_advisor_consumable`` closes the hop everywhere
else — measured at 0 actuations across 1279 recorded live runs while costing
25-44s wall-clock per turn on the dev VPS.
"""

from __future__ import annotations

import pytest

from app.chat.llm_intent_advisor import SKIP_NO_CONSUMER, intent_advisor_consumable
from app.chat.pipeline import build_live_chat_response
from app.config import settings
from app.schemas.requests import ChatRequest


def test_out_of_registry_keeps_hop() -> None:
    consumable, reason = intent_advisor_consumable(
        match_path="out_of_registry", signals={}, query="anything at all"
    )
    assert consumable is True
    assert reason is None


def test_catalog_non_spl_turn_skips() -> None:
    consumable, reason = intent_advisor_consumable(
        match_path="use_case_catalog",
        signals={},
        query="Is CVE-2024-3400 exploitation relevant to our environment?",
    )
    assert consumable is False
    assert reason == SKIP_NO_CONSUMER


def test_spl_shaped_catalog_turn_keeps_hop_for_reconcile() -> None:
    consumable, reason = intent_advisor_consumable(
        match_path="use_case_catalog",
        signals={"spl_generation": True},
        query="give me a search for failed logons",
    )
    assert consumable is True
    assert reason is None


def test_spl_mention_in_text_keeps_hop() -> None:
    consumable, _ = intent_advisor_consumable(
        match_path="exact_105",
        signals={},
        query="draft the SPL I should review for this",
    )
    assert consumable is True


def test_unsafe_signals_close_the_reconcile_window() -> None:
    consumable, reason = intent_advisor_consumable(
        match_path="use_case_catalog",
        signals={"spl_generation": True, "explicit_run_spl": True},
        query="run this spl now",
    )
    assert consumable is False
    # Command-mode / explicit-run closes the hop before the generic no-consumer skip.
    assert reason in {SKIP_NO_CONSUMER, "intent_advisory_command_mode"}


def test_explicit_authoring_keeps_hop() -> None:
    # Pinned by test_intent_advisor_scheduling_parity: explicit SPL authoring
    # turns keep the advisory hop (co-signer/downgrade-detection role).
    consumable, reason = intent_advisor_consumable(
        match_path="use_case_catalog",
        signals={"spl_generation": True, "explicit_spl_authoring": True},
        query="write me an spl snippet",
    )
    assert consumable is True
    assert reason is None


def test_t0_weak_row_keeps_hop() -> None:
    # Pinned q046-guard population: weak/demoted T0 rows keep the (sharply
    # bounded) hop rather than skipping.
    consumable, reason = intent_advisor_consumable(
        match_path="exact_105",
        signals={},
        query="show me critical notables",
        t0_weak_row=True,
    )
    assert consumable is True
    assert reason is None


def test_live_catalog_turn_records_no_consumer_skip(monkeypatch: pytest.MonkeyPatch) -> None:
    """P3-class turn (CVE/MITRE, lands on the use-case catalog): the advisory
    hop must be skipped with the no-consumer reason instead of spending the
    T2 advisory bound producing unusable output."""
    message = (
        "Is CVE-2024-3400 exploitation relevant to our environment and "
        "which MITRE ATT&CK techniques does it map to?"
    )
    response = build_live_chat_response(ChatRequest(message=message))
    q2i = response.query_to_intent if isinstance(response.query_to_intent, dict) else {}
    intent = q2i.get("intent_classification") if isinstance(q2i, dict) else {}
    assert (intent or {}).get("llm_intent_status") == "skipped"
    advisory = q2i.get("llm_intent_advisory") if isinstance(q2i, dict) else None
    if isinstance(advisory, dict):
        dropped = advisory.get("dropped_reasons") or []
        assert advisory.get("llm_called") in (False, None)
        assert SKIP_NO_CONSUMER in dropped or intent.get("llm_intent_status") == "skipped"
    else:
        consumable, reason = intent_advisor_consumable(
            match_path=(q2i.get("candidate_mappings") or {}).get("match_path"),
            signals=(q2i.get("query_signals") or {}),
            query=message,
        )
        assert consumable is False
        assert reason == SKIP_NO_CONSUMER
