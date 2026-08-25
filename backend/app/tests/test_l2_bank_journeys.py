"""L2 bank — P3 journey rows that are green today.

Scope discipline (workstream C, P3): this file adds *coverage*, never behaviour.
Every assertion below was probed against the runtime at `ae03a250` before it was
written, so a red test here means the product changed, not that the row was
aspirational.

Each test maps 1:1 to a row in ``app.tests.support.l2_bank_manifest`` and owns
exactly one invariant. ``test_l2_bank_manifest.py`` enforces that mapping in both
directions, so a test added here without a manifest row — or a row whose bound
test disappears — turns red.

Deliberately absent: assertions on ``control_plane_trace`` internals, diagnostic
ordering, timings, or any field whose contract P1/P2/P4 still own.
"""

from __future__ import annotations

from typing import Any

import pytest

from app.chat.contracts.investigation_envelope import ApprovedInvestigationEnvelope
from app.chat.contracts.investigation_outcome import derive_investigation_outcome
from app.chat.contracts.plan_delta import PlanDeltaProposal
from app.chat.investigation_plan_delta import validate_plan_delta
from app.chat.remediation_runtime import handle_remediation_review, maybe_attach_remediation_offer
from app.config import settings
from app.knowledge import soc_kb_retriever

_SEARCH_CAPABILITY = "mcp:splunk:splunk_run_query"
_DELTA_SPL = (
    "search index=pgcil_soc sourcetype=pgcil:auth earliest=-24h latest=now user=alice "
    "| stats count by user | head 100"
)

_SOP_QUERY = "What is the SOP for investigating a failed login spike?"
_OUT_OF_DOMAIN_QUERY = "How do I calibrate the office espresso machine for oat milk?"


# ---------------------------------------------------------------------------
# RAG — L2.P3.01 / L2.P3.02 / L2.P3.03
# ---------------------------------------------------------------------------


@pytest.fixture
def _rag_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    """Smallest enabling set: the retriever's own flag, nothing else."""
    monkeypatch.setattr(soc_kb_retriever.settings, "soc_kb_retrieval_enabled", True)


def _retrieve(query: str) -> dict[str, Any]:
    return soc_kb_retriever.retrieve_soc_kb(
        query=query,
        selected_skill="knowledge_recall",
        workflow_stage="analysis",
    )


def test_l2_rag_sop_match_returns_governed_entries(_rag_enabled: None) -> None:
    """L2.P3.01 — a real SOP question retrieves governed entries with declared origin."""
    result = _retrieve(_SOP_QUERY)

    assert result["retrieval_status"] == "retrieved"
    assert len(result["retrieved_entries"]) >= 1
    assert result["confidence"] > 0.0
    # Every retrieved package declares where it came from; unattributed evidence is
    # the failure mode this row exists to catch.
    assert result["evidence_origin"] not in (None, "", "none")


def test_l2_rag_no_match_returns_nothing_and_says_so(_rag_enabled: None) -> None:
    """L2.P3.02 — out-of-domain retrieves nothing and invents no near-miss citation."""
    result = _retrieve(_OUT_OF_DOMAIN_QUERY)

    assert result["retrieval_status"] == "no_match"
    assert result["retrieved_entries"] == []
    assert result["confidence"] == 0.0
    assert result["evidence_origin"] == "none"


def test_l2_rag_disabled_by_default_is_declared_not_silent() -> None:
    """L2.P3.03 — the shipped default is 'disabled', which is not the same as 'no_match'.

    No monkeypatch: this asserts the posture a default-configured deployment has.
    """
    assert settings.soc_kb_retrieval_enabled is False

    result = _retrieve(_SOP_QUERY)

    assert result["retrieval_status"] == "disabled"
    assert "soc_kb_retrieval_disabled" in result["reasons"]
    assert result["retrieved_entries"] == []


# ---------------------------------------------------------------------------
# InvestigationOutcome — L2.P3.04 / L2.P3.05 / L2.P3.06
# ---------------------------------------------------------------------------


def test_l2_empty_evidence_outcome_invents_no_findings() -> None:
    """L2.P3.04 — zero evidence yields an incomplete outcome with nothing invented."""
    outcome = derive_investigation_outcome(outcome_v2_enabled=True)

    assert outcome.investigation_status == "incomplete"
    assert outcome.disposition == "inconclusive"
    assert outcome.findings == []
    assert outcome.evidence_refs == []


def test_l2_policy_block_is_status_not_security_disposition() -> None:
    """L2.P3.05 — 'blocked' is an investigation status; it is never a security verdict.

    architecture.md states this separation explicitly. The concrete hazard is an
    analyst reading a policy block as a finding about the environment.
    """
    outcome = derive_investigation_outcome(
        context_sufficiency={"status": "blocked_by_policy"},
        outcome_v2_enabled=True,
    )

    assert outcome.investigation_status == "blocked"
    assert outcome.disposition != "blocked"
    assert outcome.disposition in {"benign", "suspicious", "inconclusive"}


def test_l2_negative_evidence_yields_benign_disposition() -> None:
    """L2.P3.06 — 'we looked and it is not there' is not 'we could not tell'."""
    outcome = derive_investigation_outcome(
        canonical_facts={
            "facts": [
                {"kind": "negative_evidence", "statement": "no matching auth events in scope"}
            ]
        },
        evidence_state={"obtained": []},
        outcome_v2_enabled=True,
    )

    assert outcome.disposition == "benign"


# ---------------------------------------------------------------------------
# Plan delta bounds — L2.P3.07 / L2.P3.08
# ---------------------------------------------------------------------------


