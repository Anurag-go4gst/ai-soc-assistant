# Phase contract and schedule merge (Plan 5 C; Plan 7/8 current authority)

**Current verified authority (Plan 7 E2 / Plan 8 X2):** `ResourcePlan + PhaseContract` is the sole **normal** production execution authority via the existing Resource Planner hub. dispatch-v2 is rollback/test-only and **cannot win** while `AI_SOC_RESOURCE_PLAN_EXECUTION_ENABLED` is true (`legacy_dispatch_v2_authority_enabled`). `_run_legacy_dispatch_fallback` is retained temporarily (Plan 7 A7) and now includes `spl_postprocessor`. Production GO remains deferred. T4 serving (F3) and live MCP/Splunk stay unproven. `PlanDelta` / step-instance execution are Plan 8 `NOT_REQUIRED_FOR_CURRENT_SCOPE`.

Repo default `AI_SOC_RESOURCE_PLAN_EXECUTION_ENABLED` is **false**; this host's `development` profile sets it **true** and dispatch-v2 **false**. Flag-off runs zero merge-seam code (`planner/executor.py:_execution_driven_schedule_detailed` returns `(None, None, None)` before importing the merge).

Historical Plan 5/6 measurements below remain as recorded evidence; they do not reopen Plan 7 authority.

## Three distinct artifacts

Plan 3 A0 decided `PHASE_POLICY_PLUS_RESOURCE_PLAN_SCHEDULING`. Plan 5 C delivered it as three artifacts, not one:

| Artifact | Module | Role |
|---|---|---|
| **PhaseRegistry** | `backend/app/planner/phase_registry.py` | Closed catalog of lifecycle phases (identity, owner, ordering constraints, hook binding). Catalog only — decides nothing about a given run. A name outside the catalog raises `UnknownPhaseError`. |
| **PhasePolicy resolver** | `backend/app/planner/phase_policy.py` | Pure deterministic `(ResolvedQueryContract, ResourcePlan, PhasePolicyInputs) → applicable/mandatory phases`. Never an LLM, never a heuristic, never a count. |
| **PhaseContract** | `backend/app/planner/phase_contract.py` | Per-run frozen set of mandatory phases plus ordering constraints. Immutable once resolved. Planner, specialists, and LLM advisories have no add/remove/reorder/downgrade API. |

Lifecycle phases are **mandatory when deterministically applicable**, not universally mandatory. A knowledge-only turn carries no SPL chain; a turn with no reference IDs carries no `reference_finalize`.

## Merge seam

`planner/phase_schedule_merge.py::merge_schedule` is the single compiler consumer. It reuses `compile_execution_schedule` and then does the two things that compiler cannot: re-insert contracted lifecycle phases the compiler is structurally unable to schedule (`spl_postprocessor`, `reference_finalize`), and evaluate **capability satisfaction at schedule level**.

Wiring: exactly one merge call site, `planner/executor.py` inside `_execution_driven_schedule_detailed`, reached when the execution flag is on **and** dispatch-v2 is not allowed to own the schedule. Ladder precedence after Plan 7 A6:

1. Flag off → fixed predicate schedule; zero merge-seam code.
2. ResourcePlan execution ON → dispatch-v2 projection is fenced (`legacy_dispatch_v2_authority_enabled` is false even if the v2 flag is true); merge ResourcePlan + PhaseContract.
3. ResourcePlan execution OFF and dispatch-v2 ON → rollback-only v2 projection may run.
4. Unsupported/invalid/unplaceable plans downgrade to the fixed schedule.

## Schedule-level capability satisfaction

Required capabilities on `ResolvedQueryContract` are satisfied by the **complete governed executable schedule**, not necessarily by one routed skill (Plan 5 amendment 5, measured at B5).

