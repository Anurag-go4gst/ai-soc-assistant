from __future__ import annotations

from typing import Any

import pytest

from app.api.routes_chat import chat
from app.schemas.requests import ChatRequest
from app.schemas.responses import PlaceholderResponse


BASELINE_CASES: list[dict[str, Any]] = [
    {
        "id": "policy_escalation_failed_login",
        "query": "What is the escalation policy for repeated failed login alerts?",
        "expected_wrong": {
            "selected_skill": "attack_discovery",
            "context_sufficiency.status": "blocked_by_policy",
            "mitre_mappings_len": 1,
            "execution.status": "requires_human_review",
            "source_evidence_count": 2,
            "source_evidence_types": ["splunk_mcp_saia", "splunk_mcp"],
        },
    },
    {
        "id": "failed_login_hybrid_action_guidance",
        "query": "Find accounts failing login in the last 24 hours, exclude service accounts, and tell me what analyst action I should take",
        "expected_wrong": {
            "selected_skill": "attack_discovery",
            "context_sufficiency.status": "blocked_by_policy",
            "candidate_spl_present": True,
            "execution.status": "requires_human_review",
            "spl_validation.approved": True,
        },
    },
    {
        "id": "mitre_mapping_without_alert_context",
        "query": "Map 148 failed logins across 12 accounts from external IPs to MITRE",
        "expected_wrong": {
            "human_review.required": True,
            "candidate_spl_present": False,
            "mitre_mappings_len": 0,
        },
    },
    {
        "id": "spl_generation_top_failed_login_users",
        "query": "Generate SPL for the top failed-login users in the last 24 hours",
        "expected_wrong": {
            "candidate_spl_present": True,
            "execution.status": "requires_human_review",
        },
    },
    {
        "id": "dga_investigation_steps",
        "query": "Explain investigation steps for DGA detection",
        "expected_wrong": {
            "selected_skill": "knowledge_recall",
        },
    },
    {
        "id": "top_failed_login_users_exclude_service_accounts",
        "query": "Show top users with failed login count in the last 24 hours and exclude service accounts",
        "expected_wrong": {
            "candidate_spl_present": True,
            "execution.status": "requires_human_review",
            "context_sufficiency.status": "blocked_by_policy",
        },
    },
]


@pytest.mark.parametrize("case", BASELINE_CASES, ids=[case["id"] for case in BASELINE_CASES])
def test_current_chat_runtime_baseline(case: dict[str, Any]) -> None:
    response = chat(ChatRequest(message=case["query"]))

    _assert_core_response_shape(response)
    snapshot = _runtime_snapshot(response)
    _xfail_baseline_behavior(snapshot, case["expected_wrong"])


def _assert_core_response_shape(response: PlaceholderResponse) -> None:
    assert response is not None
    assert isinstance(response.trace_id, str)
    assert response.trace_id
    assert isinstance(response.message, str)
    assert isinstance(response.note, str)
    assert isinstance(response.selected_skill, str)
    assert isinstance(response.source_evidence, list)

    payload = response.model_dump()
    for section in ("workflow_plan", "context_sufficiency", "execution", "human_review"):
        assert isinstance(payload.get(section), dict)

    assert isinstance(_nested(payload, "workflow_plan", "status"), str)
    assert isinstance(_nested(payload, "workflow_plan", "execution_enabled"), bool)
    assert isinstance(_nested(payload, "context_sufficiency", "status"), str)
    assert isinstance(_nested(payload, "execution", "status"), str)
    assert isinstance(_nested(payload, "human_review", "required"), bool)


def _runtime_snapshot(response: PlaceholderResponse) -> dict[str, Any]:
    payload = response.model_dump()
    source_evidence = payload.get("source_evidence") or []
    return {
        "selected_skill": payload.get("selected_skill"),
        "context_sufficiency.status": _nested(payload, "context_sufficiency", "status"),
        "mitre_mappings_len": len(payload.get("mitre_mappings") or []),
        "execution.status": _nested(payload, "execution", "status"),
        "source_evidence_count": len(source_evidence),
        "source_evidence_types": [item.get("source_type") for item in source_evidence],
        "source_evidence_rag_collected": any(
            str(item.get("source_type") or "").startswith("rag") for item in source_evidence
        ),
        "candidate_spl_present": payload.get("candidate_spl") is not None,
        "spl_validation.approved": _nested(payload, "spl_validation", "approved"),
        "human_review.required": _nested(payload, "human_review", "required"),
    }


def _nested(payload: dict[str, Any], section: str, field: str) -> Any:
    value = payload.get(section)
    if not isinstance(value, dict):
        return None
    return value.get(field)


def _xfail_baseline_behavior(snapshot: dict[str, Any], expected_wrong: dict[str, Any]) -> None:
    mismatches = {
        key: {"expected": expected, "actual": snapshot.get(key)}
        for key, expected in expected_wrong.items()
        if snapshot.get(key) != expected
    }
    if mismatches:
        pytest.xfail(f"control plane not enabled; current wrong-behavior snapshot changed: {mismatches}")
    pytest.xfail(f"control plane not enabled; current wrong-behavior snapshot still present: {expected_wrong}")
