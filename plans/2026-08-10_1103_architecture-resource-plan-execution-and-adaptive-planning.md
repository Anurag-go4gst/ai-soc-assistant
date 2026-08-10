---
name: architecture-resource-plan-execution-and-adaptive-planning
overview: "Make Resource Planner topology and decision-record dataflow falsifiable, empirically price the live shadow-planning path, and gate any adaptive-planning or execution-order change behind explicit COE decisions."
status: draft
date: 2026-08-10
canonical_plan: plans/2026-08-10_1103_architecture-resource-plan-execution-and-adaptive-planning.md
source_audit: plans/2026-08-10_0555_architecture-audit-query-understanding-and-plan-creation.md
source_plan: plans/2026-08-08_1824_architecture-review-corrective-actions.md
baseline_head: a8cef54
implementation_readiness: "READY_FOR_P0_AND_MECHANICAL_A_ITEMS; BLOCKED_AT_B1_AND_C0_DECISION_GATES"
---

# Plan 2 — ResourcePlan execution and adaptive-planning architecture

## Objective

Close the remaining post-G1 architecture gaps without reopening the completed corrective plan. Done means: Resource Planner topology assertions are independently falsifiable; every Resource Planner decision record names real state inputs and outputs; one bounded T4 observation establishes whether the shadow planner makes and discards a real model request; the user/COE explicitly chooses **RETIRE** or **RE-WIRE** for legacy discovery and LLM planning; the user/COE separately chooses **LINEAGE-ONLY** or **EXECUTION-DRIVEN** ResourcePlan ordering; only the selected conditional branches are implemented; current deterministic, SPL, MCP, HIL, RBAC, parity, and baseline invariants remain green.

This is the execution plan, not execution. Plan authoring changed no runtime code and did not run the live T4 probe.

## Sources and authority

- The authoritative open-work source is the source audit's `## Post-G1 disposition (2026-08-10)` section. Earlier audit status text is historical evidence only.
- The corrective plan is closed at `16/16`, final commit `e5c1937`; it supplies locked decisions and accepted G1 evidence and must not be reopened.
- Runtime code at `a8cef5437224a003de69f92a23edfe7a3ed5e75c` is authoritative over both documents. `baseline_head: a8cef54` is a runtime-content anchor, not a requirement that execution begin with HEAD checked out at that exact commit.
- HEAD may advance beyond `a8cef54` through plan/audit-only commits under `plans/*.md`. Before P0 does anything else, `git diff a8cef54..HEAD` must prove that no runtime, config, script, governed-registry, frontend, backend, or other non-plan file changed. Any non-`plans/*.md` path is drift and stops P0.
- The only changes from `e5c1937` to authoring HEAD are the two plan/audit markdown files. The accepted runtime baseline therefore has no intervening runtime diff, but **P0 must still re-run and record fresh results before implementation**.

## Verified starting architecture at authoring

| Surface | Current observation at `a8cef54` |
|---|---|
| Worktree | `master` is ahead of `origin/master` by 20. Existing user-owned dirt: `.claude/settings.local.json`, `plans/README.md`, `.playwright-mcp/`, two G0 PNGs, and `output/`. Do not absorb, clean, or overwrite them. |
| Protected manifest | Existing `/tmp/exec-baseline.json` checks clean: `protected artifacts unchanged (13 checked)`. P0 captures a new Plan 2 manifest at `/tmp/plan2-execution-baseline.json`. |
| Accepted pre-Plan-2 gates | Corrective G1 recorded reference probes `10 PASS / 0 DRIFT`, parity `120 exact / 0 approved / 0 critical`, governance PASS with `4795 passed, 2 skipped, 6 xfailed`, separate backend `4795 passed, 2 skipped, 6 xfailed`, and frontend build PASS. These are inherited evidence, not a substitute for P0. |
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
2. The audit described `route_setup` as stale/orphan; re-verification confirms it is still registered and unreachable at `a8cef54`.
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

No B2 item is executable until this block is filled by the user/COE:

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

No C1 item is executable until this block is filled by the user/COE:

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

- [ ] **P0 — Freeze and freshly verify the post-G1 baseline**
  - **Do:** With no runtime edits, treat `a8cef54` as the runtime baseline and first prove that every committed baseline→HEAD path is plan/audit markdown under `plans/*.md`; HEAD itself may be newer. Also prove the current worktree has no runtime-path dirt before recording HEAD, full status, safe host posture, Plan 2 protected manifest, reference probes, production parity, governance, full backend pytest, topology inventory, and decision-record inventory. Export the host-reachable PostgreSQL URL for the whole chain. Do not refresh any baseline and do not include existing dirt.
  - **Why:** Every later result must compare against a measured `a8cef54` baseline, not inherited prose.
  - **Surfaces:** `/tmp/plan2-execution-baseline.json`; `/tmp/plan2-p0-*`; plan Evidence only.
  - **Depends on:** none.
  - **Failing-first / observation:** Observation only; no fix is allowed. A non-`plans/*.md` path in `a8cef54..HEAD`, runtime worktree dirt, or any mismatch with the inherited G1 counts is drift and stops the item.
  - **Verify:** From repo root, run exactly: `git diff --name-only a8cef54..HEAD | tee /tmp/plan2-baseline-head-paths.txt`; `! rg -n -v '^plans/[^/]+\.md$' /tmp/plan2-baseline-head-paths.txt`; `git status --short -- backend frontend scripts env docker-compose.yml | tee /tmp/plan2-runtime-worktree-status.txt`; `test ! -s /tmp/plan2-runtime-worktree-status.txt`; `export DATABASE_URL="$(sed -n 's/^DATABASE_URL=//p' .env)"`; `export DATABASE_URL="${DATABASE_URL/@postgres:5432/@127.0.0.1:5434}"`; `test -n "$DATABASE_URL"`; `git rev-parse HEAD`; `git status --short --branch`; `python3 scripts/freeze_execution_baseline.py --capture --out /tmp/plan2-execution-baseline.json`; `python3 scripts/freeze_execution_baseline.py --check --in /tmp/plan2-execution-baseline.json`; `TELEMETRY_MODE=none PYTHONPATH=backend:. python3 scripts/audit_reference_probes.py --check`; `PYTHONPATH=backend:. python3 scripts/run_production_parity_eval.py --out-dir /tmp/plan2-p0-parity --check`; `./scripts/run_stage3_governance_regression.sh`; `cd backend && PYTHONPATH=../backend:.. python3 -m pytest`; return to root and re-run the manifest check and `git status --short`. Never echo `DATABASE_URL`.
  - **Evidence:** **STOPPED 2026-08-10; checkbox intentionally remains open.** Baseline→HEAD allowed paths: `plans/2026-08-10_1103_architecture-resource-plan-execution-and-adaptive-planning.md`, `plans/README.md`; non-plan path check passed. Runtime-path worktree check was empty. Start/final HEAD `18b982842c4b201932d490fd03a3ea1f5b61a78c`; unrelated status remained `.claude/settings.local.json` modified plus untracked `.playwright-mcp/`, two G0 PNGs, and `output/`. Protected manifest captured 13 artifacts and passed before/after (`protected artifacts unchanged (13 checked)`). Valid unsandboxed reference rerun: all P1–P6/N1–N4 PASS, `10/10`, zero drift. Production parity: `total=120`, `base_105=105`, `exact=120`, `approved=0`, `critical=0`. Governance pre-pytest gates passed (factory/crosswalk/validation checks; sentinel `17/17`; Tier-D `17/17`; OT `6/6`; power-industry warnings remained non-gating), but canonical backend pytest failed `app/tests/integration/test_clarification_postgres.py::test_postgres_concurrent_resume_creates_single_next_version`: concurrent resume raised `ClarificationResumeError("handoff_not_pending")`; final count `1 failed, 4794 passed, 2 skipped, 6 xfailed, 2 warnings in 549.10s`. Accepted zero-failure baseline contradicted, so the separate backend run, fresh safe-host/topology/record inventories, P0 check-off, and all later items were not run. Initial sandboxed probe/parity attempt was invalid due denied `/var/lib` writes and was replaced by the valid escalated PASS results above. No runtime change; invariant check N/A.
  - **Invariant / manifest:** Manifest must pass before and after; no runtime diff means invariant check is N/A.
  - **Commit boundary:** Evidence-only plan edit; no runtime commit.
  - **Stop:** Any non-`plans/*.md` baseline→HEAD path, runtime worktree dirt, protected drift, baseline mutation, relevant concurrent writer, or gate result contradicting the accepted baseline.

