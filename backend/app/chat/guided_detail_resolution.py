"""Gap-resolution planner (Planner 1) — no ResourcePlan authority."""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime
from typing import Any

from app.chat.canonical_handoff_store import record_duplicate_call_hash
from app.chat.contracts.gap_resolution import FieldProvenance, GapResolutionResult
from app.chat.contracts.knowledge_recall import KnowledgeRecallRequest
from app.chat.detail_merge import merge_knowledge_recall
from app.chat.detail_tools.knowledge_recall_tool import run_knowledge_recall
from app.chat.known_detail_completion import KnownCompletenessResult, MissingFieldCategory
from app.chat.select_detail_tools import select_detail_tools

MAX_TOOL_CALLS = 3
MAX_ITERATIONS = 2
RETRYABLE_ERROR_TYPES = frozenset({"timeout", "source_unavailable", "transient"})
FATAL_ERROR_TYPES = frozenset({"policy_blocked", "unsupported_source", "auth_denied"})


def _call_hash(tool: str, payload: dict[str, Any]) -> str:
    raw = f"{tool}:{sorted(payload.items())}".encode()
    return hashlib.sha256(raw).hexdigest()[:16]


def run_guided_detail_resolution(
    *,
    query: str,
    handoff_id: str,
    handoff_version: int = 1,
    intent_family: str,
    answer_goal: str,
    completeness: KnownCompletenessResult,
    reference_ids: list[str] | None = None,
    original_skill: str | None = None,
    original_answer_goal: str | None = None,
    known_values: dict[str, Any] | None = None,
    unsafe: bool = False,
    skip_tools: bool = False,
    state: dict[str, Any] | None = None,
) -> GapResolutionResult:
    resolution_id = f"gr:{uuid.uuid4().hex[:12]}"
    known_prov: dict[str, FieldProvenance] = {}
    now = datetime.now(UTC).isoformat()
    for key, value in (known_values or {}).items():
        known_prov[key] = FieldProvenance(value=value, source="user", confidence=1.0, timestamp=now)

    if skip_tools or completeness.clarification_required and not completeness.divert_to_guided:
        return GapResolutionResult(
            resolution_id=resolution_id,
            handoff_id=handoff_id,
            original_skill=original_skill,
            original_answer_goal=original_answer_goal or answer_goal,
            known_details=known_prov,
            requested_missing_details=list(completeness.missing_fields),
            resolution_status="clarification_required",
            clarification_required=True,
            limitations=list(completeness.limitations),
        )

    if unsafe:
        return GapResolutionResult(
            resolution_id=resolution_id,
            handoff_id=handoff_id,
            resolution_status="policy_blocked",
            clarification_required=True,
            limitations=["unsafe_request_blocked"],
        )

    missing_categories: dict[str, MissingFieldCategory] = dict(completeness.missing_field_categories)
    tools = select_detail_tools(
        intent_family=intent_family,
        answer_goal=answer_goal,
        missing_categories=missing_categories,
        reference_ids=reference_ids,
        original_skill=original_skill,
        unsafe=unsafe,
    )

    if not tools:
        return GapResolutionResult(
            resolution_id=resolution_id,
            handoff_id=handoff_id,
            resolution_status="resolved_without_tools",
            selected_tools=[],
        )

    from app.chat.planning_telemetry import emit_detail_tool_event, emit_detail_merge_completed

    emit_planning_event_tools = state is not None
    tool_results: dict[str, Any] = {}
    tool_statuses: dict[str, str] = {}
    call_ids: list[str] = []
    conflicts = []
    limitations: list[str] = []
    retry_count = 0
    iterations = 0

    for tool in tools:
        if iterations >= MAX_ITERATIONS:
            limitations.append("max_iterations_reached")
            break
        if len(call_ids) >= MAX_TOOL_CALLS:
            limitations.append("max_tool_calls_reached")
            break
        iterations += 1

        if tool == "knowledge_recall":
            req = KnowledgeRecallRequest(query=query, reference_ids=list(reference_ids or []))
            payload = req.model_dump()
            ch = _call_hash(tool, payload)
            if record_duplicate_call_hash(handoff_id, handoff_version, ch):
                limitations.append(f"duplicate_call_blocked:{tool}")
                tool_statuses[tool] = "duplicate_blocked"
                continue
            if emit_planning_event_tools:
                state = emit_detail_tool_event(
                    state,
                    event_suffix="selected",
                    tool=tool,
                    handoff_id=handoff_id,
                    handoff_version=handoff_version,
                ) or state
                state = emit_detail_tool_event(
                    state,
                    event_suffix="started",
                    tool=tool,
                    handoff_id=handoff_id,
                    handoff_version=handoff_version,
                ) or state
            result = run_knowledge_recall(req)
            tool_results[tool] = result.model_dump()
            tool_statuses[tool] = result.status
            if result.tool_call_id:
                call_ids.append(result.tool_call_id)
            if emit_planning_event_tools:
                if result.status == "error":
                    error_cat = "transient" if any(e in RETRYABLE_ERROR_TYPES for e in result.errors) else "fatal"
                    state = emit_detail_tool_event(
                        state,
                        event_suffix="failed",
                        tool=tool,
                        handoff_id=handoff_id,
                        handoff_version=handoff_version,
                        tool_call_id=result.tool_call_id,
                        status="error",
                        error_category=error_cat,
                    ) or state
                else:
                    state = emit_detail_tool_event(
                        state,
                        event_suffix="completed",
                        tool=tool,
                        handoff_id=handoff_id,
                        handoff_version=handoff_version,
                        tool_call_id=result.tool_call_id,
                        status=result.status,
                    ) or state
            known_prov, tool_conflicts, lims = merge_knowledge_recall(result, known=known_prov)
            if emit_planning_event_tools:
                state = emit_detail_merge_completed(
                    state,
                    {
                        "handoff_id": handoff_id,
                        "handoff_version": handoff_version,
                        "conflicts": [c.model_dump() for c in tool_conflicts],
                        "resolved_fields": list(known_prov.keys()),
                    },
                ) or state
            conflicts.extend(tool_conflicts)
            limitations.extend(lims)
            if result.status == "error":
                retry_count += 1
                if any(err in FATAL_ERROR_TYPES for err in result.errors):
                    return GapResolutionResult(
                        resolution_id=resolution_id,
                        handoff_id=handoff_id,
                        original_skill=original_skill,
                        original_answer_goal=original_answer_goal or answer_goal,
                        known_details=known_prov,
                        requested_missing_details=list(completeness.missing_fields),
                        selected_tools=tools,
                        tool_results=tool_results,
                        tool_statuses=tool_statuses,
                        unresolved_details=list(completeness.missing_fields),
                        conflicts=conflicts,
                        resolution_status="resolution_failed",
                        clarification_required=True,
                        limitations=[*limitations, "fatal_tool_error"],
                        retry_count=retry_count,
                        tool_call_ids=call_ids,
                    )
        else:
            tool_statuses[tool] = "planned_read_only"
            limitations.append(f"{tool}_execution_deferred_to_final_planner")

    resolved_keys = list(known_prov.keys())
    unresolved = [k for k in completeness.missing_fields if k not in resolved_keys]

    status = "complete"
    if unresolved:
        status = "complete_with_limitations" if known_prov else "resolution_failed"
    if completeness.clarification_required:
        status = "clarification_required"

    planner_required = [k for k, c in missing_categories.items() if c == "planner_required"]
    user_only = [k for k, c in missing_categories.items() if c == "user_only"]
    blocking = [k for k in unresolved if k in planner_required or k in user_only]
    if blocking and status not in {"clarification_required", "policy_blocked"}:
        status = "clarification_required"

    return GapResolutionResult(
        resolution_id=resolution_id,
        handoff_id=handoff_id,
        original_skill=original_skill,
        original_answer_goal=original_answer_goal or answer_goal,
        known_details=known_prov,
        requested_missing_details=list(completeness.missing_fields),
        selected_tools=tools,
        tool_results=tool_results,
        tool_statuses=tool_statuses,
        resolved_details={k: v for k, v in known_prov.items() if k not in (known_values or {})},
        unresolved_details=unresolved,
        conflicts=conflicts,
        field_sources={k: v.source for k, v in known_prov.items()},
        field_confidence={k: v.confidence for k, v in known_prov.items()},
        resolution_status=status,  # type: ignore[arg-type]
        clarification_required=status == "clarification_required",
        limitations=limitations,
        retry_count=retry_count,
        tool_call_ids=call_ids,
    )
