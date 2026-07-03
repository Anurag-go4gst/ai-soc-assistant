"""Single accumulation authority for CanonicalFacts (plan 5.1).

Harvests typed facts from pipeline state and exposes read helpers for downstream
consumers. Legacy ad-hoc keys remain on state for compatibility; new reads in
the MITRE negative-evidence path prefer the spine when present.
"""

from __future__ import annotations

import uuid
from typing import Any, Mapping

from app.chat.contracts.canonical_facts import (
    FACT_AUTHORITY,
    CanonicalFact,
    CanonicalFacts,
    EvidenceClass,
    FactKind,
    FactProvenance,
)
from app.chat.negative_evidence_extractor import extract_negative_evidence

# Keys pipeline nodes must not read directly once the spine is attached (grep gate).
RETIRED_ADHOC_READ_KEYS: frozenset[str] = frozenset(
    {
        "mitre_mappings",
        "mitre_decision",
        "mcp_evidence",
        "soc_kb_retrieval",
        "structured_context",
        "source_evidence",
    }
)

_MASTER_FACT_SIGNALS: dict[str, set[str]] = {
    "mitre_decision": {"mitre_decision", "mitre_candidate"},
    "mitre_mappings": {"mitre_decision", "mitre_candidate"},
    "source_evidence": {"executed_evidence", "rag_citation"},
    "soc_kb_retrieval": {"rag_citation"},
    "mcp_evidence": {"executed_evidence"},
    "structured_context": {"negative_evidence", "cve_finding", "executed_evidence"},
    "vulnerability_source": {"cve_finding"},
    "evidence_plan": {"plan_step_outcome"},
}


def empty_canonical_facts() -> CanonicalFacts:
    return CanonicalFacts()


def _fact_id(prefix: str) -> str:
    return f"{prefix}:{uuid.uuid4().hex[:12]}"


def append_fact(
    facts: CanonicalFacts,
    *,
    kind: FactKind,
    payload: dict[str, Any],
    node: str,
    step_id: str | None = None,
    evidence_class: EvidenceClass = "unknown",
) -> CanonicalFacts:
    existing_ids = {fact.fact_id for fact in facts.facts}
    fact_id = _fact_id(kind)
    while fact_id in existing_ids:
        fact_id = _fact_id(kind)
    new_fact = CanonicalFact(
        fact_id=fact_id,
        kind=kind,
        payload=dict(payload),
        provenance=FactProvenance(node=node, step_id=step_id, evidence_class=evidence_class),
    )
    return facts.model_copy(update={"facts": [*facts.facts, new_fact]})


def get_canonical_facts(state: Mapping[str, Any] | None) -> CanonicalFacts | None:
    if not isinstance(state, Mapping):
        return None
    raw = state.get("canonical_facts")
    if isinstance(raw, CanonicalFacts):
        return raw
    if isinstance(raw, dict) and raw.get("facts") is not None:
        return CanonicalFacts.model_validate(raw)
    return None


def _harvest_entities(state: Mapping[str, Any]) -> list[CanonicalFact]:
    out: list[CanonicalFact] = []
    qu = state.get("query_understanding")
    if qu is None:
        return out
    entities: list[Any] = []
    if hasattr(qu, "entities"):
        entities = list(getattr(qu, "entities") or [])
    elif isinstance(qu, dict):
        entities = list(qu.get("entities") or [])
    for index, entity in enumerate(entities):
        payload = entity if isinstance(entity, dict) else {"value": str(entity)}
        out.append(
            CanonicalFact(
                fact_id=_fact_id("entity"),
                kind="entity",
                payload=payload,
                provenance=FactProvenance(node="query_understanding", evidence_class="session"),
            )
        )
    timeframe = None
    if hasattr(qu, "timeframe"):
        timeframe = getattr(qu, "timeframe", None)
    elif isinstance(qu, dict):
        timeframe = qu.get("timeframe")
    if timeframe:
        out.append(
            CanonicalFact(
                fact_id=_fact_id("timeframe"),
                kind="timeframe",
                payload=timeframe if isinstance(timeframe, dict) else {"value": timeframe},
                provenance=FactProvenance(node="query_understanding", evidence_class="session"),
            )
        )
    return out


