"""Deterministic governed evidence-collection loop controller (Stage 4B).

`graph_node_evidence_planning` is the HUB. After each evidence-producing hop
(discovery `mcp_call` or gated `execution`) control returns here, which maps the
declared per-hop **requirement** (the `produces` keys a tool should yield, from
`mcp_tool_playbook.json`) against the **deliverable** actually accumulated, then
chooses the next route deterministically. The loop is bounded by a single
counter (`MAX_MCP_HOPS`); the LLM only ever proposes the chronology — every
routing/termination decision here is deterministic.

This module is pure logic: no graph, no IO, no LLM. It is imported by the
pipeline node and the LangGraph wiring, and is fully unit-testable on its own.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from app.chat.canonical_facts_spine import harvest_canonical_facts_from_state
from app.connectors.mcp.mcp_rbac import canonical_mcp_tool_name
from app.connectors.mcp.mcp_tool_chronology import _evaluate_tool_step, load_playbook
from app.orchestration.mcp_orchestration import CallBudget, CallOutcome, McpCallRecord
from app.planner.orchestration_scheduler import ScheduleDecision, outcome_edge, schedule_next
from app.planner.recipe_registry import Recipe

# A single bound covers discovery hops + execution retries combined, so the loop
# is guaranteed to terminate regardless of how routing fans out.
MAX_MCP_HOPS = 6

# Stable route labels. The graph maps these to edges; tests assert on them.
ROUTE_DISCOVERY_HOP = "discovery_hop"        # run the next read-only mcp_call hop
ROUTE_EXECUTE = "execute"                     # requirements met → proceed to the gated run_query
ROUTE_FINALIZE = "finalize"                   # evidence sufficient → context_finalize/synthesis
ROUTE_BROADEN = "broaden"                     # execution empty + broaden-eligible → defer to broaden flow
ROUTE_HUMAN_REVIEW = "human_review"           # gap an analyst can resolve
ROUTE_CAPABILITY_GAP = "capability_gap"       # no tool/data can produce it (honest degrade → finalize)
ROUTE_EXHAUSTED = "exhausted"                 # hop budget hit → proceed-with-available / HIL
ROUTE_AWAIT_EXECUTION = "await_execution"     # discovery done; remaining requirement is produced by the gated execution stage

# Produces only the gated run_query execution stage can deliver. The live
# chronology is composed with spl_approved=False (run_query never enters the
# loop plan); these requirements are satisfied later by the execution stage,
# so their absence after discovery is not an analyst-resolvable gap.
EXECUTION_STAGE_PRODUCES = frozenset({"result_rows", "events"})

# Requirements that no governed Splunk tool can satisfy (e.g. CVE / asset / vuln
# data is not indexed in Splunk). Declared unservable → honest capability gap,
# never an endless loop trying to fetch them.
UNSERVABLE_REQUIREMENTS = frozenset(
    {
        "cve",
        "cve_correlation",
        "unpatched_cve_correlation",
        "vulnerability_source",
        "asset_context",
        "cmdb",
        "lookup_dependency",
        "source_profile",
        "detection_binding",
        "context_binding",
        "case_context",
    }
)

# CVE/vulnerability-class requirements an onboarded CVE snapshot read model
# (plan §3 A4) can inform — never SERVE from Splunk, so they stay capability gaps
# for routing, but the loop can attach honest `vulnerability_source.status`
# provenance instead of a bare "not onboarded". Defined in the leaf CVE module so
# app.cve.evidence_adapter can share it without an import cycle; re-exported here
# for existing importers.
from app.cve.requirements import (  # noqa: E402
    CVE_VULNERABILITY_REQUIREMENTS,
    cve_requirements_present,
)


@dataclass
class LoopDecision:
    """The deterministic routing verdict produced by the HUB assessor."""

    route: str
    reason: str
    next_tool: str | None = None
    sufficiency: str = "needs_more"  # sufficient | needs_more | exhausted | capability_gap
    proceed_with_available: bool = False
    missing: list[str] = field(default_factory=list)
    capability_gaps: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "route": self.route,
            "reason": self.reason,
            "next_tool": self.next_tool,
            "sufficiency": self.sufficiency,
            "proceed_with_available": self.proceed_with_available,
            "missing": list(self.missing),
            "capability_gaps": list(self.capability_gaps),
        }


def declare_hop_requirements(
    chronology: list[str],
    playbook: dict[str, Any] | None = None,
) -> dict[str, list[str]]:
    """Map each planned tool to the `produces` keys it is expected to deliver."""
    tools = (playbook or load_playbook()).get("tools") or {}
    requirements: dict[str, list[str]] = {}
    for tool in chronology:
        spec = tools.get(tool) or {}
        requirements[tool] = [str(item) for item in (spec.get("produces") or [])]
    return requirements


def loop_initialized(state: dict[str, Any]) -> bool:
    """Re-entry guard: True once the HUB has composed the loop plan this turn.

    A recipe-driven turn (item 3.1) never sets mcp_chronology — it initializes
    mcp_call_records instead — so this checks either.
    """
    return isinstance(state.get("mcp_chronology"), list) or isinstance(state.get("mcp_call_records"), list)


def initialize_loop(
    chronology: list[str],
    *,
    playbook: dict[str, Any] | None = None,
    required_produces: list[str] | None = None,
) -> dict[str, Any]:
    """Return the initial loop state patch. Idempotent callers must guard with
    `loop_initialized` so this only runs once per turn."""
    requirements = declare_hop_requirements(chronology, playbook)
    needed = list(required_produces) if required_produces is not None else _flatten_requirements(requirements)
    return {
        "mcp_chronology": list(chronology),
        "mcp_cursor": 0,
        "mcp_evidence": [],
        "mcp_hops_done": 0,
        "mcp_requirements": requirements,
        "mcp_required_produces": needed,
    }


def record_hop(
    state: dict[str, Any],
    *,
    tool: str,
    delivered: list[str],
    payload: dict[str, Any] | None = None,
    outcome: str = "collected",
) -> dict[str, Any]:
    """Return a state patch recording one completed hop: advance cursor, bump the
    single bound counter, and accumulate the deliverable."""
    evidence = list(state.get("mcp_evidence") or [])
    evidence.append(
        {
            "tool": tool,
            "delivered": [str(item) for item in delivered],
            "outcome": outcome,
            "payload": payload or {},
        }
    )
    return {
        "mcp_evidence": evidence,
        "mcp_cursor": int(state.get("mcp_cursor", 0)) + 1,
        "mcp_hops_done": int(state.get("mcp_hops_done", 0)) + 1,
    }


def execution_hop_recorded(state: dict[str, Any]) -> bool:
    for hop in state.get("mcp_evidence") or []:
        if hop.get("tool") == "splunk_run_query":
            return True
    return False


def record_execution_hop(state: dict[str, Any], execution: dict[str, Any]) -> dict[str, Any]:
    """Count a gated run_query re-entry against the single hop bound."""
    if execution_hop_recorded(state):
        return {}
    status = str(execution.get("status") or "unknown")
    result_count = int(execution.get("result_count") or 0)
    delivered: list[str] = []
    if status == "executed" and result_count > 0:
        # "result_rows" is run_query's playbook `produces` key; deliver it too
        # so requirement<->deliverable accounting closes after execution.
        delivered = ["events", "result_rows"]
    elif status == "executed":
        delivered = ["negative_result"]
    outcome = "collected" if status == "executed" else status
    return record_hop(
        state,
        tool="splunk_run_query",
        delivered=delivered,
        outcome=outcome,
        payload={
            "execution_status": status,
            "result_count": result_count,
            "block_reason": execution.get("block_reason"),
        },
    )


def delivered_produces(state: dict[str, Any]) -> set[str]:
    """Union of `produces` keys delivered across all accumulated hops."""
    delivered: set[str] = set()
    for hop in state.get("mcp_evidence") or []:
        delivered.update(str(item) for item in (hop.get("delivered") or []))
    return delivered


def apply_observer_next_hop_hint(state: dict[str, Any]) -> dict[str, Any]:
    """Validate an observer next-hop hint and return a state patch.

    The observer may only propose one extra read-only discovery hop. The HUB
    remains the actor: every hint is reviewed against the same playbook policy
    used for chronology review before it can be scheduled.
    """
    trace = state.get("evidence_observer_trace")
    if not isinstance(trace, dict):
        return {}
    hint = str(trace.get("next_hop_hint") or "").strip()
    if not hint:
        return {}
    if state.get("mcp_recipe_id"):
        return {"evidence_observer_trace": {**trace, "observer_hint_ignored_recipe_turn": True}}

    canonical = canonical_mcp_tool_name(hint)
    rejected = _observer_hint_rejection_reason(state, canonical)
    if rejected:
        return {
            "evidence_observer_trace": {
                **trace,
                "observer_hint_rejected": True,
                "observer_hint_rejected_reason": rejected,
            }
        }

    chronology = list(state.get("mcp_chronology") or [])
    return {
        "mcp_chronology": [*chronology, canonical],
        "evidence_observer_trace": {
            **trace,
            "observer_hint_accepted": True,
            "observer_hint_tool": canonical,
        },
    }


def _observer_hint_rejection_reason(state: dict[str, Any], canonical: str) -> str | None:
    if canonical in {"splunk_run_query", "splunk_run_saved_search"}:
        return "execution_class_hint"
    playbook = load_playbook()
    tools = playbook.get("tools") if isinstance(playbook, dict) else {}
    if not isinstance(tools, dict) or canonical not in tools:
        return "unknown_tool"
    collected = {
        str(hop.get("tool") or "")
        for hop in (state.get("mcp_evidence") or [])
        if isinstance(hop, dict)
    }
    cursor = int(state.get("mcp_cursor", 0))
    completed = set(list(state.get("mcp_chronology") or [])[:cursor])
    if canonical in collected or canonical in completed:
        return "already_collected"
    if int(state.get("mcp_hops_done", 0)) >= MAX_MCP_HOPS:
        return "budget"
    turn_intents = state.get("mcp_turn_intents")
    intent_set = (
        frozenset(str(item) for item in turn_intents)
        if isinstance(turn_intents, (list, tuple, set, frozenset))
        else None
    )
    return _evaluate_tool_step(
        canonical,
        tools.get(canonical),
        target_index=_target_index_from_spl_validation(state.get("spl_validation")),
        spl_approved=False,
        rbac_role=None,
        turn_intents=intent_set,
    )


def _target_index_from_spl_validation(spl_validation: dict[str, Any] | None) -> str | None:
    if not isinstance(spl_validation, dict):
        return None
    normalized = str(spl_validation.get("normalized_spl") or "")
    match = re.search(r"\bindex\s*=\s*([^\s|]+)", normalized, re.IGNORECASE)
    return match.group(1).strip() if match else None


def extract_loop_scoping_targets(state: dict[str, Any]) -> dict[str, Any]:
    """Loop-time scoping targets for data-silence checks (never reads canonical_facts on state)."""
    facts = harvest_canonical_facts_from_state(state)
    hosts: list[str] = []
    timeframes: list[dict[str, Any]] = []
    for fact in facts.facts:
        if fact.kind == "entity":
            payload = fact.payload if isinstance(fact.payload, dict) else {"value": str(fact.payload)}
            for key in ("host", "hostname", "value", "entity", "name"):
                value = payload.get(key)
                if isinstance(value, str) and value.strip():
                    hosts.append(value.strip().lower())
        elif fact.kind == "timeframe":
            payload = fact.payload if isinstance(fact.payload, dict) else {"value": fact.payload}
            timeframes.append(payload)
    index = _target_index_from_spl_validation(state.get("spl_validation"))
    unique_hosts = list(dict.fromkeys(hosts))
    has_scope = bool(unique_hosts or timeframes or index)
    return {
        "hosts": unique_hosts,
        "timeframes": timeframes,
        "index": index,
        "has_scope": has_scope,
    }


def _latest_metadata_hop(state: dict[str, Any]) -> dict[str, Any] | None:
    for hop in reversed(state.get("mcp_evidence") or []):
        if hop.get("tool") == "splunk_get_metadata":
            return hop if isinstance(hop, dict) else None
    return None


def _row_count(row: dict[str, Any]) -> int:
    for key in ("totalCount", "count", "event_count"):
        raw = row.get(key)
        if raw is not None:
            try:
                return int(raw)
            except (TypeError, ValueError):
                continue
    return 0


def metadata_shows_zero_footprint(payload: dict[str, Any], targets: dict[str, Any]) -> bool:
    """True when metadata indicates zero footprint for scoped entity/index/timeframe."""
    if not targets.get("has_scope"):
        return False
    payload = payload or {}
    if payload.get("totalCount") == 0:
        return True
    preview_rows = [row for row in (payload.get("preview_rows") or []) if isinstance(row, dict)]
    result_summary = payload.get("result_summary") if isinstance(payload.get("result_summary"), dict) else {}
    target_hosts = targets.get("hosts") or []
    if target_hosts:
        matching = [
            row
            for row in preview_rows
            if any(str(row.get(field, "")).lower() in target_hosts for field in ("host", "hostname", "name"))
        ]
        if matching:
            return all(_row_count(row) == 0 for row in matching)
        payload_hosts = [str(item).lower() for item in (payload.get("hosts") or []) if item]
        if not payload_hosts:
            return True
        return not any(host in target_hosts for host in payload_hosts)
    if targets.get("index") or targets.get("timeframes"):
        if result_summary.get("sourcetype_count") == 0:
            return True
        if preview_rows and all(_row_count(row) == 0 for row in preview_rows):
            return True
    return False


def should_emit_data_silence_advisory(state: dict[str, Any]) -> bool:
    existing = state.get("data_silence_advisory")
    if isinstance(existing, dict) and (existing.get("dismissed") or existing.get("halted")):
        return False
    targets = extract_loop_scoping_targets(state)
    if not targets["has_scope"]:
        return False
    hop = _latest_metadata_hop(state)
    if hop is None:
        return False
    payload = hop.get("payload") if isinstance(hop.get("payload"), dict) else {}
    return metadata_shows_zero_footprint(payload, targets)


def build_data_silence_advisory(state: dict[str, Any]) -> dict[str, Any]:
    targets = extract_loop_scoping_targets(state)
    hop = _latest_metadata_hop(state) or {}
    return {
        "active": True,
        "review_type": "data_silence_advisory",
        "targets": {
            key: targets[key]
            for key in ("hosts", "index", "timeframes")
            if targets.get(key)
        },
        "metadata_tool": hop.get("tool"),
        "metadata_outcome": hop.get("outcome"),
        "reason": "metadata_zero_footprint",
        "note": (
            "Metadata window may lag the proposed search window; "
            "this is advisory, not a hard circuit breaker."
        ),
    }


def assess_loop(
    state: dict[str, Any],
    *,
    execution: dict[str, Any] | None = None,
    broaden_eligible: bool = False,
) -> LoopDecision:
    """The HUB decision. Deterministic; never mutates state.

    `execution` is the result of a gated run_query hop when the loop re-enters
    from the execution node; otherwise the assessor is in the discovery phase.
    """
    hops_done = int(state.get("mcp_hops_done", 0))
    chronology = list(state.get("mcp_chronology") or [])
    cursor = int(state.get("mcp_cursor", 0))
    required = [str(item) for item in (state.get("mcp_required_produces") or [])]
    discovery_only = bool(state.get("mcp_discovery_only"))

    # Honest capability gap: a required produce that no governed tool can yield.
    capability_gaps = sorted(set(required) & UNSERVABLE_REQUIREMENTS)

    # Bound check first — guarantees termination no matter the route fan-out.
    if hops_done >= MAX_MCP_HOPS:
        return LoopDecision(
            route=ROUTE_EXHAUSTED,
            reason=f"hop budget {MAX_MCP_HOPS} reached; proceed with available evidence",
            sufficiency="exhausted",
            proceed_with_available=True,
            capability_gaps=capability_gaps,
        )

    # Execution re-entry: the run_query result decides loop/broaden/finalize.
    if execution is not None:
        if discovery_only:
            return LoopDecision(
                route=ROUTE_FINALIZE,
                reason="discovery-only lane; execution hop not permitted",
                sufficiency="sufficient",
                capability_gaps=capability_gaps,
            )
        status = str(execution.get("status") or "")
        result_count = int(execution.get("result_count") or 0)
        if status == "executed" and result_count > 0:
            return LoopDecision(
                route=ROUTE_FINALIZE,
                reason="execution returned rows; evidence sufficient",
                sufficiency="sufficient",
                capability_gaps=capability_gaps,
            )
        if status == "executed" and result_count == 0:
            if broaden_eligible:
                # Decision B: the loop defers empty-result widening to the
                # existing analyst-confirmed broaden flow — it does NOT broaden
                # in-loop.
                return LoopDecision(
                    route=ROUTE_BROADEN,
                    reason="execution empty and broaden-eligible; hand off to broaden flow",
                    sufficiency="needs_more",
                    capability_gaps=capability_gaps,
                )
            return LoopDecision(
                route=ROUTE_FINALIZE,
                reason="execution empty, broaden not eligible; finalize honest negative result",
                sufficiency="sufficient",
                capability_gaps=capability_gaps,
            )
        # Non-executed (blocked/denied/timeout) → analyst handles it.
        return LoopDecision(
            route=ROUTE_HUMAN_REVIEW,
            reason=f"execution did not complete (status={status or 'unknown'})",
            sufficiency="needs_more",
            capability_gaps=capability_gaps,
        )

    # Discovery phase: more planned read-only hops to run?
    pending = chronology[cursor:]
    discovery_pending = [tool for tool in pending if tool != "splunk_run_query"]
    if discovery_pending:
        return LoopDecision(
            route=ROUTE_DISCOVERY_HOP,
            reason="pending discovery hop in chronology",
            next_tool=discovery_pending[0],
            sufficiency="needs_more",
            capability_gaps=capability_gaps,
        )

    # Discovery exhausted. Compute requirement<->deliverable for the executable
    # leg, excluding the unservable gaps (those are an honest degrade, not a loop).
    delivered = delivered_produces(state)
    missing = sorted((set(required) - delivered) - UNSERVABLE_REQUIREMENTS)

    if "splunk_run_query" in pending:
        if discovery_only:
            return LoopDecision(
                route=ROUTE_FINALIZE,
                reason="discovery-only lane; run_query not permitted",
                sufficiency="sufficient" if not missing else "needs_more",
                missing=missing,
                capability_gaps=capability_gaps,
            )
        if should_emit_data_silence_advisory(state):
            return LoopDecision(
                route=ROUTE_HUMAN_REVIEW,
                reason=(
                    "data_silence: metadata shows zero target footprint before run_query; "
                    "metadata window may lag the search window"
                ),
                next_tool="splunk_run_query",
                sufficiency="needs_more",
                missing=missing,
                capability_gaps=capability_gaps,
            )
        return LoopDecision(
            route=ROUTE_EXECUTE,
            reason="discovery complete; proceed to gated run_query",
            next_tool="splunk_run_query",
            sufficiency="sufficient" if not missing else "needs_more",
            missing=missing,
            capability_gaps=capability_gaps,
        )

    # No run_query planned. If everything servable is delivered → finalize;
    # if a servable requirement is still missing and budget remains, the analyst
    # resolves it (no tool left in the plan to produce it).
    if missing:
        # Requirements only the gated execution stage can deliver are not an
        # analyst gap mid-turn: the dispatch chain still runs run_query after
        # this loop (chronology is composed with spl_approved=False, so
        # run_query is never in the plan). Labeling those "human_review" put a
        # misleading verdict in the trace on turns that execute fine.
        if not discovery_only and set(missing) <= EXECUTION_STAGE_PRODUCES:
            return LoopDecision(
                route=ROUTE_AWAIT_EXECUTION,
                reason="discovery complete; remaining requirement is produced by the gated execution stage",
                sufficiency="needs_more",
                missing=missing,
                capability_gaps=capability_gaps,
            )
        return LoopDecision(
            route=ROUTE_HUMAN_REVIEW,
            reason="servable requirement unmet and no remaining tool produces it",
            sufficiency="needs_more",
            missing=missing,
            capability_gaps=capability_gaps,
        )
    if capability_gaps:
        return LoopDecision(
            route=ROUTE_CAPABILITY_GAP,
            reason="only unservable requirements remain; finalize as honest degrade",
            sufficiency="capability_gap",
            capability_gaps=capability_gaps,
        )
    return LoopDecision(
        route=ROUTE_FINALIZE,
        reason="all servable requirements delivered; finalize",
        sufficiency="sufficient",
        capability_gaps=capability_gaps,
    )


# --- O5c: recipe-aware HUB path (item 3.1, 2026-07-03) ---------------------
#
# The chronology-driven assess_loop above stays the default for every turn
# without a selected recipe. The item-3.2 selector (in the pipeline's
# evidence-planning first entry) sets state["mcp_recipe_id"] live for
# out_of_registry / near_105_question turns with a matching answer shape.
# When a recipe IS selected, these functions delegate the actual
# scheduling decision to the pure O5b functions (schedule_next/outcome_edge)
# and translate their vocabulary into the SAME LoopDecision route labels the
# chronology path uses, so no existing dispatch/routing code needs to change.

# "requires_human_review" is intentionally absent: classify_call_outcome
# returns None for it before this map is consulted (pending HIL = not terminal).
_STATUS_TO_OUTCOME: dict[str, CallOutcome] = {
    "blocked": "blocked",
    "skipped": "failed",
}


def classify_call_outcome(execution: dict[str, Any]) -> CallOutcome | None:
    """Classify a completed execution result into the O5b outcome vocabulary.

    Returns None when the call has not actually terminated yet (still pending
    analyst confirmation) — callers must not record a McpCallRecord for that
    turn; the loop stops at ROUTE_HUMAN_REVIEW until the next request resolves it.
    """
    status = str(execution.get("status") or "")
    if status == "requires_human_review":
        return None
    if status == "executed":
        result_count = int(execution.get("result_count") or 0)
        return "ok" if result_count > 0 else "empty"
    return _STATUS_TO_OUTCOME.get(status, "failed")


def record_recipe_call(
    state: dict[str, Any],
    *,
    call_id: str,
    execution: dict[str, Any],
) -> dict[str, Any]:
    """Return a state patch recording one completed recipe call, or {} when the
    call has not terminated yet (pending HIL — nothing to record this turn)."""
    outcome = classify_call_outcome(execution)
    if outcome is None:
        return {}
    records = list(state.get("mcp_call_records") or [])
    sequence = len(records)
    record = McpCallRecord(
        call_id=call_id,
        sequence=sequence,
        outcome=outcome,
        result_count=int(execution.get("result_count") or 0),
        error_type=str(execution.get("block_reason")) if outcome not in ("ok", "empty") and execution.get("block_reason") else None,
    )
    records.append(record.model_dump(mode="json"))
    return {
        "mcp_call_records": records,
        "mcp_hops_done": int(state.get("mcp_hops_done", 0)) + 1,
    }


def assess_loop_with_recipe(state: dict[str, Any], recipe: Recipe) -> LoopDecision:
    """The O5c HUB decision for a recipe-driven turn. Deterministic; never
    mutates state — callers apply `record_recipe_call`'s patch first."""
    hops_done = int(state.get("mcp_hops_done", 0))
    if hops_done >= MAX_MCP_HOPS:
        return LoopDecision(
            route=ROUTE_EXHAUSTED,
            reason=f"hop budget {MAX_MCP_HOPS} reached; proceed with available evidence",
            sufficiency="exhausted",
            proceed_with_available=True,
        )

    raw_records = state.get("mcp_call_records") or []
    records = [McpCallRecord.model_validate(item) for item in raw_records]
    # Budget = min(MAX_MCP_HOPS, recipe budget); never raised at runtime — the
    # single global hop bound above is a second, independent floor on top.
    budget = CallBudget(max_calls=min(MAX_MCP_HOPS - hops_done, recipe.max_calls - len(records)))

    decision: ScheduleDecision = schedule_next(recipe, records, budget)

    if decision.action == "stop":
        if decision.stop_reason == "evidence_satisfied":
            # "evidence_satisfied" covers two distinct cases the scheduler does
            # not itself distinguish: genuinely done, or the last call came
            # back empty and nothing else is ready. A recipe may predeclare the
            # latter as an analyst hand-off (RecipeCall.on_empty="hil") rather
            # than a silent finalize — consult outcome_edge for that call.
            if records and records[-1].outcome == "empty":
                last_call = recipe.call_by_id(records[-1].call_id)
                if last_call is not None and outcome_edge(last_call, "empty") == "hil":
                    return LoopDecision(
                        route=ROUTE_HUMAN_REVIEW,
                        reason=f"{records[-1].call_id} returned empty; recipe routes empty to analyst hand-off",
                        sufficiency="needs_more",
                    )
            return LoopDecision(
                route=ROUTE_FINALIZE,
                reason="recipe evidence satisfied",
                sufficiency="sufficient",
            )
        if decision.stop_reason == "budget_exhausted":
            return LoopDecision(
                route=ROUTE_EXHAUSTED,
                reason="recipe call budget exhausted",
                sufficiency="exhausted",
                proceed_with_available=True,
                missing=decision.unresolved_evidence_keys,
            )
        # fail_closed:<outcome> or any other stop reason — hard failures fail
        # closed per the recipe layer's governance invariant: no further
        # scheduling, stop for review.
        return LoopDecision(
            route=ROUTE_HUMAN_REVIEW,
            reason=decision.stop_reason or "recipe scheduling stopped",
            sufficiency="needs_more",
            missing=decision.unresolved_evidence_keys,
        )

    call = recipe.call_by_id(decision.call_id)
    route = ROUTE_DISCOVERY_HOP if call is not None and call.call_class == "metadata_discovery" else ROUTE_EXECUTE
    return LoopDecision(
        route=route,
        reason=f"recipe call ready: {decision.call_id}",
        next_tool=decision.call_id,
        sufficiency="needs_more",
        missing=decision.unresolved_evidence_keys,
    )


def _flatten_requirements(requirements: dict[str, list[str]]) -> list[str]:
    flat: list[str] = []
    for produces in requirements.values():
        for item in produces:
            if item not in flat:
                flat.append(item)
    return flat
