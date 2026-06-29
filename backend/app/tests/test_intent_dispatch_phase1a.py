"""Phase 1A — intent dispatch decision + table-driven 2C prompt modes."""

from __future__ import annotations

import pytest

from app.chat.contracts.intent_dispatch import (
    IntentPromptMode,
    build_intent_dispatch,
    classify_intent_prompt_mode,
)
from app.chat.llm_intent_advisor import _build_user_prompt
from app.llm.intent_prompt_modes import build_mode_prompt, mode_response_schema
from app.llm.sidecar_clients import build_intent_advisory_prompt


def test_classify_clarification_takes_precedence() -> None:
    mode = classify_intent_prompt_mode(
        routed_skill="spl_generation",
        signals={"explicit_spl_authoring": True, "ambiguous_investigation": True},
        requires_clarification=True,
    )
    assert mode is IntentPromptMode.clarification


def test_classify_spl_slot_extraction_for_authoring() -> None:
    mode = classify_intent_prompt_mode(
        routed_skill="spl_generation", signals={"explicit_spl_authoring": True}
    )
    assert mode is IntentPromptMode.spl_slot_extraction


def test_classify_catalogue_promotion_for_paraphrase() -> None:
    mode = classify_intent_prompt_mode(
        routed_skill="knowledge_recall", signals={"paraphrase_candidate": True}
    )
    assert mode is IntentPromptMode.catalogue_promotion


def test_build_intent_dispatch_call_mirrors_skip() -> None:
    decision = build_intent_dispatch(
        skip_advisory=False, routed_skill="spl_generation", signals={"explicit_spl_authoring": True}
    )
    assert decision.call_2c_llm is True
    assert decision.prompt_mode is IntentPromptMode.spl_slot_extraction


def test_mode_schemas_are_small_and_distinct() -> None:
    spl = mode_response_schema(IntentPromptMode.spl_slot_extraction)
    catalogue = mode_response_schema(IntentPromptMode.catalogue_promotion)
    clar = mode_response_schema(IntentPromptMode.clarification)
    assert "spl_authoring_request" in spl
    assert "intent_family_candidate" in catalogue
    assert "clarification_draft" in clar
    # Catalogue/clarification keep a tighter slot surface than the SPL extractor.
    assert len(spl["entity_slots_candidate"]) > len(catalogue["entity_slots_candidate"])


def test_mode_prompt_contains_query_and_no_markdown_fence() -> None:
    prompt = build_mode_prompt(
        IntentPromptMode.spl_slot_extraction, query="outbound spike from web01", context_block="CTX"
    )
    assert "outbound spike from web01" in prompt
    assert "```" not in prompt


def test_skip_mode_has_no_prompt_builder() -> None:
    with pytest.raises(ValueError):
        build_mode_prompt(IntentPromptMode.skip, query="q", context_block="c")


def test_build_user_prompt_falls_back_to_legacy_when_mode_none() -> None:
    """Flag-off path (prompt_mode=None) must reproduce the legacy monolithic prompt."""
    legacy = build_intent_advisory_prompt(query="q", context_block="CTX")
    via_helper = _build_user_prompt(query="q", context_block="CTX", prompt_mode=None)
    assert via_helper == legacy


def test_build_user_prompt_uses_mode_when_provided() -> None:
    mode_prompt = _build_user_prompt(
        query="q", context_block="CTX", prompt_mode=IntentPromptMode.clarification
    )
    legacy = build_intent_advisory_prompt(query="q", context_block="CTX")
    assert mode_prompt != legacy
    assert "clarification_draft" in mode_prompt
