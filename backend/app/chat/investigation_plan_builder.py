"""Deterministic InvestigationPlan baseline for guided hybrid investigation."""

from __future__ import annotations

import re
from typing import Any

from app.chat.contracts.investigation_plan import InvestigationPlan
from app.chat.guidance_templates import build_guided_investigation_guidance
from app.chat.guided_hunt_grounding import build_guided_hunt_grounding
from app.chat.signal_class_guidance import classify_signal_class

_GUIDED_BLOCKED_CAPABILITIES: tuple[str, ...] = (
    "freeform_spl_execution",
    "mcp_action",
    "raw_spl",
    "route_change",
    "severity_assignment",
    "execution_eligible",
)

_FAMILY_DATA_CATEGORIES: dict[str, list[str]] = {
    "dns_beaconing_candidate": ["dns", "proxy", "firewall_sessions"],
    "network_exfil_volume": ["firewall_sessions", "egress_flows"],
    "lateral_movement_review": ["auth", "endpoint", "network_flows"],
    "auth_failed_login_spike": ["auth", "identity"],
    "edr_powershell_suspicious_command": ["endpoint", "process_execution"],
    "ai_threat_hunt": ["llm_telemetry", "mcp_audit"],
}


def _parse_guidance_lists(guidance: str) -> tuple[list[str], list[str]]:
    """Extract bullet lists from guided investigation guidance prose."""
    hypotheses: list[str] = []
    evidence: list[str] = []
    if not guidance:
        return hypotheses, evidence
    hypothesis_match = re.search(
        r"Hypotheses\s*\n-\s*(.+?)(?:\n\nEvidence|\n\nNext steps|\Z)",
        guidance,
        flags=re.DOTALL | re.IGNORECASE,
    )
    evidence_match = re.search(
        r"Evidence to collect\s*\n-\s*(.+?)(?:\n\nNext steps|\n\nLimitations|\Z)",
        guidance,
        flags=re.DOTALL | re.IGNORECASE,
    )
    if hypothesis_match:
        hypotheses = [
            line.strip()
            for line in re.split(r"\n-\s*", hypothesis_match.group(1).strip())
            if line.strip()
        ]
    if evidence_match:
        evidence = [
            line.strip()
            for line in re.split(r"\n-\s*", evidence_match.group(1).strip())
            if line.strip()
        ]
    return hypotheses, evidence


def _objective_from_query(query: str, signal_class: str) -> str:
    normalized = " ".join((query or "").strip().split())
    if not normalized:
        return "Guided investigation (review-only)"
    class_label = signal_class.replace("_", " ")
    return (
        f"Review-only investigation for: {normalized[:240]}"
        f" (signal class: {class_label})"
    )


def _data_categories(
    *,
    signal_class: str,
    detection_families: list[str],
) -> list[str]:
    categories: list[str] = []
    if signal_class and signal_class != "unknown":
        categories.append(signal_class.replace("_", " "))
    for family in detection_families:
        for item in _FAMILY_DATA_CATEGORIES.get(family, []):
            if item not in categories:
                categories.append(item)
    if not categories:
        categories = ["network_flows", "asset_context", "change_records"]
    return categories[:8]


def _candidate_sources_from_grounding(grounding_block: Any) -> list[str]:
    sources: list[str] = []
    for family in list(getattr(grounding_block, "detection_families", None) or []):
        label = str(family).strip()
        if label and label not in sources:
            sources.append(f"detection_family:{label}")
    for ref in list(getattr(grounding_block, "skill_refs", None) or []):
        label = str(ref).strip()
        if label and label not in sources:
            sources.append(label)
    for ref in list(getattr(grounding_block, "soc_kb_refs", None) or []):
        label = str(ref).strip()
        if label and label not in sources:
            sources.append(f"soc_kb:{label[:80]}")
    return sources[:12]


def build_deterministic_investigation_plan(
    *,
    query: str,
    entities: dict[str, Any] | None = None,
    soc_kb_retrieval: dict[str, Any] | None = None,
    enrichment_projection: dict[str, Any] | None = None,
) -> InvestigationPlan:
    """Build a deterministic InvestigationPlan anchor — no MCP/LLM/tool calls."""
    guidance = build_guided_investigation_guidance(query, entities)
    hypotheses, evidence_needed = _parse_guidance_lists(guidance)
    signal_class = classify_signal_class(query, entities)
    grounding = build_guided_hunt_grounding(
        query=query,
        soc_kb_retrieval=soc_kb_retrieval,
        enrichment_projection=enrichment_projection,
    )
    detection_families = list(getattr(grounding, "detection_families", None) or [])
    environment_constraints = [
        *list(getattr(grounding, "limitations", None) or []),
        *[
            f"env_kb_slot:{slot}"
            for slot in list(getattr(grounding, "environment_kb_slots", None) or [])
        ],
        *[
            f"asset_hint:{hint}"
            for hint in list(getattr(grounding, "asset_registry_hints", None) or [])
        ],
    ]
    env_kb_needed = bool(
        getattr(grounding, "environment_kb_slots", None)
        or any("missing_slots=" in str(item) for item in environment_constraints)
    )
    return InvestigationPlan(
        investigation_objective=_objective_from_query(query, signal_class),
        hypotheses=hypotheses,
        evidence_needed=evidence_needed,
        data_categories=_data_categories(
            signal_class=signal_class,
            detection_families=detection_families,
        ),
        rag_sufficient=False,
        env_kb_needed=env_kb_needed,
        discovery_needed=False,
        environment_constraints=environment_constraints[:16],
        candidate_sources=_candidate_sources_from_grounding(grounding),
        read_only_tool_requests=[],
        safe_spl_template_requests=[],
        spl_review_requested=False,
        spl_review_reason=None,
        clarification_needed=False,
        clarification_questions=[],
        refinement_recommended=False,
        refinement_rationale=None,
        blocked_capabilities=list(_GUIDED_BLOCKED_CAPABILITIES),
        human_review_required=True,
        plan_source="deterministic_only",
        validation_warnings=[],
        llm_budget_used=0,
        refinement_round=0,
    )