- [ ] **A0 — Make Resource Planner topology independently falsifiable and remove only the proven orphan**
  - **Do:** Add `backend/app/tests/test_resource_planner_topology_contract.py` (**NEW**) and first prove the current union can mask invented edges and `route_setup` is unreachable. Then split topology surfaces: fixed edges from `compiled.builder.edges`; mapped conditional destinations from `compiled.builder.branches`; dynamic delegate edges from direct `Send` inspection; documented edges kept separate. Make `resource_planner_graph_edges()` return runtime-derived topology only (no documented union), add an explicit reconciliation result, and require documented topology to equal runtime fixed + mapped conditional + dynamic fan-out after normalized start/end handling. Assert exact four Send targets, exact specialist fan-in, all registered nodes reachable or explicitly terminal, and mutation-negative controls for invented/missing/wrong edges. Only after the failing reachability test, remove `rp_node_route_setup`, its registration, and fabricated documented edges.
  - **Why:** A documented contract must not certify itself, and an orphan must be proven against runtime construction before deletion.
  - **Surfaces:** `backend/app/graph/resource_planner_graph.py`; new topology test; existing skeleton/cardinality/dual-runtime/SPL-source parity tests.
  - **Depends on:** P0.
  - **Failing-first / observation:** Before implementation, run the new tests and record failures for documented/runtime disagreement and orphan reachability. Mutation tests must fail when an extra documented edge is injected, any Send is removed/retargeted, fan-in is removed, or an orphan is added.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_resource_planner_topology_contract.py app/tests/test_resource_planner_graph_skeleton.py app/tests/test_resource_planner_specialist_report_cardinality.py app/tests/test_dual_runtime_single_orchestration.py app/tests/test_langgraph_spl_source_resolve_parity.py -q`; then from root `python3 scripts/freeze_execution_baseline.py --check --in /tmp/plan2-execution-baseline.json` and `.cursor/hooks/audit-plan-discipline.sh plans/2026-08-10_1103_architecture-resource-plan-execution-and-adaptive-planning.md`.
  - **Evidence:** _(failing-first assertions; final edge counts by source; four Send targets; reachability result; removed symbols; pytest count; manifest; commit)_
  - **Invariant / manifest:** Full invariant check; prove four specialists and no dispatch/authority change.
  - **Commit boundary:** One topology/test commit; no decision-record, planning, or scheduling edits.
  - **Stop:** Builder internals do not expose stable fixed/branch data; a second node is unexpectedly orphaned; removing `route_setup` changes any parity probe; dynamic Send needs framework internals rather than direct contract invocation.

- [ ] **A1.1 — Inventory every decision-record reference and enforce the state-channel vocabulary**
  - **Do:** Add `backend/app/tests/test_resource_planner_decision_record_io.py` (**NEW**). Inventory every remaining Resource Planner record shape after A0, including specialist records and rejection paths. For each record, document actual read roots, write roots, and declared refs in a test-owned expected table. Validate every declared root against `ResourcePlannerGraphState.__annotations__`; allow a dotted path only when its root is a real channel and validate the nested path on representative data. Correct nonexistent-channel labels such as root `normalized_spl` to the real nested channel. Keep refs descriptive only—no code may consume them for scheduling.
  - **Why:** Schema-valid labels are the minimum mechanical prerequisite before judging semantic truth.
  - **Surfaces:** `backend/app/graph/resource_planner_graph.py`; `backend/app/chat/decision_record.py`; new test; `backend/app/tests/test_decision_record.py`.
  - **Depends on:** A0.
  - **Failing-first / observation:** The new inventory test must initially fail on `normalized_spl` and any other nonexistent/dangling path discovered; paste the complete inventory into Evidence.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_resource_planner_decision_record_io.py app/tests/test_decision_record.py app/tests/test_planner_hierarchy_contracts.py app/tests/test_state_channel_parity.py -q`; root manifest check and plan audit as in A0.
  - **Evidence:** _(record-shape count, full inventory artifact/test table, initial invalid refs, final zero invalid roots/paths, pytest, manifest, commit)_
  - **Invariant / manifest:** Invariant check; assert no new state channel unless independently justified and declared on both runtime paths.
  - **Commit boundary:** Schema/inventory commit only; semantic output corrections belong to A1.2.
  - **Stop:** A ref requires secret/raw payload exposure; tests would infer I/O from node names; validation would become a runtime dependency mechanism.

