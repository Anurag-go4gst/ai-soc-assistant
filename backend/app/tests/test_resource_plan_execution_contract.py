"""Plan 2 C1-E1 — ResourcePlan execution dependency contract (validation only).

C0 decided `EXECUTION-DRIVEN` with `v1_v2_posture: EXTEND_LIVE_RESOURCE_PLAN`.
This module pins the contract itself: unique step ids, acyclic `depends_on`,
allowed parallel groups, declared produced/required evidence keys, fallback
targets, bounded attempts, blocked/skipped semantics, and the deterministic
downgrade to the current fixed schedule.

Nothing here wires execution. No scheduler, no dispatch, no connector, no LLM.
"""

from __future__ import annotations

import pytest

from app.planner.resource_plan import PlanStep, ResourcePlan
from app.planner.resource_plan_execution import (
    EXECUTION_FALLBACK_TARGETS,
    MAX_STEP_ATTEMPTS,
    SIDE_EFFECTING_PURPOSES,
    SUPPORTED_EXECUTION_PURPOSES,
    StepExecutionSpec,
    build_execution_contract,
    derive_execution_spec,
    execution_contract_or_downgrade,
    validate_execution_contract,
)


def _step(step_id: str, purpose: str, **kwargs) -> PlanStep:
    resource = {
        "knowledge_retrieval": "rag_corpus:soc_kb",
        "spl_artifact": "spl_template:auth_failed_login_spike",
        "mcp_execution": "mcp_tool:splunk_run_query",
        "narration": "skill:narration",
        "cve_lookup": "skill:cve_lookup",
        "mitre_mapping": "skill:mitre_mapping",
    }.get(purpose, f"skill:{purpose}")
    return PlanStep(step_id=step_id, resource_id=resource, purpose=purpose, **kwargs)


def _plan(*steps: PlanStep) -> ResourcePlan:
    return ResourcePlan(steps=list(steps))


def _codes(plan: ResourcePlan) -> list[str]:
    return [error.code for error in validate_execution_contract(plan).errors]


# --- vocabulary ---------------------------------------------------------------


def test_supported_purposes_cover_every_composer_emitted_purpose() -> None:
    """A real composed plan must never downgrade for an unknown purpose."""
    composer_purposes = {
        "knowledge_retrieval",
        "spl_artifact",
        "mcp_execution",
        "mcp_discovery",
        "safe_catalog_query",
        "cve_lookup",
        "mitre_mapping",
        "evidence_collection",
        "context_sufficiency",
        "narration",
    }
    assert composer_purposes <= set(SUPPORTED_EXECUTION_PURPOSES)


def test_only_mcp_execution_is_side_effecting() -> None:
    assert SIDE_EFFECTING_PURPOSES == frozenset({"mcp_execution"})


def test_declared_evidence_keys_are_real_state_channels() -> None:
    """Evidence keys reuse the A1.1 rule: root must be a declared state channel."""
    from app.graph.resource_planner_graph import ResourcePlannerGraphState

    channels = set(ResourcePlannerGraphState.__annotations__)
    for purpose in SUPPORTED_EXECUTION_PURPOSES:
        spec = derive_execution_spec(_step(purpose, purpose))
        for key in [*spec.requires_evidence_keys, *spec.produces_evidence_keys]:
            assert key.split(".")[0] in channels, f"{purpose}:{key}"


# --- default derivation (parity anchor for C1-E2/C1-E4) -----------------------


def test_default_derivation_reproduces_the_current_fixed_schedule_semantics() -> None:
    """No declarations anywhere → SPL before MCP, RAG independent, narration last."""
    plan = _plan(
        _step("rag", "knowledge_retrieval"),
        _step("spl", "spl_artifact"),
        _step("mcp", "mcp_execution"),
        _step("narration", "narration"),
    )
    contract = build_execution_contract(plan)
    assert contract is not None
    by_id = {step.step_id: step for step in contract.steps}
    assert by_id["mcp"].depends_on == ["spl"]
    assert by_id["rag"].depends_on == []
    assert by_id["spl"].depends_on == []
    assert by_id["narration"].depends_on == []
    assert by_id["mcp"].side_effecting is True
    assert by_id["mcp"].max_attempts == 1
    assert "spl_validation" in by_id["mcp"].requires_evidence_keys
    # The only real handoff is SPL → MCP, so MCP is the only second-wave step.
    # `narration` stays dependency-free: it is not dispatched by the executor
    # (`_DISPATCHABLE_PURPOSES`), and inventing an edge for it would fabricate
    # an ordering the fixed schedule does not have.
    assert contract.waves == [["rag", "spl", "narration"], ["mcp"]]


