"""REV4 batch 1 P7 — guided SPL review gate."""

from __future__ import annotations

import pytest

from app.chat.contracts.evidence_plan import EvidencePlan
from app.chat.contracts.investigation_plan import InvestigationPlan
from app.chat.guided_spl_review_gate import build_guided_spl_draft_preview_if_allowed


def _evidence(**overrides: object) -> EvidencePlan:
    base = EvidencePlan(
        answer_mode="guided_investigation",
        rag_phase="rag_only",
        needs_rag=True,
        needs_spl=False,
        needs_mcp=False,
        needs_mitre=False,
        spl_allowed=False,
        mcp_allowed=False,
        policy_context_required=False,
        policy_context_recommended=True,
        spl_review_allowed=True,
    )
    return base.model_copy(update=overrides)


def _plan(**overrides: object) -> InvestigationPlan:
    base = InvestigationPlan(
        investigation_objective="Review-only hunt",
        hypotheses=["Vendor maintenance"],
        evidence_needed=["Firewall sessions"],
    )
    return base.model_copy(update=overrides)


def test_spl_review_gate_requires_both_capability_and_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.chat.guided_spl_review_gate.build_draft_preview",
        lambda *args, **kwargs: {"draft_spl": "| search index=test", "family_id": "test"},
    )
    query = "How should I investigate unusual outbound traffic from an OT host overnight?"
    assert (
        build_guided_spl_draft_preview_if_allowed(
            query=query,
            evidence_plan=_evidence(spl_review_allowed=False),
            investigation_plan=_plan(spl_review_requested=True),
        )
        is None
    )
    assert (
        build_guided_spl_draft_preview_if_allowed(
            query=query,
            evidence_plan=_evidence(spl_review_allowed=True),
            investigation_plan=_plan(spl_review_requested=False),
        )
        is None
    )
    preview = build_guided_spl_draft_preview_if_allowed(
        query=query,
        evidence_plan=_evidence(spl_review_allowed=True),
        investigation_plan=_plan(spl_review_requested=True),
    )
    assert isinstance(preview, dict)
    assert preview.get("draft_spl") or preview.get("family_id")
