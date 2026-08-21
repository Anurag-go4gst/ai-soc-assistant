"""Per-hop LLM call context for timing attribution (workstream E).

Call purpose is set by orchestration layers before FailoverChatClient or sidecar
wrappers run. Never carries prompt text or credentials.

Executor submissions must use ``run_with_call_context`` so purpose propagates.
"""

from __future__ import annotations

import contextvars
from collections.abc import Callable
from contextlib import contextmanager
from typing import Iterator, TypeVar

_CALL_PURPOSE: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "llm_call_purpose",
    default=None,
)

# Bounded purpose labels exposed in attribution_v2 (no free-form prose).
CALL_PURPOSE_ROUTING = "routing"
CALL_PURPOSE_SIDECAR = "sidecar"
CALL_PURPOSE_MITRE = "mitre"
CALL_PURPOSE_SUFFICIENCY = "sufficiency"
CALL_PURPOSE_SYNTHESIS_LAB = "synthesis_lab"
CALL_PURPOSE_COMPOSER = "composer"
CALL_PURPOSE_SHADOW = "shadow"
CALL_PURPOSE_SPL = "spl"
CALL_PURPOSE_OTHER = "other"

_ROLE_TO_CALL_PURPOSE: dict[str, str] = {
    "intent_shadow_classifier": CALL_PURPOSE_ROUTING,
    "shape_advisor": CALL_PURPOSE_SHADOW,
    "missing_evidence_reasoner": CALL_PURPOSE_SUFFICIENCY,
    "mitre_reasoner": CALL_PURPOSE_MITRE,
    "mitre_candidate_mapper": CALL_PURPOSE_MITRE,
    "risk_rationale_reasoner": CALL_PURPOSE_MITRE,
    "route_plan_candidate_generator": CALL_PURPOSE_SHADOW,
    "governed_composer": CALL_PURPOSE_COMPOSER,
    "evidence_observer": CALL_PURPOSE_SHADOW,
    "spl_advisory_generator": CALL_PURPOSE_SPL,
    "template_match_semantic_assist": CALL_PURPOSE_SPL,
    "template_render_parameter_assist": CALL_PURPOSE_SPL,
    "guided_investigation_plan_proposer": CALL_PURPOSE_SHADOW,
    "investigation_planner": CALL_PURPOSE_SIDECAR,
    "pattern_reasoner": CALL_PURPOSE_MITRE,
}

T = TypeVar("T")


def call_purpose_for_role(role: str | None) -> str:
    if not role:
        return CALL_PURPOSE_OTHER
    return _ROLE_TO_CALL_PURPOSE.get(role.strip(), CALL_PURPOSE_SIDECAR)


def get_call_purpose() -> str | None:
    return _CALL_PURPOSE.get()


@contextmanager
def llm_call_purpose_scope(purpose: str) -> Iterator[None]:
    token = _CALL_PURPOSE.set(purpose)
    try:
        yield
    finally:
        _CALL_PURPOSE.reset(token)


def run_with_call_context(func: Callable[[], T]) -> T:
    """Run ``func`` preserving current ContextVar state (e.g. in executors)."""
    ctx = contextvars.copy_context()
    return ctx.run(func)
