"""ResourcePlan creation authority — only plan_evidence_from_canonical may compose/commit."""

from __future__ import annotations

import contextvars
from contextlib import contextmanager
from typing import Iterator

APPROVED_AUTHORITY = "plan_evidence_from_canonical"
TEST_AUTHORITY = "test"

_authority: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "resource_plan_authority",
    default=None,
)


class ResourcePlanAuthorityViolation(RuntimeError):
    """Raised when ResourcePlan is composed or committed outside the approved authority."""


@contextmanager
def resource_plan_authority(scope: str = APPROVED_AUTHORITY) -> Iterator[None]:
    token = _authority.set(scope)
    try:
        yield
    finally:
        _authority.reset(token)


def assert_resource_plan_authority(*, operation: str) -> None:
    if _authority.get() in {APPROVED_AUTHORITY, TEST_AUTHORITY}:
        return
    raise ResourcePlanAuthorityViolation(
        f"{operation} is restricted to {APPROVED_AUTHORITY}; got {_authority.get()!r}"
    )


def is_test_compose_allowed() -> bool:
    return _authority.get() == TEST_AUTHORITY
