from __future__ import annotations

from typing import Any

from app.evidence.context_sufficiency import check_context_sufficiency


def _fact(statement: str = "source returned rows", refs: list[str] | None = None) -> dict[str, Any]:
    return {"fact_id": "f1", "statement": statement, "source_refs": refs if refs is not None else ["ev_1"]}


def _context(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "context_quality": "partial",
        "missing_evidence": [],
        "structured_facts": [_fact()],
        "mitre_candidates": [],
        "mitre_grounding_refs": [],
        "environment_grounding_refs": [],
    }
    base.update(overrides)
    return base


def _evidence(source_type: str, *, status: str = "collected", sensitivity: list[str] | None = None) -> dict[str, Any]:
    return {"source_type": source_type, "collection_status": status, "sensitivity_flags": sensitivity or []}


def test_full_answer_when_execution_grounded_and_complete() -> None:
    result = check_context_sufficiency(_context(), [_evidence("splunk_mcp")])
    assert result["status"] == "full_answer"
    assert result["synthesis_readiness"] is True
    assert result["synthesis_allowed"] is False
    assert result["human_review"] is None


def test_partial_answer_when_missing_evidence() -> None:
    result = check_context_sufficiency(_context(missing_evidence=["mcp:splunk"]), [_evidence("splunk_mcp")])
    assert result["status"] == "partial_answer"
    assert result["synthesis_readiness"] is True
    assert "mcp:splunk" in result["missing_evidence"]


def test_knowledge_only_answer_from_rag_supports_guidance() -> None:
    result = check_context_sufficiency(_context(), [_evidence("rag")])
    assert result["status"] == "knowledge_only_answer"
    assert result["synthesis_readiness"] is True


def test_saia_candidate_spl_alone_is_advisory_only() -> None:
    result = check_context_sufficiency(_context(), [_evidence("splunk_mcp_saia")])
    assert result["status"] == "spl_review_only"
    assert result["synthesis_readiness"] is False


def test_candidate_spl_alone_does_not_enable_execution_answer() -> None:
    # SAIA candidate present but no executed splunk_mcp evidence.
    result = check_context_sufficiency(_context(), [_evidence("splunk_mcp_saia")])
    assert result["status"] == "spl_review_only"
    assert "candidate_spl_advisory_only_no_execution_evidence" in result["reasons"]


def test_structured_facts_without_source_refs_are_insufficient() -> None:
    result = check_context_sufficiency(_context(structured_facts=[_fact(refs=[])]), [_evidence("splunk_mcp")])
    assert result["status"] == "insufficient_evidence"
    assert "structured_fact_missing_source_refs" in result["reasons"]


def test_no_collected_evidence_is_insufficient() -> None:
    result = check_context_sufficiency(_context(), [_evidence("splunk_mcp", status="blocked")])
    assert result["status"] == "insufficient_evidence"
    assert "no_collected_evidence" in result["reasons"]


def test_mitre_conclusion_requires_mitre_grounding() -> None:
    context = _context(mitre_candidates=[{"technique_id": "T1110"}], mitre_grounding_refs=[])
    result = check_context_sufficiency(context, [_evidence("splunk_mcp")])
    assert result["status"] == "analyst_review_required"
    assert "mitre_conclusion_requires_grounding" in result["reasons"]
    assert result["human_review"]["review_type"] == "analyst_review"


def test_mitre_conclusion_passes_with_grounding() -> None:
    context = _context(mitre_candidates=[{"technique_id": "T1110"}], mitre_grounding_refs=["kb:mitre:T1110"])
    result = check_context_sufficiency(context, [_evidence("splunk_mcp")])
    assert result["status"] == "full_answer"


def test_asset_criticality_claim_requires_asset_evidence() -> None:
    context = _context(
        structured_facts=[_fact(statement="host db01 is a critical asset")],
        environment_grounding_refs=[],
    )
    result = check_context_sufficiency(context, [_evidence("splunk_mcp")])
    assert result["status"] == "analyst_review_required"
    assert "asset_criticality_requires_asset_evidence" in result["reasons"]


def test_asset_criticality_claim_passes_with_environment_evidence() -> None:
    context = _context(
        structured_facts=[_fact(statement="host db01 is a critical asset")],
        environment_grounding_refs=["kb:asset:db01"],
    )
    result = check_context_sufficiency(context, [_evidence("splunk_mcp")])
    assert result["status"] == "full_answer"


def test_ambiguous_rag_requires_analyst_review() -> None:
    result = check_context_sufficiency(_context(), [_evidence("rag", status="ambiguous")])
    assert result["status"] == "analyst_review_required"
    assert "knowledge_ambiguity_requires_review" in result["reasons"]


def test_sensitive_leak_blocks_synthesis_readiness() -> None:
    evidence = [_evidence("splunk_mcp", sensitivity=["sensitive_value_redacted"])]
    result = check_context_sufficiency(_context(), evidence)
    assert result["status"] == "blocked_by_policy"
    assert result["synthesis_readiness"] is False
    assert "sensitive_leak_detected" in result["reasons"]
    assert result["human_review"]["required"] is True


def test_policy_blocked_context_is_blocked_by_policy() -> None:
    result = check_context_sufficiency(_context(context_quality="blocked"), [_evidence("splunk_mcp", status="blocked")])
    assert result["status"] == "blocked_by_policy"
    assert "context_collection_blocked" in result["reasons"]
