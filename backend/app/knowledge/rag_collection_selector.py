from __future__ import annotations

from typing import Any

from app.config import settings
from app.knowledge.repository import KnowledgeRepository, get_knowledge_repository


def select_rag_collections(
    *,
    query: str,
    selected_skill: str,
    workflow_stage: str | None,
    workflow_plan: dict[str, Any] | None,
    required_sources: list[str] | None,
    environment: str | None,
    allowed_use: list[str] | None,
    human_review: dict[str, Any] | None = None,
    execution_block_reason: str | None = None,
    repository: KnowledgeRepository | None = None,
) -> dict[str, Any]:
    repo = repository or get_knowledge_repository()
    configured = {item.get("collection_id"): item for item in repo.list_collections() if item.get("enabled", False)}
    env = environment or settings.soc_kb_environment
    uses = set(allowed_use or [])
    required = set(required_sources or (workflow_plan or {}).get("required_sources") or [])
    query_lower = query.lower()
    wanted: list[str] = []
    reasons: dict[str, list[str]] = {}

    def add(collection_id: str, reason: str) -> None:
        if collection_id not in wanted:
            wanted.append(collection_id)
        reasons.setdefault(collection_id, []).append(reason)

    if selected_skill == "attack_discovery":
        add("soc_sop", "attack_discovery_sop_grounding")
        add("mitre_enterprise", "attack_discovery_mitre_grounding")
        add("splunk_context", "attack_discovery_splunk_context")
        if human_review and human_review.get("required") or execution_block_reason or "rag:sop" in required:
            add("escalation_matrix", "hil_required_escalation_guidance")
    elif selected_skill == "spl_generation" or workflow_stage == "spl_generation":
        add("detection_notes", "spl_generation_detection_guidance")
        add("splunk_context", "spl_generation_environment_context")
        add("mcp_tool_policy", "spl_generation_tool_policy")
    elif selected_skill == "knowledge_recall":
        if any(term in query_lower for term in ("mitre", "t1110", "t1078", "technique")):
            add("mitre_enterprise", "knowledge_recall_mitre_signal")
        if any(term in query_lower for term in ("splunk", "index", "sourcetype", "field")):
            add("splunk_context", "knowledge_recall_splunk_signal")
        if any(term in query_lower for term in ("sop", "runbook", "escalation", "review")):
            add("soc_sop", "knowledge_recall_sop_signal")
        if any(term in query_lower for term in ("tool", "mcp", "execute")):
            add("mcp_tool_policy", "knowledge_recall_tool_policy_signal")
        if not wanted:
            add("soc_sop", "knowledge_recall_default_sop_scope")
    else:
        if "hil_guidance" in uses:
            add("soc_sop", "allowed_use_hil_guidance")
        if "tool_selection" in uses:
            add("mcp_tool_policy", "allowed_use_tool_selection")
        if "environment_grounding" in uses or "spl_generation" in uses:
            add("splunk_context", "allowed_use_environment_grounding")

    if any(term in query_lower for term in ("ics", "ot", "scada", "plc")):
        add("mitre_ics", "future_ics_query_signal")
        add("asset_policy", "future_ot_asset_policy_signal")
    if "asset" in query_lower:
        add("asset_policy", "asset_query_signal")
    if "customer" in query_lower:
        add("customer_context", "customer_context_signal")

    selected: list[str] = []
    missing: list[str] = []
    warnings: list[str] = []
    for collection_id in wanted:
        collection = configured.get(collection_id)
        if not collection:
            missing.append(collection_id)
            warnings.append(f"collection_not_configured:{collection_id}")
            continue
        if collection.get("environment") not in {"global", env}:
            missing.append(collection_id)
            warnings.append(f"collection_wrong_environment:{collection_id}")
            continue
        collection_uses = set(collection.get("allowed_use") or [])
        if uses and not collection_uses.intersection(uses):
            warnings.append(f"collection_allowed_use_mismatch:{collection_id}")
            continue
        selected.append(collection_id)

    if not selected:
        warnings.append("no_rag_collections_selected")
    return {
        "selected_collections": selected,
        "selection_reasons": reasons,
        "missing_collections": missing,
        "warnings": sorted(set(warnings)),
    }
