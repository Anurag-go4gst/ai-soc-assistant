"""Contracts for registering an Experience Center agent workflow profile."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class AgentProfile:
    """One registered agent-workflow scenario (S4 is the reference implementation)."""

    scenario_id: str
    default_agent_state: Callable[[], dict[str, Any]]
    init_session: Callable[[str, str, str], dict[str, Any]]
    handle_follow_up: Callable[..., dict[str, Any] | None]
    build_workflow: Callable[..., dict[str, Any]]
    followups_for_agent_mode: Callable[[str, list[str] | None], list[Any]]
    plan_preread_follow_ups: tuple[str, ...] = ()
    finalize_remediation_after_apply: Callable[..., dict[str, Any]] | None = None
    inline_progress_follow_ups: frozenset[str] = field(
        default_factory=lambda: frozenset(
            {
                "run_investigation",
                "approve_investigation_vuln_scan",
                "skip_investigation_vuln_scan",
                "create_remediation_plan",
                "run_remediation",
            }
        )
    )
    conversational_follow_ups: frozenset[str] = field(default_factory=frozenset)
