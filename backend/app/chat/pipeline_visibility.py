"""Batch 4 — additive response visibility and per-stage node trace (packaging-only)."""

from __future__ import annotations

from typing import Any

from app.chat.control_plane_trace import _redact
from app.chat.session_context import SessionContextResolution
from app.use_cases.content_enrichment import curated_enrichment_trace, enrichment_spl_governance

GuardrailStatus = str  # passed | review_required | blocked | not_applicable


def resolve_spl_template_status(
    *,
    use_case_id: str | None,
    candidate_spl: dict[str, Any] | None,
    spl_validation: dict[str, Any] | None,
) -> str | None:
    for payload in (spl_validation, candidate_spl):
        if isinstance(payload, dict):
            status = payload.get("spl_template_status")
            if status:
                return str(status)
    if use_case_id:
        governance = enrichment_spl_governance(use_case_id)
        if governance:
            return str(governance.get("spl_template_status") or "unavailable")
    return None


def resolve_mitre_evidence_status(mitre_decision: dict[str, Any] | None) -> dict[str, str] | None:
    if not isinstance(mitre_decision, dict):
        return None
    statuses = mitre_decision.get("evidence_statuses")
    if not isinstance(statuses, dict) or not statuses:
        return None
    return {str(key): str(value) for key, value in statuses.items()}


