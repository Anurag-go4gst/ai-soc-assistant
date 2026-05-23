from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.connectors.telemetry import get_telemetry_connector
from app.routing.skills import validate_skill

EXECUTION_STATUS = "not_started"


def _step(name: str, required_connectors: list[str], safety_gates: list[str]) -> dict[str, Any]:
    return {
        "order": 0,
        "name": name,
        "status": EXECUTION_STATUS,
        "required_connectors": required_connectors,
        "safety_gates": safety_gates,
    }


_WORKFLOW_BLUEPRINTS: dict[str, list[dict[str, Any]]] = {
    "alert_summary": [
        _step("retrieve related alerts", ["mcp"], ["validated_metadata_request_only", "minimize_alert_fields"]),
        _step("retrieve approved SOP/RAG context", ["rag"], ["approved_chunks_only", "no_full_document_payloads"]),
        _step("generate timeline", [], ["evidence_link_required"]),
        _step("map to MITRE", [], ["approved_mapping_taxonomy"]),
        _step("synthesize analyst summary", ["llm"], ["grounded_evidence_only", "insufficient_evidence_allowed"]),
    ],
    "attack_discovery": [
        _step("generate candidate SPL", ["llm"], ["spl_generation_not_enabled"]),
        _step("validate SPL", [], ["read_only_spl", "time_range_required", "aggregation_required"]),
        _step("execute validated SPL through MCP", ["mcp"], ["validated_spl_only_to_mcp", "execution_not_enabled"]),
        _step("minimize results", [], ["bounded_results_only", "no_raw_event_dump"]),
        _step("map to MITRE", [], ["approved_mapping_taxonomy"]),
        _step("synthesize findings", ["llm"], ["grounded_evidence_only", "insufficient_evidence_allowed"]),
    ],
    "spl_generation": [
        _step("retrieve SPL examples/policy", ["rag"], ["approved_chunks_only"]),
        _step("generate candidate SPL", ["llm"], ["spl_generation_not_enabled"]),
        _step("validate SPL", [], ["read_only_spl", "time_range_required", "blocked_commands_enforced"]),
        _step("return validated SPL for analyst review", [], ["human_review_required", "no_execution"]),
    ],
    "knowledge_recall": [
        _step("retrieve approved documents", ["rag"], ["approved_chunks_only"]),
        _step("rank chunks", [], ["source_metadata_required"]),
        _step("synthesize grounded answer", ["llm"], ["grounded_evidence_only", "insufficient_evidence_allowed"]),
    ],
}


def plan_workflow(
    selected_skill: str,
    tool_plan: list[str],
    query: str,
    trace_id: str,
    telemetry: Any | None = None,
) -> dict[str, Any]:
    skill = validate_skill(selected_skill)
    steps = deepcopy(_WORKFLOW_BLUEPRINTS[skill])
    required_connectors = sorted({connector for step in steps for connector in step["required_connectors"]})
    safety_gates = sorted({gate for step in steps for gate in step["safety_gates"]})

    workflow_plan = {
        "trace_id": trace_id,
        "skill": skill,
        "tool_plan": list(tool_plan),
        "status": EXECUTION_STATUS,
        "execution_enabled": False,
        "steps": steps,
        "required_connectors": required_connectors,
        "safety_gates": safety_gates,
        "message": "Workflow plan created. No SPL/MCP/RAG execution has started.",
    }

    (telemetry or get_telemetry_connector()).record_step(
        trace_id,
        "workflow_plan_created",
        EXECUTION_STATUS,
        skill=skill,
        tool_plan=list(tool_plan),
        required_connectors=required_connectors,
        safety_gates=safety_gates,
        step_count=len(steps),
        query_preview=query[:160],
        execution_enabled=False,
    )
    return workflow_plan


for _steps in _WORKFLOW_BLUEPRINTS.values():
    for _index, _workflow_step in enumerate(_steps, start=1):
        _workflow_step["order"] = _index
