---
name: architecture-resource-plan-execution-and-adaptive-planning
overview: "Make Resource Planner topology and decision-record dataflow falsifiable, empirically price the live shadow-planning path, and gate any adaptive-planning or execution-order change behind explicit COE decisions."
status: draft
date: 2026-08-10
canonical_plan: plans/2026-08-10_1103_architecture-resource-plan-execution-and-adaptive-planning.md
source_audit: plans/2026-08-10_0555_architecture-audit-query-understanding-and-plan-creation.md
source_plan: plans/2026-08-08_1824_architecture-review-corrective-actions.md
baseline_head: f34f4d8
implementation_readiness: "READY_FOR_P0_AND_MECHANICAL_A_ITEMS; BLOCKED_AT_B1_AND_C0_DECISION_GATES"
---

# Plan 2 — ResourcePlan execution and adaptive-planning architecture

## Objective

Close the remaining post-G1 architecture gaps without reopening the completed corrective plan. Done means: Resource Planner topology assertions are independently falsifiable; every Resource Planner decision record names real state inputs and outputs; one bounded T4 observation establishes whether the shadow planner makes and discards a real model request; the user/COE explicitly chooses **RETIRE** or **RE-WIRE** for legacy discovery and LLM planning; the user/COE separately chooses **LINEAGE-ONLY** or **EXECUTION-DRIVEN** ResourcePlan ordering; only the selected conditional branches are implemented; current deterministic, SPL, MCP, HIL, RBAC, parity, and baseline invariants remain green.

This is the execution plan, not execution. Plan authoring changed no runtime code and did not run the live T4 probe.

## Sources and authority

- The authoritative open-work source is the source audit's `## Post-G1 disposition (2026-08-10)` section. Earlier audit status text is historical evidence only.
- The corrective plan is closed at `16/16`, final commit `e5c1937`; it supplies locked decisions and accepted G1 evidence and must not be reopened.
- Runtime code at `f34f4d8` is authoritative over both documents. `baseline_head: f34f4d8` is a runtime-content anchor, not a requirement that execution begin with HEAD checked out at that exact commit.
- HEAD may advance beyond `f34f4d8` through plan/audit-only commits under `plans/*.md`. Before P0 does anything else, `git diff f34f4d8..HEAD` must prove that no runtime, config, script, governed-registry, frontend, backend, or other non-plan file changed. Any non-`plans/*.md` path is drift and stops P0.
- The only changes from `e5c1937` to authoring HEAD are the two plan/audit markdown files. The accepted runtime baseline therefore has no intervening runtime diff, but **P0 must still re-run and record fresh results before implementation**.

## Verified starting architecture at authoring

| Surface | Current observation at `f34f4d8` |
|---|---|
| Worktree | `master` is ahead of `origin/master`. Existing user-owned dirt: `.claude/settings.local.json`, `.playwright-mcp/`, two G0 PNGs, and `output/`. Do not absorb, clean, or overwrite them. (`plans/README.md` was committed with the plan at `4c9ac32` and is no longer dirt.) |
| Protected manifest | Checks clean at `f34f4d8`: `protected artifacts unchanged (13 checked)`. P0 recaptures the Plan 2 manifest at `/tmp/plan2-execution-baseline.json`. |
| Accepted pre-Plan-2 gates | **Rebased onto the `f34f4d8` hotfix — do not compare against the older corrective-G1 numbers.** Measured at `f34f4d8`: governance regression PASS with `4797 passed, 2 skipped, 6 xfailed` (harness 6/6, clean-answer `120 pass / 0 review / 0 fail / 0 critical`, Cisco power-grid `PASS=50 / REVIEW=0 / FAIL=0`, SPL template audit 18/18, pipeline dispatch matrix 5/5), separate full backend `4797 passed, 2 skipped, 6 xfailed`, protected manifest 13/13. The `4795 → 4797` delta is exactly the two concurrency regression tests added by the hotfix; no pre-existing test changed result. Corrective G1's reference probes `10 PASS / 0 DRIFT` and parity `120 exact / 0 approved / 0 critical` were re-measured green during P0's stopped run at `c20be00`, whose only runtime-relevant difference from `f34f4d8` is the hotfix. All of this is inherited evidence, not a substitute for P0. |
| Graph registration | 25 compiled node names including `__start__` and `route_setup`; `route_setup` remains registered. |
| `get_graph()` | Still exposes only four edges: start→bootstrap, bootstrap→route_resolution, route_resolution→delegate, and delegate→end. `xray=True` does not add the hidden fan-out/governance edges. |
| Better runtime topology seam | `compiled.builder.edges` exposes 20 fixed edges including start/end. `compiled.builder.branches` exposes mapped destinations for merge (4), `rag_early` (2), and `workflow_spl` (2); the delegate branch has `ends=None` because it returns dynamic `Send` values. This builder seam was not used by the audit and makes static/conditional verification falsifiable. |
| Dynamic fan-out | Direct `_fan_out_specialists({})` emits exactly four `Send`s targeting `specialist_skill`, `specialist_knowledge`, `specialist_mcp`, and `specialist_spl`. Each specialist has a fixed builder edge to `resource_planner_merge`. |
| Documented topology | `_documented_resource_planner_edges()` has 30 edges. It invents `bootstrap→route_setup→resource_planner_delegate` and omits the real `bootstrap→route_resolution→resource_planner_delegate`; `resource_planner_graph_edges()` still returns `get_graph introspection | documented`. |
| Orphan | `rp_node_route_setup` remains registered but has no builder edge or branch path. Removal is not authorized until A0's failing-first reachability test proves this against the current graph. |
| Decision records | There are 25 record shapes before orphan removal: the rejection helper, four specialist records, and 20 node wrappers. `ResourcePlannerGraphState` exposes 107 channels. `normalized_spl` is not a state channel; it is nested under `spl_validation`. Known false labels remain: `rag_early` claims `source_evidence`; `decide_facts` and `answer_guard` claim outputs they never write; `policy_veto` claims `human_review`; `work_bundle.apply` claims `evidence_plan`; the MCP gate claims root input `normalized_spl`. A1 must inventory all records rather than fixing only these examples. |
| ResourcePlan order | `walk_plan_steps()` preserves composed order and blocked/skipped lineage. `build_step_walk_dispatch_schedule()` still delegates to `_legacy_predicate_dispatch_schedule()`; current tests explicitly assert equality. |
| Dormant sequencing assets | `ResourcePlanV2`, recipe dependencies, and `orchestration_scheduler.py` already model bounded dependencies/failure for the fenced recipe/discovery rail. They are fixture/legacy-loop assets, not authority to wire them into canonical dispatch. C1-E may reuse concepts only after re-verifying boundaries. |
| Legacy discovery | `graph_node_evidence_planning` still fails closed with `canonical_forbids_legacy_evidence_planning`; `_run_discovery_loop_imperative` cannot initialize the loop on the canonical path; `MAX_MCP_HOPS=6` remains coupled to that fenced machinery. |
| Live discovery | With `AI_SOC_PIPELINE_DISPATCH_V2_ENABLED=true`, `graph_node_workflow_spl` still calls bounded pre-SPL MCP discovery, whose context may feed the SPL plan compiler and saved-search preference. This is separate from the fenced legacy loop. |
| LLM planning | Canonical plan creation remains deterministic in `_commit_planned_outcome` → `plan_evidence_from_canonical`. The inline bridge call remains inside the fenced legacy planning node. Finalize still calls `run_resource_plan_shadow`; its trace hard-blocks promotion. A third planning rail also exists: imperative `_run_guided_hybrid_dispatch` imports/can call `propose_investigation_plan_llm`, validates it, and is absent from the Resource Planner graph dispatch branches. On this host both guided-hybrid and guided-LLM flags are true, so the proposer is currently reserved/not attempted on that imperative branch; it is still a structurally reachable parallel planner under another supported flag posture and must be dispositioned by B1. |
| Host posture | Safe flags re-read from `.env`: local LLM; final/live synthesis true; guided, intent-advisor, SPL fallback, guided-hybrid, dispatch-v2, and LangGraph true; routing `llm_assisted_semantic`; MCP mock with global execution true; T2 deadline 210s and LLM timeout 90s. No secret values were read into this plan. |

### Authoring premise deltas

1. The audit's statement that `get_graph()` exposes only four edges remains true, but it missed the usable `compiled.builder.edges` and `.branches` seam. A0 should use that runtime builder data, not require unsupported dynamic-edge exposure from `get_graph()`.
2. The audit described `route_setup` as stale/orphan; re-verification confirms it is still registered and unreachable at `f34f4d8`.
3. The audit described decision-record inconsistencies as examples; current inventory found additional false output labels (`rag_early`, `policy_veto`, and the rejection helper). A1 is therefore an all-record inventory, not a three-line patch.
4. The audit framed execution-driven semantics as needing a new dependency design. Current code already contains dormant `ResourcePlanV2` and pure recipe scheduler contracts, but they belong to the fenced legacy rail and cannot be promoted silently.
5. Gap 4 has three LLM-planning surfaces, not two: fenced inline bridge, discard-only shadow runner, and the imperative guided-hybrid proposer rail. The Resource Planner graph has no guided-hybrid dispatch branch, but the imperative implementation remains a parity-supported runtime; RETIRE must retire the proposer authority there, while RE-WIRE must fold it into the one canonical seam. Deterministic guided dispatch, validation, and evidence collection are separate capabilities and are not implicitly retired.

## Locked invariants

- Exactly four permanent Resource Planner specialists: `skill`, `knowledge`, `mcp`, `spl`.
- Specialist reports remain bounded and advisory. Proposals may fill blanks only on an existing authorized step after validated merge; they may not add/drop steps, relax policy, or overwrite operator/COE values.
- MCP specialist performs no discovery network I/O, connector call, tool execution, or execution-gate decision.
- SPL specialist emits no SPL, calls no LLM or validator, and always reports `execution_eligible=false`.
- Canonical deterministic planning is the minimum/floor. T0 is granted only by canonical reference qualification; `alert_summary` stays no-SPL.
- Candidate SPL is not executable evidence. Only approved, non-null `spl_validation.normalized_spl` may reach the MCP execution gate.
- LLM output never directly invokes MCP and never carries SPL/query/credential/raw-event content into a planning proposal.
- MCP execution gate, deterministic tool selection, RBAC, HIL, SPL validator, authority precedence, and fail-closed policy remain authoritative.
- Legacy multi-hop discovery remains fenced unless B1 explicitly authorizes a selected re-wire design.
- Live bounded pre-SPL discovery under dispatch-v2 must not be removed, disabled, renamed as legacy discovery, or fed to the MCP specialist accidentally.
- No eval/reference/golden/governed-registry baseline is refreshed by verification.
- No new default-on flag. RE-WIRE may add a dedicated default-false flag only if the B1 decision explicitly approves its name and semantics.
- No unrelated dirty or untracked file is included in a change set.

## Scope

### In scope

- Resource Planner topology extraction, reconciliation, reachability, dynamic `Send`, fan-in, and orphan tests.
- Removal of `route_setup` only if current failing-first evidence proves it unreachable and parity proves no loss.
- Complete Resource Planner decision-record I/O inventory and correction.
- One bounded, non-destructive T4 live-core observation with call-attempt instrumentation and sanitized trace evidence.
- Two explicit decision gates and only the selected conditional implementations.
- Selected-architecture documentation and final regression/manifest/parity closure.

### Out of scope

- Reopening corrective-plan gaps 6/7 or changing its accepted evidence.
- Enabling real Splunk/MCP execution, changing execution defaults, bypassing analyst confirmation, or adding write/admin tools.
- Refreshing eval/reference baselines, golden answers, governed registries, or unrelated UI work.
- Treating decision records as a new scheduler/dataflow authority.
- Combining LLM/discovery architecture and execution-order architecture in one commit.
- Deploy/restart/production mutation except the single read-only T4 observation authorized by B0.

## Decision gates

### B1 — planning/discovery posture

**DECIDED 2026-08-10 — `selected_posture: RETIRE`.** Recorded values below; the `RE-WIRE` rows are `N/A`.

| Decided field | Value |
|---|---|
| `selected_posture` | **`RETIRE`** |
| `approved_by` | **Anurag** |
| `approved_at` | **`2026-08-10T17:29:24Z`** |
| `B0_evidence_reference` | B0 evidence recorded at commit `e99fe0b`: one graph call, T4 `out_of_registry`, guided, non-executing; **shadow attempts 0** because `draft_spl_preview_active` skipped the runner; deterministic plan remained authoritative; elapsed 954 ms. |
| `guided_hybrid_llm_rail_disposition` | **`RETIRE_PROPOSER`** |
| `bridge_trigger_match_paths` | **N/A** — `RE-WIRE` only. |
| `guided_promotion_policy` | **N/A** — `RE-WIRE` only. |
| `RE-WIRE` flag/scope/budget/discovery fields | **N/A** — `RE-WIRE` only. |

Approved rationale, verbatim in substance: deterministic canonical planning remains the current production authority. The existing LLM planning rails are retired because they are fragmented, non-authoritative, discard-only, or parallel planning authorities — **not** because adaptive LLM planning is rejected as a future architecture. Future adaptive planning, if required, is to be evaluated as a new single-seam architecture above the deterministic floor, not by retaining the current fragmented rails.

Approved dispositions, binding on B2-R1 → B2-R4:

1. Retire the fenced bridge and shadow planning surfaces **after consumer proof**.
2. Retire the imperative guided-hybrid LLM proposer.
3. Preserve deterministic guided dispatch, validators, evidence collection, and the four-specialist advisory layer.
4. Preserve live dispatch-v2 pre-SPL discovery.
5. Retire legacy discovery/chronology **only after proving there are no live consumers**.
6. Retain `ai_soc_guided_llm_enabled` for budget/deadline scope only; it must no longer gate planning-model calls.
7. Remove / pin-absent the obsolete `guided_investigation_plan_llm` dispatch-step label **after consumer verification**.
8. No MCP / SPL / HIL / RBAC or execution-authority expansion.

Execution order approved: `B2-R1 → B2-R2 → B2-R3 → B2-R4`, then **stop at C0** for the independent ResourcePlan execution-order decision.

**Approver-acknowledged evidence limit:** B0 measured zero shadow attempts, so it establishes neither shadow latency nor `qu_unavailable` coverage. `RETIRE` does not depend on either, since a discard-only path needs no latency budget; this limit is recorded so no later item cites B0 as positive evidence of shadow cost or match-path coverage.

Original requirement table, retained for reference:

| Field | Required value |
|---|---|
| `selected_posture` | `RETIRE` or `RE-WIRE` |
| `approved_by` / `approved_at` | Named user/COE approver and UTC timestamp |
| `B0_evidence_reference` | Exact evidence pasted under B0 |
| `guided_hybrid_llm_rail_disposition` | If `RETIRE`: `RETIRE_PROPOSER`, removing the imperative `propose_investigation_plan_llm` authority while preserving still-used deterministic guided dispatch/validators/collection. If `RE-WIRE`: `FOLD_INTO_CANONICAL_SEAM`, leaving no direct imperative proposer or second planning authority. |
| If `RETIRE` | Confirm deterministic canonical planning remains intentional; old legacy discovery/chronology, bridge/shadow calls, and the guided-hybrid LLM proposer may be removed; live pre-SPL discovery and still-consumed deterministic guided behavior remain. |
| If `RE-WIRE` | Confirm dedicated default-false flag name, promotion scope, max plan steps, planning timeout, deterministic fallback, and whether legacy discovery is `RETIRED` or `CANONICALLY_REIMPLEMENTED` with an explicit hop bound. |
| If `RE-WIRE` — `bridge_trigger_match_paths` | Exact approved include/exclude disposition for every current bridge/T4 candidate: `out_of_registry`, `near_105_question`, `semantic_out_of_registry`, `query_understanding_weak`, `qu_unavailable`, and empty/unknown match path. Do not approve only the shorthand “T4”; exclusions need an explicit fail-closed rationale. |
| If `RE-WIRE` — `guided_promotion_policy` | Either `REMOVE_EXCLUSION_FOR_VALIDATED_CANONICAL_PROPOSALS` when promotion scope includes guided turns, or `RETAIN_EXCLUSION_AND_EXCLUDE_GUIDED_FROM_ADAPTIVE_SCOPE` with explicit acceptance that guided turns remain deterministic. This must resolve both current guards: composer `guided_hybrid_v1` and skill `guided_investigation`. |

**RETIRE** means canonical planning intentionally remains deterministic. The selected implementation removes misleading/inert canonical surfaces and model calls with no usable output, retires the imperative guided-hybrid LLM proposer as a parallel planning authority while retaining independently used deterministic guided execution/validation/collection, removes or archives legacy discovery only after consumer proof, removes inert `MAX_MCP_HOPS` live semantics, retains bounded pre-SPL discovery, and simplifies tests/docs to the actual architecture.

**RE-WIRE** means canonical planning intentionally accepts validated adaptive proposals. Deterministic ResourcePlan remains the floor; every proposal is registry/policy validated; the LLM receives no SPL/query/credentials/raw events and cannot call MCP; plan/time/hop budgets are bounded; match-path eligibility and guided promotion scope are explicit; the imperative guided proposer is folded into the canonical seam rather than retained as a parallel authority; promotion/fallback are explicit; all existing gates remain authoritative. Selecting RE-WIRE does not by itself select a discovery design—the required field above must do so.

### C0 — ResourcePlan order semantics

**DECIDED 2026-08-11 — `selected_order_semantics: EXECUTION-DRIVEN`.** Recorded values below; the `LINEAGE-ONLY` branch (`C1-L`) is dispositioned `N/A`.