def _harvest_source_evidence(state: Mapping[str, Any]) -> list[CanonicalFact]:
    out: list[CanonicalFact] = []
    for index, record in enumerate(state.get("source_evidence") or []):
        if not isinstance(record, dict):
            continue
        evidence_class: EvidenceClass = "rag"
        source_type = str(record.get("source_type") or "")
        if source_type == "cve_snapshot":
            evidence_class = "cve"
        elif source_type in {"mcp_search", "splunk_mcp"}:
            evidence_class = "mcp_search"
        rows = record.get("preview_rows") or record.get("rows") or []
        out.append(
            CanonicalFact(
                fact_id=_fact_id("executed_evidence"),
                kind="executed_evidence",
                payload={
                    "evidence_id": record.get("evidence_id"),
                    "source_type": source_type,
                    "status": record.get("status"),
                    "row_count": len(rows) if isinstance(rows, list) else 0,
                    "row_summary": rows[:3] if isinstance(rows, list) else [],
                },
                provenance=FactProvenance(node="source_evidence", evidence_class=evidence_class),
            )
        )
    return out


def _harvest_rag(state: Mapping[str, Any]) -> list[CanonicalFact]:
    rag = state.get("soc_kb_retrieval")
    if not isinstance(rag, dict):
        return []
    citations = rag.get("citations") or rag.get("chunks") or []
    if not isinstance(citations, list):
        citations = []
    return [
        CanonicalFact(
            fact_id=_fact_id("rag_citation"),
            kind="rag_citation",
            payload={
                "retrieval_status": rag.get("retrieval_status"),
                "citation": citation if isinstance(citation, dict) else {"ref": str(citation)},
            },
            provenance=FactProvenance(node="soc_kb_retrieval", evidence_class="rag"),
        )
        for citation in citations[:10]
    ] or [
        CanonicalFact(
            fact_id=_fact_id("rag_citation"),
            kind="rag_citation",
            payload={"retrieval_status": rag.get("retrieval_status")},
            provenance=FactProvenance(node="soc_kb_retrieval", evidence_class="rag"),
        )
    ]


def _harvest_mcp_evidence(state: Mapping[str, Any]) -> list[CanonicalFact]:
    out: list[CanonicalFact] = []
    for index, record in enumerate(state.get("mcp_evidence") or []):
        if not isinstance(record, dict):
            continue
        out.append(
            CanonicalFact(
                fact_id=_fact_id("executed_evidence"),
                kind="executed_evidence",
                payload={"mcp_record": record},
                provenance=FactProvenance(node="mcp_execution", evidence_class="mcp_search"),
            )
        )
    return out


def _harvest_mitre(state: Mapping[str, Any]) -> list[CanonicalFact]:
    out: list[CanonicalFact] = []
    decision = state.get("mitre_decision")
    if isinstance(decision, dict) and decision:
        out.append(
            CanonicalFact(
                fact_id=_fact_id("mitre_decision"),
                kind="mitre_decision",
                payload=decision,
                provenance=FactProvenance(node="mitre_finalize", evidence_class="mitre"),
            )
        )
    for mapping in state.get("mitre_mappings") or []:
        payload = mapping.model_dump() if hasattr(mapping, "model_dump") else mapping
        if not isinstance(payload, dict):
            continue
        out.append(
            CanonicalFact(
                fact_id=_fact_id("mitre_candidate"),
                kind="mitre_candidate",
                payload=payload,
                provenance=FactProvenance(node="mitre_finalize", evidence_class="mitre"),
            )
        )
    return out


def _harvest_cve(state: Mapping[str, Any]) -> list[CanonicalFact]:
    structured = state.get("structured_context")
    vuln = None
    if isinstance(structured, dict):
        vuln = structured.get("vulnerability_source")
    if not isinstance(vuln, dict) or not vuln:
        return []
    return [
        CanonicalFact(
            fact_id=_fact_id("cve_finding"),
            kind="cve_finding",
            payload=vuln,
            provenance=FactProvenance(node="cve_adapter", evidence_class="cve"),
        )
    ]


def _harvest_plan_steps(state: Mapping[str, Any]) -> list[CanonicalFact]:
    out: list[CanonicalFact] = []
    evidence_plan = state.get("evidence_plan")
    if not isinstance(evidence_plan, dict):
        return out
    resource_plan = evidence_plan.get("resource_plan")
    if not isinstance(resource_plan, dict):
        return out
    for step in resource_plan.get("steps") or []:
        if not isinstance(step, dict):
            continue
        step_id = str(step.get("step_id") or "")
        out.append(
            CanonicalFact(
                fact_id=_fact_id("plan_step_outcome"),
                kind="plan_step_outcome",
                payload={
                    "step_id": step_id,
                    "resource_id": step.get("resource_id"),
                    "purpose": step.get("purpose"),
                    "status": step.get("status"),
                },
                provenance=FactProvenance(
                    node="resource_plan",
                    step_id=step_id or None,
                    evidence_class="plan",
                ),
            )
        )
    return out


