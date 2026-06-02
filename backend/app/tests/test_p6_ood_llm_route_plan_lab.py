from __future__ import annotations

from typing import Any

import pytest

from app.chat.pipeline import _apply_ood_llm_lab_metadata
from app.config import settings
from app.orchestration.mcp_execution_gate import evaluate_mcp_execution
from app.routing.supporter_registry import build_supporter_trace
from app.tests.test_mcp_execution_gate import APPROVED_VALIDATION
from app.tests.test_p2_ood_supporters_audit import _known_operation_no_coverage_candidate


def test_nearest_registry_row_supporter_is_advisory() -> None:
    trace = build_supporter_trace(
        {"primary_skill": "aggregate_and_rank", "pattern_id": "top_n_aggregation"},
        query="Which source IPs generated the most outbound connections?",
        runtime_invoked=True,
    )

    nearest = next(item for item in trace["supporters"] if item["supporter_id"] == "nearest_registry_row")
    assert nearest["status"] == "checked"
    assert nearest["authority"] == "advisory_only"
    assert nearest["question_ref"] == "q0.q002"
    assert nearest["manifest_coverage_id"] == "cov.q002.top_outbound_source_ips"
    assert trace["mcp_called"] is False
    assert trace["execution_authorized"] is False


def test_lab_primary_ood_route_plan_metadata_on_registry_miss(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "routing_mode", "llm_primary_lab")
    monkeypatch.setattr(settings, "routing_lab_llm_primary_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_environment_mode", "coe")
    route_plan_shadow: dict[str, Any] = {
        **_known_operation_no_coverage_candidate(),
        "candidate_available": True,
        "candidate_reason": "llm_shadow_candidate",
        "question_runtime_map": None,
        "precondition_evaluation": {"evaluation_skipped": True},
    }

    _apply_ood_llm_lab_metadata(
        route_plan_shadow,
        "Find top 10 users with failed Okta logins in the last 24 hours.",
    )

    lab = route_plan_shadow["ood_llm_route_plan_lab"]
    assert lab is not None
    assert lab["enabled"] is True
    assert lab["registry_exact_match"] is False
    assert lab["llm_primary_for_ood"] is True
    assert lab["validator_wins"] is True
    assert lab["execution_authorized"] is False
    nearest = next(
        item for item in route_plan_shadow["supporter_trace"]["supporters"]
        if item["supporter_id"] == "nearest_registry_row"
    )
    assert nearest["status"] == "checked"


def test_precondition_eval_blocks_before_mcp_discovery(monkeypatch: pytest.MonkeyPatch) -> None:
    telemetry = FakeTelemetry()
    calls = {"registry": 0, "connector": 0}

    def fail_registry() -> None:
        calls["registry"] += 1
        raise AssertionError("registry should not load after precondition failure")

    def fail_connector() -> None:
        calls["connector"] += 1
        raise AssertionError("connector should not be requested after precondition failure")

    monkeypatch.setattr("app.orchestration.mcp_execution_gate.get_telemetry_connector", lambda: telemetry)
    monkeypatch.setattr("app.orchestration.mcp_execution_gate.load_mcp_registry_status", fail_registry)
    monkeypatch.setattr("app.orchestration.mcp_execution_gate.get_mcp_connector", fail_connector)

    execution, review = evaluate_mcp_execution(
        trace_id="trace-precondition-block",
        selected_skill="attack_discovery",
        workflow_plan={},
        spl_validation=APPROVED_VALIDATION,
        precondition_evaluation={
            "evaluation_skipped": False,
            "route_status": "cannot_route_missing_lookup",
            "preconditions_failed": ["lookup_available"],
        },
    )

    assert calls == {"registry": 0, "connector": 0}
    assert execution["status"] == "requires_human_review"
    assert execution["tool_selection_status"] == "blocked_by_precondition_eval"
    assert execution["block_reason"] == "precondition_eval_failed"
    assert review["review_type"] == "precondition_review"
    assert telemetry.mcp_events[-1]["reason"] == "precondition_eval_failed"


class FakeTelemetry:
    def __init__(self) -> None:
        self.mcp_events: list[dict[str, Any]] = []

    def record_mcp_execution(self, trace_id: str, **fields: Any) -> None:
        self.mcp_events.append({"trace_id": trace_id, **fields})
