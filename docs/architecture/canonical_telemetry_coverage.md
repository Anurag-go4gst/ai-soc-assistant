# Canonical planning telemetry coverage

Classification for plan item **21b**. **Audit-critical** events must persist to
`canonical_planning_events` before side-effecting execution proceeds; a write
failure on that path fails closed (`persistence_failed`). **Diagnostic** events
honour `TELEMETRY_MODE` / `AI_SOC_TELEMETRY_SINK`; persistence failure is logged
with `error_category`, surfaced on the in-memory trace, and never blocks chat.

| Event | Class | Emitting node (planned / current) |
|-------|-------|-----------------------------------|
| `query_understanding.completed` | diagnostic | `canonical_planning_orchestrator` |
| `lane_router.decided` | diagnostic | `canonical_planning_orchestrator` |
| `known_completeness.evaluated` | diagnostic | `canonical_planning_orchestrator` |
| `guided_resolution.started` | diagnostic | `canonical_planning_orchestrator` |
| `guided_intent.resolved` | diagnostic | `canonical_planning_orchestrator` |
| `tier.resolved` | diagnostic | `canonical_planning_orchestrator` |
| `detail_tool.selected` | diagnostic | `guided_detail_resolution` |
| `detail_tool.started` | diagnostic | `guided_detail_resolution` |
| `detail_tool.completed` | diagnostic | `guided_detail_resolution` |
| `detail_tool.failed` | diagnostic | `guided_detail_resolution` |
| `detail_merge.completed` | diagnostic | `guided_detail_resolution` |
| `post_guided_completeness.evaluated` | diagnostic | `canonical_planning_orchestrator` |
| `clarification.requested` | diagnostic | `canonical_planning_orchestrator` |
| `handoff.persisted` | **audit-critical** | `canonical_handoff_store` (item 21) |
| `handoff.resumed` | **audit-critical** | `canonical_handoff_resumption` (item 21) |
| `planner_handoff.created` | diagnostic | `plan_evidence_from_canonical` |
| `planner_handoff.consumed` | diagnostic | `plan_evidence_from_canonical` |
| `resource_plan.created` | **audit-critical** | `plan_evidence_from_canonical` |
| `resource_plan.commit_reused` | diagnostic | `plan_evidence_from_canonical` |
| `execution.started` | **audit-critical** | `planner/executor.execute_plan_dispatch` |
| `execution_step.started` | **audit-critical** | `planner/executor` (item 20) |
| `execution_step.completed` | **audit-critical** | `planner/executor` (item 20) |
| `execution_step.failed` | **audit-critical** | `planner/executor` (item 20) |
| `execution.completed` | diagnostic | `planner/executor.execute_plan_dispatch` |
| `response.validated` | diagnostic | `response_validation` |
| `response.generated` | diagnostic | `response_validation` |
| `request.completed` | diagnostic | `pipeline` finalize (item 21) |
| `request.failed` | **audit-critical** | `response_validation.emit_request_failed` |

Startup guard: `MCP_GLOBAL_EXECUTION_ENABLED=true` with `TELEMETRY_MODE=none` and
`AI_SOC_TELEMETRY_SINK=none` is rejected — audit-critical events would have no
durable path while execution is enabled.
