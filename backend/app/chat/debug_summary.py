"""One-screen debug summary for COE trace bundles and trace list rows.

Answers the common analyst questions (why no LLM, why this route, SPL/MCP/HIL)
without spelunking nested control_plane_trace JSON.
"""

from __future__ import annotations

import hashlib
from typing import Any

from app.chat.final_output_trace import build_final_output_trace

_MAX_SKIPPED_ROLES = 7
_SEMANTIC_T4_NOTE_ALLOWLIST = frozenset(
    {
        "llm_assist_timed_out",
        "llm_provider_unavailable",
        "llm_model_slot_busy",
        "semantic_t4_llm_disabled",
        "semantic_t4_no_provider_configured",
    }
)


def build_debug_summary(
    *,
    payload: dict[str, Any] | None = None,
    control_plane_trace: dict[str, Any] | None = None,
    spl_validation: dict[str, Any] | None = None,
    run_contract: dict[str, Any] | None = None,
    human_review: dict[str, Any] | None = None,
    execution: dict[str, Any] | None = None,
    llm_budget_records: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Assemble routing / LLM / SPL / MCP / HIL explainability for debug surfaces."""
    base = payload if isinstance(payload, dict) else {}
    cp = control_plane_trace if isinstance(control_plane_trace, dict) else base.get("control_plane_trace")
    cp = cp if isinstance(cp, dict) else {}
    spl_validation = (
        spl_validation
        if isinstance(spl_validation, dict)
        else base.get("spl_validation") if isinstance(base.get("spl_validation"), dict) else {}
    )
    run_contract = (
        run_contract
        if isinstance(run_contract, dict)
        else base.get("run_contract") if isinstance(base.get("run_contract"), dict) else {}
    )
    human_review = (
        human_review
        if isinstance(human_review, dict)
        else base.get("human_review") if isinstance(base.get("human_review"), dict) else {}
    )
    execution = (
        execution
        if isinstance(execution, dict)
        else base.get("execution") if isinstance(base.get("execution"), dict) else {}
    )
    candidate_spl = base.get("candidate_spl") if isinstance(base.get("candidate_spl"), dict) else {}

    records = _budget_records(cp, llm_budget_records)
    live_records = [item for item in records if item.get("outcome") == "completed"]
    live_roles = list(dict.fromkeys(str(item["role"]) for item in live_records if item.get("role")))

    routing = _routing_block(base, cp, run_contract)
    llm_block = _llm_block(cp, candidate_spl, spl_validation, records, live_records, live_roles)
    spl_block = _spl_block(candidate_spl, spl_validation, cp)
    mcp_block = _mcp_block(execution, cp, run_contract)
    hil_block = _hil_block(human_review, run_contract, spl_validation)

    output_block = build_final_output_trace(base) if base else {}
    intent_block = _intent_block(base, cp)
    dispatch_block = _dispatch_block(base, cp)
    contract_raw = base.get("resolved_query_contract")
    if not isinstance(contract_raw, dict):
        contract_raw = cp.get("resolved_query")
    resolved_query_block = redact_resolved_query(contract_raw)
    schedule_block = _schedule_provenance_block(base, cp)

    return {
        "routing": routing,
        "llm": llm_block,
        "spl": spl_block,
        "mcp": mcp_block,
        "hil": hil_block,
        "output": output_block,
        "intent": intent_block,
        "dispatch": dispatch_block,
        "resolved_query": resolved_query_block,
        "schedule": schedule_block,
    }


def llm_live_calls_from_payload(payload: dict[str, Any]) -> int:
    """Count completed live model hops (debug badge authority)."""
    cp = payload.get("control_plane_trace")
    if not isinstance(cp, dict):
        return 0
    return sum(1 for item in _budget_records(cp, None) if item.get("outcome") == "completed")


def routing_list_fields(debug_summary: dict[str, Any] | None) -> dict[str, Any]:
    """Flatten routing slice for trace list rows."""
    routing = (debug_summary or {}).get("routing") if isinstance(debug_summary, dict) else {}
    if not isinstance(routing, dict):
        routing = {}
    patterns = routing.get("matched_patterns")
    first_pattern = patterns[0] if isinstance(patterns, list) and patterns else None
    llm = (debug_summary or {}).get("llm") if isinstance(debug_summary, dict) else {}
    spl_path = llm.get("spl_path") if isinstance(llm, dict) else None
    return {
        "match_path": routing.get("match_path"),
        "use_case_id": routing.get("use_case_id"),
        "question_ref": routing.get("question_ref"),
        "matched_pattern": first_pattern,
        "spl_path": spl_path,
    }


def redact_resolved_query(raw: dict[str, Any] | None) -> dict[str, Any]:
    """IDs/status only. No skill, no execution authority, no entities, no raw query."""
    source = raw if isinstance(raw, dict) else {}
    required = source.get("required_capabilities")
    prohibited = source.get("prohibited_capabilities")
    provenance = source.get("provenance") if isinstance(source.get("provenance"), dict) else {}
    semantic = provenance.get("semantic_t4") if isinstance(provenance.get("semantic_t4"), dict) else None
    if semantic is None and isinstance(source.get("semantic_t4"), dict):
        semantic = source.get("semantic_t4")
    semantic_block = None
    if semantic is not None:
        reasons = semantic.get("rejected_reasons")
        notes = semantic.get("notes")
        elapsed = semantic.get("elapsed_ms")
        semantic_block = {
            "invoked": bool(semantic.get("invoked")),
            "accepted": bool(semantic.get("accepted")),
            "timed_out": bool(semantic.get("timed_out")),
            # Plan 7 D1: the class of failure, so a trace can tell "the model was
            # slow" from "the endpoint was unreachable".
            "failure_kind": semantic.get("failure_kind"),
            "elapsed_ms": int(elapsed) if isinstance(elapsed, (int, float)) else None,
            "rejected_reasons": [str(item) for item in reasons][:8] if isinstance(reasons, list) else [],
            # Field names only. Lets a measurement separate "the model answered"
            # from "deterministic validation kept any of it".
            "proposed_fields": [str(item) for item in semantic.get("proposed_fields") or []][:16],
            "accepted_fields": [str(item) for item in semantic.get("accepted_fields") or []][:16],
            "notes": [
                str(item)
                for item in notes
                if isinstance(notes, list) and str(item) in _SEMANTIC_T4_NOTE_ALLOWLIST
            ][:8],
        }
    # Which fields the semantic hop actually supplied. Field names and source
    # labels only — never field values. This is what separates a schema-valid
    # echo from useful semantic completion (Plan 7 C3).
    # This redaction runs twice on a live turn: once into `control_plane_trace`,
    # then again over that already-redacted dict in `debug_summary`. The second
    # pass has no `provenance`, so it must fall back to the flattened key or it
    # silently erases what the first pass extracted — which is exactly how the
    # C3 measurement came back empty.
    raw_sources = provenance.get("field_sources")
    if not isinstance(raw_sources, dict):
        raw_sources = source.get("field_sources")
    field_sources = (
        {str(key): str(value) for key, value in sorted(raw_sources.items())}
        if isinstance(raw_sources, dict)
        else {}
    )
    semantic_fields = sorted(key for key, value in field_sources.items() if value == "semantic_t4")
    if not semantic_fields and isinstance(source.get("semantic_t4_fields"), list):
        semantic_fields = [str(item) for item in source["semantic_t4_fields"]]
    return {
        "qualification_tier": source.get("qualification_tier"),
        "field_sources": field_sources,
        "semantic_t4_fields": semantic_fields,
        "intent_family": source.get("intent_family"),
        "answer_goal": source.get("answer_goal"),
        "required_capabilities": sorted(str(item) for item in required)
        if isinstance(required, (list, tuple, set, frozenset))
        else [],
        "prohibited_capabilities": sorted(str(item) for item in prohibited)
        if isinstance(prohibited, (list, tuple, set, frozenset))
        else [],
        "ambiguity_state": source.get("ambiguity_state"),
        "clarification_required": bool(source.get("clarification_required")),
        "understanding_source": source.get("understanding_source"),
        "qualification_source": source.get("qualification_source"),
        "semantic_t4": semantic_block,
    }


def _schedule_provenance_block(
    payload: dict[str, Any],
    control_plane_trace: dict[str, Any],
) -> dict[str, Any]:
    """ResourcePlan / PhaseContract / dispatch schedule IDs. No SPL or MCP rows."""
    plan_dispatch = payload.get("plan_dispatch_trace")
    if not isinstance(plan_dispatch, dict):
        plan_dispatch = control_plane_trace.get("plan_dispatch")
    plan_dispatch = plan_dispatch if isinstance(plan_dispatch, dict) else {}
    evidence = payload.get("evidence_plan")
    if not isinstance(evidence, dict):
        evidence = control_plane_trace.get("evidence_plan")
    evidence = evidence if isinstance(evidence, dict) else {}
    resource_plan = evidence.get("resource_plan")
    resource_plan = resource_plan if isinstance(resource_plan, dict) else {}
    provenance = resource_plan.get("provenance")
    provenance = provenance if isinstance(provenance, dict) else {}
    steps = resource_plan.get("steps")
    step_ids = [
        str(step.get("step_id"))
        for step in steps
        if isinstance(step, dict) and step.get("step_id")
    ] if isinstance(steps, list) else []
    fingerprint = None
    if step_ids:
        digest = hashlib.sha256(",".join(step_ids).encode("utf-8")).hexdigest()
        fingerprint = digest[:16]
    execution_order = plan_dispatch.get("execution_order")
    execution_order = execution_order if isinstance(execution_order, dict) else {}
    phase_merge = execution_order.get("phase_merge")
    phase_merge = phase_merge if isinstance(phase_merge, dict) else {}
    phase_contract = phase_merge.get("phase_contract")
    phase_contract = phase_contract if isinstance(phase_contract, dict) else {}
    phases = phase_contract.get("phases")
    phase_names = [
        str(phase.get("name"))
        for phase in phases
        if isinstance(phase, dict) and phase.get("name")
    ] if isinstance(phases, list) else []
    schedule = plan_dispatch.get("dispatch_schedule")
    schedule = list(schedule) if isinstance(schedule, list) else []
    node_trace = payload.get("node_trace")
    duration_ms: dict[str, int] = {}
    executed: list[str] = []
    if isinstance(node_trace, list):
        for row in node_trace:
            if not isinstance(row, dict):
                continue
            name = row.get("node_name") or row.get("node")
            if not name:
                continue
            executed.append(str(name))
            raw_ms = row.get("duration_ms")
            if isinstance(raw_ms, (int, float)):
                duration_ms[str(name)] = int(raw_ms)
    if not executed:
        executed = list(schedule)
    downgrade = execution_order.get("downgrade_reason")
    if isinstance(downgrade, str) and downgrade:
        degrade_reason = downgrade
    elif phase_merge:
        degrade_reason = "merge"
    elif str(plan_dispatch.get("dispatch_source") or "") == "legacy_predicate":
        degrade_reason = "fallback"
    else:
        degrade_reason = None
    session_role = payload.get("session_role")
    if not isinstance(session_role, str):
        session_role = control_plane_trace.get("session_role")
    rbac = None
    mcp = control_plane_trace.get("mcp_execution")
    if isinstance(mcp, dict):
        rbac = mcp.get("rbac_decision") or mcp.get("rbac_role")
    inline_mandatory_raw = phase_contract.get("inline_mandatory")
    inline_mandatory = (
        [str(name) for name in inline_mandatory_raw if name]
        if isinstance(inline_mandatory_raw, list)
        else []
    )
    inline_executed_raw = plan_dispatch.get("inline_executed")
    if not isinstance(inline_executed_raw, list):
        inline_executed_raw = payload.get("pipeline_inline_executed")
    inline_executed = (
        [str(name) for name in inline_executed_raw if name]
        if isinstance(inline_executed_raw, list)
        else []
    )
    return {
        "resource_plan_id": provenance.get("resource_plan_id"),
        "resource_plan_fingerprint": fingerprint,
        "phase_names": phase_names,
        "dispatch_schedule": [str(item) for item in schedule],
        "executed_hooks": executed[:24],
        "inline_mandatory": inline_mandatory[:8],
        "inline_executed": inline_executed[:8],
        "degrade_reason": degrade_reason,
        "session_role": session_role if isinstance(session_role, str) else None,
        "rbac_decision": str(rbac) if rbac is not None else None,
        "phase_duration_ms": duration_ms,
    }


def _budget_records(
    control_plane_trace: dict[str, Any],
    llm_budget_records: list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    if llm_budget_records is not None:
        return list(llm_budget_records)
    budget = control_plane_trace.get("llm_turn_budget")
    if isinstance(budget, dict) and isinstance(budget.get("records"), list):
        return [item for item in budget["records"] if isinstance(item, dict)]
    return []


def _routing_block(
    payload: dict[str, Any],
    control_plane_trace: dict[str, Any],
    run_contract: dict[str, Any],
) -> dict[str, Any]:
    provenance = control_plane_trace.get("routing_provenance")
    provenance = provenance if isinstance(provenance, dict) else {}
    query_to_intent = control_plane_trace.get("query_to_intent")
    query_to_intent = query_to_intent if isinstance(query_to_intent, dict) else {}
    mappings = query_to_intent.get("candidate_mappings")
    mappings = mappings if isinstance(mappings, dict) else {}
    catalog = provenance.get("catalog_bundle")
    catalog = catalog if isinstance(catalog, dict) else {}
    selected_use_case = payload.get("selected_use_case")
    selected_use_case = selected_use_case if isinstance(selected_use_case, dict) else {}
    route_contract = run_contract.get("routing")
    route_contract = route_contract if isinstance(route_contract, dict) else {}

    use_case_ids = mappings.get("use_case_ids")
    first_use_case = use_case_ids[0] if isinstance(use_case_ids, list) and use_case_ids else None
    patterns = selected_use_case.get("matched_patterns") or catalog.get("matched_patterns") or []
    if not isinstance(patterns, list):
        patterns = []

    return {
        "match_path": (
            mappings.get("match_path")
            or provenance.get("deterministic_match_path")
            or route_contract.get("path_type")
        ),
        "use_case_id": (
            selected_use_case.get("use_case_id")
            or provenance.get("use_case_id")
            or first_use_case
        ),
        "matched_patterns": [str(item) for item in patterns[:3]],
        "question_ref": mappings.get("question_ref") or provenance.get("mapped_question_ref"),
        "selected_skill": payload.get("selected_skill"),
        "intent_family": query_to_intent.get("intent_family") or route_contract.get("intent_family"),
    }


def _llm_block(
    control_plane_trace: dict[str, Any],
    candidate_spl: dict[str, Any],
    spl_validation: dict[str, Any],
    records: list[dict[str, Any]],
    live_records: list[dict[str, Any]],
    live_roles: list[str],
) -> dict[str, Any]:
    hybrid = control_plane_trace.get("hybrid_role_graph")
    hybrid = hybrid if isinstance(hybrid, dict) else {}
    skipped_roles: list[dict[str, str]] = []
    for role in (hybrid.get("roles") or [])[:_MAX_SKIPPED_ROLES]:
        if not isinstance(role, dict):
            continue
        if role.get("enabled"):
            continue
        reason = role.get("skip_reason")
        role_id = role.get("role_id")
        if reason and role_id:
            skipped_roles.append({"role": str(role_id), "reason": str(reason)})

    spl_gen = control_plane_trace.get("candidate_spl_generation")
    spl_gen = spl_gen if isinstance(spl_gen, dict) else {}
    generation_mode = candidate_spl.get("generation_mode") or spl_gen.get("generation_mode")
    spl_path = _spl_path_label(generation_mode, candidate_spl)
    spl_live_called = _spl_live_called(spl_validation, records)
    composer = control_plane_trace.get("llm_composer")
    composer = composer if isinstance(composer, dict) else {}

    return {
        "live_calls": len(live_records),
        "live_roles": live_roles,
        "skipped_roles": skipped_roles,
        "spl_path": spl_path,
        "spl_live_called": spl_live_called,
        "spl_outcome": _spl_outcome(spl_validation, candidate_spl),
        "composer_skipped_reason": (
            composer.get("llm_composer_skipped_reason")
            or composer.get("llm_blocked_reason")
            or (None if composer.get("llm_composer_used") else composer.get("llm_guard_status"))
        ),
    }


def _spl_block(
    candidate_spl: dict[str, Any],
    spl_validation: dict[str, Any],
    control_plane_trace: dict[str, Any],
) -> dict[str, Any]:
    spl_gen = control_plane_trace.get("candidate_spl_generation")
    spl_gen = spl_gen if isinstance(spl_gen, dict) else {}
    reject_reasons = spl_validation.get("reject_reasons") or []
    if not isinstance(reject_reasons, list):
        reject_reasons = []
    utility_trace = candidate_spl.get("utility_spl_draft_trace")
    if not isinstance(utility_trace, dict):
        utility_trace = spl_validation.get("utility_spl_draft_trace")
    utility_trace = utility_trace if isinstance(utility_trace, dict) else {}
    post = candidate_spl.get("review_only_spl_postprocessor_trace")
    if not isinstance(post, dict):
        post = spl_validation.get("review_only_spl_postprocessor_trace")
    post = post if isinstance(post, dict) else utility_trace.get("review_only_spl_postprocessor_trace")
    post = post if isinstance(post, dict) else {}
    postprocessor_evaluated = bool(
        post.get("postprocessor_evaluated")
        or utility_trace.get("postprocessor_evaluated")
        or candidate_spl.get("review_only_spl_postprocessor_applied") is not None
    )
    postprocessor_applied = bool(
        utility_trace.get("postprocessor_applied") or post.get("postprocessor_applied")
    )
    detection_plan = candidate_spl.get("detection_plan")
    redacted_plan = None
    if isinstance(detection_plan, dict):
        redacted_plan = {
            key: detection_plan.get(key)
            for key in (
                "index",
                "sourcetype",
                "data_domain",
                "detection_family",
                "required_fields",
            )
            if detection_plan.get(key) is not None
        } or None
    return {
        "template_id": candidate_spl.get("template_id"),
        "approved": spl_validation.get("approved"),
        "reject_reasons": [str(item) for item in reject_reasons[:6]],
        "normalized_spl": bool(spl_validation.get("normalized_spl") or spl_gen.get("normalized_spl_available")),
        "postprocessor_evaluated": postprocessor_evaluated,
        "postprocessor_applied": postprocessor_applied,
        "no_op_reason": post.get("no_op_reason") or utility_trace.get("no_op_reason"),
        "spl_raw_hash": post.get("spl_raw_hash") or utility_trace.get("spl_raw_hash"),
        "spl_post_hash": post.get("spl_post_hash") or utility_trace.get("spl_post_hash"),
        "review_only_postprocessor_applied": postprocessor_applied,
        "review_only_spl_postprocessor_trace": post or None,
        "detection_plan": redacted_plan,
        "final_spl_authority": utility_trace.get("final_spl_authority")
        or post.get("final_spl_authority"),
        "final_raw_spl_source": utility_trace.get("final_raw_spl_source"),
    }


def _mcp_block(
    execution: dict[str, Any],
    control_plane_trace: dict[str, Any],
    run_contract: dict[str, Any],
) -> dict[str, Any]:
    mcp_trace = control_plane_trace.get("mcp_execution")
    mcp_trace = mcp_trace if isinstance(mcp_trace, dict) else {}
    return {
        "allowed": bool(run_contract.get("mcp_allowed")),
        "status": execution.get("status") or mcp_trace.get("status") or "skipped",
        "block_reason": execution.get("block_reason") or mcp_trace.get("block_reason"),
    }


def _hil_block(
    human_review: dict[str, Any],
    run_contract: dict[str, Any],
    spl_validation: dict[str, Any],
) -> dict[str, Any]:
    reject_reasons = spl_validation.get("reject_reasons") or []
    hil_reason = None
    if isinstance(reject_reasons, list) and reject_reasons and not spl_validation.get("approved"):
        hil_reason = "spl_validation_failed"
    return {
        "required": bool(human_review.get("required") or run_contract.get("effective_hil_required")),
        "kind": human_review.get("review_type") or human_review.get("kind"),
        "reason": human_review.get("reason") or run_contract.get("spl_block_reason") or hil_reason,
    }


def _spl_path_label(generation_mode: Any, candidate_spl: dict[str, Any]) -> str:
    mode = str(generation_mode or "").strip()
    if mode in {"deterministic_template_render", "template", "governed_template"}:
        return "governed_template"
    if mode in {"deterministic_lab_draft", "lab_draft"}:
        return "lab_draft"
    if mode == "llm_spl_advisory_fallback":
        return "llm_spl_advisory_fallback"
    if candidate_spl.get("candidate_spl") or candidate_spl.get("candidate_spl_generated"):
        return mode or "candidate"
    return "none"


def _spl_live_called(spl_validation: dict[str, Any], records: list[dict[str, Any]]) -> bool:
    if spl_validation.get("llm_model"):
        return True
    utility_trace = spl_validation.get("utility_spl_draft_trace")
    if isinstance(utility_trace, dict) and utility_trace.get("llm_spl_draft_completed"):
        return True
    for item in records:
        if item.get("outcome") != "completed":
            continue
        role = str(item.get("role") or "").lower()
        if "spl" in role or role in {"spl_t2_producer", "spl_generation"}:
            return True
    return bool(spl_validation.get("llm_fallback_used") and spl_validation.get("llm_latency_ms"))


def _spl_outcome(spl_validation: dict[str, Any], candidate_spl: dict[str, Any]) -> str | None:
    if spl_validation.get("approved"):
        return "approved"
    status = candidate_spl.get("llm_fallback_status") or spl_validation.get("llm_fallback_status")
    if status:
        return str(status)
    if spl_validation.get("reject_reasons"):
        return "validation_failed"
    if candidate_spl.get("candidate_spl_generated"):
        return "candidate_generated"
    return None

def _intent_block(payload: dict[str, Any], control_plane_trace: dict[str, Any]) -> dict[str, Any]:
    intent_dispatch = payload.get("intent_dispatch")
    if not isinstance(intent_dispatch, dict):
        intent_dispatch = control_plane_trace.get("intent_dispatch")
    intent_dispatch = intent_dispatch if isinstance(intent_dispatch, dict) else {}
    advisory = payload.get("llm_intent_advisory")
    if not isinstance(advisory, dict):
        advisory = control_plane_trace.get("llm_intent_advisory")
    advisory = advisory if isinstance(advisory, dict) else {}
    slots = advisory.get("entity_slots_candidate")
    q2i = payload.get("query_to_intent")
    return {
        "call_2c_llm": intent_dispatch.get("call_2c_llm"),
        "prompt_mode": intent_dispatch.get("prompt_mode"),
        "skip_reasons": list(intent_dispatch.get("skip_reasons") or [])[:4],
        "intent_family_candidate": advisory.get("intent_family_candidate") or advisory.get("intent_family"),
        "entity_slots": slots if isinstance(slots, dict) else {},
        "llm_intent_assist_status": q2i.get("llm_intent_assist_status") if isinstance(q2i, dict) else None,
    }


def _dispatch_block(payload: dict[str, Any], control_plane_trace: dict[str, Any]) -> dict[str, Any]:
    pipeline_dispatch = payload.get("pipeline_dispatch")
    if not isinstance(pipeline_dispatch, dict):
        pipeline_dispatch = control_plane_trace.get("pipeline_dispatch")
    pipeline_dispatch = pipeline_dispatch if isinstance(pipeline_dispatch, dict) else {}
    decision = pipeline_dispatch.get("decision")
    decision = decision if isinstance(decision, dict) else {}
    stage_schedule = decision.get("stage_schedule")
    llm_hops = decision.get("llm_hops")
    runtime = pipeline_dispatch.get("runtime_context")
    runtime = runtime if isinstance(runtime, dict) else {}
    return {
        "request_mode": decision.get("request_mode"),
        "stage_schedule": list(stage_schedule) if isinstance(stage_schedule, list) else [],
        "llm_hops": list(llm_hops) if isinstance(llm_hops, list) else [],
        "dispatch_reasons": list(decision.get("dispatch_reasons") or [])[:6],
        "dispatch_cursor": runtime.get("dispatch_cursor"),
    }

