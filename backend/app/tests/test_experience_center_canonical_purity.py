"""Experience Center must not touch canonical persistence or terminal telemetry."""

from __future__ import annotations

import json

import pytest

from app.api.routes_scenarios import run_demo_scenario_fixture
from app.demo.scenarios import SCENARIOS
from app.chat import canonical_execution_idempotency as idempotency_repo
from app.chat import canonical_handoff_repository as handoff_repo
from app.chat import durable_planning_telemetry as durable_telemetry
from app.chat.planning_telemetry import planning_events, reset_planning_telemetry_for_tests

_TERMINAL_EVENTS = frozenset({"request.completed", "request.failed"})
_RESOURCE_PLAN_COMMIT_EVENTS = frozenset(
    {
        "resource_plan.committed",
        "resource_plan.commit_reused",
    }
)


@pytest.fixture(autouse=True)
def _reset_canonical_stores() -> None:
    handoff_repo.clear_in_memory_store_for_tests()
    idempotency_repo.clear_in_memory_store_for_tests()
    reset_planning_telemetry_for_tests()
    durable_telemetry.clear_persisted_events_for_tests()
    durable_telemetry.use_test_event_store(True)
    yield
    durable_telemetry.use_test_event_store(False)


@pytest.fixture(autouse=True)
def _block_live_provider_and_canonical_runtime(monkeypatch: pytest.MonkeyPatch) -> None:
    import app.llm.sidecar_clients as sidecar_clients
    import app.llm.clients.endpoint_resolver as resolver

    def _boom(*_args, **_kwargs):
        raise AssertionError("EC path must not call a live provider or canonical runtime")

    monkeypatch.setattr(sidecar_clients, "invoke_sidecar_role", _boom)
    monkeypatch.setattr(resolver, "build_synthesis_client_from_settings", _boom)
    monkeypatch.setattr(resolver, "build_failover_chat_client", _boom)

    import app.chat.canonical_planning_orchestrator as orchestrator
    import app.planner.executor as executor

    monkeypatch.setattr(orchestrator, "run_canonical_planning", _boom)
    monkeypatch.setattr(executor, "execute_plan_dispatch", _boom)


def _scenario_ids() -> list[str]:
    return sorted(SCENARIOS.keys())


def _handoff_rows() -> list[dict]:
    return list(getattr(handoff_repo, "_TEST_STORE", {}).values())


def _idempotency_rows() -> list[dict]:
    return list(getattr(idempotency_repo, "_TEST_STORE", {}).values())


def _all_planning_event_names() -> list[str]:
    events = planning_events() + durable_telemetry.persisted_events()
    return [str(event.get("event") or "") for event in events]


@pytest.mark.parametrize("scenario_id", _scenario_ids())
def test_ec_scenario_emits_no_canonical_persistence(scenario_id: str) -> None:
    response = run_demo_scenario_fixture(scenario_id)
    assert response.message or response.analyst_summary

    assert _handoff_rows() == [], f"{scenario_id}: canonical_handoffs must stay empty"
    assert _idempotency_rows() == [], f"{scenario_id}: execution idempotency store must stay empty"

    event_names = _all_planning_event_names()
    assert event_names == [], f"{scenario_id}: canonical_planning_events must stay empty: {event_names}"

    assert not any(name in _TERMINAL_EVENTS for name in event_names)
    assert not any(name in _RESOURCE_PLAN_COMMIT_EVENTS for name in event_names)

    for row in _handoff_rows():
        assert not row.get("committed_resource_plan_id")
        assert not row.get("committed_resource_plan")

    assert response.evidence_origin == "coe_synthetic_fixture"
    assert response.demo_mode is True

    gov = response.governance_trace or response.experience_center_governance
    assert gov is not None, f"{scenario_id}: governance panel must render"
    assert response.investigation_lineage is not None, f"{scenario_id}: lineage must render"

    payload = response.model_dump()
    fs_gov = payload.get("foundation_sec_governance") or {}
    if isinstance(fs_gov, dict) and "live_llm_called" in fs_gov:
        assert fs_gov["live_llm_called"] is False
    assert '"live_llm_called": false' in json.dumps(payload).lower()
