"""Resource Planner decision-record vocabulary and semantic I/O inventory.

The table is deliberately test-owned. ``declared_inputs``/``declared_outputs``
mirror the audit labels emitted by the graph; ``actual_reads``/``actual_writes``
record the state roots established by source tracing and exercised differentially
in Plan 2 A1.2. Decision refs remain descriptive audit metadata, never scheduler
dependencies.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.graph.resource_planner_graph import (
    ResourcePlannerGraphState,
    _record_parallel_specialist_decisions,
)

_GRAPH_PATH = Path(__file__).resolve().parents[1] / "graph" / "resource_planner_graph.py"


@dataclass(frozen=True)
class RecordIo:
    actual_reads: frozenset[str]
    actual_writes: frozenset[str]
    declared_inputs: tuple[str, ...]
    declared_outputs: tuple[str, ...]


def _io(
    reads: tuple[str, ...],
    writes: tuple[str, ...],
    inputs: tuple[str, ...],
    outputs: tuple[str, ...],
) -> RecordIo:
    return RecordIo(frozenset(reads), frozenset(writes), inputs, outputs)


# Complete post-A0 inventory: 20 direct record declarations plus four logical
# specialist records emitted after parallel fan-in.
EXPECTED_RECORD_IO: dict[str, RecordIo] = {
    "work_bundle.apply": _io(
        ("validated_work_bundle",),
        (),
        ("validated_work_bundle",),
        ("evidence_plan",),
    ),
    "specialist.skill": _io(
        ("routed", "canonical_planning_input"),
        ("specialist_reports",),
        ("routed",),
        ("specialist_reports",),
    ),
    "specialist.knowledge": _io(
        ("intent_classification", "evidence_plan"),
        ("specialist_reports",),
        ("evidence_plan",),
        ("specialist_reports",),
    ),
    "specialist.mcp": _io(
        ("evidence_plan",),
        ("specialist_reports",),
        ("evidence_plan",),
        ("specialist_reports",),
    ),
    "specialist.spl": _io(
        ("evidence_plan",),
        ("specialist_reports",),
        ("evidence_plan",),
        ("specialist_reports",),
    ),
    "bootstrap": _io(
        ("request",),
        ("evidence_plan", "query_to_intent", "canonical_planning_input"),
        ("request",),
        ("evidence_plan", "query_to_intent", "canonical_planning_input"),
    ),
    "route_resolution": _io(
        ("routed", "evidence_plan"),
        ("route_contract", "planning_decision"),
        ("routed", "evidence_plan"),
        ("route_contract", "planning_decision"),
    ),
    "resource_planner.delegate": _io(
        ("evidence_plan",),
        ("specialist_delegations",),
        ("evidence_plan",),
        ("specialist_delegations",),
    ),
    "resource_planner.merge": _io(
        ("specialist_reports", "specialist_delegations", "evidence_plan"),
        ("work_bundle", "validated_work_bundle", "planner_iteration", "evidence_plan"),
        ("specialist_reports", "evidence_plan.resource_plan"),
        ("work_bundle", "planner_iteration"),
    ),
    "non_planned_finalize": _io(
        ("canonical_planning_outcome",),
        ("plan_dispatch_trace",),
        ("canonical_planning_outcome",),
        ("plan_dispatch_trace",),
    ),
    "prepare_rag_only": _io(
        ("validated_work_bundle", "evidence_plan"),
        ("evidence_plan", "execution"),
        ("evidence_plan",),
        ("execution",),
    ),
    "rag_early": _io(
        ("evidence_plan",),
        ("soc_kb_retrieval",),
        ("evidence_plan",),
        ("soc_kb_retrieval", "source_evidence"),
    ),
    "composed_dispatch": _io(
        ("validated_work_bundle", "evidence_plan"),
        ("evidence_plan", "candidate_spl", "spl_validation", "execution"),
        ("validated_work_bundle", "evidence_plan.resource_plan"),
        ("candidate_spl", "spl_validation", "execution"),
    ),
    "workflow_spl": _io(
        ("validated_work_bundle", "evidence_plan"),
        ("evidence_plan", "candidate_spl", "spl_validation"),
        ("validated_work_bundle",),
        ("candidate_spl", "spl_validation"),
    ),
    "spl_source_resolve": _io(
        ("candidate_spl", "spl_validation"),
        ("spl_validation",),
        ("candidate_spl",),
        ("spl_validation",),
    ),
    "mcp_execution_gate": _io(
        ("spl_validation",),
        ("execution", "human_review"),
        ("spl_validation", "spl_validation.normalized_spl"),
        ("execution", "human_review"),
    ),
    "spl_validate": _io(
        ("spl_validation",),
        ("spl_validation",),
        ("candidate_spl",),
        ("spl_validation",),
    ),
    "context_sufficiency": _io(
        ("context_sufficiency",),
        ("context_sufficiency",),
        ("source_evidence",),
        ("context_sufficiency",),
    ),
    "decide_facts": _io(
        (),
        (),
        ("mitre_decision", "severity_decision"),
        ("severity_decision", "mitre_mappings"),
    ),
    "answer_guard": _io(
        (),
        (),
        ("answer_contract",),
        ("answer_guard",),
    ),
    "finalize": _io(
        ("structured_context", "source_evidence"),
        ("response", "context_sufficiency", "severity_decision"),
        ("structured_context", "source_evidence"),
        ("response", "context_sufficiency", "severity_decision"),
    ),
    "validate_final_answer": _io(
        (
            "response",
            "answer_contract",
            "evidence_plan",
            "mitre_decision",
            "human_review",
            "planning_decision",
        ),
        ("final_answer_validation", "response"),
        ("response", "answer_contract"),
        ("final_answer_validation",),
    ),
    "human_review": _io(
        ("human_review",),
        ("human_review",),
        ("execution",),
        ("human_review",),
    ),
    "policy_veto": _io(
        ("evidence_plan", "execution", "spl_validation"),
        ("policy_veto", "execution", "spl_validation"),
        ("evidence_plan",),
        ("policy_veto", "execution", "human_review", "spl_validation"),
    ),
}


def _direct_record_declarations() -> dict[str, tuple[tuple[str, ...], tuple[str, ...]]]:
    tree = ast.parse(_GRAPH_PATH.read_text(encoding="utf-8"))
    declarations: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {}
    for call in ast.walk(tree):
        if not isinstance(call, ast.Call):
            continue
        if not isinstance(call.func, ast.Name) or call.func.id != "_record":
            continue
        keywords = {item.arg: item.value for item in call.keywords if item.arg}
        if not {"node", "inputs_ref", "outputs_ref"}.issubset(keywords):
            continue
        node = ast.literal_eval(keywords["node"])
        declarations[node] = (
            tuple(ast.literal_eval(keywords["inputs_ref"])),
            tuple(ast.literal_eval(keywords["outputs_ref"])),
        )
    return declarations


def _specialist_record_declarations() -> dict[str, tuple[tuple[str, ...], tuple[str, ...]]]:
    state: dict[str, Any] = {
        "routed": {"skill": "knowledge_recall"},
        "specialist_reports": [
            {"specialist_id": name, "decision_reason": f"{name}_observed"}
            for name in ("skill", "knowledge", "mcp", "spl")
        ],
    }
    updated = _record_parallel_specialist_decisions(state)
    return {
        item["node"]: (tuple(item["inputs_ref"]), tuple(item["outputs_ref"]))
        for item in updated["decision_log"]
    }


def _declared_record_inventory() -> dict[str, tuple[tuple[str, ...], tuple[str, ...]]]:
    return {**_direct_record_declarations(), **_specialist_record_declarations()}


def _assert_ref_resolves(ref: str, representative_state: dict[str, Any]) -> None:
    parts = ref.split(".")
    annotations = ResourcePlannerGraphState.__annotations__
    assert parts[0] in annotations, f"invalid state-channel root: {ref}"
    if len(parts) == 1:
        return
    value: Any = representative_state
    for part in parts:
        assert isinstance(value, dict) and part in value, f"dangling state path: {ref}"
        value = value[part]


def test_inventory_covers_every_remaining_record_shape() -> None:
    observed = _declared_record_inventory()
    assert len(observed) == 24
    assert set(observed) == set(EXPECTED_RECORD_IO)
    for node, contract in EXPECTED_RECORD_IO.items():
        assert observed[node] == (contract.declared_inputs, contract.declared_outputs)


def test_actual_read_and_write_roots_are_declared_state_channels() -> None:
    annotations = ResourcePlannerGraphState.__annotations__
    invalid = {
        f"{node}:{root}"
        for node, contract in EXPECTED_RECORD_IO.items()
        for root in contract.actual_reads | contract.actual_writes
        if root not in annotations
    }
    assert not invalid


def test_declared_refs_use_state_channel_vocabulary_and_valid_nested_paths() -> None:
    representative_state = {
        "evidence_plan": {"resource_plan": {"plan_id": "rp:test"}},
        "spl_validation": {"normalized_spl": "sanitized-test-value"},
    }
    for node, (inputs_ref, outputs_ref) in _declared_record_inventory().items():
        for ref in (*inputs_ref, *outputs_ref):
            try:
                _assert_ref_resolves(ref, representative_state)
            except AssertionError as exc:
                raise AssertionError(f"{node}: {exc}") from exc


def test_decision_refs_remain_descriptive_not_scheduler_dependencies() -> None:
    runtime_root = _GRAPH_PATH.parents[1]
    consumers: list[str] = []
    for path in runtime_root.rglob("*.py"):
        if "tests" in path.parts:
            continue
        text = path.read_text(encoding="utf-8")
        if "inputs_ref" not in text and "outputs_ref" not in text:
            continue
        for token in (
            '["inputs_ref"]',
            "['inputs_ref']",
            ".inputs_ref",
            '["outputs_ref"]',
            "['outputs_ref']",
            ".outputs_ref",
        ):
            if token in text:
                consumers.append(f"{path.relative_to(runtime_root)}:{token}")
    assert not consumers, f"decision refs gained runtime consumers: {consumers}"
