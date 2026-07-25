"""ResourcePlan creation authority — only plan_evidence_from_canonical may compose/commit."""

from __future__ import annotations

import contextvars
from contextlib import contextmanager
from collections.abc import Iterator
from typing import Any, Callable

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


_TestResourcePlanComposeHook = Callable[..., Any]
_test_resource_plan_compose_hook: _TestResourcePlanComposeHook | None = None


def register_test_resource_plan_compose_hook(
    hook: _TestResourcePlanComposeHook | None,
) -> None:
    """Tests only: attach composed ResourcePlan shadows to legacy ``plan_evidence``."""
    global _test_resource_plan_compose_hook
    _test_resource_plan_compose_hook = hook


def apply_test_resource_plan_shadow_if_allowed(plan: Any, **kwargs: Any) -> Any:
    if not is_test_compose_allowed() or _test_resource_plan_compose_hook is None:
        return plan
    return _test_resource_plan_compose_hook(plan, **kwargs)