- [ ] **A1.2 — Correct semantic inputs/outputs and prove representative node dataflow**
  - **Do:** Trace each record to actual function reads/writes and correct false labels, including but not limited to `work_bundle.apply`, `rag_early`, `mcp_execution_gate`, `decide_facts`, `answer_guard`, and `policy_veto`. Add representative differential tests that call each wrapper with sentinel state/monkeypatched pure workers, compare pre/post root channels excluding `decision_log`/`rp_graph_trace`, and assert declared outputs are genuinely produced by the logical node. Empty output lists are valid for trace-only nodes. Specialist records may name the specialist report their logical node produced, but the test must observe that producer directly. Do not turn refs into execution dependencies.
  - **Why:** Existing labels overclaim dataflow and cannot safely support architecture review or later telemetry.
  - **Surfaces:** same graph/test files as A1.1; worker wrappers in `backend/app/chat/pipeline.py` are read anchors, not refactor targets unless a false label cannot otherwise be corrected.
  - **Depends on:** A1.1.
  - **Failing-first / observation:** Record failures proving the known overclaims before correction. Negative controls must fail when a nonexistent output is added to a record.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_resource_planner_decision_record_io.py app/tests/test_resource_planner_dry_runs.py app/tests/test_resource_planner_route_wiring.py app/tests/test_control_plane_trace.py app/tests/test_resource_planner_validated_work_bundle.py -q`; root manifest check and plan audit.
  - **Evidence:** _(per-record before/after refs, differential test result, no secret refs, pytest, manifest, invariant, commit)_
  - **Invariant / manifest:** Full invariant check; telemetry/redaction and append-only decision-log behavior stay unchanged.
  - **Commit boundary:** One decision-record correctness commit; no topology/scheduler/LLM edits.
  - **Stop:** A correct record would require moving authority or adding runtime writes solely to satisfy telemetry; same differential gate fails twice.

- [ ] **B0 — Observe one bounded live-core T4 planning path**
  - **Do:** Observation only, in two stages. **B0 preflight — deterministic only:** use `understand_query()`, `extract_query_signals()`, `initial_tier_for_match_path()`, `processing_lane_for_initial_tier()`, and `bridge_trigger_match()` without invoking the graph or any LLM; require initial tier T4, processing lane `guided`, bridge eligibility, no explicit execution request, and no destructive/action intent. Treat `guided` as the processing-lane assertion—not a requirement that the lower-level deterministic route helper return the `guided_investigation` skill. **B0 observation — exactly one full graph call:** only after preflight passes, create a temporary/non-production diagnostic wrapper (prefer `/tmp`; if reusable, it must have zero production importers) that instruments the shadow planner's module-local `resource_plan_shadow.propose_validated_llm_plan` bridge path. Inject a counting proxy around the actual client returned for that proposal, increment only `shadow_bridge_generate_attempts`, and delegate unchanged; do not patch a generic/global client `generate()` used by other LLM roles. Invoke `run_resource_planner_graph(ChatRequest(...))` exactly once with the preflighted query and live synthesis left enabled. Emit only sanitized JSON: shadow bridge attempt count; `evidence_plan.resource_plan.provenance.llm_bridge`; `control_plane_trace.resource_plan_shadow`; `rp_graph_trace.visited_nodes`; deterministic plan source and before/after step fingerprints; promotion/discard result; safe budget role/outcome/latency; elapsed time. Do not print prompts, completions, credentials, endpoint URLs, SPL, or raw evidence.
  - **Why:** Static reachability cannot prove whether a real shadow request occurs, returns a plan, is promoted, or is discarded.
  - **Surfaces:** temporary probe; `backend/app/planner/resource_plan_shadow.py`; `llm_plan_bridge.py`; `pipeline.py` finalize trace; `resource_planner_graph.py` entrypoint. No production edit.
  - **Depends on:** A1.2.
  - **Failing-first / observation:** Use query `Investigate suspicious authentication behavior across identity and endpoint telemetry; identify what evidence would be needed, but do not run or modify anything.` Run deterministic preflight first. If its initial tier is not T4, its processing lane is not `guided`, it is not bridge-eligible, it requests execution, or it is action/containment-shaped, record the contradiction and stop before any full graph invocation; do not try a query ladder.
  - **Verify:** Export the host DB URL for the whole probe. Run `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=backend:. python3 /tmp/plan2_observe_t4_planning.py --preflight-only | tee /tmp/plan2-t4-planning-preflight.json`; validate with `python3 -m json.tool /tmp/plan2-t4-planning-preflight.json` and `jq -e '.initial_tier == "T4" and .processing_lane == "guided" and .bridge_trigger_eligible == true and .run_execution == false and .explicit_run_spl == false and .block_or_contain == false and .action_or_containment_shaped == false' /tmp/plan2-t4-planning-preflight.json`. Only if that passes, run `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=backend:. python3 /tmp/plan2_observe_t4_planning.py --observe | tee /tmp/plan2-t4-planning-observation.json`; validate sanitization and required keys with `python3 -m json.tool /tmp/plan2-t4-planning-observation.json` and `jq -e '.shadow_bridge_generate_attempts >= 0 and (.rp_graph_trace.visited_nodes|type=="array") and (.resource_plan_shadow|type=="object") and (.elapsed_ms|type=="number")' /tmp/plan2-t4-planning-observation.json`; re-run the manifest check. The exact temporary script body must be pasted into Evidence before execution so review can confirm deterministic-only preflight, one graph call, shadow-specific delegation, and allowlisted output.
  - **Evidence:** _(script body/hash, deterministic preflight JSON and query classification/match path, shadow-specific attempt count, shadow trace, visited nodes, plan returned/promoted/discarded, step fingerprints, budget/latency, elapsed, manifest, explicit limitation that this one `out_of_registry` observation does not price `qu_unavailable` or other trigger-path postures)_
  - **Invariant / manifest:** No runtime diff. If a reusable diagnostic script is committed, run invariant/redaction review and commit it separately.
  - **Commit boundary:** Evidence-only plan update; normally no code commit.
  - **Stop:** Deterministic preflight fails; the full graph is invoked before preflight passes; instrumentation patches a generic/global LLM method or cannot isolate the shadow planner bridge role; probe would need destructive execution; more than one shadow bridge attempt; final/live synthesis would need disabling; output contains sensitive data; evidence cannot distinguish attempted call from a skipped call.

- [ ] **B1 — COE decision: RETIRE or RE-WIRE planning/discovery architecture**
  - **Do:** Present B0 evidence, the three-surface planning inventory (fenced bridge, discard-only shadow runner, imperative guided-hybrid proposer), cost/latency, and the two options in this plan. The user/COE fills every required B1 decision field, including guided-rail disposition and, for RE-WIRE, per-match-path trigger coverage plus both guided-promotion exclusions. Note for the approver that either rail disposition also strands two dependent surfaces — the *inverted* `ai_soc_guided_llm_enabled` proposer gate (whose three budget/deadline consumers survive either way) and the `guided_investigation_plan_llm` dispatch-step label. The default executor disposition is retain-the-flag-for-budget-scope-only plus an explicit label decision, handled inside B2-R2/B2-W2; escalate to this gate only if a coherent outcome would require renaming, repurposing, or deleting the flag. Do not infer coverage for `qu_unavailable` from B0's single `out_of_registry` observation. Do not implement either branch. Disposition the rejected B2 branch N/A.
  - **Why:** This changes intended architecture and cannot be selected by an executor.
  - **Surfaces:** this plan only.
  - **Depends on:** B0.
  - **Failing-first / observation:** Decision gate; no code.
  - **Verify:** After the decision edit, run `rg -n 'selected_posture.*(RETIRE|RE-WIRE)|approved_by|approved_at|B0_evidence_reference|guided_hybrid_llm_rail_disposition|bridge_trigger_match_paths|guided_promotion_policy' plans/2026-08-10_1103_architecture-resource-plan-execution-and-adaptive-planning.md` and the plan-discipline audit.
  - **Evidence:** _(selected option, approver/date, rationale, guided-rail disposition, complete RE-WIRE config/match-path/promotion subfields if applicable, N/A disposition count)_
  - **Invariant / manifest:** N/A; no runtime change.
  - **Commit boundary:** Optional plan-only decision commit; no runtime files.
  - **Stop:** No explicit choice; guided-hybrid proposer is left as a parallel/undispositioned authority; incomplete RE-WIRE discovery/flag/budget/match-path/promotion semantics; trigger scope and guided promotion policy contradict each other; decision conflicts with locked invariants.

- [ ] **B2-R1 — RETIRE: pin deterministic canonical behavior and the live pre-SPL boundary**
  - **Do:** If RETIRE selected, add `backend/app/tests/test_retired_resource_planning_surfaces.py` (**NEW**) with exact canonical plan/dispatch fingerprints across T0–T4, a static/call-count inventory of all three planning surfaces in both runtimes, explicit proof the legacy loop is not visited, and explicit proof dispatch-v2 pre-SPL discovery still feeds the compiler/saved-search preference when authorized. Capture deterministic guided dispatch/validation/collection behavior separately from the guided LLM proposer. Add negative controls that fail if those mechanisms are conflated. **R1 pins the current pre-retirement state and must finish fully green.** Express the planning-surface inventory as a single named expected-state contract (for example a `PLANNING_SURFACE_EXPECTATION` table the assertions read) so R2 can flip it from present-and-counted to absent in one reviewable edit. Do **not** commit an assertion whose expected production state belongs to R2 — post-retirement absence is R2's contract, not R1's. Demonstrate falsifiability here by mutation or temporary local assertion, recorded in Evidence and reverted before commit.
  - **Why:** Cleanup cannot begin without separate tripwires for what must be retired and what must remain live — but a tripwire committed red is indistinguishable from a broken suite, and the plan forbids landing a knowingly failing test.
  - **Surfaces:** new test; current resource-plan, shadow, guided proposer/hybrid, evidence-loop, and dispatch-v2 tests.
  - **Depends on:** B1=`RETIRE`.
  - **Failing-first / observation:** New test must capture current shadow call, fenced bridge, direct imperative guided proposer, legacy fence, deterministic guided behavior, and live pre-SPL distinction before removal. Falsifiability is proven against the **pinned current state** — each assertion must fail under a mutation that conflates the three surfaces, removes a live pre-SPL symbol, changes a deterministic fingerprint, or misreports a planning-surface call count. Record those mutation failures in Evidence, then revert them; the committed suite is green.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_retired_resource_planning_surfaces.py app/tests/test_resource_plan_shadow.py app/tests/test_guided_investigation_plan_llm.py app/tests/test_guided_investigation_llm_firewall.py app/tests/test_guided_hybrid_collection.py app/tests/test_evidence_loop_graph.py app/tests/test_dispatch_authority_wiring.py app/tests/test_pipeline_dispatch_phase4.py app/tests/test_pipeline_dispatch_phase5.py app/tests/test_pipeline_dispatch_phase6.py -q` — must be fully green, zero failures and zero `xfail`/`skip` standing in for R2 work; manifest check.
  - **Evidence:** _(three-surface inventory/call counts, named expected-state contract, deterministic fingerprints, guided-proposer versus guided-execution distinction, live pre-SPL distinction assertions, mutation-failure log plus proof of revert, green pytest count, manifest, invariant, commit)_
  - **Invariant / manifest:** Full invariant check; no runtime behavior change in this test-first commit.
  - **Commit boundary:** Tests only, pinning current state; no expected-state assertion that only passes after R2.
  - **Stop:** Live pre-SPL discovery cannot be isolated; current canonical output differs from P0; the suite cannot be made green without either changing runtime behavior (that is R2) or weakening an assertion.

