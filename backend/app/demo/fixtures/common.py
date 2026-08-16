"""Shared Experience Center flagship envelope helpers. /demo only."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from app.demo.ec_response import (
    EcFollowUpChip,
    EcProjection,
    EcProjectionView,
    EcProvenanceStamp,
    EcSessionState,
    ExperienceCenterResponse,
)


def chip(follow_up_id: str, label: str, *, action: bool = False) -> EcFollowUpChip:
    return EcFollowUpChip(
        follow_up_id=follow_up_id,
        label=label,
        advances_state=True,
        group="action" if action else "continue",
        leads_to_action=action,
    )


def actions_for(session_id: str, scenario_id: str):
    from app.demo import ec_actions

    return list(ec_actions.list_actions_for_session(session_id, scenario_id))


def ensure_hil_action(
    *,
    kind: str,
    label: str,
    session_id: str,
    scenario_id: str,
    extra: dict[str, Any] | None = None,
):
    from app.demo import ec_actions

    existing = [
        item
        for item in actions_for(session_id, scenario_id)
        if item.kind == kind and item.label == label
    ]
    if existing:
        return existing[-1]
    return ec_actions.prepare_action(
        kind=kind,
        label=label,
        session_id=session_id,
        scenario_id=scenario_id,
        extra=extra,
    )


def ensure_executed_action(
    *,
    kind: str,
    label: str,
    session_id: str,
    scenario_id: str,
    extra: dict[str, Any] | None = None,
):
    from app.demo import ec_actions

    existing = [
        item
        for item in actions_for(session_id, scenario_id)
        if item.kind == kind and item.label == label and item.state in {"EXECUTED", "VERIFIED"}
    ]
    if existing:
        return existing[-1]
    prepared = ensure_hil_action(
        kind=kind,
        label=label,
        session_id=session_id,
        scenario_id=scenario_id,
        extra=extra,
    )
    if prepared.state == "APPROVAL_REQUIRED":
        prepared = ec_actions.approve_action(prepared.action_id)
    if prepared.state != "EXECUTED":
        return ec_actions.execute_action(prepared.action_id)
    return prepared


def evidence(
    evidence_id: str,
    source_type: str,
    source_name: str,
    rows: list[dict[str, Any]],
    *,
    provenance: str = "experience_center_fixture",
    tool_name: str | None = None,
    summary: str | None = None,
) -> dict[str, Any]:
    return {
        "evidence_id": evidence_id,
        "source_type": source_type,
        "source_name": source_name,
        "tool_name": tool_name,
        "collection_status": "collected",
        "query_or_request_summary": summary,
        "result_count": len(rows),
        "preview_rows": rows,
        "fields_returned": sorted({key for row in rows for key in row}) if rows else [],
        "warnings": ["coe_synthetic_fixture", "no_live_customer_data"],
        "provenance": provenance,
        "raw_result_stored": False,
        "output_type": "fixture_preview",
    }


def state_item(item_id: str, label: str, status: str, detail: str, provenance: str = "experience_center_fixture") -> dict[str, Any]:
    return {"id": item_id, "label": label, "status": status, "detail": detail, "provenance": provenance}


def set_status(items: list[dict[str, Any]], item_id: str, status: str, detail: str, provenance: str | None = None) -> None:
    for item in items:
        if item["id"] == item_id:
            item["status"] = status
            item["detail"] = detail
            if provenance is not None:
                item["provenance"] = provenance
            return
    items.append(state_item(item_id, item_id, status, detail, provenance or "experience_center_fixture"))


def projection(
    *,
    scenario_id: str,
    understanding: str,
    resources: list[str],
    controls: list[str],
    evidence_state: list[dict[str, Any]],
    outcome: dict[str, Any],
    control_kind: str = "ec_scenario_policy",
) -> EcProjection:
    fixture = EcProvenanceStamp(kind="experience_center_fixture", detail=scenario_id)
    return EcProjection(
        understanding=EcProjectionView(
            title="Understanding",
            summary=understanding,
            items=["route_source=ec_fixture_selected"],
            provenance=EcProvenanceStamp(kind="ec_fixture_selected", detail=scenario_id),
        ),
        resource_plan=EcProjectionView(
            title="Resources",
            summary="Fixture resources selected for this investigation. No ResourcePlan graph execution.",
            items=resources,
            provenance=fixture,
        ),
        phase_contract=EcProjectionView(
            title="Controls",
            summary="Experience Center projects controls; production PhaseContract is unused.",
            items=controls,
            provenance=EcProvenanceStamp(kind=control_kind, detail=scenario_id),
        ),
        evidence_state=EcProjectionView(
            title="Evidence obtained",
            summary="Evidence packaged from fixture and simulated connectors.",
            items=[f"{item['label']} → {item['status']}" for item in evidence_state],
            provenance=fixture,
        ),
        investigation_outcome=EcProjectionView(
            title="InvestigationOutcome",
            summary=f"Disposition {outcome.get('disposition')}. Production InvestigationOutcome unused.",
            items=[
                "production InvestigationOutcome field unused",
                *[f"confirmed: {item}" for item in outcome.get("confirmed") or []],
                *[f"unconfirmed: {item}" for item in outcome.get("unconfirmed") or []],
            ],
            provenance=fixture,
        ),
        provenance=fixture,
    )


def envelope(
    *,
    scenario_id: str,
    family: str,
    session_id: str,
    turn: int,
    applied: list[str],
    chips: list[EcFollowUpChip],
    assessment: str,
    title: str,
    found: str,
    outcome: dict[str, Any],
    evidence_state: list[dict[str, Any]],
    source_evidence: list[dict[str, Any]],
    actions: list[Any],
    resources: list[str],
    controls: list[str],
    extra: dict[str, Any] | None = None,
    awaiting_external: bool = False,
    pending_action_id: str | None = None,
    understanding: str | None = None,
    layer2_path: list[str] | None = None,
    recommended: list[str] | None = None,
    important: list[str] | None = None,
    systems: list[dict[str, Any]] | None = None,
    table: list[dict[str, Any]] | None = None,
    severity: str = "P2 High",
) -> ExperienceCenterResponse:
    remaining = [chip for chip in chips if chip.follow_up_id not in applied]
    pending = pending_action_id
    if not pending:
        prepared = next((item for item in actions if getattr(item, "state", "") in {"PREPARED", "APPROVAL_REQUIRED"}), None)
        pending = prepared.action_id if prepared else None
    analyst = {
        "finding_title": title,
        "severity_label": severity,
        "assessment": assessment,
        "direct_answer_summary": assessment,
        "one_sentence_finding": found,
        "what_we_found": found,
        "important_evidence": important or list(outcome.get("confirmed") or [])[:4],
        "unconfirmed_findings": list(outcome.get("unconfirmed") or []),
        "recommended_actions": recommended or [],
        "affected_systems": systems or [],
        "splunk_results_table": table or systems or [],
        "missing_evidence": list(outcome.get("missing_evidence") or []),
        "unsupported_claims_avoid": list(outcome.get("unconfirmed") or []),
    }
    payload = {
        "scenario_id": scenario_id,
        "trace_id": f"demo-{scenario_id}-{uuid4().hex[:8]}",
        "message": assessment,
        "note": "Experience Center fixture investigation.",
        "demo_mode": True,
        "analyst_summary": assessment,
        "analyst": analyst,
        "analyst_response": analyst,
        "selected_skill": "guided_investigation",
        "route_source": "ec_fixture_selected",
        "candidate_spl": None,
        "spl_validation": None,
        "execution": {
            "status": "simulated_receipts_packaged",
            "production_mcp_executed": False,
            "executed_spl": None,
            "block_reason": "live_mcp_not_called",
        },
        "human_review": {
            "required": True,
            "review_type": "analyst_review",
            "reason": "experience_center_hil",
            "reviewer_role": "analyst",
            "allowed_actions": ["continue_investigation"],
            "safe_message_for_user": "Simulated investigation. No production change.",
        },
        "source_evidence": source_evidence,
        "ec_projection": projection(
            scenario_id=scenario_id,
            understanding=understanding or found,
            resources=resources,
            controls=controls,
            evidence_state=evidence_state,
            outcome=outcome,
        ).model_dump(),
        "ec_actions": [item.model_dump() if hasattr(item, "model_dump") else item for item in actions],
        "ec_followups": [item.model_dump() for item in remaining],
        "ec_session_state": EcSessionState(
            session_id=session_id,
            family=family,
            scenario_id=scenario_id,
            turn=turn,
            pending_action_id=pending,
            awaiting_external=awaiting_external,
            applied_follow_up_ids=applied,
        ).model_dump(),
        "ec_provenance": {
            "envelope": "experience_center_response",
            "route_source": "ec_fixture_selected",
            "live_llm_called": False,
            "live_mcp_called": False,
            "live_rag_called": False,
        },
        "ec_investigation_outcome": outcome,
        "ec_evidence_state": evidence_state,
        "ec_affected_systems": systems or [],
        "ec_layer2_path": layer2_path
        or [
            "Understanding",
            "Evidence required",
            "Resources/tools",
            "Controls",
            "Evidence obtained",
            "InvestigationOutcome",
        ],
        "production_side_effect": False,
    }
    payload.update(extra or {})
    return ExperienceCenterResponse.model_validate(payload)


def demo_scenario(
    *,
    scenario_id: str,
    label: str,
    query: str,
    demo_order: int,
    family: str,
    summary: str,
    expected_skill: str = "guided_investigation",
    selected_use_case_id: str | None = None,
    candidate_spl: str | None = None,
    source_evidence: list[dict[str, Any]] | None = None,
):
    from app.demo.scenarios import DemoScenario

    return DemoScenario(
        scenario_id=scenario_id,
        label=label,
        category="Flagship",
        query=query,
        display_query=query,
        demo_order=demo_order,
        picker_tier="leadership",
        incident_family=family,
        fsm_family=family,
        environment_mode="connected_coe_demo",
        expected_skill=expected_skill,
        expected_sources=["mcp:splunk"],
        expected_sufficiency_mode="partial_answer",
        mcp_execution_mode="disabled",
        saia_available=True,
        rag_available=False,
        selected_use_case_id=selected_use_case_id,
        candidate_spl=candidate_spl,
        aliases=(),
        analyst_summary=summary,
        trace_explanation=["Experience Center flagship fixture.", "No live MCP/LLM/RAG."],
        source_evidence=source_evidence or [],
    )
