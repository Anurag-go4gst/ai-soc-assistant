"""Pluggable interfaces between the test harness and the live system.

The harness depends only on these three protocols. Real components (the
LLM planner, the SPL generator, and the Splunk MCP search client) can be
substituted later by passing concrete implementations into ``Runner``.
The harness itself never imports from ``backend.app``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


# Closed enum of skills the routing layer is allowed to emit.
from contracts.skill_enum import SKILL_ENUM


@dataclass(frozen=True)
class RoutingDecision:
    skill: str
    trace_id: str
    raw: dict[str, Any] | None = None


class RoutingClient(Protocol):
    """Routes an analyst query to one of the five skills."""

    def route(self, query: str) -> RoutingDecision:
        ...


class SplGenerator(Protocol):
    """Generates SPL for a routed (query, skill) pair."""

    def generate(self, query: str, skill: str) -> str:
        ...


class SplunkSearch(Protocol):
    """Executes SPL against the COE Splunk and returns result rows."""

    def run(
        self,
        spl: str,
        earliest_time: str | None = None,
        latest_time: str | None = None,
    ) -> list[dict[str, Any]]:
        ...


__all__ = [
    "SKILL_ENUM",
    "RoutingDecision",
    "RoutingClient",
    "SplGenerator",
    "SplunkSearch",
]
