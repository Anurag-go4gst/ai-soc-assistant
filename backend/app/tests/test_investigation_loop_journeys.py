"""Golden investigation-loop journeys with the product HIL path enabled.

Pytest defaults keep ``ai_soc_investigation_plan_before_resource_plan_enabled``
false. COE/VPS enable it — these tests exercise that analyst-visible path.
"""

from __future__ import annotations

import pytest

from app.chat.canonical_handoff_store import clear_all_handoffs_for_tests
from app.chat.investigation_plan_relevance import (
    plan_text_blob,
    required_auth_anchors_present,
    unjustified_primary_pivots,
)
from app.chat.pipeline import build_live_chat_response
from app.chat.session_store import clear_all_session_pins_for_tests
from app.chat.trace_effective_state import build_effective_state_projection
from app.config import settings
from app.query_understanding.parser import understand_query
from app.schemas.requests import ChatRequest

SSH_QUERY = (
    "Investigate whether the successful SSH login from 198.51.100.42, after "
    "25 failed login attempts, indicates a compromised account. Check the relevant "
    "evidence, investigate any suspicious activity after the successful login, "
    "and tell me your conclusion and recommended next action. Do not execute any remediation."
)

MFA_QUERY = (
    "Investigate whether repeated failed MFA attempts followed by a successful "
    "sign-in from the same source indicate account compromise. Correlate the "
    "successful sign-in with subsequent account activity and tell me what evidence "
    "supports or weakens the compromise hypothesis. Recommend the next action but "
    "do not execute any remediation."
)

POWERSHELL_QUERY = (
    "Investigate a suspicious PowerShell execution followed by an outbound network "
    "connection and a downloaded child process. Determine whether the events are "
    "related, evaluate the relevant endpoint and network evidence, and tell me "
    "whether the activity appears malicious. Recommend the next action but do not "
    "execute remediation."
)

ENDPOINT_PERSISTENCE_QUERY = (
    "An analyst reports that an office application spawned a script interpreter on one "
    "workstation; minutes later a new scheduled task appeared and the same host contacted "
    "an unfamiliar external address. Investigate whether these events are related, correlate "
    "them by host, user, and time, and—if the task is suspicious—check persistence and "
    "subsequent activity. Give a conclusion and recommend the safest next action, but do not "
    "execute remediation."
)

_HIL_FLAGS = {
    "ai_soc_curated_enrichment_activation_enabled": True,
    "ai_soc_investigation_plan_before_resource_plan_enabled": True,
    "ai_soc_capability_snapshot_enabled": True,
    "ai_soc_guided_composable_planning_enabled": True,
    "ai_soc_investigation_planner_enabled": False,
    "ai_soc_session_context_enabled": True,
    "ai_soc_resource_plan_execution_enabled": True,
    "langgraph_orchestration_enabled": False,
}


@pytest.fixture(autouse=True)
def _hil_product_path(monkeypatch: pytest.MonkeyPatch) -> None:
    clear_all_handoffs_for_tests()
    clear_all_session_pins_for_tests()
    for name, value in _HIL_FLAGS.items():
        monkeypatch.setattr(settings, name, value)


def _plan_blob(response) -> str:
    approval = response.investigation_approval or {}
    validated = approval.get("validated_plan") or {}
    if not validated and isinstance(response.validated_investigation_plan, dict):
        validated = response.validated_investigation_plan
    return plan_text_blob(validated)


def _approve(first, query: str):
    approval = first.investigation_approval
    assert approval is not None
    assert approval.get("status") in {"awaiting_approval", "edited_revalidated"}
    assert first.session_context_status is not None
    return build_live_chat_response(
        ChatRequest(
            message=query,
            session_id=first.session_context_status.session_id,
            investigation_review_action="run",
            investigation_handoff_id=str(approval["handoff_id"]),
            investigation_handoff_version=int(approval["handoff_version"]),
        )
    )