def build_pipeline_node_trace(
    *,
    state: dict[str, Any],
    selected_use_case_id: str | None,
    mitre_decision: dict[str, Any] | None,
    spl_validation: dict[str, Any] | None,
    candidate_spl: dict[str, Any] | None,
    execution: dict[str, Any] | None,
    human_review: dict[str, Any] | None,
    answer_guard: dict[str, Any] | None,
    final_answer_validation: dict[str, Any] | None,
    answer_contract: dict[str, Any] | None,
    severity_decision: Any | None,
    session_context_resolution: SessionContextResolution | None = None,
) -> list[dict[str, Any]]:
    """Assemble lightweight per-stage trace records from finalized pipeline state."""
    records: list[dict[str, Any]] = []
    routed = state.get("routed") if isinstance(state.get("routed"), dict) else {}
    route_shadow = state.get("route_plan_shadow") if isinstance(state.get("route_plan_shadow"), dict) else {}
    routing_resolution = state.get("routing_skill_resolution") if isinstance(
        state.get("routing_skill_resolution"), dict
    ) else {}
    evidence_plan = state.get("evidence_plan") if isinstance(state.get("evidence_plan"), dict) else {}
    spl_status = resolve_spl_template_status(
        use_case_id=selected_use_case_id,
        candidate_spl=candidate_spl if isinstance(candidate_spl, dict) else None,
        spl_validation=spl_validation if isinstance(spl_validation, dict) else None,
    )
    mitre_statuses = resolve_mitre_evidence_status(mitre_decision) or {}

    if session_context_resolution is not None:
        records.append(
            _trace_record(
                node_name="session_context",
                input_summary={
                    "session_id": session_context_resolution.session_id,
                    "follow_up_kind": session_context_resolution.follow_up_kind,
                },
                output_summary={
                    "used_previous_context": session_context_resolution.status.used_previous_context,
                    "staleness": session_context_resolution.status.staleness,
                    "used_fields": session_context_resolution.status.used_fields,
                    "ignored_fields": session_context_resolution.status.ignored_fields,
                    "clarification_required": session_context_resolution.status.clarification_required,
                },
                decision_reason="structured_session_pins_only",
                guardrail_status="review_required"
                if session_context_resolution.status.clarification_required
                else ("passed" if session_context_resolution.status.used_previous_context else "not_applicable"),
                human_review_required=session_context_resolution.status.clarification_required,
                limitations=[],
            )
        )

    records.append(
        _trace_record(
            node_name="routing_live_skill_selection",
            input_summary={"query_present": bool(state.get("request"))},
            output_summary={
                "selected_skill": routed.get("skill"),
                "effective_skill": routing_resolution.get("effective_skill") or routed.get("skill"),
                "use_case_id": selected_use_case_id,
            },
            decision_reason=str(routing_resolution.get("skill_resolution") or "deterministic_routing"),
            guardrail_status="passed" if routed.get("skill") else "not_applicable",
            human_review_required=False,
            limitations=[],
        )
    )

    planning_skill = None
    if isinstance(route_shadow.get("route_authority_compare"), dict):
        planning_skill = route_shadow["route_authority_compare"].get("planning_primary_skill")
    if planning_skill:
        records.append(
            _trace_record(
                node_name="planning_analytic_skill_resolution",
                input_summary={"legacy_skill": routed.get("skill")},
                output_summary={"planning_or_analytic_skill": planning_skill},
                decision_reason="route_authority_compare",
                guardrail_status="not_applicable",
                human_review_required=False,
                limitations=[],
            )
        )

    enrichment = curated_enrichment_trace(selected_use_case_id) if selected_use_case_id else None
    if enrichment:
        activation = enrichment.get("activation") if isinstance(enrichment.get("activation"), dict) else {}
        summary = enrichment.get("context_summary") if isinstance(enrichment.get("context_summary"), dict) else {}
        records.append(
            _trace_record(
                node_name="enrichment_loading",
                input_summary={"use_case_id": selected_use_case_id},
                output_summary={
                    "context_loaded": enrichment.get("context_loaded"),
                    "activation_lifecycle_stage": activation.get("activation_lifecycle_stage"),
                    "runtime_support_status": activation.get("runtime_support_status"),
                    "planner_runtime_activation_allowed": activation.get("planner_runtime_activation_allowed"),
                    "spl_template_status": summary.get("spl_template_status") or activation.get("spl_template_status"),
                },
                decision_reason="curated_enrichment_activation_gate",
                guardrail_status="passed" if enrichment.get("context_loaded") else "not_applicable",
                human_review_required=False,
                limitations=list(activation.get("reasons") or [])[:5],
            )
        )

    if evidence_plan:
        records.append(
            _trace_record(
                node_name="evidence_planning",
                input_summary={"intent_family": (state.get("intent_classification") or {}).get("intent_family")},
                output_summary={
                    "answer_mode": evidence_plan.get("answer_mode"),
                    "spl_allowed": evidence_plan.get("spl_allowed"),
                    "mcp_allowed": evidence_plan.get("mcp_allowed"),
                },
                decision_reason="deterministic_evidence_plan",
                guardrail_status="passed",
                human_review_required=False,
                limitations=[],
            )
        )

    records.append(
        _trace_record(
            node_name="spl_template_status",
            input_summary={
                "use_case_id": selected_use_case_id,
                "template_id": (candidate_spl or {}).get("template_id") if candidate_spl else None,
            },
            output_summary={
                "spl_template_status": spl_status,
                "governed_limitation": (spl_validation or candidate_spl or {}).get("governed_limitation")
                if isinstance(spl_validation or candidate_spl, dict)
                else None,
            },
            decision_reason=_spl_status_reason(spl_status),
            guardrail_status="review_required" if spl_status in {"planned", "unavailable"} else "passed",
            human_review_required=bool(spl_status in {"planned", "unavailable"}),
            limitations=_spl_limitations(spl_status),
        )
    )

    records.append(
        _trace_record(
            node_name="spl_validation",
            input_summary={"spl_template_status": spl_status},
            output_summary={
                "approved": (spl_validation or {}).get("approved") if spl_validation else None,
                "normalized_spl_available": bool((spl_validation or {}).get("normalized_spl"))
                if spl_validation
                else False,
                "reject_reasons": list((spl_validation or {}).get("reject_reasons") or [])[:5]
                if spl_validation
                else [],
            },
            decision_reason="validate_spl_mandatory",
            guardrail_status=_spl_validation_guardrail(spl_validation),
            human_review_required=not bool((spl_validation or {}).get("approved")) if spl_validation else False,
            limitations=[],
        )
    )

    exec_payload = execution if isinstance(execution, dict) else {}
    review_payload = human_review if isinstance(human_review, dict) else {}
    records.append(
        _trace_record(
            node_name="execution_hil_decision",
            input_summary={
                "mcp_allowed": evidence_plan.get("mcp_allowed"),
                "spl_approved": bool((spl_validation or {}).get("approved")) if spl_validation else False,
            },
            output_summary={
                "execution_status": exec_payload.get("status"),
                "execution_status_label": exec_payload.get("execution_status_label"),
                "evidence_source": exec_payload.get("evidence_source"),
                "human_review_required": review_payload.get("required"),
                "review_type": review_payload.get("review_type"),
            },
            decision_reason=str(exec_payload.get("block_reason") or exec_payload.get("tool_selection_reason") or "mcp_gate"),
            guardrail_status=_execution_guardrail(exec_payload, review_payload),
            human_review_required=bool(review_payload.get("required")),
            limitations=[],
        )
    )

    records.append(
        _trace_record(
            node_name="mitre_evidence_status",
            input_summary={"use_case_id": selected_use_case_id},
            output_summary={
                "evidence_statuses": mitre_statuses,
                "rejected_techniques": list((mitre_decision or {}).get("rejected_techniques") or [])[:8],
                "not_claimed": list((mitre_decision or {}).get("not_claimed") or [])[:8],
            },
            decision_reason=str((mitre_decision or {}).get("mapping_rationale") or "mitre_decision_resolver"),
            guardrail_status="passed" if mitre_decision else "not_applicable",
            human_review_required=False,
            limitations=[],
        )
    )

    severity_label = getattr(severity_decision, "severity_label", None) if severity_decision else None
    records.append(
        _trace_record(
            node_name="severity_decision",
            input_summary={"use_case_id": selected_use_case_id},
            output_summary={"severity_label": severity_label},
            decision_reason="deterministic_severity_policy",
            guardrail_status="passed" if severity_label else "not_applicable",
            human_review_required=False,
            limitations=list(getattr(severity_decision, "missing_evidence", None) or [])[:5]
            if severity_decision
            else [],
        )
    )

    if answer_contract:
        records.append(
            _trace_record(
                node_name="answer_contract",
                input_summary={"answer_mode": answer_contract.get("answer_mode")},
                output_summary={
                    "mitre_answer_visible": answer_contract.get("mitre_answer_visible"),
                    "candidate_mitre_count": len(answer_contract.get("candidate_mitre") or []),
                    "evidence_supported_mitre_count": len(answer_contract.get("evidence_supported_mitre") or []),
                    "spl_status": answer_contract.get("spl_status"),
                    "hil_status": answer_contract.get("hil_status"),
                    "execution_status_label": answer_contract.get("execution_status_label"),
                    "human_review_required": answer_contract.get("human_review_required"),
                },
                decision_reason="answer_contract_projection",
                guardrail_status="passed",
                human_review_required=bool(answer_contract.get("human_review_required")),
                limitations=list(answer_contract.get("missing_evidence") or [])[:5],
            )
        )

    guard_status = str((answer_guard or {}).get("guard_status") or "disabled")
    records.append(
        _trace_record(
            node_name="answer_guard",
            input_summary={"enabled": (answer_guard or {}).get("enabled")},
            output_summary={
                "guard_status": guard_status,
                "failed_checks": list((answer_guard or {}).get("failed_checks") or [])[:8],
            },
            decision_reason=str((answer_guard or {}).get("reason") or "answer_guard_lab"),
            guardrail_status=_answer_guard_guardrail(answer_guard),
            human_review_required=bool((answer_guard or {}).get("analyst_review_required")),
            limitations=[],
        )
    )

    final_status = str((final_answer_validation or {}).get("guard_status") or "not_run")
    records.append(
        _trace_record(
            node_name="final_answer_validation",
            input_summary={"contract_present": answer_contract is not None},
            output_summary={
                "guard_status": final_status,
                "failed_checks": list((final_answer_validation or {}).get("failed_checks") or [])[:8],
            },
            decision_reason=str((final_answer_validation or {}).get("reason") or "deterministic_final_validator"),
            guardrail_status=_final_validation_guardrail(final_answer_validation),
            human_review_required=bool((final_answer_validation or {}).get("analyst_review_required")),
            limitations=[],
        )
    )

    return [_redact(record) for record in records]


