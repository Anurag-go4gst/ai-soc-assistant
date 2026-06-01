from __future__ import annotations

from typing import Any, Literal

from app.query_understanding.models import QueryUnderstandingResult, RequestedOutputType
from app.routing.runtime_skill_catalog import get_skill_contract

SemanticPathType = Literal[
    "known_registry",
    "known_compatible_ood",
    "novel_ood",
    "knowledge_only",
    "clarification",
]

_KNOWLEDGE_OUTPUTS = {
    RequestedOutputType.SOP,
    RequestedOutputType.MITRE_MAPPING,
    RequestedOutputType.SUMMARY,
    RequestedOutputType.NOTE,
    RequestedOutputType.ACTION_PLAN,
}
_MCP_OUTPUTS = {RequestedOutputType.INVESTIGATION, RequestedOutputType.SPL}
_EXECUTION_SKILLS = {"attack_discovery", "spl_generation"}


def build_semantic_intent_envelope(
    *,
    query_understanding: QueryUnderstandingResult,
    routed: dict[str, Any],
    route_plan_shadow: dict[str, Any] | None,
    route_authority: dict[str, object] | None,
    primary_operation: str | None,
    coverage_id: str | None,
) -> dict[str, object]:
    """Build the P2 semantic-intent trace envelope.

    The envelope is advisory/debug metadata only. It records how deterministic
    query understanding, legacy routing, route-plan shadow, and any LLM advisory
    line up with the registry/operation target model.
    """
    llm_advisory = routed.get("llm_semantic_advisory")
    llm_advisory = dict(llm_advisory) if isinstance(llm_advisory, dict) else None
    route_decision = routed.get("route_decision")
    route_decision = dict(route_decision) if isinstance(route_decision, dict) else {}
    path_type = _path_type(
        query_understanding=query_understanding,
        routed=routed,
        primary_operation=primary_operation,
        coverage_id=coverage_id,
    )
    known_operation = bool(primary_operation and get_skill_contract(primary_operation))
    operation_provenance = _operation_provenance(
        path_type=path_type,
        llm_advisory=llm_advisory,
        known_operation=known_operation,
    )
    evidence_families = _evidence_families(
        query_understanding=query_understanding,
        routed=routed,
        llm_advisory=llm_advisory,
    )
    authority_decision = _authority_decision(route_authority)
    audit_record = _operation_audit_record(
        query=query_understanding.raw_query,
        path_type=path_type,
        primary_operation=primary_operation,
        coverage_id=coverage_id,
        operation_provenance=operation_provenance,
        authority_decision=authority_decision,
        route_authority=route_authority,
    )

    return {
        "enabled": True,
        "authority": "advisory_only",
        "path_type": path_type,
        "selected_path_authority": _selected_path_authority(route_authority, routed),
        "requested_output_type": query_understanding.requested_output_type.value,
        "nearest_registry_ref": _question_ref(route_plan_shadow),
        "coverage_id_candidate": coverage_id,
        "primary_operation_candidate": primary_operation,
        "legacy_intent_hint": routed.get("skill"),
        "entities": query_understanding.entities.model_dump(),
        "clarification_needed": query_understanding.clarification_needed,
        "clarification_question": query_understanding.clarification_question,
        "evidence_need_families": evidence_families,
        "mcp_needed": _mcp_needed(query_understanding, routed, primary_operation),
        "rag_needed": _rag_needed(query_understanding, routed),
        "mitre_candidate_needed": _mitre_needed(query_understanding, evidence_families),
        "llm_semantic_intent_called": bool(routed.get("llm_shadow")),
        "llm_path_type_candidate": None,
        "llm_requested_output_type_candidate": _llm_value(llm_advisory, "llm_requested_output_type_candidate"),
        "llm_nearest_registry_ref": None,
        "llm_coverage_id_candidate": None,
        "llm_primary_operation_candidate": _llm_value(llm_advisory, "llm_selected_skill_candidate"),
        "llm_legacy_intent_hint": _llm_value(llm_advisory, "llm_primary_intent_candidate"),
        "llm_clarification_needed": bool(_llm_value(llm_advisory, "llm_clarification_candidate")),
        "llm_evidence_need_families": _llm_evidence_families(llm_advisory),
        "semantic_intent_disagreements": list(route_decision.get("disagreements") or []),
        "operation_provenance": operation_provenance,
        "known_compatible": path_type in {"known_registry", "known_compatible_ood"},
        "authority_decision": authority_decision,
        "audit_record": audit_record,
        "final_route_unchanged": True,
        "warnings": _warnings(path_type, route_authority, llm_advisory),
    }


def _path_type(
    *,
    query_understanding: QueryUnderstandingResult,
    routed: dict[str, Any],
    primary_operation: str | None,
    coverage_id: str | None,
) -> SemanticPathType:
    if query_understanding.clarification_needed or routed.get("tool_plan") == ["needs_clarification"]:
        return "clarification"
    if query_understanding.requested_output_type in _KNOWLEDGE_OUTPUTS:
        return "knowledge_only"
    if coverage_id:
        return "known_registry"
    if primary_operation and get_skill_contract(primary_operation):
        return "known_compatible_ood"
    return "novel_ood"


def _operation_provenance(
    *,
    path_type: str,
    llm_advisory: dict[str, Any] | None,
    known_operation: bool,
) -> str:
    if path_type == "known_registry":
        return "registry"
    if llm_advisory and known_operation:
        return "llm_proposed_known_compatible"
    if llm_advisory:
        return "llm_proposed_novel"
    if known_operation:
        return "deterministic_known_compatible"
    return "none"


