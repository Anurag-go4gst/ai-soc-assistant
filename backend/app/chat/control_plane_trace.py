"""Unified control-plane trace assembly.

The trace builder is packaging-only: it must not call RAG, MCP, SPL validation,
MITRE resolution, or any LLM path.
"""

from __future__ import annotations

from typing import Any

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
        "evidence_plan": state.get("evidence_plan"),
        "route_adjudication": state.get("route_adjudication"),
        "llm_plan_validation": state.get("llm_plan_validation"),
        "tool_plan": _tool_plan(state),
        "mitre_registry_metadata": _mitre_registry_metadata(state.get("mitre_decision")),
        "mitre_branch_result": state.get("mitre_branch_result"),
        "mitre_decision": state.get("mitre_decision"),
        "rag_trace": _rag_trace(rag),
        "candidate_spl_generation": _candidate_spl_generation_trace(candidate_spl, spl_validation),
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
    }
    if node_trace:
        trace["node_trace"] = node_trace
    return _redact(trace)


def _resource_planner_trace(state: dict[str, Any]) -> dict[str, Any] | None:
    evidence_plan = state.get("evidence_plan") if isinstance(state.get("evidence_plan"), dict) else {}
    resource_plan = evidence_plan.get("resource_plan") if isinstance(evidence_plan.get("resource_plan"), dict) else {}
    provenance = resource_plan.get("provenance") if isinstance(resource_plan.get("provenance"), dict) else {}
    decisions = provenance.get("resource_decisions")
    if isinstance(decisions, dict):
        return {
            "source": "evidence_plan.resource_plan.provenance.resource_decisions",
            "resource_decisions": decisions,
        }

    planning = state.get("planning_decision") if isinstance(state.get("planning_decision"), dict) else {}
    summary = planning.get("resource_plan_summary")
    if isinstance(summary, dict):
        return {
            "source": "planning_decision.resource_plan_summary",
            "resource_decisions": summary,
        }
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
    return {
        "llm_advisory_attempted": attempted,
        "llm_called": llm_called,
        "llm_candidate_present": candidate_present,
        "llm_advisory_used": advisory_used,
        "llm_route_candidate": str(route_candidate) if route_candidate else None,
        "llm_intent_candidate": str(intent_candidate) if intent_candidate else None,
        "llm_dropped_reasons": dropped_reasons,
        "llm_narration_used": narration_used,
        "llm_overridden_by_policy": overridden,
    }


def _candidate_spl_generation_trace(
    candidate_spl: dict[str, Any] | None,
    spl_validation: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if not candidate_spl and not spl_validation:
        return None
    validation = spl_validation or {}
    candidate = candidate_spl or {}
    return {
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
        "match_status": rag.get("match_status") or rag.get("status"),
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
    return {
        "validated": "slot_binding_validated" in (spl_validation.get("warnings") or [])
        or bool(missing),
        "missing_bindings": missing,
        "approved": spl_validation.get("approved"),
        "policy_version": spl_validation.get("policy_version"),
    }


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