def test_mcp_step_without_an_spl_step_declares_no_phantom_dependency() -> None:
    plan = _plan(_step("mcp", "mcp_execution"), _step("narration", "narration"))
    contract = build_execution_contract(plan)
    assert contract is not None
    assert contract.step_by_id("mcp").depends_on == []


def test_explicit_declaration_overrides_derivation() -> None:
    plan = _plan(
        _step("rag", "knowledge_retrieval"),
        _step(
            "spl",
            "spl_artifact",
            execution=StepExecutionSpec(depends_on=["rag"]),
        ),
    )
    contract = build_execution_contract(plan)
    assert contract is not None
    assert contract.step_by_id("spl").depends_on == ["rag"]
    assert contract.waves == [["rag"], ["spl"]]


# --- invalid-contract matrix (failing-first) ---------------------------------


def test_duplicate_step_ids_are_rejected() -> None:
    plan = _plan(_step("spl", "spl_artifact"), _step("spl", "narration"))
    assert "duplicate_step_id" in _codes(plan)


def test_unknown_dependency_is_rejected() -> None:
    plan = _plan(_step("spl", "spl_artifact", execution=StepExecutionSpec(depends_on=["ghost"])))
    assert "unknown_dependency" in _codes(plan)


def test_self_dependency_is_rejected() -> None:
    plan = _plan(_step("spl", "spl_artifact", execution=StepExecutionSpec(depends_on=["spl"])))
    assert "self_dependency" in _codes(plan)


def test_dependency_cycle_is_rejected() -> None:
    plan = _plan(
        _step("a", "knowledge_retrieval", execution=StepExecutionSpec(depends_on=["b"])),
        _step("b", "spl_artifact", execution=StepExecutionSpec(depends_on=["a"])),
    )
    assert "dependency_cycle" in _codes(plan)


def test_unknown_evidence_key_is_rejected() -> None:
    plan = _plan(
        _step(
            "spl",
            "spl_artifact",
            execution=StepExecutionSpec(produces_evidence_keys=["not_a_channel"]),
        )
    )
    assert "unknown_evidence_key" in _codes(plan)


def test_nested_evidence_key_resolves_against_a_real_channel() -> None:
    plan = _plan(
        _step(
            "mcp",
            "mcp_execution",
            execution=StepExecutionSpec(requires_evidence_keys=["spl_validation.normalized_spl"]),
        )
    )
    assert "unknown_evidence_key" not in _codes(plan)


def test_side_effecting_step_may_not_declare_retries() -> None:
    plan = _plan(_step("mcp", "mcp_execution", execution=StepExecutionSpec(max_attempts=2)))
    assert "unsafe_retry_side_effecting" in _codes(plan)


def test_attempts_are_bounded_on_both_ends() -> None:
    too_many = _plan(
        _step("rag", "knowledge_retrieval", execution=StepExecutionSpec(max_attempts=MAX_STEP_ATTEMPTS + 1))
    )
    assert "attempts_out_of_bounds" in _codes(too_many)
    too_few = _plan(_step("rag", "knowledge_retrieval", execution=StepExecutionSpec(max_attempts=0)))
    assert "attempts_out_of_bounds" in _codes(too_few)


def test_invalid_fallback_target_is_rejected() -> None:
    plan = _plan(_step("spl", "spl_artifact", execution=StepExecutionSpec(on_failure="nowhere")))
    assert "invalid_fallback_target" in _codes(plan)


def test_terminal_and_hil_fallback_targets_are_accepted() -> None:
    for target in sorted(EXECUTION_FALLBACK_TARGETS):
        plan = _plan(_step("spl", "spl_artifact", execution=StepExecutionSpec(on_failure=target)))
        assert "invalid_fallback_target" not in _codes(plan)


def test_self_fallback_target_is_rejected() -> None:
    plan = _plan(_step("spl", "spl_artifact", execution=StepExecutionSpec(on_failure="spl")))
    assert "self_fallback_target" in _codes(plan)


def test_parallel_group_may_not_contain_a_side_effecting_step() -> None:
    plan = _plan(
        _step("rag", "knowledge_retrieval", execution=StepExecutionSpec(parallel_group="reads")),
        _step("mcp", "mcp_execution", execution=StepExecutionSpec(parallel_group="reads")),
    )
    assert "parallel_group_side_effecting" in _codes(plan)


