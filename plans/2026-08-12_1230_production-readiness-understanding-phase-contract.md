---
name: production-readiness-understanding-phase-contract
overview: "Fix the runtime-map builder, resolve query understanding into a typed contract before the final route, build the Phase Contract + deterministic merge seam, then re-measure the residual routing defects instead of patching them."
status: active
date: 2026-08-12
canonical_plan: plans/2026-08-12_1230_production-readiness-understanding-phase-contract.md
source_plan: plans/2026-08-11_1834_routing-evaluation-and-authority-corrections.md
baseline_head: 2f678b9
implementation_readiness: READY
approved: 2026-08-12 (with amendments — see "Approved decisions" and Drift log)
---

# Plan 5 — Production-Readiness Architecture

## Objective

Plans 2–4 are closed at baseline `2f678b9` (PR #130, `--merge`). They left the system with a measured routing
instrument and a decided-but-unbuilt execution architecture. Plan 5 makes the architecture real, in the order the
defects actually block each other:

1. **A** — the runtime-map builder destroys promoted MITRE metadata on regeneration, so no later phase may safely
   regenerate that map. Fix first.
2. **B** — final routing consumes an understanding that itself consumed the *provisional* route. That circularity is
   why Plan 4 could not fix the D2 residue. Introduce a `ResolvedQueryContract`.
3. **C** — Plan 3 A0 decided `PHASE_POLICY_PLUS_RESOURCE_PLAN_SCHEDULING` but built none of it. There is no phase
   registry and there are three mutually inconsistent stage surfaces plus a second execution engine.
4. **D** — only *after* B and C, re-measure the residual routing defects. Do not patch them with keyword heuristics
   beforehand.

Target shape (acceptance architecture):

```
QUERY → known qualification → T1/T2/T3 sufficiently known?
   YES → trusted deterministic understanding
   NO (T4) → semantic understanding (bounded, advisory, deterministically validated)
        → RESOLVED QUERY CONTRACT (goal, ambiguity, required caps, prohibited caps, evidence reqs, provenance)
        → FINAL SKILL → RESOURCE PLAN (steps+deps+evidence) + PHASE CONTRACT (mandatory lifecycle phases)
        → DETERMINISTIC MERGE → ONE RUNNABLE SCHEDULE
        → knowledge / SPL / MCP / validation / HIL, zero..N times, ordered by dependencies
        → evidence-gap evaluation → bounded refinement → ANSWER
```

Architectural principles this plan holds to: knowledge / SPL / MCP are **not** mutually exclusive routing choices — a
ResourcePlan may contain any of them zero, one or many times · ordering comes from **dependencies**, never a fixed
Knowledge→SPL→MCP sequence · every new SPL passes deterministic validation before execution · read-only evidence calls
may repeat when justified, side-effecting or uncertain actions never auto-repeat · the LLM may understand, classify,
propose and enrich, but never executes MCP/SPL and never holds execution authority · deterministic policy, RBAC, HIL,
SPL validation and the MCP gate stay authoritative · fast deterministic T1–T3 paths are preserved and pay no LLM cost ·
ResourcePlan answers "what work/evidence/dependencies are required?", Phase Policy answers "what mandatory lifecycle
phases must surround that work?" · one deterministic compiler produces one executable schedule.

**Amendments approved 2026-08-12 (binding on Phases B and C):**

1. **The final skill is a primary route/ownership signal, not the sole ResourcePlan capability authority.** Skill
   selection decides route and ownership; it does not by itself enumerate what the ResourcePlan may contain. The
   authority for required and prohibited capabilities is the `ResolvedQueryContract` resolved against the skill
   contract — a skill contract may **deny** a capability, never silently widen or replace the resolved requirement.
   A ResourcePlan may therefore contain knowledge / SPL / MCP steps that the routed skill's contract permits, in any
   dependency-valid multiplicity, without the skill being treated as the capability enumerator.
2. **Phase C must explicitly deliver three distinct artifacts**, not one: a **PhaseRegistry** (the single closed
   catalog of lifecycle phases, unifying today's three inconsistent surfaces), a deterministic **PhasePolicy resolver**
   (decides which phases apply to *this* run, from deterministic inputs only), and a per-run **PhaseContract** (the
   resolved, immutable set of mandatory phases plus their ordering constraints for that run).
3. **Lifecycle phases are mandatory when deterministically applicable, not universally mandatory on every request.**
   A knowledge-only turn does not carry an SPL chain; a turn with no reference IDs does not carry `reference_finalize`.
   Applicability is a deterministic predicate over the `ResolvedQueryContract` and the committed ResourcePlan —
   never a heuristic, never a count.
4. **PhasePolicy — not the LLM, not the ResourcePlanner — determines applicability and non-removability.** Once
   PhasePolicy has resolved a phase into the per-run PhaseContract, neither the planner nor any advisory may add,
   remove, reorder or downgrade it. The planner proposes work; PhasePolicy proposes nothing and decides lifecycle.

**Amendment 5, added 2026-08-13 from the measured B5 evidence (binding on Phase C):**

5. **Required capabilities are satisfied by the complete governed executable schedule, not necessarily by one routed
   skill.** B5 measured what happens when the opposite reading is enforced at route level: `live_investigation`
   requires SPL+MCP, `spl_generation` grants SPL only, so the veto demoted a legitimately SPL-authoring in-catalogue
   hunt (`cisco.ot.029`) to `knowledge_recall` and destroyed its candidate SPL and HIL gate — with **zero** routing
   improvements anywhere in the truth set. The target model is:

   ```
   ResolvedQueryContract.required_capabilities
        → ResourcePlan (several capability-bearing steps) + PhaseContract
        → deterministic merge → ONE governed executable schedule
        → capability satisfaction evaluated at SCHEDULE level
   ```

   A plan whose primary skill is `spl_generation` may legitimately satisfy `{spl, mcp}` as
   `spl → validate_spl → mcp read/evidence → synthesis`. Capability compatibility therefore remains a **diagnostic
   and a constraint** — a skill-capability contradiction is real and may **deny** — but its automatic consequence
   must **not** be `veto → knowledge_recall`. No capability may be widened because an LLM proposes it, and
   deterministic policy stays the authority.

## Stop conditions

- All checklist items checked with recorded evidence, **or**
- Same verification gate fails twice on one item, **or**
- A named decision gate below is reached — **stop and ask**

## Sources and authority

- Plan 2 (`plans/2026-08-10_1103_…`, Done 27/27), Plan 3 (`plans/2026-08-11_0915_…`, Done 9/9) and Plan 4
  (`plans/2026-08-11_1834_…`, Done 19/19, merged `2f678b9`) are **historical authority**. Their locked decisions —
  B1 `RETIRE`, C0 `EXECUTION-DRIVEN`, A0 `PHASE_POLICY_PLUS_RESOURCE_PLAN_SCHEDULING`, B2 capability compatibility,
  D3 advisory finality, seam inventory 0-adopted, `UNDERSTANDING_ROUTER_ON_LOW_CONFIDENCE` retired — are inputs and
  must not be reopened without contradicting repo evidence.
- Plan 4 is closed and is **not** reopened by this plan.
- Runtime code at `2f678b9` is authoritative over every document, including this one.

---

## Four places the requested architecture conflicts with the current code

Reported rather than silently absorbed. Each is verified against the worktree, with anchors.

### 1. Phase A is **two** defects, not one — and the carried note is wrong

Measured by in-memory rebuild of `tools/coverage_authoring/question_runtime_map_builder.py` against committed
`backend/app/coverage/question_runtime_map_v1.json` (**not** `docs/evals/` — the carried path is wrong too):

- **7 fields dropped**, not "11 nulled": `mitre_registry`, `mitre_registry_schema_version`, `mitre_requires_evidence`,
  `mitre_requires_alert_context`, `mitre_visibility_policy`, `mitre_candidate`, `mitre_blocked`.
- **2 fields conflict on 61 of 105 rows**: `mitre_runtime_kb_overlap` / `mitre_runtime_kb_match_count`. Disk holds the
  promoter's DRAFT value (`q0.q004 → []`); the builder recomputes against `mitre_attack_subset.json`
  (`q0.q004 → ['T1071','T1041']`). The promotion *erased* derivable overlap data. Which is authoritative is a real
  semantic question, not a lost-field question → decision gate `A_KB_OVERLAP_AUTHORITY`.
- **2 fields already agree**: `mitre_permitted`, `mitre_permitted_sources` byte-identical on 105/105.

`CLAUDE.md:79` and `plans/2026-08-11_1834_…:779` must be corrected as part of Phase A.

**New reachability finding (highest severity in A):**
`tools/coverage_authoring/tests/test_question_operation_map_stage3l_s6_2.py:37-56` calls `write_all_question_maps()`
against the **real committed** `OUTPUT_PATH`, snapshot-and-restore in a `finally`. An interrupted test run silently
destroys the 7 MITRE fields on disk. No `tmp_path` isolation.

### 2. Phase B's premise ("routing before understanding") is inverted — the real defect is circularity

Understanding **already** precedes the final route: `adjudicate_control_plane_route` is gated on
`isinstance(state.get("intent_classification"), dict)` (`backend/app/chat/pipeline.py:2341`), and the final skill is
committed later still, at `graph_node_route_contract` (`pipeline.py:2375-2382`).

The actual defect is that the understanding is contaminated by the provisional route:

- `build_query_to_intent(routed_skill=…)` at `canonical_planning_orchestrator.py:447` and `:520`;
- `IntentClassification.primary_intent` is **overwritten with the routed skill** at `:481`;
- `qualify_reference_query` writes `routed["skill"]` from inside the intent stage (`:540-551`).

So `UNDERSTANDING_BEFORE_FINAL_ROUTE` scopes to **decontaminating the understanding input**, not reordering the graph.
Much smaller, much safer, and it is the change that actually unblocks D2.

**Do not build on `graph_node_query_to_intent` (`pipeline.py:1079`) — it is dead on the live path.** Its only importers
are `planner_led_shadow_graph.py:111` and `linear_graph_legacy.py:114`, and `linear_graph_legacy` has zero non-test
callers. The live seam is `canonical_planning_orchestrator._resolve_lane_intent_and_details:299`.

**No existing contract is a clean carrier.** `RouteContract` mixes routing authority + intent family + answer shape
(`contracts/run_contract.py:14`). `RunContract` is worse — 22 fields spanning answer shape and execution semantics
(`:47`). `CanonicalPlanningInput.RoutingContext` (`contracts/canonical_planning_input.py:41`) mixes tier + lane + skill
+ family + answer goal. The one clean starting point is `QueryUnderstandingSnapshot` (`:58`), whose only weakness is an
untyped `signals` dict.

**T4 is real code**, not user vocabulary — but it is defined **twice and inconsistently**:
`catalogue/match_tiers.py:23` vs `chat/lane_router.py:26`. They disagree on T3 (`fuzzy_alias_catalog`) and on T0
(regex-on-ids vs `qualify_reference_query`). `lane_router` is the live-path authority. A `ResolvedQueryContract` must
pick one and retire the other, never add a third → gate `B_TIER_AUTHORITY_UNIFICATION`.

### 3. Capability compatibility is **not enforced on a default live turn**

`resolve_capability_compatibility` (`chat/skill_intent_compatibility.py:119`) is fail-closed and correct, but its only
production consumer is `pipeline_dispatch_builder.py:438`, reachable solely via `graph_node_evidence_planning`
(`pipeline.py:1795`), which is (a) gated on `ai_soc_pipeline_dispatch_v2_enabled` (**default False**, `config.py:403`)
and (b) not wired into `resource_planner_graph.py` at all — `pipeline.py:644` states it is "fenced off canonical turns".

Today it is an **eval-time instrument** (`backend/app/evals/routing_truth_set.py:300`) plus a dormant dispatch-v2 path.

Therefore: carrying required/prohibited capabilities fail-closed in the `ResolvedQueryContract` **introduces**
enforcement. That is a behavioural delta with truth-set and baseline consequences. Plan 5 builds it **measured and
default-off**; activation is a separate, explicitly-approved item → gate `B_LIVE_CAPABILITY_ENFORCEMENT`.

### 4. The second execution engine is dormant at repo default but **LIVE on the COE host**

`_run_legacy_dispatch_fallback` (`pipeline.py:5746`) has exactly one call site (`:652`, session-SPL-refine, not
flag-gated), but its private `hook_nodes` loop (`:5773-5799`) only activates when `v2_hooks` is truthy — i.e. when
dispatch-v2 is on. Repo default false; **the COE host sets it true** (recorded in `CLAUDE.md`). So any change to the
dispatch builder or the fallback loop is live on COE the moment it lands. Phase C must treat COE as a production
surface, not a lab.

---

## Verified starting architecture (2026-08-12, at `2f678b9`/`2080420`)

| Surface | Observation |
|---|---|
| Live `/chat` spine | `api/routes_chat.py:39` → `:113` `run_chat_via_resource_planner_graph` (`langgraph_orchestration_enabled` default **True**, `config.py:398`). `pipeline.py:554` is rollback-only and calls the same canonical seam. |
| Single parse contract | `understand_query` runs once, `pipeline.py:998`; `route_skill` receives the result (`skill_router.py:50`), never re-parses (`skill_router.py:37`). |
| Final-route decision | `adjudicate_route` (`routing/route_adjudication.py:90`), ~15 ordered rules. |
| Final-route **commit** | `graph_node_route_contract` (`pipeline.py:2375-2382`) via `run_contract_builder.py:280-286` — the last writer of `routed["skill"]`. |
| `routed["skill"]` writers, in order | `skill_router.py:50` → `catalogue/live_router_bind.py` (`pipeline.py:1032`) → `canonical_planning_orchestrator.py:543` (T0) → `pipeline.py:2381`. |
| Plan 4 D3 gate | `routing/governance.py:398` `_advisory_may_replace_skill`; replacement only when `tool_plan == LOW_CONFIDENCE_ROUTE["tool_plan"]` (`:431`). Preserved. |
| Answer-shape leakage into routing | `answer_shape_router` gates routing at `query_understanding/parser.py:322`, `select_route_from_understanding.py:296`, `:329`. Not shape-only in practice. |
| Seam inventory | `backend/app/tests/test_execution_seam_coverage.py:35-46` — 2 SEAM / 4 DECISION_REQUIRED / 4 KEEP_SEPARATE, **0 adopted**. Its comment at `:110-111` cites stale anchors (`655`/`2273`; now `657`/`2275`). |
| Phase registry | **None.** Three inconsistent surfaces: `PipelineStage` enum (`contracts/pipeline_dispatch.py:14-21`), `_HOOK_BY_NAME` 8 entries (`planner/executor.py:290`), fallback `hook_nodes` 7 entries (`pipeline.py:5774`). `ensure_workflow_plan` executor-only; **`mitre_finalize`/`cve_adapter` owned by neither loop**. |
| Execution-driven contract (Plan 2 C0) | `planner/resource_plan_execution.py:79-87` `StepExecutionSpec`; compiler `planner/resource_plan_execution_scheduler.py:79`; handoffs `…_handoffs.py:208`; reconcile `…_outcomes.py:88`. Single wiring seam `executor.py:180`; flag read at exactly one place, `executor.py:218`. |
| Ladder precedence | dispatch-v2 projected schedule beats the execution-driven compiler (`executor.py:221-222`, reason `dispatch_v2_projected_schedule`). |
| SPL-before-MCP | `validate_spl` in `graph_node_spl_postprocessor` (`pipeline.py:2597`, state at `:2617`) precedes `graph_node_execution` (`:2922`), the only caller of `evaluate_mcp_execution`. Every schedule places `execution` last. |
| HIL / RBAC authority | `orchestration/mcp_execution_gate.py:40-52` (two independent HIL axes), `:31` `session_role_for_mcp_gate` applied `:115`. Unchanged by Plan 5. |
| Guided refinement | `chat/guided_hybrid_refinement.py:14` cap 3; fingerprint `:104`; evidence-key diff consumed `pipeline.py:5939-5969`. |
| Truth-set evaluator | `scripts/eval_routing_truth_set.py`; **deterministic arm measures `select_route_from_understanding` directly** (`:66`); `--check` is no-regression, not identity (`:245-267`); missing baseline = hard FAIL (`:337`). |
| Protected manifest | `scripts/freeze_execution_baseline.py:28-54` — **14** members. `question_runtime_map_v1.json` is **not** among them. `use_cases/catalog.json` **is**, and the MITRE promoter writes it (`promote_mitre_registry_to_runtime.py:117`). |
| Governance writes under `--check` | `run_soc_clean_answer_eval.py:125-132` and `run_langgraph_dual_parity_eval.py:105-111` write **before** the `--check` branch. Six committed reports (3 parity `9c65106`, 3 clean-answer `8792338`, both 2026-07-25) are refreshed by every governance run, plus `docs/evals/out/` and `llm_template_audit_report.md`. |

---

## Locked invariants

Routing stays deterministic — no LLM holds a routing decision · a contradiction may only **deny** a capability, never
widen one · Plan 4 D3 `_advisory_may_replace_skill` semantics preserved exactly · no retired LLM planning rail returns
(Plan 2 B1 = `RETIRE`) · no LLM → MCP path; the backend mediates all MCP access · candidate SPL is never executable;
only an approved non-null `spl_validation.normalized_spl` reaches the MCP gate · SPL validation stays before the MCP
gate; MCP gate, HIL and RBAC remain authoritative · `AI_SOC_RESOURCE_PLAN_EXECUTION_ENABLED` stays **default false**
for all of Plan 5 · EC fixture path never calls a live model and emits no traces · no eval / reference / golden /
governed-registry baseline is refreshed by verification · the 105 answer goldens are unchanged · the six stale
governance reports are **reverted, not committed**, after every governance run · no unrelated dirty file enters any
change set.

**Baseline to preserve (at `2f678b9`):** truth-set route-correct `64/76`; `capability_inconsistent` `13`; live
route-correct `59/76`; advisory capability downgrades `0`; unsafe containment `12/12`; backend `5119 passed / 0 failed`;
production parity `120 exact / 0 critical`; Cisco `50 PASS / 0 FAIL / 0 CRITICAL`; out-of-set PASS; reference probes
`10/10`; sentinel `17/17`; path honoring `105/105`; protected manifest recorded as `14/14` by Plan 4 but **measured 13** at P0 (see A4.5 — the gate reads an ephemeral `/tmp` manifest dated Aug 9 and silently skips the undeclared 14th member); cumulative invariants `7/7`.

**Correction that must not be re-lost:** `run_production_parity_eval.py` compares the two runtime spines against each
other. `120 exact` is **runtime equivalence** — not answer correctness, not routing correctness. It never reads
`question_105_golden.jsonl`.

---

## Routing-change forecast rule

Mandatory for any item touching routing or authority. Temporary-arm forecasting must run **all** of: targeted tests ·
full backend pytest · routing truth set (`--arm both`) · production parity · path honoring · sentinel · Cisco ·
reference probes · protected manifest · `./scripts/run_stage3_governance_regression.sh`. pytest alone does **not**
cover derived/governance artifacts. If an authoritative input changes, inventory every generated/derived artifact
**before** applying the change.

Every item whose Verify runs governance ends with:
`git status --porcelain docs/evals/ && git checkout -- docs/evals/` (Plan 3 precedent: reverted twice, byte-equal
except `generated_at`).

---

## Approved decisions (recorded 2026-08-12 — these gates are CLOSED)

| Gate | Item | Decision | Consequence for execution |
|---|---|---|---|
| `A_KB_OVERLAP_AUTHORITY` | A1 | **`DRAFT_AUTHORITATIVE_CLOSED`** (measured and closed 2026-08-12) | The builder adopts the promoter DRAFT values for `mitre_runtime_kb_overlap` / `_match_count`. Byte-idempotent against the committed map, zero behaviour change. **No STOP at A1** — A1 becomes a measurement item that records the 61-row diff as evidence and proceeds. The recompute-against-`mitre_attack_subset.json` option is recorded as a separately-scoped future decision, not actioned here. **Re-opens only if** A1's measurement contradicts the decision — i.e. the DRAFT value is shown to produce a *wrong* live MITRE visibility outcome. |
| `A_MAP_PROTECTION` | A5 | **APPROVED** — `question_runtime_map_v1.json` joins `PROTECTED` **after** builder correctness is proven | A5 adds the map to `scripts/freeze_execution_baseline.py` `PROTECTED`; manifest moves **14 → 15**. Every later evidence line reads 15/15. Ordering is binding: protection lands after A2–A4 pass, never before. |
| `B_TIER_AUTHORITY_UNIFICATION` | B2 | **`lane_router` live-path vocabulary** | `chat/lane_router.py:26` is the single tier authority; the duplicate literal in `catalogue/match_tiers.py:23` is retired. **No STOP at B2** unless the measurement shows retirement changes a live `live_router_bind` outcome. |
| `B_LIVE_CAPABILITY_ENFORCEMENT` | B5 | **`DEFAULT_OFF_ARCHITECTURALLY_DEFERRED`** (decided 2026-08-13 on the measured B5 evidence; supersedes the 2026-08-12 "default-OFF, activation undecided" wording) | `ai_soc_live_capability_enforcement_enabled` stays **default false** for all of Plan 5 and may not be defaulted ON in Phase B or C without a new explicit approval. Measured basis: OFF is fully green; ON produced **0** truth-set route improvements, resolved **none** of `rt.d2.003/010/017`, the `asset_identity_context`/`data_source_health` ownership rows or paraphrase under-routing, and **regressed `cisco.ot.029`** (`spl_generation`→`knowledge_recall`, candidate SPL and `requires_human_review` lost). Root cause: route-level enforcement read "the one selected skill must grant every required capability", so `live_investigation` (requires SPL+MCP) vetoed `spl_generation` (grants SPL only). That is **not** the target architecture — see the binding amendment 5 in the Objective. `cisco.ot.029` must **not** be patched with a special-case route rule. |
| `C_SEAM_ADOPTION` | C3 | **Proof required. No adoption or retirement pre-approved.** | C3 produces the equivalence proof only. `_run_legacy_dispatch_fallback` is not retired and no `DECISION_REQUIRED` seam is adopted in Plan 5. Inventory stays 2 SEAM / 4 DECISION_REQUIRED / 4 KEEP_SEPARATE, 0 adopted. |
| `D_RESIDUAL_ROUTING_OWNERSHIP` | D1 | **CLOSED 2026-08-13.** Two recorded decisions: `D1_LIVE_POSTURE_ROUTE = RATIFIED_FOR_MEASURED_ROWS`; `D1_PARAPHRASE_RESIDUE = DEFERRED_T4_SEMANTIC_SERVING_LIMIT`. | **Live-posture ratification** applies only to the 7 measured `asset_identity_context` / `data_source_health` rows that now commit `spl_generation` (`rt.d1.003/005/006/011/012/013/014`). It does **not** generalize those families to always-`spl_generation`, and no skill contract is widened. **Paraphrase residue** (`para.003/004/005/006/007/008/012/015`) is a T4 semantic-understanding serving/latency/generalization limit, out of scope for Plan 5: no keyword heuristic, no contract widening, no "clarification-by-design" relabel, no T4 timeout raise, no serving/model posture change. |
| `A2_DRAFT_VS_RUNTIME_CANDIDATE_AUTHORITY` | A2 → A2.5 | **RESOLVED for A2 by option 3 (approved 2026-08-12); the promotion question moves to A2.5.** The MITRE DRAFT is one curation commit (`7ee7a34`) ahead of the committed runtime map on **11 rows**: `q0.q021/028/040`→`T1071`, `q0.q046/047/060/062/089`→`T1110`, `q0.q050/063/083`→`T1059.001`, all `[]` in the runtime map. `56b48d9` promoted the earlier DRAFT (`1106dd3`); the promoter was never re-run after `7ee7a34`. A2's two acceptance criteria are mutually exclusive at these rows. Full analysis + 3 options: `docs/evals/plan5/a2_draft_runtime_divergence.md`. Option 3 approved: A2 reproduces the deployed promoted state and records the gap in an audited ledger; **the 11 rows are deliberately NOT promoted in A2**. |
| `MITRE_DRAFT_RUNTIME_PROMOTION_RECONCILIATION` | A2.5 | **`DEFERRED_SEPARATE_GOVERNED_PROMOTION`** (recorded 2026-08-12). DRAFT stays authoring source; runtime map stays deployed state; 11-row ledger persists; promotion requires separate MITRE governance review. | **No promotion in Plan 5.** Ledger: `docs/input/mitre_enrichment/unpromoted_draft_drift_v1.json`. Decision doc: `docs/evals/plan5/a2_5_deferred_promotion_decision.md`. |
| `STALE_REPORT_REFRESH` | — | Out of scope by instruction | The six reports stay stale and attributed to Plans 2–4 drift. Any refresh is a separately scoped decision. |

**Remaining live STOP conditions:** C3 (only on a proposal to adopt a seam or retire the fallback). A1, A5, B2, B5 and D1 no longer stop execution — B5 was answered on 2026-08-13 with `DEFAULT_OFF_ARCHITECTURALLY_DEFERRED`; D1 was answered on 2026-08-13 with `RATIFIED_FOR_MEASURED_ROWS` + `DEFERRED_T4_SEMANTIC_SERVING_LIMIT`. A *new* STOP fires only if some later item proposes defaulting the capability veto ON, adopting a seam, retiring the fallback, promoting the 11-row MITRE DRAFT, raising the T4 timeout, or widening a skill contract.

---

## Dependency order

```
P0
 → A0 → A1 → A2 → A2.5(STOP) → A3 → A4 → A4.5 → A5
 → B0 → B1 → B2 → B3 → B4 → B5(STOP only on activation) → B6
 → C0 → C0.1 → C0.2 → C1 → C2 → C3(STOP only on adoption/retirement) → C4
 → D0 → D1(CLOSED)
 → E0 → G0 → G1
```

A1, A5 and B2 carry recorded decisions and no longer stop execution.

Phase boundaries (full-gate checkpoints): after **A5**, after **B6**, after **C4**, after **D1**, at **G1**.

---

## Checklist — 28 items

### P0 — baseline freeze

- [x] **P0** — Record the pre-change baseline and prove the tree is clean
  - **Do:** Capture all baseline figures listed above by running the gate suite once, unmodified, at `2f678b9`. Record raw output paths under `docs/evals/plan5/baseline/`. Confirm the six stale governance reports are dirty-after-run and revert them.
  - **Verify:** `./scripts/run_stage3_governance_regression.sh` PASS; `cd backend && PYTHONPATH=../backend:.. python3 -m pytest -q` → `5119 passed`; `PYTHONPATH=backend:. python3 scripts/eval_routing_truth_set.py --arm both --check --baseline docs/evals/routing_truth_set_baseline_v1.json` → 0 regressions; `python3 scripts/freeze_execution_baseline.py --check` (records the **measured 13**, see A4.5 — the gate is not durable at baseline); then `git status --porcelain docs/evals/` lists exactly the 6 reports + `docs/evals/out/` + `llm_template_audit_report.md`, and `git checkout -- docs/evals/` restores.
  - **Depends on:** none
  - **Evidence:** 2026-08-12, HEAD `2080420` (descendant of `2f678b9`). Full record: `docs/evals/plan5/baseline/P0_BASELINE.md`, raw log `docs/evals/plan5/baseline/governance_p0.log`. Governance **PASS** (exit 0); backend **`5119 passed, 3 skipped, 6 xfailed`** (526.79s); truth set both arms **`route_ok=64/76, capability_inconsistent=13, unsafe_contained=12/12, live_route_ok=59/76, capability_downgrades=0`**, `--check` **0 regressions**; parity **`total=120 exact=120 approved=0 critical=0`**; Cisco **`PASS=50 REVIEW=0 FAIL=0 CRITICAL=0`**; sentinel **17/17 no drift**; path honoring **105/105**; OT probe **6/6**; dispatch matrix **5/5**. **Deviation:** protected manifest measured **13 checked**, not the recorded 14 — the gate reads an ephemeral `/tmp/exec-baseline.json` dated Aug 9 and iterates the stored manifest rather than `PROTECTED`, leaving `routing_truth_set_baseline_v1.json` declared-but-unguarded. Raised as new item **A4.5**. Governance rewrote 5 stale reports + `llm_template_audit_report.md` under `--check`; all reverted with `git checkout --`, `docs/evals/` clean afterwards. `langgraph_dual_parity_report.csv` was **not** touched — the stale set behaves as 5+1, not a uniform 6.

### Phase A — runtime-map builder correctness

- [x] **A0** — Failing-first idempotency test
  - **Do:** Add `tools/coverage_authoring/tests/test_question_runtime_map_idempotency.py`: build the map in memory (no writes), serialize `json.dumps(payload, indent=2) + "\n"`, assert byte-equality with committed `backend/app/coverage/question_runtime_map_v1.json`. Copy the `--check`/stale pattern from `scripts/build_soc_capability_crosswalk.py:785-815`.
  - **Verify:** test **FAILS** first, and its failure output names exactly the 7 dropped fields and the 61 conflicting rows.
  - **Depends on:** P0
  - **Evidence:** 2026-08-12. Added `tools/coverage_authoring/tests/test_question_runtime_map_idempotency.py` (4 tests, in-memory build only — it never writes the artifact, because writing is precisely what the defect makes dangerous). `python3 -m pytest tools/coverage_authoring/tests/test_question_runtime_map_idempotency.py -q` → **`3 failed, 1 passed`**. Failure output names the defect exactly as forecast: `fields dropped (7): ['mitre_blocked','mitre_candidate','mitre_registry','mitre_registry_schema_version','mitre_requires_alert_context','mitre_requires_evidence','mitre_visibility_policy']`, `fields added (0): none`, `field changed value on 61 row(s): mitre_runtime_kb_match_count`, `field changed value on 61 row(s): mitre_runtime_kb_overlap` (first affected refs `q0.q004`…). The 4th test (`test_row_count_and_top_level_keys_are_stable`) **passes**, confirming row count 105, top-level keys, `manifest_row_count` and row order are already stable — the defect is confined to the MITRE fields.

- [x] **A1** — `A_KB_OVERLAP_AUTHORITY` measurement (decision **already recorded** = `DRAFT_AUTHORITATIVE_CURRENT_BEHAVIOR`; no STOP unless contradicted)
  - **Do:** Produce the 61-row diff (`mitre_runtime_kb_overlap`, `mitre_runtime_kb_match_count`, draft vs recompute) as `docs/evals/plan5/kb_overlap_diff.md`. Trace whether either value reaches a live `/chat` MITRE visibility outcome via `threat/mitre_registry_enrichment.py:241-297` and `knowledge/mapping_exports.py:874,902-908`. Record the recompute option as a separately-scoped future decision. Proceed to A2 under the recorded decision.
  - **Verify:** diff file exists with all 61 rows; live-reachability answered yes/no with anchors; **STOP only if** the evidence shows the DRAFT value produces a wrong live MITRE visibility outcome — otherwise continue to A2 without asking.
  - **Depends on:** A0
  - **Evidence:** 2026-08-12. `docs/evals/plan5/kb_overlap_diff.md` + row data `docs/evals/plan5/kb_overlap_rows.json` (all 61 rows). **Direction is uniform: all 61 are rebuild-adds**, never removals; the committed DRAFT value is empty on 59 of 61. **Live reachability: YES** — `chat/mitre_branch.py:72` / `threat/mitre_decision.py:67` → `registry_mitre_metadata_for_runtime` (`mitre_registry_enrichment.py:274`) → `_synthetic_draft_item_from_runtime_row` (`:214`) → `normalize_legacy_mitre_fields:115`, which extends the analyst-visible **candidate** list from this field. **Measured live effect of the recompute: 0 of 61 rows change the normalized metadata** — `:137` filters candidates against permitted (`candidate = _dedupe([t for t in candidate if t not in set(permitted)])`) and every recomputed ID is already permitted. Decision **confirmed, not contradicted**: DRAFT is byte-idempotent, behaviour-preserving, and the conservative direction; the recompute has no measured benefit. **No STOP — proceeded to A2.**
    **Second finding, which reclassifies A2.** Running the same simulation against the *other* half of the defect (stripping the 7 promoter-owned fields, i.e. what a regeneration actually does): **11 of 105 rows change**, all in `mitre_candidate`, and all **broaden** — `q0.q021/028/040` `[]`→`['T1071']`; `q0.q046/047/060/062/089` `[]`→`['T1110']`; `q0.q050/063/083` `[]`→`['T1059.001']`. Cause: the governed runtime path is taken only when `runtime_row.get("mitre_registry")` is a dict (`:280`); dropping it collapses those rows to the draft/enrichment fallback, which does not apply the registry's suppression. So a regeneration would make the system **assert MITRE technique IDs on 11 of 105 questions that the governed registry currently suppresses** — an unsupported-claim broadening, not merely lost metadata. This raises A3 from hygiene to containment.

- [x] **A2** — Fix the builder to reproduce promoter-owned MITRE metadata
  - **Do:** In `question_runtime_map_builder.py`, import and apply `scripts/promote_mitre_registry_to_runtime.py::runtime_patch_for_draft_item` (`:46-79`) reading `docs/input/mitre_enrichment/question_105_for_mitre_enrichment.DRAFT.json`. Do **not** reimplement the patch. Do not hand-maintain the output. Preserve exact serialization (`indent=2`, no `sort_keys`, trailing newline) and key insertion order.
  - **Verify:** A0's test passes; `git diff --stat backend/app/coverage/question_runtime_map_v1.json` is **empty** after a real regeneration; `MITRE_REGISTRY_SCHEMA_VERSION` (`threat/mitre_registry_schema.py:10`) matches every row.
  - **Depends on:** A1
  - **Evidence:** 2026-08-12, closed under **option 3** (approved). Shared pure helper `backend/app/threat/mitre_runtime_promotion.py` — **extracted, not imported from the promoter**, because importing that CLI mutates `sys.path` at import time (`promote_mitre_registry_to_runtime.py:13`). Promoter now imports it; its two local definitions (**56 lines**) deleted, so no duplicated MITRE patch logic remains. Builder gained `_apply_governed_mitre_registry`, applying the patch with `row.update(...)` so key insertion order — and therefore byte identity — holds.
    **Idempotency:** regenerated vs committed sha256 both `621232b2a97b40b2944fede12e3a42723aaef1494367cb80c8ca2c3decb20c28` — **byte identical**; `git diff` on the map **empty**; all 7 governed MITRE fields survive; both DRAFT-authoritative overlap fields unchanged; zero unrelated field changes across all 105 rows.
    **Containment, before → after:** pre-fix the builder exposed exactly the forecast unsupported techniques (14 failing tests, e.g. `q0.q046: [] -> ['T1110']`); post-fix **0 rows widen** and all 105 resolve identically through the real live lookup `registry_mitre_metadata_for_runtime`. The 11 named rows are pinned individually so a regression names the specific broken suppression.
    **Drift detection:** `docs/input/mitre_enrichment/unpromoted_draft_drift_v1.json` records the 11 unpromoted rows (candidate **and** `candidate_provenance`, which `7ee7a34` also added). `tools/coverage_authoring/tests/test_question_runtime_map_draft_drift.py` asserts the ledger equals measured drift **in both directions**, forbids a ledger entry wider than the DRAFT, and requires the ledger to document its own reconciliation. Tamper-proved: removing a real drift row and adding a fake widening row → `2 failed`; restored → `5 passed`. **The 11 rows are deliberately NOT promoted here** — that is A2.5.
    **Gates:** `tools/coverage_authoring/tests` **55 passed**; operation-map audit `entries=105 drift=0`; path honoring **105/105**; MITRE/coverage consumers **84 passed**; promoter `--dry-run` unchanged (`questions 105/105, use_cases 42/65`); full backend pytest **`5119 passed, 3 skipped, 6 xfailed`** — baseline held.

- [x] **A2.5** — `MITRE_DRAFT_RUNTIME_PROMOTION_RECONCILIATION` (**DEFERRED — no promotion**)
  - **Do:** Decide whether the 11 candidate-anchor promotions `7ee7a34` added to the DRAFT should be promoted into `question_runtime_map_v1.json`. Present, per row, the technique, the promotion rationale recorded in `mitre_registry.candidate_provenance` (`llm_catalogue_audit_2026-06-16:candidate_promotion`), and the analyst-visible effect of promoting. Do **not** run the promoter as part of this item — `scripts/promote_mitre_registry_to_runtime.py` also writes `backend/app/use_cases/catalog.json`, which is a protected governed registry, so a promotion is a protected-artifact change requiring its own approval and re-capture.
  - **Verify:** decision recorded with the 11-row table; if promotion is approved, the ledger's `rows` is emptied, `test_ledger_rows_match_measured_drift_exactly` passes with zero drift, the map diff is exactly the 11 rows, and the protected manifest is re-captured deliberately; if declined, `7ee7a34` is recorded as deliberately un-promoted and the ledger persists as the audited record.
  - **Depends on:** A2
  - **Evidence:** 2026-08-12. **Decision: `DEFERRED_SEPARATE_GOVERNED_PROMOTION`.** DRAFT stays authoring source; runtime map stays deployed state; 11 rows **not** promoted. Record: `docs/evals/plan5/a2_5_deferred_promotion_decision.md`. Drift: `q0.q021/028/040`→T1071, `q0.q046/047/060/062/089`→T1110, `q0.q050/063/083`→T1059.001. Ledger + `test_question_runtime_map_draft_drift.py` remain the audit gate.

- [x] **A3** — Isolate the destructive test
  - **Do:** Change `tools/coverage_authoring/tests/test_question_operation_map_stage3l_s6_2.py:37-56` to write into `tmp_path` instead of the real `OUTPUT_PATH`; remove the snapshot/restore `finally`.
  - **Verify:** `python3 -m pytest tools/coverage_authoring/tests -q` passes; assert during the run that `git status --porcelain backend/app/coverage/` stays empty; kill-mid-test simulation leaves the committed file intact.
  - **Depends on:** A2
  - **Evidence:** 2026-08-12. `write_all_question_maps` gained optional `runtime_path` / `report_path` targets — writing the committed artifacts is now a deliberate act rather than the only thing the function can do. `test_emit_maps_writes_both_artifacts` writes to `tmp_path`, audits via `audit_operation_map(runtime_path=…, report_path=…)` (which already accepted paths), and **asserts the committed map is byte-unchanged**; the snapshot/restore `finally` is deleted. Added `test_emit_maps_cannot_touch_committed_artifacts_when_it_fails`, which monkeypatches the report writer to raise mid-run and proves the interrupted case the old restore could not survive. `python3 -m pytest tools/coverage_authoring/tests -q` → **`56 passed`**; `git status --porcelain backend/app/coverage/ docs/stage3l_s6_105_question_operation_map.json` **empty** after the full suite. Swept the repo: the only remaining bare `write_all_question_maps()` is the CLI at `coverage_drafter.py:212`, which is the intentional authoring path.

- [x] **A4** — Prove no unrelated map field moved, and no consumer broke
  - **Do:** Field-by-field diff of regenerated vs committed across all 105 rows and all top-level keys. Run every MITRE consumer identified in the audit.
  - **Verify:** diff empty; `pytest backend/app/tests/test_mitre_registry_enrichment.py backend/app/tests/test_knowledge_exports.py backend/app/tests/test_promotion_status_review.py backend/app/tests/test_row_authority_report.py backend/app/tests/test_105_path_regression_sample.py -q` passes; `python3 scripts/eval_105_path_honoring.py` → `105/105`.
  - **Depends on:** A3
  - **Evidence:** 2026-08-12. Field-by-field diff of regenerated vs committed across all 105 rows and all top-level keys: top-level keys equal; row refs **and order** equal; **rows with differing key order: 0**; **total differing (row, field) pairs: 0**; `mitre_registry_schema_version` uniform at `2026-06-control-plane-v1` on all 105. Consumers: the five named pytest modules **84 passed**; `eval_105_path_honoring.py` **PASS 105/105**; `build_row_authority_report.py --check` ok; `build_soc_capability_crosswalk.py --check` ok (105 question rows); `build_skill_coverage_matrix.py --check` ok (105 rows); `build_sentinel_set.py --check` **PASS 17/17, no drift**. The `q0.q105: missing_authoritative_mapping` WARN is **pre-existing** — it appears in the P0 baseline governance log, so it is not a consequence of this change. No `docs/evals/` drift from the `--check` runs.

- [x] **A4.5** — Make the protected manifest durable and actually guard all declared members (**found at P0**)
  - **Do:** `scripts/freeze_execution_baseline.py` compares against `--in`, default **`/tmp/exec-baseline.json`** (`:151-152`), and `check()` counts and iterates the **stored** manifest, not `PROTECTED` (`:140`). Consequence measured at P0: the live `/tmp` manifest is dated **Aug 9**, predating Plan 4 R1.5, so `docs/evals/routing_truth_set_baseline_v1.json` is *declared* protected (`:37-40`) but **absent from the stored manifest and therefore unguarded** — drift on it is invisible. `--check` reports **13 checked**, not the 14 recorded in Plan 4's closure. On a fresh host or after a reboot the file is gone and `--check` exits 2. Fix: commit the manifest to a durable repo path (e.g. `docs/evals/protected_execution_baseline.json`), default `--in`/`--out` to it, and make `check()` fail closed when a member of `PROTECTED` is missing from the stored manifest rather than silently skipping it.
  - **Verify:** `python3 scripts/freeze_execution_baseline.py --check` → **14 checked** from the committed manifest with no `/tmp` dependency; deleting `/tmp/exec-baseline.json` does not change the result; a member added to `PROTECTED` but not re-captured **fails** the check instead of being skipped (failing-first test); tampering with `routing_truth_set_baseline_v1.json` is now detected.
  - **Depends on:** A4
  - **Evidence:** 2026-08-12. Added `DEFAULT_MANIFEST_PATH = docs/evals/protected_execution_baseline.json` and defaulted both `--in`/`--out` to it; `check()` now iterates `PROTECTED` as well as the stored manifest and **fails closed** on a declared-but-unrecorded member. Manifest captured deliberately after confirming all 14 protected files were at their committed state: `captured 14 artifacts`. Results: `--check` → **`protected artifacts unchanged (14 checked)`**, exit 0; **`rm /tmp/exec-baseline.json` then `--check` still 14/14, exit 0** (no ephemeral dependency); failing-first test suite **5 failed → 9 passed** alongside the existing CLI tests. **The previously-unguarded artifact is now genuinely guarded** — appending one byte to `routing_truth_set_baseline_v1.json` produces `PROTECTED ARTIFACT DRIFT: [eval_baselines] … b0fb10e0bea2 -> 94fd0b2dfb24`, exit 1; restored → green. The count moved 13 → 14 by **guarding more**, not by adjusting a number.

- [x] **A5** — Correct the carried notes, add the map to `PROTECTED` (**approved**), Phase-A full gates
  - **Do:** Correct `CLAUDE.md:79` and the Plan 4 carry-forward: 7 fields dropped, 2 conflicting, 2 stable — not "11 nulled" — and the path is `backend/app/coverage/`, not `docs/evals/`. Then add `backend/app/coverage/question_runtime_map_v1.json` to `PROTECTED` in `scripts/freeze_execution_baseline.py:28-54` and re-capture. Ordering is binding: protection lands only after A2–A4 have proven builder correctness.
  - **Verify:** full forecast-rule gate set green; `python3 scripts/freeze_execution_baseline.py --check` → **15/15** against the durable committed manifest from A4.5 (14 declared members + the runtime map); regenerating the map after re-capture leaves the manifest check green (proves idempotency and protection agree); `git checkout -- docs/evals/` after governance.
  - **Depends on:** A4
  - **Evidence:** 2026-08-12. **Notes corrected** in `CLAUDE.md`: the builder is idempotent as of A2; the old "nulls all 11 MITRE fields" note replaced with the measured 7-dropped / 2-conflicting-on-61-rows / 2-stable breakdown; path corrected to `backend/app/coverage/`; the containment dimension, the DRAFT-vs-runtime drift ledger and the A4.5 manifest change documented. **Plan 4's file was not edited** — it is closed; its text stands as historical and is superseded by this plan.
    **Protection added.** `question_runtime_map_v1.json` joined `PROTECTED` under `governed_registries`. A4.5's fail-closed check caught it *before* re-capture — `declared protected but absent from the manifest — re-capture deliberately, do not ignore`, exit 1 — then a deliberate `--capture` → **`captured 15 artifacts`**, `--check` → **`protected artifacts unchanged (15 checked)`**. Tamper-proved: editing one `mitre_candidate` → `621232b2a97b -> 7453179852bd`, exit 1; restored → green. The manifest diff is exactly **one line**, the map's hash. Counts moved 13 → 14 → 15 by guarding more, never by adjusting a number.
    **Phase-A full gate set:** governance regression **PASS** (exit 0); backend pytest **`5124 passed, 3 skipped, 6 xfailed`** (baseline 5119 + the 5 new A4.5 durability tests); truth set `--arm both` **PASS, 0 regressions** and numerically identical to baseline (`route_ok=64/76`, `capability_inconsistent=13`, `live_route_ok=59/76`, `capability_downgrades=0`, `unsafe_contained=12/12`); parity **`total=120 exact=120 approved=0 critical=0`**; Cisco **`PASS=50 REVIEW=0 FAIL=0 CRITICAL=0`**; sentinel **17/17 no drift**; path honoring **105/105**; reference probes **9 passed**; OT probe **6/6**; SPL template audit `18 passed, 0 review_required`; protected manifest **15/15**. Governance again rewrote the 6 stale reports under `--check`; all reverted, leaving only the intended one-line manifest change.

### Phase B — understanding before final route

- [x] **B0** — Authority audit and written call-order map (no code change)
  - **Do:** Commit `docs/architecture/routing_authority_map.md`: the ordered live call graph, all four `routed["skill"]` writers, every clarification production point, the answer-shape leakage into routing (3 live sites), and the dead-node warning for `graph_node_query_to_intent`. Classify each surface: **preserve / move / adapt / retire / defer**.
  - **Verify:** every claim carries a `file:line` anchor that `grep` confirms; a reviewer can trace query→final skill without reading code.
  - **Depends on:** A5
  - **Evidence:** 2026-08-12. `docs/architecture/routing_authority_map.md` — live call order, `routed["skill"]` writers, `build_query_to_intent` contamination sites, clarification table, answer-shape leakage, tier authority (`lane_router` vs `match_tiers`), dead nodes. Anchors grep-verified.

- [x] **B1** — Define `ResolvedQueryContract` (typed, inert)
  - **Do:** New `backend/app/chat/contracts/resolved_query.py`, pydantic, modelled on `QueryUnderstandingSnapshot` (`canonical_planning_input.py:58`). Fields: `normalized_goal`, `intent_family`, `answer_goal`, `ambiguity_state`, `clarification_required` + `clarification_reason`, `required_capabilities`, `prohibited_capabilities`, `evidence_requirements`, `entities`, `time_scope`, `understanding_source` (`deterministic_qualification` | `semantic_t4`), `confidence`, `provenance`. **Do not** reuse `RouteContract.intent_family` or `RoutingContext.answer_goal` — both are populated after routing from a route-contaminated intent. Contract carries **no** execution authority and **no** skill.
  - **Verify:** unit tests for construction/validation/fail-closed defaults; `grep` proves the module imports nothing from `run_contract.py`; not yet referenced by any pipeline node.
  - **Depends on:** B0
  - **Evidence:** 2026-08-12. `backend/app/chat/contracts/resolved_query.py` + `test_resolved_query_contract.py` → **8 passed**. Fail-closed capabilities; no `run_contract` import; not wired to pipeline.

- [x] **B2** — `B_TIER_AUTHORITY_UNIFICATION` (**STOP** only if live-impacting)
  - **Do:** Measure the T3/T0 disagreement between `catalogue/match_tiers.py:23` and `chat/lane_router.py:26` across the 105 + truth-set corpora. Adopt the live-path authority (`lane_router`), retire the duplicate literal, and have `ResolvedQueryContract` carry exactly one tier vocabulary.
  - **Verify:** measured disagreement table committed; after unification `live_router_bind` outcomes are unchanged on 105/105; full backend pytest green.
  - **Depends on:** B1
  - **Evidence:** 2026-08-12. `docs/evals/plan5/tier_unification_measurement.md` — only path diff `fuzzy_alias_catalog`; **0/105** tier disagreements. `match_tiers.py` imports path sets from `lane_router`. `test_catalogue_match_tiers.py` + `test_canonical_catalogue_tier_authority.py` → **17 passed**. No live bind change.

- [x] **B3** — Decontaminate the understanding input (the real `UNDERSTANDING_BEFORE_FINAL_ROUTE`)
  - **Do:** Remove `routed_skill` from the `build_query_to_intent` inputs at `canonical_planning_orchestrator.py:447` and `:520`; stop overwriting `IntentClassification.primary_intent` with the routed skill (`:481`); move the T0 `routed["skill"]` write out of the intent stage (`:540-551`) into an explicit pre-route qualification step. Produce the `ResolvedQueryContract` here.
  - **Verify:** failing-first test asserting `build_query_to_intent` output is identical for the same query under two different provisional skills; then full backend pytest; truth set `--arm both`; parity; path honoring `105/105`.
  - **Depends on:** B2
  - **Evidence:** 2026-08-12. Removed `routed_skill` from live `build_query_to_intent` calls (`canonical_planning_orchestrator.py`, `canonical_query_to_intent_resume.py`); stopped known-lane `primary_intent` overwrite; T0 no longer mutates `routed["skill"]` — `reference_knowledge` adjudication rule + `resolved_tier==T0` deterministic_route override in `graph_node_route_resolution`. Added `resolved_query_builder.py`; `ResolvedQueryContract` emitted on canonical planning state. `test_understanding_route_invariance.py` → **4 passed**; `test_canonical_catalogue_tier_authority.py` → **8/8** (incl. CVE T4→T0). Truth set `--arm both --check` **0 regressions** (`64/76`); path honoring **105/105**; manifest **15/15**. Full governance re-run deferred to B6 phase boundary.

- [x] **B4** — Bounded T4 semantic understanding behind deterministic validation
  - **Do:** For T4 only, allow an optional bounded semantic understanding hop that fills `ResolvedQueryContract` fields, advisory, deterministically validated, behind a **default-off** flag. Hard wall-clock bound (~2s, per the q046 precedent — the VPS instruct model runs 30–120s) with no failover. T1–T3 keep the trusted deterministic qualification path untouched and pay no LLM cost.
  - **Verify:** flag-off byte-identical on 105 + truth set; flag-on cannot alter `required_capabilities` downward and cannot set a skill (asserted by test); latency bound asserted; timeout degrades to the deterministic contract.
  - **Depends on:** B3
  - **Evidence:** 2026-08-12. Flag `ai_soc_t4_semantic_understanding_enabled` default **false**, timeout **2.0s**. Module `semantic_t4_understanding.py`: T1–T3 never invoke; one LocalChatClient hop (no failover); injected-provider wall-clock bound measured (`sleep 2s` / timeout 0.15s → elapsed **<0.8s**, deterministic contract kept). Merge rejects skill keys, clarification removal, required-cap reduction, and capability widening not implied by the accepted family. `test_semantic_t4_understanding.py` → **14 passed**. Flag-OFF gates: backend pytest **5112 passed / 0 failed**; truth set `--arm both --check` **0 regressions** (`64/76`, live `59/76`); path honoring **105/105**; governance **PASS** (parity **120 exact**, Cisco **50/0/0**, sentinel **17/17**, reference **9 passed**, manifest **15/15**). Stale reports reverted. `resolved_query_contract` declared on `ChatPipelineState` so LangGraph does not drop it.

- [x] **B5** — Wire the contract into adjudication + `B_LIVE_CAPABILITY_ENFORCEMENT` (**STOP**)
  - **Do:** Make `adjudicate_route` (`route_adjudication.py:90`) consume `ResolvedQueryContract`. Reuse `resolve_capability_compatibility` (`skill_intent_compatibility.py:119`) — do **not** build a second capability table. Implement the fail-closed veto **default-off** and measure OFF/ON. An advisory may never downgrade or override a resolved deterministic capability requirement (Plan 4 D3 gate preserved verbatim).
  - **Verify:** OFF/ON truth-set delta table committed; OFF is byte-identical to baseline; full forecast-rule gate set on OFF; user approval recorded before any ON default.
  - **Depends on:** B4
  - **Evidence:** 2026-08-12. Flag `ai_soc_live_capability_enforcement_enabled` remains **default false**. `adjudicate_route` consumes `ResolvedQueryContract`; `enforce_route_capabilities` reuses `resolve_capability_compatibility` (never promotes). `test_capability_enforcement.py` → **11 passed**. Adjudication truth-set table: **0/87 route changes**, 87 compatible. ON pytest: **3 failed / 5158 passed** — real delta is **cisco.ot.029** (`spl_generation`→`knowledge_recall`) because `live_investigation` requires MCP and `spl_generation` does not grant it. D2/paraphrase/ownership rows: observation only, no rescue. OFF gates: pytest **5161 passed**; truth set `--arm both --check` **0 regressions** (`64/76`, live `59/76`); path **105/105**; governance **PASS** (parity **120 exact**, Cisco **50/0/0**, sentinel **17/17**); reference probes **10/10**; manifest **15/15**. Stale reports reverted. **STOP: recommend remain OFF.** Artifact: `docs/evals/plan5/b5_capability_enforcement_off_on.md`.

- [x] **B6** — Confirm which truth-set arm observes the change, and Phase-B full gates
  - **Do:** The deterministic arm calls `select_route_from_understanding` **directly** (`eval_routing_truth_set.py:66`), so B3–B5 changes landing in adjudication/contract layers may be **invisible** to it. Determine and document which arm observes each change; if the evaluator must be extended, measure the exact affected rows first — the frozen baseline is protected.
  - **Verify:** written arm-observability matrix; if the evaluator changes, the frozen-baseline diff is measured and **STOP** if any frozen expectation moves; full gate set green; `git checkout -- docs/evals/`.
  - **Depends on:** B5
  - **Evidence:** 2026-08-13. Matrix: `docs/evals/plan5/b6_evaluator_observability_matrix.md` — 6 layers × 14 evaluators, every layer anchored and grep-verified (`select_route_from_understanding.py:28` · `skill_router.py:50` · `resolved_query_builder.py:95` + `canonical_planning_orchestrator.py:888` · `route_adjudication.py:92` live at `pipeline.py:2347` · `graph_node_route_contract` `pipeline.py:2380` · `executor.py:180`).
    **Conclusion: nothing in the frozen truth set observes layers 3–5 by construction** — the deterministic arm stops at `select_route_from_understanding` (`eval_routing_truth_set.py:126,130`), the live arm at `route_skill` (`:72,75`), and neither calls `adjudicate_route`. `scripts/eval_b5_capability_enforcement.py` is the layer 3–5 arm. The only instrument that caught the B5 `cisco.ot.029` delta was the full-pipeline in-catalogue contract guard (`in_catalogue_contract.py:10`, entering through `routes_chat.chat`); the Cisco *eval script* did not, because `--profile deterministic` never reaches routing adjudication (`cisco_powergrid_soc_question_eval.py:14-16`). Three further findings recorded: layer 6 is thinly covered at repo default (both dispatch-v2 and execution flags false, so Phase C must bring its own probes); layer-4 coverage is **conditional** — on the `handoff_load_failed` degrade path `route_adjudication` is absent and a full-pipeline evaluator silently measures layer 2; and the truth-set evaluator still builds its *reported* (never-gated) family/shape columns from a route-contaminated `build_query_to_intent(routed_skill=…)` (`:133`), left unchanged deliberately.
    **Evaluator NOT extended, no frozen semantics touched.** The separate-arm option was taken, so B6's STOP never fired: `routing_truth_set_baseline_v1.json` (itself a `PROTECTED` member) and the in-catalogue fixture baseline are byte-unchanged. Pin: `backend/app/tests/test_evaluator_observability_matrix.py` (5 tests) asserts call reachability per layer — deterministic arm reaches select-route and **never** adjudication, live arm reaches `route_skill`, the B5 arm reaches contract **and** adjudication, the full-pipeline guard still enters via `routes_chat`, and enforcement is not left ON by the measurement arm. Also removed a duplicate `resolved_query_contract` key in a `canonical_planning_orchestrator.py` clarification-state dict literal (same value both times — no behaviour change).
    **Phase-B full gate set:** governance regression **PASS** (exit 0); backend pytest **`5166 passed, 3 skipped, 6 xfailed`** (5161 at B5 + the 5 new pins), and again `5166 passed` inside governance; truth set `--arm both --check` **PASS, 0 regressions**, numerically identical to baseline (`route_ok=64/76`, `capability_inconsistent=13`, `unsafe_contained=12/12`, live `59/76`, `capability_downgrades=0`); parity **`total=120 exact=120 approved=0 critical=0`**; Cisco **`PASS=50 REVIEW=0 FAIL=0 CRITICAL=0`**; sentinel **17/17 no drift**; path honoring **105/105**; reference probes **9 passed**; OT probe **6/6**; harness 6/6; dispatch matrix gate PASS; protected manifest **15/15**; plan-discipline audit **0 gaps**. Governance rewrote the 6 stale reports under `--check`; all reverted with `git checkout --`, `docs/evals/` clean afterwards.
    **Phase-B closure invariants:** `ai_soc_live_capability_enforcement_enabled=False` (`config.py:417`) and `ai_soc_t4_semantic_understanding_enabled=False` (`config.py:413`) both default off; `ai_soc_resource_plan_execution_enabled=False` (`:410`); T1–T3 invoke no semantic hop (pinned by `test_semantic_t4_understanding.py`); Plan 4 D3 finality untouched — `git diff 2f678b9 -- backend/app/routing/governance.py` is **empty**; no LLM→MCP/SPL authority path created — `git diff 2f678b9` over `orchestration/mcp_execution_gate.py`, `mcp/` and `safeguards/spl_validator.py` is **empty**.

**Phase B is COMPLETE** (B0–B6). Understanding is decontaminated and typed, tier vocabulary is unified, the T4 semantic hop and the capability veto both ship default-off and measured, and the observability of every routing layer is documented and pinned.

### Phase C — phase contract + canonical execution

- [x] **C0** — **PhaseRegistry**: one closed catalog of lifecycle phases
  - **Do:** New `backend/app/planner/phase_registry.py`. A closed, typed catalog of every lifecycle phase with its identity, owner, ordering constraints and hook binding: `ensure_workflow_plan`, `prepare_rag_only`, `rag_early`, `workflow_spl`, `spl_postprocessor`, `spl_source_resolve`, `reference_finalize`, `mitre_finalize`, `cve_adapter`, `execution` (terminal). Unify the **three inconsistent surfaces** — `PipelineStage` enum (`contracts/pipeline_dispatch.py:14-21`), `_HOOK_BY_NAME` 8 entries (`planner/executor.py:290`), fallback `hook_nodes` 7 entries (`pipeline.py:5774`). Explicitly assign `mitre_finalize`/`cve_adapter`, owned by **neither** loop today. Registry is a catalog only — it decides nothing about a given run.
  - **Verify:** failing-first test enumerating the three surfaces and asserting each phase resolves identically in all three after unification; a phase name outside the registry is rejected (closed-catalog test, mirroring the canonical telemetry catalog pattern); `_SPL_CHAIN` order (`pipeline_dispatch_builder.py:36-40`) is expressed as a registry ordering constraint, asserted at runtime rather than only in the stage builder.
  - **Depends on:** B6
  - **Evidence:** 2026-08-13. **Measurement first** (in-process introspection of the live objects, not by eye): `docs/evals/plan5/c0_phase_surface_disagreement.md` — three surfaces, **12 distinct phases, no two surfaces agreeing**. Findings: (a) naming collision — `mcp_execution` (stage) vs `execution` (both hook loops), hand-translated at `contracts/pipeline_dispatch.py:210-212` with nothing keeping them in step; (b) **`mitre_finalize` and `cve_adapter` are scheduled by a surface that cannot run them** — appended at `pipeline_dispatch_builder.py:333,347,365,370`, dropped by a bare `continue` at `contracts/pipeline_dispatch.py:216-217`, absent from both hook loops, yet **really executed inline inside `graph_node_context_finalize` (`pipeline.py:3545`)** — MITRE via `run_mitre_evidence_branch` (`:3634`), CVE via `_resolve_vulnerability_source_status` (`:2122`, called `:5187`) — and attributed by name in the facts spine (`canonical_facts_spine.py:207,219,237`). The work is real, claimed in provenance, and invisible to every schedule; (c) `pre_spl_mcp_discovery` is stage-only; (d) `ensure_workflow_plan` is executor-only, so a fallback turn cannot get the workflow-plan stub; (e) the compiler deliberately omits `spl_postprocessor` and `reference_finalize` (`resource_plan_execution_scheduler.py:40-41`) — precisely the Plan 3 A0 stage-drop measurement.
    **Registry:** `backend/app/planner/phase_registry.py` — closed catalog of 11 canonical phases, each with owner (`executor_hook` / `pipeline_inline` / `dispatch_v2_inline`), hook binding, stage alias, execution anchors, the **named applicability input** C0.1 must implement, `mandatory_when_applicable`, `planner_removable` (**False for every phase**), `terminal`, `after` ordering constraints and its security/execution authority. Catalog only — it decides nothing about a run, and holds no settings/state/I-O (asserted by AST, not by reading prose). `UnknownPhaseError` closes the catalog; `validate_schedule_order` turns `_SPL_CHAIN`'s hand-written list order into a runtime-checked constraint, including `spl_postprocessor → execution` and `spl_source_resolve → execution`.
    **Tests:** `backend/app/tests/test_phase_registry.py` → **15 passed**. Surfaces are introspected live (`_HOOK_BY_NAME` via AST, fallback `hook_nodes` via source, `PipelineStage` via the enum), so a drifting surface breaks here rather than in production; the measured gaps are asserted as *declared* data (`phases_without_hook_owner() == {mitre_finalize, cve_adapter, pre_spl_mcp_discovery}`) so closing or widening one is visible. **Failing-first proved by tamper:** dropping `spl_postprocessor.after` and the `spl_postprocessor → execution` constraint → `3 failed` (`test_spl_chain_order_is_expressed_as_registry_constraints`, `test_spl_validation_must_precede_the_execution_gate`, `test_valid_schedule_passes_and_reversed_schedule_raises`); restored → `15 passed`. Every schedule the live compiler emits across the 8 `_compile_hooks` input combinations satisfies the registry order. Nothing imports the registry yet — zero runtime behaviour change.

- [x] **C0.1** — **PhasePolicy resolver**: deterministic applicability
  - **Do:** New `backend/app/planner/phase_policy.py`. A pure deterministic resolver: `(ResolvedQueryContract, committed ResourcePlan) → set of applicable phases + ordering constraints`. **Lifecycle phases are mandatory when deterministically applicable, not universally mandatory** — a knowledge-only turn carries no SPL chain; a turn with no reference IDs carries no `reference_finalize`; a turn with no MITRE/CVE signal carries no finalizer. Applicability predicates read deterministic inputs only — never an LLM, never a heuristic, never a count. **PhasePolicy alone** decides applicability and non-removability; the planner proposes work and proposes no lifecycle.
  - **Verify:** failing-first table-driven test over turn archetypes (knowledge-only / SPL+MCP / reference-ID / MITRE-mapping / clarification-only) asserting the exact applicable-phase set for each; test asserting the resolver is pure (same inputs → same output, no I/O, no model call); test asserting no ResourcePlan or advisory input can change an applicability verdict.
  - **Depends on:** C0
  - **Evidence:** 2026-08-13. `backend/app/planner/phase_policy.py` — `resolve_phase_policy(ResolvedQueryContract, ResourcePlan|None, PhasePolicyInputs) → PhasePolicyResolution(applicable, mandatory, ordering, reasons)`. **Pure by construction**: every runtime fact the verdict depends on is passed in (`has_workflow_plan`, `pre_spl_discovery_enabled` — the caller's already-read dispatch-v2 flag), so the resolver imports no settings, reads no state and performs no I/O; asserted by AST, not prose. Predicates read the contract's capabilities/answer-goal/evidence requirements and the plan's live-vs-inert step purposes — never a count, never a heuristic.
    **Archetypes measured (exact sets):** knowledge-only → `{prepare_rag_only, rag_early}` with **no** SPL chain and no execution phase; SPL+MCP → `{workflow_spl, spl_postprocessor, spl_source_resolve, execution}` with ordering `workflow_spl→spl_postprocessor` and `spl_postprocessor→execution`; reference-ID → `{reference_finalize}` only; MITRE-mapping → `mitre_finalize` without `cve_adapter`; clarification-only → **empty lifecycle**, even when a plan carries SPL and MCP steps.
    **Authority direction pinned:** `test_plan_content_can_only_add_a_phase_never_remove_one` — a plan may add phases, and a plan that blocks every SPL step still cannot drop the SPL chain the contract requires; `prohibited_capabilities` (the contract's **deny**, never a widen) is the only thing that removes a phase. `pre_spl_mcp_discovery` is the single applicable-but-not-mandatory phase. `backend/app/tests/test_phase_policy.py` → **18 passed**.

- [x] **C0.2** — **PhaseContract**: the per-run resolved, immutable lifecycle
  - **Do:** New typed `PhaseContract` (per run) emitted by C0.1: the resolved mandatory phases, their ordering constraints, and their non-removability marks. Immutable once resolved. Neither the ResourcePlanner, the four advisory specialists, nor any LLM advisory may add, remove, reorder or downgrade a phase in it. Recorded in `control_plane_trace` for observability (redacted, no authority).
  - **Verify:** failing-first tests: a planner step attempting to remove a contracted phase is rejected fail-closed; a specialist `WorkBundle` merge cannot mutate the contract; reordering attempts raise rather than silently reorder; the contract is present in the trace and carries no execution authority.
  - **Depends on:** C0.1
  - **Evidence:** 2026-08-13. `backend/app/planner/phase_contract.py` — frozen `PhaseContract` (frozen `ContractedPhase` tuples) built by `build_phase_contract` / `resolve_and_freeze`. **Immutable and un-editable**: assignment raises `FrozenInstanceError` at both levels, and the type exposes **no** add/remove/reorder/downgrade API at all — the planner and the four advisory specialists have no handle to reach it (pinned by reading `planner_hierarchy.py`, the `WorkBundle` owner, and asserting it names neither `phase_contract` nor `PhaseContract`).
    **Fails closed, does not repair:** `validate_schedule` raises `PhaseContractViolation` when a schedule omits a mandatory hook-bound phase (measured: dropping `spl_postprocessor` from an SPL+MCP schedule names it in the error), when it **reorders** one (`execution` before `spl_postprocessor`), and when it contains a phase PhasePolicy found **inapplicable** — so a non-applicable phase is absent rather than emitted as a no-op. `inline_mandatory` names the hook-less phases (`mitre_finalize`, `cve_adapter`, `pre_spl_mcp_discovery`) explicitly so "absent from the schedule" can never be misread as "not owed by this run" — the exact confusion that let those two phases go unowned.
    **Trace surface** `trace_payload()` is names/ordering/reasons only, `removable=False` on every phase, carrying no execution field and no authority; live emission is deferred to C2 so that nothing new appears on a default-flag turn. `backend/app/tests/test_phase_contract.py` → **11 passed**; C0+C0.1+C0.2 together → **44 passed**.

- [x] **C1** — Deterministic merge seam (compiler)
  - **Do:** Merge `ResolvedQueryContract` + `ResourcePlan` + the per-run `PhaseContract` into **one** dependency-valid schedule. Reuse `planner/resource_plan_execution_scheduler.py:79` `compile_execution_schedule`; do not write a second compiler. Ordering comes from dependencies — knowledge / SPL / MCP may appear zero, one or many times in any dependency-valid order. The routed skill is a route/ownership signal here, **not** the capability enumerator: the plan's admissible capabilities come from the `ResolvedQueryContract` resolved against the skill contract, which may only deny. Every SPL must have a validation dependency before any execution step that consumes it. Read-only evidence steps may repeat when justified; side-effecting or uncertain steps keep `max_attempts=1` (`resource_plan_execution.py:266-268`).
  - **Verify:** failing-first probes for the interleaved shape (`knowledge_1 → mcp_1 → knowledge_2 → spl_1 → validate → mcp_2 → gap-check → spl_2 → validate → mcp_3 → synthesis`); cycle rejection; a plan omitting a phase the `PhaseContract` marked applicable is rejected, not silently accepted; a phase the `PhaseContract` marked **not** applicable is absent rather than emitted as a no-op; unsupported/invalid plans downgrade to the fixed schedule.
  - **Depends on:** C0.2
  - **Evidence:** 2026-08-13. `backend/app/planner/phase_schedule_merge.py` — `merge_schedule(ResolvedQueryContract, ResourcePlan, PhaseContract, ScheduleInputs) → (MergedSchedule | None, reason)`. **One compiler, not two**: it calls the existing `compile_execution_schedule` and then does the two things that compiler cannot — re-insert contracted lifecycle phases it is structurally unable to schedule (`SCHEDULABLE_HOOKS` excludes `spl_postprocessor` and `reference_finalize`), and evaluate capability satisfaction at schedule level. Insertion is deterministic: a missing mandatory phase goes at the earliest index satisfying every registry `after` constraint, or the whole merge downgrades (`phase_contract_unplaceable`) — never a silent repair.
    **Interleaving proved:** a 9-step plan `k1 → m1 → k2 → s1 → m2 → gap → s2 → m3 → narration` compiles to one dependency-valid schedule with `workflow_spl < spl_postprocessor < execution` and wave order `s1 < m2 < s2 < m3`. Multiplicity lives in the plan (2 SPL steps, 3 MCP steps); the hook vocabulary is not a fixed Knowledge→SPL→MCP sequence — an SPL-first plan orders SPL before knowledge.
    **Schedule-level capability satisfaction (amendment 5, the B5 lesson):** `evaluate_capability_satisfaction` is deterministic — a phase/purpose table, no model, no route veto. An `spl_generation`-primary plan of `spl → validate → mcp` reports `satisfied=True, granted={spl, mcp}, missing={}` — the exact case route-level enforcement got wrong on `cisco.ot.029`. A shortfall is **reported** (`missing={spl}`), never converted into a route change; a schedule granting a prohibited capability fails satisfaction.
    **Fails closed:** cyclic plan, absent plan, unsupported purpose, side-effecting step declaring a retry, and any contract violation all return `(None, reason)` so the caller keeps the fixed schedule; read-only steps may still declare `max_attempts=3`. `backend/app/tests/test_phase_schedule_merge.py` → **16 passed**.

- [x] **C2** — Integrate behind the existing flag; prove flag-off neutrality
  - **Do:** Wire the merge seam at the single existing seam `executor.py:180`, under `AI_SOC_RESOURCE_PLAN_EXECUTION_ENABLED` (**stays default false**). Preserve the ladder precedence: a dispatch-v2 projected schedule still wins (`executor.py:221-222`). Heed Plan 3 A0's measured warning — a compiler made authoritative without lifecycle hooks dropped a stage on 4 of 5 probes; the phase contract from C0 is exactly the missing piece and must be proven present.
  - **Verify:** flag-off runs **zero** merge-seam code (asserted by test); flag-off full gate set byte-identical to baseline; flag-on measured on a probe corpus with the 4-of-5 stage-drop probe now 5/5.
  - **Depends on:** C1
  - **Evidence:** 2026-08-13. Wired at the **single existing seam** — `executor._execution_driven_schedule_detailed`, reached only from `build_step_walk_dispatch_schedule` (`executor.py:203`) and the trace builder; `test_merge_seam_has_exactly_one_wiring_site` asserts exactly one `merge_schedule(` call site so a second execution authority cannot appear quietly. `AI_SOC_RESOURCE_PLAN_EXECUTION_ENABLED` **stays default false**.
    **Flag-off:** monkeypatching both `merge_schedule` and `resolve_phase_policy` to raise leaves a flag-off turn green — zero merge-seam code runs — and the flag-off trace carries no `execution_order` key at all, so trace bytes are unchanged. Full backend pytest at repo default: **`5235 passed, 3 skipped, 6 xfailed`** (5166 at B6 + 69 new C0–C2 tests), 0 failures.
    **Flag-on, measured:** committed probe `scripts/eval_phase_merge_probe.py` (+ `docs/evals/plan5/c2_phase_merge_probe.json`) reproduces Plan 3 A0's finding and then closes it — `compiler_only_stage_drops=4/5` (exactly the A0 classes: `spl_postprocessor` on all three SPL probes, `reference_finalize` on the MITRE probe) → **`merged_stage_drops=0/5`**. The 4-of-5 probe is now 5/5. One real defect surfaced and fixed on the way: PhasePolicy originally scoped `prepare_rag_only` to knowledge-only turns, which dropped it on the RAG+SPL hybrid — dispatch-v2 emits it whenever `rag_early` leads, so the predicate now follows the knowledge lane. **Precedence preserved:** a dispatch-v2 projected schedule still wins (`dispatch_v2_projected_schedule`), and a turn with no/invalid `ResolvedQueryContract` degrades to the byte-identical pre-C1 compiler result. Trace payload is names/ordering/reasons only, every phase `removable=false`, no execution field. `backend/app/tests/test_phase_merge_activation.py` → **9 passed**.

- [x] **C3** — Second-engine audit + `C_SEAM_ADOPTION` (**STOP**)
  - **Do:** Re-verify `_run_legacy_dispatch_fallback` reachability (`pipeline.py:5746`, sole call site `:652`; its hook loop activates only when dispatch-v2 is on — **true on the COE host**). Produce an equivalence proof between its loop and the unified registry. Update the stale anchors in `test_execution_seam_coverage.py:110-111` (`657`/`2275`). Do **not** retire the fallback in this plan without the proof and approval.
  - **Verify:** equivalence proof committed; seam-coverage pins updated and green; if no adoption, the inventory still reads 2 SEAM / 4 DECISION_REQUIRED / 4 KEEP_SEPARATE, **0 adopted**.
  - **Depends on:** C2
  - **Evidence:** 2026-08-13. **Proof only — nothing adopted, nothing retired.** `docs/evals/plan5/c3_fallback_equivalence.md`. Reachability re-verified: `_run_legacy_dispatch_fallback` (`pipeline.py:5751`) still has **exactly one** call site (`:653`, session-SPL-refine, not flag-gated); its inner v2 branch activates only when dispatch-v2 projects a schedule — repo default false, **COE host true**. Stale seam anchors corrected: `execute_plan_dispatch` call sites re-measured as `pipeline.py:658` / `:2276` (the test comment carried `655`/`2273`).
    **Verdict: not equivalent, in the direction that matters.** The legacy branch runs `workflow_spl → [rag_early] → spl_source_resolve → execution` and **never runs `spl_postprocessor`**, while the PhaseContract marks it mandatory for exactly that turn shape; it also never runs `reference_finalize` or `ensure_workflow_plan`. The gap fails **closed** today only because two other gates hold — the RP-graph `spl_validate` node (`resource_planner_graph.py:799`) and the MCP gate refusing any candidate without `approved is True` and non-null `normalized_spl` (`mcp_execution_gate.py:428-432`). The fallback is safe by virtue of other gates, not by running the lifecycle it owes.
    Three options recorded with risk (keep as-is / give the fallback the PhaseContract / retire it and route refine through `execute_plan_dispatch`). Options 2 and 3 both change production-default execution authority — and on COE they touch a live path — so **neither is taken**; the inventory stays **2 SEAM / 4 DECISION_REQUIRED / 4 KEEP_SEPARATE, 0 adopted**, pinned by `backend/app/tests/test_fallback_lifecycle_equivalence.py` → **5 passed**.

- [x] **C4** — Bounded refinement on the unified schedule + Phase-C full gates
  - **Do:** Confirm the guided round gate (`guided_hybrid_refinement.py:14,104`; evidence-key diff at `pipeline.py:5939-5969`) operates against the merged schedule: new evidence, remaining gaps, plan fingerprint, no-new-evidence detection, sufficiency, round/call budgets. Reuse `resource_plan_execution_handoffs.py:235` `refinement_decision`; add no second refinement mechanism.
  - **Verify:** identical-fingerprint stop still holds with new evidence present (`test_guided_bounded_refinement.py:124`); cap 3 enforced first; empty evidence buys no round; full forecast-rule gate set; `git checkout -- docs/evals/`.
  - **Depends on:** C3
  - **Evidence:** 2026-08-13. No second refinement mechanism: `backend/app/tests/test_phase_refinement_bound.py` drives the **existing** `refinement_decision` seam (`resource_plan_execution_handoffs.py:235`) and the existing guided cap against a plan that went through the C1 merge, and asserts `refinement_decision` is defined in exactly one planner module while none of the three new modules mentions refinement at all.
    **Bounds measured on the merged schedule:** cap is checked **first** — `rounds_used == 3` returns `round_bound_reached` even with new evidence *and* an open gap; empty evidence returns `no_new_evidence`; growth with **no** remaining gap returns `evidence_satisfied`, so new evidence alone cannot bypass sufficiency; only `new_evidence_with_open_gap` earns a round. The guided cap is 3 and `should_run_refinement_pass` stops at round 2. The side-effecting `mcp_execution` step keeps `side_effecting=True, max_attempts=1` after merge, and the merge itself refuses any plan whose side-effecting step declares a retry. Existing `test_guided_bounded_refinement.py` (identical-fingerprint stop with new evidence present) re-run unchanged: **28 passed** together.
    **Phase-C full gate set (repo default, flag OFF):** governance regression **PASS** (exit 0); backend pytest **`5247 passed, 3 skipped, 6 xfailed`** (5166 at B6 + 81 new C0–C4 tests), and `5247 passed` again inside governance; truth set `--arm both --check` **PASS, 0 regressions**, identical to baseline (`route_ok=64/76`, `capability_inconsistent=13`, live `59/76`, `capability_downgrades=0`, `unsafe_contained=12/12`); parity **`total=120 exact=120 approved=0 critical=0`**; Cisco **`PASS=50 REVIEW=0 FAIL=0 CRITICAL=0`**; sentinel **17/17 no drift** (×3 gates); path honoring **105/105**; reference probes **9 passed**; OT probe **6/6**; dispatch matrix PASS; protected manifest **15/15**; phase-merge probe `merged_stage_drops=0/5`. Governance rewrote the 6 stale reports under `--check`; all reverted, `docs/evals/` clean apart from the new Plan 5 artifacts.

### Phase D — residual routing evaluation

- [x] **D0** — Re-measure, do not patch
  - **Do:** Re-run the truth set (`--arm both`) after B+C with **no** new keyword heuristic. Produce a per-row before/after table for: `rt.d2.003/010/017`; the ~10 ambiguous rows under `asset_identity_context` / `data_source_health`; the paraphrase class (Plan 4 closed at 2/12 route-correct, accounting for 10 of the 13 `capability_inconsistent`).
  - **Verify:** table committed to `docs/evals/plan5/residual_routing_after_architecture.md`; every row classified **resolved-by-architecture / unchanged / regressed**; regressions block progress.
  - **Depends on:** C4
  - **Evidence:** 2026-08-13. **Measurement only** — no rule added, no contract widened, no baseline refreshed. Producer `scripts/eval_residual_routing_after_architecture.py`; report `docs/evals/plan5/residual_routing_after_architecture.md` (+ generated table/JSON). Measured at **five layers** because B6 proved the frozen arms see only L1/L2: L1 `select_route_from_understanding`, L2 `route_skill`, L3 `ResolvedQueryContract`, L4 `adjudicate_route`, L5 full `/chat`.
    **25 residual rows (3 D2 · 10 ownership · 12 paraphrase): L4 and L5 both = 10 resolved / 15 unchanged / 0 regressed, agreeing row-for-row; L1 reports 0 of the same 10.** Resolved: all 7 SPL-needing ownership rows, **`rt.d2.003`**, `rt.para.001`, `rt.para.010` — each now `spl_generation` with contract `spl_generation_only` / `spl_artifact` / `required={spl}`, clearing `capability_inconsistent`. Of the 15 unchanged, **7 are already route-correct** (`rt.d2.010`, `rt.d2.017`, `para.002/009/011/013/014` — `knowledge_recall` is inside their acceptable sets). **Genuine residue: 8 paraphrase rows** (`para.003/004/005/006/007/008/012/015`), all with an identical contract signature — `T4` / `out_of_registry` / `clarification_required` / `answer_goal=clarification` / `required_capabilities={}` / `evidence_requirements=[]` / `confidence=0.45` / `entities` = the 16-key slot **schema** (no extracted values) / `time_scope=None`. Zero regressions at any layer; frozen truth set still `--check` clean (`64/76`, live `59/76`).
    **B4 side probe (does the semantic hop expose better inputs?): measured NO at its current bound.** Run inside the backend container where the model endpoint resolves, flag toggled in-process only (`.env` untouched): hop **invoked 8/8, accepted 0/8** — 6 `timed_out` at the 2.0 s wall-clock bound, 2 `empty_output` with `llm_model_slot_busy`; contract byte-identical OFF vs ON on every row. The bound behaved exactly as designed (no widening, no skill, deterministic degrade), but the single-slot 8B model cannot answer in 2 s on this host. Artifact: `docs/evals/plan5/d0_t4_semantic_side_probe.json`.
    **Unratified side effect found:** the ownership class (`asset_identity_context` / `data_source_health`) is no longer routed as knowledge in production — 7 rows now commit `spl_generation` as a consequence of B3's decontamination, not of any ownership decision. Inside the labels' acceptable sets, so it scores correct, but it is a live behaviour change that D1 should ratify or object to explicitly.

- [x] **D1** — `D_RESIDUAL_ROUTING_OWNERSHIP` (**CLOSED** — user decision 2026-08-13)
  - **Do:** For rows the architecture did not resolve, state whether a deterministic discriminator now exists (Plan 4 measured none — two of the three D2 rows have an empty signal set). If ownership or product intent is genuinely undecided, **STOP with options**. Do not widen `knowledge_recall`, `alert_summary` or any skill contract to move a metric.
  - **Verify:** each unresolved row has either a proposed deterministic rule with a measured OFF/ON delta, or an explicit recorded STOP with options.
  - **Depends on:** D0
  - **Evidence:** 2026-08-13. User closed D1 with two recorded decisions; no code change, no heuristic, no contract widening. Source measurement: `docs/evals/plan5/residual_routing_after_architecture.md` + `d0_t4_semantic_side_probe.json`.
    **`D1_LIVE_POSTURE_ROUTE = RATIFIED_FOR_MEASURED_ROWS`.** The 7 measured live-query/posture rows that now commit `spl_generation` are ratified as the production outcome: `rt.d1.003/005/006/011/012/013/014`. Rationale recorded: decontaminated `ResolvedQueryContract` requires `{spl}`; L4 adjudication and L5 full `/chat` agree row-for-row; those rows clear prior `capability_inconsistent`; D0 measured 0 regressions; reversing them would need a new exception or reintroducing route-contaminated understanding. **Not generalized:** `asset_identity_context` / `data_source_health` are **not** always owned by `spl_generation`. The remaining 3 ownership-class rows (`para.009/013/014`) stay `knowledge_recall` and are already route-correct. No capability contract widening.
    **`D1_PARAPHRASE_RESIDUE = DEFERRED_T4_SEMANTIC_SERVING_LIMIT`.** Genuine unresolved residue is the 8 paraphrases `para.003/004/005/006/007/008/012/015`. D0/B4: all 8 reach T4; semantic hop invoked 8/8, accepted 0/8 (6 timeout at 2.0s, 2 `empty_output`/`llm_model_slot_busy`); OFF and ON `ResolvedQueryContract` identical; no safe deterministic discriminator; 0 regressions. Explicitly **not** done: keyword heuristic, skill-contract widening, "clarification-by-design" relabel, T4 timeout raise, serving/model posture change. Classified as a T4 semantic-understanding serving/latency/generalization limitation, **not** a routing-table defect. Future work (latency/SLO, serving capacity, alternate model/classifier) is **out of scope for Plan 5**.
    Already-correct unchanged rows need no rule: `rt.d2.010`, `rt.d2.017`, `para.002/009/011/013/014`. STOP at D1 is closed.

### E / G — report, docs, closure

- [x] **E0** — Architecture + evaluation report
  - **Do:** `docs/evals/plan5_architecture_and_routing_report.md`: what the architecture resolved, what it did not, the OFF/ON deltas, what remains default-off, and the honest statement that parity `120 exact` is runtime equivalence only.
  - **Verify:** every number traceable to a committed artifact; no claim without a gate output.
  - **Depends on:** D1
  - **Evidence:** 2026-08-13. Report committed at `docs/evals/plan5_architecture_and_routing_report.md`. Numbers traced to D0 residual report/JSON, B5 OFF/ON measurement, B6 observability matrix, C0/C2/C3 phase artifacts, A2.5 promotion deferral, `config.py:410-417` defaults. Layer tally L1 0/25/0 · L4 10/15/0 · L5 10/15/0; L4=L5 row-for-row; residue 8 paraphrases; regressions 0. Explicitly does not claim routing fully generalized. Frozen `--arm both` 64/76 and parity 120 exact are documented as non-observers of L4/L5.

- [x] **G0** — Docs alignment
  - **Do:** Update `CLAUDE.md` (Phase-A note correction, phase contract, `ResolvedQueryContract`, capability-enforcement posture, COE dispatch-v2 warning), `AGENTS.md` if operating rules moved, `plans/README.md` Active-work row, and `docs/architecture/` for the new seam.
  - **Verify:** `.cursor/hooks/audit-plan-discipline.sh plans/2026-08-12_1230_production-readiness-understanding-phase-contract.md` → zero `GAP:`; every doc claim anchored.
  - **Depends on:** E0
  - **Evidence:** 2026-08-13. Docs aligned: `CLAUDE.md` (ResolvedQueryContract flow, PhaseRegistry/PhasePolicy/PhaseContract, B5 default-OFF + `cisco.ot.029`, D1 ratification + paraphrase deferral, COE dispatch-v2, protected manifest 15/15, parity semantics, Plan 5 table row); `plans/README.md` Active-work row; `docs/architecture/routing_authority_map.md` current-flow section; new `docs/architecture/phase_contract_and_schedule.md`; E0 report. **AGENTS.md not edited** — no operating rule changed (LLM still never calls MCP; candidate SPL still never executable; D3 advisory-finality unchanged). Anchors: `config.py:410/413/417` still default false; `canonical_planning_orchestrator.py:447/:516` still omit `routed_skill`; `executor.py:286` still the single `merge_schedule(` site. Audit: `.cursor/hooks/audit-plan-discipline.sh` → **0 gaps** (26 checked / 2 unchecked G0+G1 before this check-off). Six stale governance reports intentionally unrefreshed.

- [ ] **G1** — Final closure gates
  - **Do:** Re-run the complete forecast-rule gate set twice. Re-audit every checked item's evidence. Confirm the six stale governance reports are still stale and uncommitted.
  - **Verify:** governance PASS ×2; backend pytest ≥ `5119 passed / 0 failed`; truth set `--check` 0 regressions; parity `120 exact / 0 critical`; Cisco `50/0/0`; probes `10/10`; sentinel `17/17`; path honoring `105/105`; manifest `15/15` from the durable committed manifest (14 declared + runtime map, per A4.5 and A5); invariants `7/7`; `git status` shows no `docs/evals/` report drift committed; `/invariant-check` clean.
  - **Depends on:** G0
  - **Evidence:** _(fill when done)_

---

## What Plan 5 does NOT close

- The six stale governance reports stay stale (out of scope by instruction).
- `AI_SOC_RESOURCE_PLAN_EXECUTION_ENABLED` stays **default false**. Plan 5 proves the architecture; it does not activate it.
- Live capability enforcement stays **default off** (`B_LIVE_CAPABILITY_ENFORCEMENT = DEFAULT_OFF_ARCHITECTURALLY_DEFERRED`). Defaulting it ON needs a new explicit approval.
- No `DECISION_REQUIRED` seam is adopted and `_run_legacy_dispatch_fallback` is not retired unless `C_SEAM_ADOPTION` is approved with proof.
- Paraphrase routing of the 8 residual T4 rows (`para.003/004/005/006/007/008/012/015`) remains open as `D1_PARAPHRASE_RESIDUE = DEFERRED_T4_SEMANTIC_SERVING_LIMIT`. Plan 5 forbids keyword patches, contract widening, timeout raises, and serving-posture changes. Future T4 serving/SLO/classifier work is a separate plan.
- The 7 measured live-posture rows are ratified (`D1_LIVE_POSTURE_ROUTE = RATIFIED_FOR_MEASURED_ROWS`) without generalizing `asset_identity_context` / `data_source_health` family ownership.
- The 11-row MITRE DRAFT→runtime promotion remains deferred (`DEFERRED_SEPARATE_GOVERNED_PROMOTION`).
- No live unsafe execution is enabled to prove architecture.

---

## Verification (end-to-end)

```bash
# per-item targeted
cd backend && PYTHONPATH=../backend:.. python3 -m pytest <targeted> -q

# phase boundary — full forecast-rule set
cd backend && PYTHONPATH=../backend:.. python3 -m pytest -q
PYTHONPATH=backend:. python3 scripts/eval_routing_truth_set.py --arm both --check \
  --baseline docs/evals/routing_truth_set_baseline_v1.json
PYTHONPATH=backend:. python3 scripts/eval_105_path_honoring.py
python3 scripts/freeze_execution_baseline.py --check
./scripts/run_stage3_governance_regression.sh
git status --porcelain docs/evals/ && git checkout -- docs/evals/   # MANDATORY after governance
```

Live smoke (COE, dispatch-v2 is **on** there): one `/chat` turn per lane — T1 exact-105, T3 near-105, T4
out-of-registry hunt, and one clarification-required query — asserting route, phase order, `execution_eligible=false`,
and no unexpected LLM hop.

## Verification gaps (flag before coding)

None — every item carries a concrete Verify. A1 and D1 were measurement items whose Verify is a committed measurement;
both decisions are now recorded. No remaining Plan 5 decision gate.

## Drift log

- 2026-08-12 — Plan authored. Four premise corrections recorded against the original brief (Phase A is two defects and
  the map path/field-count note is wrong; Phase B's ordering premise is inverted — the defect is circularity;
  capability compatibility is not live-enforced today; the second execution engine is live on COE). No item added or
  removed as a result; scope of B narrowed from "reorder the graph" to "decontaminate the understanding input".
- 2026-08-12 — **Approved with amendments.** All six decision gates recorded (see "Approved decisions"): A1 =
  `DRAFT_AUTHORITATIVE_CURRENT_BEHAVIOR`, A5 protection approved post-proof (manifest 14 → 15), B2 = `lane_router`
  vocabulary, B5 default-OFF only, C3 proof-only, D1 deferred to post-B+C measurement. Four architecture amendments
  added to the Objective and made binding on B and C: (1) final skill is a route/ownership signal, not the sole
  ResourcePlan capability authority; (2) Phase C delivers **PhaseRegistry + PhasePolicy resolver + per-run
  PhaseContract** as three distinct artifacts; (3) lifecycle phases are mandatory **when deterministically
  applicable**, not universally; (4) PhasePolicy — not the LLM or ResourcePlanner — owns applicability and
  non-removability. Checklist grew **23 → 25** (C0 split into C0 / C0.1 / C0.2). Status draft → active. STOPs at A1,
  A5 and B2 removed; STOPs remain at B5 (activation only), C3 (adoption/retirement only) and D1.
- 2026-08-12 — **A2 STOP raised.** A2's builder correction is implemented (shared pure helper
  `backend/app/threat/mitre_runtime_promotion.py`; promoter de-duplicated, 56 lines removed; builder applies the
  patch with `update` so key order and byte identity hold) and **restores all 7 governed MITRE fields**. It cannot
  close: 11 rows still differ in `mitre_candidate` because the DRAFT is one curation commit ahead of the committed
  runtime map. Root cause traced (`1106dd3` → `56b48d9` promoted → `7ee7a34` advanced the DRAFT, promoter never
  re-run). This also reframes the A1 containment finding — the 11 "broadening" rows are the same 11, so the
  broadening and the divergence are **one** defect, not two. New gate `A2_DRAFT_VS_RUNTIME_CANDIDATE_AUTHORITY`.
  No governed artifact modified; `question_runtime_map_v1.json` untouched.
- 2026-08-12 — **P0 finding, item added.** The protected-manifest gate is not durable and does not guard everything it
  declares: `freeze_execution_baseline.py` defaults `--in`/`--out` to **`/tmp/exec-baseline.json`** (`:151-152`) and
  `check()` iterates the **stored** manifest rather than `PROTECTED` (`:140`). The live `/tmp` manifest is dated Aug 9,
  before Plan 4 R1.5 added `routing_truth_set_baseline_v1.json`, so that file is declared protected but **unguarded**,
  and `--check` reports **13**, not the 14 recorded in Plan 4's closure. New item **A4.5** makes the manifest durable
  and fail-closed before A5 adds the runtime map. Checklist **25 → 26**.
- 2026-08-13 — **`B_LIVE_CAPABILITY_ENFORCEMENT` decided = `DEFAULT_OFF_ARCHITECTURALLY_DEFERRED`** on the measured B5
  evidence (`docs/evals/plan5/b5_capability_enforcement_off_on.md`, option 1). The flag stays default false through
  Phases B, C and D; changing that default needs a new explicit approval. `cisco.ot.029` is **not** to be patched with
  a special-case route rule. Binding **amendment 5** added to the Objective: required capabilities are satisfied at
  **schedule** level, not by a single routed skill — capability compatibility remains a diagnostic/deny constraint,
  never an automatic `veto → knowledge_recall`. This constrains C1's schedule-level satisfaction function.
- 2026-08-13 — **Checklist header corrected 27 → 28.** The count was stale: the drift log records the growth 23 → 25
  (C0 split) and 25 → 26 (A4.5), but the header was never updated past 27 while the file has always listed 28 items
  (P0 · A0 A1 A2 A2.5 A3 A4 A4.5 A5 · B0–B6 · C0 C0.1 C0.2 C1–C4 · D0 D1 · E0 G0 G1). No item was added or removed by
  this correction — only the header number moved.
- 2026-08-13 — **`D_RESIDUAL_ROUTING_OWNERSHIP` closed.** User recorded `D1_LIVE_POSTURE_ROUTE = RATIFIED_FOR_MEASURED_ROWS` (7 measured ownership rows that commit `spl_generation`; not a family-wide ownership rule) and `D1_PARAPHRASE_RESIDUE = DEFERRED_T4_SEMANTIC_SERVING_LIMIT` (8 T4 paraphrases; no heuristic, no contract widening, no timeout/serving change in Plan 5). STOP at D1 is closed. Residual routing is no longer a Plan 5 decision gate.
- 2026-08-13 — **E0/G0 docs.** Architecture+routing report at `docs/evals/plan5_architecture_and_routing_report.md`. `CLAUDE.md`, `plans/README.md`, `docs/architecture/routing_authority_map.md`, and new `docs/architecture/phase_contract_and_schedule.md` aligned to current flow. `AGENTS.md` unchanged (no operating-rule delta). Plan-discipline audit 0 gaps.
