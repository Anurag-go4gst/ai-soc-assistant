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
from types import SimpleNamespace
from typing import Any

import pytest

from app.graph import resource_planner_graph as rp
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
        (),
    ),
    "specialist.skill": _io(
        ("routed", "canonical_planning_input"),
        ("specialist_reports",),
        ("routed", "canonical_planning_input"),
        ("specialist_reports",),
    ),
    "specialist.knowledge": _io(
        ("intent_classification", "evidence_plan"),
        ("specialist_reports",),
        ("intent_classification", "evidence_plan"),
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
        (
            "routed",
            "route_plan_shadow",
            "selected_use_case",
            "query_to_intent",
            "evidence_plan",
            "route_adjudication",
            "intent_classification",
        ),
        ("route_plan_shadow", "llm_plan_validation", "skill_selection", "selected_skill_chain"),
        ("routed", "route_plan_shadow"),
        ("route_plan_shadow", "llm_plan_validation", "skill_selection", "selected_skill_chain"),
    ),
    "resource_planner.delegate": _io(
        (),
        ("specialist_delegations",),
        (),
        ("specialist_delegations",),
    ),
    "resource_planner.merge": _io(
        ("specialist_reports", "specialist_delegations", "evidence_plan"),
        ("work_bundle", "validated_work_bundle", "planner_iteration", "evidence_plan"),
        ("specialist_reports", "specialist_delegations", "evidence_plan.resource_plan"),
        ("work_bundle", "validated_work_bundle", "planner_iteration", "evidence_plan"),
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
        ("validated_work_bundle", "evidence_plan"),
        ("evidence_plan", "execution"),
    ),
    "rag_early": _io(
        ("request", "workflow_plan", "execution", "planning_decision"),
        ("soc_kb_retrieval",),
        ("workflow_plan",),
        ("soc_kb_retrieval",),
    ),
    "composed_dispatch": _io(
        ("validated_work_bundle", "evidence_plan"),
        ("evidence_plan", "candidate_spl", "spl_validation", "execution"),
        ("validated_work_bundle", "evidence_plan.resource_plan"),
        ("evidence_plan", "candidate_spl", "spl_validation", "execution"),
    ),
    "workflow_spl": _io(
        ("validated_work_bundle", "evidence_plan"),
        ("evidence_plan", "candidate_spl", "spl_validation"),
        ("validated_work_bundle", "evidence_plan"),
        ("evidence_plan", "candidate_spl", "spl_validation"),
    ),
    "spl_source_resolve": _io(
        ("candidate_spl", "spl_validation"),
        ("spl_validation",),
        ("candidate_spl", "spl_validation"),
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
        ("spl_validation",),
        ("spl_validation",),
    ),
    "context_sufficiency": _io(
        ("resolved_query_contract", "evidence_state", "evidence_plan", "source_evidence"),
        (
            "evidence_sufficiency",
            "context_sufficiency",
            "evidence_state",
            "investigation_progress",
            "investigation_run_status",
        ),
        ("resolved_query_contract", "evidence_state", "evidence_plan", "source_evidence"),
        (
            "evidence_sufficiency",
            "context_sufficiency",
            "evidence_state",
            "investigation_progress",
            "investigation_run_status",
        ),
    ),
    "plan_delta_reasoner": _io(
        (
            "approved_investigation_envelope",
            "capability_snapshot",
            "evidence_state",
            "investigation_run_status",
            "plan_delta_revisions",
        ),
        (
            "plan_delta_decision",
            "plan_delta_revisions",
            "plan_delta_execution_request",
            "investigation_run_status",
        ),
        (
            "approved_investigation_envelope",
            "capability_snapshot",
            "evidence_state",
            "investigation_run_status",
            "plan_delta_revisions",
        ),
        (
            "plan_delta_decision",
            "plan_delta_revisions",
            "plan_delta_execution_request",
            "investigation_run_status",
        ),
    ),
    "decide_facts": _io(
        (),
        (),
        (),
        (),
    ),
    "answer_guard": _io(
        (),
        (),
        (),
        (),
    ),
    "finalize": _io(
        (
            "evidence_plan",
            "request",
            "routed",
            "workflow_plan",
            "spl_validation",
            "execution",
            "soc_kb_retrieval",
            "mcp_evidence",
            "reference_resolution",
            "selected_use_case",
            "route_contract",
            "human_review",
            "candidate_spl",
        ),
        ("response", "context_sufficiency", "severity_decision"),
        ("evidence_plan", "execution", "soc_kb_retrieval", "spl_validation"),
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
        (
            "response",
            "answer_contract",
            "evidence_plan",
            "mitre_decision",
            "human_review",
            "planning_decision",
        ),
        ("final_answer_validation", "response"),
    ),
    "human_review": _io(
        ("human_review",),
        ("human_review",),
        ("human_review",),
        ("human_review",),
    ),
    "policy_veto": _io(
        ("evidence_plan", "execution", "spl_validation"),
        ("policy_veto", "execution", "spl_validation"),
        ("evidence_plan", "execution", "spl_validation"),
        ("policy_veto", "execution", "spl_validation"),
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
    assert len(observed) == 25
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


def test_declared_refs_are_semantically_grounded_in_traced_io() -> None:
    mismatches: list[str] = []
    for node, contract in EXPECTED_RECORD_IO.items():
        declared_reads = {ref.split(".", 1)[0] for ref in contract.declared_inputs}
        declared_writes = {ref.split(".", 1)[0] for ref in contract.declared_outputs}
        invalid_reads = sorted(declared_reads - contract.actual_reads)
        invalid_writes = sorted(declared_writes - contract.actual_writes)
        if invalid_reads or invalid_writes:
            mismatches.append(
                f"{node}: invalid_reads={invalid_reads}, invalid_writes={invalid_writes}"
            )
    assert not mismatches, "decision-record semantic overclaims:\n" + "\n".join(mismatches)


def _changed_business_roots(before: dict[str, Any], after: dict[str, Any]) -> set[str]:
    excluded = {"decision_log", "rp_graph_trace"}
    missing = object()
    return {
        key
        for key in set(before) | set(after)
        if key not in excluded and before.get(key, missing) != after.get(key, missing)
    }


def _assert_declared_outputs_observed(
    node: str,
    declared_outputs: tuple[str, ...],
    changed_roots: set[str],
) -> None:
    roots = {ref.split(".", 1)[0] for ref in declared_outputs}
    missing = sorted(roots - changed_roots)
    assert not missing, f"{node} declared outputs not observed: {missing}"


def _assert_wrapper_dataflow(
    node: str,
    wrapper: Any,
    state: dict[str, Any],
) -> dict[str, Any]:
    before = dict(state)
    after = wrapper(state)
    records = [item for item in after.get("decision_log") or [] if item.get("node") == node]
    assert records, f"{node} did not emit its decision record"
    observed_refs = tuple(records[-1]["outputs_ref"])
    assert observed_refs == EXPECTED_RECORD_IO[node].declared_outputs
    _assert_declared_outputs_observed(node, observed_refs, _changed_business_roots(before, after))
    return after


def _pure_writer(*roots: str) -> Any:
    def write(state: dict[str, Any]) -> dict[str, Any]:
        return {**state, **{root: {"sentinel": root} for root in roots}}

    return write


def test_representative_wrapper_dataflow_produces_every_declared_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(rp, "graph_node_init_routing", _pure_writer("query_to_intent"))
    monkeypatch.setattr(
        "app.chat.canonical_planning_orchestrator.run_canonical_planning",
        _pure_writer("evidence_plan", "canonical_planning_input"),
    )
    _assert_wrapper_dataflow("bootstrap", rp.rp_node_bootstrap, {"request": object()})

    monkeypatch.setattr(
        rp,
        "graph_node_shadow_tail",
        _pure_writer(
            "route_plan_shadow",
            "llm_plan_validation",
            "skill_selection",
            "selected_skill_chain",
        ),
    )
    _assert_wrapper_dataflow(
        "route_resolution",
        rp.rp_node_route_resolution,
        {"routed": {}, "route_plan_shadow": {"before": True}},
    )

    registry = SimpleNamespace(
        specialists=[
            SimpleNamespace(specialist_id=name, ownership_scope=(name,))
            for name in ("skill", "knowledge", "mcp", "spl")
        ]
    )
    monkeypatch.setattr(rp, "load_specialist_registry", lambda: registry)
    _assert_wrapper_dataflow(
        "resource_planner.delegate",
        rp.rp_node_resource_planner_delegate,
        {},
    )

    fake_plan = SimpleNamespace(model_dump=lambda: {"plan_id": "rp:after"})
    fake_bundle = SimpleNamespace(
        merge_decision_reason=rp._MERGE_DECISION_VALIDATED,
        model_dump=lambda: {"bundle_id": "bundle:after"},
    )
    fake_iteration = SimpleNamespace(
        bundle=fake_bundle,
        resource_plan=fake_plan,
        model_dump=lambda: {"iteration": 0},
    )
    monkeypatch.setattr(
        rp.ResourcePlan,
        "model_validate",
        classmethod(lambda cls, payload: fake_plan),
    )
    monkeypatch.setattr(rp, "_coerce_specialist_reports", lambda reports: [])
    monkeypatch.setattr(rp, "build_planner_iteration", lambda **kwargs: fake_iteration)
    _assert_wrapper_dataflow(
        "resource_planner.merge",
        rp.rp_node_resource_planner_merge,
        {
            "evidence_plan": {"resource_plan": {"plan_id": "rp:before"}},
            "specialist_reports": [],
            "specialist_delegations": [],
        },
    )

    from app.chat.canonical_outcome_read import OutcomeReadKind

    read = SimpleNamespace(
        kind=OutcomeReadKind.VALID,
        outcome=SimpleNamespace(status="clarification_required"),
    )
    monkeypatch.setattr(
        "app.chat.canonical_outcome_read.read_canonical_planning_outcome",
        lambda state: read,
    )
    monkeypatch.setattr(
        "app.chat.canonical_mode.build_non_planned_dispatch_state",
        lambda state, status: {**state, "plan_dispatch_trace": {"status": status}},
    )
    _assert_wrapper_dataflow(
        "non_planned_finalize",
        rp.rp_node_non_planned_finalize,
        {"canonical_planning_outcome": {"status": "clarification_required"}},
    )

    monkeypatch.setattr(rp, "_apply_work_bundle_to_workers", _pure_writer("evidence_plan"))
    monkeypatch.setattr(rp, "graph_node_prepare_rag_only", _pure_writer("execution"))
    _assert_wrapper_dataflow(
        "prepare_rag_only",
        rp.rp_node_prepare_rag_only,
        {"validated_work_bundle": {}, "evidence_plan": {"before": True}},
    )

    monkeypatch.setattr(rp, "graph_node_rag_early", _pure_writer("soc_kb_retrieval"))
    _assert_wrapper_dataflow(
        "rag_early",
        rp.rp_node_rag_early,
        {"workflow_plan": {"before": True}},
    )

    monkeypatch.setattr(
        rp,
        "graph_node_composed_dispatch",
        _pure_writer("candidate_spl", "spl_validation", "execution"),
    )
    _assert_wrapper_dataflow(
        "composed_dispatch",
        rp.rp_node_composed_dispatch,
        {"validated_work_bundle": {}, "evidence_plan": {"before": True}},
    )

    monkeypatch.setattr(
        rp,
        "graph_node_workflow_spl",
        _pure_writer("candidate_spl", "spl_validation"),
    )
    _assert_wrapper_dataflow(
        "workflow_spl",
        rp.rp_node_workflow_spl,
        {"validated_work_bundle": {}, "evidence_plan": {"before": True}},
    )

    monkeypatch.setattr(rp, "graph_node_spl_source_resolve", _pure_writer("spl_validation"))
    _assert_wrapper_dataflow(
        "spl_source_resolve",
        rp.rp_node_spl_source_resolve,
        {"candidate_spl": {}, "spl_validation": {"before": True}},
    )

    monkeypatch.setattr(rp, "graph_node_execution", _pure_writer("execution", "human_review"))
    _assert_wrapper_dataflow(
        "mcp_execution_gate",
        rp.rp_node_mcp_execution_gate,
        {"spl_validation": {"normalized_spl": "sanitized-test-value"}},
    )

    _assert_wrapper_dataflow(
        "spl_validate",
        rp.rp_node_spl_validate,
        {"spl_validation": {"approved": False}},
    )
    _assert_wrapper_dataflow(
        "context_sufficiency",
        rp.rp_node_context_sufficiency,
        {"approved_investigation_envelope": {}},
    )
    monkeypatch.setattr(
        "app.chat.investigation_plan_delta.attach_plan_delta_decision",
        _pure_writer(
            "plan_delta_decision",
            "plan_delta_revisions",
            "plan_delta_execution_request",
            "investigation_run_status",
        ),
    )
    _assert_wrapper_dataflow(
        "plan_delta_reasoner",
        rp.rp_node_plan_delta_reasoner,
        {
            "approved_investigation_envelope": {},
            "capability_snapshot": {},
            "evidence_state": {},
            "investigation_run_status": {},
            "plan_delta_revisions": [],
        },
    )
    _assert_wrapper_dataflow("decide_facts", rp.rp_node_decide_facts, {})
    _assert_wrapper_dataflow("answer_guard", rp.rp_node_answer_guard, {})

    monkeypatch.setattr(rp, "annotate_step_statuses", lambda state: state)
    monkeypatch.setattr(
        rp,
        "graph_node_context_finalize",
        _pure_writer("response", "context_sufficiency", "severity_decision"),
    )
    _assert_wrapper_dataflow(
        "finalize",
        rp.rp_node_finalize,
        {
            "evidence_plan": {},
            "execution": {},
            "soc_kb_retrieval": {},
            "spl_validation": {},
        },
    )

    @dataclass(frozen=True)
    class FakeResponse:
        message: str
        analyst_response: dict[str, Any]

    monkeypatch.setattr(rp, "PlaceholderResponse", FakeResponse)
    monkeypatch.setattr(
        rp,
        "validate_final_answer",
        lambda **kwargs: SimpleNamespace(model_dump=lambda: {"status": "valid"}),
    )
    monkeypatch.setattr(
        rp,
        "patch_control_plane_trace_decision_log",
        lambda response, state: FakeResponse("after", response.analyst_response),
    )
    _assert_wrapper_dataflow(
        "validate_final_answer",
        rp.rp_node_validate_final_answer,
        {
            "response": FakeResponse("before", {"summary": "safe"}),
            "answer_contract": {},
            "evidence_plan": {},
            "mitre_decision": {},
            "human_review": {},
            "planning_decision": {},
        },
    )

    _assert_wrapper_dataflow("human_review", rp.rp_node_human_review, {})
    _assert_wrapper_dataflow(
        "policy_veto",
        rp.rp_node_policy_veto,
        {
            "evidence_plan": {"mcp_allowed": False, "spl_allowed": False},
            "execution": {"status": "executed"},
            "spl_validation": {"execution_eligible": True},
        },
    )
    _assert_wrapper_dataflow(
        "work_bundle.apply",
        lambda state: rp._reject_validated_work_bundle(
            state,
            reason="representative_rejection",
            detail="sanitized",
        ),
        {"validated_work_bundle": {"tasks": "invalid"}},
    )


def test_specialist_record_outputs_are_observed_on_direct_producers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_report = SimpleNamespace(
        model_dump=lambda: {
            "delegation_id": "del:test",
            "specialist_id": "test",
            "decision_reason": "representative",
        }
    )
    monkeypatch.setattr(rp, "build_knowledge_audit_report", lambda **kwargs: fake_report)
    monkeypatch.setattr(rp, "build_mcp_audit_report", lambda **kwargs: fake_report)
    monkeypatch.setattr(rp, "build_spl_audit_report", lambda **kwargs: fake_report)
    producers = {
        "specialist.skill": (
            rp.rp_node_specialist_skill,
            {"routed": {"skill": "knowledge_recall"}, "canonical_planning_input": {"routing": {}}},
        ),
        "specialist.knowledge": (rp.rp_node_specialist_knowledge, {}),
        "specialist.mcp": (rp.rp_node_specialist_mcp, {}),
        "specialist.spl": (rp.rp_node_specialist_spl, {}),
    }
    for node, (producer, state) in producers.items():
        produced = producer(state)
        assert produced.get("specialist_reports"), node
        _assert_declared_outputs_observed(
            node,
            EXPECTED_RECORD_IO[node].declared_outputs,
            _changed_business_roots(state, produced),
        )


def test_nonexistent_output_negative_control_binds() -> None:
    with pytest.raises(AssertionError, match="nonexistent_output"):
        _assert_declared_outputs_observed(
            "decide_facts",
            ("nonexistent_output",),
            set(),
        )


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