| Decided field | Value |
|---|---|
| `selected_order_semantics` | **`EXECUTION-DRIVEN`** |
| `approved_by` | **Anurag** |
| `approved_at` | **`2026-08-11T05:53:15Z`** |
| `current_schedule_evidence` | C0 opposite-order matrix in this item's Evidence: five probes; four with a composed ResourcePlan show opposite step order → byte-identical dispatch schedule and `step_walk == legacy_predicate` in both directions. |
| `v1_v2_posture` | **`EXTEND_LIVE_RESOURCE_PLAN`.** Do **not** promote `ResourcePlanV2` or `orchestration_scheduler.py` wholesale. Their dependency/failure/scheduler concepts may be reused only after each reused concept's authority boundary is re-verified against the fenced-recipe origin and pinned by test. C1-E1 extends the live `ResourcePlan` contract. |
| `parallelism_policy` | Parallel execution allowed **only** for steps proven genuinely independent and safe/read-only. Any dependency-sensitive stage stays explicitly ordered. SPL validation always precedes MCP execution. MCP execution gate, HIL, RBAC and policy remain authoritative and are never parallelized away. |
| `rollback_fallback_contract` | An absent, invalid, cyclic, or unsupported ResourcePlan deterministically downgrades to the existing fixed schedule (`_legacy_predicate_dispatch_schedule` semantics) with no behavior delta. Uncertain or side-effecting operations are **never** automatically retried. The execution-driven path stays non-authoritative until its own proof is green. |
| `activation_posture` | **`DEDICATED_DEFAULT_FALSE_FLAG`** |
| `execution_order_flag_name` | **`AI_SOC_RESOURCE_PLAN_EXECUTION_ENABLED`** — must default `false` through implementation and proof; no executor may rename or default it on. |
| `guided_refinement_disposition` | Carried in from B2-R2 `FOLLOW_UP_REFINEMENT_DESIGN`. **C1-E3 must evaluate** bounded guided refinement using genuinely round-varying data: `plan → collection → new evidence / unresolved gap evaluation → bounded deterministic re-plan`. `collected_count` or an equivalent simple heuristic is **not** an acceptable trigger; a second round is valid only if new evidence/gap state can materially change the deterministic next plan. `MAX_GUIDED_INVESTIGATION_ROUNDS` stays the hard bound and no retired LLM planning authority may be reintroduced. |

Approved rationale: ResourcePlan order today is lineage-only by construction, so any real dependency, parallelism, or output→input semantics must be introduced deliberately and provably, behind a dedicated default-false flag, with the fixed deterministic schedule as the always-available fallback. Selecting EXECUTION-DRIVEN authorizes design and proof only — it does not by itself change any default, gate order, or execution authority.

Conditional disposition: `C1-L` is checked `N/A` (1 item). The rejected-branch rule under **Conditional-item disposition** applies.

Original requirement table, retained for reference:

**Carried-in requirement from B2-R2 (user decision `FOLLOW_UP_REFINEMENT_DESIGN`, 2026-08-10):** guided investigation is one-round under RETIRE. This is a **known capability gap, not the intended permanent refinement architecture**. The missing piece is a round-varying planning input derived from newly collected evidence or unresolved evidence gaps. If C0 selects **`EXECUTION-DRIVEN`**, bounded guided refinement must be evaluated as part of the execution/data-handoff design, specifically C1-E3 output→input handoffs: `plan → collection → evidence/gap evaluation → bounded re-plan`. If C0 selects **`LINEAGE-ONLY`**, guided multi-round refinement must be recorded as a separate follow-up architecture plan so one-round behavior does not become an accidental permanent limitation. Either way `MAX_GUIDED_INVESTIGATION_ROUNDS` stays the hard bound and no LLM planning authority may be reintroduced.

| Field | Required value |
|---|---|
| `selected_order_semantics` | `LINEAGE-ONLY` or `EXECUTION-DRIVEN` |
| `approved_by` / `approved_at` | Named user/COE approver and UTC timestamp |
| `current_schedule_evidence` | A reference to C0's observed order/parity matrix |
| If `EXECUTION-DRIVEN` | Confirm use/rejection of dormant V2 concepts, parallelism policy, and rollback/fallback contract. |
| If `EXECUTION-DRIVEN` — `activation_posture` | `DEDICATED_DEFAULT_FALSE_FLAG` or `CANONICAL_DEFAULT_AFTER_PROOF`. `DEDICATED_DEFAULT_FALSE_FLAG` is the recommended initial posture because it introduces no new default-on behavior. |
| If `DEDICATED_DEFAULT_FALSE_FLAG` — `execution_order_flag_name` | Exact user/COE-approved setting/environment name. It must default false; an executor may not invent or rename it. |

**LINEAGE-ONLY** makes the current fixed governed schedule an intentional contract and prevents ResourcePlan order from gaining accidental authority.

**EXECUTION-DRIVEN** requires explicit dependency, parallelism, output→input, blocked/skipped, failure, HIL/RBAC, validation, pre-SPL discovery, finalization, activation, and deterministic fallback semantics. It is not a list reorder. `CANONICAL_DEFAULT_AFTER_PROOF` does not authorize an early default switch: the execution-driven path remains non-authoritative until C1-E1 through C1-E5 are green, and C1-E6 must complete the full proof and record the separately reviewable activation-only change plus a second full gate run.

### Conditional-item disposition

Immediately after each decision, mark every item in the rejected branch checked with Evidence `N/A — rejected by <gate> decision <value>, <approver/date>`. Do not execute its commands. G1 accepts a conditional item only when it is completed with evidence or explicitly dispositioned N/A this way.

## Dependency order

Common mechanical and observation spine:

`P0 → A0 → A1.1 → A1.2 → B0 → B1 (STOP for decision) → C0 (STOP for independent decision)`

Selected planning/discovery branch:

- RETIRE: `B1 → B2-R1 → B2-R2 → B2-R3 → B2-R4`
- RE-WIRE: `B1 → B2-W1 → B2-W2 → B2-W3 → B2-W4 → B2-W5 → B2-W6 → B2-W7`

Selected order branch, after the selected B2 branch closes:

- LINEAGE-ONLY: `C0 + selected B2 closure → C1-L`
- EXECUTION-DRIVEN: `C0 + selected B2 closure → C1-E1 → C1-E2 → C1-E3 → C1-E4 → C1-E5 → C1-E6`

Closure:

`selected B2 closure + selected C1 closure → G0 → G1`

## Commit/change-set order

1. `A0`: topology truth sources, tests, and proven orphan removal only.
2. `A1.1`: decision-ref schema/inventory; `A1.2`: semantic I/O corrections.
3. `B0`: diagnostic observation artifact/evidence only; `B1` and `C0`: plan-only decision records.
4. One selected B2 branch, one commit per listed item; never mix RETIRE and RE-WIRE work.
5. One selected C1 branch, one commit per listed item; never mix with B2.
6. `G0`: documentation only.
7. `G1`: tests/evidence/plan closure only; no opportunistic runtime fixes.

Run `.claude/skills/invariant-check/SKILL.md` manually before every runtime commit. One FAIL blocks the commit.

## Loop-ready checklist

- [x] **P0 — Freeze and freshly verify the post-G1 baseline**
  - **Do:** With no runtime edits, treat `f34f4d8` as the runtime baseline and first prove that every committed baseline→HEAD path is plan/audit markdown under `plans/*.md`; HEAD itself may be newer. Also prove the current worktree has no runtime-path dirt before recording HEAD, full status, safe host posture, Plan 2 protected manifest, reference probes, production parity, governance, full backend pytest, topology inventory, and decision-record inventory. Export the host-reachable PostgreSQL URL for the whole chain. Do not refresh any baseline and do not include existing dirt.
  - **Why:** Every later result must compare against a measured `f34f4d8` baseline, not inherited prose.
  - **Surfaces:** `/tmp/plan2-execution-baseline.json`; `/tmp/plan2-p0-*`; plan Evidence only.
  - **Depends on:** none.
  - **Failing-first / observation:** Observation only; no fix is allowed. A non-`plans/*.md` path in `f34f4d8..HEAD`, runtime worktree dirt, or any mismatch with the inherited G1 counts is drift and stops the item.
  - **Verify:** From repo root, run exactly: `git diff --name-only f34f4d8..HEAD | tee /tmp/plan2-baseline-head-paths.txt`; `! rg -n -v '^plans/[^/]+\.md$' /tmp/plan2-baseline-head-paths.txt`; `git status --short -- backend frontend scripts env docker-compose.yml | tee /tmp/plan2-runtime-worktree-status.txt`; `test ! -s /tmp/plan2-runtime-worktree-status.txt`; `export DATABASE_URL="$(sed -n 's/^DATABASE_URL=//p' .env)"`; `export DATABASE_URL="${DATABASE_URL/@postgres:5432/@127.0.0.1:5434}"`; `test -n "$DATABASE_URL"`; `git rev-parse HEAD`; `git status --short --branch`; `python3 scripts/freeze_execution_baseline.py --capture --out /tmp/plan2-execution-baseline.json`; `python3 scripts/freeze_execution_baseline.py --check --in /tmp/plan2-execution-baseline.json`; `TELEMETRY_MODE=none PYTHONPATH=backend:. python3 scripts/audit_reference_probes.py --check`; `PYTHONPATH=backend:. python3 scripts/run_production_parity_eval.py --out-dir /tmp/plan2-p0-parity --check`; `./scripts/run_stage3_governance_regression.sh`; `cd backend && PYTHONPATH=../backend:.. python3 -m pytest`; return to root and re-run the manifest check and `git status --short`. Never echo `DATABASE_URL`.
  - **Evidence:** **COMPLETE 2026-08-10 against runtime baseline `f34f4d8`, start HEAD `17ebd19ee70ce8263179c1eeb4343877bd94e841`.** Fresh `f34f4d8..HEAD` inspection returned only `plans/2026-08-10_1103_architecture-resource-plan-execution-and-adaptive-planning.md`; the non-plan-path guard passed. Runtime-scoped worktree status was empty before and after; unrelated user-owned dirt remained unchanged (`.claude/settings.local.json`, `.playwright-mcp/`, two G0 PNGs, `output/`). The Plan 2 manifest was freshly captured and passed before/after (`protected artifacts unchanged (13 checked)`). Valid host-reachable runs passed: reference probes P1–P6/N1–N4 `10/10`; production parity `total=120`, `base_105=105`, `exact=120`, `approved=0`, `critical=0`; canonical governance PASS with backend `4797 passed, 2 skipped, 6 xfailed`, harness `6/6`, reference knowledge `9 passed`, observation window `8 passed, 1 skipped`, dual parity `120 exact / 0 approved / 0 critical`, clean-answer `120 pass / 0 review / 0 fail / 0 critical`, SPL template audit `18/18`, Cisco power grid `PASS=50 / REVIEW=0 / FAIL=0 / CRITICAL=0`, and dispatch matrix `5/5`; independent full-backend pytest matched exactly at `4797 passed, 2 skipped, 6 xfailed, 2 warnings in 537.91s`. Governance regenerated five tracked eval reports with timestamp/timing/order/observed-output churn; row-level verdict/classification projections and summary verdict counts were byte-equivalent, so the generated files were reverted and final protected/runtime status remained clean. Safe host posture was re-read without secrets: local/air-gapped LLM, cloud disallowed; final/live synthesis, guided LLM, intent advisor, SPL fallback, guided hybrid, dispatch-v2, LangGraph, MCP global, and MCP mock flags true; routing `llm_assisted_semantic`; T2 deadline 210s; LLM timeout 90s. Fresh topology inventory: 25 compiled node names; `get_graph()` 4 edges; builder 20 fixed edges; mapped conditional destinations `4+2+2`; delegate `ends=None` with four direct `Send` targets; documented set 30; current documented/introspected union 34. Fresh decision inventory: 21 `_record` call shapes including the rejection helper plus four parallel specialist shapes = 25 total; 24 `rp_node_*` wrappers; 107 state channels. No runtime diff; invariant check N/A. A0 was not started.

    **SUPERSEDED ATTEMPT — STOPPED 2026-08-10 at baseline `a8cef54`, HEAD `18b9828`.** Its stop cause (`handoff_not_pending`) was diagnosed as a pre-existing lock-ordering race, not drift, and fixed in `f34f4d8`; see the drift log. Re-run every command in Verify — no result below may be carried forward. Baseline→HEAD allowed paths: `plans/2026-08-10_1103_architecture-resource-plan-execution-and-adaptive-planning.md`, `plans/README.md`; non-plan path check passed. Runtime-path worktree check was empty. Start/final HEAD `18b982842c4b201932d490fd03a3ea1f5b61a78c`; unrelated status remained `.claude/settings.local.json` modified plus untracked `.playwright-mcp/`, two G0 PNGs, and `output/`. Protected manifest captured 13 artifacts and passed before/after (`protected artifacts unchanged (13 checked)`). Valid unsandboxed reference rerun: all P1–P6/N1–N4 PASS, `10/10`, zero drift. Production parity: `total=120`, `base_105=105`, `exact=120`, `approved=0`, `critical=0`. Governance pre-pytest gates passed (factory/crosswalk/validation checks; sentinel `17/17`; Tier-D `17/17`; OT `6/6`; power-industry warnings remained non-gating), but canonical backend pytest failed `app/tests/integration/test_clarification_postgres.py::test_postgres_concurrent_resume_creates_single_next_version`: concurrent resume raised `ClarificationResumeError("handoff_not_pending")`; final count `1 failed, 4794 passed, 2 skipped, 6 xfailed, 2 warnings in 549.10s`. Accepted zero-failure baseline contradicted, so the separate backend run, fresh safe-host/topology/record inventories, P0 check-off, and all later items were not run. Initial sandboxed probe/parity attempt was invalid due denied `/var/lib` writes and was replaced by the valid escalated PASS results above. No runtime change; invariant check N/A.
  - **Invariant / manifest:** Manifest must pass before and after; no runtime diff means invariant check is N/A.
  - **Commit boundary:** Evidence-only plan edit; no runtime commit.
  - **Stop:** Any non-`plans/*.md` baseline→HEAD path, runtime worktree dirt, protected drift, baseline mutation, relevant concurrent writer, or gate result contradicting the accepted baseline.

