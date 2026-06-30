from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


class IntentPromptMode(str, Enum):
    """Table-driven 2C prompt mode (Phase 1A)."""

    skip = "skip"
    spl_slot_extraction = "spl_slot_extraction"
    catalogue_promotion = "catalogue_promotion"
    clarification = "clarification"


class IntentDispatchDecision(BaseModel):
    """Stage-1 dispatch authority — owns whether/how Node 2C runs.

    Built from ``state["routed"]`` (deterministic skill) + ``query_understanding``
    deterministic signals, at the top of ``graph_node_query_to_intent`` BEFORE the
    2C LLM call. It must never read ``RouteContract`` or adjudicated skill (those
    nodes run after 2C).
    """

    schema_version: Literal["v1"] = "v1"
    call_2c_llm: bool = False
    prompt_mode: IntentPromptMode = IntentPromptMode.skip
    skip_reasons: list[str] = Field(default_factory=list)
    dispatch_reasons: list[str] = Field(default_factory=list)
    authority_holder: str = "intent_dispatch_v1"


def classify_intent_prompt_mode(
    *,
    routed_skill: str | None,
    signals: dict[str, Any] | None,
    requires_clarification: bool = False,
) -> IntentPromptMode:
    """Deterministic 2C prompt-mode selection (Phase 1A).

    Precedence: clarification > spl_slot_extraction > catalogue_promotion. The
    default for live investigation that still needs slots is spl_slot_extraction.
    """
    sig = signals or {}
    if requires_clarification or bool(sig.get("ambiguous_investigation")):
        return IntentPromptMode.clarification
    if (
        bool(sig.get("explicit_spl_authoring"))
        or bool(sig.get("spl_authoring_request"))
        or bool(sig.get("universal_spl_utility"))
        or routed_skill == "spl_generation"
    ):
        return IntentPromptMode.spl_slot_extraction
    if bool(sig.get("paraphrase_candidate")) or bool(sig.get("near_catalogue_low_confidence")):
        return IntentPromptMode.catalogue_promotion
    return IntentPromptMode.spl_slot_extraction


def build_intent_dispatch(
    *,
    skip_advisory: bool,
    skip_reason: str | None = None,
    routed_skill: str | None = None,
    signals: dict[str, Any] | None = None,
    requires_clarification: bool = False,
) -> IntentDispatchDecision:
    """Stage-1 decision built from the deterministic skip outcome + routed signals.

    ``call_2c_llm`` mirrors the node's deterministic skip decision exactly
    (``not skip_advisory``) so flag-on gating introduces no divergence — the only
    flag-on behavior change is the mode-specific prompt selected for the call.
    """
    if skip_advisory:
        return IntentDispatchDecision(
            call_2c_llm=False,
            prompt_mode=IntentPromptMode.skip,
            skip_reasons=[skip_reason] if skip_reason else [],
        )
    mode = classify_intent_prompt_mode(
        routed_skill=routed_skill,
        signals=signals,
        requires_clarification=requires_clarification,
    )
    return IntentDispatchDecision(
        call_2c_llm=True,
        prompt_mode=mode,
        dispatch_reasons=[f"intent_prompt_mode:{mode.value}"],
    )
