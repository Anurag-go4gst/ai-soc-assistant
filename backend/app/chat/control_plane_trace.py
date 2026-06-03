"""Unified control-plane trace assembly.

The trace builder is packaging-only: it must not call RAG, MCP, SPL validation,
MITRE resolution, or any LLM path.
"""

from __future__ import annotations

from typing import Any

_SECRET_KEYS = ("secret", "token", "password", "passwd", "api_key", "apikey", "dsn", "auth")


def build_control_plane_trace(
    state: dict[str, Any],
    *,
    source_evidence: list[dict[str, Any]] | None = None,
    context_sufficiency: dict[str, Any] | None = None,
    synthesis_mode: str | None = None,
    answer_guard: dict[str, Any] | None = None,
) -> dict[str, Any]:
    route_shadow = state.get("route_plan_shadow") if isinstance(state.get("route_plan_shadow"), dict) else {}
    rag = state.get("soc_kb_retrieval") if isinstance(state.get("soc_kb_retrieval"), dict) else None
    spl_validation = state.get("spl_validation") if isinstance(state.get("spl_validation"), dict) else None
    execution = state.get("execution") if isinstance(state.get("execution"), dict) else None

    trace = {
        "query_to_intent": state.get("query_to_intent"),
        "evidence_plan": state.get("evidence_plan"),
        "route_adjudication": state.get("route_adjudication"),
        "llm_plan_validation": state.get("llm_plan_validation"),
        "tool_plan": _tool_plan(state),
        "mitre_registry_metadata": _mitre_registry_metadata(state.get("mitre_decision")),
        "mitre_decision": state.get("mitre_decision"),
        "rag_trace": _rag_trace(rag),
        "spl_slot_binding": _spl_slot_binding_trace(spl_validation),
        "mcp_execution": _mcp_trace(execution),
        "sufficiency": context_sufficiency,
        "synthesis_mode": {"mode": synthesis_mode},
        "answer_guard": answer_guard,
        "source_evidence_refs": [
            str(item.get("evidence_id"))
            for item in (source_evidence or [])
            if isinstance(item, dict) and item.get("evidence_id")
        ],
        "precondition_evaluation": route_shadow.get("precondition_evaluation"),
    }
    return _redact(trace)


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
            if any(secret in key_str.lower() for secret in _SECRET_KEYS):
                redacted[key_str] = "[REDACTED]"
            else:
                redacted[key_str] = _redact(item)
        return redacted
    if isinstance(value, list):
        return [_redact(item) for item in value]
    if isinstance(value, str) and any(marker in value.lower() for marker in ("bearer ", "password=", "token=")):
        return "[REDACTED]"
    return value