- [ ] **B2-R2 — RETIRE: remove the discarded shadow call and unreachable promotion surfaces**
  - **Do:** Remove the real shadow model call from canonical finalize and replace only any required trace compatibility with an explicit deterministic `retired`/`not_called` posture. Inventory all callers before removing `resource_plan_shadow.py`, the unreachable inline bridge application, promotion merge, or tests. Apply B1=`RETIRE_PROPOSER` to the imperative guided-hybrid rail: remove its direct `propose_investigation_plan_llm` call and dedicated proposer authority, but retain deterministic guided dispatch, committed-plan projection, Validator A/B, and evidence collection wherever consumer proof shows they remain used. Delete only surfaces proven to have no retained consumer. Preserve generic LLM client infrastructure used by other roles. Two follow-on surfaces the proposer removal exposes must be dispositioned in the same commit, not left implicit: (a) **`ai_soc_guided_llm_enabled` semantics.** Its proposer consumer is an *inverted* gate — flag true reserves the proposer with `guided_finalize_composer_reserved`, flag false calls it — so removing the `else` branch deletes the flag's only proposer meaning while its three budget/deadline consumers (`pipeline.py:967`, `pipeline.py:1045`, `guided_llm_budget.py:12`) legitimately remain. Re-verify the current consumer set by `rg`, retain the flag for budget/deadline scope, and record explicitly that it no longer gates any planning-model call; do not rename, repurpose, or delete it here. (b) **Guided dispatch-step trace compatibility.** The `dispatch_steps.append("guided_investigation_plan_llm")` emitter is gated on `llm_result.attempted`; state whether the step label is removed or pinned absent, and prove the chosen posture against trace/scorecard consumers found by `rg` — the shadow `retired`/`not_called` clause above covers the shadow runner only.
  - **Why:** RETIRE should neither spend a model hop on a discarded result nor retain a separate imperative planning authority. A flag whose name still implies planning authority, or a dispatch-step label that outlives its producer, reintroduces exactly the documentation/runtime divergence this plan closes.
  - **Surfaces:** `pipeline.py`; `resource_plan_shadow.py`; `plan_promotion_merge.py`; `llm_plan_bridge.py`; `guided_investigation_plan_llm.py`; `guided_hybrid_executor.py` and guided validators/collection as retain-boundary anchors; related tests and trace scorecard consumers found by `rg`.
  - **Depends on:** B2-R1.
  - **Failing-first / observation:** Flip R1's named expected-state contract from present-and-counted to absent **first**, as a separate reviewable step; that edit alone must make the suite red against the un-retired runtime, proving the assertions bind. Then implement the removals until it is green again. R1's deterministic-guided and live-pre-SPL assertions stay unchanged and must never go red — a failure there means retirement overreached. Consumer inventory is mandatory before deletion.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_retired_resource_planning_surfaces.py app/tests/test_resource_plan_shadow.py app/tests/test_llm_primary_planning.py app/tests/test_llm_plan_bridge.py app/tests/test_llm_plan_bridge_promotion.py app/tests/test_guided_investigation_plan_llm.py app/tests/test_guided_investigation_llm_firewall.py app/tests/test_compose_guided_resource_plan.py app/tests/test_control_plane_trace.py app/tests/test_cisco_live_chat_contract.py -q`; production parity `--check`; manifest check.
  - **Evidence:** _(three-surface consumer inventory, removed/retained guided surfaces, zero planning-model attempt proof in both runtimes, deterministic guided parity, shadow trace compatibility, `ai_soc_guided_llm_enabled` consumer list before/after with retained budget scope stated, guided dispatch-step label disposition and its consumer proof, pytest/parity/manifest/invariant, commit)_
  - **Invariant / manifest:** Full invariant check; deterministic plan fingerprints unchanged. Flag-group review must show no flag renamed, repurposed, defaulted on, or left gating a removed planning call.
  - **Commit boundary:** Planning-model surface retirement only — shadow call, unreachable bridge/promotion surfaces, imperative guided proposer, plus the dependent guided flag-scope and dispatch-step-label dispositions and the R1 expected-state flip. No legacy discovery deletion.
  - **Stop:** A planning consumer outside the three inventoried surfaces appears; the known guided proposer cannot be retired without an unapproved analyst-visible change; removing a surface changes deterministic plans or response authority; `ai_soc_guided_llm_enabled` would need renaming/repurposing/removal to keep its remaining consumers coherent, or the guided dispatch-step label has a consumer that cannot tolerate either disposition — both are B1 scope, not executor scope.

- [ ] **B2-R3 — RETIRE: remove fenced legacy discovery/chronology and inert hop semantics**
  - **Do:** Re-inventory non-test consumers. Remove `_run_discovery_loop_imperative`, legacy `graph_node_evidence_planning` discovery/chronology/observer flow, inert `MAX_MCP_HOPS` live claims, and dedicated modules only where no retained consumer exists. Re-check that R2 removed the imperative `guided_investigation_plan_llm` proposer without classifying the still-consumed deterministic guided-hybrid executor/validators/collection as legacy discovery. Keep unrelated observer/recipe utilities if another approved path uses them. Do not touch `graph_node_pre_spl_mcp_discovery` or dispatch-v2 context.
  - **Why:** RETIRE should make canonical architecture honest without deleting the separate live discovery mechanism.
  - **Surfaces:** `pipeline.py`; `evidence_loop.py`; `linear_graph_legacy.py`; `guided_investigation_plan_llm.py` absence check; `guided_hybrid_executor.py`/guided validators/collection retention checks; observer/recipe modules and tests proven dead by inventory; dispatch-v2 tests as guard.
  - **Depends on:** B2-R2.
  - **Failing-first / observation:** Static caller test must fail while fenced legacy symbols remain and fail if any live pre-SPL symbol is removed.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_retired_resource_planning_surfaces.py app/tests/test_evidence_loop.py app/tests/test_evidence_loop_all_tier_discovery.py app/tests/test_evidence_loop_graph.py app/tests/test_evidence_loop_recipe.py app/tests/test_guided_investigation_llm_firewall.py app/tests/test_guided_hybrid_collection.py app/tests/test_mock_mcp_discovery_gating.py app/tests/test_dispatch_authority_wiring.py app/tests/test_pipeline_dispatch_phase4.py app/tests/test_pipeline_dispatch_phase5.py app/tests/test_pipeline_dispatch_phase6.py -q`; manifest check.
  - **Evidence:** _(consumer graph, symbols/modules removed or retained with reason, live pre-SPL tests, pytest/manifest/invariant, commit)_
  - **Invariant / manifest:** Full invariant check; zero change to MCP execution gate/SPL validator.
  - **Commit boundary:** Legacy discovery retirement only.
  - **Stop:** Any symbol has a current canonical/live consumer; deletion would weaken a gate or remove pre-SPL discovery.

