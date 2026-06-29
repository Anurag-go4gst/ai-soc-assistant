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


def build_intent_dispatch(state_slice: dict[str, Any] | None = None) -> IntentDispatchDecision:
    """Phase 0 stub — returns a skip decision.

    Full pre-2C signal logic (routed skill + deterministic signals + settings
    gate) lands in Phase 1A. Returning ``skip`` keeps the flag-off path
    byte-identical: nothing reads this decision until 2C is wired to it.
    """
    return IntentDispatchDecision(
        call_2c_llm=False,
        prompt_mode=IntentPromptMode.skip,
        skip_reasons=["intent_dispatch_stub_phase0"],
    )