- [x] **A0 — Make Resource Planner topology independently falsifiable and remove only the proven orphan**
  - **Do:** Add `backend/app/tests/test_resource_planner_topology_contract.py` (**NEW**) and first prove the current union can mask invented edges and `route_setup` is unreachable. Then split topology surfaces: fixed edges from `compiled.builder.edges`; mapped conditional destinations from `compiled.builder.branches`; dynamic delegate edges from direct `Send` inspection; documented edges kept separate. Make `resource_planner_graph_edges()` return runtime-derived topology only (no documented union), add an explicit reconciliation result, and require documented topology to equal runtime fixed + mapped conditional + dynamic fan-out after normalized start/end handling. Assert exact four Send targets, exact specialist fan-in, all registered nodes reachable or explicitly terminal, and mutation-negative controls for invented/missing/wrong edges. Only after the failing reachability test, remove `rp_node_route_setup`, its registration, and fabricated documented edges.
  - **Why:** A documented contract must not certify itself, and an orphan must be proven against runtime construction before deletion.
  - **Surfaces:** `backend/app/graph/resource_planner_graph.py`; new topology test; existing skeleton/cardinality/dual-runtime/SPL-source parity tests.
  - **Depends on:** P0.
  - **Failing-first / observation:** Before implementation, run the new tests and record failures for documented/runtime disagreement and orphan reachability. Mutation tests must fail when an extra documented edge is injected, any Send is removed/retargeted, fan-in is removed, or an orphan is added.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_resource_planner_topology_contract.py app/tests/test_resource_planner_graph_skeleton.py app/tests/test_resource_planner_specialist_report_cardinality.py app/tests/test_dual_runtime_single_orchestration.py app/tests/test_langgraph_spl_source_resolve_parity.py -q`; then from root `python3 scripts/freeze_execution_baseline.py --check --in /tmp/plan2-execution-baseline.json` and `.cursor/hooks/audit-plan-discipline.sh plans/2026-08-10_1103_architecture-resource-plan-execution-and-adaptive-planning.md`.
  - **Evidence:** **COMPLETE 2026-08-10 against runtime baseline `f34f4d8`.** New `backend/app/tests/test_resource_planner_topology_contract.py` (19 tests) was written and run before implementation: **8 failed, 11 passed**. Failing-first assertions, all against the un-retired runtime: (1) `test_public_edge_accessor_is_runtime_derived_only` proved the union masks fabrication — `resource_planner_graph_edges()` returned `('bootstrap','route_setup')` and `('route_setup','resource_planner_delegate')`, which exist nowhere in the builder, plus a phantom `('resource_planner_delegate','__end__')` from `get_graph()`, while omitting the real `('validate_final_answer','__end__')`; (2) `test_documented_topology_equals_runtime_topology` reported 2 documented-only edges (both `route_setup`) and 2 runtime-only edges (`bootstrap→route_resolution`, `route_resolution→resource_planner_delegate`) — the documented set both invented and omitted, so the fix had to do both; (3) `test_no_registered_node_is_orphaned` returned `{'route_setup'}`; (4) `test_every_node_has_an_outbound_edge_or_is_explicitly_terminal` reported `route_setup is a dead end and not declared terminal`; (5) `test_route_setup_is_not_registered`; (6) `test_mutation_injected_orphan_is_detected` returned `{'orphan_node','route_setup'}`; (7)–(8) both sentinel-normalization parametrizations. Implementation: `reconcile_topology()` and `unreachable_nodes()` are pure functions taking injected topology, so the seven mutation-negative controls (invented edge, missing edge, removed `Send`, retargeted `Send`, removed fan-in, injected orphan, severed edge orphaning a subtree) never rebuild the `lru_cache`d graph. Final counts, each from its own source: builder fixed **20** (2 sentinel), mapped conditional **8** (merge 4, `rag_early` 2, `workflow_spl` 2), dynamic `Send` **4**, runtime union **32**, documented **30** — exactly runtime-minus-sentinels, reconciled by exact equality, not subset. `get_graph()` is no longer used for edges. Four `Send` targets in order: `specialist_skill`, `specialist_knowledge`, `specialist_mcp`, `specialist_spl`; inbound-to-`resource_planner_merge` equals exactly that set via unconditional fixed edges, with no specialist-to-specialist chaining. The delegate branch is located by name and asserted `ends is None`; targets come from invoking `_fan_out_specialists({})`, never from unwrapping LangGraph's `BranchSpec` — the Stop condition on framework internals did not fire. Registered nodes **23**, unreachable **`set()`**. Removed symbols: `rp_node_route_setup`, its `add_node("route_setup", …)` registration, both fabricated documented edges, and the then-dead `graph_node_shadow_enrichment` import (still imported by `planner_led_shadow_graph.py`, `linear_graph_legacy.py`; that module's own separate `route_setup` was not touched). Pre-deletion sweep over non-`.py` files found only plan/audit prose and `docs/evals/langgraph_dual_parity_answers.md` rows belonging to the shadow/linear graph, no protected artifact. Verification: item Verify command **54 passed**; full backend **4816 passed, 2 skipped, 6 xfailed, 0 failed** (delta `4797 → 4816` is exactly the 19 new tests); governance regression **PASS** (`stage3_governance_regression: PASS`, exit 0) with harness 6/6, dual parity `120 exact / 0 approved / 0 critical`, clean-answer `120 pass / 0 review / 0 fail / 0 critical`, Cisco `PASS=50 / REVIEW=0 / FAIL=0 / CRITICAL=0`, dispatch matrix `5/5`, SPL templates 17/17 no drift, 6/6 probes; reference probes **10/10** matching the frozen baseline. Manifest `protected artifacts unchanged (13 checked)`; plan audit `0 gap(s)`. Invariant check 7/7 PASS: no `call_tool`/`splunk_run_query`/`execution_eligible`/`normalized_spl` lines in the diff, no secrets, `app/demo/` untouched, no new flag or settings read, no state-channel addition, no test weakened, and every deletion `route_setup`-scoped. Governance regenerated the same five `docs/evals/` reports as at P0; the observed-output deltas (parity rows 112–113 `contract_answer_mode`, `enabled_sections`, `mitre_technique_ids`, `mitre_answer_visible`) were reproduced **identically with the A0 diff stashed at baseline**, so they are host-environment churn, not an A0 behavior change, and the files were reverted. Commit: `03b333b`.
  - **Invariant / manifest:** Full invariant check; prove four specialists and no dispatch/authority change.
  - **Commit boundary:** One topology/test commit; no decision-record, planning, or scheduling edits.
  - **Stop:** Builder internals do not expose stable fixed/branch data; a second node is unexpectedly orphaned; removing `route_setup` changes any parity probe; dynamic Send needs framework internals rather than direct contract invocation.

- [x] **A1.1 — Inventory every decision-record reference and enforce the state-channel vocabulary**
  - **Do:** Add `backend/app/tests/test_resource_planner_decision_record_io.py` (**NEW**). Inventory every remaining Resource Planner record shape after A0, including specialist records and rejection paths. For each record, document actual read roots, write roots, and declared refs in a test-owned expected table. Validate every declared root against `ResourcePlannerGraphState.__annotations__`; allow a dotted path only when its root is a real channel and validate the nested path on representative data. Correct nonexistent-channel labels such as root `normalized_spl` to the real nested channel. Keep refs descriptive only—no code may consume them for scheduling.
  - **Why:** Schema-valid labels are the minimum mechanical prerequisite before judging semantic truth.
  - **Surfaces:** `backend/app/graph/resource_planner_graph.py`; `backend/app/chat/decision_record.py`; new test; `backend/app/tests/test_decision_record.py`.
  - **Depends on:** A0.
  - **Failing-first / observation:** The new inventory test must initially fail on `normalized_spl` and any other nonexistent/dangling path discovered; paste the complete inventory into Evidence.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_resource_planner_decision_record_io.py app/tests/test_decision_record.py app/tests/test_planner_hierarchy_contracts.py app/tests/test_state_channel_parity.py -q`; root manifest check and plan audit as in A0.
  - **Evidence:** **COMPLETE 2026-08-10; runtime commit `a435d8a`.** Added test-owned `EXPECTED_RECORD_IO` in `backend/app/tests/test_resource_planner_decision_record_io.py`, covering all **24** post-A0 shapes (20 direct declarations + four specialist records), with separately documented actual read roots, actual write roots, and emitted refs. Failing-first: new slice returned **1 failed, 3 passed**; the sole invalid declaration was `mcp_execution_gate` root `normalized_spl`. Corrected only its descriptive label to `spl_validation.normalized_spl`; no state channel or runtime dependency was added. Final vocabulary result: **zero invalid roots, zero dangling dotted paths**, with `evidence_plan.resource_plan` and `spl_validation.normalized_spl` resolved against representative data; a static negative assertion found zero runtime consumers of `inputs_ref`/`outputs_ref`. Exact Verify slice: **32 passed**. Manifest: `protected artifacts unchanged (13 checked)`. Invariant: **7/7 PASS** — no MCP/LLM/SPL authority, demo, secret, state-channel, flag, port, or test-honesty change. Semantic mismatches intentionally remain declared as inventory inputs for A1.2 rather than being corrected in this schema-only commit.

    | Record shape | Actual read roots | Actual write roots | Declared inputs → outputs after A1.1 |
    |---|---|---|---|
    | `work_bundle.apply` | `validated_work_bundle` | none | `validated_work_bundle` → `evidence_plan` |
    | `specialist.skill` | `routed`, `canonical_planning_input` | `specialist_reports` | `routed` → `specialist_reports` |
    | `specialist.knowledge` | `intent_classification`, `evidence_plan` | `specialist_reports` | `evidence_plan` → `specialist_reports` |
    | `specialist.mcp` | `evidence_plan` | `specialist_reports` | `evidence_plan` → `specialist_reports` |
    | `specialist.spl` | `evidence_plan` | `specialist_reports` | `evidence_plan` → `specialist_reports` |
    | `bootstrap` | `request` | `evidence_plan`, `query_to_intent`, `canonical_planning_input` | `request` → `evidence_plan`, `query_to_intent`, `canonical_planning_input` |
    | `route_resolution` | `routed`, `evidence_plan` | `route_contract`, `planning_decision` | `routed`, `evidence_plan` → `route_contract`, `planning_decision` |
    | `resource_planner.delegate` | `evidence_plan` | `specialist_delegations` | `evidence_plan` → `specialist_delegations` |
    | `resource_planner.merge` | `specialist_reports`, `specialist_delegations`, `evidence_plan` | `work_bundle`, `validated_work_bundle`, `planner_iteration`, `evidence_plan` | `specialist_reports`, `evidence_plan.resource_plan` → `work_bundle`, `planner_iteration` |
    | `non_planned_finalize` | `canonical_planning_outcome` | `plan_dispatch_trace` | `canonical_planning_outcome` → `plan_dispatch_trace` |
    | `prepare_rag_only` | `validated_work_bundle`, `evidence_plan` | `evidence_plan`, `execution` | `evidence_plan` → `execution` |
    | `rag_early` | `evidence_plan` | `soc_kb_retrieval` | `evidence_plan` → `soc_kb_retrieval`, `source_evidence` |
    | `composed_dispatch` | `validated_work_bundle`, `evidence_plan` | `evidence_plan`, `candidate_spl`, `spl_validation`, `execution` | `validated_work_bundle`, `evidence_plan.resource_plan` → `candidate_spl`, `spl_validation`, `execution` |
    | `workflow_spl` | `validated_work_bundle`, `evidence_plan` | `evidence_plan`, `candidate_spl`, `spl_validation` | `validated_work_bundle` → `candidate_spl`, `spl_validation` |
    | `spl_source_resolve` | `candidate_spl`, `spl_validation` | `spl_validation` | `candidate_spl` → `spl_validation` |
    | `mcp_execution_gate` | `spl_validation` | `execution`, `human_review` | `spl_validation`, `spl_validation.normalized_spl` → `execution`, `human_review` |
    | `spl_validate` | `spl_validation` | `spl_validation` | `candidate_spl` → `spl_validation` |
    | `context_sufficiency` | `context_sufficiency` | `context_sufficiency` | `source_evidence` → `context_sufficiency` |
    | `decide_facts` | none | none | `mitre_decision`, `severity_decision` → `severity_decision`, `mitre_mappings` |
    | `answer_guard` | none | none | `answer_contract` → `answer_guard` |
    | `finalize` | `structured_context`, `source_evidence` | `response`, `context_sufficiency`, `severity_decision` | `structured_context`, `source_evidence` → `response`, `context_sufficiency`, `severity_decision` |
    | `validate_final_answer` | `response`, `answer_contract`, `evidence_plan`, `mitre_decision`, `human_review`, `planning_decision` | `final_answer_validation`, `response` | `response`, `answer_contract` → `final_answer_validation` |
    | `human_review` | `human_review` | `human_review` | `execution` → `human_review` |
    | `policy_veto` | `evidence_plan`, `execution`, `spl_validation` | `policy_veto`, `execution`, `spl_validation` | `evidence_plan` → `policy_veto`, `execution`, `human_review`, `spl_validation` |
  - **Invariant / manifest:** Invariant check; assert no new state channel unless independently justified and declared on both runtime paths.
  - **Commit boundary:** Schema/inventory commit only; semantic output corrections belong to A1.2.
  - **Stop:** A ref requires secret/raw payload exposure; tests would infer I/O from node names; validation would become a runtime dependency mechanism.

