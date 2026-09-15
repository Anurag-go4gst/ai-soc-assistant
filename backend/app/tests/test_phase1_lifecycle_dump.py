"""Phase 1 observation dump of the controlled SOC lifecycle. No product changes."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.chat.remediation_runtime import remediation_plan_eligible
from app.config import settings
from app.graph.resource_planner_graph import plan_delta_reasoning_eligible

from app.tests.test_controlled_soc_lifecycle_acceptance import (
    LIFECYCLE_QUERY,
    _approve_investigation,
    _arm_hil,
    _arm_mcp,
    _chat,
    _confirm_execution_if_needed,
    _discover,
    _session_id,
    _stub_reasoners,
    _SOURCE_PROFILE_SLOTS,
)
from tools.controlled_mcp_server.server import ControlledMcpServer

_DUMP_PATH = Path("/tmp/phase1_lifecycle_dump.json")
_TURN_DUMP_PATH = Path("/tmp/phase1_turn_trace.json")


def _summarize_source(item: dict) -> dict:
    preview = item.get("preview_rows") or []
    return {
        "evidence_id": item.get("evidence_id"),
        "source_type": item.get("source_type"),
        "collection_status": item.get("collection_status"),
        "result_count": item.get("result_count"),
        "fields_returned": item.get("fields_returned"),
        "preview_keys": sorted(
            {str(key) for row in preview if isinstance(row, dict) for key in row.keys()}
        )[:40],
        "preview_blob": json.dumps(preview)[:4000],
    }


def test_phase1_dump_controlled_lifecycle(monkeypatch: pytest.MonkeyPatch) -> None:
    server = ControlledMcpServer(mode="full")
    server.start()
    captured: dict = {}
    try:
        _arm_mcp(monkeypatch, server)
        _arm_hil(monkeypatch)
        _discover(server)
        _stub_reasoners(monkeypatch, captured)

        first = _chat(LIFECYCLE_QUERY)
        first_payload = first.model_dump(mode="json")
        approval = first_payload.get("investigation_approval") or {}
        assert approval.get("status") in {"awaiting_approval", "edited_revalidated"}, approval

        second = _approve_investigation(first, LIFECYCLE_QUERY)
        payload = second.model_dump(mode="json")
        envelope = payload.get("approved_investigation_envelope") or {}
        evidence_plan = payload.get("evidence_plan") or {}
        resource_plan = evidence_plan.get("resource_plan") or {}
        source = [item for item in (payload.get("source_evidence") or []) if isinstance(item, dict)]
        collected = [
            item
            for item in source
            if item.get("collection_status") == "collected"
            and item.get("source_type") in {"splunk_mcp", "mcp_discovery"}
        ]
        outcome = payload.get("investigation_outcome") or {}
        run_status = payload.get("investigation_run_status") or {}
        sufficiency = payload.get("evidence_sufficiency") or {}
        evidence_state = payload.get("evidence_state") or {}
        context = payload.get("context_sufficiency") or {}
        gate = payload.get("final_evidence_gate") or {}
        rqc = payload.get("resolved_query_contract") or {}
        eligible = remediation_plan_eligible(payload)

        dump = {
            "query": LIFECYCLE_QUERY,
            "first_turn": {
                "investigation_approval_status": approval.get("status"),
                "validated_plan": approval.get("validated_plan")
                or first_payload.get("validated_investigation_plan"),
                "message_excerpt": (first_payload.get("message") or "")[:800],
            },
            "approved_envelope": {
                "objective": envelope.get("objective"),
                "entities": envelope.get("entities"),
                "time_scope": envelope.get("time_scope"),
                "approved_evidence_categories": envelope.get("approved_evidence_categories"),
                "allowed_read_only_capabilities": envelope.get("allowed_read_only_capabilities"),
                "source_index_scope": envelope.get("source_index_scope"),
                "envelope_version": envelope.get("envelope_version"),
            },
            "evidence_plan": {
                "answer_mode": evidence_plan.get("answer_mode"),
                "required_evidence_keys": evidence_plan.get("required_evidence_keys"),
                "missing_required_evidence": evidence_plan.get("missing_required_evidence"),
                "needs_rag": evidence_plan.get("needs_rag"),
                "needs_spl": evidence_plan.get("needs_spl"),
                "needs_mcp": evidence_plan.get("needs_mcp"),
                "mcp_allowed": evidence_plan.get("mcp_allowed"),
                "checklist": evidence_plan.get("checklist"),
            },
            "resource_plan_steps": [
                {
                    "id": step.get("step_id"),
                    "purpose": step.get("purpose"),
                    "status": step.get("status"),
                    "reason": step.get("status_reason"),
                    "resource": step.get("resource_id"),
                }
                for step in (resource_plan.get("steps") or [])
                if isinstance(step, dict)
            ],
            "read_execution": {
                "status": (payload.get("execution") or {}).get("status"),
                "block_reason": (payload.get("execution") or {}).get("block_reason"),
                "tool": (payload.get("execution") or {}).get("selected_tool"),
                "search_calls": server.search_calls,
            },
            "source_evidence": [_summarize_source(item) for item in source],
            "collected_environment": [_summarize_source(item) for item in collected],
            "plan_delta": {
                "status": (payload.get("plan_delta_decision") or {}).get("status"),
                "reason": (payload.get("plan_delta_decision") or {}).get("reason"),
                "prompt": captured.get("plan_delta_prompt"),
            },
            "resolved_query_contract": {
                "intent_family": rqc.get("intent_family"),
                "answer_goal": rqc.get("answer_goal"),
                "evidence_requirements": rqc.get("evidence_requirements"),
                "required_capabilities": rqc.get("required_capabilities"),
                "entities": rqc.get("entities"),
            },
            "context_sufficiency": context,
            "evidence_sufficiency": sufficiency,
            "evidence_state": {
                "required": evidence_state.get("required"),
                "obtained": evidence_state.get("obtained"),
                "missing": evidence_state.get("missing"),
                "blocked": evidence_state.get("blocked"),
                "diagnostic": evidence_state.get("diagnostic"),
            },
            "final_evidence_gate": {
                "collected_evidence_refs": gate.get("collected_evidence_refs"),
                "allow_live_result_language": gate.get("allow_live_result_language"),
                "allow_severity_assessment": gate.get("allow_severity_assessment"),
            },
            "investigation_run_status": run_status,
            "investigation_outcome": outcome,
            "severity_label": payload.get("severity") or payload.get("severity_label") or outcome.get("severity_label"),
            "remediation_plan_eligible": eligible,
            "remediation_approval": payload.get("remediation_approval"),
            "message_excerpt": (payload.get("message") or "")[:1200],
            "flags": {
                "outcome_v2": settings.ai_soc_investigation_outcome_v2_enabled,
                "remediation_planner": settings.ai_soc_remediation_planner_enabled,
            },
        }
        _DUMP_PATH.write_text(json.dumps(dump, default=str, indent=2))
        assert collected, "Phase 1 dump requires admitted environment SourceEvidence"
        assert server.search_calls >= 1
        assert _DUMP_PATH.exists()
    finally:
        server.stop()


def _eligibility_from_payload(payload: dict) -> tuple[bool, str]:
    execution = payload.get("execution") or {}
    human = payload.get("human_review") or {}
    return plan_delta_reasoning_eligible(
        {
            "approved_investigation_envelope": payload.get("approved_investigation_envelope"),
            "investigation_approval": payload.get("investigation_approval"),
            "investigation_run_status": payload.get("investigation_run_status"),
            "execution": execution if isinstance(execution, dict) else {},
            "human_review": human if isinstance(human, dict) else {},
            "source_evidence": payload.get("source_evidence") or [],
        }
    )


def _turn_row(
    *,
    turn: int,
    label: str,
    response,
    captured: dict,
    server,
    attempts_before: int,
) -> dict:
    payload = response.model_dump(mode="json")
    execution = payload.get("execution") or {}
    human = payload.get("human_review") or {}
    source = [item for item in (payload.get("source_evidence") or []) if isinstance(item, dict)]
    collected = [
        item
        for item in source
        if item.get("collection_status") == "collected"
        and item.get("source_type") in {"splunk_mcp", "mcp_discovery"}
    ]
    run_status = payload.get("investigation_run_status") or {}
    sufficiency = payload.get("evidence_sufficiency") or payload.get("context_sufficiency") or {}
    steps = ((payload.get("evidence_plan") or {}).get("resource_plan") or {}).get("steps") or []
    current_step = next(
        (
            str(step.get("status") or "")
            for step in steps
            if isinstance(step, dict)
            and str(step.get("status") or "") not in {"completed", "executed", "skipped"}
        ),
        str((steps[-1] or {}).get("status") if steps else execution.get("status") or ""),
    )
    attempts = list(captured.get("plan_delta_attempts") or [])
    attempted = len(attempts) > attempts_before
    eligible, reason = _eligibility_from_payload(payload)
    exec_status = str(execution.get("status") or "")
    return {
        "TURN": turn,
        "LABEL": label,
        "HIL_STATE": {
            "required": bool(human.get("required")),
            "review_type": human.get("review_type"),
            "reason": human.get("reason"),
            "approval_status": (payload.get("investigation_approval") or {}).get("status"),
        },
        "EXECUTION_REQUESTED": bool(payload.get("approved_investigation_envelope")),
        "EXECUTION_AUTHORIZED": exec_status in {"executed", "failed", "blocked", "denied"},
        "EXECUTION_PERFORMED": exec_status == "executed",
        "CURRENT_STEP_STATUS": current_step or exec_status,
        "EXECUTION_STATUS": exec_status,
        "SOURCE_EVIDENCE_COUNT": len(source),
        "ADMITTED_ENVIRONMENT_EVIDENCE_COUNT": len(collected),
        "SUFFICIENCY_STATUS": sufficiency.get("status") or run_status.get("status"),
        "MISSING_EVIDENCE": run_status.get("missing_evidence"),
        "PLANDELTA_ATTEMPTED": attempted,
        "PLANDELTA_ELIGIBLE": eligible,
        "PLANDELTA_REASON": attempts[-1].get("missing") if attempted and attempts else reason,
        "PLANDELTA_ELIGIBILITY_REASON": reason,
        "SEARCH_CALLS": server.search_calls,
        "OUTCOME": {
            "status": (payload.get("investigation_outcome") or {}).get("investigation_status"),
            "disposition": (payload.get("investigation_outcome") or {}).get("disposition"),
        },
    }


def test_phase1_turn_by_turn_plandelta_ordering(monkeypatch: pytest.MonkeyPatch) -> None:
    """Prove PlanDelta does not run on the HIL-waiting / pre-execution hop."""
    server = ControlledMcpServer(mode="full")
    server.start()
    captured: dict = {}
    rows: list[dict] = []
    try:
        _arm_mcp(monkeypatch, server)
        _arm_hil(monkeypatch)
        _discover(server)
        _stub_reasoners(monkeypatch, captured)

        first = _chat(LIFECYCLE_QUERY)
        rows.append(
            _turn_row(
                turn=1,
                label="plan_offered",
                response=first,
                captured=captured,
                server=server,
                attempts_before=0,
            )
        )

        approval = first.investigation_approval or {}
        awaiting = _chat(
            LIFECYCLE_QUERY,
            session_id=_session_id(first),
            investigation_review_action="run",
            investigation_handoff_id=str(approval["handoff_id"]),
            investigation_handoff_version=int(approval["handoff_version"]),
            source_profile_slots=dict(_SOURCE_PROFILE_SLOTS),
        )
        rows.append(
            _turn_row(
                turn=2,
                label="plan_approved_pre_confirm",
                response=awaiting,
                captured=captured,
                server=server,
                attempts_before=0,
            )
        )
        assert rows[-1]["EXECUTION_STATUS"] in {"requires_human_review", "awaiting_confirmation", "not_started", ""}
        assert rows[-1]["PLANDELTA_ATTEMPTED"] is False, rows[-1]
        assert rows[-1]["PLANDELTA_ELIGIBLE"] is False
        assert rows[-1]["PLANDELTA_ELIGIBILITY_REASON"] in {
            "awaiting_tool_confirmation",
            "current_read_not_terminal",
        }

        current = awaiting
        turn = 3
        while turn <= 8:
            execution = current.execution
            status = execution.status if execution is not None else None
            if status != "requires_human_review":
                break
            before = len(captured.get("plan_delta_attempts") or [])
            current = _confirm_execution_if_needed(current, LIFECYCLE_QUERY, max_rounds=1)
            rows.append(
                _turn_row(
                    turn=turn,
                    label="execution_confirm",
                    response=current,
                    captured=captured,
                    server=server,
                    attempts_before=before,
                )
            )
            turn += 1

        _TURN_DUMP_PATH.write_text(
            json.dumps({"turns": rows, "attempts": captured.get("plan_delta_attempts")}, default=str, indent=2)
        )
        hil_waiting = [row for row in rows if row["LABEL"] == "plan_approved_pre_confirm"]
        assert hil_waiting and hil_waiting[0]["PLANDELTA_ATTEMPTED"] is False
        post_exec = [row for row in rows if row["EXECUTION_PERFORMED"] or row["SEARCH_CALLS"] >= 1]
        assert post_exec, rows
        attempted = [row for row in rows if row["PLANDELTA_ATTEMPTED"]]
        if attempted:
            first_attempt = (captured.get("plan_delta_attempts") or [{}])[0]
            assert int(first_attempt.get("admitted_count") or 0) >= 1
        assert _TURN_DUMP_PATH.exists()
    finally:
        server.stop()
