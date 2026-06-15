"""Deterministic review of an MCP tool-call chronology.

Flow this implements (planning only — no live MCP I/O):

    LLM proposes a tool chronology  →  this module reviews/approves it against
    ``mcp_tool_playbook.json``  →  approved plan is what would run.
    If the LLM proposal is missing or fully rejected, the deterministic default
    chronology is used instead (fallback).

The LLM is advisory: it can only *narrow/reorder* within the governed playbook.
It can never introduce a blocked/conditional tool, bypass RBAC, or open the
execution gate. Deterministic policy always wins; execution stays gated by
``MCP_GLOBAL_EXECUTION_ENABLED`` + server flags + HIL/COE elsewhere.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

_PLAYBOOK_PATH = Path(__file__).with_name("mcp_tool_playbook.json")

DecisionSource = Literal[
    "deterministic_default",
    "llm_reviewed",
    "llm_reviewed_adjusted",
    "deterministic_fallback",
]


@dataclass(frozen=True)
class DroppedStep:
    tool: str
    reason: str


@dataclass(frozen=True)
class ChronologyPlan:
    approved_tools: list[str]
    decision_source: DecisionSource
    dropped: list[DroppedStep] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "approved_tools": list(self.approved_tools),
            "decision_source": self.decision_source,
            "dropped": [{"tool": d.tool, "reason": d.reason} for d in self.dropped],
            "warnings": list(self.warnings),
        }


@lru_cache(maxsize=1)
def load_playbook() -> dict[str, Any]:
    return json.loads(_PLAYBOOK_PATH.read_text(encoding="utf-8"))


def deterministic_default_chronology(
    *,
    target_index: str | None = None,
    include_knowledge_objects: bool = True,
    spl_approved: bool = False,
) -> list[str]:
    """The governed baseline order, pruned to the current context."""
    playbook = load_playbook()
    tools: dict[str, Any] = playbook["tools"]
    sequence: list[str] = []
    for name in playbook["default_chronology"]:
        spec = tools.get(name, {})
        if spec.get("blocked"):
            continue
        if name == "splunk_get_index_info" and not target_index:
            continue
        if name == "splunk_get_knowledge_objects" and not include_knowledge_objects:
            continue
        if name == "splunk_run_query" and not spl_approved:
            # The search hop only enters the plan once SPL is approved/normalized.
            continue
        sequence.append(name)
    return sequence


def review_proposed_tool_chronology(
    proposed: list[str] | None,
    *,
    target_index: str | None = None,
    include_knowledge_objects: bool = True,
    spl_approved: bool = False,
    rbac_role: str | None = None,
) -> ChronologyPlan:
    """Validate an LLM-proposed chronology; fall back to the deterministic plan.

    The approved tool set is always re-ordered to the canonical playbook order
    (deterministic wins on sequencing). The LLM only influences *which* optional
    discovery steps are included.
    """
    playbook = load_playbook()
    tools: dict[str, Any] = playbook["tools"]
    default = deterministic_default_chronology(
        target_index=target_index,
        include_knowledge_objects=include_knowledge_objects,
        spl_approved=spl_approved,
    )

    if not proposed:
        return ChronologyPlan(approved_tools=default, decision_source="deterministic_default")

    accepted: list[str] = []
    dropped: list[DroppedStep] = []
    warnings: list[str] = []
    seen: set[str] = set()

    for raw in proposed:
        tool = str(raw).strip()
        if tool in seen:
            dropped.append(DroppedStep(tool, "duplicate"))
            continue
        seen.add(tool)
        spec = tools.get(tool)
        if spec is None:
            dropped.append(DroppedStep(tool, "unknown_tool"))
            continue
        if spec.get("blocked"):
            dropped.append(DroppedStep(tool, spec.get("blocked_reason", "blocked")))
            continue
        if tool == "splunk_run_query" and not spl_approved:
            dropped.append(DroppedStep(tool, "approved_normalized_spl_missing"))
            continue
        if tool == "splunk_get_index_info" and not target_index:
            dropped.append(DroppedStep(tool, "no_target_index"))
            continue
        if rbac_role is not None:
            allowed_roles = spec.get("rbac_roles")
            if allowed_roles and rbac_role not in allowed_roles:
                dropped.append(DroppedStep(tool, f"rbac_denied:{rbac_role}"))
                continue
        accepted.append(tool)

    if not accepted:
        warnings.append("llm_proposal_empty_after_review_fell_back_to_deterministic")
        return ChronologyPlan(
            approved_tools=default,
            decision_source="deterministic_fallback",
            dropped=dropped,
            warnings=warnings,
        )

    # Deterministic wins on ordering: sort accepted tools by canonical order.
    def _order(name: str) -> float:
        value = tools.get(name, {}).get("order")
        return float("inf") if value is None else float(value)

    approved = sorted(accepted, key=_order)

    source: DecisionSource = "llm_reviewed"
    if dropped or approved != [t for t in proposed if t in approved]:
        source = "llm_reviewed_adjusted"
        if approved != accepted:
            warnings.append("reordered_to_canonical_playbook_order")

    return ChronologyPlan(
        approved_tools=approved,
        decision_source=source,
        dropped=dropped,
        warnings=warnings,
    )
