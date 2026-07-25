from __future__ import annotations

from app.chat.pipeline import _mitre_outputs_for_finalize
from app.threat.mitre_decision import resolve_mitre_decision
from app.threat.mitre_registry_schema import MitreRegistryMetadata


def _metadata() -> MitreRegistryMetadata:
    return MitreRegistryMetadata(
        mitre_permitted=["T1110.001"],
        mitre_candidate=["T1078"],
        mitre_blocked=["T1003", "T1562.001"],
        mitre_requires_evidence=True,
        mitre_requires_alert_context=False,
        mapping_rationale="test metadata",
    )


def test_policy_intent_suppresses_registry_mitre_visibility() -> None:
    decision = resolve_mitre_decision(
        registry_metadata=_metadata(),
        intent_classification={
            "intent_family": "policy_knowledge",
            "answer_goal": ["policy_context"],
            "requires_clarification": False,
        },
        evidence_plan={"answer_mode": "rag_only"},
    )
    assert decision.mitre_status == "not_answer_visible"
    assert decision.answer_visible is False
    assert decision.techniques == []
    assert decision.registry_candidates == ["T1110.001", "T1078"]


def test_live_investigation_allows_candidate_visible_mitre_only() -> None:
    decision = resolve_mitre_decision(
        registry_metadata=_metadata(),
        intent_classification={
            "intent_family": "live_investigation",
            "answer_goal": ["live_results"],
            "requires_clarification": False,
        },
        evidence_plan={"answer_mode": "live_investigation", "needs_mcp": True},
        source_refs=["evidence-1"],
    )
    assert decision.mitre_status == "candidate"
    assert decision.answer_visible is True
    technique_ids = {item["technique_id"] for item in decision.techniques}
    assert "T1110.001" in technique_ids
    assert "T1003" not in technique_ids
    assert "T1562.001" not in technique_ids
    assert set(decision.rejected_techniques) == {"T1003", "T1562.001"}


def test_explicit_mitre_mapping_without_context_requires_clarification() -> None:
    decision = resolve_mitre_decision(
        registry_metadata=_metadata().model_copy(update={"mitre_requires_alert_context": True}),
        intent_classification={
            "intent_family": "mitre_mapping",
            "answer_goal": ["mitre_mapping"],
            "requires_clarification": True,
        },
        evidence_plan={"answer_mode": "clarification"},
    )
    assert decision.mitre_status == "requires_alert_context"
    assert decision.answer_visible is False
    # MITRE is deferred pending alert context: no technique is claimed or
    # not-claimed yet. Registry-blocked techniques still surface via rejected,
    # not via a blanket _DEFAULT_NOT_CLAIMED list (removed in Commit 1).
    assert decision.not_claimed == []
    assert {"T1003", "T1562.001"}.issubset(set(decision.rejected_techniques))


def test_canonical_finalize_hides_policy_mitre(monkeypatch) -> None:
    mappings, decision = _mitre_outputs_for_finalize(
        question_ref="q0.q046",
        use_case_id="auth_failed_login_spike",
        source_refs=["legacy-source"],
        intent_classification={"intent_family": "policy_knowledge", "answer_goal": []},
        evidence_plan={"answer_mode": "rag_only"},
    )
    assert mappings == []
    assert decision is not None
    assert decision["answer_visible"] is False


def test_flag_on_finalize_hides_policy_mitre(monkeypatch) -> None:
    mappings, decision = _mitre_outputs_for_finalize(
        question_ref="q0.q046",
        use_case_id="auth_failed_login_spike",
        source_refs=["policy-source"],
        intent_classification={
            "intent_family": "policy_knowledge",
            "answer_goal": ["policy_context"],
            "requires_clarification": False,
        },
        evidence_plan={"answer_mode": "rag_only"},
    )
    assert mappings == []
    assert decision is not None
    assert decision["answer_visible"] is False
    assert decision["registry_candidates"]
