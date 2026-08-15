# Plan 7 A7 — session SPL refine / legacy fallback lifecycle proof

Date: 2026-08-15 UTC

Disposition: **B. `LEGACY_FALLBACK_ROLLBACK_ONLY_RETAIN_TEMPORARILY`**

Target flags: LangGraph ON, ResourcePlan execution ON, dispatch-v2 OFF. No change to
`architecture.md`; no dispatch-v2 reactivation.

## Reachability and ownership

| Symbol/path | Production reachable | Rollback only | Test only | Current owner | Lifecycle coverage | Safe disposition |
|---|---:|---:|---:|---|---|---|
| production `/chat` selector → `run_chat_via_resource_planner_graph` | yes | no | no | Resource Planner graph | committed ResourcePlan; PhaseContract/merge at composed dispatch | retain as sole normal entry |
| `_session_spl_refine_stage` inside `graph_node_workflow_spl` | conditionally, when the target graph schedules the SPL worker | no | no | SPL worker under ResourcePlan lifecycle | candidate is deterministically validated; PhaseContract owns postprocessor/source resolve/execution when a committed plan exists | retain |
| `_session_spl_refine_active` imperative branch | no under target selector | yes | yes | legacy imperative orchestration | selects the duplicate fallback only after LangGraph is disabled | fence as rollback-only |
| `_run_legacy_dispatch_fallback` | no under target selector | yes | yes | legacy imperative rollback runtime | now explicitly `workflow_spl → spl_postprocessor → spl_source_resolve → execution` | retain temporarily, one caller only |
| dispatch-v2 `imperative_hook_schedule_from_state` / projections | no when ResourcePlan execution is on | yes when ResourcePlan execution is off and v2 is on | yes | legacy rollback schedule projection | helper fence refuses authority whenever ResourcePlan execution is enabled | retain for rollback compatibility |
| `dispatch_v2_route_after_*` in `linear_graph_legacy.py` | no from production `/chat` | no current operational approval | yes (legacy graph/parity harness) | legacy test harness | outside Resource Planner production topology | retain historical/test surface; not normal authority |
| `build_plan_dispatch_trace_from_pipeline_dispatch` demo/trace compatibility | no authority | compatibility only | yes | diagnostic projection | trace-only and now fenced with the same ResourcePlan-off predicate | retain diagnostic compatibility |

Static importer/caller proof:

- `_run_legacy_dispatch_fallback` has exactly one code caller, the imperative
  `session_spl_refine` branch.
- `resource_planner_graph.py` neither imports nor calls `_run_legacy_dispatch_fallback`.
- `/chat` selects `run_chat_via_resource_planner_graph` while LangGraph is enabled.
- `linear_graph_legacy.py` is exercised as a test/parity harness; it is not the production
  selector.

## Before/after lifecycle

Before A7, the non-v2 fallback ran `workflow_spl → spl_source_resolve → execution`; it owed the
mandatory `spl_postprocessor` but skipped it. After A7 it runs:

```text
workflow_spl → spl_postprocessor → spl_source_resolve → execution
```

The observed rollback-only session-refine candidate is revalidated before postprocessing. The
postprocessor mutation does not pass deterministic revalidation, so the path fails closed with:

- `spl_validation.approved=false`;
- `spl_validation.normalized_spl=null`;
- reject reason `postprocessor_mutation_revalidation_failed`;
- execution not live-executed.

That is a safety correction, not approval to execute. The target Resource Planner graph never
enters the duplicate fallback; the exercised follow-up currently degrades without a candidate
instead of selecting a second executor.

## Required six proofs

| Question | Result | Evidence |
|---|---|---|
| Who owns `spl_source_resolve`? | ResourcePlan/PhaseContract on target; explicit ordered legacy node only in rollback fallback | phase-contract/merge tests; fallback order test |
| Does `spl_postprocessor` execute? | yes on every applicable target schedule and now yes in the retained fallback | `test_fallback_legacy_branch_runs_the_mandatory_spl_lifecycle`; A3 tests |
| Is candidate SPL deterministically validated? | yes; the observed fallback mutation fails revalidation closed | session-context A7 regression test |
| Can candidate SPL reach MCP without approved non-null `normalized_spl`? | no | MCP gate source pins plus 43 focused MCP gate/contract tests |
| Do HIL/RBAC remain authoritative? | yes; execution remains not-executed/review-only and no gate code changed | MCP gate tests; invariant review |
| Is execution duplicated? | no; target graph has no fallback importer, fallback has one caller, schedules contain no duplicate hook | execution-seam inventory and dispatch call-count tests |

## Focused verification

- A7 local: `test_batch5_session_context.py`, `test_fallback_lifecycle_equivalence.py`,
  `test_execution_seam_coverage.py` — **29 passed**.
- Target/authority/lifecycle focused suites — **66 passed**, **208 passed**, and **46 passed**.
- MCP execution gate/contract — **43 passed**.
- Backend-container target-graph session-refine non-entry proof passed; fallback structural and
  seam tests passed there. The broad container session file also exposed profile-dependent live
  advisory noise in unrelated MITRE/session setup, so it is not cited as a clean suite pass.
- Reference authority probes in the backend container — **10/10 passed** after the authorized
  authority-source migration.
- Invariant check — **7/7 PASS** (recorded in the Plan 7 evidence update).

## Residual limitation

The retained fallback is still a duplicate executor in an old orchestration posture. It is not
deleted because old-release rollback and historical tests still depend on it. It is not an
alternative normal production authority, and a later cleanup may remove it together with the
older release compatibility surface. No live Splunk/MCP claim is made.
