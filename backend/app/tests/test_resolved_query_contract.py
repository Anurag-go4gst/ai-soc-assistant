"""Plan 5 B1 — ResolvedQueryContract construction and fail-closed validation."""

from __future__ import annotations

import pytest

from app.chat.contracts.resolved_query import (
    ALLOWED_CAPABILITIES,
    ResolvedQueryContract,
)


def test_minimal_valid_contract() -> None:
    contract = ResolvedQueryContract(
        normalized_goal="summarize alert severity",
        intent_family="alert_summary",
        answer_goal="severity_assessment",
        ambiguity_state="unambiguous",
        qualification_tier="T1",
        qualification_source="exact_105_question",
        confidence=0.95,
    )
    assert contract.required_capabilities == frozenset()
    assert contract.prohibited_capabilities == frozenset()
    assert contract.understanding_source == "deterministic_qualification"


def test_capability_sets_accept_known_values() -> None:
    contract = ResolvedQueryContract(
        normalized_goal="hunt lateral movement",
        intent_family="live_investigation",
        answer_goal="live_results",
        ambiguity_state="unambiguous",
        required_capabilities=["spl", "mcp"],
        prohibited_capabilities=[],
        qualification_tier="T4",
        qualification_source="out_of_registry",
        confidence=0.4,
    )
    assert contract.required_capabilities == frozenset({"spl", "mcp"})


@pytest.mark.parametrize("bad_cap", ["execute", "llm", ""])
def test_unknown_capability_fails_closed(bad_cap: str) -> None:
    with pytest.raises(ValueError, match="unknown capability"):
        ResolvedQueryContract(
            normalized_goal="x",
            intent_family="knowledge_only",
            answer_goal="policy_citation",
            ambiguity_state="unambiguous",
            required_capabilities=[bad_cap],
            qualification_tier="T3",
            qualification_source="near_105_question",
        )


def test_required_prohibited_overlap_rejected() -> None:
    with pytest.raises(ValueError, match="both required and prohibited"):
        ResolvedQueryContract(
            normalized_goal="x",
            intent_family="spl_generation_only",
            answer_goal="spl_artifact",
            ambiguity_state="unambiguous",
            required_capabilities=["spl"],
            prohibited_capabilities=["spl"],
            qualification_tier="T2",
            qualification_source="use_case_catalog",
        )


def test_clarification_requires_reason() -> None:
    with pytest.raises(ValueError, match="clarification_reason"):
        ResolvedQueryContract(
            normalized_goal="run this",
            intent_family="clarification_required",
            answer_goal="clarification",
            ambiguity_state="clarification_required",
            clarification_required=True,
            qualification_tier="T4",
            qualification_source="out_of_registry",
        )


def test_module_does_not_import_run_contract() -> None:
    import ast
    from pathlib import Path

    # Repo-anchored, not cwd-relative: another test in the suite chdirs, and a
    # relative path then reads nothing and fails this contract for the wrong reason.
    source = (Path(__file__).resolve().parents[1] / "chat" / "contracts" / "resolved_query.py").read_text()
    tree = ast.parse(source)
    imports = [
        node.names[0].name if isinstance(node, ast.Import) else node.module
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
    ]
    assert "app.chat.contracts.run_contract" not in imports
    assert ALLOWED_CAPABILITIES == frozenset({"spl", "mcp"})


def test_requested_conditional_actions_default_empty() -> None:
    contract = ResolvedQueryContract(
        normalized_goal="summarize alert severity",
        intent_family="alert_summary",
        answer_goal="severity_assessment",
        ambiguity_state="unambiguous",
        qualification_tier="T1",
        qualification_source="exact_105_question",
        confidence=0.95,
    )
    assert contract.requested_conditional_actions == []
    assert contract.requested_outputs == []
    assert contract.contract_version == "2026-08-26"


def test_builder_preserves_design_case_conditional_intents() -> None:
    from app.chat.resolved_query_builder import build_resolved_query_contract

    query = (
        "Investigate the 25 failed SSH logins followed by a successful login to the "
        "admin account from 198.51.100.42. Determine whether the account is "
        "compromised. If the evidence confirms malicious activity, prepare the "
        "remediation actions and draft an email to the firewall and identity teams "
        "summarizing the evidence and requesting the required containment actions."
    )
    contract = build_resolved_query_contract(
        query=query,
        qualification_tier="T4",
        qualification_source="out_of_registry",
    )
    kinds = {a.action_kind for a in contract.requested_conditional_actions}
    assert kinds == {"remediation", "email_draft"}
    email = next(a for a in contract.requested_conditional_actions if a.action_kind == "email_draft")
    assert email.lifecycle_state == "PENDING_CONDITION"
    assert email.predicate_id == "account_compromise_confirmed"
    assert email.recipient_roles == ["firewall_team", "identity_team"]
    assert "remediation_plan" in contract.requested_outputs
    assert "email_draft" in contract.requested_outputs


def test_builder_preserves_all_governed_recipient_roles_without_addresses() -> None:
    from app.chat.resolved_query_builder import build_resolved_query_contract

    contract = build_resolved_query_contract(
        query=(
            "If compromise is confirmed, draft an email to the firewall team, identity team, "
            "incident commander, and system owner. Do not send it to analyst@example.invalid."
        ),
        qualification_tier="T4",
        qualification_source="out_of_registry",
    )

    email = next(a for a in contract.requested_conditional_actions if a.action_kind == "email_draft")
    assert email.recipient_roles == [
        "firewall_team",
        "identity_team",
        "incident_commander",
        "system_owner",
    ]
    assert "@" not in str(email.model_dump())


def test_conditional_action_drops_unknown_roles_and_address_values() -> None:
    from app.chat.contracts.resolved_query import RequestedConditionalAction

    action = RequestedConditionalAction(
        action_kind="email_draft",
        recipient_roles=["firewall_team", "invented_team", "analyst@example.invalid"],
    )

    assert action.recipient_roles == ["firewall_team"]
