"""Plan 8 U0 — T1–T3 emit locked vs unresolved understanding fields."""

from __future__ import annotations

from app.chat.resolved_query_builder import build_resolved_query_contract
from app.query_understanding.parser import understand_query


def _build(query: str, *, tier: str, source: str):
    qu = understand_query(query)
    return build_resolved_query_contract(
        query=query,
        query_understanding=qu,
        qualification_tier=tier,  # type: ignore[arg-type]
        qualification_source=source,
    )


def test_t1_locks_deterministic_fields_and_does_not_call_t4() -> None:
    contract = _build(
        "What incident or alert network events are high or critical right now?",
        tier="T1",
        source="exact_105_question",
    )
    assert "intent_family" in contract.locked_fields
    assert "answer_goal" in contract.locked_fields
    assert "normalized_goal" in contract.locked_fields
    assert contract.unresolved_fields == []
    assert "required_capabilities" in contract.derived_field_names
    assert "evidence_requirements" in contract.derived_field_names
    sufficiency = contract.understanding_sufficiency or {}
    assert sufficiency["stage"] == "UNDERSTANDING"
    assert sufficiency["next_action"] == "CONTINUE"
    assert sufficiency["status"] == "SUFFICIENT"


def test_t4_names_only_unresolved_semantic_fields() -> None:
    contract = _build(
        "Hunt for CI/CD supply-chain compromise indicators across our environment",
        tier="T4",
        source="out_of_registry",
    )
    assert contract.locked_fields["intent_family"] == contract.intent_family
    assert "normalized_goal" not in contract.locked_fields
    assert "semantic_goal" in contract.unresolved_fields
    assert "required_capabilities" not in contract.unresolved_fields
    assert "required_capabilities" in contract.derived_field_names
    sufficiency = contract.understanding_sufficiency or {}
    assert sufficiency["next_action"] == "CALL_T4"
    assert sufficiency["status"] == "PARTIAL"
    assert "semantic_goal" in sufficiency["unresolved"]


def test_explicit_source_ip_and_time_are_locked() -> None:
    contract = _build(
        "Show failed VPN administrator logins from 203.0.113.24 yesterday.",
        tier="T2",
        source="use_case_catalog",
    )
    locked = contract.locked_fields
    assert any(key.startswith("entities.source_ip") or "203.0.113.24" in str(value) for key, value in locked.items())
    assert "time_scope" in locked or contract.time_scope
    assert contract.unresolved_fields == []
    assert (contract.understanding_sufficiency or {}).get("next_action") == "CONTINUE"


def test_clarification_does_not_request_t4() -> None:
    contract = _build(
        "compare this with what happened last week and tell me if it is getting worse",
        tier="T4",
        source="out_of_registry",
    )
    # Unresolved semantic referent is T4's job, not a T1–T3 CLARIFY skip.
    assert (contract.understanding_sufficiency or {}).get("next_action") == "CALL_T4"
    assert contract.clarification_required is False
    assert "semantic_referent" in (contract.unresolved_fields or [])
    assert "required_capabilities" not in contract.unresolved_fields