def _harvest_negative_evidence(state: Mapping[str, Any]) -> list[CanonicalFact]:
    negative = extract_negative_evidence(
        query_signals=state.get("query_signals") if isinstance(state.get("query_signals"), dict) else None,
        source_evidence=state.get("source_evidence") if isinstance(state.get("source_evidence"), list) else None,
        structured_context=state.get("structured_context") if isinstance(state.get("structured_context"), dict) else None,
    )
    if not negative:
        return []
    return [
        CanonicalFact(
            fact_id=_fact_id("negative_evidence"),
            kind="negative_evidence",
            payload=negative,
            provenance=FactProvenance(node="negative_evidence_extractor", evidence_class="unknown"),
        )
    ]


def harvest_canonical_facts_from_state(state: Mapping[str, Any]) -> CanonicalFacts:
    """Project all known state channels into an append-only fact list."""
    harvested: list[CanonicalFact] = []
    for harvester in (
        _harvest_entities,
        _harvest_source_evidence,
        _harvest_rag,
        _harvest_mcp_evidence,
        _harvest_mitre,
        _harvest_cve,
        _harvest_plan_steps,
        _harvest_negative_evidence,
    ):
        harvested.extend(harvester(state))
    return CanonicalFacts(facts=harvested)


def merge_canonical_facts(existing: CanonicalFacts | None, new_facts: CanonicalFacts) -> CanonicalFacts:
    if existing is None:
        return new_facts
    seen = {fact.fact_id for fact in existing.facts}
    merged = list(existing.facts)
    for fact in new_facts.facts:
        if fact.fact_id in seen:
            continue
        merged.append(fact)
        seen.add(fact.fact_id)
    return existing.model_copy(update={"facts": merged})


def attach_canonical_facts_to_state(state: dict[str, Any]) -> dict[str, Any]:
    """Harvest + merge facts onto pipeline state (idempotent per fact_id)."""
    harvested = harvest_canonical_facts_from_state(state)
    merged = merge_canonical_facts(get_canonical_facts(state), harvested)
    return {**state, "canonical_facts": merged.model_dump_canonical()}


def negative_evidence_from_facts(facts: CanonicalFacts | None) -> dict[str, Any] | None:
    if facts is None:
        return None
    rows = facts.facts_by_kind("negative_evidence")
    if not rows:
        return None
    payload = rows[-1].payload
    return payload if isinstance(payload, dict) else None


def facts_superset_of_master_state(state: Mapping[str, Any], facts: CanonicalFacts) -> bool:
    """True when canonical facts cover every master signal present on state."""
    kinds = facts.kinds()
    for key, required_kinds in _MASTER_FACT_SIGNALS.items():
        value = state.get(key)
        if key == "structured_context" and isinstance(value, dict) and value.get("vulnerability_source"):
            if not kinds.intersection(required_kinds):
                return False
            continue
        if key == "evidence_plan":
            ep = value if isinstance(value, dict) else {}
            rp = ep.get("resource_plan") if isinstance(ep.get("resource_plan"), dict) else {}
            if rp.get("steps") and not kinds.intersection(required_kinds):
                return False
            continue
        if value and not kinds.intersection(required_kinds):
            return False
    return True


def synthesis_fact_summary(facts: CanonicalFacts) -> dict[str, Any]:
    """Compact package for synthesis / grounding consumers."""
    return {
        "authority_holder": FACT_AUTHORITY,
        "fact_count": len(facts.facts),
        "kinds": sorted(facts.kinds()),
        "mitre_decisions": [f.payload for f in facts.facts_by_kind("mitre_decision")],
        "cve_findings": [f.payload for f in facts.facts_by_kind("cve_finding")],
        "rag_citations": [f.payload for f in facts.facts_by_kind("rag_citation")],
        "negative_evidence": [f.payload for f in facts.facts_by_kind("negative_evidence")],
        "plan_steps": [f.payload for f in facts.facts_by_kind("plan_step_outcome")],
        "executed_evidence": [f.payload for f in facts.facts_by_kind("executed_evidence")],
    }