def _envelope() -> ApprovedInvestigationEnvelope:
    return ApprovedInvestigationEnvelope(
        envelope_version=2,
        objective="Investigate alice authentication activity",
        targets=["user:alice"],
        entities={"user": "alice"},
        time_scope="last 24 hours",
        approved_evidence_categories=["sessions"],
        allowed_read_only_capabilities=[_SEARCH_CAPABILITY],
        source_index_scope={"indexes": ["pgcil_soc"]},
    )


def _available_snapshot() -> dict[str, Any]:
    return {
        "rows": [
            {
                "capability_id": _SEARCH_CAPABILITY,
                "capability_need": "required",
                "availability": "available",
            }
        ]
    }


def _proposal(envelope: ApprovedInvestigationEnvelope, **overrides: Any) -> PlanDeltaProposal:
    payload: dict[str, Any] = {
        "envelope_version": 2,
        "objective": envelope.objective,
        "evidence_need": "authentication_correlation",
        "capability_id": _SEARCH_CAPABILITY,
        "access_mode": "read_only",
        "targets": envelope.targets,
        "entities": envelope.entities,
        "time_scope": envelope.time_scope,
        "source_index_scope": envelope.source_index_scope,
        "tool_arguments": {"query": _DELTA_SPL},
    }
    payload.update(overrides)
    return PlanDeltaProposal.model_validate(payload)


def test_l2_duplicate_plan_delta_is_refused_as_no_progress() -> None:
    """L2.P3.07 — repeating the same effective delta buys no round and no budget."""
    envelope = _envelope()
    snapshot = _available_snapshot()

    first = validate_plan_delta(
        _proposal(envelope),
        envelope=envelope,
        capability_snapshot=snapshot,
        missing_evidence=["authentication_correlation"],
        prior_revisions=[],
    )
    assert first.status == "accepted"
    assert first.validated_delta is not None

    duplicate = validate_plan_delta(
        _proposal(
            envelope,
            prior_revision_fingerprint=first.validated_delta.revision_fingerprint,
        ),
        envelope=envelope,
        capability_snapshot=snapshot,
        missing_evidence=["authentication_correlation"],
        prior_revisions=[first.validated_delta.model_dump(mode="json")],
    )

    assert duplicate.status == "no_progress"
    assert duplicate.reason == "duplicate_effective_plan_delta"
    assert duplicate.validated_delta is None


def test_l2_write_access_mode_is_not_an_investigation_delta() -> None:
    """L2.P3.08 — a write proposed as investigation work is routed out, not validated.

    Investigation is read-only. The correct behaviour is not a bare rejection but a
    referral to the remediation lane, which is what makes this distinct from the
    unavailable-capability rejection in L2.P0.07.
    """
    envelope = _envelope()

    decision = validate_plan_delta(
        _proposal(envelope, access_mode="write"),
        envelope=envelope,
        capability_snapshot=_available_snapshot(),
        missing_evidence=["authentication_correlation"],
        prior_revisions=[],
    )

    assert decision.status == "remediation_recommended"
    assert decision.reason == "writes_are_not_investigation_plan_delta"
    assert decision.validated_delta is None


# ---------------------------------------------------------------------------
# Remediation lifecycle — L2.P3.09 / L2.P3.10
# ---------------------------------------------------------------------------


@pytest.fixture
def _remediation_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_remediation_planner_enabled", True)


def _completed_outcome_state() -> dict[str, Any]:
    return {
        "investigation_outcome": {
            "investigation_status": "completed",
            "disposition": "suspicious",
            "remediation_offer_required": True,
            "findings": ["repeated failed logins from 10.0.0.8"],
            "severity_label": "P2",
            "recommended_actions": ["block source ip"],
        }
    }


def test_l2_remediation_offer_then_decline_builds_no_plan(_remediation_enabled: None) -> None:
    """L2.P3.09 — the offer is an affordance; declining it leaves no plan behind."""
    offered = maybe_attach_remediation_offer(_completed_outcome_state())
    approval = offered["remediation_approval"]

    assert approval["status"] == "offered"
    assert approval["allowed_actions"] == ["create", "decline"]
    # Nothing is planned merely by being offered.
    assert approval["validated_plan"] is None

    declined = handle_remediation_review(offered, action="decline")
    declined_approval = declined["remediation_approval"]

    assert declined_approval["status"] == "declined"
    assert declined_approval["validated_plan"] is None
    assert "approved_remediation_envelope" not in declined


def test_l2_remediation_approval_yields_envelope_without_execution(
    _remediation_enabled: None,
) -> None:
    """L2.P3.10 — approval produces the envelope that P11 execution would *consume*.

    The envelope is the input to execution, never the authorization for it. This row
    is the load-bearing one for 'no unapproved write'.
    """
    offered = maybe_attach_remediation_offer(_completed_outcome_state())

    created = handle_remediation_review(offered, action="create")
    created_approval = created["remediation_approval"]
    plan = created_approval["validated_plan"] or {}

    assert created_approval["status"] == "awaiting_approval"
    assert created_approval["allowed_actions"] == ["approve", "edit", "cancel"]
    assert plan["execution_authorized"] is False
    assert plan["human_approval_required"] is True

    approved = handle_remediation_review(created, action="approve")
    approved_approval = approved["remediation_approval"]

    assert approved_approval["status"] == "approved"
    assert approved["approved_remediation_envelope"]["envelope_version"] == 1
    # Approval must not have executed, scheduled, or recorded any write.
    assert approved_approval["execution_result"] is None
    assert "remediation_execution" not in approved