- [ ] **B2-R4 — RETIRE: branch regression proof**
  - **Do:** Re-run targeted retirement, dual-runtime, reference, parity, and governance gates; record that deterministic canonical plans and analyst-visible authority are unchanged and neither runtime retains a ResourcePlan/guided-plan proposer model hop.
  - **Why:** Cleanup is complete only if absence and parity are both proven.
  - **Surfaces:** tests/evidence only.
  - **Depends on:** B2-R3.
  - **Failing-first / observation:** No implementation; repair only failures caused within B2-R scope.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_retired_resource_planning_surfaces.py app/tests/test_resource_plan_shadow.py app/tests/test_llm_primary_planning.py app/tests/test_llm_plan_bridge.py app/tests/test_guided_investigation_plan_llm.py app/tests/test_guided_investigation_llm_firewall.py app/tests/test_guided_hybrid_collection.py app/tests/test_evidence_loop.py app/tests/test_evidence_loop_graph.py app/tests/test_dispatch_authority_wiring.py app/tests/test_pipeline_dispatch_phase4.py app/tests/test_pipeline_dispatch_phase5.py app/tests/test_pipeline_dispatch_phase6.py -q`; from root use P0's two-command host DB export without echoing it, then run `TELEMETRY_MODE=none PYTHONPATH=backend:. python3 scripts/audit_reference_probes.py --check`; `PYTHONPATH=backend:. python3 scripts/run_production_parity_eval.py --out-dir /tmp/plan2-retire-parity --check`; `./scripts/run_stage3_governance_regression.sh`; `python3 scripts/freeze_execution_baseline.py --check --in /tmp/plan2-execution-baseline.json`.
  - **Evidence:** _(exact counts, zero shadow/bridge/guided-proposer calls in both runtimes, deterministic guided behavior retained, reference/parity/governance, manifest, invariant, commit if tests change)_
  - **Invariant / manifest:** Full cumulative invariant check for B2-R.
  - **Commit boundary:** Regression/test-only commit if needed; no new feature.
  - **Stop:** Any baseline drift, authority change, or hidden consumer appears.

- [ ] **B2-W1 — RE-WIRE: add explicit default-false posture configuration**
  - **Do:** If RE-WIRE selected, implement only the B1-approved dedicated flag name and bounded settings (plan step cap, timeout, discovery posture/hop cap). Defaults are disabled/fail-closed; no piggyback on synthesis/intent flags. Status surfaces expose booleans/numbers only, no endpoint/credential. Add `backend/app/tests/test_canonical_adaptive_planning_config.py` (**NEW**).
  - **Why:** Adaptive planning must be an explicit operator choice with reviewable bounds.
  - **Surfaces:** `backend/app/config.py`; settings/status schemas and redacted status builder; env docs/profiles only if B1 authorizes; new test.
  - **Depends on:** B1=`RE-WIRE` with complete config fields.
  - **Failing-first / observation:** Tests first prove flag absent and unrelated synthesis flags cannot enable planning.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_canonical_adaptive_planning_config.py app/tests/test_settings_status.py app/tests/test_settings_status_safety.py app/tests/test_llm_settings_stage3jb.py app/tests/test_resource_plan_authority.py -q`; manifest check.
  - **Evidence:** _(approved flag/bounds, default-off and redaction tests, pytest/manifest/invariant, commit)_
  - **Invariant / manifest:** Full invariant check; B1 approval is evidence for the otherwise prohibited new flag.
  - **Commit boundary:** Config/status only; no bridge call.
  - **Stop:** B1 did not approve exact semantics; any flag defaults on or bypasses safety.

