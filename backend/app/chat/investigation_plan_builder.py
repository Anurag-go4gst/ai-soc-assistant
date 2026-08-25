"""Deterministic InvestigationPlan baseline for guided hybrid investigation."""

from __future__ import annotations

import json
import re
from typing import Any

from app.chat.contracts.investigation_plan import (
    InvestigationCapabilityBinding,
    InvestigationPlan,
)
from app.chat.guidance_templates import build_guided_investigation_guidance
from app.chat.guided_hunt_grounding import build_guided_hunt_grounding
from app.chat.planned_mcp_call import enrich_capability_binding
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


def _as_mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    dump = getattr(value, "model_dump", None)
    if callable(dump):
        payload = dump(mode="json")
        return dict(payload) if isinstance(payload, dict) else {}
    return {}


def _authoritative_facts(rqc: dict[str, Any]) -> list[str]:
    """Stable T1-T4-independent facts from the Final RQC."""
    facts: list[str] = []
    for key, value in sorted((_as_mapping(rqc.get("entities"))).items()):
        if value not in (None, "", [], {}):
            facts.append(f"entity:{key}={json.dumps(value, sort_keys=True, ensure_ascii=False)}")
    time_scope = str(rqc.get("time_scope") or "").strip()
    if time_scope:
        facts.append(f"time_scope:{time_scope}")
    for capability in sorted(str(item) for item in (rqc.get("required_capabilities") or [])):
        facts.append(f"required_capability:{capability}")
    for requirement in rqc.get("evidence_requirements") or []:
        text = str(requirement or "").strip()
        if text:
            facts.append(f"evidence_requirement:{text[:240]}")
    return facts[:32]


def _required_capability_bindings(snapshot: dict[str, Any]) -> list[InvestigationCapabilityBinding]:
    bindings: list[InvestigationCapabilityBinding] = []
    for row in snapshot.get("rows") or []:
        if not isinstance(row, dict) or row.get("capability_need") != "required":
            continue
        availability = str(row.get("availability") or "unavailable")
        binding = InvestigationCapabilityBinding(
            capability_id=str(row.get("capability_id") or ""),
            capability_need="required",
            availability=availability,  # type: ignore[arg-type]
            access_mode="read_only" if availability == "available" else "manual_or_alternate",
        )
        bindings.append(enrich_capability_binding(binding))
    return bindings


def build_deterministic_investigation_plan(
    *,
    query: str,
    entities: dict[str, Any] | None = None,
    soc_kb_retrieval: dict[str, Any] | None = None,
    enrichment_projection: dict[str, Any] | None = None,
    resolved_query_contract: dict[str, Any] | Any | None = None,
    capability_snapshot: dict[str, Any] | Any | None = None,
) -> InvestigationPlan:
    """Build a deterministic InvestigationPlan anchor — no MCP/LLM/tool calls."""
    rqc = _as_mapping(resolved_query_contract)
    snapshot = _as_mapping(capability_snapshot)
    stable_query = str(rqc.get("normalized_goal") or query).strip()
    stable_entities = _as_mapping(rqc.get("entities")) or dict(entities or {})
    guidance = build_guided_investigation_guidance(stable_query, stable_entities)
    hypotheses, evidence_needed = _parse_guidance_lists(guidance)
    signal_class = classify_signal_class(stable_query, stable_entities)
    grounding = build_guided_hunt_grounding(
        query=stable_query,
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
    rqc_evidence = [
        str(item).strip()
        for item in (rqc.get("evidence_requirements") or [])
        if str(item).strip()
    ]
    evidence_needed = list(dict.fromkeys([*rqc_evidence, *evidence_needed]))
    authoritative_facts = _authoritative_facts(rqc)
    return InvestigationPlan(
        investigation_objective=_objective_from_query(stable_query, signal_class),
        hypotheses=hypotheses,
        evidence_needed=evidence_needed,
        data_categories=_data_categories(
            signal_class=signal_class,
            detection_families=detection_families,
        ),
        dependencies=["final_resolved_query_contract", "capability_snapshot"],
        conditions=[fact for fact in authoritative_facts if fact.startswith(("entity:", "time_scope:"))],
        success_criteria=[
            f"Collect governed evidence for: {item[:220]}"
            for item in evidence_needed[:8]
        ] or ["Record governed evidence or an explicit evidence gap."],
        capability_bindings=_required_capability_bindings(snapshot),
        authoritative_facts=authoritative_facts,
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
