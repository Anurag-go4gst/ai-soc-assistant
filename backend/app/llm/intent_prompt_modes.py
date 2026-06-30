"""Table-driven 2C (intent advisory) prompt modes (Phase 1A).

Each mode exports ``build_prompt(query, context_block) -> str`` and
``response_schema() -> dict`` with a small, focused JSON schema. The 8B intent
role is DEGRADED on a large schema, so each mode keeps only the slot keys it
needs. Mode selection is deterministic (``IntentDispatchDecision.prompt_mode``);
these builders are pure and only used on the live path when
``AI_SOC_PIPELINE_DISPATCH_V2_ENABLED`` is on. The legacy monolithic
``build_intent_advisory_prompt`` remains the flag-off default.
"""

from __future__ import annotations

import json
from typing import Any

from app.chat.contracts.intent_dispatch import IntentPromptMode
from app.llm.prompts import AUTHORITY_HIERARCHY_RULES, REVIEW_ONLY_SAFETY_RULES

# Max entity slot keys surfaced per mode (kept small per 8B scorecard).
_SPL_SLOT_KEYS = [
    "index",
    "indexes",
    "sourcetype",
    "host",
    "user",
    "src_ip",
    "dest_ip",
    "event_code",
    "time_window",
    "threshold",
    "lookup",
]
_CATALOGUE_SLOT_KEYS = ["index", "sourcetype", "host", "user", "event_code"]
_CLARIFICATION_SLOT_KEYS = ["host", "user", "event_id"]


def _slot_template(keys: list[str]) -> dict[str, str]:
    return {key: "" for key in keys}


def _authority_block() -> str:
    authority = "Authority hierarchy:\n" + "\n".join(f"- {r}" for r in AUTHORITY_HIERARCHY_RULES)
    safety = "Review-only safety:\n" + "\n".join(f"- {r}" for r in REVIEW_ONLY_SAFETY_RULES)
    return f"{authority}\n\n{safety}"


def _render(query: str, context_block: str, instructions: str, schema: dict[str, Any]) -> str:
    return (
        f"{context_block}\n\n"
        f"Analyst query:\n{query}\n\n"
        f"{instructions}\n\n"
        f"{_authority_block()}\n\n"
        "Return ONE JSON object matching this shape (no markdown):\n"
        f"{json.dumps(schema, indent=2)}"
    )


# --- spl_slot_extraction -------------------------------------------------

def _spl_slot_extraction_schema() -> dict[str, Any]:
    return {
        "entity_slots_candidate": _slot_template(_SPL_SLOT_KEYS),
        "entity_slot_confidence": {},
        "spl_authoring_request": True,
        "requires_source_profile": None,
        "confidence_metadata": {"confidence": 0.0},
    }


def _spl_slot_extraction_prompt(query: str, context_block: str) -> str:
    instructions = (
        "Extract entity_slots_candidate only for values explicitly present or strongly implied "
        "in the analyst query. Do NOT invent indexes, sourcetypes, IPs, hosts, users, lookups, "
        "or time windows. Canonical names: event_id/eventid -> event_code, account/username -> user."
    )
    return _render(query, context_block, instructions, _spl_slot_extraction_schema())


# --- catalogue_promotion -------------------------------------------------

def _catalogue_promotion_schema() -> dict[str, Any]:
    return {
        "intent_family_candidate": "",
        "question_ref_candidate": "",
        "use_case_id_candidate": "",
        "paraphrase_detected": False,
        "entity_slots_candidate": _slot_template(_CATALOGUE_SLOT_KEYS),
        "confidence_metadata": {"confidence": 0.0},
    }


def _catalogue_promotion_prompt(query: str, context_block: str) -> str:
    instructions = (
        "Decide whether this query is a paraphrase of a known catalogue use case. "
        "Propose intent_family_candidate / question_ref_candidate / use_case_id_candidate only "
        "when the match is strong; otherwise leave blank and set paraphrase_detected=false. "
        "Do not invent slot values."
    )
    return _render(query, context_block, instructions, _catalogue_promotion_schema())


# --- clarification -------------------------------------------------------

def _clarification_schema() -> dict[str, Any]:
    return {
        "ambiguity_reasons": [],
        "clarification_draft": None,
        "entity_slots_candidate": _slot_template(_CLARIFICATION_SLOT_KEYS),
        "confidence_metadata": {"confidence": 0.0},
    }


def _clarification_prompt(query: str, context_block: str) -> str:
    instructions = (
        "The query is ambiguous or missing alert context. List ambiguity_reasons and draft a "
        "single clarification question (clarification_draft). Capture only explicit anchor slots "
        "(host/user/event_id). Never assume an alert that was not provided."
    )
    return _render(query, context_block, instructions, _clarification_schema())


_MODE_BUILDERS = {
    IntentPromptMode.spl_slot_extraction: (_spl_slot_extraction_prompt, _spl_slot_extraction_schema),
    IntentPromptMode.catalogue_promotion: (_catalogue_promotion_prompt, _catalogue_promotion_schema),
    IntentPromptMode.clarification: (_clarification_prompt, _clarification_schema),
}


def build_mode_prompt(mode: IntentPromptMode, *, query: str, context_block: str) -> str:
    """Return the mode-specific 2C prompt. ``skip`` has no prompt (no LLM call)."""
    if mode not in _MODE_BUILDERS:
        raise ValueError(f"no prompt builder for intent prompt mode: {mode}")
    return _MODE_BUILDERS[mode][0](query, context_block)


def mode_response_schema(mode: IntentPromptMode) -> dict[str, Any]:
    if mode not in _MODE_BUILDERS:
        raise ValueError(f"no response schema for intent prompt mode: {mode}")
    return _MODE_BUILDERS[mode][1]()
