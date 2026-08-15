# Phase contract and schedule merge (Plan 5 C)

Live execution architecture after Plan 5 Phase C. Runtime code is authoritative. This document describes **what exists**, not what is activated: `AI_SOC_RESOURCE_PLAN_EXECUTION_ENABLED` stays **default false**. Flag-off runs zero merge-seam code (`planner/executor.py:_execution_driven_schedule_detailed` returns `(None, None, None)` before importing the merge).

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

Wiring: exactly one call site, `planner/executor.py` inside `_execution_driven_schedule_detailed`, reached only when the execution flag is on **and** dispatch-v2 has not already projected a schedule. Ladder precedence:

1. Flag off → fixed predicate schedule; zero merge-seam code.
2. Dispatch-v2 projected schedule present → that projection wins (`dispatch_v2_projected_schedule`).
3. Otherwise merge ResourcePlan + PhaseContract. Unsupported/invalid/unplaceable plans downgrade to the fixed schedule.

## Schedule-level capability satisfaction

Required capabilities on `ResolvedQueryContract` are satisfied by the **complete governed executable schedule**, not necessarily by one routed skill (Plan 5 amendment 5, measured at B5).

A plan whose primary skill is `spl_generation` may legitimately satisfy `{spl, mcp}` as `spl → validate_spl → mcp read/evidence → synthesis`. Route-level "one skill must grant everything" enforcement demoted `cisco.ot.029` to `knowledge_recall` and is **default OFF** (`ai_soc_live_capability_enforcement_enabled=false`). A schedule-level shortfall is **reported**, never converted into a route change. A skill contract may **deny** a capability; it may never silently widen one.

## Known gaps (recorded, not adopted)

- `mitre_finalize` / `cve_adapter` execute inside `graph_node_context_finalize` and are named `pipeline_inline` in the registry. They are not represented consistently by the hook-loop schedule surfaces. The PhaseContract lists them in `inline_mandatory` so absence from the hook schedule cannot be misread as "not owed". **Plan 6 E0** added the matching *observed* side: `pipeline_inline_executed` (`planner/inline_execution_provenance.py`) names the inline phases that actually ran, surfaced as `debug_summary.schedule.inline_executed` next to `inline_mandatory`. It is provenance only — it dispatches, schedules and authorizes nothing.
- `_run_legacy_dispatch_fallback` (`chat/pipeline.py`) does not run `spl_postprocessor`. It is **not** retired. Safety today is the MCP gate refusing unapproved/null `normalized_spl`, plus the RP-graph `spl_validate` node on the default spine. Proof: `docs/evals/plan5/c3_fallback_equivalence.md`.
- Seam inventory stays 2 SEAM / 4 DECISION_REQUIRED / 4 KEEP_SEPARATE, **0 adopted** (`test_execution_seam_coverage.py`).
- **Measured on the VPS (Plan 6, Arm C: exec ON + v2 OFF):** merge is genuinely reachable and executed on **5/12** corpus rows; **7/12** were legitimately `merge_not_reachable`. But two `workflow_spl` / `no_schedulable_step` rows (`p6.multi.knowledge_spl_mcp`, `p6.live_posture.d1_003`) **lose `spl_postprocessor`** that dispatch-v2 supplies today — known missed work, and the reason C0 recorded KEEP OFF. Closing this structurally (not per query ID) is Plan 7's Workstream A.
- Flag-on probe closed Plan 3 A0's 4-of-5 stage-drop: `docs/evals/plan5/c2_phase_merge_probe.json` (`merged_stage_drops=0/5`). That probe is not an activation.

## COE warning

Repo default `AI_SOC_PIPELINE_DISPATCH_V2_ENABLED=false`. This VPS sets it true, so dispatch-v2 projected schedules beat the execution-driven compiler there. Changes to the dispatch builder or the fallback loop are live the moment they land.

**Which committed profile actually supplies the flags is not `coe.env.example`.** Compose loads `env/profiles/${AI_SOC_ENV_PROFILE:-coe}.env.example` and then `.env`; this host sets `AI_SOC_ENV_PROFILE=development`, so `development.env.example` is in effect (found in the Plan 6 F4 rollback drill). Check `AI_SOC_ENV_PROFILE` before reasoning about any flag, and remember that editing only `.env` does not remove profile-supplied keys.

**Plan 6 outcome:** `P6_PRODUCTION_GO_LIVE = DEFER`. The merge architecture is proven **experimentally**, not production-authoritative; authority remains dispatch-v2. `exec ON + v2 ON` is `V2_WINS` and is never ResourcePlan activation. See `docs/evals/plan6_activation_and_t4_report.md`.

Related: [`routing_authority_map.md`](routing_authority_map.md) (query → contract → skill), [`docs/evals/plan5_architecture_and_routing_report.md`](../evals/plan5_architecture_and_routing_report.md).
