"""Test helpers for legacy evidence-planning and committed ResourcePlan seams."""

from __future__ import annotations

from typing import Any


def with_legacy_langgraph_harness(state: dict[str, Any]) -> dict[str, Any]:
    """Allow graph_node_evidence_planning first entry under canonical mode."""
    return {**state, "legacy_langgraph_harness": True}


def with_committed_resource_plan(
    state: dict[str, Any],
    *,
    steps: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Mark evidence_plan.resource_plan as committed for canonical dispatch/execution."""
    evidence = dict(state.get("evidence_plan") or {})
    resource_plan = dict(evidence.get("resource_plan") or {})
    if steps is not None:
        resource_plan["steps"] = steps
    provenance = dict(resource_plan.get("provenance") or {})
    provenance["committed"] = True
    resource_plan["provenance"] = provenance
    resource_plan.setdefault("plan_source", "deterministic")
    evidence["resource_plan"] = resource_plan
    return {**state, "evidence_plan": evidence}
