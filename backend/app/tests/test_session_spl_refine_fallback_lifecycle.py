"""Plan 8 X3 — consume Plan 7 A7 fallback disposition without reopening it.

The named pin exists so Plan 8's exact Verify command has a regression artifact.
It restates Plan 7 A7 structural proofs; it does not change rollback behavior.
"""

from __future__ import annotations

from pathlib import Path

from app.tests.test_fallback_lifecycle_equivalence import (
    test_fallback_legacy_branch_runs_the_mandatory_spl_lifecycle,
    test_fallback_still_has_exactly_one_call_site,
    test_mcp_gate_still_refuses_unvalidated_spl,
    test_plan7_classifies_session_fallback_as_rollback_only_not_adopted,
    test_target_resource_planner_graph_cannot_call_legacy_fallback,
)

_PROOF = Path(__file__).resolve().parents[3] / "docs/evals/plan7/a7_fallback_lifecycle_proof.md"


def test_plan7_a7_disposition_is_rollback_only_retain_temporarily() -> None:
    text = _PROOF.read_text(encoding="utf-8")
    assert "LEGACY_FALLBACK_ROLLBACK_ONLY_RETAIN_TEMPORARILY" in text
    for question in (
        "Who owns `spl_source_resolve`?",
        "Does `spl_postprocessor` execute?",
        "Is candidate SPL deterministically validated?",
        "Can candidate SPL reach MCP without approved non-null `normalized_spl`?",
        "Do HIL/RBAC remain authoritative?",
        "Is execution duplicated?",
    ):
        assert question in text


def test_x3_preserves_a7_structural_pins() -> None:
    test_fallback_still_has_exactly_one_call_site()
    test_fallback_legacy_branch_runs_the_mandatory_spl_lifecycle()
    test_mcp_gate_still_refuses_unvalidated_spl()
    test_plan7_classifies_session_fallback_as_rollback_only_not_adopted()
    test_target_resource_planner_graph_cannot_call_legacy_fallback()
