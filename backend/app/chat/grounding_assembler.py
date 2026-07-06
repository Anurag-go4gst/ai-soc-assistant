"""WS-F — deterministic grounding assembler for T2 (out-of-catalogue) rescue.

Deterministically assembles a *grounding block* from in-repo references (detection
families, enterprise MITRE candidates, ATLAS AI-threat references, SOC-KB and skill
hooks) for the guided-hunt path and weak-case LLM composition. Output is advisory
context, never authority.

Design intent (see plan 2026-06-16_1258 §14 WS-F):
- T2 questions are unknown — they may be AI/LLM/MCP-threat questions. We keep an
  ATLAS reference reachable so the depository is not lost even before full ATLAS
  data is onboarded. Today ATLAS references are IDs + tactics + case-study scores
  only (no names); a `TechniqueResolver` slot lets an offline ATT&CK-Excel /
  ATLAS-YAML or STIX backend fill in names/descriptions without changing callers.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.knowledge.atlas_attack_crosswalk import (
    atlas_technique_suggested_remediation,
    atlas_technique_to_template_hints,
)
from app.knowledge.mapping_exports import atlas_technique_enrichment, build_atlas_coverage_gap
from app.planner.reference_registry import AI_THREAT_KEYWORDS as _AI_THREAT_KEYWORDS
from app.threat.attack_data_resolver import technique_resolver_from_settings
from app.threat.resolver_types import NullTechniqueResolver, TechniqueResolver


@dataclass
class GroundingBlock:
    """Deterministic advisory context for a T2 rescue prompt. Never authority."""

    question: str
    ai_threat_signal: bool = False
    detection_families: list[str] = field(default_factory=list)
    enterprise_mitre_refs: list[str] = field(default_factory=list)
    atlas_references: list[dict[str, Any]] = field(default_factory=list)
    soc_kb_refs: list[str] = field(default_factory=list)
    skill_refs: list[str] = field(default_factory=list)
    technique_details: dict[str, dict[str, Any]] = field(default_factory=dict)
    limitations: list[str] = field(default_factory=list)
    environment_kb_slots: list[str] = field(default_factory=list)
    asset_registry_hints: list[str] = field(default_factory=list)
    evidence_citations: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "question": self.question,
            "ai_threat_signal": self.ai_threat_signal,
            "detection_families": list(self.detection_families),
            "enterprise_mitre_refs": list(self.enterprise_mitre_refs),
            "atlas_references": list(self.atlas_references),
            "soc_kb_refs": list(self.soc_kb_refs),
            "skill_refs": list(self.skill_refs),
            "technique_details": dict(self.technique_details),
            "limitations": list(self.limitations),
            "environment_kb_slots": list(self.environment_kb_slots),
            "asset_registry_hints": list(self.asset_registry_hints),
            "evidence_citations": list(self.evidence_citations),
        }

    def to_prompt_block(self) -> str:
        """Render advisory grounding text for a sidecar prompt. Advisory only."""
        lines: list[str] = ["GROUNDING CONTEXT (advisory only — not authority, not evidence):"]
        if self.detection_families:
            lines.append("- Candidate detection families: " + ", ".join(self.detection_families))
        if self.enterprise_mitre_refs:
            lines.append("- Candidate ATT&CK techniques (advisory): " + ", ".join(self.enterprise_mitre_refs))
        if self.atlas_references:
            refs = ", ".join(
                self._format_ref(ref) for ref in self.atlas_references
            )
            lines.append("- MITRE ATLAS AI-threat references (advisory taxonomy): " + refs)
        for ref in self.soc_kb_refs:
            lines.append(f"- SOC-KB reference: {ref}")
        for ref in self.skill_refs:
            lines.append(f"- Skill reference: {ref}")
        for slot in self.environment_kb_slots:
            lines.append(f"- Environment KB slot: {slot}")
        for hint in self.asset_registry_hints:
            lines.append(f"- Asset registry hint: {hint}")
        for limitation in self.limitations:
            lines.append(f"- Limitation: {limitation}")
        return "\n".join(lines)

    def _format_ref(self, ref: dict[str, Any]) -> str:
        tid = str(ref.get("technique_id") or "")
        detail = self.technique_details.get(tid) or {}
        name = detail.get("name")
        base = f"{tid} ({name})" if name else tid
        extras: list[str] = []
        mitigation_names = [
            str(item.get("name") or "")
            for item in ref.get("mitigations") or []
            if isinstance(item, dict) and str(item.get("name") or "").strip()
        ][:2]
        case_names = [
            str(item.get("name") or "")
            for item in ref.get("case_studies") or []
            if isinstance(item, dict) and str(item.get("name") or "").strip()
        ][:2]
        if mitigation_names:
            extras.append("mitigations: " + ", ".join(mitigation_names))
        if case_names:
            extras.append("case studies: " + ", ".join(case_names))
        return f"{base}; {'; '.join(extras)}" if extras else base


def detect_ai_threat_signal(question: str) -> bool:
    lowered = (question or "").lower()
    return any(keyword in lowered for keyword in _AI_THREAT_KEYWORDS)


def atlas_reference_for_question(question: str, *, limit: int = 8) -> list[dict[str, Any]]:
    """Return frequency-ranked ATLAS AML references when a question looks AI-threat shaped.

    Keeps the ATLAS depository reachable for unknown T2 questions even before the
    full ATLAS STIX bundle is onboarded. Returns [] when no AI signal or ATLAS is
    not onboarded — fail-closed, never fabricates.
    """
    if not detect_ai_threat_signal(question):
        return []
    coverage = build_atlas_coverage_gap()
    # Accept any onboarded ATLAS source (raw Navigator layer or the E3 normalized
    # canonical layer); only a not_onboarded deployment yields no references.
    if not str(coverage.get("atlas_source_status") or "").startswith("onboarded"):
        return []
    top = coverage.get("top_techniques_by_case_study_frequency") or []
    refs: list[dict[str, Any]] = []
    for row in top[:limit]:
        technique_id = str(row.get("technique_id") or "")
        if not technique_id:
            continue
        enrichment = atlas_technique_enrichment(technique_id)
        ref: dict[str, Any] = {
            "technique_id": technique_id,
            "score": row.get("score"),
            "tactics": list(row.get("tactics") or []),
            "mitigations": list(enrichment.get("mitigations") or []),
            "case_studies": list(enrichment.get("case_studies") or []),
        }
        template_ids = atlas_technique_to_template_hints(technique_id)
        if template_ids:
            detail = technique_resolver_from_settings().detail(technique_id)
            attack_ref = str((detail or {}).get("attack_technique_ref") or "")
            ref["suggested_detection_hint"] = {
                "attack_technique_ref": attack_ref,
                "template_ids": template_ids,
                "disclaimer": (
                    "heuristic tactic/technique overlap via MITRE's own ATLAS→ATT&CK crosswalk, "
                    "not an official ATLAS-to-SPL mapping; run only if you judge it relevant"
                ),
            }
        remediation = atlas_technique_suggested_remediation(technique_id)
        if remediation:
            ref["remediation_preview"] = {
                "text": str(remediation.get("text") or ""),
                "availability": "not_available_this_tier",
                "note": (
                    "Descriptive only — no action is taken or proposed. Live remediation requires "
                    "a separate, explicitly-approved capability tier change."
                ),
            }
        refs.append(ref)
    return refs


def assemble_grounding(
    question: str,
    *,
    resolver: TechniqueResolver | None = None,
    detection_families: list[str] | None = None,
    enterprise_mitre_refs: list[str] | None = None,
    soc_kb_refs: list[str] | None = None,
    skill_refs: list[str] | None = None,
) -> GroundingBlock:
    """Deterministically assemble a T2 grounding block.

    Detection families, enterprise MITRE refs, SOC-KB and skill refs are passed in by
    the caller from deterministic registries; this module owns the ATLAS AI-threat
    reference resolution and the resolver-backed technique detail lookup.
    """
    resolver = resolver or NullTechniqueResolver()
    ai_signal = detect_ai_threat_signal(question)
    atlas_refs = atlas_reference_for_question(question)

    block = GroundingBlock(
        question=question,
        ai_threat_signal=ai_signal,
        detection_families=list(detection_families or []),
        enterprise_mitre_refs=list(enterprise_mitre_refs or []),
        atlas_references=atlas_refs,
        soc_kb_refs=list(soc_kb_refs or []),
        skill_refs=list(skill_refs or []),
    )

    # Resolve names/descriptions where a backend is available (None by default).
    for tid in list(block.enterprise_mitre_refs) + [str(r.get("technique_id") or "") for r in atlas_refs]:
        if not tid or tid in block.technique_details:
            continue
        detail = resolver.detail(tid)
        if detail:
            block.technique_details[tid] = detail

    atlas_ids = [str(r.get("technique_id") or "") for r in atlas_refs]
    atlas_names_resolved = any(tid in block.technique_details for tid in atlas_ids if tid)
    if atlas_refs and not atlas_names_resolved:
        block.limitations.append(
            "ATLAS references are technique IDs + tactics + case-study scores only; "
            "onboard the vendored ATLAS YAML (or STIX bundle) resolver for names/descriptions."
        )
    if ai_signal and not atlas_refs:
        block.limitations.append("AI-threat question detected but ATLAS taxonomy is not onboarded.")

    return block


def assemble_grounding_from_facts(
    facts: Any,
    question: str,
    *,
    resolver: TechniqueResolver | None = None,
    detection_families: list[str] | None = None,
    skill_refs: list[str] | None = None,
) -> GroundingBlock:
    """Item 5.4 — build a GroundingBlock from the CanonicalFacts spine.

    `facts` is an `app.chat.contracts.canonical_facts.CanonicalFacts` instance
    (typed as `Any` here to avoid a hard import-time dependency in this module).
    Row-derived evidence citations (with lineage: evidence_id, source_type) are
    surfaced when executed evidence exists; when it doesn't, an honest
    limitation is recorded instead of silently omitting the gap. MITRE/RAG refs
    are read from the spine rather than requiring the caller to pass them in.
    Deterministic facts remain overlay authority elsewhere (answer/adapter
    validators) — this is advisory grounding context only, never authority.
    """
    enterprise_mitre_refs: list[str] = []
    for mitre_fact in facts.facts_by_kind("mitre_decision"):
        for technique in mitre_fact.payload.get("techniques") or []:
            tid = technique.get("technique_id") if isinstance(technique, dict) else None
            if tid and tid not in enterprise_mitre_refs:
                enterprise_mitre_refs.append(tid)

    soc_kb_refs: list[str] = []
    for rag_fact in facts.facts_by_kind("rag_citation"):
        citation = rag_fact.payload.get("citation")
        if isinstance(citation, dict):
            ref = citation.get("ref") or citation.get("title") or citation.get("source")
            if ref:
                soc_kb_refs.append(str(ref))

    block = assemble_grounding(
        question,
        resolver=resolver,
        detection_families=detection_families,
        enterprise_mitre_refs=enterprise_mitre_refs,
        soc_kb_refs=soc_kb_refs,
        skill_refs=skill_refs,
    )

    evidence_citations: list[dict[str, Any]] = []
    for evidence_fact in facts.facts_by_kind("executed_evidence"):
        payload = evidence_fact.payload
        row_count = payload.get("row_count")
        evidence_id = payload.get("evidence_id")
        if evidence_id and isinstance(row_count, int) and row_count > 0:
            evidence_citations.append(
                {
                    "evidence_id": evidence_id,
                    "source_type": payload.get("source_type"),
                    "row_count": row_count,
                    "row_summary": payload.get("row_summary") or [],
                }
            )
    block.evidence_citations = evidence_citations
    if not evidence_citations:
        block.limitations.append(
            "No executed evidence rows available for this turn; grounding is "
            "advisory taxonomy only, not evidence-backed."
        )
    return block
