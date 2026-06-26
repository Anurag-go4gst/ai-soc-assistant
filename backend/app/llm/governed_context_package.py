"""Shared governed context for sidecar LLM calls (no raw MCP rows).

Two builders:

- ``build_governed_context_package_v1`` — thin, used at the intent node where only
  registry candidates exist (no contract/evidence yet).
- ``build_governed_context_package_for_contract`` — richer, used at finalize-stage
  sidecars (missing-evidence reasoner) where the ``AnswerContract``, redacted SOC-KB
  snippets, and evidence-plan resource decisions are available.

Both exclude credentials, executable SPL authority, and raw MCP rows by construction:
callers pass only already-redacted strings, and the package never reaches into
``SourceEvidence`` payloads itself.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from app.safeguards.evidence_sanitizer import redact_secret_values

from app.query_understanding.models import QueryUnderstandingResult

if TYPE_CHECKING:
    from app.chat.contracts.answer_contract import AnswerContract


logger = logging.getLogger(__name__)

# Default character budget for a sidecar prompt context block. Kept in characters
# (not tokens) so truncation is deterministic and unit-testable without a tokenizer;
# ~4 chars/token => ~1.5k tokens, comfortably inside role ``max_input_tokens``.
DEFAULT_MAX_CONTEXT_CHARS = 6000
CONTEXT_TRUNCATION_MARKER = "context_truncation"


@dataclass(frozen=True)
class GovernedContextPackage:
    raw_query: str
    registry_question_candidates: list[str] = field(default_factory=list)
    registry_use_case_candidates: list[str] = field(default_factory=list)
    match_path: str | None = None
    routed_skill: str | None = None
    limitations: list[str] = field(default_factory=list)
    # Finalize-stage enrichment (empty for the thin intent-node package).
    answer_mode: str | None = None
    hil_status: str | None = None
    missing_evidence: list[str] = field(default_factory=list)
    required_evidence: list[str] = field(default_factory=list)
    candidate_mitre: list[str] = field(default_factory=list)
    not_claimed_mitre: list[str] = field(default_factory=list)
    unsupported_claims_avoid: list[str] = field(default_factory=list)
    resource_decisions: list[str] = field(default_factory=list)
    soc_kb_snippets: list[str] = field(default_factory=list)
    # Phase 2.5 — skill metadata + MCP tool capability hints (descriptions only,
    # never execution schema or credentials). For out-of-catalog / weak composition.
    skill_sections: list[str] = field(default_factory=list)
    mcp_tool_hints: list[str] = field(default_factory=list)
    t2_grounding_block: str | None = None
    use_case_id: str | None = None

    def to_prompt_block(self, *, max_chars: int = DEFAULT_MAX_CONTEXT_CHARS) -> str:
        """Render an ordered, redacted context block, truncating low-priority
        sections first when over ``max_chars``. Highest-priority context (query,
        registry candidates, contract findings) is preserved; SOC-KB snippets and
        resource decisions are dropped first because they are the most verbose."""
        # (priority, label, values) — lower priority number = kept longest.
        priced_sections: list[tuple[int, str, list[str]]] = [
            (3, "registry_question_candidates", self.registry_question_candidates[:8]),
            (3, "registry_use_case_candidates", self.registry_use_case_candidates[:8]),
            (2, "missing_evidence", self.missing_evidence[:10]),
            (2, "required_evidence", self.required_evidence[:10]),
            (2, "candidate_mitre", self.candidate_mitre[:12]),
            (2, "not_claimed_mitre", self.not_claimed_mitre[:12]),
            (2, "do_not_claim", self.unsupported_claims_avoid[:10]),
            (3, "limitations", self.limitations[:8]),
            (4, "skill_sections", self.skill_sections[:8]),
            (4, "t2_grounding", [self.t2_grounding_block] if self.t2_grounding_block else []),
            (5, "mcp_tool_hints", self.mcp_tool_hints[:8]),
            (5, "resource_decisions", self.resource_decisions[:10]),
            (6, "soc_kb_snippets", self.soc_kb_snippets[:6]),
        ]
        scalars = [f"raw_query: {_sanitize_prompt_fragment(self.raw_query)}"]
        for label, value in (
            ("match_path", self.match_path),
            ("routed_skill", self.routed_skill),
            ("answer_mode", self.answer_mode),
            ("hil_status", self.hil_status),
            ("use_case_id", self.use_case_id),
        ):
            if value:
                scalars.append(f"{label}: {_sanitize_prompt_fragment(str(value))}")

        def render(sections: list[tuple[int, str, list[str]]]) -> str:
            lines = [_sanitize_prompt_fragment(line) for line in scalars]
            for _, label, values in sections:
                if values:
                    sanitized = "; ".join(_sanitize_prompt_fragment(str(v)) for v in values)
                    lines.append(f"{label}: {sanitized}")
            return "\n".join(lines)

        block = render(priced_sections)
        if len(block) <= max_chars:
            return block

        # Over budget: drop sections by descending priority number until it fits.
        kept = sorted(priced_sections, key=lambda item: item[0])
        while kept and len(render(kept)) > max_chars:
            kept.pop()  # remove the lowest-priority (highest number) section
        rendered = render(kept)
        logger.info(
            "%s applied: %d chars over %d budget; kept %d sections",
            CONTEXT_TRUNCATION_MARKER,
            len(block),
            max_chars,
            len(kept),
        )
        return rendered + f"\n{CONTEXT_TRUNCATION_MARKER}: true"


from collections import OrderedDict

# P2-B: cache stable context prompt blocks within a process (bounded LRU).
_CONTEXT_PROMPT_CACHE: OrderedDict[str, str] = OrderedDict()
_CONTEXT_CACHE_MAX = 64


def cached_context_prompt_block(package: GovernedContextPackage, *, max_chars: int = DEFAULT_MAX_CONTEXT_CHARS) -> str:
    """Return ``package.to_prompt_block()`` with a bounded in-process cache.

    The cache key must cover every input that changes the rendered block — all
    package fields (not just query/match_path/skill) and ``max_chars`` — otherwise a
    thin intent-node package and a finalize-stage enriched package for the same query
    collide and the second caller gets a stale block.
    """
    import dataclasses

    key = hashlib.sha256(
        (repr(dataclasses.astuple(package)) + f"|max_chars={max_chars}").encode()
    ).hexdigest()[:32]
    cached = _CONTEXT_PROMPT_CACHE.get(key)
    if cached is not None:
        _CONTEXT_PROMPT_CACHE.move_to_end(key)
        return cached
    block = package.to_prompt_block(max_chars=max_chars)
    _CONTEXT_PROMPT_CACHE[key] = block
    if len(_CONTEXT_PROMPT_CACHE) > _CONTEXT_CACHE_MAX:
        _CONTEXT_PROMPT_CACHE.popitem(last=False)
    return block


def build_governed_context_package_v1(
    *,
    query: str,
    query_understanding: QueryUnderstandingResult | None = None,
    candidate_mappings: dict[str, Any] | None = None,
    routed_skill: str | None = None,
) -> GovernedContextPackage:
    """Thin package for the intent node (registry candidates only)."""
    mappings = candidate_mappings or {}
    question_candidates = _question_candidates(mappings, query_understanding)
    use_case_candidates = _use_case_candidates(mappings, query_understanding)
    return GovernedContextPackage(
        raw_query=query,
        registry_question_candidates=question_candidates,
        registry_use_case_candidates=use_case_candidates,
        match_path=str(mappings.get("match_path") or "") or None,
        routed_skill=routed_skill,
    )


def build_governed_context_package_for_contract(
    *,
    query: str,
    contract: "AnswerContract",
    soc_kb_snippets: list[str] | None = None,
    resource_decisions: list[str] | None = None,
    skill_sections: list[str] | None = None,
    mcp_tool_hints: list[str] | None = None,
    t2_grounding_block: str | None = None,
    routed_skill: str | None = None,
) -> GovernedContextPackage:
    """Rich package for finalize-stage sidecars + out-of-catalog composition.

    ``soc_kb_snippets`` must already be redacted text excerpts (never raw MCP rows).
    ``mcp_tool_hints`` are one-line tool capability descriptions — never execution
    schema, parameters, or credentials.
    """
    return GovernedContextPackage(
        raw_query=query,
        match_path=None,
        routed_skill=routed_skill,
        answer_mode=contract.answer_mode,
        hil_status=str(contract.hil_status) if contract.hil_status else None,
        missing_evidence=[str(item) for item in contract.missing_evidence if item],
        required_evidence=[str(item) for item in (contract.required_evidence or []) if item],
        candidate_mitre=[str(item) for item in contract.candidate_mitre if item],
        not_claimed_mitre=[str(item) for item in contract.not_claimed_mitre if item],
        unsupported_claims_avoid=[str(item) for item in contract.unsupported_claims_avoid if item],
        limitations=[str(item) for item in contract.limitations if item],
        resource_decisions=[str(item) for item in (resource_decisions or []) if item],
        soc_kb_snippets=[str(item) for item in (soc_kb_snippets or []) if item],
        skill_sections=[str(item) for item in (skill_sections or []) if item],
        mcp_tool_hints=[str(item) for item in (mcp_tool_hints or []) if item],
        t2_grounding_block=t2_grounding_block,
        use_case_id=contract.use_case_id,
    )


def _question_candidates(
    mappings: dict[str, Any],
    query_understanding: QueryUnderstandingResult | None,
) -> list[str]:
    candidates: list[str] = []
    ref = mappings.get("question_ref")
    if isinstance(ref, str) and ref:
        candidates.append(ref)
    if query_understanding and query_understanding.mapped_question_ref:
        if query_understanding.mapped_question_ref not in candidates:
            candidates.append(query_understanding.mapped_question_ref)
    return candidates


def _use_case_candidates(
    mappings: dict[str, Any],
    query_understanding: QueryUnderstandingResult | None,
) -> list[str]:
    candidates: list[str] = []
    for item in mappings.get("use_case_ids") or []:
        if item:
            candidates.append(str(item))
    if query_understanding:
        for item in query_understanding.mapped_use_case_ids or []:
            if item and str(item) not in candidates:
                candidates.append(str(item))
    return candidates


def _sanitize_prompt_fragment(text: str) -> str:
    return redact_secret_values(text)
