"""Phase 2 (I7): expanded GovernedContextPackage for finalize-stage sidecars."""

from __future__ import annotations

from app.chat.contracts.answer_contract import AnswerContract
from app.llm.governed_context_package import (
    CONTEXT_TRUNCATION_MARKER,
    GovernedContextPackage,
    build_governed_context_package_for_contract,
    build_governed_context_package_v1,
    cached_context_prompt_block,
)


def _contract(**overrides) -> AnswerContract:
    base = dict(
        intent_family="alert_triage",
        answer_mode="live_investigation",
        missing_evidence=["mfa_status", "post_login_activity"],
        limitations=["No source IP ownership confirmed"],
        candidate_mitre=["T1110"],
        not_claimed_mitre=["T1078"],
        unsupported_claims_avoid=["account_compromise"],
        hil_status="not_required",
        use_case_id="uc_brute_force",
    )
    base.update(overrides)
    return AnswerContract(**base)


def test_includes_contract_findings_and_resource_decisions() -> None:
    pkg = build_governed_context_package_for_contract(
        query="why did this alert fire",
        contract=_contract(),
        soc_kb_snippets=["Redacted SOP excerpt: rotate creds on confirmed brute force"],
        resource_decisions=["soc_kb_rag:selected", "splunk_mcp:deferred"],
    )
    block = pkg.to_prompt_block()
    assert "mfa_status" in block
    assert "T1110" in block  # candidate mitre
    assert "T1078" in block  # not-claimed mitre
    assert "account_compromise" in block  # do-not-claim
    assert "soc_kb_rag:selected" in block
    assert "Redacted SOP excerpt" in block
    assert "uc_brute_force" in block


def test_excludes_secrets_and_raw_rows() -> None:
    # Caller passes only redacted strings; the package must never reach into
    # SourceEvidence itself. Assert no field path exists for raw payloads.
    pkg = build_governed_context_package_for_contract(
        query="q",
        contract=_contract(),
    )
    block = pkg.to_prompt_block()
    assert "token" not in block.lower()
    assert "authorization" not in block.lower()
    # soc_kb_snippets empty when none passed — no accidental injection.
    assert "soc_kb_snippets" not in block


def test_truncation_emits_marker_and_drops_low_priority_first() -> None:
    big_snippets = [f"redacted snippet line {i} " * 40 for i in range(6)]
    big_decisions = [f"decision_{i}" * 30 for i in range(10)]
    pkg = build_governed_context_package_for_contract(
        query="q",
        contract=_contract(),
        soc_kb_snippets=big_snippets,
        resource_decisions=big_decisions,
    )
    block = pkg.to_prompt_block(max_chars=400)
    assert CONTEXT_TRUNCATION_MARKER in block
    assert len(block) <= 400 + len(f"\n{CONTEXT_TRUNCATION_MARKER}: true")
    # High-priority contract findings survive; verbose snippets dropped first.
    assert "mfa_status" in block
    assert "redacted snippet line" not in block


def test_v1_thin_package_unaffected() -> None:
    pkg = build_governed_context_package_v1(
        query="list smb top talkers",
        candidate_mappings={"match_path": "exact_105", "question_ref": "q010"},
        routed_skill="spl_generation",
    )
    block = pkg.to_prompt_block()
    assert "q010" in block
    assert "match_path: exact_105" in block
    # No finalize-stage sections leak into the thin package.
    assert "missing_evidence" not in block


def test_cached_block_does_not_collide_thin_vs_enriched() -> None:
    """Regression: the cache key must cover all content fields + max_chars, not just
    query/match_path/skill, or an enriched package returns the stale thin block."""
    common = dict(raw_query="failed login spike", match_path="catalogue_105", routed_skill="attack_discovery")
    thin = GovernedContextPackage(**common)
    enriched = GovernedContextPackage(
        **common, candidate_mitre=["T1110"], missing_evidence=["source ip"], answer_mode="partial_answer"
    )
    thin_block = cached_context_prompt_block(thin)
    enriched_block = cached_context_prompt_block(enriched)
    assert thin_block != enriched_block
    assert "T1110" in enriched_block and "missing_evidence" in enriched_block
    # max_chars participates in the key.
    assert cached_context_prompt_block(enriched, max_chars=40) != enriched_block
    # Stable cache hit: identical inputs return the same object.
    assert cached_context_prompt_block(thin) == thin_block