- [ ] **B2-W2 — RE-WIRE: insert one canonical bridge seam after the deterministic floor**
  - **Do:** Add one named helper at `_commit_planned_outcome` after `plan_evidence_from_canonical` builds the deterministic floor and before `planned_outcome` persists it. Both runtimes continue through the same canonical seam. Implement the exact B1 `bridge_trigger_match_paths` disposition rather than preserving `_TRIGGER_MATCH_PATHS` by accident. Fold the imperative guided-hybrid proposer into this seam: remove its direct `propose_investigation_plan_llm` call/parallel authority while preserving deterministic guided execution and validation. That fold exposes two surfaces which must be dispositioned in this same commit, not left implicit: (a) **`ai_soc_guided_llm_enabled` semantics.** Its proposer consumer is an *inverted* gate — flag true reserves the proposer with `guided_finalize_composer_reserved`, flag false calls it — so folding removes the flag's only proposer meaning while its three budget/deadline consumers (`pipeline.py:967`, `pipeline.py:1045`, `guided_llm_budget.py:12`) legitimately remain. Re-verify the consumer set by `rg`, retain the flag for budget/deadline scope only, and prove it cannot enable, disable, or otherwise gate the new canonical seam — the B2-W1 dedicated flag is the sole planning switch, and the existing "no piggyback on synthesis/intent flags" rule extends to this one. (b) **Guided dispatch-step trace compatibility.** The `dispatch_steps.append("guided_investigation_plan_llm")` emitter is gated on `llm_result.attempted`; decide whether the label is removed or re-sourced from the canonical seam's own attempt outcome, and prove the chosen posture against trace/scorecard consumers found by `rg`. With flag off, output is byte/field equivalent. Do not wire legacy `graph_node_evidence_planning` or direct MCP.
  - **Why:** There must be one live canonical insertion point, not parallel planning authorities. A retained guided flag that still appears to gate planning, or a dispatch-step label re-sourced by accident, would recreate a second de-facto planning switch.
  - **Surfaces:** `canonical_planning_orchestrator.py`; `pipeline.py`; `llm_plan_bridge.py`/promotion helper; `guided_investigation_plan_llm.py`; guided-hybrid executor/validator boundaries; `test_canonical_adaptive_planning_wiring.py` (**NEW**); dual-runtime/authority tests.
  - **Depends on:** B2-W1.
  - **Failing-first / observation:** Static seam test fails until exactly one canonical caller exists across both runtimes and no direct guided proposer remains; path-table tests fail for every B1-approved trigger that is absent and every excluded trigger that calls. Flag-off parity is captured first.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_canonical_adaptive_planning_wiring.py app/tests/test_dual_runtime_single_orchestration.py app/tests/test_canonical_planning_architecture.py app/tests/test_resource_plan_authority.py app/tests/test_canonical_handoff_e2e_probes.py app/tests/test_guided_investigation_plan_llm.py app/tests/test_guided_investigation_llm_firewall.py -q`; production parity `--check`; manifest check.
  - **Evidence:** _(single caller proof across both runtimes, exact match-path matrix including `qu_unavailable`, no direct guided/legacy caller, flag-off parity, `ai_soc_guided_llm_enabled` consumer list before/after with proof it cannot gate the seam, guided dispatch-step label disposition and its consumer proof, pytest/parity/manifest/invariant, commit)_
  - **Invariant / manifest:** Full invariant check; deterministic plan remains floor and sole fallback. Flag-group review must show exactly one planning switch — the B2-W1 dedicated flag — and no flag renamed, repurposed, or defaulted on.
  - **Commit boundary:** Insertion seam only; proposal semantics remain non-promoting until W3.
  - **Stop:** A second runtime needs a separate seam; any direct guided proposer/parallel planning authority remains; a B1-approved match path cannot reach the seam under the approved flag/posture; an excluded path does not fail closed; flag-off differs; canonical persistence order would become ambiguous; `ai_soc_guided_llm_enabled` would need renaming/repurposing/removal, or would end up co-gating the seam alongside the dedicated flag; the guided dispatch-step label has a consumer that tolerates neither removal nor re-sourcing — all three are B1 scope, not executor scope.

- [ ] **B2-W3 — RE-WIRE: validate and promote proposals without weakening the floor**
  - **Do:** Harden the proposal schema and promotion contract: registry IDs/purposes only; B1 plan cap; forbidden raw-query/SPL/credential keys recursively rejected; no execution eligibility; all deterministic floor steps/policy checks/status constraints retained; additions only where skill/resource policy permits; exact promotion provenance and dropped reasons. Implement the B1 `guided_promotion_policy` explicitly: if guided is in adaptive scope, replace the current `guided_hybrid_v1`/`guided_investigation` blanket returns with validated canonical handling; if excluded, retain both guards and test the declared deterministic-only scope. Add mutation tests for floor removal, invented resource, policy relaxation, unsafe args, direct MCP intent, oversized plans, and both guided guard shapes.
  - **Why:** An LLM proposal is data, never authority.
  - **Surfaces:** `llm_plan_bridge.py`; `plan_promotion_merge.py`; resource registry/plan models; `test_canonical_adaptive_planning_promotion.py` (**NEW**) plus existing bridge tests.
  - **Depends on:** B2-W2.
  - **Failing-first / observation:** Mutation cases fail before hardening; deterministic floor fingerprint must remain identical on every rejection.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_canonical_adaptive_planning_promotion.py app/tests/test_llm_plan_bridge.py app/tests/test_llm_plan_bridge_promotion.py app/tests/test_llm_primary_planning.py app/tests/test_compose_guided_resource_plan.py app/tests/test_guided_investigation_plan_llm.py app/tests/test_resource_plan_authority.py app/tests/test_specialist_report_contracts.py -q`; manifest check.
  - **Evidence:** _(mutation matrix, exact guided-promotion disposition for composer and skill guards, promotion/fallback fingerprints, pytest/manifest/invariant, commit)_
  - **Invariant / manifest:** Full invariant check including recursive secret/query/SPL scan.
  - **Commit boundary:** Proposal validation/promotion only; no discovery scheduling.
  - **Stop:** Any proposal can remove a floor step, authorize execution, or carry forbidden content.

