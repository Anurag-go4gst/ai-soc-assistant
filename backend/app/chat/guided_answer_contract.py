"""AnswerContract surfacing for guided hybrid evidence (REV4 batch 2 P13b)."""

from __future__ import annotations

from typing import Any

from app.chat.contracts.answer_contract import AnswerContract, HilStatus
from app.chat.guided_hybrid_refinement import count_collected_guided_hops

_DISCOVERY_TOOL_PREFIX = "splunk_"
_SAFE_CATALOG_TOOL = "guided_safe_catalog"


def _hop_payload(hop: dict[str, Any]) -> dict[str, Any]:
    payload = hop.get("payload")
    return payload if isinstance(payload, dict) else {}


def _discovery_summary(hops: list[dict[str, Any]]) -> list[dict[str, Any]]:
    summary: list[dict[str, Any]] = []
    for hop in hops:
        if not isinstance(hop, dict):
            continue
        tool = str(hop.get("tool") or "")
        if tool == _SAFE_CATALOG_TOOL or tool == "splunk_run_query":
            continue
        if not tool.startswith(_DISCOVERY_TOOL_PREFIX):
            continue
        outcome = str(hop.get("outcome") or "planned")
        summary.append(
            {
                "tool": tool,
                "collection_status": outcome,
                "delivered": [str(item) for item in hop.get("delivered") or [] if item],
                "planned_only": outcome != "collected",
            }
        )
    return summary


def _safe_catalog_summary(hops: list[dict[str, Any]]) -> list[dict[str, Any]]:
    summary: list[dict[str, Any]] = []
    for hop in hops:
        if not isinstance(hop, dict):
            continue
        if str(hop.get("tool") or "") != _SAFE_CATALOG_TOOL:
            continue
        payload = _hop_payload(hop)
        outcome = str(hop.get("outcome") or "planned")
        summary.append(
            {
                "template_id": payload.get("template_id"),
                "collection_status": outcome,
                "provenance": payload.get("provenance") or "guided_safe_catalog",
                "read_only": True,
                "planned_only": outcome != "collected",
                "label": "safe catalog evidence collection under guided investigation controls",
            }
        )
    return summary


def _guided_collection_posture(
    *,
    evidence_plan: dict[str, Any] | None,
    evidence_planned: int,
    evidence_collected: int,
) -> dict[str, Any]:
    plan = evidence_plan or {}
    return {
        "mode": "guided_investigation",
        "mcp_allowed": False,
        "freeform_spl_execution_allowed": bool(plan.get("freeform_spl_execution_allowed")) is False,
        "safe_spl_execution_allowed": bool(plan.get("safe_spl_execution_allowed")),
        "discovery_allowed": bool(plan.get("discovery_allowed")),
        "spl_review_allowed": bool(plan.get("spl_review_allowed")),
        "safe_catalog_under_guided_controls": True,
        "remediation_performed": False,
        "evidence_planned": evidence_planned,
        "evidence_collected": evidence_collected,
        "posture_label": (
            "Planned discovery and safe-catalog hops run under guided investigation controls; "
            "no free-form SPL execution or remediation was performed."
        ),
    }


def enhance_answer_contract_for_guided_hybrid(
    contract: AnswerContract,
    *,
    guided_handoff: dict[str, Any] | None,
    mcp_evidence: list[dict[str, Any]] | None,
    evidence_plan: dict[str, Any] | None,
) -> AnswerContract:
    """Surface guided discovery/catalog evidence without widening SPL execution eligibility."""
    if not isinstance(guided_handoff, dict) or not guided_handoff:
        return contract

    hops = [hop for hop in (mcp_evidence or []) if isinstance(hop, dict)]
    evidence_planned = int(guided_handoff.get("evidence_planned") or 0)
    evidence_collected = count_collected_guided_hops(hops)
    blocked_resources = [
        item for item in guided_handoff.get("blocked_resources") or [] if isinstance(item, dict)
    ]
    discovery_summary = _discovery_summary(hops)
    safe_catalog_summary = _safe_catalog_summary(hops)
    posture = _guided_collection_posture(
        evidence_plan=evidence_plan,
        evidence_planned=evidence_planned,
        evidence_collected=evidence_collected,
    )

    hil_status: HilStatus = contract.hil_status
    if hil_status == "not_required":
        hil_status = "required"

    render = dict(contract.render_sections)
    if discovery_summary or safe_catalog_summary or evidence_planned:
        render["guided_evidence"] = True

    return contract.model_copy(
        update={
            "guided_collection_posture": posture,
            "discovery_evidence_summary": discovery_summary,
            "safe_catalog_evidence_summary": safe_catalog_summary,
            "evidence_planned": evidence_planned,
            "evidence_collected": evidence_collected,
            "blocked_resources": blocked_resources,
            "human_review_required": True,
            "hil_status": hil_status,
            "render_sections": render,
        }
    )
