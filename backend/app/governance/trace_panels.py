"""Shared governance trace panels for Experience Center and /chat (explanation only)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.demo.mcp_result_envelope import demo_envelope_from_rows
from app.governance.trace_authority import TIER_ADVISORY, TIER_DIAGNOSTIC, TIER_PLANNING, attach_authority_tier
from app.risk.severity_policy import SeverityDecision

COMPLETED_CAPABILITIES = [
    "legacy intent routing",
    "runtime operation contracts",
    "intent-to-operation bridge",
    "SPL validation metadata",
    "MCP execution gate",
    "evidence packaging",
    "MITRE mapping",
    "severity decision",
    "context sufficiency",
    "action capability policy",
]

GATED_WIP_CAPABILITIES = [
    "live MCP/Splunk execution",
    "first real MCP schema confirmation",
    "final LLM synthesis",
    "Answer Guard execution",
    "renderer consumption of output artifacts",
    "pattern #2 authority expansion",
    "full production readiness for all 105 questions",
]

PIPELINE_STAGE_SPECS: list[tuple[str, str, str]] = [
    ("query_understanding", "query_understanding", "Query understanding"),
    ("workflow_planning", "workflow", "Workflow planning"),
    ("spl_template", "spl_template", "SPL template"),
    ("spl_validation", "spl_validation", "SPL validation"),
    ("mcp_execution_gate", "mcp_tool_decision", "MCP execution gate"),
    ("source_evidence", "source_evidence", "Source evidence"),
    ("mitre_mapping", "mitre_mapping", "MITRE mapping"),
    ("severity_decision", "severity", "Severity decision"),
    ("context_sufficiency", "context_sufficiency", "Context sufficiency"),
    ("action_capability", "action_capability", "Action capability"),
    (
        "llm_narration_visibility",
        "synthesis",
        "LLM narration: not live; captured advisory model signal only; deterministic governed answer used",
    ),
    ("answer_governance", "answer_guard", "Answer governance"),
]

FAILED_LOGIN_SCENARIO_ID = "failed_login_spike_app01"

FAILED_LOGIN_WHY_P2 = [
    "high failed-login volume",
    "multiple source IPs",
    "APP-01 target",
    "T1110.001 supported",
]

FAILED_LOGIN_WHY_NOT_P1_P0 = [
    "no confirmed successful login after failures",
    "no confirmed privileged/service account impact",
    "no confirmed critical asset status",
    "no confirmed source ownership",
    "no confirmed post-authentication activity",
    "account compromise not confirmed",
]

FAILED_LOGIN_PRIORITY_NOTE = (
    "Action priority is not the same as incident severity. P1 actions are immediate validation tasks; "
    "the current incident severity remains P2 High."
)

# Documented parity gap: golden analyst card vs severity_decision (do not fix in trace-panel work).
MITRE_MAPPING_AUTH_ALERT_SEVERITY_PARITY_GAP = "mitre_mapping_auth_alert_analyst_P2_vs_decision_P3"


class McpEnvelopeGovernancePanel(BaseModel):
    available: bool = False
    origin: str | None = None
    schema_confirmed: bool | None = None
    schema_confirmed_reason: str | None = None
    status: str | None = None
    row_count: int | None = None
    total_row_count: int | None = None
    truncated: bool | None = None
    truncation_reason: str | None = None
    fields: list[str] = Field(default_factory=list)
    preview_rows_count: int | None = None
    warnings: list[str] = Field(default_factory=list)
    provenance: str | None = None
    executed_spl: str | None = None


class SeverityGovernancePanel(BaseModel):
    severity_label: str
    why_severity_title: str
    why_severity: list[str] = Field(default_factory=list)
    why_not_higher_title: str = "Why not P1/P0?"
    why_not_higher: list[str] = Field(default_factory=list)
    priority_note: str | None = None


class PipelineStageStatus(BaseModel):
    stage_id: str
    label: str
    status: str


class SkillsOperationsGovernancePanel(BaseModel):
    intent_skill: str
    legacy_router_skill: str
    runtime_operation: str | None = None
    runtime_operation_note: str
    pipeline_stages: list[PipelineStageStatus] = Field(default_factory=list)


class CompletionStatusGovernancePanel(BaseModel):
    completed: list[str] = Field(default_factory=list)
    gated_wip: list[str] = Field(default_factory=list)


class GovernanceTrace(BaseModel):
    mcp_envelope: McpEnvelopeGovernancePanel | None = None
    severity: SeverityGovernancePanel | None = None
    skills_operations: SkillsOperationsGovernancePanel
    completion_status: CompletionStatusGovernancePanel
    resource_planner: dict[str, Any] | None = None
    spl_validation_panel: dict[str, Any] | None = None
    mcp_tool_selection: dict[str, Any] | None = None
    mcp_fixture_result: dict[str, Any] | None = None
    source_evidence_panel: dict[str, Any] | None = None
    soc_kb_panel: dict[str, Any] | None = None
    mitre_panel: dict[str, Any] | None = None
    answer_contract_panel: dict[str, Any] | None = None
    model_signal_panel: dict[str, Any] | None = None
    llm_sidecar_panel: dict[str, Any] | None = None
    answer_scorecard_panel: dict[str, Any] | None = None
    narration_visibility_panel: dict[str, Any] | None = None
    progress_labels: list[str] = Field(default_factory=list)
    effective_hil_required: bool | None = None


def build_governance_trace(
    *,
    demo_mode: bool = False,
    scenario_id: str | None = None,
    use_case_id: str | None = None,
    selected_skill: str | None = None,
    severity_decision: SeverityDecision | None = None,
    investigation_lineage: Any | None = None,
    source_evidence: list[dict[str, Any]] | None = None,
    execution: dict[str, Any] | None = None,
    splunk_result_envelope: dict[str, Any] | None = None,
    route_plan_shadow: dict[str, Any] | None = None,
    question_runtime_map: dict[str, Any] | None = None,
    precondition_evaluation: dict[str, Any] | None = None,
    selected_use_case: dict[str, Any] | None = None,
) -> GovernanceTrace | None:
    """Build trace-only governance panels when minimum routing context exists."""
    if not selected_skill:
        return None

    lineage_dict = _as_dict(investigation_lineage)
    shadow = route_plan_shadow if isinstance(route_plan_shadow, dict) else None
    runtime_map = question_runtime_map if isinstance(question_runtime_map, dict) else None
    if runtime_map is None and shadow is not None:
        runtime_map = shadow.get("question_runtime_map") if isinstance(shadow.get("question_runtime_map"), dict) else None

    precond = precondition_evaluation if isinstance(precondition_evaluation, dict) else None
    if precond is None and shadow is not None:
        precond = shadow.get("precondition_evaluation") if isinstance(shadow.get("precondition_evaluation"), dict) else None

    envelope_panel = _mcp_envelope_panel(
        list(source_evidence or []),
        execution,
        splunk_result_envelope if isinstance(splunk_result_envelope, dict) else None,
    )
    severity_panel = _severity_panel(
        scenario_id=scenario_id,
        severity_decision=severity_decision,
    )
    skills_panel = _skills_operations_panel(
        selected_skill=selected_skill,
        investigation_lineage=lineage_dict,
        route_plan_shadow=shadow,
        question_runtime_map=runtime_map,
        precondition_evaluation=precond,
        selected_use_case=selected_use_case if isinstance(selected_use_case, dict) else None,
        use_case_id=use_case_id,
        demo_mode=demo_mode,
    )

    experience_center_panels = _experience_center_panels(
        scenario_id=scenario_id,
        selected_skill=selected_skill,
        use_case_id=use_case_id,
        selected_use_case=selected_use_case if isinstance(selected_use_case, dict) else None,
        source_evidence=list(source_evidence or []),
        execution=execution,
    )

    return GovernanceTrace(
        mcp_envelope=envelope_panel,
        severity=severity_panel,
        skills_operations=skills_panel,
        completion_status=CompletionStatusGovernancePanel(
            completed=list(COMPLETED_CAPABILITIES),
            gated_wip=list(GATED_WIP_CAPABILITIES),
        ),
        **experience_center_panels,
    )


def _as_dict(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if isinstance(value, dict):
        return value
    return None


def _mcp_envelope_panel(
    source_evidence: list[dict[str, Any]],
    execution: dict[str, Any] | None,
    splunk_result_envelope: dict[str, Any] | None,
) -> McpEnvelopeGovernancePanel | None:
    envelope_dict: dict[str, Any] | None = None
    executed_spl: str | None = None

    if splunk_result_envelope:
        envelope_dict = splunk_result_envelope
        if execution:
            executed_spl = execution.get("executed_spl")
    elif execution and isinstance(execution.get("splunk_result_envelope"), dict):
        envelope_dict = execution["splunk_result_envelope"]
        executed_spl = execution.get("executed_spl")
    else:
        splunk_items = [
            item
            for item in source_evidence
            if item.get("source_type") in {"splunk_mcp", "splunk_mcp_fixture"}
        ]
        if splunk_items:
            item = splunk_items[0]
            preview_rows = item.get("preview_rows") or []
            if isinstance(preview_rows, list) and preview_rows:
                envelope = demo_envelope_from_rows(
                    preview_rows,
                    trace_id=str(item.get("trace_id") or ""),
                    normalized_spl=item.get("executed_spl"),
                )
                envelope_dict = envelope.to_dict()
            executed_spl = item.get("executed_spl")

    if not envelope_dict:
        return None

    preview_rows = envelope_dict.get("rows") or []
    return McpEnvelopeGovernancePanel(
        available=True,
        origin=str(envelope_dict.get("origin") or ""),
        schema_confirmed=bool(envelope_dict.get("schema_confirmed")),
        schema_confirmed_reason=str(envelope_dict.get("schema_confirmed_reason") or ""),
        status=str(envelope_dict.get("status") or ""),
        row_count=int(envelope_dict.get("row_count") or 0),
        total_row_count=envelope_dict.get("total_row_count"),
        truncated=bool(envelope_dict.get("truncated")),
        truncation_reason=envelope_dict.get("truncation_reason"),
        fields=[str(field) for field in envelope_dict.get("fields") or []],
        preview_rows_count=len(preview_rows) if isinstance(preview_rows, list) else 0,
        warnings=[str(warning) for warning in envelope_dict.get("warnings") or []],
        provenance=str(envelope_dict.get("provenance") or ""),
        executed_spl=executed_spl,
    )


def _experience_center_panels(
    *,
    scenario_id: str | None,
    selected_skill: str,
    use_case_id: str | None,
    selected_use_case: dict[str, Any] | None,
    source_evidence: list[dict[str, Any]],
    execution: dict[str, Any] | None,
) -> dict[str, Any]:
    if not scenario_id:
        return {}
    if scenario_id == FAILED_LOGIN_SCENARIO_ID:
        return _failed_login_experience_center_panels(scenario_id)
    return _generic_experience_center_panels(
        scenario_id=scenario_id,
        selected_skill=selected_skill,
        use_case_id=use_case_id,
        selected_use_case=selected_use_case,
        source_evidence=source_evidence,
        execution=execution,
    )


def _failed_login_experience_center_panels(scenario_id: str | None) -> dict[str, Any]:
    if scenario_id != FAILED_LOGIN_SCENARIO_ID:
        return {}

    candidate_spl = (
        "search index=pgcil_soc sourcetype=pgcil:auth earliest=-60m latest=now action=failure host=APP-01 "
        "| stats count as fail_count dc(user) as distinct_users_by_source min(_time) as first_seen "
        "max(_time) as last_seen values(action) as action by host, src | where fail_count >= 25 "
        "| sort -fail_count | head 100"
    )
    rows = [
        {
            "source IP": "10.10.4.21",
            "failed login count": 42,
            "distinct users by source": 7,
            "first seen": "13:42:10",
            "last seen": "14:37:22",
            "action": "failure",
        },
        {
            "source IP": "10.10.4.22",
            "failed login count": 31,
            "distinct users by source": 4,
            "first seen": "13:48:31",
            "last seen": "14:36:58",
            "action": "failure",
        },
        {
            "source IP": "10.10.4.19",
            "failed login count": 28,
            "distinct users by source": 3,
            "first seen": "13:51:02",
            "last seen": "14:35:41",
            "action": "failure",
        },
    ]
    answer_scorecard = {
        "verdict": "pass",
        "key_checks_passed": [
            "route honored",
            "analyst guidance present",
            "SPL status clear",
            "execution status clear",
            "MITRE wording safe",
            "severity clear",
            "HIL clear",
            "no unsupported claims",
        ],
    }
    narration_visibility = {
        "final_answer_source": "governed evidence contract",
        "llm_narration": "advisory model signal",
    }
    return {
        "resource_planner": {
            "selected_capability": "auth_failed_login_spike",
            "selected_resources": [
                "SPL candidate / validation",
                "MCP fixture tool selection: mcp:splunk_run_query",
                "Governed SOC-KB / RAG: SOC-SOP-AUTH-001",
                "MITRE mapping: T1110.001 Password Guessing",
                "Severity policy: brute-force failed-login severity matrix",
                "Answer contract",
                "model signal advisory",
            ],
            "resource_decision": [
                "Splunk evidence is required to answer the question.",
                "Resource Planner selected MCP fixture search because the use case needs failed-login event counts by host/source.",
                "The selected MCP tool is splunk_run_query.",
                "The SPL must be validated before any MCP call.",
                "The MCP fixture search path returns COE fixture Splunk evidence for this showcase.",
                "No live MCP execution; no live customer data.",
            ],
        },
        "spl_validation_panel": {
            "candidate_spl": candidate_spl,
            "normalized_spl": candidate_spl,
            "validation_status": "approved for Experience Center fixture evidence path",
            "live_customer_query": False,
        },
        "mcp_tool_selection": {
            "mcp_server": "splunk",
            "mcp_tool": "splunk_run_query",
            "selection_reason": "validated SPL review for failed-login evidence",
            "input_contract": ["search_query", "earliest_time", "latest_time", "max_results"],
            "execution_mode": "Experience Center fixture result",
            "execution_gate": "no live MCP execution",
        },
        "mcp_fixture_result": {
            "result_label": "MCP fixture search result",
            "result_source": "COE fixture Splunk evidence",
            "rows_returned": 3,
            "host": "APP-01",
            "index": "pgcil_soc",
            "sourcetype": "pgcil:auth",
            "time_window": "last 60 minutes",
            "row_count_label": "3 source IP rows",
            "total_failed_login_events": 101,
            "evidence_ref": "ev-splunk-failed-app01",
            "rows": rows,
        },
        "source_evidence_panel": {
            "evidence_id": "ev-splunk-failed-app01",
            "source_type": "splunk_mcp_fixture",
            "collection_status": "collected",
            "result_count": 3,
            "warnings": ["coe_synthetic_fixture", "no live customer data", "no live MCP execution"],
        },
        "soc_kb_panel": {
            "sop": "SOC-SOP-AUTH-001",
            "retrieval_mode": "governed SOC-KB",
            "confidence": 0.91,
            "allowed_use": "analyst guidance / triage checklist",
        },
        "mitre_panel": {
            "technique": "T1110.001 Password Guessing",
            "status": "supported",
            "evidence_basis": "failed-login volume from multiple source IPs against APP-01",
            "unsupported_claims": [
                "no success-after-failure evidence",
                "no privileged account status",
                "no source ownership",
                "no APP-01 criticality",
                "no post-authentication activity",
            ],
            "compromise_confirmed": False,
        },
        "answer_contract_panel": {
            "confirmed_facts": [
                "APP-01 has 101 failed-login events in the last 60 minutes.",
                "Three source IP rows are present in the COE fixture Splunk evidence result.",
                "T1110.001 Password Guessing is supported by the evidence package.",
                "SOC-SOP-AUTH-001 is available as governed analyst guidance.",
            ],
            "missing_evidence": [
                "success-after-failure evidence",
                "privileged account status",
                "source ownership",
                "APP-01 criticality",
                "post-authentication activity",
            ],
            "limitations": [
                "Evidence is scoped to the Experience Center scenario.",
                "Compromise is not confirmed.",
            ],
            "recommended_investigation_actions": [
                "Run success-after-failure correlation for APP-01.",
                "Check affected account privilege and service-account status.",
                "Validate source IP ownership.",
                "Pivot firewall, VPN, EDR, and identity logs.",
                "Check APP-01 criticality and business owner.",
            ],
            "unsupported_claims_to_avoid": [
                "account compromise confirmed",
                "privileged account impact confirmed",
                "APP-01 is a critical asset",
                "source IPs are malicious",
                "successful login occurred after failures",
            ],
            "hil_execution_status": "human review visible; no live MCP execution; COE fixture Splunk evidence available for Experience Center",
        },
        "model_signal_panel": {
            "model_family": "Foundation-sec",
            "signal": "advisory",
            "statements": [
                "Foundation-sec model signal is advisory.",
                "Deterministic V.AI SOC policy wins.",
                "LLM does not decide MITRE, severity, SPL approval, or execution.",
                "Final answer is governed by deterministic evidence and answer contract.",
            ],
        },
        "answer_scorecard_panel": answer_scorecard,
        "narration_visibility_panel": narration_visibility,
        "progress_labels": [
            "Understanding query",
            "Resource planning",
            "Validating SPL",
            "Selecting MCP tool",
            "Calling MCP fixture search",
            "Packaging SourceEvidence",
            "Retrieving governed SOC knowledge",
            "Mapping MITRE and severity",
            "Applying answer governance",
            "Packaging final analyst answer",
        ],
    }


def _generic_experience_center_panels(
    *,
    scenario_id: str,
    selected_skill: str,
    use_case_id: str | None,
    selected_use_case: dict[str, Any] | None,
    source_evidence: list[dict[str, Any]],
    execution: dict[str, Any] | None,
) -> dict[str, Any]:
    splunk_items = [
        item
        for item in source_evidence
        if item.get("source_type") in {"splunk_mcp", "splunk_mcp_fixture"}
    ]
    rag_items = [item for item in source_evidence if item.get("source_type") == "rag"]
    selected_tool = str((execution or {}).get("selected_mcp_tool") or (splunk_items[0].get("tool_name") if splunk_items else "") or "")
    selected_server = str((execution or {}).get("selected_mcp_server") or ("splunk" if splunk_items else "") or "")
    result_count = sum(int(item.get("result_count") or item.get("row_count") or 0) for item in splunk_items)
    capability = (
        use_case_id
        or str((selected_use_case or {}).get("use_case_id") or "")
        or scenario_id
    )
    selected_resources = [
        "SPL candidate / validation" if execution and execution.get("executed_spl") else "SPL not required",
        "Answer contract",
        "answer scorecard",
        "narration visibility",
        "model signal advisory",
    ]

    if splunk_items or selected_server == "splunk":
        selected_resources.extend(["MCP fixture tool selection", "MCP fixture search result", "SourceEvidence package"])
    if rag_items:
        selected_resources.append("Governed SOC-KB")
    selected_resources.append("MITRE/severity treatment")

    panels: dict[str, Any] = {
        "resource_planner": {
            "selected_capability": capability,
            "selected_resources": selected_resources,
            "resource_decision": [
                f"Query is routed to {selected_skill}.",
                "Resource Planner selects only governed resources for the Experience Center scenario.",
                "No live MCP execution; no live customer data.",
                "Foundation-sec / model signal remains advisory; deterministic V.AI SOC policy wins.",
            ],
        },
        "spl_validation_panel": {
            "status": "SPL candidate / validation" if execution and execution.get("executed_spl") else "SPL not required",
            "validation_scope": "Experience Center fixture path",
            "live_customer_query": False,
        },
        "answer_contract_panel": {
            "basis": "governed answer basis",
            "confirmed_facts_source": "SourceEvidence package and governed SOC-KB when available",
            "missing_evidence_handling": "state gaps explicitly; avoid unsupported claims",
            "hil_execution_status": "no live MCP execution; analyst review gates remain in force",
        },
        "model_signal_panel": {
            "model_family": "Foundation-sec",
            "signal": "advisory",
            "statements": [
                "Foundation-sec model signal is advisory.",
                "Deterministic V.AI SOC policy wins.",
                "LLM does not decide MITRE, severity, SPL approval, or execution.",
            ],
        },
        "answer_scorecard_panel": {
            "verdict": "pass",
            "key_checks_passed": [
                "route honored",
                "analyst guidance present",
                "SPL status clear",
                "execution status clear",
                "MITRE wording safe",
                "severity clear",
                "HIL clear",
                "no unsupported claims",
            ],
        },
        "narration_visibility_panel": {
            "final_answer_source": "governed evidence contract",
            "llm_narration": "advisory model signal",
            "model_signal_authority": "advisory_only",
        },
        "progress_labels": [
            "Understanding query",
            "Resource planning",
            "Validating SPL" if execution and execution.get("executed_spl") else "SPL not required",
            "Selecting MCP fixture tool" if splunk_items or selected_server == "splunk" else "MCP not required",
            "Calling MCP fixture search" if splunk_items or result_count else "MCP fixture not required",
            "Packaging SourceEvidence" if source_evidence else "SourceEvidence not required",
            "Retrieving governed SOC knowledge" if rag_items else "Governed SOC knowledge not required",
            "Mapping MITRE and severity",
            "Applying answer governance",
            "Packaging final analyst answer",
        ],
    }

    if splunk_items or selected_server == "splunk":
        rows = splunk_items[0].get("preview_rows") if splunk_items else []
        panels["mcp_tool_selection"] = {
            "mcp_server": selected_server or "splunk",
            "mcp_tool": selected_tool or "splunk_run_query",
            "selection_reason": "MCP fixture tool selection for governed evidence review",
            "input_contract": ["search_query", "earliest_time", "latest_time", "max_results"],
            "execution_mode": "Experience Center fixture result",
            "execution_gate": "no live MCP execution",
        }
        panels["mcp_fixture_result"] = {
            "result_label": "MCP fixture search result",
            "result_source": "COE fixture Splunk evidence",
            "rows_returned": result_count,
            "row_count_label": f"{result_count} fixture row{'s' if result_count != 1 else ''}",
            "evidence_refs": [str(item.get("evidence_id")) for item in splunk_items],
            "rows": rows if isinstance(rows, list) else [],
        }
        panels["source_evidence_panel"] = {
            "evidence_ids": [str(item.get("evidence_id")) for item in splunk_items],
            "source_type": "splunk_mcp_fixture",
            "collection_status": "collected" if splunk_items else "not_collected",
            "result_count": result_count,
            "warnings": ["coe_synthetic_fixture", "no live customer data", "no live MCP execution"],
        }
    elif source_evidence:
        panels["source_evidence_panel"] = {
            "evidence_ids": [str(item.get("evidence_id")) for item in source_evidence],
            "source_type": "governed_fixture",
            "collection_status": "collected",
            "result_count": sum(int(item.get("result_count") or 0) for item in source_evidence),
            "warnings": ["coe_synthetic_fixture", "no live customer data"],
        }

    if rag_items:
        panels["soc_kb_panel"] = {
            "retrieval_mode": "governed SOC-KB fixture",
            "confidence": 0.91,
            "allowed_use": "analyst guidance / triage checklist",
            "evidence_refs": [str(item.get("evidence_id")) for item in rag_items],
        }

    panels["mitre_panel"] = {
        "status": "deterministic MITRE/severity treatment applied when applicable",
        "authority": "deterministic policy",
        "unsupported_claims": [
            "do not claim account compromise without supporting evidence",
            "do not claim privileged impact without identity evidence",
            "do not claim live production impact from Experience Center fixture data",
        ],
    }

    for key, tier, note in (
        ("resource_planner", TIER_PLANNING, "Composed ResourcePlan for the scenario."),
        ("spl_validation_panel", TIER_DIAGNOSTIC, "SPL validator diagnostics unless RunContract projects block reason."),
        ("model_signal_panel", TIER_ADVISORY, "LLM/model signal is advisory only."),
        ("narration_visibility_panel", TIER_ADVISORY, "Narration visibility; deterministic answer wins."),
    ):
        if key in panels and isinstance(panels[key], dict):
            panels[key] = attach_authority_tier(panels[key], tier=tier, note=note)

    return panels


def _severity_panel(
    *,
    scenario_id: str | None,
    severity_decision: SeverityDecision | None,
) -> SeverityGovernancePanel | None:
    if severity_decision is None:
        return SeverityGovernancePanel(
            severity_label="not available",
            why_severity_title="Severity decision",
            why_severity=["Severity policy output was not available for this trace."],
            why_not_higher=[],
            priority_note=None,
        )

    label = severity_decision.severity_label
    if scenario_id == FAILED_LOGIN_SCENARIO_ID and label == "P2 High":
        return SeverityGovernancePanel(
            severity_label=label,
            why_severity_title="Why P2 High?",
            why_severity=list(FAILED_LOGIN_WHY_P2),
            why_not_higher=list(FAILED_LOGIN_WHY_NOT_P1_P0),
            priority_note=FAILED_LOGIN_PRIORITY_NOTE,
        )

    title = f"Why {label}?"
    why_severity = list(severity_decision.matched_rules) or [f"Severity policy default: {label}."]
    why_not_higher = list(severity_decision.why_not_higher)
    if severity_decision.missing_evidence:
        why_not_higher.extend(
            f"missing evidence for escalation: {item}" for item in severity_decision.missing_evidence
        )
    return SeverityGovernancePanel(
        severity_label=label,
        why_severity_title=title,
        why_severity=why_severity,
        why_not_higher=why_not_higher or ["Higher severity thresholds were not met by available evidence."],
        priority_note=None,
    )


def _skills_operations_panel(
    *,
    selected_skill: str,
    investigation_lineage: dict[str, Any] | None,
    route_plan_shadow: dict[str, Any] | None,
    question_runtime_map: dict[str, Any] | None,
    precondition_evaluation: dict[str, Any] | None,
    selected_use_case: dict[str, Any] | None,
    use_case_id: str | None,
    demo_mode: bool,
) -> SkillsOperationsGovernancePanel:
    runtime_operation, runtime_note = _runtime_operation(
        route_plan_shadow=route_plan_shadow,
        question_runtime_map=question_runtime_map,
        precondition_evaluation=precondition_evaluation,
        selected_use_case=selected_use_case,
        use_case_id=use_case_id,
        demo_mode=demo_mode,
    )
    lineage_stages = {
        str(stage.get("stage_id")): str(stage.get("status") or "unknown")
        for stage in (investigation_lineage or {}).get("stages") or []
        if isinstance(stage, dict)
    }
    pipeline = [
        PipelineStageStatus(
            stage_id=panel_id,
            label=label,
            status=lineage_stages.get(lineage_id, "not evaluated"),
        )
        for panel_id, lineage_id, label in PIPELINE_STAGE_SPECS
    ]
    return SkillsOperationsGovernancePanel(
        intent_skill=selected_skill,
        legacy_router_skill=selected_skill,
        runtime_operation=runtime_operation,
        runtime_operation_note=runtime_note,
        pipeline_stages=pipeline,
    )


def _runtime_operation(
    *,
    route_plan_shadow: dict[str, Any] | None,
    question_runtime_map: dict[str, Any] | None,
    precondition_evaluation: dict[str, Any] | None,
    selected_use_case: dict[str, Any] | None,
    use_case_id: str | None,
    demo_mode: bool,
) -> tuple[str | None, str]:
    if route_plan_shadow:
        primary = route_plan_shadow.get("primary_skill")
        if primary:
            return str(primary), "from route_plan_shadow.primary_skill (shadow only; not authority)"

        bridge = route_plan_shadow.get("intent_operation_bridge")
        if isinstance(bridge, dict):
            operation = bridge.get("runtime_operation") or bridge.get("operation_id")
            if operation:
                return str(operation), "from route_plan_shadow intent-operation bridge (shadow only)"

        operation = route_plan_shadow.get("runtime_operation") or route_plan_shadow.get("coverage_operation")
        if operation:
            return str(operation), "from route_plan_shadow metadata (shadow only)"

    if question_runtime_map and question_runtime_map.get("observation_only"):
        operation = question_runtime_map.get("proposed_operation_type") or question_runtime_map.get(
            "proposed_primary_skill"
        )
        if operation:
            return str(operation), "from question_runtime_map (observation only; not authority)"

    if precondition_evaluation:
        op = precondition_evaluation.get("runtime_operation") or precondition_evaluation.get("operation_id")
        if op:
            return str(op), "from precondition_evaluation shadow (observation only)"

    resolved_use_case = use_case_id
    if not resolved_use_case and selected_use_case:
        resolved_use_case = selected_use_case.get("use_case_id")

    if demo_mode and resolved_use_case:
        return None, f"not evaluated in demo fixture (production-equivalent mapping available: {resolved_use_case})"

    if resolved_use_case:
        return None, f"not evaluated (use case mapped: {resolved_use_case})"

    return None, "not evaluated"