- [x] **A1.2 — Correct semantic inputs/outputs and prove representative node dataflow**
  - **Do:** Trace each record to actual function reads/writes and correct false labels, including but not limited to `work_bundle.apply`, `rag_early`, `mcp_execution_gate`, `decide_facts`, `answer_guard`, and `policy_veto`. Add representative differential tests that call each wrapper with sentinel state/monkeypatched pure workers, compare pre/post root channels excluding `decision_log`/`rp_graph_trace`, and assert declared outputs are genuinely produced by the logical node. Empty output lists are valid for trace-only nodes. Specialist records may name the specialist report their logical node produced, but the test must observe that producer directly. Do not turn refs into execution dependencies.
  - **Why:** Existing labels overclaim dataflow and cannot safely support architecture review or later telemetry.
  - **Surfaces:** same graph/test files as A1.1; worker wrappers in `backend/app/chat/pipeline.py` are read anchors, not refactor targets unless a false label cannot otherwise be corrected.
  - **Depends on:** A1.1.
  - **Failing-first / observation:** Record failures proving the known overclaims before correction. Negative controls must fail when a nonexistent output is added to a record.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_resource_planner_decision_record_io.py app/tests/test_resource_planner_dry_runs.py app/tests/test_resource_planner_route_wiring.py app/tests/test_control_plane_trace.py app/tests/test_resource_planner_validated_work_bundle.py -q`; root manifest check and plan audit.
  - **Evidence:** **COMPLETE 2026-08-10; runtime commit `7f9121a`.** Failing-first semantic assertion returned **1 failed** with eight explicit overclaiming shapes: `work_bundle.apply` output `evidence_plan`; `rag_early` output `source_evidence`; `spl_validate` input `candidate_spl`; `context_sufficiency` input `source_evidence`; all claimed I/O on trace-only `decide_facts` and `answer_guard`; `human_review` input `execution`; and `policy_veto` output `human_review`. Completing the full source trace also corrected the stale route-tail, delegation, merge, worker-application, finalize, validator, and specialist labels rather than limiting the fix to those eight examples. Per-record changes: `work_bundle.apply` output `evidence_plan→[]`; `specialist.skill` input `routed→routed+canonical_planning_input`; `specialist.knowledge` input `evidence_plan→intent_classification+evidence_plan`; `route_resolution` inputs `routed+evidence_plan→routed+route_plan_shadow`, outputs `route_contract+planning_decision→route_plan_shadow+llm_plan_validation+skill_selection+selected_skill_chain`; delegate input `evidence_plan→[]`; merge added input `specialist_delegations` and outputs `validated_work_bundle+evidence_plan`; `prepare_rag_only` added input `validated_work_bundle` and output `evidence_plan`; `rag_early` input `evidence_plan→workflow_plan`, output `soc_kb_retrieval+source_evidence→soc_kb_retrieval`; composed dispatch added output `evidence_plan`; workflow SPL added input/output `evidence_plan`; SPL source resolve added input `spl_validation`; SPL validate input `candidate_spl→spl_validation`; context sufficiency input `source_evidence→context_sufficiency`; decide-facts and answer-guard refs became empty; finalize inputs `structured_context+source_evidence→evidence_plan+execution+soc_kb_retrieval+spl_validation`; final validator added its four actual decision inputs and response write; human-review input `execution→human_review`; policy-veto added `execution+spl_validation` inputs and removed false `human_review` output. `bootstrap`, `non_planned_finalize`, both MCP/SPL specialist records, and the A1.1-corrected MCP-gate nested ref required no semantic change. Representative differential coverage calls every direct wrapper with sentinel state/narrow pure-worker stubs, compares pre/post business roots excluding `decision_log`/`rp_graph_trace`, directly observes all four specialist producers, permits empty outputs only for trace-only nodes, and includes a mutation-negative `nonexistent_output` assertion that fails as intended. Exact host-reachable Verify slice: **47 passed, 2 warnings in 8.77s**. Zero secret/raw refs; refs remain descriptive with zero scheduler consumers. Manifest **13/13**; invariant **7/7 PASS**; no topology, scheduler, LLM, SPL/MCP gate, HIL, RBAC, state-channel, flag, or authority change.
  - **Invariant / manifest:** Full invariant check; telemetry/redaction and append-only decision-log behavior stay unchanged.
  - **Commit boundary:** One decision-record correctness commit; no topology/scheduler/LLM edits.
  - **Stop:** A correct record would require moving authority or adding runtime writes solely to satisfy telemetry; same differential gate fails twice.

- [x] **B0 — Observe one bounded live-core T4 planning path**
  - **Do:** Observation only, in two stages. **B0 preflight — deterministic only:** use `understand_query()`, `extract_query_signals()`, `initial_tier_for_match_path()`, `processing_lane_for_initial_tier()`, and `bridge_trigger_match()` without invoking the graph or any LLM; require initial tier T4, processing lane `guided`, bridge eligibility, no explicit execution request, and no destructive/action intent. Treat `guided` as the processing-lane assertion—not a requirement that the lower-level deterministic route helper return the `guided_investigation` skill. **B0 observation — exactly one full graph call:** only after preflight passes, create a temporary/non-production diagnostic wrapper (prefer `/tmp`; if reusable, it must have zero production importers) that instruments the shadow planner's module-local `resource_plan_shadow.propose_validated_llm_plan` bridge path. Inject a counting proxy around the actual client returned for that proposal, increment only `shadow_bridge_generate_attempts`, and delegate unchanged; do not patch a generic/global client `generate()` used by other LLM roles. Invoke `run_resource_planner_graph(ChatRequest(...))` exactly once with the preflighted query and live synthesis left enabled. Emit only sanitized JSON: shadow bridge attempt count; `evidence_plan.resource_plan.provenance.llm_bridge`; `control_plane_trace.resource_plan_shadow`; `rp_graph_trace.visited_nodes`; deterministic plan source and before/after step fingerprints; promotion/discard result; safe budget role/outcome/latency; elapsed time. Do not print prompts, completions, credentials, endpoint URLs, SPL, or raw evidence.
  - **Why:** Static reachability cannot prove whether a real shadow request occurs, returns a plan, is promoted, or is discarded.
  - **Surfaces:** temporary probe; `backend/app/planner/resource_plan_shadow.py`; `llm_plan_bridge.py`; `pipeline.py` finalize trace; `resource_planner_graph.py` entrypoint. No production edit.
  - **Depends on:** A1.2.
  - **Failing-first / observation:** Use query `Investigate suspicious authentication behavior across identity and endpoint telemetry; identify what evidence would be needed, but do not run or modify anything.` Run deterministic preflight first. If its initial tier is not T4, its processing lane is not `guided`, it is not bridge-eligible, it requests execution, or it is action/containment-shaped, record the contradiction and stop before any full graph invocation; do not try a query ladder.
  - **Verify:** Export the host DB URL for the whole probe. Run `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=backend:. python3 /tmp/plan2_observe_t4_planning.py --preflight-only | tee /tmp/plan2-t4-planning-preflight.json`; validate with `python3 -m json.tool /tmp/plan2-t4-planning-preflight.json` and `jq -e '.initial_tier == "T4" and .processing_lane == "guided" and .bridge_trigger_eligible == true and .run_execution == false and .explicit_run_spl == false and .block_or_contain == false and .action_or_containment_shaped == false' /tmp/plan2-t4-planning-preflight.json`. Only if that passes, run `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=backend:. python3 /tmp/plan2_observe_t4_planning.py --observe | tee /tmp/plan2-t4-planning-observation.json`; validate sanitization and required keys with `python3 -m json.tool /tmp/plan2-t4-planning-observation.json` and `jq -e '.shadow_bridge_generate_attempts >= 0 and (.rp_graph_trace.visited_nodes|type=="array") and (.resource_plan_shadow|type=="object") and (.elapsed_ms|type=="number")' /tmp/plan2-t4-planning-observation.json`; re-run the manifest check. The exact temporary script body must be pasted into Evidence before execution so review can confirm deterministic-only preflight, one graph call, shadow-specific delegation, and allowlisted output.
  - **Evidence:** **PRE-EXECUTION WRAPPER REVIEW 2026-08-10.** The exact temporary script below was syntax-checked but has not yet run preflight or invoked the graph. SHA-256: `fae9a245a05bee94dda6e2eb2131566b76381f2c7b51658a981854d104d05918`. Review: preflight imports/calls only deterministic classification helpers; `--observe` refuses a failed preflight; the script contains exactly one `run_resource_planner_graph(...)` call; it wraps only `resource_plan_shadow.propose_validated_llm_plan`, supplies a counting proxy around the actual `_bridge_client()` returned for that proposal, and delegates `generate()` unchanged; the additional pipeline shadow-run wrapper records only pre/post structural hashes. Stdout is an allowlisted JSON object containing no prompt, completion, credentials, endpoint, SPL, query text, or raw evidence.

    ```python
    /root/.bashrc: line 5: # ~/.bashrc: executed by bash(1) for non-login shells.
    # see /usr/share/doc/bash/examples/startup-files (in the package bash-doc)
    # for examples

    # If not running interactively, dont: No such file or directory
    #!/usr/bin/env python3
    """One-shot, sanitized Plan 2 B0 T4 shadow-planning observation."""

    from __future__ import annotations

    import argparse
    import contextlib
    import hashlib
    import json
    import sys
    import time
    from typing import Any

    QUERY = (
        "Investigate suspicious authentication behavior across identity and endpoint telemetry; "
        "identify what evidence would be needed, but do not run or modify anything."
    )


    def _json(payload: dict[str, Any]) -> None:
        print(json.dumps(payload, sort_keys=True, separators=(",", ":")))


    def deterministic_preflight() -> dict[str, Any]:
        # Keep import/config diagnostics off stdout so the tee target is one JSON object.
        with contextlib.redirect_stdout(sys.stderr):
            from app.chat.lane_router import (
                initial_tier_for_match_path,
                processing_lane_for_initial_tier,
            )
            from app.chat.query_signals import extract_query_signals
            from app.planner.llm_plan_bridge import bridge_trigger_match
            from app.query_understanding.parser import understand_query

            query_understanding = understand_query(QUERY)
            signals = extract_query_signals(QUERY, query_understanding)
            match_path = str(query_understanding.deterministic_match_path or "")
            initial_tier = initial_tier_for_match_path(match_path)
            processing_lane = processing_lane_for_initial_tier(initial_tier)

        return {
            "initial_tier": initial_tier,
            "processing_lane": processing_lane,
            "match_path": match_path,
            "bridge_trigger_eligible": bool(bridge_trigger_match(match_path)),
            "run_execution": bool(signals.get("run_execution")),
            "explicit_run_spl": bool(signals.get("explicit_run_spl")),
            "block_or_contain": bool(signals.get("block_or_contain")),
            "action_or_containment_shaped": bool(
                signals.get("action_or_containment_shaped")
            ),
        }


    def _preflight_passed(payload: dict[str, Any]) -> bool:
        return bool(
            payload.get("initial_tier") == "T4"
            and payload.get("processing_lane") == "guided"
            and payload.get("bridge_trigger_eligible") is True
            and payload.get("run_execution") is False
            and payload.get("explicit_run_spl") is False
            and payload.get("block_or_contain") is False
            and payload.get("action_or_containment_shaped") is False
        )


    def _step_fingerprint(evidence_plan: dict[str, Any] | None) -> dict[str, Any] | None:
        if not isinstance(evidence_plan, dict):
            return None
        plan = evidence_plan.get("resource_plan")
        if not isinstance(plan, dict):
            return None
        steps = plan.get("steps")
        safe_steps = []
        if isinstance(steps, list):
            for step in steps:
                if not isinstance(step, dict):
                    continue
                safe_steps.append(
                    {
                        "step_id": str(step.get("step_id") or ""),
                        "resource_id": str(step.get("resource_id") or ""),
                        "purpose": str(step.get("purpose") or ""),
                        "status": str(step.get("status") or ""),
                    }
                )
        encoded = json.dumps(safe_steps, sort_keys=True, separators=(",", ":")).encode()
        return {
            "step_count": len(safe_steps),
            "sha256": hashlib.sha256(encoded).hexdigest(),
        }


    def _safe_shadow_trace(raw: Any) -> dict[str, Any]:
        if not isinstance(raw, dict):
            return {}
        allowed = (
            "shadow_only",
            "promotion_blocked",
            "llm_called",
            "deterministic_plan_source",
            "skipped_reason",
            "shadow_plan_source",
            "shadow_step_count",
            "live_plan_source_unchanged",
        )
        return {key: raw.get(key) for key in allowed if key in raw}


    def _safe_budget_record(state: dict[str, Any]) -> dict[str, Any]:
        budget = state.get("llm_turn_budget")
        records = getattr(budget, "records", None)
        if not isinstance(records, list):
            return {
                "role": "route_plan_candidate_generator",
                "outcome": "not_recorded",
                "latency_ms": None,
            }
        for record in reversed(records):
            if (
                isinstance(record, dict)
                and record.get("role") == "route_plan_candidate_generator"
            ):
                return {
                    "role": "route_plan_candidate_generator",
                    "outcome": str(record.get("outcome") or "unknown"),
                    "latency_ms": (
                        int(record["latency_ms"])
                        if isinstance(record.get("latency_ms"), (int, float))
                        else None
                    ),
                }
        return {
            "role": "route_plan_candidate_generator",
            "outcome": "not_recorded",
            "latency_ms": None,
        }


    def observe_once(preflight: dict[str, Any]) -> dict[str, Any]:
        if not _preflight_passed(preflight):
            raise RuntimeError("deterministic_preflight_failed")

        observed: dict[str, Any] = {
            "shadow_bridge_generate_attempts": 0,
            "step_fingerprint_before": None,
            "step_fingerprint_after": None,
            "shadow_result": {},
        }

        with contextlib.redirect_stdout(sys.stderr):
            from app.chat import pipeline
            from app.graph.resource_planner_graph import run_resource_planner_graph
            from app.planner import llm_plan_bridge, resource_plan_shadow
            from app.schemas.requests import ChatRequest

            original_propose = resource_plan_shadow.propose_validated_llm_plan
            original_shadow_run = pipeline.run_resource_plan_shadow

            class ShadowBridgeClientProxy:
                def __init__(self, delegate: Any) -> None:
                    self._delegate = delegate

                def generate(self, **kwargs: Any) -> Any:
                    observed["shadow_bridge_generate_attempts"] += 1
                    return self._delegate.generate(**kwargs)

                def __getattr__(self, name: str) -> Any:
                    return getattr(self._delegate, name)

            def instrumented_propose(**kwargs: Any) -> Any:
                actual_client = kwargs.get("client") or llm_plan_bridge._bridge_client()
                if actual_client is None:
                    raise RuntimeError("shadow_bridge_client_unavailable_for_instrumentation")
                return original_propose(
                    **{**kwargs, "client": ShadowBridgeClientProxy(actual_client)}
                )

            def instrumented_shadow_run(**kwargs: Any) -> Any:
                observed["step_fingerprint_before"] = _step_fingerprint(
                    kwargs.get("evidence_plan")
                )
                result = original_shadow_run(**kwargs)
                observed["step_fingerprint_after"] = _step_fingerprint(
                    kwargs.get("evidence_plan")
                )
                observed["shadow_result"] = _safe_shadow_trace(result.to_trace_dict())
                return result

            resource_plan_shadow.propose_validated_llm_plan = instrumented_propose
            pipeline.run_resource_plan_shadow = instrumented_shadow_run

            started = time.monotonic()
            # The only full graph invocation in this script.
            state = run_resource_planner_graph(ChatRequest(message=QUERY))
            elapsed_ms = int((time.monotonic() - started) * 1000)

        evidence_plan = state.get("evidence_plan")
        resource_plan = (
            evidence_plan.get("resource_plan")
            if isinstance(evidence_plan, dict)
            else None
        )
        provenance = (
            resource_plan.get("provenance")
            if isinstance(resource_plan, dict)
            and isinstance(resource_plan.get("provenance"), dict)
            else {}
        )
        response = state.get("response")
        control_plane_trace = getattr(response, "control_plane_trace", None)
        trace_shadow = (
            control_plane_trace.get("resource_plan_shadow")
            if isinstance(control_plane_trace, dict)
            else None
        )
        safe_shadow = _safe_shadow_trace(trace_shadow) or dict(observed["shadow_result"])
        bridge_value = provenance.get("llm_bridge")
        if bridge_value == "promoted":
            promotion_result = "promoted_inline"
        elif safe_shadow.get("llm_called") and safe_shadow.get("promotion_blocked"):
            promotion_result = "discarded_shadow_only"
        elif safe_shadow.get("skipped_reason"):
            promotion_result = f"skipped:{safe_shadow['skipped_reason']}"
        else:
            promotion_result = "no_valid_shadow_proposal"

        return {
            "shadow_bridge_generate_attempts": int(
                observed["shadow_bridge_generate_attempts"]
            ),
            "evidence_plan_resource_plan_provenance_llm_bridge": (
                str(bridge_value) if bridge_value is not None else None
            ),
            "resource_plan_shadow": safe_shadow,
            "rp_graph_trace": {
                "visited_nodes": [
                    str(item)
                    for item in (state.get("rp_graph_trace") or {}).get(
                        "visited_nodes", []
                    )
                ]
            },
            "deterministic_plan_source": (
                str(resource_plan.get("plan_source") or "")
                if isinstance(resource_plan, dict)
                else None
            ),
            "step_fingerprint_before": observed["step_fingerprint_before"],
            "step_fingerprint_after": observed["step_fingerprint_after"],
            "shadow_plan_returned": bool(safe_shadow.get("shadow_step_count")),
            "promotion_or_discard_result": promotion_result,
            "budget": _safe_budget_record(state),
            "elapsed_ms": elapsed_ms,
        }


    def main() -> int:
        parser = argparse.ArgumentParser()
        mode = parser.add_mutually_exclusive_group(required=True)
        mode.add_argument("--preflight-only", action="store_true")
        mode.add_argument("--observe", action="store_true")
        args = parser.parse_args()

        preflight = deterministic_preflight()
        if args.preflight_only:
            _json(preflight)
            return 0
        _json(observe_once(preflight))
        return 0


    if __name__ == "__main__":
        raise SystemExit(main())
    ```

    **OBSERVED ONCE 2026-08-10; no retry and no runtime commit.** Deterministic preflight JSON: `{"action_or_containment_shaped":false,"block_or_contain":false,"bridge_trigger_eligible":true,"explicit_run_spl":false,"initial_tier":"T4","match_path":"out_of_registry","processing_lane":"guided","run_execution":false}`; both `json.tool` and the exact `jq -e` predicate passed before observation. With final/live synthesis left enabled and the host DB override exported without echo, the script then made exactly one full `run_resource_planner_graph(...)` call. Sanitized observation: `shadow_bridge_generate_attempts=0`; live `evidence_plan.resource_plan.provenance.llm_bridge=null`; shadow trace `{"llm_called":false,"skipped_reason":"draft_spl_preview_active"}`; deterministic plan source `deterministic`; no shadow plan returned; result `skipped:draft_spl_preview_active`; before/after shadow step fingerprints both `null` because the shadow runner was skipped before entry; route-plan budget record `outcome=not_recorded`, `latency_ms=null`; total graph elapsed **954 ms**. Visited nodes, in order: `bootstrap`, `route_resolution`, `resource_planner_delegate`, all four specialists, `resource_planner_merge`, `composed_dispatch`, `spl_validate`, `mcp_execution_gate`, `context_sufficiency`, `decide_facts`, `answer_guard`, `human_review`, `policy_veto`, `finalize`, `validate_final_answer`. Required-key `jq` validation passed with the stronger `attempts<=1` assertion; a negative scan confirmed the JSON artifact contains no URL, host, prompt, completion, credential/key/token/password, candidate/normalized SPL, or raw-evidence field. Existing non-shadow local-client diagnostics wrote two DNS failures to stderr (including a configured local endpoint); they were not captured by `tee`, contained no credential, and the shadow-specific proxy correctly did not count them. Manifest: `protected artifacts unchanged (13 checked)`. This observation proves **zero shadow-bridge model cost on this one `out_of_registry` turn because draft-preview gating skipped the runner**; it does not price a returned/promoted/discarded shadow plan, `qu_unavailable`, `semantic_out_of_registry`, `query_understanding_weak`, `near_105_question`, or other flag/budget/draft-preview postures. The observation can distinguish attempted from skipped: proxy count 0 plus the explicit finalize skip reason and absent budget record.
  - **Invariant / manifest:** No runtime diff. If a reusable diagnostic script is committed, run invariant/redaction review and commit it separately.
  - **Commit boundary:** Evidence-only plan update; normally no code commit.
  - **Stop:** Deterministic preflight fails; the full graph is invoked before preflight passes; instrumentation patches a generic/global LLM method or cannot isolate the shadow planner bridge role; probe would need destructive execution; more than one shadow bridge attempt; final/live synthesis would need disabling; output contains sensitive data; evidence cannot distinguish attempted call from a skipped call.

- [x] **B1 — COE decision: RETIRE or RE-WIRE planning/discovery architecture**
  - **Do:** Present B0 evidence, the three-surface planning inventory (fenced bridge, discard-only shadow runner, imperative guided-hybrid proposer), cost/latency, and the two options in this plan. The user/COE fills every required B1 decision field, including guided-rail disposition and, for RE-WIRE, per-match-path trigger coverage plus both guided-promotion exclusions. Note for the approver that either rail disposition also strands two dependent surfaces — the *inverted* `ai_soc_guided_llm_enabled` proposer gate (whose three budget/deadline consumers survive either way) and the `guided_investigation_plan_llm` dispatch-step label. The default executor disposition is retain-the-flag-for-budget-scope-only plus an explicit label decision, handled inside B2-R2/B2-W2; escalate to this gate only if a coherent outcome would require renaming, repurposing, or deleting the flag. Do not infer coverage for `qu_unavailable` from B0's single `out_of_registry` observation. Do not implement either branch. Disposition the rejected B2 branch N/A.
  - **Why:** This changes intended architecture and cannot be selected by an executor.
  - **Surfaces:** this plan only.
  - **Depends on:** B0.
  - **Failing-first / observation:** Decision gate; no code.
  - **Verify:** After the decision edit, run `rg -n 'selected_posture.*(RETIRE|RE-WIRE)|approved_by|approved_at|B0_evidence_reference|guided_hybrid_llm_rail_disposition|bridge_trigger_match_paths|guided_promotion_policy' plans/2026-08-10_1103_architecture-resource-plan-execution-and-adaptive-planning.md` and the plan-discipline audit.
  - **Evidence:** **DECIDED 2026-08-10.** `selected_posture: RETIRE`, `approved_by: Anurag`, `approved_at: 2026-08-10T17:29:24Z`, `B0_evidence_reference` = B0 evidence at `e99fe0b`. `guided_hybrid_llm_rail_disposition: RETIRE_PROPOSER`. Rationale: deterministic canonical planning stays the production authority; the rails are retired for being fragmented/non-authoritative/discard-only/parallel authorities, not because adaptive planning is rejected — a future adaptive design is to be a single seam above the deterministic floor. Eight approved dispositions recorded in the B1 decision block, including retain `ai_soc_guided_llm_enabled` for budget/deadline scope only, remove the `guided_investigation_plan_llm` label after consumer verification, retire fenced bridge/shadow and legacy discovery only after consumer proof, retain live dispatch-v2 pre-SPL discovery and the four-specialist advisory layer, and no MCP/SPL/HIL/RBAC or execution-authority expansion. **N/A disposition count: 4** — `bridge_trigger_match_paths`, `guided_promotion_policy`, the `RE-WIRE` flag/scope/budget/discovery field set, and the entire B2-W1…B2-W7 branch. Approver acknowledged that B0 recorded zero shadow attempts, so it evidences neither shadow latency nor `qu_unavailable` coverage; `RETIRE` does not rest on either. Approved order: `B2-R1 → B2-R2 → B2-R3 → B2-R4`, then stop at C0. No runtime change; invariant/manifest N/A. Commit: `a19fec4`.
  - **Invariant / manifest:** N/A; no runtime change.
  - **Commit boundary:** Optional plan-only decision commit; no runtime files.
  - **Stop:** No explicit choice; guided-hybrid proposer is left as a parallel/undispositioned authority; incomplete RE-WIRE discovery/flag/budget/match-path/promotion semantics; trigger scope and guided promotion policy contradict each other; decision conflicts with locked invariants.

- [x] **B2-R1 — RETIRE: pin deterministic canonical behavior and the live pre-SPL boundary**
  - **Do:** If RETIRE selected, add `backend/app/tests/test_retired_resource_planning_surfaces.py` (**NEW**) with exact canonical plan/dispatch fingerprints across T0–T4, a static/call-count inventory of all three planning surfaces in both runtimes, explicit proof the legacy loop is not visited, and explicit proof dispatch-v2 pre-SPL discovery still feeds the compiler/saved-search preference when authorized. Capture deterministic guided dispatch/validation/collection behavior separately from the guided LLM proposer. Add negative controls that fail if those mechanisms are conflated. **R1 pins the current pre-retirement state and must finish fully green.** Express the planning-surface inventory as a single named expected-state contract (for example a `PLANNING_SURFACE_EXPECTATION` table the assertions read) so R2 can flip it from present-and-counted to absent in one reviewable edit. Do **not** commit an assertion whose expected production state belongs to R2 — post-retirement absence is R2's contract, not R1's. Demonstrate falsifiability here by mutation or temporary local assertion, recorded in Evidence and reverted before commit.
  - **Why:** Cleanup cannot begin without separate tripwires for what must be retired and what must remain live — but a tripwire committed red is indistinguishable from a broken suite, and the plan forbids landing a knowingly failing test.
  - **Surfaces:** new test; current resource-plan, shadow, guided proposer/hybrid, evidence-loop, and dispatch-v2 tests.
  - **Depends on:** B1=`RETIRE`.
  - **Failing-first / observation:** New test must capture current shadow call, fenced bridge, direct imperative guided proposer, legacy fence, deterministic guided behavior, and live pre-SPL distinction before removal. Falsifiability is proven against the **pinned current state** — each assertion must fail under a mutation that conflates the three surfaces, removes a live pre-SPL symbol, changes a deterministic fingerprint, or misreports a planning-surface call count. Record those mutation failures in Evidence, then revert them; the committed suite is green.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_retired_resource_planning_surfaces.py app/tests/test_resource_plan_shadow.py app/tests/test_guided_investigation_plan_llm.py app/tests/test_guided_investigation_llm_firewall.py app/tests/test_guided_hybrid_collection.py app/tests/test_evidence_loop_graph.py app/tests/test_dispatch_authority_wiring.py app/tests/test_pipeline_dispatch_phase4.py app/tests/test_pipeline_dispatch_phase5.py app/tests/test_pipeline_dispatch_phase6.py -q` — must be fully green, zero failures and zero `xfail`/`skip` standing in for R2 work; manifest check.
  - **Evidence:** **COMPLETE 2026-08-10 at `176a520`.** New `backend/app/tests/test_retired_resource_planning_surfaces.py`, **19 tests, all green, zero skips**. Named expected-state contract `PLANNING_SURFACE_EXPECTATION` holds all three surfaces; `RETAINED_SURFACE_EXPECTATION` holds what R3 must not touch. Three-surface inventory as observed: (1) **shadow** — `run_resource_plan_shadow` present, call site present, *is invoked* on some canonical turns (e.g. the 105 query) but `llm_called=False` with `skipped_reason=shadow_disabled`, and `live_plan_source_unchanged=True`, so zero model hops and a discarded result; (2) **inline bridge** — `apply_llm_primary_resource_plan` present with a call site, but its enclosing function is `graph_node_evidence_planning` (proved by AST, not proximity), which is fenced, so **0 calls on canonical turns in both runtimes**; (3) **guided proposer** — `propose_investigation_plan_llm` present inside `_run_guided_hybrid_dispatch` behind the inverted gate, pinned by source ordering (gate < reserved branch < call), with `proposer_gate_consumers=1` and `GUIDED_FLAG_BUDGET_CONSUMERS=3` scoped to `pipeline.py` + `llm/guided_llm_budget.py` only. Call counts patch **pipeline module globals**, since `pipeline.py` binds all three symbols by from-import — patching the defining modules counts nothing. Guided-proposer versus guided-execution distinction: negative control asserts `guided_investigation_planner`, `guided_capability_validator`, `planner/composer`, and `guided_hybrid_collection` never import the proposer, plus a gate test showing the deterministic precondition `investigation_planning_enabled` alone opens/closes the rail. Live pre-SPL: `graph_node_pre_spl_mcp_discovery` pinned permanently present. Legacy fence pinned via `canonical_planning_failure.reason == canonical_forbids_legacy_evidence_planning`. **Mutation log** (each flip run alone, then reverted): M1 shadow `symbol_present`→False **1 failed**; M2 bridge `call_site_present`→False **2 failed**; M3 `flag_gates_proposer`→False **1 failed**; M4 `proposer_gate_consumers` 1→0 **1 failed**; M5 shadow `model_called_on_canonical_turn`→True **2 failed**; M6 bridge `reachable_on_canonical_turn`→True **2 failed**; M7 retained pre-SPL `symbol_present`→False **1 failed**. M2/M3 initially *skipped* rather than failed — a skipped tripwire is indistinguishable from a passing one, so both retired-state branches were rewritten to assert absence and re-verified red. Revert proved byte-identical by `diff`. Verify command **77 passed**, zero failures, zero xfail/skip. Manifest `13/13`; invariant check 7/7 PASS (tests-only diff, no runtime file touched). Commit: `176a520`.
  - **Invariant / manifest:** Full invariant check; no runtime behavior change in this test-first commit.
  - **Commit boundary:** Tests only, pinning current state; no expected-state assertion that only passes after R2.
  - **Stop:** Live pre-SPL discovery cannot be isolated; current canonical output differs from P0; the suite cannot be made green without either changing runtime behavior (that is R2) or weakening an assertion.