def build_pipeline_visibility(
    *,
    state: dict[str, Any],
    selected_use_case_id: str | None,
    mitre_decision: dict[str, Any] | None,
    spl_validation: dict[str, Any] | None,
    candidate_spl: dict[str, Any] | None,
    execution: dict[str, Any] | None,
    human_review: dict[str, Any] | None,
    answer_guard: dict[str, Any] | None,
    final_answer_validation: dict[str, Any] | None,
    answer_contract: dict[str, Any] | None,
    severity_decision: Any | None,
    session_context_resolution: SessionContextResolution | None = None,
) -> dict[str, Any]:
    node_trace = build_pipeline_node_trace(
        state=state,
        selected_use_case_id=selected_use_case_id,
        mitre_decision=mitre_decision,
        spl_validation=spl_validation if isinstance(spl_validation, dict) else None,
        candidate_spl=candidate_spl if isinstance(candidate_spl, dict) else None,
        execution=execution if isinstance(execution, dict) else None,
        human_review=human_review if isinstance(human_review, dict) else None,
        answer_guard=answer_guard,
        final_answer_validation=final_answer_validation,
        answer_contract=answer_contract,
        severity_decision=severity_decision,
        session_context_resolution=session_context_resolution,
    )
    guard_status = str((answer_guard or {}).get("guard_status") or "disabled") if answer_guard else None
    safety_status = (
        str((final_answer_validation or {}).get("guard_status") or "not_run")
        if final_answer_validation
        else None
    )
    return {
        "mitre_evidence_status": resolve_mitre_evidence_status(mitre_decision),
        "spl_template_status": resolve_spl_template_status(
            use_case_id=selected_use_case_id,
            candidate_spl=candidate_spl if isinstance(candidate_spl, dict) else None,
            spl_validation=spl_validation if isinstance(spl_validation, dict) else None,
        ),
        "node_trace": node_trace,
        "answer_guard_status": guard_status,
        "final_answer_safety_status": safety_status,
    }


