"""T4.1 — executed-but-empty results are negative evidence, never insufficient.

Pins the empty-result contract across the evidence chain:
build_source_evidence -> structure_context -> check_context_sufficiency,
plus the safety rules that an empty result must never create a compromise
claim, an evidence_supported MITRE status, or a severity escalation.
"""

from __future__ import annotations

from typing import Any

from app.evidence.context_structurer import structure_context
from app.evidence.context_sufficiency import (
    BLOCKED_BY_POLICY,
    FULL_ANSWER,
    INSUFFICIENT_EVIDENCE,
    PARTIAL_ANSWER,
    check_context_sufficiency,
)
from app.evidence.source_evidence import build_source_evidence
from app.risk.severity_policy import decide_severity
from app.threat.mitre_evidence_preconditions import cap_mitre_status_for_evidence_tier

_TRACE_ID = "trace_t41_negative_result"
_QUERY = "Which accounts had failed logins in the last 24 hours?"
_SPL = "search index=pgcil_soc sourcetype=pgcil:auth earliest=-24h latest=now | stats count by user | head 100"


def _spl_validation() -> dict[str, Any]:
    return {"normalized_spl": _SPL, "approved": True, "warnings": []}


def _execution(status: str, *, result_count: int = 0, **extra: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "status": status,
        "result_count": result_count,
        "results_preview": extra.pop("results_preview", []),
        "selected_mcp_server": "mock_splunk",
        "selected_mcp_tool": "splunk_run_query",
    }
    if status == "executed":
        payload["executed_spl"] = _SPL
    payload.update(extra)
    return payload


def _evidence_for(execution: dict[str, Any]) -> list[dict[str, Any]]:
    return build_source_evidence(
        trace_id=_TRACE_ID,
        query=_QUERY,
        selected_skill="attack_discovery",
        spl_validation=_spl_validation(),
        execution=execution,
    )


def _sufficiency_for(execution: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    evidence = _evidence_for(execution)
    context = structure_context(
        query=_QUERY,
        trace_id=_TRACE_ID,
        selected_skill="attack_discovery",
        workflow_plan={"required_sources": []},
        spl_validation=_spl_validation(),
        execution=execution,
        source_evidence=evidence,
    )
    return context, check_context_sufficiency(context, evidence)


def test_executed_empty_result_is_negative_answer_not_insufficient() -> None:
    _, sufficiency = _sufficiency_for(_execution("executed", result_count=0))
    assert sufficiency["status"] in {FULL_ANSWER, PARTIAL_ANSWER}
    assert sufficiency["status"] != INSUFFICIENT_EVIDENCE
    assert "execution_negative_result" in sufficiency["reasons"]
    # Negative result is an answer; synthesis stays disallowed regardless.
    assert sufficiency["synthesis_readiness"] is True
    assert sufficiency["synthesis_allowed"] is False


def test_query_never_ran_still_insufficient() -> None:
    for status in ("skipped", "failed"):
        _, sufficiency = _sufficiency_for(_execution(status))
        assert sufficiency["status"] == INSUFFICIENT_EVIDENCE, status
        assert "no_collected_evidence" in sufficiency["reasons"], status
        assert "execution_negative_result" not in sufficiency["reasons"], status

    # Blocked execution keeps its existing blocked-by-policy classification.
    _, blocked = _sufficiency_for(
        _execution("blocked", block_reason="mcp_execution_disabled")
    )
    assert blocked["status"] == BLOCKED_BY_POLICY


def test_empty_result_does_not_create_mitre_supported_or_compromise_claim() -> None:
    context, _ = _sufficiency_for(_execution("executed", result_count=0))

    # No MITRE candidates can be derived from an empty result set.
    assert context["mitre_candidates"] == []

    # No fact statement may read as a compromise or confirmation claim.
    statements = " ".join(
        str(fact.get("statement") or "") for fact in context["structured_facts"]
    ).lower()
    for forbidden in ("compromis", "confirmed", "attack detected", "malicious"):
        assert forbidden not in statements, forbidden

    # The tier cap can only ever downgrade an evidence_supported claim; an
    # empty result therefore cannot mint one (no upgrade path exists).
    for tier in ("source_grounded", "stub_or_metadata", "signal_only"):
        assert cap_mitre_status_for_evidence_tier("candidate", tier) == "candidate"
        assert cap_mitre_status_for_evidence_tier("not_claimed", tier) == "not_claimed"

    # An empty result must not escalate severity relative to no evidence at all,
    # both without a policy and under an active use-case severity policy.
    no_evidence_ctx = {"metrics": {}}
    for use_case_id in (None, "auth_failed_login_spike"):
        with_empty = decide_severity(use_case_id, context, [])
        baseline = decide_severity(use_case_id, no_evidence_ctx, [])
        assert with_empty.severity_label == baseline.severity_label, use_case_id


def test_empty_result_records_collection_status_collected_and_result_count_zero() -> None:
    evidence = _evidence_for(_execution("executed", result_count=0))
    mcp_items = [item for item in evidence if item["source_type"] == "splunk_mcp"]
    assert len(mcp_items) == 1
    item = mcp_items[0]
    assert item["collection_status"] == "collected"
    assert item["result_count"] == 0
    assert "execution_completed_zero_rows" in item["warnings"]
    assert item["execution_outcome"] == "negative_result"
    assert item["preview_rows"] == []
