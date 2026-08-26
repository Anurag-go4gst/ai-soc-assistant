"""Eval-only prompt arm selection.

Production hops default to ACTIVE. The candidate arm is selected only inside the
P8 A/B runner via ``use_prompt_eval_arm('candidate')``. Nothing in the request
path sets this.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Literal

PromptEvalArm = Literal["active", "candidate"]

_PROMPT_EVAL_ARM: ContextVar[PromptEvalArm] = ContextVar("ai_soc_prompt_eval_arm", default="active")


def prompt_eval_arm() -> PromptEvalArm:
    return _PROMPT_EVAL_ARM.get()


@contextmanager
def use_prompt_eval_arm(arm: PromptEvalArm) -> Iterator[None]:
    if arm not in {"active", "candidate"}:
        raise ValueError(f"unknown prompt eval arm: {arm}")
    token = _PROMPT_EVAL_ARM.set(arm)
    try:
        yield
    finally:
        _PROMPT_EVAL_ARM.reset(token)