- [x] **B2-R2 — RETIRE: remove the discarded shadow call and unreachable promotion surfaces**
  - **Do:** Remove the real shadow model call from canonical finalize and replace only any required trace compatibility with an explicit deterministic `retired`/`not_called` posture. Inventory all callers before removing `resource_plan_shadow.py`, the unreachable inline bridge application, promotion merge, or tests. Apply B1=`RETIRE_PROPOSER` to the imperative guided-hybrid rail: remove its direct `propose_investigation_plan_llm` call and dedicated proposer authority, but retain deterministic guided dispatch, committed-plan projection, Validator A/B, and evidence collection wherever consumer proof shows they remain used. Delete only surfaces proven to have no retained consumer. Preserve generic LLM client infrastructure used by other roles. Two follow-on surfaces the proposer removal exposes must be dispositioned in the same commit, not left implicit: (a) **`ai_soc_guided_llm_enabled` semantics.** Its proposer consumer is an *inverted* gate — flag true reserves the proposer with `guided_finalize_composer_reserved`, flag false calls it — so removing the `else` branch deletes the flag's only proposer meaning while its three budget/deadline consumers (`pipeline.py:967`, `pipeline.py:1045`, `guided_llm_budget.py:12`) legitimately remain. Re-verify the current consumer set by `rg`, retain the flag for budget/deadline scope, and record explicitly that it no longer gates any planning-model call; do not rename, repurpose, or delete it here. (b) **Guided dispatch-step trace compatibility.** The `dispatch_steps.append("guided_investigation_plan_llm")` emitter is gated on `llm_result.attempted`; state whether the step label is removed or pinned absent, and prove the chosen posture against trace/scorecard consumers found by `rg` — the shadow `retired`/`not_called` clause above covers the shadow runner only.
  - **Why:** RETIRE should neither spend a model hop on a discarded result nor retain a separate imperative planning authority. A flag whose name still implies planning authority, or a dispatch-step label that outlives its producer, reintroduces exactly the documentation/runtime divergence this plan closes.
  - **Surfaces:** `pipeline.py`; `resource_plan_shadow.py`; `plan_promotion_merge.py`; `llm_plan_bridge.py`; `guided_investigation_plan_llm.py`; `guided_hybrid_executor.py` and guided validators/collection as retain-boundary anchors; related tests and trace scorecard consumers found by `rg`.
  - **Depends on:** B2-R1.
  - **Failing-first / observation:** Flip R1's named expected-state contract from present-and-counted to absent **first**, as a separate reviewable step; that edit alone must make the suite red against the un-retired runtime, proving the assertions bind. Then implement the removals until it is green again. R1's deterministic-guided and live-pre-SPL assertions stay unchanged and must never go red — a failure there means retirement overreached. Consumer inventory is mandatory before deletion.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_retired_resource_planning_surfaces.py app/tests/test_resource_plan_shadow.py app/tests/test_llm_primary_planning.py app/tests/test_llm_plan_bridge.py app/tests/test_llm_plan_bridge_promotion.py app/tests/test_guided_investigation_plan_llm.py app/tests/test_guided_investigation_llm_firewall.py app/tests/test_compose_guided_resource_plan.py app/tests/test_control_plane_trace.py app/tests/test_cisco_live_chat_contract.py -q`; production parity `--check`; manifest check.
  - **Evidence:** **COMPLETE 2026-08-10 at `3c9a685`.** **Failing-first:** flipping the R1 contract to retired, alone against the un-retired runtime, produced **10 failures**; the RETAINED assertions stayed green throughout, proving retirement did not overreach. **Consumer inventory before deletion:** shadow — production consumers were `pipeline.py` only; the **trace key** has live consumers `app/quality/llm_role_scorecard.py:97` and `app/evals/run_out_of_catalogue_scorecard.py:101`, plus EC's own sidecar in `app/demo/scenarios.py`, so the key is retained with `shadow_status="retired"` / `skipped_reason="retired_not_called"`. Bridge/promotion — sole production consumer was the fenced `graph_node_evidence_planning` call. Guided proposer — sole consumer `_run_guided_hybrid_dispatch`. **Removed:** shadow call block, `apply_llm_primary_resource_plan` + `record_planner_sidecar` call, the inverted gate and `propose_investigation_plan_llm` call, the `guided_investigation_plan_llm` dispatch label, and three now-dead imports. **Retained with reason:** `resource_plan_shadow.py`, `plan_promotion_merge.py`, `llm_plan_bridge.py` have zero production call sites but retained test consumers covering floor preservation (`merge_floor_with_promoted_never_drops_floor_steps`), budget caps (`_BRIDGE_TIMEOUT_SECONDS_CAP`), output preprocessing and composer CVE/MITRE validation — none retired by B1, so the plan's delete-only-if-no-retained-consumer rule was not met. **Flag disposition:** `ai_soc_guided_llm_enabled` consumers scoped to `pipeline.py` + `llm/guided_llm_budget.py` went **4 → 3**: proposer gate 1 → **0**, budget/deadline 3 → **3** unchanged. Not renamed, repurposed, defaulted on, or left gating a removed call. **Label disposition:** removed with its producer and pinned absent by the R1 contract. **Test dispositions (deleted, not weakened):** `test_oos_promoted_plan_addition_drives_dispatch_order` and `test_llm_unavailable_keeps_deterministic_plan` drove the bridge through the fenced node and asserted `provenance["llm_bridge"]` — subject retired, removal noted in-file; the `test_cisco_live_chat_contract.py` monkeypatch that failed if the shadow ran was dropped because no call site remains and the R1 contract pins absence structurally, which is strictly stronger. **Verification:** R2 Verify command **80 passed**; full backend **4842 passed, 2 skipped, 6 xfailed, 0 failed**; production parity **`total=120 base_105=105 exact=120 approved=0 critical=0`**; manifest `13/13`; invariant check 7/7 PASS (no MCP/SPL/execution lines, no secrets, `demo/` untouched, no new flags). **Capability gap — decided `FOLLOW_UP_REFINEMENT_DESIGN` (user, 2026-08-10):** guided investigations become **one-round**. `refinement_recommended` had exactly two sources — the deterministic baseline, which hardcodes `False` (`investigation_plan_builder.py:159`), and the retired proposal path gated on `llm_attempted` (`guided_investigation_planner.py:252`). No existing deterministic signal can justify a second round because the loop's inputs do not vary between rounds: the baseline reads the **outer** `state`, collection is idempotency-deduped via `run_idempotent_execution_step`, and `evidence` is unchanged, so round N+1 is input-identical to round N. Signals inspected and rejected: `collected_count` (returned but discarded; re-run dedupes to the same result), `validation.blocked_resources` (identical each round), `evidence_needed`/`hypotheses` (static per query), missing/empty source results (same idempotent re-run), and the refinement helpers themselves (pure functions of round + recommended). Analyst-visible: yes — repo default `ai_soc_guided_llm_enabled=False` plus the inverted gate meant the proposer *was* called in the default posture, so `refinement_rounds` goes `[0,1,2]` → `[0]` and `guided_refinement` no longer appears. `MAX_GUIDED_INVESTIGATION_ROUNDS` and the refinement contracts are **kept** as the hard safety bound and are not deleted. The missing requirement is a **round-varying planning input derived from newly collected evidence or unresolved evidence gaps**; carried into C0, not solved in R2. Commit: `3c9a685`.
  - **Invariant / manifest:** Full invariant check; deterministic plan fingerprints unchanged. Flag-group review must show no flag renamed, repurposed, defaulted on, or left gating a removed planning call.
  - **Commit boundary:** Planning-model surface retirement only — shadow call, unreachable bridge/promotion surfaces, imperative guided proposer, plus the dependent guided flag-scope and dispatch-step-label dispositions and the R1 expected-state flip. No legacy discovery deletion.
  - **Stop:** A planning consumer outside the three inventoried surfaces appears; the known guided proposer cannot be retired without an unapproved analyst-visible change; removing a surface changes deterministic plans or response authority; `ai_soc_guided_llm_enabled` would need renaming/repurposing/removal to keep its remaining consumers coherent, or the guided dispatch-step label has a consumer that cannot tolerate either disposition — both are B1 scope, not executor scope.

- [x] **B2-R3 — RETIRE: remove fenced legacy discovery/chronology and inert hop semantics**
  - **Do:** Re-inventory non-test consumers. Remove `_run_discovery_loop_imperative`, legacy `graph_node_evidence_planning` discovery/chronology/observer flow, inert `MAX_MCP_HOPS` live claims, and dedicated modules only where no retained consumer exists. Re-check that R2 removed the imperative `guided_investigation_plan_llm` proposer without classifying the still-consumed deterministic guided-hybrid executor/validators/collection as legacy discovery. Keep unrelated observer/recipe utilities if another approved path uses them. Do not touch `graph_node_pre_spl_mcp_discovery` or dispatch-v2 context.
  - **Why:** RETIRE should make canonical architecture honest without deleting the separate live discovery mechanism.
  - **Surfaces:** `pipeline.py`; `evidence_loop.py`; `linear_graph_legacy.py`; `guided_investigation_plan_llm.py` absence check; `guided_hybrid_executor.py`/guided validators/collection retention checks; observer/recipe modules and tests proven dead by inventory; dispatch-v2 tests as guard.
  - **Depends on:** B2-R2.
  - **Failing-first / observation:** Static caller test must fail while fenced legacy symbols remain and fail if any live pre-SPL symbol is removed.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_retired_resource_planning_surfaces.py app/tests/test_evidence_loop.py app/tests/test_evidence_loop_all_tier_discovery.py app/tests/test_evidence_loop_graph.py app/tests/test_evidence_loop_recipe.py app/tests/test_guided_investigation_llm_firewall.py app/tests/test_guided_hybrid_collection.py app/tests/test_mock_mcp_discovery_gating.py app/tests/test_dispatch_authority_wiring.py app/tests/test_pipeline_dispatch_phase4.py app/tests/test_pipeline_dispatch_phase5.py app/tests/test_pipeline_dispatch_phase6.py -q`; manifest check.
  - **Evidence:** **COMPLETE 2026-08-10 at `55ae6a7`.** **Consumer graph:** every evidence-loop consumer (`assess_loop`, `assess_loop_with_recipe`, `initialize_loop`, `record_execution_hop`, `record_recipe_call`) resolves inside `graph_node_evidence_planning` or `graph_node_mcp_call`, and `graph_node_evidence_planning` is **also the loop's only initializer** (`pipeline.py:1949`, `:1972`). That node is fenced off canonical turns, so `loop_initialized(state)` is permanently `False` live. **Failing-first:** flipping `live_call_sites_present` and `imperative_drain_present` to `False` went red on exactly 2 tests pre-removal, green post-removal. **Removed:** the `discovery_loop` call site (ran on every non-guided turn, returned immediately), the `evidence_planning_loop` re-entry call site (never reached), and `_run_discovery_loop_imperative` itself, now unreferenced. **Retained with reason:** `graph_node_evidence_planning` and `graph_node_mcp_call` — the legacy harness graph (`linear_graph_legacy.py:115`) registers both and ~10 test files call them directly; **`MAX_MCP_HOPS`** — inert on live paths but **not dead code**: it still bounds recipe call budgets at `evidence_loop.py:639` via `min(MAX_MCP_HOPS - hops_done, recipe.max_calls - len(records))`. Removing it would weaken a live bound, an explicit R3 stop condition, so it is retained and the budget expression is now pinned by test. `graph_node_pre_spl_mcp_discovery` and dispatch-v2 context untouched; zero change to the MCP execution gate or SPL validator. Verify command **113 passed**; full backend **4846 passed, 2 skipped, 6 xfailed, 0 failed**; manifest `13/13`; invariant 7/7. Commit: `55ae6a7`.
  - **Invariant / manifest:** Full invariant check; zero change to MCP execution gate/SPL validator.
  - **Commit boundary:** Legacy discovery retirement only.
  - **Stop:** Any symbol has a current canonical/live consumer; deletion would weaken a gate or remove pre-SPL discovery.

- [x] **B2-R4 — RETIRE: branch regression proof**
  - **Do:** Re-run targeted retirement, dual-runtime, reference, parity, and governance gates; record that deterministic canonical plans and analyst-visible authority are unchanged and neither runtime retains a ResourcePlan/guided-plan proposer model hop.
  - **Why:** Cleanup is complete only if absence and parity are both proven.
  - **Surfaces:** tests/evidence only.
  - **Depends on:** B2-R3.
  - **Failing-first / observation:** No implementation; repair only failures caused within B2-R scope.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_retired_resource_planning_surfaces.py app/tests/test_resource_plan_shadow.py app/tests/test_llm_primary_planning.py app/tests/test_llm_plan_bridge.py app/tests/test_guided_investigation_plan_llm.py app/tests/test_guided_investigation_llm_firewall.py app/tests/test_guided_hybrid_collection.py app/tests/test_evidence_loop.py app/tests/test_evidence_loop_graph.py app/tests/test_dispatch_authority_wiring.py app/tests/test_pipeline_dispatch_phase4.py app/tests/test_pipeline_dispatch_phase5.py app/tests/test_pipeline_dispatch_phase6.py -q`; from root use P0's two-command host DB export without echoing it, then run `TELEMETRY_MODE=none PYTHONPATH=backend:. python3 scripts/audit_reference_probes.py --check`; `PYTHONPATH=backend:. python3 scripts/run_production_parity_eval.py --out-dir /tmp/plan2-retire-parity --check`; `./scripts/run_stage3_governance_regression.sh`; `python3 scripts/freeze_execution_baseline.py --check --in /tmp/plan2-execution-baseline.json`.
  - **Evidence:** **COMPLETE 2026-08-10 — Phase B (RETIRE branch) closed.** Targeted retirement suite (13 files) **120 passed**. Full backend **4846 passed, 2 skipped, 6 xfailed, 0 failed**. Reference probes **10/10**, all matching the frozen baseline. Production parity **`total=120 base_105=105 exact=120 approved=0 critical=0`**. Governance regression **PASS** (`stage3_governance_regression: PASS`, exit 0) with in-run backend `4846 passed`, harness `8 passed, 1 skipped`, dual parity `120 exact / 0 approved / 0 critical`, clean-answer `120 pass / 0 review / 0 fail / 0 critical / 0 major`, Cisco `PASS=50 / REVIEW=0 / FAIL=0 / CRITICAL=0`, dispatch matrix `5/5`. Manifest `protected artifacts unchanged (13 checked)`. **Zero planning-hop proof, both runtimes:** `run_resource_plan_shadow`, `apply_llm_primary_resource_plan`, `propose_investigation_plan_llm`, and `_run_discovery_loop_imperative` are all absent from the pipeline module (`hasattr` False for each), and live turns on both the imperative path and the RP graph report `shadow_status="retired"`, `llm_called=False`. **Deterministic guided behavior retained:** Validator A/B, `compose_guided_resource_plan`, evidence collection, and the MCP/SPL/HIL posture all unchanged and green. **Host gate invocation note:** reference probes and governance require `DATABASE_URL` pointed at the published `127.0.0.1:5434` when run from the host, because the compose value `postgres:5432` does not resolve outside Docker. With that override the A0-era probe failure disappeared, confirming it was never a code regression. Governance regenerated the same five `docs/evals/` reports with the churn signature proven environmental during A0 (parity rows 112–113: `contract_answer_mode`, `enabled_sections`, `mitre_technique_ids`, `mitre_answer_visible`, plus ordering/timing fields); verdict counts were identical, so the files were reverted per the protected-artifact policy. No test changes were needed in R4, so no code commit. Evidence commit: `a65e915`.
  - **Invariant / manifest:** Full cumulative invariant check for B2-R.
  - **Commit boundary:** Regression/test-only commit if needed; no new feature.
  - **Stop:** Any baseline drift, authority change, or hidden consumer appears.

- [x] **B2-W1 — RE-WIRE: add explicit default-false posture configuration**
  - **Do:** If RE-WIRE selected, implement only the B1-approved dedicated flag name and bounded settings (plan step cap, timeout, discovery posture/hop cap). Defaults are disabled/fail-closed; no piggyback on synthesis/intent flags. Status surfaces expose booleans/numbers only, no endpoint/credential. Add `backend/app/tests/test_canonical_adaptive_planning_config.py` (**NEW**).
  - **Why:** Adaptive planning must be an explicit operator choice with reviewable bounds.
  - **Surfaces:** `backend/app/config.py`; settings/status schemas and redacted status builder; env docs/profiles only if B1 authorizes; new test.
  - **Depends on:** B1=`RE-WIRE` with complete config fields.
  - **Failing-first / observation:** Tests first prove flag absent and unrelated synthesis flags cannot enable planning.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_canonical_adaptive_planning_config.py app/tests/test_settings_status.py app/tests/test_settings_status_safety.py app/tests/test_llm_settings_stage3jb.py app/tests/test_resource_plan_authority.py -q`; manifest check.
  - **Evidence:** N/A — rejected by B1 decision RETIRE, Anurag / 2026-08-10T17:29:24Z.
  - **Invariant / manifest:** Full invariant check; B1 approval is evidence for the otherwise prohibited new flag.
  - **Commit boundary:** Config/status only; no bridge call.
  - **Stop:** B1 did not approve exact semantics; any flag defaults on or bypasses safety.