def _assert_mcp_off_execution_boundary(second) -> None:
    payload = second.model_dump(mode="json")
    evidence = payload.get("evidence_plan") or {}
    assert evidence.get("needs_mcp") is True
    assert evidence.get("mcp_available") in {False, None}
    assert evidence.get("answer_mode") != "guided_investigation"
    execution = payload.get("execution") or {}
    assert execution.get("status") != "executed"
    assert execution.get("executed_spl") in (None, "")
    if payload.get("spl_validation") is None:
        assert execution.get("block_reason") == "read_source_required_but_unavailable"
        assert execution.get("tool_selection_reason") == "read_source_required_but_unavailable"
    else:
        assert execution.get("block_reason") == "mcp_not_allowed_by_evidence_plan"
    outcome = payload.get("investigation_outcome") or {}
    assert list(outcome.get("findings") or []) == []
    rem = payload.get("remediation_execution") or {}
    assert rem in ({}, None) or not rem.get("executed_any")
    effective = build_effective_state_projection(payload)
    assert effective["execution"]["execution_requested"] is True
    assert effective["execution"]["execution_performed"] is False
    assert effective["review_only"] is False
    if effective["spl_authoring"].get("spl_artifact_available"):
        assert effective["spl_authoring"]["spl_role"] == "investigation_fallback"
        assert effective["evidence"]["spl_artifact"]["status"] == "draft_fallback"
    from app.chat.reviewer_trace import assemble_forensic_bundle, build_reviewer_trace

    reviewer = build_reviewer_trace(
        assemble_forensic_bundle(
            trace_id="loop",
            run={
                "trace_id": "loop",
                "status": "completed",
                "selected_skill": payload.get("selected_skill"),
                "answer_mode": payload.get("answer_mode"),
                "metadata": {"effective_state": effective, "selected_skill": payload.get("selected_skill")},
            },
            events=[],
            payload=payload,
        )
    )
    assert reviewer["review_decision"]["run_outcome"] != "completed_review_only"
    assert reviewer["execution"]["execution_requested"] is True
    reason = str(reviewer["review_decision"].get("reason") or "")
    assert "neither requested nor authorised" not in reason.lower()
    wp = payload.get("workflow_plan") or {}
    if "mcp_search" in list(wp.get("tool_plan") or []):
        assert wp.get("plan_role") != "guided_review_blueprint"
        assert "no_live_query" not in list(wp.get("safety_gates") or [])
    message = str(second.message or "")
    card = second.analyst_response
    card_text = ""
    if card is not None:
        card_text = " ".join(
            str(part or "")
            for part in (
                getattr(card, "direct_answer_summary", None),
                getattr(card, "one_sentence_finding", None),
                getattr(card, "review_notice", None),
            )
        )
    visible = f"{message} {card_text} {second.note or ''}".lower()
    assert "review-only" not in visible
    assert "unavailable" in visible or "disabled" in visible
    assert "inconclusive" in visible or "insufficient" in visible
    assert list(outcome.get("evidence_refs") or []) == []
    severity = str(outcome.get("severity_label") or "").lower()
    assert not severity.startswith("p"), severity


@pytest.mark.parametrize("pass_id", [1, 2])
def test_ssh_hil_plan_then_mcp_off_run(pass_id: int) -> None:  # noqa: ARG001
    first = build_live_chat_response(ChatRequest(message=SSH_QUERY))
    blob = _plan_blob(first)
    anchors = required_auth_anchors_present(blob)
    assert anchors["authentication_failure"] is True
    assert anchors["authentication_success"] is True
    assert anchors["post_login_activity"] is True
    assert "review-only" not in blob.lower()
    selected = first.selected_use_case.model_dump() if first.selected_use_case else {}
    if not selected:
        selected = (first.model_dump(mode="json").get("selected_use_case") or {})
    assert first.selected_skill == "attack_discovery"
    assert selected.get("use_case_id") == "auth_success_after_failure"
    second = _approve(first, SSH_QUERY)
    _assert_mcp_off_execution_boundary(second)


@pytest.mark.parametrize("pass_id", [1, 2])
def test_mfa_hil_plan_rejects_ot_beacon_then_mcp_off_run(pass_id: int) -> None:
    first = build_live_chat_response(ChatRequest(message=MFA_QUERY))
    blob = _plan_blob(first)
    assert unjustified_primary_pivots(blob, query=MFA_QUERY) == []
    anchors = required_auth_anchors_present(blob)
    assert anchors["authentication_failure"] is True
    assert anchors["authentication_success"] is True
    assert "network beacon" not in blob.lower()
    assert "ot inventory" not in blob.lower()
    second = _approve(first, MFA_QUERY)
    _assert_mcp_off_execution_boundary(second)


@pytest.mark.parametrize("pass_id", [1, 2])
def test_powershell_hil_plan_is_endpoint_network_family(pass_id: int) -> None:
    first = build_live_chat_response(ChatRequest(message=POWERSHELL_QUERY))
    blob = _plan_blob(first).lower()
    assert "process" in blob or "powershell" in blob
    assert "network" in blob or "outbound" in blob or "connection" in blob
    assert "network beacon" not in blob
    second = _approve(first, POWERSHELL_QUERY)
    payload = second.model_dump(mode="json")
    rem = payload.get("remediation_execution") or {}
    assert rem in ({}, None) or not rem.get("executed_any")
    outcome = payload.get("investigation_outcome") or {}
    assert list(outcome.get("findings") or []) == []


@pytest.mark.parametrize("pass_id", [1, 2])
def test_endpoint_persistence_query_preserves_investigation_shape(pass_id: int) -> None:  # noqa: ARG001
    understood = understand_query(ENDPOINT_PERSISTENCE_QUERY)
    assert "one" not in understood.entities.host
    first = build_live_chat_response(ChatRequest(message=ENDPOINT_PERSISTENCE_QUERY))
    blob = _plan_blob(first).lower()
    assert first.selected_skill == "guided_investigation"
    assert first.investigation_approval is not None
    assert first.investigation_approval.get("status") == "awaiting_approval"
    assert "process" in blob or "script" in blob
    assert "scheduled" in blob or "persistence" in blob
    assert "network" in blob or "external" in blob or "connection" in blob
    second = _approve(first, ENDPOINT_PERSISTENCE_QUERY)
    _assert_mcp_off_execution_boundary(second)
