from __future__ import annotations

from typing import Any

import pytest

from app.api.routes_chat import chat
from app.routing.operation_audit import operation_audit_human_review
from app.routing.supporter_registry import build_supporter_trace
from app.schemas.requests import ChatRequest
from app.tests.test_route_plan_stage3k_r2 import _patch_common_chat_dependencies, _valid_route_plan_candidate


def _novel_operation_candidate() -> dict[str, Any]:
    candidate = _valid_route_plan_candidate()
    candidate["primary_skill"] = "invent_new_soc_operation"
    candidate["pattern_id"] = "novel_unregistered_operation"
    candidate["operation_type"] = "speculative_hunt"
    candidate["post_enrichment"] = []
    return candidate


def _known_operation_no_coverage_candidate() -> dict[str, Any]:
    candidate = _valid_route_plan_candidate()
    candidate["pattern_id"] = "known_operation_no_registry_row"
    candidate["parameters"]["group_by"] = {"field": "src_ip", "source_class": "network_traffic"}
    candidate["source_class"] = "network_traffic"
    return candidate


def test_novel_ood_candidate_stops_at_audit_hil(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_common_chat_dependencies(
        monkeypatch,
        skill="attack_discovery",
        disable_deterministic_route_plan=True,
    )
    monkeypatch.setattr("app.api.routes_chat._route_plan_shadow_candidate", lambda query: _novel_operation_candidate())

    response = chat(ChatRequest(message="Find top 10 users with failed Okta logins in the last 24 hours."))

    assert response.primary_operation == "invent_new_soc_operation"
    assert response.coverage_id is None
    assert response.semantic_intent is not None
    assert response.semantic_intent["path_type"] == "novel_ood"
    assert response.operation_audit is not None
    assert response.operation_audit["audit_required"] is True
    assert response.operation_audit["promotion_candidate"] is True
    assert response.operation_audit["spl_execution_allowed"] is False
    assert response.route_plan_shadow.operation_audit == response.operation_audit
    audit_review = operation_audit_human_review(response.operation_audit)
    assert audit_review is not None
    assert audit_review["review_type"] == "operation_promotion_review"
    assert response.human_review.required is True
    assert response.execution.executed_spl is None


def test_known_compatible_ood_records_review_without_live_execute(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_common_chat_dependencies(monkeypatch, skill="attack_discovery")
    monkeypatch.setattr(
        "app.api.routes_chat._route_plan_shadow_candidate",
        lambda query: _known_operation_no_coverage_candidate(),
    )

    response = chat(ChatRequest(message="Rank network source IPs by connection volume."))

    assert response.primary_operation == "aggregate_and_rank"
    assert response.coverage_id is None
    assert response.semantic_intent is not None
    assert response.semantic_intent["path_type"] == "known_compatible_ood"
    assert response.operation_audit is not None
    assert response.operation_audit["route_status"] == "known_compatible_review"
    assert response.operation_audit["promotion_candidate"] is False
    assert response.human_review.review_type != "operation_promotion_review"
    assert response.execution.executed_spl is None


def test_supporter_trace_is_read_only_and_never_calls_mcp(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_common_chat_dependencies(monkeypatch, skill="attack_discovery")
    monkeypatch.setattr(
        "app.api.routes_chat._route_plan_shadow_candidate",
        lambda query: _known_operation_no_coverage_candidate(),
    )

    response = chat(ChatRequest(message="Rank network source IPs by connection volume."))

    assert response.route_plan_shadow.supporter_trace is not None
    trace = response.route_plan_shadow.supporter_trace
    assert trace["authority"] == "advisory_read_only"
    assert trace["mcp_called"] is False
    assert trace["spl_generated"] is False
    assert trace["execution_authorized"] is False
    assert {item["supporter_id"] for item in trace["supporters"]} >= {
        "route_plan_preflight",
        "ioc_registry_staleness_check",
        "detection_registry_ref_check",
        "precondition_shadow_evaluation",
    }


def test_supporter_trace_checks_ioc_staleness_when_lookup_required(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.config.settings.ioc_registry_enabled", True)
    trace = build_supporter_trace(
        {
            "primary_skill": "lookup_correlation",
            "parameters": {"lookup_ref": "internal_curated_v1"},
            "evidence_needs": {"lookup_required": True},
        }
    )

    ioc_status = next(item for item in trace["supporters"] if item["supporter_id"] == "ioc_registry_staleness_check")
    assert ioc_status["lookup_required"] is True
    assert ioc_status["status"] == "checked"
    assert ioc_status["side_effects"] is False
