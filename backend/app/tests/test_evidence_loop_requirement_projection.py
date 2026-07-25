from __future__ import annotations

from app.chat.pipeline import _loop_required_produces


def test_evidence_loop_returns_to_plan_for_missing_lookup() -> None:
    requirements = _loop_required_produces(
        {
            "row_authority_summary": {
                "row_authority_status": "exact_known_needs_lookup",
                "blockers": ["lookup_artifact_required"],
            }
        }
    )

    assert requirements == ["lookup_dependency"]


def test_evidence_loop_returns_to_plan_for_missing_source_profile() -> None:
    requirements = _loop_required_produces(
        {
            "source_profile_binding_summary": {
                "environment_kb_is_telemetry": False,
                "source_profile_bindings_missing": [
                    {"profile_key": "ot_network_index", "slot": "index"},
                ],
            }
        }
    )

    assert requirements == ["source_profile"]


def test_evidence_loop_carries_missing_required_evidence() -> None:
    requirements = _loop_required_produces(
        {
            "missing_required_evidence": ["mfa_status", "post_login_activity"],
            "evidence_needs": ["mfa_status"],
        }
    )

    assert requirements == ["mfa_status", "post_login_activity"]


def test_evidence_loop_degrades_when_required_mcp_disabled() -> None:
    requirements = _loop_required_produces(
        {
            "mcp_allowed": None,
            "row_authority_summary": {
                "row_authority_status": "exact_known_needs_detection_binding",
            },
            "source_profile_binding_summary": {
                "source_profile_bindings_missing": [
                    {"profile_key": "vpn_index", "slot": "vpn_index"},
                ],
            },
        }
    )

    assert requirements == ["detection_binding", "source_profile"]


from app.chat.pipeline import build_live_chat_response, _loop_required_produces
from app.config import settings
from app.schemas.requests import ChatRequest
import pytest


def test_run_contract_loop_decision_matches_evidence_loop_decision() -> None:
    payload = build_live_chat_response(
        ChatRequest(message="Which users have excessive failed logins?")
    ).model_dump(mode="json")
    plan = payload.get("evidence_plan") or {}
    contract = payload.get("run_contract") or {}
    gate = (payload.get("structured_context") or {}).get("final_evidence_gate") or {}
    requirements = _loop_required_produces(plan)
    missing = plan.get("missing_required_evidence") or []
    if requirements:
        assert set(requirements).issubset(set(missing) | set(plan.get("evidence_needs") or []))
    assert int(contract.get("collected_evidence_count") or 0) == 0
    assert contract.get("allow_live_result_language") is False
    assert gate.get("collected_evidence_count") == contract.get("collected_evidence_count")


def test_missing_lookup_chat_probe_no_live_language() -> None:
    query = (
        "Generate a review-only SPL query to correlate power_sector_iocs.csv indicator_ip "
        "with Cisco ASA traffic in index=cisco_asa against dest_ip for the last 24h."
    )
    payload = build_live_chat_response(ChatRequest(message=query)).model_dump(mode="json")
    contract = payload.get("run_contract") or {}
    assert contract.get("allow_live_result_language") is False
    assert int(contract.get("collected_evidence_count") or 0) == 0


def test_mcp_needed_but_blocked_preserves_route_and_capability() -> None:
    payload = build_live_chat_response(
        ChatRequest(message="Which users have excessive failed logins?")
    ).model_dump(mode="json")
    plan = payload.get("evidence_plan") or {}
    contract = payload.get("run_contract") or {}
    if not plan.get("needs_mcp"):
        pytest.skip("probe did not require MCP")
    routing = contract.get("routing") or {}
    assert payload.get("selected_skill") == routing.get("canonical_skill")
    steps = (plan.get("resource_plan") or {}).get("steps") or []
    assert any(isinstance(s, dict) and s.get("step_id") == "mcp" for s in steps)
    posture = contract.get("mcp_posture") or {}
    assert posture.get("execution_authorized") is False