- [x] **B2-W2 — RE-WIRE: insert one canonical bridge seam after the deterministic floor**
  - **Do:** Add one named helper at `_commit_planned_outcome` after `plan_evidence_from_canonical` builds the deterministic floor and before `planned_outcome` persists it. Both runtimes continue through the same canonical seam. Implement the exact B1 `bridge_trigger_match_paths` disposition rather than preserving `_TRIGGER_MATCH_PATHS` by accident. Fold the imperative guided-hybrid proposer into this seam: remove its direct `propose_investigation_plan_llm` call/parallel authority while preserving deterministic guided execution and validation. That fold exposes two surfaces which must be dispositioned in this same commit, not left implicit: (a) **`ai_soc_guided_llm_enabled` semantics.** Its proposer consumer is an *inverted* gate — flag true reserves the proposer with `guided_finalize_composer_reserved`, flag false calls it — so folding removes the flag's only proposer meaning while its three budget/deadline consumers (`pipeline.py:967`, `pipeline.py:1045`, `guided_llm_budget.py:12`) legitimately remain. Re-verify the consumer set by `rg`, retain the flag for budget/deadline scope only, and prove it cannot enable, disable, or otherwise gate the new canonical seam — the B2-W1 dedicated flag is the sole planning switch, and the existing "no piggyback on synthesis/intent flags" rule extends to this one. (b) **Guided dispatch-step trace compatibility.** The `dispatch_steps.append("guided_investigation_plan_llm")` emitter is gated on `llm_result.attempted`; decide whether the label is removed or re-sourced from the canonical seam's own attempt outcome, and prove the chosen posture against trace/scorecard consumers found by `rg`. With flag off, output is byte/field equivalent. Do not wire legacy `graph_node_evidence_planning` or direct MCP.
  - **Why:** There must be one live canonical insertion point, not parallel planning authorities. A retained guided flag that still appears to gate planning, or a dispatch-step label re-sourced by accident, would recreate a second de-facto planning switch.
  - **Surfaces:** `canonical_planning_orchestrator.py`; `pipeline.py`; `llm_plan_bridge.py`/promotion helper; `guided_investigation_plan_llm.py`; guided-hybrid executor/validator boundaries; `test_canonical_adaptive_planning_wiring.py` (**NEW**); dual-runtime/authority tests.
  - **Depends on:** B2-W1.
  - **Failing-first / observation:** Static seam test fails until exactly one canonical caller exists across both runtimes and no direct guided proposer remains; path-table tests fail for every B1-approved trigger that is absent and every excluded trigger that calls. Flag-off parity is captured first.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_canonical_adaptive_planning_wiring.py app/tests/test_dual_runtime_single_orchestration.py app/tests/test_canonical_planning_architecture.py app/tests/test_resource_plan_authority.py app/tests/test_canonical_handoff_e2e_probes.py app/tests/test_guided_investigation_plan_llm.py app/tests/test_guided_investigation_llm_firewall.py -q`; production parity `--check`; manifest check.
  - **Evidence:** N/A — rejected by B1 decision RETIRE, Anurag / 2026-08-10T17:29:24Z.
  - **Invariant / manifest:** Full invariant check; deterministic plan remains floor and sole fallback. Flag-group review must show exactly one planning switch — the B2-W1 dedicated flag — and no flag renamed, repurposed, or defaulted on.
  - **Commit boundary:** Insertion seam only; proposal semantics remain non-promoting until W3.
  - **Stop:** A second runtime needs a separate seam; any direct guided proposer/parallel planning authority remains; a B1-approved match path cannot reach the seam under the approved flag/posture; an excluded path does not fail closed; flag-off differs; canonical persistence order would become ambiguous; `ai_soc_guided_llm_enabled` would need renaming/repurposing/removal, or would end up co-gating the seam alongside the dedicated flag; the guided dispatch-step label has a consumer that tolerates neither removal nor re-sourcing — all three are B1 scope, not executor scope.

- [x] **B2-W3 — RE-WIRE: validate and promote proposals without weakening the floor**
  - **Do:** Harden the proposal schema and promotion contract: registry IDs/purposes only; B1 plan cap; forbidden raw-query/SPL/credential keys recursively rejected; no execution eligibility; all deterministic floor steps/policy checks/status constraints retained; additions only where skill/resource policy permits; exact promotion provenance and dropped reasons. Implement the B1 `guided_promotion_policy` explicitly: if guided is in adaptive scope, replace the current `guided_hybrid_v1`/`guided_investigation` blanket returns with validated canonical handling; if excluded, retain both guards and test the declared deterministic-only scope. Add mutation tests for floor removal, invented resource, policy relaxation, unsafe args, direct MCP intent, oversized plans, and both guided guard shapes.
  - **Why:** An LLM proposal is data, never authority.
  - **Surfaces:** `llm_plan_bridge.py`; `plan_promotion_merge.py`; resource registry/plan models; `test_canonical_adaptive_planning_promotion.py` (**NEW**) plus existing bridge tests.
  - **Depends on:** B2-W2.
  - **Failing-first / observation:** Mutation cases fail before hardening; deterministic floor fingerprint must remain identical on every rejection.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_canonical_adaptive_planning_promotion.py app/tests/test_llm_plan_bridge.py app/tests/test_llm_plan_bridge_promotion.py app/tests/test_llm_primary_planning.py app/tests/test_compose_guided_resource_plan.py app/tests/test_guided_investigation_plan_llm.py app/tests/test_resource_plan_authority.py app/tests/test_specialist_report_contracts.py -q`; manifest check.
  - **Evidence:** N/A — rejected by B1 decision RETIRE, Anurag / 2026-08-10T17:29:24Z.
  - **Invariant / manifest:** Full invariant check including recursive secret/query/SPL scan.
  - **Commit boundary:** Proposal validation/promotion only; no discovery scheduling.
  - **Stop:** Any proposal can remove a floor step, authorize execution, or carry forbidden content.

- [x] **B2-W4 — RE-WIRE: implement the approved discovery/hop/time budget semantics**
  - **Do:** Implement exactly the B1-selected discovery posture. If legacy discovery is RETIRED, keep it fenced/remove inert semantics and allow no adaptive discovery step. If CANONICALLY_REIMPLEMENTED, validate discovery steps into a deterministic scheduler; LLM never selects/calls a connector; enforce B1 hop/time/step caps; preserve execution gate; keep dispatch-v2 pre-SPL discovery separate and prevent double discovery. Reuse V2/recipe concepts only after proving they do not import fenced authority.
  - **Why:** `MAX_MCP_HOPS` cannot silently regain meaning, and two discovery mechanisms cannot double-run.
  - **Surfaces:** approved scheduler/plan contracts; `evidence_loop.py` only if selected; dispatch-v2 pipeline and tests; `test_canonical_adaptive_planning_budget.py` (**NEW**).
  - **Depends on:** B2-W3.
  - **Failing-first / observation:** Tests inject over-budget, duplicate-discovery, LLM-direct-tool, timeout, and flag-off cases before implementation.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_canonical_adaptive_planning_budget.py app/tests/test_orchestration_scheduler.py app/tests/test_recipe_registry_contract.py app/tests/test_dispatch_authority_wiring.py app/tests/test_pipeline_dispatch_phase4.py app/tests/test_pipeline_dispatch_phase5.py app/tests/test_pipeline_dispatch_phase6.py app/tests/test_mcp_execution_gate.py -q`; manifest check.
  - **Evidence:** N/A — rejected by B1 decision RETIRE, Anurag / 2026-08-10T17:29:24Z.
  - **Invariant / manifest:** Full invariant check; no LLM→MCP path and no execution-authority expansion.
  - **Commit boundary:** Discovery/budget semantics only.
  - **Stop:** B1 posture incomplete; dispatch-v2 and adaptive discovery cannot be distinguished; a connector call would occur outside the gate.

- [x] **B2-W5 — RE-WIRE: add redacted planning trace and model-hop telemetry**
  - **Do:** Record attempt/call/outcome/latency, flag/budget skip reason, validation verdict, promotion status, deterministic fallback, plan source and bounded step IDs. Do not persist prompts, rationale text beyond existing bounded safe provenance, args, query, endpoint, credentials, RAG/raw events, or SPL. Make attempted-but-invalid distinct from not-called. Retire the ambiguous `llm_called=false/no_valid_shadow_proposal` semantics.
  - **Why:** B0 showed that architecture cost/promotion must be empirically observable.
  - **Surfaces:** canonical planning trace, `TurnLlmBudget`, telemetry redaction, control-plane trace, `test_canonical_adaptive_planning_trace.py` (**NEW**).
  - **Depends on:** B2-W4.
  - **Failing-first / observation:** Redaction tests and attempted-vs-skipped matrix first.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_canonical_adaptive_planning_trace.py app/tests/test_control_plane_trace.py app/tests/test_telemetry_connector.py app/tests/test_live_chat_telemetry_spine.py app/tests/test_turn_llm_budget_enforced.py app/tests/test_resource_plan_shadow.py -q`; manifest check.
  - **Evidence:** N/A — rejected by B1 decision RETIRE, Anurag / 2026-08-10T17:29:24Z.
  - **Invariant / manifest:** Full invariant/redaction check.
  - **Commit boundary:** Trace/telemetry only.
  - **Stop:** Safe evidence cannot distinguish call attempt/result; any forbidden content reaches telemetry.

- [x] **B2-W6 — RE-WIRE: prove timeout/rejection/failure fallback**
  - **Do:** Add deterministic tests for disabled, budget skip, no client, timeout, exception, invalid JSON/schema, all steps dropped, partial valid plan, persistence failure, and discovery failure. Every case must return the deterministic floor or a governed planning failure—never a partial/unvalidated plan—and must not duplicate final shadow calls.
  - **Why:** Adaptive planning is acceptable only when failure is operationally equivalent to deterministic planning.
  - **Surfaces:** canonical bridge helper; sidecar timeout; promotion; persistence; `test_canonical_adaptive_planning_fallback.py` (**NEW**).
  - **Depends on:** B2-W5.
  - **Failing-first / observation:** Parameterized failure matrix written first.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_canonical_adaptive_planning_fallback.py app/tests/test_canonical_adaptive_planning_wiring.py app/tests/test_canonical_adaptive_planning_promotion.py app/tests/test_canonical_adaptive_planning_budget.py app/tests/test_canonical_adaptive_planning_trace.py app/tests/test_canonical_handoff_persistence_failclosed.py -q`; manifest check.
  - **Evidence:** N/A — rejected by B1 decision RETIRE, Anurag / 2026-08-10T17:29:24Z.
  - **Invariant / manifest:** Full invariant check.
  - **Commit boundary:** Failure/fallback only.
  - **Stop:** Any failure loses the floor, weakens policy, or makes a second model call.

- [x] **B2-W7 — RE-WIRE: parity and regression proof**
  - **Do:** Prove flag-off exact parity and flag-on governed widening only for B1-approved paths; run a fake-client trigger matrix covering `out_of_registry`, `near_105_question`, `semantic_out_of_registry`, `query_understanding_weak`, `qu_unavailable`, and empty/unknown path, plus novel T4 probes and one explicitly approved live observation if still needed. Record plan-size/time budgets and no authority changes. B0's single `out_of_registry` call is not evidence for the other paths.
  - **Why:** RE-WIRE must prove both compatibility and bounded value before closure.
  - **Surfaces:** adaptive test family, eval/parity/governance evidence.
  - **Depends on:** B2-W6.
  - **Failing-first / observation:** No new architecture in this item; failures are fixed only within W1–W6 scope.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_canonical_adaptive_planning_config.py app/tests/test_canonical_adaptive_planning_wiring.py app/tests/test_canonical_adaptive_planning_promotion.py app/tests/test_canonical_adaptive_planning_budget.py app/tests/test_canonical_adaptive_planning_trace.py app/tests/test_canonical_adaptive_planning_fallback.py -q`; from root use P0's host DB export, then run `TELEMETRY_MODE=none PYTHONPATH=backend:. python3 scripts/audit_reference_probes.py --check`; `PYTHONPATH=backend:. python3 scripts/run_production_parity_eval.py --out-dir /tmp/plan2-rewire-parity --check`; `PYTHONPATH=backend:. python3 scripts/eval_out_of_set_intent_probe.py --check`; `./scripts/run_stage3_governance_regression.sh`; manifest check.
  - **Evidence:** N/A — rejected by B1 decision RETIRE, Anurag / 2026-08-10T17:29:24Z.
  - **Invariant / manifest:** Full cumulative invariant check for B2-W.
  - **Commit boundary:** Regression/test-only commit if needed.
  - **Stop:** Baseline refresh needed; any non-approved route changes; live probe requires new authority.

- [x] **C0 — COE decision: LINEAGE-ONLY or EXECUTION-DRIVEN ResourcePlan order**
  - **Do:** Re-run current walk/schedule tests and build a small matrix with at least two ResourcePlans containing the same steps in opposite order. Show `step_walk_order`, actual dispatch schedule, output dependencies, and current policy/HIL timing. Present both options and fill every C0 decision field. If EXECUTION-DRIVEN, explicitly choose `activation_posture`; if `DEDICATED_DEFAULT_FALSE_FLAG`, record the exact approved `execution_order_flag_name`. Do not implement either branch. Disposition the rejected C1 branch N/A.
  - **Why:** Ordering authority is independent of the LLM/discovery posture and requires explicit intent.
  - **Surfaces:** plan evidence; `executor.py`; current step-dispatch/planner tests.
  - **Depends on:** B1 decision completed; it may be decided before B2 implementation.
  - **Failing-first / observation:** Observation/decision only. Opposite plan orders must currently yield the same predicate schedule; contradiction is drift and stops the gate.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_resource_plan_step_dispatch.py app/tests/test_planner_executor.py app/tests/test_dispatch_authority_wiring.py -q`; then `rg -n 'selected_order_semantics.*(LINEAGE-ONLY|EXECUTION-DRIVEN)|approved_by|approved_at|current_schedule_evidence|activation_posture.*(DEDICATED_DEFAULT_FALSE_FLAG|CANONICAL_DEFAULT_AFTER_PROOF)|execution_order_flag_name'` on this plan and run the plan audit.
  - **Evidence:** **COMPLETE 2026-08-11 at HEAD `c6d900a`; decision `EXECUTION-DRIVEN`, approved by Anurag at `2026-08-11T05:53:15Z`.** Verify pytest slice: **36 passed** (`test_resource_plan_step_dispatch.py`, `test_planner_executor.py`, `test_dispatch_authority_wiring.py`). Opposite-order matrix was produced by a non-committed `/tmp` observation script that builds each state through `understand_query` → `build_query_to_intent` → `plan_evidence` under the same `TEST_AUTHORITY` compose hook the suite uses, then deep-copies the state and reverses `evidence_plan.resource_plan.steps` only. No connector, LLM, or graph call.

    | Probe (skill) | Composed step order (forward) | Reversed order | Schedule forward | Schedule reversed | Identical? | `step_walk == legacy` fwd/rev |
    |---|---|---|---|---|---|---|
    | `Which users have excessive failed logins?` (attack_discovery) | `spl:spl_artifact`, `mcp:mcp_execution`, `narration` | `narration`, `mcp:mcp_execution`, `spl:spl_artifact` | `workflow_spl`, `spl_source_resolve`, `execution` | same | **yes** | yes / yes |
    | `Generate SPL for failed logins` (spl_generation) | `spl`, `mcp`, `narration` | reversed | `workflow_spl`, `spl_source_resolve`, `execution` | same | **yes** | yes / yes |
    | `Strange OT chatter…` (guided_investigation) | *no composed ResourcePlan* | — | — | — | n/a | n/a |
    | `What is our password policy for contractor accounts?` (knowledge_recall) | `rag:knowledge_retrieval`, `narration` | reversed | `prepare_rag_only`, `rag_early` | same | **yes** | yes / yes |
    | `Which hosts are generating the most SMB traffic?` (attack_discovery) | `spl`, `mcp`, `narration` | reversed | `workflow_spl`, `spl_source_resolve`, `execution` | same | **yes** | yes / yes |

    **Premise confirmed, no drift:** in every probe with a composed plan, reversing ResourcePlan step order changed `step_walk_order` but left the dispatch schedule byte-identical, and `build_step_walk_dispatch_schedule` equalled `_legacy_predicate_dispatch_schedule` in both directions — ResourcePlan order is lineage today, not execution authority (`executor.py:180-191` delegates unconditionally).

    **Guided observation (not a contradiction):** the `guided_investigation` probe has no composed ResourcePlan because `compose_resource_plan_testutil.py:31-35` deliberately returns the plan uncomposed when `answer_mode == "guided_investigation"` and `ai_soc_guided_hybrid_investigation_enabled` is true, which is this host's posture. Recorded because it bears directly on the carried-in refinement requirement: the guided lane currently has no composed ResourcePlan to reorder or re-plan from, which C1-E3 must account for.

    **Output dependencies in the current fixed schedule** (read from `executor.py:194-233` and its module docstring, `executor.py:9-12`): `workflow_spl` produces `candidate_spl` consumed by `spl_source_resolve`, which produces the resolved/validated `spl_validation` consumed by `execution`; `rag_early` precedes SPL only when `uses_pre_mcp_rag`; `prepare_rag_only` + `rag_early` form the RAG-only tail with no execution stage; `ensure_workflow_plan` is the SPL-blocked substitute. `execution` is always last and is the sole owner of `evaluate_mcp_execution` and the HIL gate — the executor never calls a connector and cannot bypass a gate.

    **Policy/HIL timing observed:** two distinct block points. Composition-time veto — the `spl_generation` probe's `mcp` step arrived already `blocked_policy` with `skipped_step_reasons["mcp"] == "skill_contract"` and `blocked_step_ids == ['mcp']`, so it is never dispatched. Gate-time — the MCP execution gate and HIL run inside the `execution` node, after SPL validation. Both must remain in place under any execution-driven schedule.

    **Decision fields recorded** in the C0 decision block above: `EXECUTION-DRIVEN`; approver/timestamp; `v1_v2_posture: EXTEND_LIVE_RESOURCE_PLAN` (no wholesale V2/scheduler promotion; concept reuse only after per-concept authority-boundary verification); parallelism restricted to genuinely independent safe/read-only steps; deterministic downgrade to the fixed schedule for absent/invalid/unsupported plans with no automatic retry of uncertain or side-effecting operations; `activation_posture: DEDICATED_DEFAULT_FALSE_FLAG`; `execution_order_flag_name: AI_SOC_RESOURCE_PLAN_EXECUTION_ENABLED` (default false). N/A dispositions: **1** (`C1-L`). No runtime change; manifest `protected artifacts unchanged (13 checked)`; plan audit `0 gap(s)`.
  - **Invariant / manifest:** No runtime change; manifest check.
  - **Commit boundary:** Optional plan-only decision commit.
  - **Stop:** No explicit choice; EXECUTION-DRIVEN activation posture is incomplete; dedicated-flag posture lacks an exact approved default-false flag name; matrix contradicts current fixed-schedule premise; choice would weaken a locked gate.

- [x] **C1-L — LINEAGE-ONLY: make fixed scheduling an explicit, tested contract**
  - **Do:** Rename/document the schedule seam so it does not promise a future reorder; keep `step_walk_order` informational; add mutation tests proving arbitrary ResourcePlan order cannot reorder validation, execution gate, RAG, or finalization, and cannot bypass blocked steps. Update trace labels to say `lineage_order` where backward compatibility permits without breaking schema.
  - **Why:** If lineage-only is intentional, accidental future execution authority must be prevented.
  - **Surfaces:** `executor.py`; step-dispatch/trace tests; `test_resource_plan_lineage_only_contract.py` (**NEW**).
  - **Depends on:** C0=`LINEAGE-ONLY` and selected B2 closure.
  - **Failing-first / observation:** Opposite-order mutation tests first.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_resource_plan_lineage_only_contract.py app/tests/test_resource_plan_step_dispatch.py app/tests/test_planner_executor.py app/tests/test_dispatch_authority_wiring.py app/tests/test_pipeline_dispatch_phase6b.py -q`; production parity `--check`; manifest check.
  - **Evidence:** N/A — rejected by C0 decision EXECUTION-DRIVEN, Anurag / 2026-08-11T05:53:15Z.
  - **Invariant / manifest:** Full invariant check.
  - **Commit boundary:** Small docs/test/seam-hardening commit only.
  - **Stop:** Existing consumer treats step order as authority; trace rename breaks a public contract.