def _trace_record(
    *,
    node_name: str,
    input_summary: dict[str, Any],
    output_summary: dict[str, Any],
    decision_reason: str,
    guardrail_status: GuardrailStatus,
    human_review_required: bool,
    limitations: list[str],
) -> dict[str, Any]:
    return {
        "node_name": node_name,
        "input_summary": input_summary,
        "output_summary": output_summary,
        "decision_reason": decision_reason,
        "guardrail_status": guardrail_status,
        "human_review_required": human_review_required,
        "limitations": limitations,
    }


def _spl_status_reason(status: str | None) -> str:
    if status == "active":
        return "active_template_available"
    if status == "planned":
        return "spl_template_planned_no_free_spl_fallback"
    if status == "unavailable":
        return "spl_template_unavailable_no_free_spl_fallback"
    return "spl_template_status_unknown"


def _spl_limitations(status: str | None) -> list[str]:
    if status == "planned":
        return ["SPL template is planned; governed limitation applies."]
    if status == "unavailable":
        return ["SPL template unavailable for this use case."]
    return []


def _spl_validation_guardrail(spl_validation: dict[str, Any] | None) -> GuardrailStatus:
    if not spl_validation:
        return "not_applicable"
    if spl_validation.get("approved"):
        return "passed"
    return "review_required"


def _execution_guardrail(execution: dict[str, Any], human_review: dict[str, Any]) -> GuardrailStatus:
    if human_review.get("required"):
        return "review_required"
    status = str(execution.get("status") or "")
    if status == "blocked":
        return "blocked"
    if status == "executed":
        return "passed"
    return "review_required"


def _answer_guard_guardrail(answer_guard: dict[str, Any] | None) -> GuardrailStatus:
    if not answer_guard or not answer_guard.get("enabled"):
        return "not_applicable"
    status = str(answer_guard.get("guard_status") or "")
    if status == "blocked":
        return "blocked"
    if status == "passed":
        return "passed"
    return "not_applicable"


def _final_validation_guardrail(final_answer_validation: dict[str, Any] | None) -> GuardrailStatus:
    if not final_answer_validation:
        return "not_applicable"
    status = str(final_answer_validation.get("guard_status") or "")
    if status == "blocked":
        return "blocked"
    if status == "passed":
        return "passed"
    return "not_applicable"