def test_parallel_group_may_not_contain_an_intra_group_dependency() -> None:
    plan = _plan(
        _step("rag", "knowledge_retrieval", execution=StepExecutionSpec(parallel_group="reads")),
        _step(
            "cve",
            "cve_lookup",
            execution=StepExecutionSpec(parallel_group="reads", depends_on=["rag"]),
        ),
    )
    assert "parallel_group_internal_dependency" in _codes(plan)


def test_read_only_parallel_group_is_accepted() -> None:
    plan = _plan(
        _step("rag", "knowledge_retrieval", execution=StepExecutionSpec(parallel_group="reads")),
        _step("cve", "cve_lookup", execution=StepExecutionSpec(parallel_group="reads")),
    )
    assert validate_execution_contract(plan).valid


# --- blocked / skipped semantics ---------------------------------------------


def test_blocked_step_is_not_executable_and_blocks_its_dependents() -> None:
    plan = _plan(
        _step("spl", "spl_artifact", status="blocked_policy", status_reason="skill_contract"),
        _step("mcp", "mcp_execution"),
    )
    contract = build_execution_contract(plan)
    assert contract is not None
    assert contract.step_by_id("spl").executable is False
    assert contract.step_by_id("spl").skip_reason == "skill_contract"
    assert contract.step_by_id("mcp").executable is False
    assert contract.step_by_id("mcp").skip_reason == "dependency_blocked:spl"


def test_not_onboarded_step_is_not_executable() -> None:
    plan = _plan(_step("mcp", "mcp_execution", status="not_onboarded"))
    contract = build_execution_contract(plan)
    assert contract is not None
    assert contract.step_by_id("mcp").executable is False
    assert contract.step_by_id("mcp").skip_reason == "resource_not_onboarded"


# --- deterministic downgrade --------------------------------------------------


def test_absent_plan_downgrades() -> None:
    contract, reason = execution_contract_or_downgrade(None)
    assert contract is None
    assert reason == "no_resource_plan"


def test_empty_plan_downgrades() -> None:
    contract, reason = execution_contract_or_downgrade(_plan())
    assert contract is None
    assert reason == "empty_resource_plan"


def test_invalid_plan_downgrades_with_the_first_error_code() -> None:
    plan = _plan(_step("spl", "spl_artifact", execution=StepExecutionSpec(depends_on=["ghost"])))
    contract, reason = execution_contract_or_downgrade(plan)
    assert contract is None
    assert reason == "contract_invalid:unknown_dependency"


def test_unsupported_purpose_downgrades() -> None:
    plan = _plan(_step("weird", "teleport_the_analyst"))
    contract, reason = execution_contract_or_downgrade(plan)
    assert contract is None
    assert reason == "unsupported_purpose:teleport_the_analyst"


def test_valid_plan_does_not_downgrade() -> None:
    plan = _plan(_step("spl", "spl_artifact"), _step("mcp", "mcp_execution"))
    contract, reason = execution_contract_or_downgrade(plan)
    assert reason is None
    assert contract is not None


# --- contract may not become an execution authority --------------------------


def test_contract_module_performs_no_io_and_reads_no_flag() -> None:
    """Scan code, not prose: no I/O import, no settings read, no registry load."""
    import ast
    import inspect

    from app.planner import resource_plan_execution

    tree = ast.parse(inspect.getsource(resource_plan_execution))
    imported: set[str] = set()
    called: set[str] = set()
    attributes: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.add(node.module or "")
            imported.update(f"{node.module}.{alias.name}" for alias in node.names)
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            called.add(node.func.id)
        elif isinstance(node, ast.Attribute):
            attributes.add(node.attr)

    forbidden_modules = {"requests", "httpx", "app.config", "app.config.settings"}
    assert not (imported & forbidden_modules), imported & forbidden_modules
    assert not any(name.startswith("app.connectors") for name in imported), imported
    assert not any(name.startswith("app.mcp") for name in imported), imported
    assert not any(name.startswith("app.llm") for name in imported), imported
    for forbidden_call in {"load_resource_registry", "call_tool", "generate", "evaluate_mcp_execution"}:
        assert forbidden_call not in called, forbidden_call
    assert "settings" not in attributes


@pytest.mark.parametrize("purpose", sorted(SUPPORTED_EXECUTION_PURPOSES))
def test_every_supported_purpose_derives_a_bounded_spec(purpose: str) -> None:
    spec = derive_execution_spec(_step("s", purpose))
    assert 1 <= spec.max_attempts <= MAX_STEP_ATTEMPTS
    assert spec.on_failure in EXECUTION_FALLBACK_TARGETS
    if purpose in SIDE_EFFECTING_PURPOSES:
        assert spec.max_attempts == 1