- [ ] **C1-E1 — EXECUTION-DRIVEN: define and validate the dependency contract**
  - **Do:** Decide, from the C0 record, whether to extend live `ResourcePlan` or promote a bounded subset of `ResourcePlanV2`; define unique IDs, acyclic `depends_on`, allowed parallel groups, declared produced/required evidence keys, fallback targets, max attempts, blocked/skipped semantics, and deterministic downgrade to the current schedule. Do not wire execution yet.
  - **Why:** A list order is insufficient to govern dependent or parallel work.
  - **Surfaces:** resource-plan contracts, validators, registry/composer; `test_resource_plan_execution_contract.py` (**NEW**).
  - **Depends on:** C0=`EXECUTION-DRIVEN` and selected B2 closure.
  - **Failing-first / observation:** Cycles, missing dependencies, unknown evidence keys, unsafe retries, and invalid fallback targets fail first.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_resource_plan_execution_contract.py app/tests/test_recipe_registry_contract.py app/tests/test_resource_plan_authority.py app/tests/test_planner_hierarchy_contracts.py -q`; manifest check.
  - **Evidence:** _(schema decision, invalid matrix, downgrade contract, pytest/manifest/invariant, commit)_
  - **Invariant / manifest:** Full invariant check; no live wiring.
  - **Commit boundary:** Contract/validation only.
  - **Stop:** C0 does not resolve V1/V2 posture; contract permits unbounded/cyclic/retrying side effects.

- [ ] **C1-E2 — EXECUTION-DRIVEN: build a pure schedule compiler**
  - **Do:** Compile validated step dependencies into deterministic waves/stages without calling workers. Map purposes to existing governed hooks, preserve stable tie-breaking, prevent duplicate execution, and fall back to the fixed schedule for absent/invalid/unsupported contracts. No connector/LLM call.
  - **Why:** Scheduling logic must be independently testable before live wiring.
  - **Surfaces:** `executor.py` or a new pure scheduler module; dormant scheduler reused only if authority boundaries match; `test_resource_plan_execution_scheduler.py` (**NEW**).
  - **Depends on:** C1-E1.
  - **Failing-first / observation:** Reorder, parallel, blocked, cycle, duplicate, unsupported-purpose, and fallback cases first.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_resource_plan_execution_scheduler.py app/tests/test_orchestration_scheduler.py app/tests/test_resource_plan_step_dispatch.py app/tests/test_planner_executor.py -q`; manifest check.
  - **Evidence:** _(schedule matrix, deterministic order, fallback, no-I/O proof, pytest/manifest/invariant, commit)_
  - **Invariant / manifest:** Full invariant check.
  - **Commit boundary:** Pure scheduler only.
  - **Stop:** Scheduler must infer dependencies from node names/booleans; unsupported plan cannot fall back exactly.

- [ ] **C1-E3 — EXECUTION-DRIVEN: define step output→input handoffs**
  - **Do:** Add bounded typed handoffs for current real dependencies: RAG→SPL slot fill, dispatch-v2 pre-SPL discovery→SPL compiler/preference, SPL candidate→source resolve→validation, approved normalized SPL→MCP gate, evidence→finalization. Missing/empty outputs produce declared skip/block/fallback states; no arbitrary state-key interpolation.
  - **Why:** Execution order matters only if downstream inputs are explicit and validated.
  - **Surfaces:** pipeline state contracts, dispatch context/handoffs, scheduler result; `test_resource_plan_execution_handoffs.py` (**NEW**).
  - **Depends on:** C1-E2.
  - **Failing-first / observation:** Missing key, wrong type, empty RAG, failed discovery, unapproved SPL, and fabricated key tests first.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_resource_plan_execution_handoffs.py app/tests/test_langgraph_spl_source_resolve_parity.py app/tests/test_pipeline_dispatch_phase4.py app/tests/test_pipeline_dispatch_phase5.py app/tests/test_mcp_execution_gate.py -q`; manifest check.
  - **Evidence:** _(handoff table, failure outcomes, pre-SPL distinction, pytest/manifest/invariant, commit)_
  - **Invariant / manifest:** Full invariant check; all new state keys declared on LangGraph state.
  - **Commit boundary:** Typed handoffs only; no live scheduler switch.
  - **Stop:** Handoff can carry raw prompt/credentials; candidate SPL reaches execution; undeclared state key needed.

- [ ] **C1-E4 — EXECUTION-DRIVEN: wire both runtimes behind explicit authority**
  - **Do:** Wire the validated scheduler into the single canonical dispatch seam for both Resource Planner graph and imperative rollback. Preserve policy veto, SPL validation before MCP gate, HIL/RBAC, idempotency, pre-SPL discovery timing, and deterministic fixed-schedule fallback. Implement exactly the C0-approved activation posture. For `DEDICATED_DEFAULT_FALSE_FLAG`, use the exact approved `execution_order_flag_name`, default it false, and prove flag-off fixed-schedule parity. For `CANONICAL_DEFAULT_AFTER_PROOF`, keep the new scheduler non-authoritative through C1-E5 and defer the separately reviewable default activation to C1-E6 after proof; do not create a hidden temporary default-on path.
  - **Why:** Dual-runtime parity and gate timing are the live architecture boundary.
  - **Surfaces:** `executor.py`; `resource_planner_graph.py`; pipeline/config activation surface; dual-runtime tests; `test_resource_plan_execution_wiring.py` (**NEW**); `test_resource_plan_execution_activation.py` (**NEW**).
  - **Depends on:** C1-E3.
  - **Failing-first / observation:** Flag-off exact parity, graph/imperative equality, and gate-order tests first.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_resource_plan_execution_wiring.py app/tests/test_resource_plan_execution_activation.py app/tests/test_dual_runtime_single_orchestration.py app/tests/test_dispatch_authority_wiring.py app/tests/test_resource_plan_step_dispatch.py app/tests/test_mcp_execution_gate.py app/tests/test_execution_idempotency.py app/tests/test_per_step_hook_idempotency.py -q`; production parity `--check`; manifest check.
  - **Evidence:** _(selected activation posture, exact flag/default when applicable, dual-runtime order, inactive-posture fixed-schedule parity, gate sequence, pytest/parity/manifest/invariant, commit)_
  - **Invariant / manifest:** Full invariant check.
  - **Commit boundary:** Live wiring only.
  - **Stop:** C0 activation posture is incomplete; dedicated-flag posture lacks the exact approved default-false flag; canonical-default posture becomes authoritative before C1-E6 proof; runtimes require divergent schedulers; a safety gate moves later/bypasses.

- [ ] **C1-E5 — EXECUTION-DRIVEN: harden failure, skip, fallback, and finalization**
  - **Do:** Test and implement dependency failure propagation, skipped/blocked downstream steps, empty evidence, timeout/denied/uncertain side effects, fallback target, HIL stop, partial evidence finalization, and deterministic rollback. Ensure answer/evidence assembly runs once with honest limitations and step statuses are stable/idempotent.
  - **Why:** Multi-step execution must fail closed without losing available evidence or repeating side effects.
  - **Surfaces:** scheduler reconcile/status annotation, idempotency, finalization; `test_resource_plan_execution_failures.py` (**NEW**).
  - **Depends on:** C1-E4.
  - **Failing-first / observation:** Full outcome matrix first, including uncertain execution reconciliation.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_resource_plan_execution_failures.py app/tests/test_execution_idempotency.py app/tests/test_per_step_hook_idempotency.py app/tests/test_resource_plan_step_dispatch.py app/tests/test_context_sufficiency_stage3j.py app/tests/test_final_evidence_gate.py app/tests/test_final_answer_validator.py -q`; manifest check.
  - **Evidence:** _(outcome matrix, one-finalize/one-side-effect proof, statuses, pytest/manifest/invariant, commit)_
  - **Invariant / manifest:** Full invariant check.
  - **Commit boundary:** Failure/finalization only.
  - **Stop:** Any uncertain side effect is retried automatically; partial evidence becomes unsupported claim; finalization duplicates.

- [ ] **C1-E6 — EXECUTION-DRIVEN: parity and novel-query proof**
  - **Do:** Run a tier/intent/order matrix and novel SOC queries; compare selected schedule against current fixed fallback, confirm only approved order differences, and run reference/parity/governance/full backend gates. If C0 selected `CANONICAL_DEFAULT_AFTER_PROOF`, only after C1-E1 through C1-E5 and this proof are green, make the separately reviewable activation-only default change, then repeat every C1-E6 gate and record both pre- and post-activation results. If C0 selected `DEDICATED_DEFAULT_FALSE_FLAG`, retain the false default.
  - **Why:** Execution-driven ordering is a stage boundary and needs broad proof.
  - **Surfaces:** execution test family/evals/evidence only.
  - **Depends on:** C1-E5.
  - **Failing-first / observation:** No new feature work; fix only C1-E scope failures. The sole permitted runtime edit here is the C0-authorized activation-only default change after an initial fully green proof.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_resource_plan_execution_contract.py app/tests/test_resource_plan_execution_scheduler.py app/tests/test_resource_plan_execution_handoffs.py app/tests/test_resource_plan_execution_wiring.py app/tests/test_resource_plan_execution_failures.py -q`; from root use P0's host DB export, then run `PYTHONPATH=backend:. python3 scripts/eval_out_of_set_intent_probe.py --check`; `TELEMETRY_MODE=none PYTHONPATH=backend:. python3 scripts/audit_reference_probes.py --check`; `PYTHONPATH=backend:. python3 scripts/run_production_parity_eval.py --out-dir /tmp/plan2-execution-driven-parity --check`; `./scripts/run_stage3_governance_regression.sh`; `cd backend && PYTHONPATH=../backend:.. python3 -m pytest`; return to root and run the manifest check.
  - **Evidence:** _(matrix, novel queries, allowed deltas, activation posture/default, exact pre/post-activation counts when applicable, manifest, cumulative invariant, commit)_
  - **Invariant / manifest:** Full cumulative invariant check for C1-E.
  - **Commit boundary:** Regression/test-only commit if needed; for `CANONICAL_DEFAULT_AFTER_PROOF`, a separate activation-only commit after initial green proof, followed by the repeated full gates.
  - **Stop:** Unapproved answer/route changes; baseline refresh; full gate fails twice.

- [ ] **G0 — Align current architecture/operator documentation with selected outcomes**
  - **Do:** Update only claims changed by A0/A1 and the selected B2/C1 branches. Preserve historical audit evidence. Explicitly distinguish fenced/retired/reimplemented legacy discovery from live dispatch-v2 pre-SPL discovery. Document whether ResourcePlan order is lineage or authority, the guided-hybrid proposer disposition, shadow/bridge posture, match-path and guided-promotion scope, hop/time/flag semantics, topology truth sources, and decision-record limitations. Where `ai_soc_guided_llm_enabled` is described, state its post-change scope explicitly — budget/deadline only, no planning-call gate — and remove any surviving text implying it enables guided LLM planning; correct the guided dispatch-step label's documented meaning to match the B2 disposition. Update diagrams only if their current-path claims changed; keep all mirrors byte-identical and build frontend if a served copy changes.
  - **Why:** Operators must see the selected architecture, not historical scaffolding.
  - **Surfaces:** `docs/architecture/mcp_tool_routing.md`; `chat_pipeline_state_v2_and_node_trace.md`; `llm_budget_model.md`; architecture review resolution; `CLAUDE.md`; COE config docs; architecture HTML/mirrors only if needed.
  - **Depends on:** selected B2 closure and selected C1 closure.
  - **Failing-first / observation:** `rg` current claims before edit; documentation contract tests fail first only for claims that actually changed.
  - **Verify:** From root run `rg -n 'pre-SPL|legacy|ResourcePlan|lineage|execution-driven|RETIRE|RE-WIRE|MAX_MCP_HOPS|decision.*inputs_ref|topology' docs/architecture/mcp_tool_routing.md docs/architecture/chat_pipeline_state_v2_and_node_trace.md docs/architecture/llm_budget_model.md docs/architecture/architecture_review_2026-08-08.md CLAUDE.md docs/coe/COE_ROLLOUT_CONFIGURATION.md`; `PYTHONPATH=backend:. python3 -m pytest backend/app/tests/test_architecture_details_flow_contract.py -q`; `cmp -s docs/architecture/details.html frontend/public/docs/architecture/details.html`; `cd frontend && npm run build`; then apply the manifest handling policy below and record whether the served mirrors changed.
  - **Evidence:** _(changed claims/files, explicit discovery distinction, mirror/build result if applicable, manifest disposition, commit)_
  - **Invariant / manifest:** Documentation-only invariant review. If protected published mirrors intentionally change, record exact group and recapture only after user/COE confirms; never recapture eval/golden/registry drift.
  - **Commit boundary:** Documentation only.
  - **Stop:** Historical evidence would need rewriting; protected change is broader than approved docs; current selected posture is ambiguous.

- [ ] **G1 — Final Plan 2 closure gate**
  - **Do:** Re-audit all 27 items. Every selected item must be checked with observed Evidence; every rejected conditional item must be checked with explicit N/A decision evidence. Review cumulative diff for secrets, authority expansion, baseline noise, and unrelated dirt. Run invariant check, selected targeted suites, non-mutating reference probes, parity, protected manifest, governance, full backend, and frontend build when G0 changed frontend/docs. Record exact counts and final commits; set frontmatter `status: done` and `implementation_readiness: COMPLETE` only after all pass.
  - **Why:** Architecture decisions are not closed until implementation and evidence agree.
  - **Surfaces:** whole selected Plan 2 diff and this plan.
  - **Depends on:** G0.
  - **Failing-first / observation:** Re-walk inherited checkmarks skeptically; a missing/N/A-without-decision Evidence field fails closure.
  - **Verify:** From repo root use P0's two-command host DB export without echoing it; run `.cursor/hooks/audit-plan-discipline.sh plans/2026-08-10_1103_architecture-resource-plan-execution-and-adaptive-planning.md`; `python3 scripts/freeze_execution_baseline.py --check --in /tmp/plan2-execution-baseline.json`; `TELEMETRY_MODE=none PYTHONPATH=backend:. python3 scripts/audit_reference_probes.py --check`; `PYTHONPATH=backend:. python3 scripts/run_production_parity_eval.py --out-dir /tmp/plan2-final-parity --check`; `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests -k 'resource_planner_topology_contract or resource_planner_decision_record_io or retired_resource_planning_surfaces or canonical_adaptive_planning or resource_plan_lineage_only_contract or resource_plan_execution' -q`; return to root and run `./scripts/run_stage3_governance_regression.sh`; `cd backend && PYTHONPATH=../backend:.. python3 -m pytest`; `cd ../frontend && npm run build`; return to root and re-run the manifest check.
  - **Evidence:** _(27/27 disposition, selected decisions, targeted/full counts, reference rows, parity tuple, governance/harness counts, frontend result/N/A, manifest before/after, invariant verdict, commits, known gaps)_
  - **Invariant / manifest:** Cumulative `/invariant-check` across baseline→HEAD; all seven groups PASS. No secrets/new execution authority beyond the explicit selected decisions.
  - **Commit boundary:** Final test/evidence/plan-closure commit only.
  - **Stop:** Any unchecked/non-dispositioned item; invariant FAIL; protected drift; baseline refresh; unapproved authority; same valid gate fails twice.

## Protected artifacts and baseline policy

P0 captures `/tmp/plan2-execution-baseline.json` with the existing 13-artifact guard. The protected groups remain:

| Group | Policy |
|---|---|
| Eval/reference baselines and probe JSON | Immutable. All probes use `--check`; any desired refresh is a separate user-authorized plan. |
| 105 golden answers | Immutable; parity is the comparison, not permission to rewrite. |
| Governed use-case/skill/SPL registries | Immutable unless a selected decision explicitly needs a new contract and the user separately authorizes registry scope; neither decision currently pre-authorizes it. |
| Published architecture doc mirrors | Keep mutually identical. G0 may intentionally change them only if selected architecture changes the served diagram; record/approve and recapture that group only. |

Run the manifest before and after every runtime item. Unexpected drift is a stop condition, never a warning. `/tmp` observation artifacts are not committed.

## Global stop conditions

Stop and record the issue in the Drift log when:

1. The same valid verification gate fails twice on one item.
2. Current behavior contradicts a locked premise or selected decision.
3. A change expands execution authority beyond explicit B1/C0 approval.
4. A baseline/golden/registry would need refreshing.
5. An advisory specialist would perform live I/O or authorize execution.
6. B1 or C0 has not been explicitly completed before its conditional implementation.
7. Protected artifacts drift unexpectedly.
8. An unrelated/concurrent writer changes a relevant file or HEAD during an item.
9. Legacy discovery and live pre-SPL discovery cannot be kept observably separate.
10. LLM output could carry SPL/query/credentials/raw evidence or directly select/invoke MCP.
11. A new state channel is written without LangGraph declaration and dual-runtime proof.
12. A side-effecting or uncertain execution would be retried automatically.

Do not silently adapt, skip, weaken a test, change a decision, or switch conditional branches.

## Verification gaps

None at authoring time. Tests marked **NEW** are created in the owning item. B0's temporary wrapper body is intentionally not prewritten in this plan: its exact reviewed body/hash must be pasted into B0 Evidence before deterministic preflight and the single live invocation, so shadow-specific call delegation and output allowlisting are auditable without adding production code.

## Drift log

| Date | Note |
|---|---|
| 2026-08-10 | Plan created at `a8cef54`; no runtime implementation performed. Existing user-owned dirt recorded and excluded. |
| 2026-08-10 | Authoring plan-discipline audit run with `.cursor/hooks/audit-plan-discipline.sh`: checklist present; 27 Verify fields; summary `0 checked, 27 unchecked, 0 gap(s)`. |
| 2026-08-10 | B0 authoring preflight was exercised deterministically without a graph or LLM call: the proposed query resolved to `out_of_registry`, initial tier `T4`, processing lane `guided`, bridge-eligible `true`, with execution/SPL/containment/action signals all `false`. The lower-level route helper returned `spl_generation`, so B0 correctly asserts the `guided` lane rather than a `guided_investigation` skill label. |
| 2026-08-10 | Pre-B1 gap review confirmed a third planning rail in imperative `_run_guided_hybrid_dispatch`, current bridge triggers limited to `out_of_registry`/`near_105_question`, and promotion guards for composer `guided_hybrid_v1` and skill `guided_investigation`. Both guided flags are true on this host, so that imperative proposer is currently reserved/not attempted, but the parallel call path remains structurally reachable and parity-supported. B1/B2 now require an explicit rail, trigger-path, and guided-promotion disposition. C1-after-B2 serialization was reviewed and retained as intentional stage/commit isolation. |
| 2026-08-10 | **P0 attempt 1 STOPPED at baseline `a8cef54`, HEAD `18b9828`.** Reference probes `10/10`, parity `120 exact / 0 approved / 0 critical`, manifest 13/13 all green, but governance backend pytest failed `test_postgres_concurrent_resume_creates_single_next_version` with `handoff_not_pending` (`1 failed, 4794 passed`). Recorded at `c20be00`. Stop was correct per stop condition 2. |
| 2026-08-10 | **Diagnosis: not baseline drift.** P0 itself proved `a8cef54..HEAD` was plan-markdown only, so no runtime code had changed since the green corrective-G1 baseline — the failure could not be a regression. The test passed 8/8 in isolation. Root cause was a real check-then-lock race in `canonical_handoff_resumption._merge_clarification_answer_db`: the successor-version lookup ran *before* `load_pending_for_update`'s `SELECT ... FOR UPDATE`, so a losing concurrent resume could observe the window between `supersede_version` and `persist_handoff_record` and reject a completed peer as a stale handoff. Production-reachable via double-click/retry; analyst-visible as a spurious error instead of an idempotent replay. No SPL/MCP/execution-authority involvement. The accepted G1 baseline had been lucky, not correct. |
| 2026-08-10 | **Hotfix `f34f4d8` landed as a separate correctness commit, outside Plan 2 scope.** Both resume paths now order `lock pending row → re-read successor → idempotent replay if present → else validate`. The memory path was already safe (its caller holds `memory_handoff_lock`) but relied on an unstated precondition; reordered identically and documented so the defect class cannot survive in one backend only — no second lock, since `_handoff_lock` is non-reentrant. Barrier-synchronized regression tests added on both backends, 5 rounds each. Failing-first verified: pre-fix source fails with `handoff_not_pending`; post-fix 15 consecutive runs green (150 forced races). Gates at `f34f4d8`: full backend `4797 passed, 2 skipped, 6 xfailed, 0 failed`; governance regression PASS; manifest 13/13; invariant check 7/7 PASS. Eval reports regenerated by the gate were reverted — verdicts unchanged and verification does not refresh baselines. |
| 2026-08-10 | **Plan 2 runtime baseline rebased `a8cef54` → `f34f4d8`** and the inherited-gate row updated `4795 → 4797` (delta is exactly the two new concurrency tests; no pre-existing test changed result). P0 attempt 1's evidence is retained as a superseded record and must not be carried forward — **P0 re-runs from scratch**. Plan structure, item count (27), and both decision gates are unchanged. |
| 2026-08-10 | Residual review of the guided-rail amendment: the proposer gate at `pipeline.py:5956` is *inverted* — `ai_soc_guided_llm_enabled` true reserves the proposer (`guided_finalize_composer_reserved`), false calls it. Verified consumer set is four non-test sites: `pipeline.py:967`, `pipeline.py:1045`, `pipeline.py:5956`, `guided_llm_budget.py:12`; the three survivors are budget/deadline only. Retiring or folding the proposer therefore strands the flag's planning meaning and the `dispatch_steps.append("guided_investigation_plan_llm")` label. Both are now dispositioned inside B2-R2 and B2-W2 (retain flag for budget scope; explicit label decision) with escalation to B1 only if rename/repurpose/removal would be required. No new checklist items; count stays 27. |
| 2026-08-10 | User review before P0 found a test-state contradiction: B2-R1 is a tests-only commit but required assertions that only pass after B2-R2's removals, so R1 could not have landed green. Resolved by splitting ownership — R1 pins the current pre-retirement state behind a named expected-state contract and commits fully green (falsifiability shown by mutation, reverted); R2 flips that contract to absent as its own first reviewable step, which must go red before the removals make it green again. R1's deterministic-guided and live-pre-SPL assertions must never go red in R2. Checked the rest of the checklist for the same pattern: R1→R2 is the only item pair that splits test authoring from implementation; A0, A1.1, A1.2, B2-R3, all B2-W and all C1-E items own both, so their failing-first steps resolve within the item. B2-R2's commit boundary also rewritten to cover what it now owns (planning-model surface retirement, not just shadow/bridge). |
| 2026-08-10 | P0 STOP: valid governance regression contradicted the accepted zero-failure baseline. `test_postgres_concurrent_resume_creates_single_next_version` failed because one concurrent resume observed `handoff_not_pending`; suite result `1 failed, 4794 passed, 2 skipped, 6 xfailed`. Manifest remained `13/13`, reference probes were `10/10`, and production parity was `120 exact / 0 approved / 0 critical`. No fix or later P0/A0 work was attempted. |
| 2026-08-10 | Source audit's Post-G1 disposition and closed corrective plan read completely. Corrective plan remains closed at `e5c1937`. |
| 2026-08-10 | Topology re-measure: `get_graph()` remains 4 edges, but `compiled.builder.edges` (20 fixed edges) and `.branches` (8 mapped conditional destinations plus dynamic delegate) provide a previously undocumented falsifiable seam. A0 uses it rather than requiring unsupported dynamic `Send` exposure. |
| 2026-08-10 | `route_setup` remains registered and unreachable; deletion is planned only after A0 failing-first reachability evidence. |
| 2026-08-10 | Decision-ref inventory widened beyond the audit's three examples: additional false outputs are visible on `work_bundle.apply`, `rag_early`, and `policy_veto`. A1 covers the full remaining inventory. |
| 2026-08-10 | Dormant `ResourcePlanV2` and pure orchestration scheduler exist, but are tied to fixture/fenced legacy concepts; C1-E may not promote them without the C0 decision and boundary tests. |
| 2026-08-10 | **B2-R3 COMPLETE at `55ae6a7`, B2-R4 COMPLETE — Phase B (RETIRE) closed.** R3 removed only unreachable call sites: the evidence loop's sole initializer is the fenced `graph_node_evidence_planning`, so `loop_initialized` is permanently false on canonical turns. **`MAX_MCP_HOPS` was found NOT to be inert code** — it still bounds recipe call budgets at `evidence_loop.py:639`, so it was retained and pinned by test rather than removed; deleting it would have weakened a live bound. R4 gates: targeted 120, full backend 4846/0 failed, probes 10/10, parity 120 exact, governance PASS, manifest 13/13, and all four retired symbols absent with `shadow_status=retired` in both runtimes. Host gates need `DATABASE_URL=…@127.0.0.1:5434` because the compose hostname does not resolve outside Docker. Next gate: **C0**, undecided. |
| 2026-08-10 | **B2-R2 capability gap decided `FOLLOW_UP_REFINEMENT_DESIGN` (user).** Retiring the guided proposer made `llm_attempted` permanently false, and the deterministic baseline hardcodes `refinement_recommended=False`, so guided investigation is now **one-round** and `MAX_GUIDED_INVESTIGATION_ROUNDS` is unreachable. Investigated before deciding: no existing deterministic signal can justify a second round, because the loop's inputs are round-invariant — the baseline reads the outer `state` not the accumulating `collection_state`, collection is idempotency-deduped, and `evidence` never changes, so round N+1 is input-identical to round N. `collected_count`, `validation.blocked_resources`, `evidence_needed`, empty-source results and the refinement helpers were each inspected and rejected. **This is a known capability gap, not the intended permanent refinement architecture.** `RETIRE_PROPOSER` stays approved, no LLM proposer is restored, no weak heuristic added, and the cap/refinement contracts are retained undeleted. The missing requirement is a **round-varying planning input derived from newly collected evidence or unresolved evidence gaps**, carried into C0: `EXECUTION-DRIVEN` must evaluate it under C1-E3 `plan → collection → evidence/gap evaluation → bounded re-plan`; `LINEAGE-ONLY` must record it as a separate follow-up architecture plan. Analyst-visible: `refinement_rounds` `[0,1,2]` → `[0]`, no `guided_refinement` dispatch step. |
| 2026-08-10 | **B2-R2 COMPLETE at `3c9a685`.** Contract flip alone went red on 10 tests with RETAINED assertions green. Three modules retained on disk with zero production call sites because their tests cover non-retired behavior. Flag went 4 → 3 consumers (proposer gate 1 → 0, budget 3 unchanged). Full backend `4842 passed, 0 failed`; parity `120 exact / 0 approved / 0 critical`; manifest 13/13. |
| 2026-08-10 | **B1 DECIDED: `RETIRE`, approved by Anurag at `2026-08-10T17:29:24Z`.** `guided_hybrid_llm_rail_disposition: RETIRE_PROPOSER`. Eight dispositions bind B2-R1 → B2-R4; the whole B2-W branch (7 items) is dispositioned N/A per the conditional-item rule, alongside `bridge_trigger_match_paths` and `guided_promotion_policy`. Approver explicitly acknowledged that B0 measured **zero** shadow attempts (`draft_spl_preview_active` skipped the runner), so B0 evidences neither shadow latency nor `qu_unavailable` coverage and must not be cited for either later; `RETIRE` does not rest on those. The decision retires the current rails as fragmented/non-authoritative/discard-only/parallel authorities and does **not** reject adaptive LLM planning as a future architecture — a future design is to be a single seam above the deterministic floor. Approved order: `B2-R1 → B2-R2 → B2-R3 → B2-R4`, then stop at C0. |
| 2026-08-10 | **A0 COMPLETE at `03b333b`.** The union-masking defect was confirmed empirically before removal: `resource_planner_graph_edges()` returned two edges that exist nowhere in the builder. `route_setup` was proven orphaned by the failing reachability test and removed; final topology is fixed 20 / mapped 8 / dynamic 4 / documented 30, reconciled by exact equality, 23 registered nodes, zero unreachable. No dispatch, specialist-authority, MCP, SPL, or scheduling behavior changed; parity stayed `120 exact / 0 approved / 0 critical`. |
| 2026-08-10 | **Host environment cannot run the governance gate as-is — not a code regression.** `DATABASE_URL` targets `postgres:5432`, which does not resolve outside Docker (no `/etc/hosts` entry, no DNS), so every canonical handoff save/load raises from `asyncpg.create_pool` and the clean-answer eval refuses ~115 rows with `ARTIFACT_WRITE_REFUSED: …:exception`. Reproduced identically **with the A0 diff stashed at the P0 baseline** (`EXIT=3`), so attribution is environmental. The container is not a substitute: it aborts on the first gate because `/tmp/ai-soc-references/Anthropic-Cybersecurity-Skills` is not mounted. The gate passes on the host with `DATABASE_URL` overridden to the published `127.0.0.1:5434`; that override is how governance must be invoked from the host until the clone is mounted or the URL is host-resolvable. Reference probes have the same split — they fail on the host at `pipeline.py:3669` and pass `10/10` in-container. |
| 2026-08-10 | Latent pre-existing bug found while triaging the above, **left unfixed as out of A0's commit boundary**: `pipeline.py:3669` calls `.get()` on `_query_signals_from_state()`, which returns `None` whenever `query_to_intent` is absent, raising `AttributeError` instead of degrading. Reachable whenever canonical planning cannot complete. Needs its own correctness item. |
| 2026-08-10 | Governance regenerated the same five `docs/evals/` reports as at P0, and this time with genuine observed-output deltas (parity rows 112–113 `contract_answer_mode` → `None`, `enabled_sections` 6→8, `mitre_technique_ids` 0→2, `mitre_answer_visible` False→True). Re-running the parity eval **with the A0 diff stashed** reproduced every delta byte-for-byte, so the churn is host-environment nondeterminism, not an A0 behavior change. Files reverted; verdicts were `120 exact` in both runs. A stray newline appended to `backend/app/chat/detail_tools/__init__.py` by the run was also reverted. |
| 2026-08-10 | **Fresh P0 COMPLETE at runtime baseline `f34f4d8`, start HEAD `17ebd19`.** Baseline→HEAD and runtime-worktree guards passed; manifest 13/13, reference probes 10/10, parity 120 exact with zero approved/critical, governance PASS, and independent backend `4797 passed, 2 skipped, 6 xfailed`. Safe host, topology (25 nodes; builder 20 fixed + 8 mapped + 4 dynamic Send targets), and decision-record (25 shapes; 107 channels) inventories were re-measured. Governance's five regenerated eval files had identical verdict/classification projections and summary counts; metadata/timing/order/observed-output churn was reverted. No runtime change; A0 not started. |
| 2026-08-10 | **A1.1 COMPLETE at `a435d8a`.** The complete post-A0 inventory contains 24 decision-record shapes. Failing-first isolated one vocabulary defect, root `normalized_spl`; it is now the descriptive nested ref `spl_validation.normalized_spl`. All roots/dotted paths validate, refs have zero scheduling consumers, targeted tests are 32 passed, manifest 13/13, and invariants 7/7. Semantic overclaims remain explicit for A1.2. |
| 2026-08-10 | **A1.2 COMPLETE at `7f9121a`.** All 24 record shapes are now semantically grounded; every direct wrapper and four specialist producers have representative differential coverage, trace-only nodes carry empty output lists, and a nonexistent-output mutation fails. Exact valid host gate: 47 passed; manifest 13/13; invariants 7/7. Two accidentally concurrent restricted-sandbox copies stalled after 25 tests without an assertion result; both exact PIDs were terminated and one host-reachable rerun with the already-proven DB override passed in 8.77s. This was execution-environment noise, not a valid gate failure. |
| 2026-08-11 | **C0 DECIDED: `EXECUTION-DRIVEN`, approved by Anurag at `2026-08-11T05:53:15Z`.** Activation posture `DEDICATED_DEFAULT_FALSE_FLAG` with approved flag `AI_SOC_RESOURCE_PLAN_EXECUTION_ENABLED` (default false); `v1_v2_posture: EXTEND_LIVE_RESOURCE_PLAN` — no wholesale `ResourcePlanV2`/`orchestration_scheduler` promotion, concept reuse only after per-concept authority-boundary verification. Parallelism limited to genuinely independent safe/read-only steps; SPL validation stays before the MCP gate; HIL/RBAC/policy stay authoritative; invalid/unsupported plans downgrade deterministically to the fixed schedule; uncertain/side-effecting operations are never auto-retried. The opposite-order matrix confirmed the lineage-only premise (4/5 probes composed; reversing steps changed `step_walk_order` but not the schedule, and `step_walk == legacy` both directions). The guided probe composed no ResourcePlan at all under this host's `guided_hybrid` posture — recorded and carried into C1-E3 alongside the B2-R2 `FOLLOW_UP_REFINEMENT_DESIGN` requirement. `C1-L` dispositioned N/A (1 item). Next: `C1-E1`. |
| 2026-08-11 | Before the C0 edit, `backend/app/chat/detail_tools/__init__.py` again carried the known import-time stray-newline artifact (same as the A0 run); reverted, leaving the runtime-scoped worktree clean. Not a code change. |
| 2026-08-10 | **B0 COMPLETE with one full graph call.** Preflight was `out_of_registry` / T4 / `guided`, bridge-eligible, and non-executing/non-action-shaped. Shadow-specific generate attempts were **0** because finalize reported `draft_spl_preview_active`; deterministic plan source remained `deterministic`, no plan was returned/promoted/discarded, graph elapsed 954 ms, and manifest stayed 13/13. The JSON artifact passed required-key and sensitive-field scans. Existing non-shadow client logging exposed a credential-free local endpoint on stderr only; this was excluded from the JSON evidence. B0 therefore does not price `qu_unavailable` or any posture in which the shadow runner actually enters. |
