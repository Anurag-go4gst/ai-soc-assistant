"""Per-step hook idempotency — contract, P0 hooks, and negative controls (Workstream D)."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import MagicMock

import pytest

from app.chat.canonical_execution_idempotency import (
    AcquireOutcome,
    build_idempotency_key,
    clear_in_memory_store_for_tests,
    fail_execution_step,
    inspect_execution_step,
    use_in_memory_store_for_tests,
)
from app.chat.hook_replay_contract import (
    HOOK_REPLAY_CONTRACT_VERSION,
    HookReplayEnvelope,
    build_input_fingerprint,
    build_mcp_execution_fingerprint,
    build_stored_hook_payload,
    reject_forbidden_replay_fields,
    rehydrate_mcp_execution_pair,
    sanitize_hook_result_summary,
)
from app.chat.per_step_hook_idempotency import (
    HookIdempotencyContext,
    run_idempotent_hook,
    run_idempotent_mcp_execution_hook,
    uncertainty_execution_review,
)
from app.tests.test_mcp_execution_gate import APPROVED_VALIDATION, CapturingConnector, FakeTelemetry
from app.orchestration.human_review import no_human_review
from app.orchestration.mcp_execution_gate import evaluate_mcp_execution


@pytest.fixture(autouse=True)
def _memory_idempotency() -> None:
    use_in_memory_store_for_tests(True)
    clear_in_memory_store_for_tests()
    yield
    clear_in_memory_store_for_tests()


def _context() -> HookIdempotencyContext:
    return HookIdempotencyContext(
        resource_plan_id="rp:test",
        handoff_id="h-1",
        handoff_version=1,
        step_id="hook:mcp_execution",
        lease_owner="trace-1",
    )


def _envelope(**overrides: Any) -> HookReplayEnvelope:
    base = {
        "contract_version": HOOK_REPLAY_CONTRACT_VERSION,
        "hook_name": "mcp_spl_search",
        "resource_plan_id": "rp:test",
        "handoff_id": "h-1",
        "handoff_version": 1,
        "step_id": "hook:mcp_execution",
        "operation_identity": "mcp_spl_search",
        "input_fingerprint": build_mcp_execution_fingerprint(
            selected_mcp_tool="splunk_run_query",
            selected_mcp_server="splunk",
            normalized_spl="search index=main | head 1",
            execution_intent="spl_search",
        ),
    }
    base.update(overrides)
    return HookReplayEnvelope.model_validate(base)


def _selection() -> dict[str, Any]:
    return {
        "execution_intent": "spl_search",
        "selected_mcp_server": "splunk",
        "selected_mcp_tool": "splunk_run_query",
        "tool_selection_status": "selected",
        "tool_selection_reason": "policy_ok",
    }


def _execution_pair() -> tuple[dict[str, Any], dict[str, Any]]:
    execution = {
        "status": "executed",
        "execution_intent": "spl_search",
        "selected_mcp_server": "splunk",
        "selected_mcp_tool": "splunk_run_query",
        "tool_selection_status": "selected",
        "tool_selection_reason": "policy_ok",
        "result_count": 1,
        "duration_ms": 5,
        "evidence_source": "mock",
        "execution_eligible": True,
    }
    return execution, no_human_review()


def test_hook_replay_envelope_rejects_extra_fields() -> None:
    with pytest.raises(ValueError):
        HookReplayEnvelope.model_validate(
            {
                "contract_version": HOOK_REPLAY_CONTRACT_VERSION,
                "hook_name": "mcp_spl_search",
                "resource_plan_id": "rp:test",
                "handoff_id": "h-1",
                "handoff_version": 1,
                "step_id": "s1",
                "operation_identity": "mcp_spl_search",
                "input_fingerprint": "abc",
                "api_key": "secret",
            }
        )


def test_replay_payload_rejects_secret_fields() -> None:
    with pytest.raises(ValueError, match="hook_replay_forbidden_key"):
        reject_forbidden_replay_fields({"status": "executed", "bearer_token": "x"})


def test_fingerprint_changes_produce_distinct_operations() -> None:
    fp_a = build_mcp_execution_fingerprint(
        selected_mcp_tool="splunk_run_query",
        selected_mcp_server="splunk",
        normalized_spl="search index=main | head 1",
        execution_intent="spl_search",
    )
    fp_b = build_mcp_execution_fingerprint(
        selected_mcp_tool="splunk_run_query",
        selected_mcp_server="splunk",
        normalized_spl="search index=other | head 1",
        execution_intent="spl_search",
    )
    assert fp_a != fp_b


def test_duplicate_hook_invokes_connector_once() -> None:
    context = _context()
    envelope = _envelope()
    calls = {"count": 0}

    def execute_side_effect() -> tuple[dict[str, Any], dict[str, Any]]:
        calls["count"] += 1
        return _execution_pair()

    first = run_idempotent_mcp_execution_hook(
        context,
        envelope,
        selection=_selection(),
        operation_contract="side_effecting_without_stable_idempotency",
        execute_side_effect=execute_side_effect,
    )
    second = run_idempotent_mcp_execution_hook(
        context,
        envelope,
        selection=_selection(),
        operation_contract="side_effecting_without_stable_idempotency",
        execute_side_effect=lambda: (_ for _ in ()).throw(AssertionError("connector should not run")),
    )
    assert first[0] == AcquireOutcome.EXECUTE
    assert second[0] == AcquireOutcome.REPLAY
    assert calls["count"] == 1


def test_concurrent_workers_invoke_connector_at_most_once() -> None:
    context = _context()
    envelope = _envelope()
    calls = {"count": 0}

    def execute_side_effect() -> tuple[dict[str, Any], dict[str, Any]]:
        calls["count"] += 1
        return _execution_pair()

    with ThreadPoolExecutor(max_workers=2) as pool:
        future_a = pool.submit(
            run_idempotent_mcp_execution_hook,
            context,
            envelope,
            selection=_selection(),
            operation_contract="side_effecting_without_stable_idempotency",
            execute_side_effect=execute_side_effect,
        )
        future_b = pool.submit(
            run_idempotent_mcp_execution_hook,
            context,
            envelope,
            selection=_selection(),
            operation_contract="side_effecting_without_stable_idempotency",
            execute_side_effect=execute_side_effect,
        )
        outcomes = {future_a.result(timeout=5)[0], future_b.result(timeout=5)[0]}

    assert AcquireOutcome.EXECUTE in outcomes
    assert calls["count"] == 1


def test_active_lease_blocks_second_worker_execution() -> None:
    from app.chat.canonical_execution_idempotency import acquire_execution_step

    context = _context()
    envelope = _envelope()
    operation = f"mcp_spl_search:{envelope.input_fingerprint}"
    first = acquire_execution_step(
        resource_plan_id=context.resource_plan_id,
        step_id=context.step_id,
        operation=operation,
        handoff_id=context.handoff_id,
        handoff_version=context.handoff_version,
        lease_owner="worker-a",
        side_effecting=True,
    )
    assert first.outcome == AcquireOutcome.EXECUTE
    second = acquire_execution_step(
        resource_plan_id=context.resource_plan_id,
        step_id=context.step_id,
        operation=operation,
        handoff_id=context.handoff_id,
        handoff_version=context.handoff_version,
        lease_owner="worker-b",
        side_effecting=True,
    )
    assert second.outcome == AcquireOutcome.IN_PROGRESS


def test_stale_lease_without_stable_contract_requires_reconciliation() -> None:
    context = _context()
    envelope = _envelope()
    operation = f"mcp_spl_search:{envelope.input_fingerprint}"
    key = build_idempotency_key(
        resource_plan_id=context.resource_plan_id,
        handoff_id=context.handoff_id,
        handoff_version=context.handoff_version,
        step_id=context.step_id,
        operation=operation,
    )
    run_idempotent_hook(
        context,
        envelope,
        operation_contract="side_effecting_without_stable_idempotency",
        side_effecting=True,
        execute=lambda: build_stored_hook_payload(envelope, connector_invoked=True),
    )
    fail_execution_step(idempotency_key=key, result={"error": "crash"}, retryable=True)
    record = inspect_execution_step(
        resource_plan_id=context.resource_plan_id,
        step_id=context.step_id,
        operation=operation,
        handoff_id=context.handoff_id,
        handoff_version=context.handoff_version,
    )
    assert record is not None
    from app.chat import canonical_execution_idempotency as store

    stale = record.model_copy(
        update={
            "status": "running",
            "lease_expires_at": datetime.now(UTC) - timedelta(seconds=5),
        }
    )
    store._TEST_STORE[key] = stale.model_dump(mode="json")  # type: ignore[attr-defined]
    outcome, stored = run_idempotent_hook(
        context,
        envelope,
        operation_contract="side_effecting_without_stable_idempotency",
        side_effecting=True,
        execute=lambda: build_stored_hook_payload(envelope, connector_invoked=True),
    )
    assert outcome == AcquireOutcome.REQUIRES_RECONCILIATION
    assert stored.get("reason") == "execution_outcome_uncertain"


def test_uncertain_execution_surfaces_manual_reconciliation() -> None:
    execution, review = uncertainty_execution_review({"reason": "execution_outcome_uncertain"})
    assert execution["outcome_uncertain"] is True
    assert review["required"] is True
    assert review["review_type"] == "manual_reconciliation"


def test_replay_cannot_elevate_execution_eligible() -> None:
    stored = build_stored_hook_payload(
        _envelope(),
        execution={"status": "executed", "execution_eligible": True, "result_count": 1},
        human_review=no_human_review(),
    )
    execution, _review = rehydrate_mcp_execution_pair(stored, selection=_selection())
    assert execution.get("execution_eligible") is False


def test_replay_cannot_bypass_required_hil() -> None:
    stored = build_stored_hook_payload(
        _envelope(),
        execution={"status": "executed", "result_count": 0},
        human_review={
            "required": True,
            "review_type": "execution_approval",
            "reason": "policy_block",
            "reviewer_role": "soc_lead",
            "allowed_actions": ["reject_execution"],
            "safe_message_for_user": "blocked",
        },
    )
    execution, review = rehydrate_mcp_execution_pair(stored, selection=_selection())
    assert review["required"] is True
    assert execution["status"] == "requires_human_review"


def test_stored_summary_only_includes_allowlisted_fields() -> None:
    summary = sanitize_hook_result_summary(
        {
            "status": "executed",
            "result_count": 2,
            "api_key": "must-not-appear",
            "splunk_result_envelope": {"rows": []},
        }
    )
    assert summary == {"status": "executed", "result_count": 2}


def test_evaluate_mcp_execution_with_hook_idempotency_replays_without_second_connector_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connector = CapturingConnector()
    calls: list[int] = []
    original_call = connector.call_tool

    def _counting_call_tool(*args: Any, **kwargs: Any) -> dict[str, Any]:
        calls.append(1)
        return original_call(*args, **kwargs)

    connector.call_tool = _counting_call_tool  # type: ignore[method-assign]
    monkeypatch.setenv("MCP_GLOBAL_EXECUTION_ENABLED", "true")
    monkeypatch.setenv("MCP_SERVER_MOCK_EXECUTION_ENABLED", "true")
    monkeypatch.setattr("app.orchestration.mcp_execution_gate.settings.ai_soc_demo_or_lab_execution_mode", True)
    monkeypatch.setattr("app.orchestration.mcp_execution_gate.settings.ai_soc_allow_mock_execution_without_hil_in_demo", True)
    monkeypatch.setattr("app.orchestration.mcp_execution_gate.settings.ai_soc_require_spl_execution_confirmation", False)
    monkeypatch.setattr("app.orchestration.mcp_execution_gate.get_telemetry_connector", lambda: FakeTelemetry())
    monkeypatch.setattr("app.orchestration.mcp_execution_gate.get_mcp_connector", lambda: connector)
    hook_ctx = _context()

    evaluate_mcp_execution(
        trace_id="trace-1",
        selected_skill="attack_discovery",
        workflow_plan={},
        spl_validation=APPROVED_VALIDATION,
        hook_idempotency=hook_ctx,
    )
    evaluate_mcp_execution(
        trace_id="trace-1",
        selected_skill="attack_discovery",
        workflow_plan={},
        spl_validation=APPROVED_VALIDATION,
        hook_idempotency=hook_ctx,
    )
    assert connector.arguments["search_query"] == APPROVED_VALIDATION["normalized_spl"]
    assert len(calls) == 1


def test_fingerprint_mismatch_uses_distinct_idempotency_keys() -> None:
    fp_a = build_input_fingerprint(allowlisted={"x": 1})
    fp_b = build_input_fingerprint(allowlisted={"x": 2})
    env_a = _envelope(input_fingerprint=fp_a)
    env_b = _envelope(input_fingerprint=fp_b)
    assert f"mcp_spl_search:{fp_a}" != f"mcp_spl_search:{fp_b}"
    assert env_a.input_fingerprint != env_b.input_fingerprint