def _authority_decision(route_authority: dict[str, object] | None) -> str:
    if not route_authority:
        return "shadow_only"
    decision = route_authority.get("authority_decision")
    if decision == "applied":
        return "allowed"
    if decision == "fallback":
        return "shadow_only"
    return "shadow_only"


def _selected_path_authority(route_authority: dict[str, object] | None, routed: dict[str, Any]) -> str:
    if route_authority and route_authority.get("authority_decision") == "applied":
        return "deterministic_registry"
    if routed.get("selected_by") == "deterministic_clarification":
        return "deterministic_clarification"
    if routed.get("selected_by") == "llm_assisted_semantic_normalized":
        return "llm_advisory_normalized"
    return "shadow_only"


def _question_ref(route_plan_shadow: dict[str, Any] | None) -> str | None:
    if not isinstance(route_plan_shadow, dict):
        return None
    runtime_map = route_plan_shadow.get("question_runtime_map")
    if isinstance(runtime_map, dict):
        value = runtime_map.get("question_ref")
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _evidence_families(
    *,
    query_understanding: QueryUnderstandingResult,
    routed: dict[str, Any],
    llm_advisory: dict[str, Any] | None,
) -> list[str]:
    families: set[str] = set()
    normalized = query_understanding.normalized_query
    if any(term in normalized for term in ("login", "auth", "okta", "lockout")):
        families.add("authentication")
    if any(term in normalized for term in ("dns", "domain", "dga")):
        families.add("dns")
    if any(term in normalized for term in ("process", "powershell", "endpoint", "edr")):
        families.add("endpoint")
    if any(term in normalized for term in ("notable", "risk", "case", "alert")):
        families.add("notable")
    if query_understanding.requested_output_type in _KNOWLEDGE_OUTPUTS:
        families.add("kb")
    if query_understanding.requested_output_type == RequestedOutputType.MITRE_MAPPING:
        families.add("mitre")
    for need in (llm_advisory or {}).get("llm_evidence_needs", []) or []:
        if isinstance(need, dict):
            source_type = str(need.get("source_type") or "")
            if "auth" in source_type:
                families.add("authentication")
            elif "mitre" in source_type:
                families.add("mitre")
            elif "kb" in source_type or "playbook" in source_type:
                families.add("kb")
    if routed.get("skill") in _EXECUTION_SKILLS and not families:
        families.add("splunk")
    return sorted(families)


def _llm_evidence_families(llm_advisory: dict[str, Any] | None) -> list[str]:
    if not llm_advisory:
        return []
    values: set[str] = set()
    for need in llm_advisory.get("llm_evidence_needs", []) or []:
        if isinstance(need, dict):
            source_type = str(need.get("source_type") or "")
            if source_type:
                values.add(source_type)
    return sorted(values)


def _mcp_needed(
    query_understanding: QueryUnderstandingResult,
    routed: dict[str, Any],
    primary_operation: str | None,
) -> bool:
    if query_understanding.requested_output_type in _MCP_OUTPUTS:
        return True
    return bool(primary_operation and routed.get("skill") in _EXECUTION_SKILLS)


def _rag_needed(query_understanding: QueryUnderstandingResult, routed: dict[str, Any]) -> bool:
    if query_understanding.requested_output_type in _KNOWLEDGE_OUTPUTS:
        return True
    return "retrieve_approved_context" in list(routed.get("tool_plan") or [])


def _mitre_needed(query_understanding: QueryUnderstandingResult, evidence_families: list[str]) -> bool:
    return query_understanding.requested_output_type == RequestedOutputType.MITRE_MAPPING or (
        "authentication" in evidence_families
    )


def _llm_value(llm_advisory: dict[str, Any] | None, key: str) -> object | None:
    if not llm_advisory:
        return None
    value = llm_advisory.get(key)
    return value if value not in ("", [], {}) else None


def _operation_audit_record(
    *,
    query: str,
    path_type: str,
    primary_operation: str | None,
    coverage_id: str | None,
    operation_provenance: str,
    authority_decision: str,
    route_authority: dict[str, object] | None,
) -> dict[str, object] | None:
    if path_type not in {"known_compatible_ood", "novel_ood"}:
        return None
    return {
        "audit_required": True,
        "query": query,
        "path_type": path_type,
        "proposed_operation": primary_operation,
        "operation_provenance": operation_provenance,
        "coverage_id": coverage_id,
        "authority_decision": authority_decision,
        "route_status": "hil_or_review" if path_type == "novel_ood" else "known_compatible_review",
        "promotion_candidate": path_type == "novel_ood",
        "nearest_registry_hint": coverage_id,
        "reason": (route_authority or {}).get("authority_fallback_reason"),
    }


def _warnings(
    path_type: str,
    route_authority: dict[str, object] | None,
    llm_advisory: dict[str, Any] | None,
) -> list[str]:
    warnings: list[str] = []
    if path_type == "novel_ood":
        warnings.append("novel_ood_requires_audit_hil")
    if route_authority and route_authority.get("authority_decision") == "fallback":
        reason = route_authority.get("authority_fallback_reason") or "unknown"
        warnings.append(f"authority_fallback:{reason}")
    for item in (llm_advisory or {}).get("warnings", []) or []:
        warnings.append(str(item))
    return sorted(set(warnings))
