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


def test_intent_dispatch_is_a_declared_state_channel() -> None:
    """Regression: intent_dispatch must be a ChatPipelineState channel.

    LangGraph's StateGraph drops keys not declared on the state schema, so an
    undeclared intent_dispatch silently vanished from control_plane_trace on the
    LangGraph path (imperative path kept it). Declaring the channel keeps Stage-1
    dispatch observable on both orchestrations.
    """
    from app.chat.pipeline import ChatPipelineState

    assert "intent_dispatch" in ChatPipelineState.__annotations__


def test_intent_advisory_coercion_accepts_8b_type_quirks() -> None:
    """8B emits bool-as-string + confidence-as-word; coercion must rescue them.

    The JSON extractor parses the object; strict pydantic then dropped these as
    schema_invalid. Coercion normalizes the known quirks so a well-formed advisory
    is accepted (still non-authoritative) instead of lost.
    """
    from app.chat.contracts.llm_intent_advisory import LLMIntentAdvisory
    from app.chat.llm_intent_advisor import _coerce_intent_advisory_payload

    quirk = {
        "spl_authoring_request": "true",
        "paraphrase_detected": "no",
        "requires_source_profile": "false",
        "entity_slots_candidate": {"user": "admin"},
        "entity_slot_confidence": {"user": "high"},
        "extra_unknown": "ignored",
    }
    # Strict validate on the raw quirk fails (the schema_invalid we observed live).
    import pytest as _pytest

    with _pytest.raises(Exception):
        LLMIntentAdvisory.model_validate(quirk)

    payload, warnings = _coerce_intent_advisory_payload(quirk)
    adv = LLMIntentAdvisory.model_validate(payload)
    assert adv.spl_authoring_request is True
    assert adv.paraphrase_detected is False
    assert adv.requires_source_profile is False
    assert adv.entity_slot_confidence == {"user": 0.9}
    assert any("coerced" in w for w in warnings)