- [ ] **B2-W4 — RE-WIRE: implement the approved discovery/hop/time budget semantics**
  - **Do:** Implement exactly the B1-selected discovery posture. If legacy discovery is RETIRED, keep it fenced/remove inert semantics and allow no adaptive discovery step. If CANONICALLY_REIMPLEMENTED, validate discovery steps into a deterministic scheduler; LLM never selects/calls a connector; enforce B1 hop/time/step caps; preserve execution gate; keep dispatch-v2 pre-SPL discovery separate and prevent double discovery. Reuse V2/recipe concepts only after proving they do not import fenced authority.
  - **Why:** `MAX_MCP_HOPS` cannot silently regain meaning, and two discovery mechanisms cannot double-run.
  - **Surfaces:** approved scheduler/plan contracts; `evidence_loop.py` only if selected; dispatch-v2 pipeline and tests; `test_canonical_adaptive_planning_budget.py` (**NEW**).
  - **Depends on:** B2-W3.
  - **Failing-first / observation:** Tests inject over-budget, duplicate-discovery, LLM-direct-tool, timeout, and flag-off cases before implementation.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_canonical_adaptive_planning_budget.py app/tests/test_orchestration_scheduler.py app/tests/test_recipe_registry_contract.py app/tests/test_dispatch_authority_wiring.py app/tests/test_pipeline_dispatch_phase4.py app/tests/test_pipeline_dispatch_phase5.py app/tests/test_pipeline_dispatch_phase6.py app/tests/test_mcp_execution_gate.py -q`; manifest check.
  - **Evidence:** _(selected posture, budget matrix, double-run proof, gate proof, pytest/manifest/invariant, commit)_
  - **Invariant / manifest:** Full invariant check; no LLM→MCP path and no execution-authority expansion.
  - **Commit boundary:** Discovery/budget semantics only.
  - **Stop:** B1 posture incomplete; dispatch-v2 and adaptive discovery cannot be distinguished; a connector call would occur outside the gate.

- [ ] **B2-W5 — RE-WIRE: add redacted planning trace and model-hop telemetry**
  - **Do:** Record attempt/call/outcome/latency, flag/budget skip reason, validation verdict, promotion status, deterministic fallback, plan source and bounded step IDs. Do not persist prompts, rationale text beyond existing bounded safe provenance, args, query, endpoint, credentials, RAG/raw events, or SPL. Make attempted-but-invalid distinct from not-called. Retire the ambiguous `llm_called=false/no_valid_shadow_proposal` semantics.
  - **Why:** B0 showed that architecture cost/promotion must be empirically observable.
  - **Surfaces:** canonical planning trace, `TurnLlmBudget`, telemetry redaction, control-plane trace, `test_canonical_adaptive_planning_trace.py` (**NEW**).
  - **Depends on:** B2-W4.
  - **Failing-first / observation:** Redaction tests and attempted-vs-skipped matrix first.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_canonical_adaptive_planning_trace.py app/tests/test_control_plane_trace.py app/tests/test_telemetry_connector.py app/tests/test_live_chat_telemetry_spine.py app/tests/test_turn_llm_budget_enforced.py app/tests/test_resource_plan_shadow.py -q`; manifest check.
  - **Evidence:** _(trace schema/matrix, redaction grep, pytest/manifest/invariant, commit)_
  - **Invariant / manifest:** Full invariant/redaction check.
  - **Commit boundary:** Trace/telemetry only.
  - **Stop:** Safe evidence cannot distinguish call attempt/result; any forbidden content reaches telemetry.

- [ ] **B2-W6 — RE-WIRE: prove timeout/rejection/failure fallback**
  - **Do:** Add deterministic tests for disabled, budget skip, no client, timeout, exception, invalid JSON/schema, all steps dropped, partial valid plan, persistence failure, and discovery failure. Every case must return the deterministic floor or a governed planning failure—never a partial/unvalidated plan—and must not duplicate final shadow calls.
  - **Why:** Adaptive planning is acceptable only when failure is operationally equivalent to deterministic planning.
  - **Surfaces:** canonical bridge helper; sidecar timeout; promotion; persistence; `test_canonical_adaptive_planning_fallback.py` (**NEW**).
  - **Depends on:** B2-W5.
  - **Failing-first / observation:** Parameterized failure matrix written first.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_canonical_adaptive_planning_fallback.py app/tests/test_canonical_adaptive_planning_wiring.py app/tests/test_canonical_adaptive_planning_promotion.py app/tests/test_canonical_adaptive_planning_budget.py app/tests/test_canonical_adaptive_planning_trace.py app/tests/test_canonical_handoff_persistence_failclosed.py -q`; manifest check.
  - **Evidence:** _(failure matrix, floor fingerprints, no duplicate call, pytest/manifest/invariant, commit)_
  - **Invariant / manifest:** Full invariant check.
  - **Commit boundary:** Failure/fallback only.
  - **Stop:** Any failure loses the floor, weakens policy, or makes a second model call.

- [ ] **B2-W7 — RE-WIRE: parity and regression proof**
  - **Do:** Prove flag-off exact parity and flag-on governed widening only for B1-approved paths; run a fake-client trigger matrix covering `out_of_registry`, `near_105_question`, `semantic_out_of_registry`, `query_understanding_weak`, `qu_unavailable`, and empty/unknown path, plus novel T4 probes and one explicitly approved live observation if still needed. Record plan-size/time budgets and no authority changes. B0's single `out_of_registry` call is not evidence for the other paths.
  - **Why:** RE-WIRE must prove both compatibility and bounded value before closure.
  - **Surfaces:** adaptive test family, eval/parity/governance evidence.
  - **Depends on:** B2-W6.
  - **Failing-first / observation:** No new architecture in this item; failures are fixed only within W1–W6 scope.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_canonical_adaptive_planning_config.py app/tests/test_canonical_adaptive_planning_wiring.py app/tests/test_canonical_adaptive_planning_promotion.py app/tests/test_canonical_adaptive_planning_budget.py app/tests/test_canonical_adaptive_planning_trace.py app/tests/test_canonical_adaptive_planning_fallback.py -q`; from root use P0's host DB export, then run `TELEMETRY_MODE=none PYTHONPATH=backend:. python3 scripts/audit_reference_probes.py --check`; `PYTHONPATH=backend:. python3 scripts/run_production_parity_eval.py --out-dir /tmp/plan2-rewire-parity --check`; `PYTHONPATH=backend:. python3 scripts/eval_out_of_set_intent_probe.py --check`; `./scripts/run_stage3_governance_regression.sh`; manifest check.
  - **Evidence:** _(flag-off exact tuple, approved/excluded trigger-path matrix, guided promotion posture, flag-on cases, novel probes, budgets, reference/parity/governance, manifest, invariant, commit if test-only)_
  - **Invariant / manifest:** Full cumulative invariant check for B2-W.
  - **Commit boundary:** Regression/test-only commit if needed.
  - **Stop:** Baseline refresh needed; any non-approved route changes; live probe requires new authority.