A plan whose primary skill is `spl_generation` may legitimately satisfy `{spl, mcp}` as `spl → validate_spl → mcp read/evidence → synthesis`. Route-level "one skill must grant everything" enforcement demoted `cisco.ot.029` to `knowledge_recall` and is **default OFF** (`ai_soc_live_capability_enforcement_enabled=false`). A schedule-level shortfall is **reported**, never converted into a route change. A skill contract may **deny** a capability; it may never silently widen one.

## Known gaps (recorded, not adopted)

- `mitre_finalize` / `cve_adapter` execute inside `graph_node_context_finalize` and are named `pipeline_inline` in the registry. They are not represented consistently by the hook-loop schedule surfaces. The PhaseContract lists them in `inline_mandatory` so absence from the hook schedule cannot be misread as "not owed". **Plan 6 E0** added the matching *observed* side: `pipeline_inline_executed` (`planner/inline_execution_provenance.py`) names the inline phases that actually ran, surfaced as `debug_summary.schedule.inline_executed` next to `inline_mandatory`. It is provenance only — it dispatches, schedules and authorizes nothing.
- `_run_legacy_dispatch_fallback` (`chat/pipeline.py`) is **rollback-only** (Plan 7 A7 `LEGACY_FALLBACK_ROLLBACK_ONLY_RETAIN_TEMPORARILY`). After A7 it runs `workflow_spl → spl_postprocessor → spl_source_resolve → execution`. It is not a second normal executor. The MCP gate still refuses unapproved/null `normalized_spl`. Proof: `docs/evals/plan7/a7_fallback_lifecycle_proof.md`.
- Seam inventory stays 2 SEAM / 4 DECISION_REQUIRED / 4 KEEP_SEPARATE, **0 adopted** (`test_execution_seam_coverage.py`).
- **Measured on the VPS (Plan 6, Arm C: exec ON + v2 OFF):** merge is genuinely reachable and executed on **5/12** corpus rows; **7/12** were legitimately `merge_not_reachable`. But two `workflow_spl` / `no_schedulable_step` rows (`p6.multi.knowledge_spl_mcp`, `p6.live_posture.d1_003`) **lose `spl_postprocessor`** that dispatch-v2 supplies today — known missed work, and the reason C0 recorded KEEP OFF. Closing this structurally (not per query ID) is Plan 7's Workstream A.
- Flag-on probe closed Plan 3 A0's 4-of-5 stage-drop: `docs/evals/plan5/c2_phase_merge_probe.json` (`merged_stage_drops=0/5`). That probe is not an activation.

## COE / host warning

Repo default `AI_SOC_PIPELINE_DISPATCH_V2_ENABLED=false`. Plan 7 retired v2 from **normal** authority; this host's `development` profile keeps v2 **false** and ResourcePlan execution **true**, so the compiler is the normal path here. `coe.env.example` still historically sets v2 true / execution false — that profile is not this host.

**Which committed profile actually supplies the flags is not `coe.env.example`.** Compose loads `env/profiles/${AI_SOC_ENV_PROFILE:-coe}.env.example` and then `.env`; this host sets `AI_SOC_ENV_PROFILE=development`. Check `AI_SOC_ENV_PROFILE` before reasoning about any flag, and remember that editing only `.env` does not remove profile-supplied keys.

**Plan 7 outcome:** `RESOURCEPLAN_AUTHORITY=APPROVED`; `PRODUCTION_GO_LIVE=DEFERRED / NO-GO` (F3 T4 serving). **Plan 6** `P6_PRODUCTION_GO_LIVE = DEFER` remains historical. `exec ON + v2 ON` is still `V2_WINS` and is never ResourcePlan activation — Plan 7 fences that combination. See `docs/evals/plan7/` and `docs/evals/plan6_activation_and_t4_report.md`.

Related: [`routing_authority_map.md`](routing_authority_map.md) (query → contract → skill), [`docs/evals/plan5_architecture_and_routing_report.md`](../evals/plan5_architecture_and_routing_report.md).
