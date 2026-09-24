"""CIO-facing content layer for EC agent workflows.

Scenario packs produce the lifecycle mechanics (steps, statuses, findings). This module adds
the layer a CIO reads on top of them, uniformly for every registered scenario:

* **Why each step exists** — investigation steps carry ``rationale`` / ``decides`` /
  ``if_skipped``; remediation steps carry ``rationale`` / ``reversible`` / ``approver`` /
  ``risk_if_skipped``. A plan the viewer is asked to approve must justify itself.
* **Executive brief** — verdict, business impact, risk delta, confidence, and the decision
  needed, at ``INVESTIGATION_COMPLETE`` and ``COMPLETE``. Additive: ``executive_summary``
  (``string[]``) is untouched because the S1 UI and tests pin its shape.
* **Tool fabric** — step tool labels resolve through :mod:`tool_catalog`, so the same
  connector has the same name in every question.
* **Audience hygiene** — engineering notes ("no X MCP is onboarded", "live LLM") belong in the
  transparency drawer, not in analyst-visible plan text.

Content lives in one module per scenario (``fixtures/<id>/cio_content.py``) and registers
here; a scenario without registered content passes through unchanged.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from app.demo.ec_agent.tool_catalog import resolve_tool_id, tool_display_name, tool_fabric

INVESTIGATION_WHY_KEYS = ("rationale", "decides", "if_skipped")
REMEDIATION_WHY_KEYS = ("rationale", "reversible", "approver", "risk_if_skipped")

_STEP_LIST_PATHS = (
    ("investigation_plan", "steps"),
    ("investigation_results", "steps"),
    ("remediation_plan", "steps"),
    ("remediation_results", "steps"),
    ("execution_progress", "steps"),
)

# Brief lines that describe the demo harness rather than the investigation.
_INTERNAL_BRIEF_LINE = re.compile(r"\blive (mcp|llm)\b|experience center path", re.IGNORECASE)

# Lifecycles that show the investigation-level brief vs the closing brief.
_BRIEF_KEY_BY_LIFECYCLE = {
    "INVESTIGATION_COMPLETE": "investigation",
    "REMEDIATION_PLAN_READY": "investigation",
    "REMEDIATING": "investigation",
    "VERIFYING": "investigation",
    "COMPLETE": "complete",
    "PARTIAL": "complete",
}


@dataclass(frozen=True)
class CioContent:
    scenario_id: str
    opening_narrative: str
    step_why: dict[str, dict[str, str]]
    executive_brief: dict[str, dict[str, Any]] = field(default_factory=dict)
    # Optional analyst-facing replacements for step summaries that contained internal notes.
    step_summary: dict[str, str] = field(default_factory=dict)


_CONTENT: dict[str, CioContent] = {}


def register_cio_content(content: CioContent) -> None:
    if content.scenario_id in _CONTENT:
        raise ValueError(f"CIO content already registered: {content.scenario_id}")
    _CONTENT[content.scenario_id] = content


def cio_content_for(scenario_id: str) -> CioContent | None:
    _ensure_loaded()
    return _CONTENT.get(scenario_id)


_LOADED = False


def _ensure_loaded() -> None:
    global _LOADED
    if _LOADED:
        return
    import app.demo.ec_agent.cio_content_registry  # noqa: F401

    _LOADED = True


def _enrich_step(step: dict[str, Any], content: CioContent, used_tool_ids: set[str]) -> None:
    step_id = str(step.get("id") or "")
    why = content.step_why.get(step_id)
    if why:
        for key, value in why.items():
            step.setdefault(key, value)
    summary = content.step_summary.get(step_id)
    if summary:
        step["summary"] = summary

    labels = [str(label) for label in step.get("tools") or []]
    tool_ids: list[str] = []
    display: list[str] = []
    for label in labels:
        tool_id = resolve_tool_id(label)
        if tool_id is None:
            display.append(label)
            continue
        if tool_id not in tool_ids:
            tool_ids.append(tool_id)
            display.append(tool_display_name(tool_id))
    if labels:
        step["tools"] = display
        step["tool_ids"] = tool_ids
        used_tool_ids.update(tool_ids)


def enrich_agent_workflow(scenario_id: str, workflow: dict[str, Any]) -> dict[str, Any]:
    """Return ``workflow`` with the CIO layer applied (mutates and returns the same dict)."""
    content = cio_content_for(scenario_id)
    if content is None:
        return workflow

    used_tool_ids: set[str] = set()
    for container_key, list_key in _STEP_LIST_PATHS:
        container = workflow.get(container_key)
        if not isinstance(container, dict):
            continue
        for step in container.get(list_key) or []:
            if isinstance(step, dict):
                _enrich_step(step, content, used_tool_ids)

    workflow["opening_narrative"] = content.opening_narrative

    brief = workflow.get("brief")
    if isinstance(brief, dict) and brief.get("what_i_know"):
        brief["what_i_know"] = [
            line for line in brief["what_i_know"] if not _INTERNAL_BRIEF_LINE.search(str(line))
        ]

    brief_key = _BRIEF_KEY_BY_LIFECYCLE.get(str(workflow.get("lifecycle") or ""))
    if brief_key and brief_key in content.executive_brief:
        workflow["executive_brief"] = dict(content.executive_brief[brief_key])

    workflow["tool_fabric"] = tool_fabric(used_tool_ids)
    return workflow