- [ ] **C0 — COE decision: LINEAGE-ONLY or EXECUTION-DRIVEN ResourcePlan order**
  - **Do:** Re-run current walk/schedule tests and build a small matrix with at least two ResourcePlans containing the same steps in opposite order. Show `step_walk_order`, actual dispatch schedule, output dependencies, and current policy/HIL timing. Present both options and fill every C0 decision field. If EXECUTION-DRIVEN, explicitly choose `activation_posture`; if `DEDICATED_DEFAULT_FALSE_FLAG`, record the exact approved `execution_order_flag_name`. Do not implement either branch. Disposition the rejected C1 branch N/A.
  - **Why:** Ordering authority is independent of the LLM/discovery posture and requires explicit intent.
  - **Surfaces:** plan evidence; `executor.py`; current step-dispatch/planner tests.
  - **Depends on:** B1 decision completed; it may be decided before B2 implementation.
  - **Failing-first / observation:** Observation/decision only. Opposite plan orders must currently yield the same predicate schedule; contradiction is drift and stops the gate.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_resource_plan_step_dispatch.py app/tests/test_planner_executor.py app/tests/test_dispatch_authority_wiring.py -q`; then `rg -n 'selected_order_semantics.*(LINEAGE-ONLY|EXECUTION-DRIVEN)|approved_by|approved_at|current_schedule_evidence|activation_posture.*(DEDICATED_DEFAULT_FALSE_FLAG|CANONICAL_DEFAULT_AFTER_PROOF)|execution_order_flag_name'` on this plan and run the plan audit.
  - **Evidence:** _(opposite-order matrix, current schedule, output dependencies, selected option, activation posture and exact flag name when applicable, approver/date, N/A disposition count)_
  - **Invariant / manifest:** No runtime change; manifest check.
  - **Commit boundary:** Optional plan-only decision commit.
  - **Stop:** No explicit choice; EXECUTION-DRIVEN activation posture is incomplete; dedicated-flag posture lacks an exact approved default-false flag name; matrix contradicts current fixed-schedule premise; choice would weaken a locked gate.

- [ ] **C1-L — LINEAGE-ONLY: make fixed scheduling an explicit, tested contract**
  - **Do:** Rename/document the schedule seam so it does not promise a future reorder; keep `step_walk_order` informational; add mutation tests proving arbitrary ResourcePlan order cannot reorder validation, execution gate, RAG, or finalization, and cannot bypass blocked steps. Update trace labels to say `lineage_order` where backward compatibility permits without breaking schema.
  - **Why:** If lineage-only is intentional, accidental future execution authority must be prevented.
  - **Surfaces:** `executor.py`; step-dispatch/trace tests; `test_resource_plan_lineage_only_contract.py` (**NEW**).
  - **Depends on:** C0=`LINEAGE-ONLY` and selected B2 closure.
  - **Failing-first / observation:** Opposite-order mutation tests first.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_resource_plan_lineage_only_contract.py app/tests/test_resource_plan_step_dispatch.py app/tests/test_planner_executor.py app/tests/test_dispatch_authority_wiring.py app/tests/test_pipeline_dispatch_phase6b.py -q`; production parity `--check`; manifest check.
  - **Evidence:** _(order mutations, fixed gate sequence, trace compatibility, pytest/parity/manifest/invariant, commit)_
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
| 2026-08-10 | Residual review of the guided-rail amendment: the proposer gate at `pipeline.py:5956` is *inverted* — `ai_soc_guided_llm_enabled` true reserves the proposer (`guided_finalize_composer_reserved`), false calls it. Verified consumer set is four non-test sites: `pipeline.py:967`, `pipeline.py:1045`, `pipeline.py:5956`, `guided_llm_budget.py:12`; the three survivors are budget/deadline only. Retiring or folding the proposer therefore strands the flag's planning meaning and the `dispatch_steps.append("guided_investigation_plan_llm")` label. Both are now dispositioned inside B2-R2 and B2-W2 (retain flag for budget scope; explicit label decision) with escalation to B1 only if rename/repurpose/removal would be required. No new checklist items; count stays 27. |
| 2026-08-10 | User review before P0 found a test-state contradiction: B2-R1 is a tests-only commit but required assertions that only pass after B2-R2's removals, so R1 could not have landed green. Resolved by splitting ownership — R1 pins the current pre-retirement state behind a named expected-state contract and commits fully green (falsifiability shown by mutation, reverted); R2 flips that contract to absent as its own first reviewable step, which must go red before the removals make it green again. R1's deterministic-guided and live-pre-SPL assertions must never go red in R2. Checked the rest of the checklist for the same pattern: R1→R2 is the only item pair that splits test authoring from implementation; A0, A1.1, A1.2, B2-R3, all B2-W and all C1-E items own both, so their failing-first steps resolve within the item. B2-R2's commit boundary also rewritten to cover what it now owns (planning-model surface retirement, not just shadow/bridge). |
| 2026-08-10 | P0 STOP: valid governance regression contradicted the accepted zero-failure baseline. `test_postgres_concurrent_resume_creates_single_next_version` failed because one concurrent resume observed `handoff_not_pending`; suite result `1 failed, 4794 passed, 2 skipped, 6 xfailed`. Manifest remained `13/13`, reference probes were `10/10`, and production parity was `120 exact / 0 approved / 0 critical`. No fix or later P0/A0 work was attempted. |
| 2026-08-10 | Source audit's Post-G1 disposition and closed corrective plan read completely. Corrective plan remains closed at `e5c1937`. |
| 2026-08-10 | Topology re-measure: `get_graph()` remains 4 edges, but `compiled.builder.edges` (20 fixed edges) and `.branches` (8 mapped conditional destinations plus dynamic delegate) provide a previously undocumented falsifiable seam. A0 uses it rather than requiring unsupported dynamic `Send` exposure. |
| 2026-08-10 | `route_setup` remains registered and unreachable; deletion is planned only after A0 failing-first reachability evidence. |
| 2026-08-10 | Decision-ref inventory widened beyond the audit's three examples: additional false outputs are visible on `work_bundle.apply`, `rag_early`, and `policy_veto`. A1 covers the full remaining inventory. |
| 2026-08-10 | Dormant `ResourcePlanV2` and pure orchestration scheduler exist, but are tied to fixture/fenced legacy concepts; C1-E may not promote them without the C0 decision and boundary tests. |
