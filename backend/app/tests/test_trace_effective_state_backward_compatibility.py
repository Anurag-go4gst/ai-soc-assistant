"""Legacy debug-bundle consumers must be unaffected by the effective-state work.

The reconciliation is additive: existing fields keep their names, positions and
meanings, and `effective_state` is a new sibling block. These pins fail if a
legacy field is renamed, removed, or silently redefined.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from app.chat.debug_summary import build_debug_summary
from app.chat.final_output_trace import build_final_output_trace

_FIXTURE = Path(__file__).parent / "fixtures" / "trace_consistency" / "p2_review_only_spl_payload.json"

#: Blocks the bundle exposed before the effective-state projection existed.
_LEGACY_DEBUG_SUMMARY_BLOCKS = (
    "routing",
    "llm",
    "spl",
    "mcp",
    "hil",
    "output",
    "intent",
    "dispatch",
    "resolved_query",
    "schedule",
    "evidence_state",
    "investigation_outcome",
    "auth0",
    "t4_circuit",
)


def _payload() -> dict[str, Any]:
    return json.loads(_FIXTURE.read_text())


@pytest.fixture()
def summary() -> dict[str, Any]:
    return build_debug_summary(payload=_payload())


def test_every_legacy_debug_summary_block_is_still_present(summary: dict[str, Any]) -> None:
    for block in _LEGACY_DEBUG_SUMMARY_BLOCKS:
        assert block in summary, block
        assert isinstance(summary[block], dict), block


def test_effective_state_is_additive(summary: dict[str, Any]) -> None:
    assert "effective_state" in summary
    assert summary["effective_state"]["schema_version"] == "trace_effective_state_v1"
    assert set(_LEGACY_DEBUG_SUMMARY_BLOCKS) <= set(summary)


def test_legacy_hil_block_keeps_its_original_meaning(summary: dict[str, Any]) -> None:
    """`debug_summary.hil` still reports the raised review, unmodified.

    The reconciled current-turn/execution split lives on `effective_state.hil`;
    consumers reading the old block see exactly what they saw before.
    """
    assert summary["hil"]["required"] is True
    assert summary["hil"]["reason"] == "source_profile_slots_missing"
    assert summary["hil"]["kind"] == "spl_source_profile_clarification"
    # And the reconciled view disagrees on purpose, with the history retained.
    effective = summary["effective_state"]["hil"]
    assert effective["current_turn_hil_required"] is False
    assert effective["legacy_hil_required"] is True
    assert effective["legacy_hil_reason"] == "source_profile_slots_missing"


def test_legacy_final_output_block_is_unchanged() -> None:
    output = build_final_output_trace(_payload())
    assert output["hil_required"] is True
    assert output["hil_reason"] == "source_profile_slots_missing"
    assert output["answer_mode"] == "spl_utility_authoring"
    assert output["execution_status"] == "skipped"
    assert set(output) == {
        "message",
        "analyst_summary",
        "selected_skill",
        "answer_mode",
        "severity_label",
        "mitre_status",
        "hil_required",
        "hil_reason",
        "guard_status",
        "final_answer_safety_status",
        "execution_status",
    }


def test_legacy_spl_and_mcp_blocks_are_unchanged(summary: dict[str, Any]) -> None:
    assert summary["spl"]["approved"] is False
    assert summary["spl"]["normalized_spl"] is False
    assert summary["spl"]["reject_reasons"] == ["review_only_spl_authoring"]
    assert summary["spl"]["final_spl_authority"] == "deterministic_postprocessor"
    assert summary["mcp"]["status"] == "skipped"
    assert summary["mcp"]["result_count"] == 0
    assert summary["mcp"]["allowed"] is False


def test_legacy_evidence_state_buckets_are_unchanged(summary: dict[str, Any]) -> None:
    """Only `applicability` was added to items; the buckets are untouched."""
    state = summary["evidence_state"]
    assert state["schema_version"] == "minimal_evidence_state_v2"
    assert "spl" in state["missing"]
    assert "mcp:splunk" in state["missing"]
    assert "negative_evidence" in state["obtained"]
    # The false positive is gone and its truthful replacement is present.
    assert "executed_evidence" not in state["obtained"]
    assert "source_evidence" in state["obtained"]


def test_evidence_state_items_keep_their_legacy_keys(summary: dict[str, Any]) -> None:
    for item in summary["evidence_state"]["items"]:
        assert set(item) == {"key", "status", "trust_class", "provenance", "applicability"}


def test_legacy_llm_used_definition_is_preserved(summary: dict[str, Any]) -> None:
    """`llm_used` still means "an LLM materially authored the output"."""
    from app.quality.store import _llm_used

    payload = _payload()
    assert _llm_used(payload) is False
    assert summary["effective_state"]["llm"]["legacy_llm_used"] is _llm_used(payload)
    # The role-scoped fields carry what the single boolean could not.
    llm = summary["effective_state"]["llm"]
    assert llm["llm_called_any"] is True
    assert llm["roles_attempted"] == ["spl_advisory_generator"]
    assert llm["llm_contributed_to_final_output"] is False
    # `calls_attempted` and the legacy `live_calls` mean different things and are
    # named differently on purpose.
    assert llm["calls_attempted"] == 1
    assert llm["calls_completed"] == 0
    assert summary["llm"]["live_calls"] == 0


def test_rag_trace_additions_are_additive() -> None:
    from app.chat.control_plane_trace import _rag_trace

    trace = _rag_trace({"retrieval_status": "retrieved", "retrieval_workflow_stage": "context"})
    for legacy_key in (
        "match_status",
        "retrieval_status",
        "rag_skipped_for_spl_utility_authoring",
        "reasons",
        "retrieval_backend",
        "collection_ids",
        "evidence_refs",
        "missing_sources",
    ):
        assert legacy_key in trace, legacy_key
    assert trace["retrieval_workflow_stage"] == "context"


def test_projection_failure_degrades_without_breaking_the_summary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A diagnostic projection must never take chat down with it."""
    import app.chat.trace_effective_state as module

    def _boom(_payload: dict[str, Any]) -> dict[str, Any]:
        raise RuntimeError("projection defect")

    monkeypatch.setattr(module, "_build", _boom)
    state = module.build_effective_state_projection(_payload())
    assert state["projection_status"] == "failed"
    assert state["schema_version"] == "trace_effective_state_v1"
