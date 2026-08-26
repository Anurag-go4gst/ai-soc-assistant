"""Eval-only prompt arm selection.

Production hops default to ACTIVE. The candidate arm is selected only inside the
P8 A/B runner via ``use_prompt_eval_arm('candidate')``. Nothing in the request
path sets this.

Live T4/planner hops run inside a ThreadPoolExecutor, so the eval arm is also
stored in process-wide thread-safe state for the duration of the context
manager. Production never enters that context manager.
"""

from __future__ import annotations

import threading
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Literal

PromptEvalArm = Literal["active", "candidate"]

_PROMPT_EVAL_ARM: ContextVar[PromptEvalArm] = ContextVar("ai_soc_prompt_eval_arm", default="active")
_ARM_LOCK = threading.Lock()
_PROCESS_ARM: PromptEvalArm | None = None


def prompt_eval_arm() -> PromptEvalArm:
    with _ARM_LOCK:
        if _PROCESS_ARM is not None:
            return _PROCESS_ARM
    return _PROMPT_EVAL_ARM.get()


@contextmanager
def use_prompt_eval_arm(arm: PromptEvalArm) -> Iterator[None]:
    if arm not in {"active", "candidate"}:
        raise ValueError(f"unknown prompt eval arm: {arm}")
    global _PROCESS_ARM
    token = _PROMPT_EVAL_ARM.set(arm)
    with _ARM_LOCK:
        previous = _PROCESS_ARM
        _PROCESS_ARM = arm
    try:
        yield
    finally:
        with _ARM_LOCK:
            _PROCESS_ARM = previous
        _PROMPT_EVAL_ARM.reset(token)
