"""Canonical planning telemetry catalog — all 28 events (plan item 21)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.chat.planning_telemetry_policy import (
    AUDIT_CRITICAL_PLANNING_EVENTS,
    DIAGNOSTIC_PLANNING_EVENTS,
)

TelemetryClass = Literal["audit-critical", "diagnostic"]


@dataclass(frozen=True)
class CanonicalTelemetryEventSpec:
    event: str
    classification: TelemetryClass
    node_name: str
    success_condition: str
    failure_condition: str | None
    required_payload: tuple[str, ...]
    dedup_identity: str


def _spec(
    event: str,
    *,
    node_name: str,
    success_condition: str,
    failure_condition: str | None = None,
    required_payload: tuple[str, ...] = ("trace_id", "status"),
    dedup_identity: str | None = None,
) -> CanonicalTelemetryEventSpec:
    if event in AUDIT_CRITICAL_PLANNING_EVENTS:
        classification: TelemetryClass = "audit-critical"
    elif event in DIAGNOSTIC_PLANNING_EVENTS:
        classification = "diagnostic"
    else:
        raise ValueError(f"event not classified in policy: {event}")
    return CanonicalTelemetryEventSpec(
        event=event,
        classification=classification,
        node_name=node_name,
        success_condition=success_condition,
        failure_condition=failure_condition,
        required_payload=required_payload,
        dedup_identity=dedup_identity or f"decision_id per emit_planning_event ({event})",
    )


CANONICAL_TELEMETRY_EVENT_SPECS: tuple[CanonicalTelemetryEventSpec, ...] = (
    _spec(
        "query_understanding.completed",
        node_name="understand_query",
        success_condition="Query understanding node completes",
        required_payload=("trace_id", "match_path", "status"),
    ),
    _spec(
        "lane_router.decided",
        node_name="lane_router",
        success_condition="Lane router selects initial/resolved tier and processing lane",
        required_payload=("trace_id", "match_path", "initial_tier", "resolved_tier", "processing_lane", "status"),
    ),
    _spec(
        "known_completeness.evaluated",
        node_name="known_detail_completion",
        success_condition="Known-path completeness gate evaluates",
        required_payload=("completeness_status", "status"),
    ),
    _spec(
        "guided_resolution.started",
        node_name="guided_detail_resolution",
        success_condition="Guided detail resolution begins for a handoff",
        required_payload=("handoff_id", "status"),
    ),
    _spec(
        "guided_intent.resolved",
        node_name="canonical_planning_orchestrator",
        success_condition="T4 intent classification completes",
        required_payload=("intent_family", "status"),
    ),
    _spec(
        "tier.resolved",
        node_name="tier_resolver",
        success_condition="Initial and resolved tier recorded",
        required_payload=("initial_tier", "resolved_tier", "processing_lane", "status"),
    ),
    _spec(
        "detail_tool.selected",
        node_name="detail_tool",
        success_condition="Detail tool chosen for a missing field category",
        required_payload=("handoff_id", "selected_tools", "status"),
    ),
    _spec(
        "detail_tool.started",
        node_name="detail_tool",
        success_condition="Detail tool invocation begins",
        required_payload=("handoff_id", "selected_tools", "status"),
    ),
    _spec(
        "detail_tool.completed",
        node_name="detail_tool",
        success_condition="Detail tool returns a terminal non-error status",
        required_payload=("handoff_id", "tool_statuses", "status"),
    ),
    _spec(
        "detail_tool.failed",
        node_name="detail_tool",
        success_condition="Detail tool returns error status",
        failure_condition="Tool error or fatal policy block",
        required_payload=("handoff_id", "error_category", "status"),
    ),
    _spec(
        "detail_merge.completed",
        node_name="detail_merge",
        success_condition="Detail tool output merged into handoff field state",
        required_payload=("handoff_id", "resolved_fields", "status"),
    ),
    _spec(
        "post_guided_completeness.evaluated",
        node_name="post_guided_completeness",
        success_condition="Post-guided completeness gate evaluates",
        required_payload=("completeness_status", "status"),
    ),
    _spec(
        "clarification.requested",
        node_name="clarification",
        success_condition="Clarification handoff persisted and outcome emitted",
        required_payload=("handoff_id", "handoff_version", "unresolved_fields", "status"),
        dedup_identity="handoff_id + handoff_version + clarification.requested",
    ),
    _spec(
        "handoff.persisted",
        node_name="canonical_handoff_store",
        success_condition="Handoff row durably written",
        failure_condition="HandoffPersistenceError → persistence_failed",
        required_payload=("handoff_id", "handoff_version", "handoff_status", "status"),
        dedup_identity="handoff_id + handoff_version + handoff_status transition",
    ),
    _spec(
        "handoff.resumed",
        node_name="canonical_handoff_resumption",
        success_condition="Clarification answer advances handoff version",
        failure_condition="ClarificationResumeError",
        required_payload=("handoff_id", "handoff_version", "prior_handoff_version", "status"),
        dedup_identity="handoff_id + prior_handoff_version + resumed_version",
    ),
    _spec(
        "planner_handoff.created",
        node_name="canonical_handoff_builder",
        success_condition="CanonicalPlanningInput packaged for final planner",
        required_payload=("handoff_id", "handoff_version", "status"),
    ),
    _spec(
        "planner_handoff.consumed",
        node_name="plan_evidence_from_canonical",
        success_condition="Final planner consumes canonical handoff",
        required_payload=("handoff_id", "resource_plan_id", "status"),
    ),
    _spec(
        "resource_plan.created",
        node_name="plan_evidence_from_canonical",
        success_condition="New ResourcePlan committed",
        failure_condition="commit persistence failure",
        required_payload=("resource_plan_id", "handoff_id", "handoff_version", "status"),
        dedup_identity="resource_plan_id",
    ),
    _spec(
        "resource_plan.commit_reused",
        node_name="plan_evidence_from_canonical",
        success_condition="Idempotent replay returns existing committed plan",
        required_payload=("resource_plan_id", "handoff_id", "handoff_version", "status"),
        dedup_identity="handoff_id + handoff_version + resource_plan_id",
    ),
    _spec(
        "execution.started",
        node_name="execution",
        success_condition="Plan dispatch begins with committed ResourcePlan",
        failure_condition="audit-critical telemetry persistence failure",
        required_payload=("resource_plan_id", "handoff_id", "status"),
    ),
    _spec(
        "execution_step.started",
        node_name="execution_step",
        success_condition="Idempotent step lease acquired before tool invoke",
        failure_condition="concurrent in_progress lease",
        required_payload=("resource_plan_id", "step_id", "operation", "status"),
        dedup_identity="canonical_execution_idempotency idempotency_key",
    ),
    _spec(
        "execution_step.completed",
        node_name="execution_step",
        success_condition="Step result persisted as completed",
        required_payload=("resource_plan_id", "step_id", "operation", "status"),
        dedup_identity="canonical_execution_idempotency idempotency_key",
    ),
    _spec(
        "execution_step.failed",
        node_name="execution_step",
        success_condition="Step failure persisted (retryable or terminal)",
        failure_condition="tool error or timeout",
        required_payload=("resource_plan_id", "step_id", "operation", "error_category", "status"),
        dedup_identity="canonical_execution_idempotency idempotency_key",
    ),
    _spec(
        "execution.completed",
        node_name="execution",
        success_condition="Plan dispatch schedule finishes",
        required_payload=("resource_plan_id", "handoff_id", "status"),
    ),
    _spec(
        "response.validated",
        node_name="response_validation",
        success_condition="Response layer validation passes",
        failure_condition="validation reasons present",
        required_payload=("trace_id", "session_id", "status"),
    ),
    _spec(
        "response.generated",
        node_name="response_assembly",
        success_condition="Final PlaceholderResponse assembled",
        failure_condition="assembly must not emit when validation failed",
        required_payload=("trace_id", "session_id", "status"),
    ),
    _spec(
        "request.completed",
        node_name="request_terminal",
        success_condition="Successful planned turn completes exactly once",
        failure_condition="must not emit for clarification_required",
        required_payload=("trace_id", "session_id", "status"),
        dedup_identity="trace_id + turn terminal flag canonical_request_terminal_event",
    ),
    _spec(
        "request.failed",
        node_name="request_terminal",
        success_condition="Terminal failure recorded exactly once",
        failure_condition="persistence_failed, validation_failed, execution_failed",
        required_payload=("trace_id", "session_id", "reason", "error_category", "status"),
        dedup_identity="trace_id + turn terminal flag canonical_request_terminal_event",
    ),
)


CANONICAL_TELEMETRY_EVENTS: frozenset[str] = frozenset(spec.event for spec in CANONICAL_TELEMETRY_EVENT_SPECS)


def catalog_event_names() -> frozenset[str]:
    return CANONICAL_TELEMETRY_EVENTS


def spec_for_event(event: str) -> CanonicalTelemetryEventSpec | None:
    for spec in CANONICAL_TELEMETRY_EVENT_SPECS:
        if spec.event == event:
            return spec
    return None


@dataclass(frozen=True)
class ProductionEmitterWiring:
    """Production source files and markers proving real-node emission (item 21)."""

    source_paths: tuple[str, ...]
    markers: tuple[str, ...]


#: Each event must be wired from at least one production module (not catalog/tests only).
PRODUCTION_EMITTER_WIRING: dict[str, ProductionEmitterWiring] = {
    "query_understanding.completed": ProductionEmitterWiring(
        ("backend/app/chat/canonical_planning_orchestrator.py",),
        ('event="query_understanding.completed"',),
    ),
    "lane_router.decided": ProductionEmitterWiring(
        ("backend/app/chat/canonical_planning_orchestrator.py",),
        ("emit_lane_router_decided",),
    ),
    "known_completeness.evaluated": ProductionEmitterWiring(
        ("backend/app/chat/canonical_planning_orchestrator.py",),
        ("emit_known_completeness_evaluated",),
    ),
    "guided_resolution.started": ProductionEmitterWiring(
        ("backend/app/chat/canonical_planning_orchestrator.py",),
        ("emit_guided_resolution_started",),
    ),
    "guided_intent.resolved": ProductionEmitterWiring(
        ("backend/app/chat/canonical_planning_orchestrator.py",),
        ('event="guided_intent.resolved"',),
    ),
    "tier.resolved": ProductionEmitterWiring(
        ("backend/app/chat/canonical_planning_orchestrator.py",),
        ("emit_tier_resolved",),
    ),
    "detail_tool.selected": ProductionEmitterWiring(
        ("backend/app/chat/guided_detail_resolution.py",),
        ('event_suffix="selected"',),
    ),
    "detail_tool.started": ProductionEmitterWiring(
        ("backend/app/chat/guided_detail_resolution.py",),
        ('event_suffix="started"',),
    ),
    "detail_tool.completed": ProductionEmitterWiring(
        ("backend/app/chat/guided_detail_resolution.py",),
        ('event_suffix="completed"',),
    ),
    "detail_tool.failed": ProductionEmitterWiring(
        ("backend/app/chat/guided_detail_resolution.py",),
        ('event_suffix="failed"',),
    ),
    "detail_merge.completed": ProductionEmitterWiring(
        ("backend/app/chat/guided_detail_resolution.py",),
        ("emit_detail_merge_completed",),
    ),
    "post_guided_completeness.evaluated": ProductionEmitterWiring(
        ("backend/app/chat/canonical_planning_orchestrator.py",),
        ("emit_post_guided_completeness_evaluated",),
    ),
    "clarification.requested": ProductionEmitterWiring(
        ("backend/app/chat/canonical_planning_orchestrator.py",),
        ("emit_clarification_requested",),
    ),
    "handoff.persisted": ProductionEmitterWiring(
        (
            "backend/app/chat/canonical_planning_orchestrator.py",
            "backend/app/chat/plan_evidence_from_canonical.py",
        ),
        ("emit_handoff_persisted",),
    ),
    "handoff.resumed": ProductionEmitterWiring(
        ("backend/app/chat/canonical_planning_orchestrator.py",),
        ("emit_handoff_resumed",),
    ),
    "planner_handoff.created": ProductionEmitterWiring(
        ("backend/app/chat/plan_evidence_from_canonical.py",),
        ("emit_planner_handoff_created",),
    ),
    "planner_handoff.consumed": ProductionEmitterWiring(
        ("backend/app/chat/plan_evidence_from_canonical.py",),
        ("emit_planner_handoff_consumed",),
    ),
    "resource_plan.created": ProductionEmitterWiring(
        ("backend/app/chat/plan_evidence_from_canonical.py",),
        ("emit_resource_plan_created",),
    ),
    "resource_plan.commit_reused": ProductionEmitterWiring(
        ("backend/app/chat/plan_evidence_from_canonical.py",),
        ("emit_resource_plan_commit_reused",),
    ),
    "execution.started": ProductionEmitterWiring(
        ("backend/app/planner/executor.py",),
        ('event="execution.started"',),
    ),
    "execution.completed": ProductionEmitterWiring(
        ("backend/app/planner/executor.py",),
        ('event="execution.completed"',),
    ),
    "execution_step.started": ProductionEmitterWiring(
        ("backend/app/chat/canonical_execution_idempotency.py",),
        ('"execution_step.started"',),
    ),
    "execution_step.completed": ProductionEmitterWiring(
        ("backend/app/chat/canonical_execution_idempotency.py",),
        ('"execution_step.completed"',),
    ),
    "execution_step.failed": ProductionEmitterWiring(
        ("backend/app/chat/canonical_execution_idempotency.py",),
        ('"execution_step.failed"',),
    ),
    "response.validated": ProductionEmitterWiring(
        ("backend/app/chat/response_validation.py",),
        ('event="response.validated"',),
    ),
    "response.generated": ProductionEmitterWiring(
        ("backend/app/chat/response_validation.py",),
        ('event="response.generated"',),
    ),
    "request.completed": ProductionEmitterWiring(
        ("backend/app/chat/pipeline.py",),
        ("emit_request_completed",),
    ),
    "request.failed": ProductionEmitterWiring(
        (
            "backend/app/chat/response_validation.py",
            "backend/app/chat/canonical_mode.py",
        ),
        ("emit_request_failed",),
    ),
}
