"""Planning telemetry sink reconciliation (plan item 10)."""

from __future__ import annotations

from typing import Any

import pytest

from app.chat import durable_planning_telemetry as telemetry
from app.chat.planning_telemetry_policy import (
    diagnostic_planning_telemetry_to_db_enabled,
    is_audit_critical_planning_event,
    should_persist_planning_event_to_db,
    validate_canonical_planning_telemetry_config,
)
from app.config import ConfigError, Settings, _validate


@pytest.fixture(autouse=True)
def _reset() -> Any:
    telemetry.use_test_event_store(False)
    telemetry.clear_persisted_events_for_tests()
    yield
    telemetry.use_test_event_store(False)
    telemetry.clear_persisted_events_for_tests()


def test_audit_critical_events_are_recognized() -> None:
    assert is_audit_critical_planning_event("resource_plan.created")
    assert is_audit_critical_planning_event("request.failed")
    assert is_audit_critical_planning_event("handoff.persisted")
    assert not is_audit_critical_planning_event("lane_router.decided")
    assert not is_audit_critical_planning_event("planner_handoff.created")


def test_diagnostic_events_honour_sink_none() -> None:
    settings = Settings(telemetry_mode="db", ai_soc_telemetry_sink="none")
    assert diagnostic_planning_telemetry_to_db_enabled(settings) is False
    assert should_persist_planning_event_to_db("lane_router.decided", settings=settings) is False
    assert should_persist_planning_event_to_db("resource_plan.created", settings=settings) is True


def test_diagnostic_events_honour_telemetry_mode_none() -> None:
    settings = Settings(telemetry_mode="none", ai_soc_telemetry_sink="db")
    assert diagnostic_planning_telemetry_to_db_enabled(settings) is False


def test_diagnostic_skipped_when_sink_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.config import settings

    monkeypatch.setattr(settings, "telemetry_mode", "db")
    monkeypatch.setattr(settings, "ai_soc_telemetry_sink", "none")
    monkeypatch.setattr(telemetry, "canonical_db_disabled", lambda: False)

    def _boom(*_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("run_in_canonical_unit_of_work should not be called")

    monkeypatch.setattr(telemetry, "run_in_canonical_unit_of_work", _boom)

    telemetry.persist_planning_event({"event": "lane_router.decided", "trace_id": "t-1"})

    assert telemetry.persisted_events() == []


def test_audit_critical_still_persists_when_sink_none(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.config import settings

    monkeypatch.setattr(settings, "telemetry_mode", "db")
    monkeypatch.setattr(settings, "ai_soc_telemetry_sink", "none")
    monkeypatch.setattr(telemetry, "canonical_db_disabled", lambda: False)

    called = {"count": 0}

    def _run(fn, **_kwargs):
        called["count"] += 1
        return None

    monkeypatch.setattr(telemetry, "run_in_canonical_unit_of_work", _run)

    telemetry.persist_planning_event({"event": "resource_plan.created", "trace_id": "t-2"}, immediate=True)

    assert called["count"] == 1


def test_startup_rejects_execution_with_all_telemetry_disabled() -> None:
    with pytest.raises(ConfigError, match="audit-critical"):
        _validate(
            Settings(
                telemetry_mode="none",
                ai_soc_telemetry_sink="none",
                mcp_global_execution_enabled=True,
            )
        )


def test_startup_allows_none_sink_without_execution() -> None:
    validated = _validate(
        Settings(
            telemetry_mode="none",
            ai_soc_telemetry_sink="none",
            mcp_global_execution_enabled=False,
        )
    )
    assert validated.ai_soc_telemetry_sink == "none"


def test_validate_canonical_planning_telemetry_config_direct() -> None:
    with pytest.raises(ConfigError):
        validate_canonical_planning_telemetry_config(
            Settings(
                telemetry_mode="none",
                ai_soc_telemetry_sink="none",
                mcp_global_execution_enabled=True,
            )
        )
