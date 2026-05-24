from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.orchestration.human_review import human_review

# Modes that describe what kind of answer the collected package could support.
# Synthesis itself is NOT enabled in this stage; these are readiness signals only.
FULL_ANSWER = "full_answer"
PARTIAL_ANSWER = "partial_answer"
ANALYST_REVIEW_REQUIRED = "analyst_review_required"
SPL_REVIEW_ONLY = "spl_review_only"
KNOWLEDGE_ONLY_ANSWER = "knowledge_only_answer"
BLOCKED_BY_POLICY = "blocked_by_policy"
INSUFFICIENT_EVIDENCE = "insufficient_evidence"

# Modes for which a future synthesis stage may proceed once it is implemented.
# Synthesis still stays gated by `synthesis_allowed`, which remains False here.
_READY_MODES = {FULL_ANSWER, PARTIAL_ANSWER, KNOWLEDGE_ONLY_ANSWER}

# Keyword hooks for an asset-criticality claim. The structurer does not yet emit
# an explicit criticality field, so this rule only fires on keyworded facts.
_ASSET_CRITICALITY_KEYWORDS = ("crown jewel", "critical asset", "asset criticality", "high-value asset", "business critical")

# Source types that are advisory candidate-SPL producers, never execution evidence.
_CANDIDATE_SPL_SOURCE_TYPES = {"splunk_mcp_saia"}


@dataclass
class ContextSufficiencyResult:
    """Typed result of the context sufficiency gate.

    `synthesis_readiness` reflects whether the evidence package *would* support
    synthesis. The hard `synthesis_allowed` kill-switch (always False in this
    stage) is owned by the not-yet-built synthesis stage.
    """

    mode: str
    reasons: list[str] = field(default_factory=list)
    missing_evidence: list[str] = field(default_factory=list)
    human_review: dict[str, Any] | None = None

    @property
    def synthesis_readiness(self) -> bool:
        # Single source of truth: readiness follows the mode, not per-branch flags.
        return self.mode in _READY_MODES

    def to_envelope(self) -> dict[str, Any]:
        return {
            "status": self.mode,
            "synthesis_allowed": False,
            "synthesis_readiness": self.synthesis_readiness,
            "reasons": sorted(set(self.reasons)),
            "missing_evidence": sorted(set(self.missing_evidence)),
            "human_review": self.human_review,
        }


def check_context_sufficiency(
    structured_context: dict[str, Any],
    source_evidence: list[dict[str, Any]],
) -> dict[str, Any]:
    """Classify the SourceEvidence + StructuredContext package into one answer mode.

    Drop-in replacement for the prior pass/partial/fail gate: still returns a dict
    consumed by the chat route, now with a seven-mode `status` plus `synthesis_readiness`.
    """
    return _classify(structured_context, source_evidence).to_envelope()


