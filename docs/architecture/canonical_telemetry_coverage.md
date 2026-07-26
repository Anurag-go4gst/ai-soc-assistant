# Canonical planning telemetry coverage

Classification for plan items **21** and **21b**. **Audit-critical** events must persist to
`canonical_planning_events` before side-effecting execution proceeds; a write failure on that
path fails closed (`persistence_failed`). **Diagnostic** events honour `TELEMETRY_MODE` /
`AI_SOC_TELEMETRY_SINK`; persistence failure is logged with `error_category`, surfaced on the
in-memory trace, and never blocks chat.

Correlation fields (`trace_id`, `session_id`, `turn_id`, `decision_id`, `parent_decision_id`,
`handoff_id`, `handoff_version`, `resource_plan_id`, `node_name`, `node_version`,
`contract_version`, `status`, `duration_ms`, `error_category`) are read from the **unminimized**
event and bound as typed columns. `minimize()` applies only to the free-form JSON payload.

Terminal consistency:

| Outcome | Terminal events |
|---------|-----------------|
| Successful response assembly | Exactly one `request.completed` |
| Terminal failure | Exactly one `request.failed` |
| Clarification | `clarification.requested` only — no `request.completed` / `request.failed` from planning |
| Failed response assembly | `request.failed` — no `response.generated` |
| Idempotent replay | No duplicate terminal events (`canonical_request_terminal_event`) |

Startup guard: `MCP_GLOBAL_EXECUTION_ENABLED=true` with `TELEMETRY_MODE=none` and
`AI_SOC_TELEMETRY_SINK=none` is rejected — audit-critical events would have no durable path
while execution is enabled.

Experience Center / demo (`backend/app/demo/`) does not import planning telemetry emitters.

## Event catalog

| Event | Class | Emitting node | Success | Failure | Required payload | Dedup identity |
|-------|-------|---------------|---------|---------|------------------|----------------|
| `query_understanding.completed` | diagnostic | `canonical_planning_orchestrator` | QU completes | — | `trace_id`, `match_path`, `status` | `decision_id` per emit |
| `lane_router.decided` | diagnostic | `canonical_planning_orchestrator` | Lane/tier chosen | — | `trace_id`, `match_path`, tiers, lane, `status` | `decision_id` |
| `known_completeness.evaluated` | diagnostic | `canonical_planning_orchestrator` | Known gate runs | — | `completeness_status`, `status` | `decision_id` |
| `guided_resolution.started` | diagnostic | `canonical_planning_orchestrator` | Guided resolution begins | — | `handoff_id`, `status` | `decision_id` |
| `guided_intent.resolved` | diagnostic | `canonical_planning_orchestrator` | T4 intent resolved | — | `intent_family`, `status` | `decision_id` |
| `tier.resolved` | diagnostic | `canonical_planning_orchestrator` | Tier recorded | — | tiers, lane, `status` | `decision_id` |
| `detail_tool.selected` | diagnostic | `guided_detail_resolution` | Tool chosen | — | `handoff_id`, `selected_tools`, `status` | `decision_id` |
| `detail_tool.started` | diagnostic | `guided_detail_resolution` | Tool invoke starts | — | `handoff_id`, `selected_tools`, `status` | `decision_id` |
| `detail_tool.completed` | diagnostic | `guided_detail_resolution` | Tool returns OK | — | `handoff_id`, `tool_statuses`, `status` | `decision_id` |
| `detail_tool.failed` | diagnostic | `guided_detail_resolution` | Tool error | fatal/transient policy | `handoff_id`, `error_category`, `status` | `decision_id` |
| `detail_merge.completed` | diagnostic | `guided_detail_resolution` | Merge completes | — | `handoff_id`, `resolved_fields`, `status` | `decision_id` |
| `post_guided_completeness.evaluated` | diagnostic | `canonical_planning_orchestrator` | Post-guided gate | — | `completeness_status`, `status` | `decision_id` |
| `clarification.requested` | diagnostic | `canonical_planning_orchestrator` | Handoff persisted | persistence error → `persistence_failed` | `handoff_id`, `handoff_version`, `unresolved_fields`, `status` | `handoff_id` + version |
| `handoff.persisted` | **audit-critical** | `canonical_planning_orchestrator`, `plan_evidence_from_canonical` | Row written | `HandoffPersistenceError` | `handoff_id`, `handoff_version`, `handoff_status`, `status` | handoff + status transition |
| `handoff.resumed` | **audit-critical** | `canonical_handoff_resumption` (via orchestrator) | Version advanced | `ClarificationResumeError` | `handoff_id`, versions, `status` | prior + resumed version |
| `planner_handoff.created` | diagnostic | `plan_evidence_from_canonical` | CPI packaged | — | `handoff_id`, `handoff_version`, `status` | `decision_id` |
| `planner_handoff.consumed` | diagnostic | `plan_evidence_from_canonical` | Final planner consumes | — | `handoff_id`, `resource_plan_id`, `status` | `decision_id` |
| `resource_plan.created` | **audit-critical** | `plan_evidence_from_canonical` | Plan committed | commit persistence failure | `resource_plan_id`, handoff fields, `status` | `resource_plan_id` |
| `resource_plan.commit_reused` | diagnostic | `plan_evidence_from_canonical` | Idempotent replay | — | `resource_plan_id`, handoff fields, `status` | handoff + plan id |
| `execution.started` | **audit-critical** | `planner/executor.execute_plan_dispatch` | Dispatch begins | audit-critical persist failure | `resource_plan_id`, `handoff_id`, `status` | `decision_id` |
| `execution_step.started` | **audit-critical** | `canonical_execution_idempotency.run_idempotent_execution_step` | Lease acquired | concurrent `in_progress` | `resource_plan_id`, `step_id`, `operation`, `status` | idempotency key |
| `execution_step.completed` | **audit-critical** | `canonical_execution_idempotency` | Step completed / replay | — | step identity fields, `status` | idempotency key |
| `execution_step.failed` | **audit-critical** | `canonical_execution_idempotency` | Step failure persisted | tool error | step identity + `error_category` | idempotency key |
| `execution.completed` | diagnostic | `planner/executor.execute_plan_dispatch` | Schedule finishes | — | `resource_plan_id`, `handoff_id`, `status` | `decision_id` |
| `response.validated` | diagnostic | `response_validation` | Validation pass/fail recorded | validation reasons | `trace_id`, `session_id`, `status` | `decision_id` |
| `response.generated` | diagnostic | `response_validation` / `pipeline` finalize | Response assembled | skipped when `request.failed` | `trace_id`, `session_id`, `status` | `decision_id` |
| `request.completed` | diagnostic | `pipeline` finalize (`emit_request_completed`) | Successful turn | must not emit for clarification | `trace_id`, `session_id`, `status` | `canonical_request_terminal_event` |
| `request.failed` | **audit-critical** | `response_validation`, `canonical_mode.build_persistence_failed_state` | Terminal failure | validation / persistence / execution | `trace_id`, `session_id`, `reason`, `error_category` | `canonical_request_terminal_event` |

Machine-readable catalog: `backend/app/chat/canonical_telemetry_catalog.py`.

Verification: `pytest backend/app/tests/test_canonical_telemetry_coverage.py -q`
