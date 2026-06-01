from __future__ import annotations

from typing import Any

from app.routing.runtime_skill_catalog import get_skill_contract


def build_operation_audit_record(
    *,
    query: str,
    primary_operation: str | None,
    coverage_id: str | None,
    semantic_intent: dict[str, object] | None,
    route_plan_shadow: dict[str, Any] | None,
) -> dict[str, object] | None:
    """Build a trace-only audit record for OOD operation proposals."""
    semantic_audit = semantic_intent.get("audit_record") if isinstance(semantic_intent, dict) else None
    if isinstance(semantic_audit, dict):
        if not semantic_audit.get("proposed_operation"):
            return None
        return {
            **semantic_audit,
            "audit_sink": "trace_only",
            "mcp_called": False,
            "spl_execution_allowed": False,
        }

    if not primary_operation or coverage_id or get_skill_contract(primary_operation):
        return None

    blocking_findings = []
    if isinstance(route_plan_shadow, dict):
        blocking_findings = list(route_plan_shadow.get("blocking_findings") or [])

    return {
        "audit_required": True,
        "audit_sink": "trace_only",
        "query": query,
        "path_type": "novel_ood",
        "proposed_operation": primary_operation,
        "operation_provenance": "llm_or_route_plan_proposed_novel",
        "coverage_id": coverage_id,
        "authority_decision": "shadow_only",
        "route_status": "hil_or_review",
        "promotion_candidate": True,
        "nearest_registry_hint": None,
        "reason": "unknown_primary_skill",
        "blocking_findings": blocking_findings,
        "mcp_called": False,
        "spl_execution_allowed": False,
    }


def operation_audit_human_review(audit_record: dict[str, object] | None) -> dict[str, Any] | None:
    if not audit_record or not audit_record.get("audit_required"):
        return None
    if audit_record.get("path_type") != "novel_ood":
        return None
    return {
        "required": True,
        "review_type": "operation_promotion_review",
        "reason": "novel_operation_requires_coe_review",
        "reviewer_role": "soc_coe",
        "allowed_actions": ["reject", "promote_to_registry", "request_more_context"],
        "safe_message_for_user": (
            "This query proposes an operation that is not in the governed registry. "
            "It has been stopped for SOC COE review and cannot execute live."
        ),
    }