def _classify(
    structured_context: dict[str, Any],
    source_evidence: list[dict[str, Any]],
) -> ContextSufficiencyResult:
    missing_evidence = list(structured_context.get("missing_evidence") or [])
    collected = [item for item in source_evidence if item.get("collection_status") == "collected"]
    facts = structured_context.get("structured_facts") or []

    # Rule 1: a sensitive leak blocks synthesis readiness outright.
    if any(item.get("sensitivity_flags") for item in collected):
        return ContextSufficiencyResult(
            mode=BLOCKED_BY_POLICY,
            reasons=["sensitive_leak_detected"],
            missing_evidence=missing_evidence,
            human_review=_blocked_review("sensitive_evidence_leak_detected"),
        )

    # Rule 2: execution blocked by policy / HIL gate.
    if structured_context.get("context_quality") == "blocked":
        return ContextSufficiencyResult(
            mode=BLOCKED_BY_POLICY,
            reasons=["context_collection_blocked"],
            missing_evidence=missing_evidence,
            human_review=_blocked_review("context_collection_blocked"),
        )

    # Rule 3: ambiguous knowledge retrieval needs an analyst (retrieval happened
    # but could not be disambiguated, so it is neither "collected" nor empty).
    if any(item.get("source_type") == "rag" and item.get("collection_status") == "ambiguous" for item in source_evidence):
        return ContextSufficiencyResult(
            mode=ANALYST_REVIEW_REQUIRED,
            reasons=["knowledge_ambiguity_requires_review"],
            missing_evidence=missing_evidence,
            human_review=_analyst_review("knowledge_ambiguity_requires_review"),
        )

    # Rule 4: nothing was collected at all.
    if not collected:
        return ContextSufficiencyResult(
            mode=INSUFFICIENT_EVIDENCE,
            reasons=["no_collected_evidence"],
            missing_evidence=missing_evidence,
        )

    # Rule 5: structured facts must always cite a source.
    if any(not fact.get("source_refs") for fact in facts):
        return ContextSufficiencyResult(
            mode=INSUFFICIENT_EVIDENCE,
            reasons=["structured_fact_missing_source_refs"],
            missing_evidence=missing_evidence,
        )

    # Rule 6: a MITRE conclusion requires MITRE grounding.
    if structured_context.get("mitre_candidates") and not structured_context.get("mitre_grounding_refs"):
        return ContextSufficiencyResult(
            mode=ANALYST_REVIEW_REQUIRED,
            reasons=["mitre_conclusion_requires_grounding"],
            missing_evidence=[*missing_evidence, "mitre_grounding"],
            human_review=_analyst_review("mitre_conclusion_requires_grounding"),
        )

    # Rule 7: an asset-criticality claim requires asset/environment evidence.
    if _has_asset_criticality_claim(facts) and not structured_context.get("environment_grounding_refs"):
        return ContextSufficiencyResult(
            mode=ANALYST_REVIEW_REQUIRED,
            reasons=["asset_criticality_requires_asset_evidence"],
            missing_evidence=[*missing_evidence, "asset_evidence"],
            human_review=_analyst_review("asset_criticality_requires_asset_evidence"),
        )

    has_execution = any(item.get("source_type") in {"mcp", "splunk_mcp"} for item in collected)
    has_rag = any(item.get("source_type") == "rag" for item in collected)
    only_candidate_spl = all(item.get("source_type") in _CANDIDATE_SPL_SOURCE_TYPES for item in collected)

    # Rule 8: SAIA / candidate SPL alone is advisory; it cannot back an execution answer.
    if only_candidate_spl:
        return ContextSufficiencyResult(
            mode=SPL_REVIEW_ONLY,
            reasons=["candidate_spl_advisory_only_no_execution_evidence"],
            missing_evidence=missing_evidence,
        )

    # Rule 9: knowledge-only evidence supports SOP/knowledge guidance.
    if has_rag and not has_execution:
        return ContextSufficiencyResult(
            mode=KNOWLEDGE_ONLY_ANSWER,
            reasons=["knowledge_guidance_supported_by_governed_rag"],
            missing_evidence=missing_evidence,
        )

    # Rule 10: execution evidence present but required/optional gaps remain.
    if missing_evidence:
        return ContextSufficiencyResult(
            mode=PARTIAL_ANSWER,
            reasons=["missing_optional_or_required_evidence"],
            missing_evidence=missing_evidence,
        )

    # Rule 11: grounded execution evidence with no gaps.
    return ContextSufficiencyResult(
        mode=FULL_ANSWER,
        reasons=[],
        missing_evidence=[],
    )


def _has_asset_criticality_claim(facts: list[dict[str, Any]]) -> bool:
    for fact in facts:
        statement = str(fact.get("statement") or "").lower()
        if any(keyword in statement for keyword in _ASSET_CRITICALITY_KEYWORDS):
            return True
    return False


def _blocked_review(reason: str) -> dict[str, Any]:
    return human_review(
        "execution_approval",
        reason,
        "soc_lead",
        ["approve_execution_after_policy_check", "reject_execution"],
        "Context collection is blocked by policy; synthesis stays disabled until a SOC lead reviews evidence collection.",
    )


def _analyst_review(reason: str) -> dict[str, Any]:
    return human_review(
        "analyst_review",
        reason,
        "soc_analyst",
        ["approve_after_analyst_review", "request_more_evidence"],
        "Collected context needs analyst review before any answer can be grounded.",
    )
