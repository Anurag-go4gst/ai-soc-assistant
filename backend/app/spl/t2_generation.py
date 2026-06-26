"""T1 SPL-native review-only generation entrypoint.

Ties the deterministic pipeline together for an SPL-meta turn (e.g.
``soc_generate_spl``):

    pre-parse hard tokens -> T2 shape extraction -> (optional LLM candidate,
    safely parsed) -> deterministic repair/rebuild -> review-only artifact.

The artifact is always ``execution_eligible=false`` / ``review_required=true``.
No path here executes anything or makes SPL executable.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from app.spl.deterministic_spl_repair import repair_spl_candidate
from app.spl.governed_llm_spl import parse_spl_candidate
from app.spl.t2_pre_parse import pre_parse_spl_tokens
from app.spl.t2_shape import SplShape, extract_spl_shape


@dataclass
class T2SplArtifact:
    runtime_operation: str
    source_profile: str | None
    shape: dict[str, Any]
    candidate_spl: str
    execution_eligible: bool = False
    review_required: bool = True
    renderable: bool = False
    blocked: bool = False
    repairs: list[str] = field(default_factory=list)
    block_reasons: list[str] = field(default_factory=list)
    validation_notes: list[str] = field(default_factory=list)
    llm_warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "runtime_operation": self.runtime_operation,
            "source_profile": self.source_profile,
            "shape": self.shape,
            "candidate_spl": self.candidate_spl,
            "execution_eligible": False,
            "review_required": True,
            "renderable": self.renderable,
            "blocked": self.blocked,
            "repairs": self.repairs,
            "block_reasons": self.block_reasons,
            "validation_notes": self.validation_notes,
            "llm_warnings": self.llm_warnings,
        }


def generate_review_only_spl(
    query: str,
    *,
    llm_raw_output_provider: Callable[[], str] | None = None,
) -> T2SplArtifact:
    """Produce a review-only SPL artifact for a T1 SPL-native turn."""
    tokens = pre_parse_spl_tokens(query)

    llm_shape: dict[str, Any] | None = None
    llm_candidate_spl: str | None = None
    llm_warnings: list[str] = []
    if llm_raw_output_provider is not None:
        try:
            raw = llm_raw_output_provider()
        except Exception:  # noqa: BLE001 — advisory hop must never break the turn
            raw = None
            llm_warnings.append("llm_provider_raised")
        parsed = parse_spl_candidate(raw)
        llm_warnings.extend(parsed.warnings)
        if parsed.parsed_ok:
            llm_shape = {
                "runtime_operation": parsed.runtime_operation,
                "entity_fields": parsed.entity_fields,
                "metric_fields": parsed.metric_fields,
            }
            llm_candidate_spl = parsed.candidate_spl or None

    shape: SplShape = extract_spl_shape(query, tokens=tokens, llm_shape=llm_shape)
    repaired = repair_spl_candidate(shape, llm_candidate_spl=llm_candidate_spl)

    return T2SplArtifact(
        runtime_operation=shape.runtime_operation,
        source_profile=shape.source_profile,
        shape=shape.to_dict(),
        candidate_spl=repaired.candidate_spl,
        renderable=bool(repaired.candidate_spl) and not repaired.blocked,
        blocked=repaired.blocked,
        repairs=repaired.repairs,
        block_reasons=repaired.block_reasons,
        validation_notes=[*shape.assumptions, *repaired.validation_notes],
        llm_warnings=llm_warnings,
    )
