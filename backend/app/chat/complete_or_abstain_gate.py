"""T1-T3 complete-or-abstain acceptance gate (deterministic).

Frozen ``architecture.md`` §2.2 requires T1-T3 to either ACCEPT a complete,
sufficiently confident governed match or ABSTAIN **completely** from semantic
authority. There is no third outcome: a partially committed semantic contract
for T4 to patch field-by-field is exactly what the architecture forbids.

This module owns that single decision. It is a pure projection over already
computed deterministic signals:

* no LLM call, no route selection, no capability/tool grant, no execution authority
* no I/O, no registry lookup, no clock
* it never *produces* a contract; it only says whether one may be committed

The candidate interface is deliberately source-agnostic. T3 lexical/catalogue
candidates populate it today; when embedding/vector retrieval arrives it becomes
an additional candidate *source* feeding the same gate, never a new authority
tier (architecture "Future T3 vector / embedding matching"). Embeddings are not
implemented here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from app.chat.lane_router import initial_tier_for_match_path

UnderstandingDecision = Literal["ACCEPT", "ABSTAIN"]

CandidateSource = Literal["lexical", "embedding"]

#: Governed tiers whose match may carry a complete deterministic understanding.
GOVERNED_TIERS = frozenset({"T1", "T2", "T3"})

#: Minimum winner confidence for ACCEPT. Mirrors the deterministic routing floor
#: rather than inventing a second number.
DEFAULT_MIN_CONFIDENCE = 0.70

#: Minimum gap between the best and the runner-up candidate. A crowded field is
#: ambiguous even when the winner clears the confidence floor, and the
#: architecture lists "low margin / ambiguous candidates" as an abstain trigger.
DEFAULT_MIN_MARGIN = 0.10

#: Reasons that block *both* ACCEPT arms (catalogue and complete-deterministic).
_HARD_INCOMPLETE_REASONS = frozenset(
    {
        "not_fully_governed",
        "policy_blocked",
        "clarification_required",
        "completeness_incomplete",
        "missing_required_fields",
        "unresolved_semantic_fields",
        "semantic_incompatibility",
    }
)


@dataclass(frozen=True)
class MatchCandidate:
    """One T1-T3 candidate offered to the gate.

    ``source`` records how the candidate was retrieved. It is provenance only:
    the gate applies identical rules to every source, so an embedding candidate
    can never outrank the deterministic checks below.
    """

    candidate_id: str
    match_path: str
    confidence: float
    source: CandidateSource = "lexical"


@dataclass(frozen=True)
class UnderstandingAcceptance:
    """Outcome of the gate. ``ABSTAIN`` carries no partial semantic commitment."""

    decision: UnderstandingDecision
    tier: str
    reason_codes: tuple[str, ...] = ()
    accepted_candidate_id: str | None = None
    winner_confidence: float | None = None
    winner_margin: float | None = None
    candidate_sources: tuple[str, ...] = field(default_factory=tuple)

    @property
    def is_accept(self) -> bool:
        return self.decision == "ACCEPT"

    @property
    def is_abstain(self) -> bool:
        return self.decision == "ABSTAIN"

    @property
    def t4_permitted(self) -> bool:
        """T4 runs only after a complete abstain (architecture §2.2 branch B)."""
        return self.is_abstain


def _ranked(candidates: tuple[MatchCandidate, ...]) -> list[MatchCandidate]:
    return sorted(candidates, key=lambda c: (-float(c.confidence), c.candidate_id))


def evaluate_complete_or_abstain(
    *,
    match_path: str | None,
    candidates: tuple[MatchCandidate, ...] | list[MatchCandidate] = (),
    completeness_status: str | None = None,
    clarification_required: bool = False,
    policy_blocked: bool = False,
    unresolved_fields: tuple[str, ...] | list[str] = (),
    missing_required_fields: tuple[str, ...] | list[str] = (),
    semantically_compatible: bool = True,
    fully_governed: bool = True,
    semantic_contract_complete: bool = False,
    min_confidence: float = DEFAULT_MIN_CONFIDENCE,
    min_margin: float = DEFAULT_MIN_MARGIN,
) -> UnderstandingAcceptance:
    """Decide ACCEPT (commit the complete contract, skip T4) or ABSTAIN.

    Every abstain trigger named by the architecture is checked, and **all**
    applicable reason codes are collected rather than short-circuiting on the
    first one, so provenance can explain the decision (P4) without re-deriving it.

    Two ACCEPT arms (both skip T4):

    1. Catalogue T1–T3 complete governed match (confidence + margin + no gaps).
    2. ``semantic_contract_complete`` — deterministic stages already resolved every
       material semantic dimension. Covers fully specified review-only SPL
       authoring and other out_of_registry happy paths that do not need a
       semantic hop. Catalogue-tier confidence/margin and ``not_governed_tier``
       do not veto this arm.
    """
    ordered = _ranked(tuple(candidates))
    tier = initial_tier_for_match_path(match_path)
    reasons: list[str] = []

    if not fully_governed:
        reasons.append("not_fully_governed")
    if policy_blocked:
        reasons.append("policy_blocked")
    if clarification_required or completeness_status == "clarification_required":
        reasons.append("clarification_required")
    if completeness_status == "incomplete":
        reasons.append("completeness_incomplete")
    if list(missing_required_fields):
        reasons.append("missing_required_fields")
    # An unresolved field is precisely the partial-contract signal the frozen
    # architecture refuses to hand to T4 as a patch list. It forces a full abstain.
    if list(unresolved_fields):
        reasons.append("unresolved_semantic_fields")
    if not semantically_compatible:
        reasons.append("semantic_incompatibility")

    winner = ordered[0] if ordered else None
    winner_confidence = float(winner.confidence) if winner is not None else None
    winner_margin: float | None = None
    if winner is not None:
        runner_up = ordered[1] if len(ordered) > 1 else None
        winner_margin = (
            float(winner.confidence) - float(runner_up.confidence) if runner_up is not None else None
        )

    if tier not in GOVERNED_TIERS:
        reasons.append("not_governed_tier")
    elif winner is None:
        reasons.append("no_candidate")
    else:
        if winner_confidence is not None and winner_confidence < min_confidence:
            reasons.append("low_confidence")
        if winner_margin is not None and winner_margin < min_margin:
            reasons.append("low_margin")

    sources = tuple(sorted({str(c.source) for c in ordered}))
    hard_incomplete = bool(_HARD_INCOMPLETE_REASONS & set(reasons))

    # Arm 2: complete deterministic understanding (may be out_of_registry).
    if semantic_contract_complete and not hard_incomplete:
        return UnderstandingAcceptance(
            decision="ACCEPT",
            tier=tier,
            reason_codes=("complete_deterministic_understanding",),
            accepted_candidate_id=winner.candidate_id if winner is not None else None,
            winner_confidence=winner_confidence,
            winner_margin=winner_margin,
            candidate_sources=sources,
        )

    if reasons:
        return UnderstandingAcceptance(
            decision="ABSTAIN",
            tier=tier,
            reason_codes=tuple(sorted(set(reasons))),
            accepted_candidate_id=None,
            winner_confidence=winner_confidence,
            winner_margin=winner_margin,
            candidate_sources=sources,
        )

    return UnderstandingAcceptance(
        decision="ACCEPT",
        tier=tier,
        reason_codes=("complete_governed_match",),
        accepted_candidate_id=winner.candidate_id if winner is not None else None,
        winner_confidence=winner_confidence,
        winner_margin=winner_margin,
        candidate_sources=sources,
    )
