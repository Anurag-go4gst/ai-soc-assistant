"""WS-F — deterministic grounding assembler for T2 (out-of-catalogue) rescue.

Deterministically assembles a *grounding block* from in-repo references (detection
families, enterprise MITRE candidates, ATLAS AI-threat references, SOC-KB and skill
hooks) for the guided-hunt path and weak-case LLM composition. Output is advisory
context, never authority.

Design intent (see plan 2026-06-16_1258 §14 WS-F):
- T2 questions are unknown — they may be AI/LLM/MCP-threat questions. We keep an
  ATLAS reference reachable so the depository is not lost even before full ATLAS
  data is onboarded. Today ATLAS references are IDs + tactics + case-study scores
  only (no names); a `TechniqueResolver` slot lets a later mitreattack-python /
  ATLAS-STIX backend fill in names/descriptions without changing callers.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from app.knowledge.mapping_exports import build_atlas_coverage_gap

# Keywords that flag a question as AI/LLM/MCP-threat shaped → attach ATLAS reference.
# Deterministic and intentionally broad; this only adds advisory context, never routes.
_AI_THREAT_KEYWORDS: tuple[str, ...] = (
    "llm", "large language model", "prompt injection", "jailbreak", "model theft",
    "model extraction", "data poisoning", "training data", "rag poisoning",
    "embedding", "ai model", "ml model", "machine learning model", "inference api",
    "model endpoint", "mcp server", "mcp tool", "agent", "ai assistant",
    "foundation model", "adversarial example", "model evasion",
)


@runtime_checkable
class TechniqueResolver(Protocol):
    """Resolves a technique ID (ATT&CK Txxxx or ATLAS AML.Txxxx) to detail.

    Default deployment uses :class:`NullTechniqueResolver` (returns None). A later
    offline backend built on mitreattack-python + local STIX bundles can implement
    this to return {"name", "description", "deprecated"} without touching callers.
    """

    def detail(self, technique_id: str) -> dict[str, Any] | None: ...


class NullTechniqueResolver:
    """No-op resolver — names/descriptions unavailable until STIX bundle onboarded."""

    def detail(self, technique_id: str) -> dict[str, Any] | None:  # noqa: ARG002
        return None


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
        for limitation in self.limitations:
            lines.append(f"- Limitation: {limitation}")
        return "\n".join(lines)

    def _format_ref(self, ref: dict[str, Any]) -> str:
        tid = str(ref.get("technique_id") or "")
        detail = self.technique_details.get(tid) or {}
        name = detail.get("name")
        return f"{tid} ({name})" if name else tid


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
    if coverage.get("atlas_source_status") != "onboarded_raw_layer":
        return []
    top = coverage.get("top_techniques_by_case_study_frequency") or []
    return [
        {
            "technique_id": row.get("technique_id"),
            "score": row.get("score"),
            "tactics": list(row.get("tactics") or []),
        }
        for row in top[:limit]
    ]


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

    if atlas_refs and not block.technique_details:
        block.limitations.append(
            "ATLAS references are technique IDs + tactics + case-study scores only; "
            "onboard the ATLAS STIX bundle (via a mitreattack-python-backed resolver) "
            "for names/descriptions."
        )
    if ai_signal and not atlas_refs:
        block.limitations.append("AI-threat question detected but ATLAS taxonomy is not onboarded.")

    return block
