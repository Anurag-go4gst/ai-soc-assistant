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
