# Plan 5 C0 — measured disagreement between the three lifecycle-phase surfaces

Measured in-process at `2a0ff02` by introspecting the live objects (not by reading them by eye):
`PipelineStage` (`chat/contracts/pipeline_dispatch.py:11`), `_HOOK_BY_NAME` (`planner/executor.py:290`),
the fallback `hook_nodes` literal (`chat/pipeline.py:5779`), and the compiler's `SCHEDULABLE_HOOKS`
(`planner/resource_plan_execution_scheduler.py:42`).

## Membership

| Phase | `PipelineStage` | `_HOOK_BY_NAME` | fallback `hook_nodes` | `SCHEDULABLE_HOOKS` |
|---|---|---|---|---|
| `prepare_rag_only` | – | Y | Y | Y |
| `rag_early` | Y | Y | Y | Y |
| `pre_spl_mcp_discovery` | Y | – | – | – |
| `workflow_spl` | Y | Y | Y | Y |
| `spl_postprocessor` | Y | Y | Y | **–** |
| `spl_source_resolve` | Y | Y | Y | Y |
| `ensure_workflow_plan` | – | Y | **–** | Y |
| `reference_finalize` | Y | Y | Y | **–** |
| `mitre_finalize` | Y | **–** | **–** | – |
| `cve_adapter` | Y | **–** | **–** | – |
| `execution` / `mcp_execution` | Y (as `mcp_execution`) | Y (as `execution`) | Y (as `execution`) | Y (as `execution`) |

Three surfaces, **12 distinct phases**, and **no two surfaces agree**:

1. **Naming collision.** The same phase is `mcp_execution` in the stage vocabulary and `execution` in both hook
   loops. Translation happens by hand inside `imperative_hook_schedule_from_state`
   (`contracts/pipeline_dispatch.py:210-212`) — nothing checks the two names stay in step.
2. **`mitre_finalize` and `cve_adapter` are scheduled by a surface that cannot run them.**
   `pipeline_dispatch_builder.py:333,347,365,370` appends them to `stage_schedule`; the projection then drops both
   on the floor (`contracts/pipeline_dispatch.py:216-217`, a bare `continue`), and neither hook loop has an entry.
   They are not dead: both execute **inline inside `graph_node_context_finalize`** (`pipeline.py:3545`) — MITRE via
   `run_mitre_evidence_branch` (`:3634`), CVE via `_resolve_vulnerability_source_status` (`:2122`, called `:5187`) —
   and the canonical facts spine attributes facts to them by name (`canonical_facts_spine.py:207,219,237`).
   **So the work is real, is claimed in provenance, and is invisible to every schedule.** No schedule can order it,
   require it, or prove it ran.
3. **`pre_spl_mcp_discovery` is stage-only** — dispatch-v2 runs it inline in `graph_node_workflow_spl`, and the
   projection also `continue`s past it (`:194-195`).
4. **`ensure_workflow_plan` is hook-only** and missing from the fallback loop, so an SPL-blocked turn that lands in
   the fallback cannot be given the workflow-plan stub the executor path would give it.
5. **The compiler silently omits two phases it cannot schedule.** `spl_postprocessor` and `reference_finalize` are
   excluded from `SCHEDULABLE_HOOKS` by design ("driven by their own stage predicates",
   `resource_plan_execution_scheduler.py:40-41`) — which is exactly the Plan 3 A0 measurement that the
   execution-driven compiler drops a stage on 4 of 5 probes when made authoritative without a lifecycle contract.

## Why this is the C0 defect and not a naming nit

`spl_postprocessor` owns `validate_spl` (`pipeline.py:2597`), the deterministic gate that must precede the MCP
execution gate. Today "SPL validation precedes execution" holds because two hand-written schedules happen to list the
hooks in that order, and a third (the compiler) omits the phase entirely and relies on a predicate elsewhere. No
surface *states* the constraint, so nothing can enforce it.

C0's registry makes the catalog closed and the ordering constraint declarative; C0.1 decides applicability per run;
C0.2 freezes it into a per-run contract the planner cannot edit.
