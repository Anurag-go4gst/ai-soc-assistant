"""Unified control-plane trace assembly.

The trace builder is packaging-only: it must not call RAG, MCP, SPL validation,
MITRE resolution, or any LLM path.
"""

from __future__ import annotations

from typing import Any

from app.chat.debug_summary import (
    project_auth0_debug,
    project_evidence_state_debug,
    project_investigation_outcome_debug,
    redact_resolved_query,
)
from app.schemas.responses import PlaceholderResponse
from app.planner.recipe_registry import get_recipe
from app.spl.spl_artifact_trace_projection import build_spl_artifact_handoff_summary
from app.spl.spl_provenance_trace import build_spl_provenance_summary
from app.chat.understanding_provenance import build_understanding_provenance
from app.governance.trace_authority import (
    TIER_ADVISORY,
    TIER_DIAGNOSTIC,
    TIER_PLANNING,
    attach_authority_tier,
    authority_label,
    build_control_plane_authority_index,
)

_SECRET_KEYS = (
    "secret",
    "password",
    "passwd",
    "api_key",
    "apikey",
    "_token",
    "dsn",
    "bearer_token",
    "access_token",
    "auth_token",
    "credential",
)


def build_control_plane_trace(
    state: dict[str, Any],
    *,
    source_evidence: list[dict[str, Any]] | None = None,
    context_sufficiency: dict[str, Any] | None = None,
    synthesis_mode: str | None = None,
    answer_guard: dict[str, Any] | None = None,
    node_trace: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    route_shadow = state.get("route_plan_shadow") if isinstance(state.get("route_plan_shadow"), dict) else {}
    rag = state.get("soc_kb_retrieval") if isinstance(state.get("soc_kb_retrieval"), dict) else None
    spl_validation = state.get("spl_validation") if isinstance(state.get("spl_validation"), dict) else None
    candidate_spl = state.get("candidate_spl") if isinstance(state.get("candidate_spl"), dict) else None
    spl_draft_preview = state.get("spl_draft_preview") if isinstance(state.get("spl_draft_preview"), dict) else None
    execution = state.get("execution") if isinstance(state.get("execution"), dict) else None
    routed = state.get("routed") if isinstance(state.get("routed"), dict) else {}
    routing_provenance = (
        routed.get("routing_provenance")
        if isinstance(routed.get("routing_provenance"), dict)
        else None
    )

    advisory = state.get("llm_intent_advisory")
    if hasattr(advisory, "model_dump"):
        advisory = advisory.model_dump()
    trace = {
        "routing_provenance": routing_provenance,
        "planning_decision": state.get("planning_decision"),
        "query_to_intent": state.get("query_to_intent"),
        "llm_intent_advisory": advisory,
        "shape_advisory": state.get("shape_advisory")
        if isinstance(state.get("shape_advisory"), dict)
        else None,
        "evidence_plan": state.get("evidence_plan"),
        "route_adjudication": state.get("route_adjudication"),
        "llm_plan_validation": state.get("llm_plan_validation"),
        "tool_plan": _tool_plan(state),
        "mitre_registry_metadata": _mitre_registry_metadata(state.get("mitre_decision")),
        "mitre_branch_result": state.get("mitre_branch_result"),
        "mitre_decision": state.get("mitre_decision"),
        "rag_trace": _rag_trace(rag),
        "candidate_spl_generation": _candidate_spl_generation_trace(candidate_spl, spl_validation),
        "spl_artifact_handoff_summary": attach_authority_tier(
            build_spl_artifact_handoff_summary(
                candidate_spl=candidate_spl,
                spl_validation=spl_validation,
                spl_draft_preview=spl_draft_preview,
            ),
            tier=TIER_DIAGNOSTIC,
            note="SPL degrade-chain read model only; not execution authority.",
        ),
        "spl_provenance": build_spl_provenance_summary(
            candidate_spl,
            spl_validation,
            _budget_records(state),
        ),
        "spl_slot_binding": _spl_slot_binding_trace(spl_validation),
        "mcp_execution": _mcp_trace(execution),
        "sufficiency": context_sufficiency,
        "synthesis_mode": {"mode": synthesis_mode},
        "answer_contract": state.get("answer_contract"),
        "answer_contract_v2": state.get("answer_contract"),
        "final_answer_validation": state.get("final_answer_validation"),
        "answer_guard": answer_guard,
        "source_evidence_refs": [
            str(item.get("evidence_id"))
            for item in (source_evidence or [])
            if isinstance(item, dict) and item.get("evidence_id")
        ],
        "precondition_evaluation": route_shadow.get("precondition_evaluation"),
        "resource_planner": _resource_planner_trace(state),
        "llm_advisory_trace": _llm_advisory_trace(state),
        "spl_authoring_trace": _spl_authoring_trace(state),
        "intent_dispatch": state.get("intent_dispatch")
        if isinstance(state.get("intent_dispatch"), dict)
        else None,
        "pipeline_dispatch": state.get("pipeline_dispatch")
        if isinstance(state.get("pipeline_dispatch"), dict)
        else None,
        "resolved_query": redact_resolved_query(
            state.get("resolved_query_contract")
            if isinstance(state.get("resolved_query_contract"), dict)
            else None
        ),
        "understanding_provenance": build_understanding_provenance(
            resolved_query_contract=state.get("resolved_query_contract"),
            route_adjudication=state.get("route_adjudication")
            if isinstance(state.get("route_adjudication"), dict)
            else None,
            routed=routed,
            candidate_spl=candidate_spl,
            spl_validation=spl_validation,
        ),
        "evidence_state": project_evidence_state_debug(
            state.get("evidence_state") if isinstance(state.get("evidence_state"), dict) else None
        ),
        "investigation_outcome": project_investigation_outcome_debug(
            state.get("investigation_outcome")
            if isinstance(state.get("investigation_outcome"), dict)
            else None
        ),
        "session_role": state.get("session_role")
        if isinstance(state.get("session_role"), str)
        else None,
        "spl_source_resolve": state.get("spl_source_resolve")
        if isinstance(state.get("spl_source_resolve"), dict)
        else None,
        # Item 2.3/2.4 (2026-07-03): the derived, risk-classified artifact
        # consumed by graph_node_execution — surfaced here so the analyst-visible
        # trace/debug API carries the full vigilance audit trail (risk_tier,
        # checks_passed/failed, blocked_reason), not just the execution outcome.
        "llm_derived_spl_artifact": state.get("llm_derived_spl_artifact")
        if isinstance(state.get("llm_derived_spl_artifact"), dict)
        else None,
        # O5c multi-call lineage (item 3.3, 2026-07-03): per-call records for a
        # recipe-driven turn (item 3.1/3.2), enriched with the call's class and
        # declared evidence keys from the recipe definition, plus the raw
        # deterministic loop verdict (mcp_loop, shared by both the chronology
        # and recipe-driven hub paths — already written by items already shipped).
        "mcp_calls": _mcp_calls_trace(state),
        "mcp_loop": state.get("mcp_loop")
        if isinstance(state.get("mcp_loop"), dict)
        else None,
        "run_shape_transition": _run_shape_transition_trace(state, context_sufficiency),
        "mcp_tool_readiness": _mcp_tool_readiness_trace(state, execution),
        # Item 5.4 (2026-07-03): advisory grounding assembled from the
        # CanonicalFacts spine — row-derived evidence citations with lineage
        # when evidence was executed, an honest limitation when it wasn't.
        # Never authority; surfaced here so it's genuinely consumed/inspectable
        # rather than dead-ended on internal pipeline state.
        "grounding_block": state.get("grounding_block")
        if isinstance(state.get("grounding_block"), dict)
        else None,
        "decision_log": _decision_log_trace(state),
    }
    run_contract = state.get("run_contract") if isinstance(state.get("run_contract"), dict) else None
    final_evidence_gate = (
        state.get("final_evidence_gate") if isinstance(state.get("final_evidence_gate"), dict) else None
    )
    if run_contract is not None:
        trace["run_contract"] = attach_authority_tier(
            run_contract,
            tier="AUTHORITATIVE",
            note="RunContract owns final-run public posture.",
        )
    if final_evidence_gate is not None:
        trace["final_evidence_gate"] = attach_authority_tier(
            final_evidence_gate,
            tier="AUTHORITATIVE",
            note="FinalEvidenceGate owns evidence-derived permissions.",
        )
    slot_projection = None
    if isinstance(candidate_spl, dict):
        slot_projection = candidate_spl.get("slot_constraint_projection")
    if isinstance(slot_projection, dict):
        trace["slot_constraint_projection"] = attach_authority_tier(
            slot_projection,
            tier=TIER_PLANNING,
            note="Final SPL slot/constraint projection for the turn.",
        )
    trace["trace_authority_index"] = build_control_plane_authority_index(
        has_run_contract=run_contract is not None,
        has_final_evidence_gate=final_evidence_gate is not None,
    )
    trace["route_plan_shadow_authority"] = authority_label(
        TIER_DIAGNOSTIC,
        "Route plan shadow is diagnostic only; not final route authority.",
    )
    if node_trace:
        trace["node_trace"] = node_trace
    return _redact(trace)


def _run_shape_transition_trace(
    state: dict[str, Any],
    context_sufficiency: dict[str, Any] | None,
) -> dict[str, Any]:
    """Initial vs final governed run shape — no chain-of-thought."""
    evidence_plan = state.get("evidence_plan") if isinstance(state.get("evidence_plan"), dict) else {}
    planning = state.get("planning_decision") if isinstance(state.get("planning_decision"), dict) else {}
    q2i = state.get("query_to_intent") if isinstance(state.get("query_to_intent"), dict) else {}
    sufficiency = context_sufficiency if isinstance(context_sufficiency, dict) else {}
    answer_contract = state.get("answer_contract") if isinstance(state.get("answer_contract"), dict) else {}

    initial = (
        str(planning.get("answer_mode") or "").strip()
        or str(q2i.get("answer_mode") or "").strip()
        or str((evidence_plan.get("initial_answer_mode") or "")).strip()
        or None
    )
    final = (
        str(sufficiency.get("answer_mode") or "").strip()
        or str(evidence_plan.get("answer_mode") or "").strip()
        or str(answer_contract.get("answer_mode") or "").strip()
        or None
    )
    if not final:
        rqc = state.get("resolved_query_contract") if isinstance(state.get("resolved_query_contract"), dict) else {}
        intent_family = str(rqc.get("intent_family") or "").strip()
        if intent_family in {"live_investigation", "guided_investigation", "hybrid_investigation_plus_policy"}:
            final = "live_investigation" if intent_family == "live_investigation" else intent_family
        elif intent_family in {"spl_generation_only", "spl_generation_and_run"}:
            final = "spl_utility_authoring"
    reasons = evidence_plan.get("reasons") if isinstance(evidence_plan.get("reasons"), list) else []
    changed = bool(initial and final and initial != final)
    authority = None
    if changed:
        authority = "evidence_plan" if evidence_plan.get("answer_mode") else "context_sufficiency"
    elif final:
        authority = "evidence_plan" if evidence_plan.get("answer_mode") == final else "context_sufficiency"
    return attach_authority_tier(
        {
            "schema_version": "run_shape_transition_v1",
            "initial_run_shape": initial,
            "final_run_shape": final,
            "changed": changed,
            "change_reasons": [str(item) for item in reasons][:12],
            "authority": authority,
        },
        tier=TIER_PLANNING,
        note="Governed run-shape packaging only; not execution authority.",
    )


def _mcp_tool_lifecycle_state(
    *,
    planned: bool,
    attempted: bool,
    executed: bool,
    succeeded: bool,
    failed: bool,
    skipped: bool,
) -> str:
    if succeeded:
        return "SUCCEEDED"
    if failed:
        return "FAILED"
    if executed:
        return "EXECUTED"
    if attempted:
        return "ATTEMPTED"
    if skipped:
        return "SKIPPED"
    if planned:
        return "PLANNED"
    return "SKIPPED"


def _mcp_tool_readiness_trace(
    state: dict[str, Any],
    execution: dict[str, Any] | None,
) -> dict[str, Any]:
    """Planned MCP tools with PLANNED/ATTEMPTED/EXECUTED/... lifecycle states."""
    tools: list[dict[str, Any]] = []
    approval = state.get("investigation_approval") if isinstance(state.get("investigation_approval"), dict) else {}
    validated = approval.get("validated_plan") if isinstance(approval.get("validated_plan"), dict) else {}
    bindings = validated.get("capability_bindings") if isinstance(validated.get("capability_bindings"), list) else []
    execution = execution if isinstance(execution, dict) else {}
    selected_server = str(execution.get("selected_mcp_server") or "").strip() or None
    selected_tool = str(execution.get("selected_mcp_tool") or "").strip() or None
    exec_status = str(execution.get("status") or "").strip().lower()
    block_reason = str(execution.get("block_reason") or "").strip() or None
    call_grant = execution.get("call_grant") if isinstance(execution.get("call_grant"), dict) else {}
    pending = (
        execution.get("pending_execution_confirmation")
        if isinstance(execution.get("pending_execution_confirmation"), dict)
        else {}
    )
    pending_grant = pending.get("call_grant") if isinstance(pending.get("call_grant"), dict) else {}
    grant = call_grant or pending_grant
    attempted = exec_status not in {"", "skipped", "not_started", "none"}
    executed = exec_status in {"ok", "partial", "empty", "failed", "timeout", "denied", "error"}
    succeeded = exec_status in {"ok", "partial", "empty"}
    failed = exec_status in {"failed", "timeout", "denied", "error"}
    skipped = exec_status in {"skipped", "not_started", "none", ""} or bool(block_reason)
    execution_eligible = bool(execution.get("execution_eligible") is True)

    for binding in bindings:
        if not isinstance(binding, dict):
            continue
        capability_id = str(binding.get("capability_id") or "").strip()
        server = None
        tool = None
        if capability_id.startswith("mcp:"):
            parts = capability_id.split(":")
            if len(parts) >= 3:
                server = parts[1] or None
                tool = parts[2] or None
        availability = str(binding.get("availability") or "").strip() or None
        planned = True
        tool_attempted = bool(attempted and selected_tool and tool and selected_tool == tool)
        tool_executed = bool(executed and tool_attempted)
        tool_succeeded = bool(succeeded and tool_attempted)
        tool_failed = bool(failed and tool_attempted)
        tool_skipped = (not tool_attempted) and (
            skipped or availability in {"unavailable", "blocked"} or bool(block_reason)
        )
        purpose = str(binding.get("purpose") or "").strip() or None
        planned_arguments = (
            binding.get("planned_arguments")
            if isinstance(binding.get("planned_arguments"), dict)
            else None
        )
        argument_template = (
            binding.get("argument_template")
            if isinstance(binding.get("argument_template"), dict)
            else None
        )
        unresolved = [
            str(item)
            for item in (binding.get("unresolved_arguments") or [])
            if str(item).strip()
        ]
        auth_posture = str(binding.get("authorization_posture") or "exact_call_auth0_grant_required")
        if tool_attempted and grant.get("fingerprint"):
            authorization_status = "granted" if exec_status not in {"denied"} else "denied"
        elif unresolved or availability != "available":
            authorization_status = "not_requested"
        elif planned_arguments:
            authorization_status = "pending_exact_call_grant"
        else:
            authorization_status = "blocked_unresolved_arguments" if unresolved else "not_requested"

        entry: dict[str, Any] = {
            "server": server,
            "tool": tool,
            "capability_id": capability_id or None,
            "purpose": purpose,
            "authorization_required": auth_posture,
            "authorization_status": authorization_status,
            "execution_eligible": False if not tool_attempted else execution_eligible,
            "availability": availability,
            "access_mode": binding.get("access_mode"),
            "read_write_classification": binding.get("read_write_classification"),
            "lifecycle_state": _mcp_tool_lifecycle_state(
                planned=planned,
                attempted=tool_attempted,
                executed=tool_executed,
                succeeded=tool_succeeded,
                failed=tool_failed and not tool_succeeded,
                skipped=tool_skipped,
            ),
            "planned": planned,
            "attempted": tool_attempted,
            "executed": tool_executed,
            "succeeded": tool_succeeded,
            "failed": tool_failed and not tool_succeeded,
            "skipped": tool_skipped,
            "result": exec_status or None,
            "skip_or_block_reason": block_reason
            or (f"capability_{availability}" if availability and availability != "available" else None),
        }
        if planned_arguments is not None:
            entry["planned_arguments"] = planned_arguments
            if grant.get("canonical_arguments_hash"):
                entry["canonical_arguments_hash"] = grant.get("canonical_arguments_hash")
        if argument_template is not None:
            entry["argument_template"] = argument_template
        if unresolved:
            entry["unresolved_arguments"] = unresolved
        tools.append(entry)

    if not tools and (selected_tool or selected_server or block_reason or exec_status):
        purpose = str(execution.get("execution_intent") or "").strip() or None
        tools.append(
            {
                "server": selected_server,
                "tool": selected_tool,
                "capability_id": None,
                "purpose": purpose,
                "authorization_required": "exact_call_auth0_grant_required",
                "authorization_status": "granted" if grant.get("fingerprint") else "not_requested",
                "execution_eligible": execution_eligible,
                "availability": str(execution.get("tool_selection_status") or "") or None,
                "access_mode": None,
                "lifecycle_state": _mcp_tool_lifecycle_state(
                    planned=bool(selected_tool or selected_server),
                    attempted=attempted,
                    executed=executed,
                    succeeded=succeeded,
                    failed=failed,
                    skipped=skipped,
                ),
                "planned": bool(selected_tool or selected_server),
                "attempted": attempted,
                "executed": executed,
                "succeeded": succeeded,
                "failed": failed,
                "skipped": skipped,
                "result": exec_status or None,
                "skip_or_block_reason": block_reason,
            }
        )

    workflow = state.get("workflow_plan") if isinstance(state.get("workflow_plan"), dict) else {}
    return attach_authority_tier(
        {
            "schema_version": "mcp_tool_readiness_v2",
            "required_sources": list(workflow.get("required_sources") or []),
            "missing_sources": list(workflow.get("missing_sources") or []),
            "tools": tools,
        },
        tier=TIER_DIAGNOSTIC,
        note="MCP planned-vs-attempted readiness for harness validation when live MCP is unavailable.",
    )


def _mcp_calls_trace(state: dict[str, Any]) -> list[dict[str, Any]]:
    """Per-call lineage for a recipe-driven turn (item 3.3): each accumulated
    mcp_call_records entry enriched with the call's class and declared
    evidence keys from the recipe definition. Empty list — never None — when
    no recipe is active (the vast majority of turns today, since item 3.2's
    selector is the only thing that ever sets mcp_recipe_id)."""
    raw_records = state.get("mcp_call_records")
    if not isinstance(raw_records, list) or not raw_records:
        return []
    recipe_id = state.get("mcp_recipe_id")
    recipe = None
    if isinstance(recipe_id, str) and recipe_id:
        recipe = get_recipe(recipe_id)
    calls: list[dict[str, Any]] = []
    for record in raw_records:
        if not isinstance(record, dict):
            continue
        call_id = str(record.get("call_id") or "")
        call_def = recipe.call_by_id(call_id) if recipe is not None else None
        outcome = record.get("outcome")
        # A call only resolves its declared evidence keys on a resolving
        # outcome (ok/partial/empty) — a failed/blocked/timeout/denied call
        # resolved nothing, matching orchestration_scheduler's own definition.
        resolved = (
            list(call_def.produces_evidence_keys)
            if call_def is not None and outcome in ("ok", "partial", "empty")
            else []
        )
        calls.append(
            {
                "call_id": call_id,
                "call_class": call_def.call_class if call_def is not None else None,
                "outcome": outcome,
                "evidence_keys_resolved": resolved,
                "result_count": record.get("result_count"),
                "block_reason": record.get("error_type"),
            }
        )
    return calls


def _spl_authoring_trace(state: dict[str, Any]) -> dict[str, Any] | None:
    q2i = state.get("query_to_intent") if isinstance(state.get("query_to_intent"), dict) else {}
    signals = q2i.get("query_signals") if isinstance(q2i.get("query_signals"), dict) else {}
    trace = signals.get("spl_authoring_trace")
    if not isinstance(trace, dict) or not trace:
        return None
    return attach_authority_tier(
        trace,
        tier=TIER_PLANNING,
        note="Explicit SPL authoring detection and clarification override trace.",
    )


def _decision_log_trace(state: dict[str, Any]) -> list[dict[str, Any]] | None:
    from app.chat.decision_record import decision_log_for_trace

    records = decision_log_for_trace(state)
    if not records:
        return None
    wrapped = attach_authority_tier(
        {"records": records, "record_count": len(records)},
        tier=TIER_DIAGNOSTIC,
        note="Append-only planner hierarchy audit trail; advisory packaging only.",
    )
    if isinstance(wrapped, dict):
        return wrapped.get("records") if isinstance(wrapped.get("records"), list) else records
    return records


def patch_control_plane_trace_decision_log(
    response: PlaceholderResponse,
    state: dict[str, Any],
) -> PlaceholderResponse:
    """Sync analyst-visible ``decision_log`` after post-compose graph hops."""
    records = _decision_log_trace(state)
    if not records:
        return response
    trace = response.control_plane_trace
    trace_payload = dict(trace) if isinstance(trace, dict) else {}
    trace_payload["decision_log"] = records
    return response.model_copy(update={"control_plane_trace": trace_payload})


def _resource_planner_trace(state: dict[str, Any]) -> dict[str, Any] | None:
    evidence_plan = state.get("evidence_plan") if isinstance(state.get("evidence_plan"), dict) else {}
    resource_plan = evidence_plan.get("resource_plan") if isinstance(evidence_plan.get("resource_plan"), dict) else {}
    provenance = resource_plan.get("provenance") if isinstance(resource_plan.get("provenance"), dict) else {}
    decisions = provenance.get("resource_decisions")
    if isinstance(decisions, dict):
        return attach_authority_tier(
            {
                "source": "evidence_plan.resource_plan.provenance.resource_decisions",
                "resource_decisions": decisions,
            },
            tier=TIER_PLANNING,
            note="Composed ResourcePlan resource decisions.",
        )

    planning = state.get("planning_decision") if isinstance(state.get("planning_decision"), dict) else {}
    summary = planning.get("resource_plan_summary")
    if isinstance(summary, dict):
        return attach_authority_tier(
            {
                "source": "planning_decision.resource_plan_summary",
                "resource_decisions": summary,
            },
            tier=TIER_PLANNING,
            note="Planning-decision ResourcePlan summary.",
        )
    return None


def _budget_records(state: dict[str, Any]) -> list[dict[str, Any]] | None:
    budget = state.get("llm_turn_budget")
    records = getattr(budget, "records", None)
    if isinstance(records, list):
        return [dict(item) for item in records if isinstance(item, dict)]
    if isinstance(budget, dict):
        raw = budget.get("records")
        if isinstance(raw, list):
            return [dict(item) for item in raw if isinstance(item, dict)]
    return None


def _llm_advisory_trace(state: dict[str, Any]) -> dict[str, Any]:
    routed = state.get("routed") if isinstance(state.get("routed"), dict) else {}
    route_shadow = state.get("route_plan_shadow") if isinstance(state.get("route_plan_shadow"), dict) else {}
    comparison = routed.get("comparison") if isinstance(routed.get("comparison"), dict) else {}
    route_advisory = routed.get("llm_semantic_advisory")
    if not isinstance(route_advisory, dict):
        route_advisory = comparison.get("llm") if isinstance(comparison.get("llm"), dict) else {}
    llm_shadow = routed.get("llm_shadow") if isinstance(routed.get("llm_shadow"), dict) else {}
    llm_shadow_metadata = llm_shadow.get("metadata") if isinstance(llm_shadow.get("metadata"), dict) else {}
    query_to_intent = state.get("query_to_intent") if isinstance(state.get("query_to_intent"), dict) else {}
    intent_advisory = query_to_intent.get("llm_intent_advisory")
    if not isinstance(intent_advisory, dict):
        state_advisory = state.get("llm_intent_advisory")
        if hasattr(state_advisory, "model_dump"):
            intent_advisory = state_advisory.model_dump()
        elif isinstance(state_advisory, dict):
            intent_advisory = state_advisory
        else:
            intent_advisory = {}
    route_candidate = (
        route_advisory.get("llm_selected_skill_candidate")
        or route_advisory.get("skill")
        or route_advisory.get("candidate_skill")
    )
    if llm_shadow_metadata.get("mock") is True:
        route_candidate = None
    intent_candidate = (
        intent_advisory.get("intent_family_candidate")
        or intent_advisory.get("intent_family")
        or intent_advisory.get("candidate_intent_family")
    )
    intent_status = str(query_to_intent.get("llm_intent_assist_status") or "skipped")
    selected_by = str(routed.get("selected_by") or "")
    final_source = str(state.get("final_answer_source") or "")
    narration_used = final_source in {"live_llm_synthesis", "llm_narration"}
    attempted = intent_status not in {"", "skipped"}
    llm_called = bool(route_shadow.get("llm_called") or intent_advisory.get("llm_called"))
    candidate_present = bool(route_candidate or intent_candidate)
    dropped_reasons = list(
        dict.fromkeys(
            [str(reason) for reason in route_shadow.get("llm_candidate_dropped_reasons") or []]
            + [str(reason) for reason in intent_advisory.get("dropped_reasons") or []]
        )
    )
    advisory_used = bool(llm_called or candidate_present)
    overridden = bool(
        candidate_present
        and (
            selected_by not in {"llm_advisory_validated", "llm_assisted_semantic"}
            or intent_status in {"rejected", "corrected"}
            or state.get("answer_guard", {}).get("guard_status") == "blocked"
        )
    )
    scheduling = (
        intent_advisory.get("scheduling_trace")
        if isinstance(intent_advisory.get("scheduling_trace"), dict)
        else {}
    )
    payload = {
        "llm_advisory_attempted": attempted,
        "llm_called": llm_called,
        "llm_candidate_present": candidate_present,
        "llm_advisory_used": advisory_used,
        "llm_route_candidate": str(route_candidate) if route_candidate else None,
        "llm_intent_candidate": str(intent_candidate) if intent_candidate else None,
        "llm_dropped_reasons": dropped_reasons,
        "llm_narration_used": narration_used,
        "llm_overridden_by_policy": overridden,
        "llm_advisory_status": scheduling.get("llm_advisory_status"),
        "llm_advisory_timed_out": scheduling.get("llm_advisory_timed_out"),
        "llm_advisory_deferred": scheduling.get("llm_advisory_deferred"),
        "llm_advisory_budget_ms": scheduling.get("llm_advisory_budget_ms"),
        "llm_advisory_fallback_reason": scheduling.get("llm_advisory_fallback_reason"),
        "advisory_classification_source": scheduling.get("advisory_classification_source"),
        "deterministic_fallback_used": scheduling.get("deterministic_fallback_used"),
        "intent_advisor_bound_reason": scheduling.get("intent_advisor_bound_reason"),
        "intent_advisor_bound_timeout_ms": scheduling.get("intent_advisor_bound_timeout_ms"),
    }
    return attach_authority_tier(
        payload,
        tier=TIER_ADVISORY,
        note="LLM dropped reasons are advisory; not final routing failure.",
    )


def _candidate_spl_generation_trace(
    candidate_spl: dict[str, Any] | None,
    spl_validation: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if not candidate_spl and not spl_validation:
        return None
    validation = spl_validation or {}
    candidate = candidate_spl or {}
    utility_trace = candidate.get("utility_spl_draft_trace") or validation.get("utility_spl_draft_trace")
    utility_trace = utility_trace if isinstance(utility_trace, dict) else {}
    payload = {
        "generation_mode": candidate.get("generation_mode"),
        "selected_candidate_spl_provider": validation.get("selected_candidate_spl_provider")
        or candidate.get("selected_candidate_spl_provider"),
        "fallback_required": validation.get("fallback_required") or candidate.get("fallback_required"),
        "candidate_spl_generated": candidate.get("candidate_spl_generated"),
        "validation_required": candidate.get("validation_required"),
        "execution_eligible": candidate.get("execution_eligible"),
        "llm_supported": validation.get("llm_supported") or candidate.get("llm_supported"),
        "llm_fallback_used": validation.get("llm_fallback_used") or candidate.get("llm_fallback_used"),
        "llm_fallback_status": validation.get("llm_fallback_status") or candidate.get("llm_fallback_status"),
        "llm_fallback_reason": validation.get("llm_fallback_reason") or candidate.get("llm_fallback_reason"),
        "llm_model": validation.get("llm_model") or candidate.get("llm_model"),
        "llm_latency_ms": validation.get("llm_latency_ms") or candidate.get("llm_latency_ms"),
        "approved": validation.get("approved"),
        "normalized_spl_available": bool(validation.get("normalized_spl")),
    }
    for key in (
        "llm_spl_draft_enabled",
        "llm_spl_draft_requested",
        "llm_spl_draft_completed",
        "llm_spl_draft_timed_out",
        "llm_spl_draft_used",
        "llm_spl_draft_skipped_reason",
        "utility_spl_draft_timeout_seconds",
        "final_raw_spl_source",
        "deterministic_skeleton_used",
        "final_spl_authority",
        "postprocessor_applied",
        "review_only_spl_postprocessor_trace",
    ):
        if key in utility_trace:
            payload[key] = utility_trace.get(key)
    if "llm_spl_draft_skipped_reason" not in payload and utility_trace.get("llm_spl_draft_dropped_reason"):
        payload["llm_spl_draft_skipped_reason"] = utility_trace.get("llm_spl_draft_dropped_reason")
    if candidate.get("review_only_spl_postprocessor_trace") is not None:
        payload["review_only_spl_postprocessor_trace"] = candidate.get("review_only_spl_postprocessor_trace")
    return payload


def _tool_plan(state: dict[str, Any]) -> dict[str, Any] | None:
    workflow = state.get("workflow_plan")
    if not isinstance(workflow, dict):
        return None
    return {
        "skill": workflow.get("skill"),
        "tool_plan": workflow.get("tool_plan"),
        "execution_enabled": workflow.get("execution_enabled"),
        "required_sources": workflow.get("required_sources"),
        "missing_sources": workflow.get("missing_sources"),
    }


def _mitre_registry_metadata(mitre_decision: Any) -> dict[str, Any] | None:
    if not isinstance(mitre_decision, dict):
        return None
    metadata = mitre_decision.get("registry_metadata")
    return metadata if isinstance(metadata, dict) else None


def _rag_trace(rag: dict[str, Any] | None) -> dict[str, Any]:
    if not rag:
        return {"match_status": "not_run"}
    return {
        "match_status": rag.get("match_status") or rag.get("status") or rag.get("retrieval_status"),
        "retrieval_status": rag.get("retrieval_status"),
        "rag_skipped_for_spl_utility_authoring": rag.get("rag_skipped_for_spl_utility_authoring"),
        "reasons": rag.get("reasons"),
        "retrieval_backend": rag.get("retrieval_backend"),
        "collection_ids": rag.get("collection_ids"),
        "evidence_refs": rag.get("evidence_refs"),
        "missing_sources": rag.get("missing_sources"),
    }


def _spl_slot_binding_trace(spl_validation: dict[str, Any] | None) -> dict[str, Any] | None:
    if not spl_validation:
        return None
    reasons = [str(item) for item in spl_validation.get("reject_reasons") or []]
    missing = [item.removeprefix("missing_binding:") for item in reasons if item.startswith("missing_binding:")]
    return attach_authority_tier(
        {
            "validated": "slot_binding_validated" in (spl_validation.get("warnings") or [])
            or bool(missing),
            "missing_bindings": missing,
            "approved": spl_validation.get("approved"),
            "policy_version": spl_validation.get("policy_version"),
            "reject_reasons": [str(item) for item in spl_validation.get("reject_reasons") or []],
        },
        tier=TIER_DIAGNOSTIC,
        note="Validator reject details are diagnostic unless projected by RunContract.",
    )


def _mcp_trace(execution: dict[str, Any] | None) -> dict[str, Any] | None:
    if not execution:
        return None
    return {
        "status": execution.get("status"),
        "execution_intent": execution.get("execution_intent"),
        "tool_selection_status": execution.get("tool_selection_status"),
        "block_reason": execution.get("block_reason"),
        "selected_mcp_server": execution.get("selected_mcp_server"),
        "selected_mcp_tool": execution.get("selected_mcp_tool"),
        "evidence_source": execution.get("evidence_source"),
        "result_count": execution.get("result_count") if isinstance(execution.get("result_count"), int) else None,
        "call_grant_consumed": bool(execution.get("call_grant_consumed")),
        "auth0": project_auth0_debug(execution),
    }


def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            key_str = str(key)
            if _is_secret_key(key_str):
                redacted[key_str] = "[REDACTED]"
            else:
                redacted[key_str] = _redact(item)
        return redacted
    if isinstance(value, list):
        return [_redact(item) for item in value]
    if isinstance(value, str) and any(marker in value.lower() for marker in ("bearer ", "password=", "token=")):
        return "[REDACTED]"
    return value


def _is_secret_key(key: str) -> bool:
    lowered = key.lower()
    return any(secret in lowered for secret in _SECRET_KEYS)
