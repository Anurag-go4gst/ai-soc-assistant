from __future__ import annotations

import pytest

from app.api.routes_chat import chat
from app.routing.operation_audit_store import (
    clear_operation_audit_store_for_tests,
    export_coe_promotion_candidates,
    list_operation_audit_entries,
    record_operation_audit,
)
from app.routing.use_case_registry_bridge import build_use_case_registry_bridge
from app.schemas.requests import ChatRequest
from app.tests.test_p2_ood_supporters_audit import _novel_operation_candidate
from app.tests.test_route_plan_stage3k_r2 import _patch_common_chat_dependencies


def test_use_case_registry_bridge_is_advisory_only() -> None:
    bridge = build_use_case_registry_bridge("Which SOP covers brute force authentication?")
    assert bridge["authority"] == "advisory_only"
    assert bridge["top_use_case_id"] == "soc_show_sop"


def test_operation_audit_store_records_and_detects_repeat_pattern() -> None:
    clear_operation_audit_store_for_tests()
    for _ in range(3):
        record_operation_audit(
            {
                "audit_required": True,
                "proposed_operation": "repeatable_custom_op",
                "path_type": "novel_ood",
            },
            trace_id="trace-repeat",
        )
    promotions = export_coe_promotion_candidates()
    assert any(item["proposed_operation"] == "repeatable_custom_op" for item in promotions)
    assert len(list_operation_audit_entries()) >= 3


def test_chat_surfaces_use_case_bridge_on_shadow(monkeypatch: pytest.MonkeyPatch) -> None:
    clear_operation_audit_store_for_tests()
    _patch_common_chat_dependencies(monkeypatch, skill="attack_discovery")
    monkeypatch.setattr(
        "app.api.routes_chat._route_plan_shadow_candidate",
        lambda query: _novel_operation_candidate(),
    )

    response = chat(
        ChatRequest(message="Find top 10 users with failed Okta logins in the last 24 hours.")
    )

    assert response.route_plan_shadow is not None
    assert response.route_plan_shadow.use_case_registry_bridge is not None
    assert response.route_plan_shadow.use_case_registry_bridge["authority"] == "advisory_only"
    assert response.operation_audit is not None
    assert "coe_promotion_queue" in response.operation_audit
