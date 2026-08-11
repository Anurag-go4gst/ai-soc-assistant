---
name: execution-driven-adoption-and-guided-refinement
overview: "Establish the adoption path for all production-reachable execution paths, reconcile scheduling authority, and make bounded guided refinement live where its existing contract supports it."
status: draft
date: 2026-08-11
canonical_plan: plans/2026-08-11_0915_execution-driven-adoption-and-guided-refinement.md
source_plan: plans/2026-08-10_1103_architecture-resource-plan-execution-and-adaptive-planning.md
baseline_head: 9ee21fd
implementation_readiness: "READY_FOR_P0_H0_A1_B0; STOPS_AT_A0_AND_B1_DECISION_GATES"
---

# Plan 3 — Execution-driven adoption and guided refinement

## Objective

Establish the **adoption path** for all production-reachable execution paths, reconcile scheduling authority, and make bounded guided refinement live **where its existing contract supports it**.

Plan 2 built the execution-driven architecture and proved it safe; it deliberately stopped at mechanism. Done means:

- the live `query_signals` degrade defect is fixed;
- scheduling authority between dispatch-v2 and the execution-driven compiler is reconciled by explicit decision rather than by precedence accident;
- **every** production-reachable execution path is inventoried, classified `ADOPT_CANDIDATE` / `KEEP_SEPARATE` / `DECISION_REQUIRED`, and pinned by structural test — so the adoption path is established and reviewable, not assumed;
- guided refinement runs bounded on real round-varying evidence on the path whose existing `validated_resource_plan` contract already supports it;
- the flag-off/flag-on difference is measured and classified.

Explicitly **not** in this plan: redesigning the scheduler; **rewiring any bypass into the seam — A1 is inventory + structural tests only**; enabling the execution flag by default. Adoption is *charted* here and *executed* only under a recorded decision.

## Sources and authority

- Plan 2 (`plans/2026-08-10_1103_...`) is **Done, 27/27**, merged at `9ee21fd` (PR #128). Its locked decisions (B1 `RETIRE`, C0 `EXECUTION-DRIVEN`) are inputs here and must not be reopened without contradicting repo evidence.
- Runtime code at `9ee21fd` is authoritative over both documents. `baseline_head: 9ee21fd` is a runtime-content anchor.
- Plan 2's five recorded known gaps are the starting backlog; items H0/A0/A1/B0 close four of them, and the fifth (flag-on changes authority not order) is what B1 measures.

## Verified starting architecture (research, 2026-08-11)

| Surface | Observation at `9ee21fd` |
|---|---|
| H0 defect | **Live.** `pipeline.py:3622` assigns `mitre_query_signals = _query_signals_from_state(state)`, which returns `None` when `query_to_intent` is missing/non-dict; `:3643` calls `.get("alert_context_present")` on it. Recorded in Plan 2 as `:3669` — lines shifted, defect unchanged. Ten sibling call sites already guard with `or {}`; four pass the raw value on (`:3635`, `:3667`, `:3990`, `:4205`, `:6906`), and those callees accept `None` safely. |
| H0 reachability | **Corrected during H0 execution — this row's original claim was wrong.** The `.get()` is an argument expression to `run_mitre_evidence_branch`, so it evaluates before the call is entered, but `or` **does** still short-circuit within it. Measured true condition: a query with **no** alert markers **and** a missing/non-dict `query_to_intent` — a knowledge-style turn whose canonical planning did not complete. Narrower than first recorded, still live and production-reachable; both halves are now pinned by test. |
| Schedule producers | **Three, not two.** (1) dispatch-v2 `stage_schedule` — `build_pipeline_dispatch` (`pipeline_dispatch_builder.py:342`, called `pipeline.py:1500`), projected by `imperative_hook_schedule_from_state` (`contracts/pipeline_dispatch.py:182`). (2) legacy predicate schedule (`executor.py:194`) whose **first branch consumes the v2 projection** (`:199`), then applies blocked-step filtering and append rules. (3) the flag-gated compiler, which stands down with `dispatch_v2_projected_schedule`. |
| Consequence | On this host `.env` has `AI_SOC_PIPELINE_DISPATCH_V2_ENABLED=true`, so the "fixed fallback schedule" **is** the v2 schedule wherever a projection exists, and the execution-driven path is near-vacuous. |
| Vocabulary overlap | v2 maps stages to the *same* hook names the compiler emits, and additionally emits `spl_postprocessor` and `reference_finalize`, which `SCHEDULABLE_HOOKS` deliberately excludes as predicate-driven. Any unification must disposition those two. |
| Graph seam coverage | `_rp_dispatch_route` (`resource_planner_graph.py:480`) returns `non_planned_finalize` / `rag_only` / `composed_dispatch` / `workflow_spl`. **Only `composed_dispatch` reaches `execute_plan_dispatch`.** `LANGGRAPH_ORCHESTRATION_ENABLED` defaults true, so the two highest-traffic answer shapes bypass the seam on the production spine. There is **no guided-hybrid branch in the graph at all**. |
| Guided refinement | Loop at `pipeline.py:5936-5949` gates on `validated_plan.refinement_recommended`, hardcoded `False` since the proposer retired (`investigation_plan_builder.py:159`), so `refinement_cap_reached` / `should_run_refinement_pass` (`guided_hybrid_refinement.py:15,20`) can never fire. `MAX_GUIDED_INVESTIGATION_ROUNDS = 3`. |
| B0 contract source | **Exists and is clean.** Guided-hybrid already holds a real `ResourcePlan` — `validated_resource_plan` (`guided_capability_validator.py:65`), consumed at `pipeline.py:5900`. Plan 2's `build_execution_contract()` takes it directly. |
| Correction to a Plan 2 note | Plan 2's C0 evidence recorded "guided composes no ResourcePlan". That was a **test-harness artifact** — `compose_resource_plan_testutil.py:31-35` skips composition for guided under `guided_hybrid`. Production `composer.py:116-132` **does** compose guided steps. |
| Idempotency | Guided collection already carries `HookReplayEnvelope`, `plan_step_operation_identity()` and `build_safe_catalog_fingerprint()` (`guided_hybrid_collection.py`). B0 reuses them; it does not invent replay protection. |

## Locked invariants

Exactly four Resource Planner specialists (`skill`, `knowledge`, `mcp`, `spl`) · specialists advisory only · no specialist live I/O · deterministic canonical planning remains the authority · no retired LLM planning rail may return · no LLM → MCP path · candidate SPL is never executable evidence; only approved non-null `spl_validation.normalized_spl` reaches the MCP gate · MCP execution gate, HIL, RBAC and policy remain authoritative · live pre-SPL discovery stays distinct from retired legacy discovery · no automatic retry of uncertain or side-effecting work · `AI_SOC_RESOURCE_PLAN_EXECUTION_ENABLED` stays default false unless separately approved · no eval/reference/golden/registry baseline refreshed by verification · no unrelated dirty file in any change set.

## Scope

**In scope:** the H0 correctness fix; scheduling-authority inventory and decision; seam-coverage inventory, classification and structural tests; wiring the existing refinement mechanism with a plan-fingerprint stop; a bounded flag-off/flag-on evaluation; documentation and closure.

**Out of scope:** redesigning the scheduler; rewiring `rag_only` / `workflow_spl` / guided-hybrid / session-refine into the seam (A1 is inventory only, by user decision); disabling dispatch-v2; enabling the execution flag by default; any MCP/SPL/HIL/RBAC authority change; refreshing baselines.

## Decision gates

### A0 — scheduling authority

**DECIDED 2026-08-11 — `selected_authority_model: PHASE_POLICY_PLUS_RESOURCE_PLAN_SCHEDULING`.** Recorded values below; this is the "other named model" branch of the field spec, chosen over both `V2_AUTHORITATIVE_WHERE_PRESENT` and `COMPILER_CONSUMES_V2_PROJECTION` after the A0 evidence showed the two producers answer different questions.

| Decided field | Value |
|---|---|
| `selected_authority_model` | **`PHASE_POLICY_PLUS_RESOURCE_PLAN_SCHEDULING`** |
| `approved_by` | **Anurag** |
| `approved_at` | **`2026-08-11T15:01:05Z`** |
| `authority_evidence` | A0's 5-probe × 4-posture hook-diff matrix in the A0 item Evidence: `legacy_equals_v2` true in 10/10 v2-on rows; compiler downgrades `dispatch_v2_projected_schedule` in every v2-on row; `v2_only` hooks non-empty on 4/5 probes with `compiler_only` empty everywhere. |
| `predicate_hook_disposition` | **`SYSTEM_OWNED_LIFECYCLE_HOOKS`.** `spl_postprocessor` and `reference_finalize` stay system-owned. They must **not** become normal ResourcePlan steps merely to reach hook-list parity. Their presence and order come from Phase Policy / request-mode predicates, and the canonical scheduling seam must preserve them structurally. |
| `dispatch_v2_disposition` | **Not disabled.** Long-term role is request-shape / phase-policy derivation, **not** permanent independent final-schedule authority. A compatibility adapter over the existing v2 `stage_schedule` is permitted as a *migration mechanism* while the phase-contract abstraction is introduced; that adapter must never be mistaken for the target. Target is `dispatch-v2 policy logic → phase contract`, not permanently `v2 flat hook schedule → second scheduler → reconciliation`. |
| `legacy_disposition` | Compatibility/fallback infrastructure only — A0 proved it is not a genuine third authority when v2 is present. Do not expand it. |
| `flag_posture` | `AI_SOC_RESOURCE_PLAN_EXECUTION_ENABLED` remains default **`false`**. A0 does **not** authorize a production-default scheduling change; no default-on behavior without later explicit approval. |

**Target architecture.** The problem was never a choice between two rival schedulers. Dispatch-v2 and the ResourcePlan compiler answer different questions and need separate authority boundaries:

- **Phase Policy owns** which mandatory lifecycle/answer-shape phases a request requires — SPL chain integrity, `spl_postprocessor`, `reference_finalize`, MITRE/CVE finalization, and other request-mode/predicate-driven lifecycle requirements. System-owned; the planner may never add, remove or arbitrarily reorder them.
- **ResourcePlan owns** which investigation/evidence work is required — resources, dependencies, handoffs, evidence needs, bounded attempts, safe parallelism. It must not express system lifecycle hooks.

Canonical seam:

```
route / request mode → Phase Policy → Phase Contract
                                          ↘
                                           deterministic merge / compiler seam
                                          ↗            ↓
              deterministic ResourcePlan     one validated runnable schedule → executor
```

Only the deterministic merge/compiler seam produces the final executable schedule. **Invariants:** Phase Policy does not micro-order ResourcePlan work; ResourcePlan does not control mandatory lifecycle hooks.

**Implementation status — decided, not built.** No remaining Plan 3 item constructs the phase contract: A1 is inventory-only, B0 is guided refinement, B1 is measurement, G0/G1 are documentation and closure. This decision therefore fixes the *target* and the *boundaries*; building it is a separate plan, which G0 must state explicitly so the decision does not decay into aspiration.

Original requirement table, retained for reference:

| Field | Required value |
|---|---|
| `selected_authority_model` | `V2_AUTHORITATIVE_WHERE_PRESENT` · `COMPILER_CONSUMES_V2_PROJECTION` · other named model |
| `approved_by` / `approved_at` | Named approver and UTC timestamp |
| `authority_evidence` | Reference to A0's three-producer hook-diff matrix |
| `predicate_hook_disposition` | Explicit disposition of `spl_postprocessor` and `reference_finalize` — the two hooks v2 emits and the compiler excludes |
| `dispatch_v2_disposition` | Confirm dispatch-v2 is **not** disabled, and state what remains authoritative on hosts where it is enabled |

**Options, from measured A0 evidence (2026-08-11). The executor does not choose; all three are presented with the nine required fields.**

| Field | `V2_AUTHORITATIVE_WHERE_PRESENT` | `COMPILER_CONSUMES_V2_PROJECTION` | `COMPILER_AUTHORITATIVE_AFTER_HOOK_PARITY` |
|---|---|---|---|
| **Scheduling authority** | dispatch-v2 wherever it projects; legacy predicates only when v2 is off | The compiler, but it *ingests* the v2 projection as an input instead of standing down | The compiler, once it can emit the two predicate hooks |
| **Role of dispatch-v2** | Primary authority; unchanged behavior | Demoted to a **stage-source**, not a scheduler | Demoted to a projection the compiler validates against, then retired as an authority |
| **Role of legacy predicate schedule** | Pass-through when v2 on (proven 10/10); real fallback when v2 off | Same, plus the compiler's declared downgrade target | Fallback only |
| **Role of ResourcePlan compiler** | Stays dormant on dispatch-v2 hosts — effectively shelf-ware there | Becomes the single seam that *produces* the schedule from plan + projection | Sole producer |
| **Compatibility with existing gates** | Full — nothing moves; SPL-before-gate and HIL untouched | Full **if** the projection's stage order is preserved; the compiler already fixes the governed lane order in code | Full **only after** `spl_postprocessor` / `reference_finalize` are representable; until then it drops stages |
| **Migration complexity** | None | Moderate — one new input path plus parity proof per posture | High — needs a plan-step or append-rule design for the two predicate hooks, then full parity |
| **Risk of dual authority** | Low today, but the precedence stays implicit and undocumented | **Lowest** — one producer by construction, v2 becomes data | Low after migration; elevated during it |
| **Effect on `rag_only` / `workflow_spl` / other graph paths** | None — they bypass this seam entirely regardless (A1 inventories them) | None directly; adoption of those paths remains a separate A1-gated decision | None directly; same |
| **Creates default-on behavior?** | No | **Only if** the compiler is allowed to act while `AI_SOC_RESOURCE_PLAN_EXECUTION_ENABLED` is false — must stay behind the flag, so no | No, provided the flag still gates it |

**Measured constraint binding all three:** adopting the compiler as authoritative *without* first resolving `spl_postprocessor` / `reference_finalize` drops a stage on 4 of 5 probes. Any option that ends with the compiler producing the schedule must name its predicate-hook mechanism before implementation.

### B1 — default posture

If B1's evidence supports changing the flag default, record the proposal and **STOP**; the default change is not authorized by this plan.

## Dependency order

`P0 → H0 → A0 (STOP) → A1 → B0 → B1 (STOP if default change proposed) → G0 → G1`

## Loop-ready checklist

- [x] **P0 — Freeze the Plan 3 baseline**
  - **Do:** With no runtime edits, record HEAD, prove the runtime-scoped worktree is clean, re-read safe host posture without secret values, capture a fresh protected manifest, and confirm inherited gate counts still hold. Do not refresh any baseline and do not absorb existing user-owned dirt (`.claude/settings.local.json`, `.playwright-mcp/`, two G0 PNGs, `output/`).
  - **Why:** Every later result must compare against a measured `9ee21fd` baseline, not inherited prose.
  - **Surfaces:** `/tmp/plan3-execution-baseline.json`; plan Evidence only.
  - **Depends on:** none.
  - **Failing-first / observation:** Observation only. Runtime worktree dirt, protected drift, or a contradicted inherited count stops the item.
  - **Verify:** `git rev-parse HEAD`; `git status --short -- backend frontend scripts docker-compose.yml` must be empty; `python3 scripts/freeze_execution_baseline.py --capture --out /tmp/plan3-execution-baseline.json` then `--check`; export the host DB URL (`127.0.0.1:5434`, never echoed); `TELEMETRY_MODE=none PYTHONPATH=backend:. python3 scripts/audit_reference_probes.py --check`; `PYTHONPATH=backend:. python3 scripts/run_production_parity_eval.py --out-dir /tmp/plan3-p0-parity --check`.
  - **Evidence:** **COMPLETE 2026-08-11 at HEAD `728bd76`, runtime baseline `9ee21fd`.** `git diff --name-only 9ee21fd..HEAD` returned only `CLAUDE.md` and this plan file — no runtime, config, script, registry, frontend or backend path, so the runtime content is exactly the merged `9ee21fd` baseline. Runtime-scoped worktree (`backend frontend scripts docker-compose.yml .env.example`) was empty after one revert (below) and empty again at item close. Pre-existing user-owned dirt was left untouched and excluded: `.claude/settings.local.json`, `.playwright-mcp/`, two G0 PNGs, `output/`.

    **One stray artifact reverted, not a code change:** `backend/app/chat/detail_tools/__init__.py` again carried the known import-time appended newline (a `+` of one blank line to a previously empty file), produced by read-only python imports during research. Same artifact recorded twice in Plan 2's drift log; reverted with `git checkout --` before capture.

    Protected manifest captured fresh (`captured 13 artifacts -> /tmp/plan3-execution-baseline.json`) and passed before and after the item: `protected artifacts unchanged (13 checked)`.

    Host-reachable gates, `DATABASE_URL` rewritten to `127.0.0.1:5434` for the whole chain and never echoed: reference probes P1–P6/N1–N4 **`all probes match the frozen baseline` (10/10)**; production parity **`total=120 base_105=105 exact=120 approved=0 critical=0`**. Both match the inherited post-merge counts; nothing was refreshed.

    Safe host posture re-read as booleans only, no secret values: `ai_soc_resource_plan_execution_enabled=False` (the Plan 2 flag still default-off), `ai_soc_pipeline_dispatch_v2_enabled=True`, `langgraph_orchestration_enabled=True`, `ai_soc_guided_hybrid_investigation_enabled=True`, `ai_soc_guided_llm_enabled=True`, `ai_soc_llm_final_synthesis_enabled=True`, `ai_soc_llm_live_synthesis_enabled=True`, `ai_soc_llm_spl_fallback_enabled=True`, `mcp_discovery_enabled=True`, `ai_soc_planner_mitre_branch_enabled=True`, `routing_mode=llm_assisted_semantic`. **This posture confirms the A0 premise directly:** dispatch-v2 is on and the execution flag is off, so on this host the execution-driven compiler stands down wherever a v2 projection exists.

    Full backend (4978) is inherited from the merge and re-run at G1, not here. No runtime diff, so the invariant check is N/A for this item. H0 was not started.
  - **Invariant / manifest:** Manifest before and after; no runtime diff means invariant check is N/A.
  - **Commit boundary:** Evidence-only plan edit.
  - **Stop:** Runtime worktree dirt, protected drift, or any inherited count contradicted.

- [x] **H0 — Degrade safely when query signals are absent**
  - **Do:** Add a failing-first test driving the enclosing finalize path with state lacking `query_to_intent`, asserting a degraded result rather than `AttributeError`. Fix by guarding the `pipeline.py:3622` assignment with `or {}`, matching the ten sibling call sites. Run the completeness sweep `grep -n "= _query_signals_from_state("` and audit every assigned variable's uses — a direct-chaining grep is insufficient because the defect travels through an intermediate variable. Record that `run_contract_builder.py`'s duplicate helper (`:319`, sites `:62/:99/:175`) is already clean. Confirm and record that `run_mitre_evidence_branch` treats `{}` as equivalent to `None` (`mitre_branch.py:105`, `:133`), so the guard cannot alter happy-path behavior. No routing, MITRE, or authority change.
  - **Why:** A reachable `AttributeError` on the finalize path is a live correctness defect, and it must be closed before adoption work builds on that path.
  - **Surfaces:** `backend/app/chat/pipeline.py`; new/extended test under `backend/app/tests/`.
  - **Depends on:** P0.
  - **Failing-first / observation:** The new test must fail with `AttributeError` before the fix and pass after. Record both outputs.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_mitre_branch_contract.py app/tests/test_control_plane_trace.py app/tests/test_final_answer_validator.py -q` plus the new test; from root `python3 scripts/freeze_execution_baseline.py --check --in /tmp/plan3-execution-baseline.json`.
  - **Evidence:** **COMPLETE 2026-08-11; runtime commit `8a3073b`.** New `backend/app/tests/test_query_signals_degrade.py` (17 tests); one-line guard plus explanatory comment at `pipeline.py:3622`.

    **Premise correction — the plan's stated reachability was wrong and is corrected here.** The starting-architecture table claimed the enclosing `or` "does not protect" the read because it sits in an argument expression. Half right: the argument expression *is* evaluated before `run_mitre_evidence_branch` is entered, but `or` still short-circuits **within** it. Measured directly: `_mitre_alert_context_present("Summarise the brute force alert for handover") is True` → right operand never evaluated, no crash; `_mitre_alert_context_present("What is our password policy for contractor accounts?") is False` → right operand evaluated → `AttributeError: 'NoneType' object has no attribute 'get'` reproduced in isolation. **True reachability: a query with no alert markers AND a missing/non-dict `query_to_intent`** — i.e. a knowledge-style turn whose canonical planning did not complete. Narrower than recorded, still live and production-reachable. Two tests now pin both halves of the condition so it cannot silently change.

    **Failing-first, at the exact line:** `AttributeError` at `app/chat/pipeline.py:3643`. Verified twice — once with the first draft test, and again after the final test existed by stashing the fix: **5 failed, 12 passed** without the guard (exactly the five degrade cases), **17 passed** with it.

    **Completeness sweep** (`grep -n "= _query_signals_from_state("`): eight sites total. `pipeline.py:3622` was the **only** unguarded assignment; `pipeline.py:3086/3745/4268/4529` and `run_contract_builder.py:62/99/175` already used `or {}`. `run_contract_builder.py`'s duplicate helper (`:319`) is identical in shape and clean. The four keyword-argument pass-throughs (`pipeline.py:3635/3667/3990/4205/6906`) are deliberately left unguarded — every callee declares `query_signals: dict | None = None`. A test pins the sweep, excluding kwarg pass-through by construction so it cannot produce false positives.

    **Callee `{}` ≡ `None` proof, recorded before accepting the fix:** `mitre_branch.py:105` `bool((query_signals or {}).get("use_case_review_guidance"))`, `:106` same for `mitre_map`, `:133` `signals = query_signals or {}`. The guard therefore removes a crash without altering a single decision value — confirmed by a control test that finalizes unmodified production state and by a positive test that real signals still flow through.

    **Test-state honesty.** Three hand-rolled fixture attempts were discarded: finalize hard-reads nine `state[...]` keys, and a synthetic dict proved only that the fixture was wrong (it failed successively on `route_plan_shadow`, `query_understanding`, `selected_skill_chain` shape, then `confidence`). The final test builds state through the **production seam** — `run_canonical_flow()` (routing + canonical planning) followed by `graph_node_shadow_tail()`, which is the node that actually populates `selected_skill_chain` and `route_plan_shadow` and runs immediately before finalize on the live path. `_ensure_context_finalize_state` fills execution/human_review/workflow_plan inside finalize itself.

    **One case deliberately excluded from the finalize matrix:** a *string* `query_to_intent` fails `PlaceholderResponse` schema validation later in finalize (`pipeline.py:5340`). That is correct defensive behavior and a different concern from the H0 crash, so it stays in the helper-contract test and out of the degrade matrix, with the reason recorded at the parametrize.

    **Observation, not fixed (out of H0 scope):** finalize's nine direct `state[...]` reads are the same defect *class* — they raise rather than degrade when canonical planning is incomplete. H0's brief was the one known reachable defect; the rest would need their own correctness item and a decision about whether finalize should degrade or fail closed.

    **Gates.** Item slice **72 passed** (`test_query_signals_degrade.py`, `test_mitre_evidence_branch_phase5b.py`, `test_mitre_decision_runtime.py`, `test_control_plane_trace.py`, `test_final_answer_validator.py`, `test_state_channel_parity.py`) — the plan's Verify named `test_mitre_branch_contract.py`, which does not exist; the two real MITRE suites were substituted and that substitution is recorded rather than silently dropped. Manifest `protected artifacts unchanged (13 checked)`. Invariant check **7/7 PASS** — no routing, MITRE-policy, planning or execution-authority change.
  - **Invariant / manifest:** Full invariant check; prove no routing/authority change.
  - **Commit boundary:** One correctness commit; never mixed with adoption work.
  - **Stop:** The correct fix would require changing MITRE decision behavior or widening authority.

- [x] **A0 — Reconcile dispatch-v2 and execution-driven scheduling authority → DECISION, STOP**
  - **Do:** Inventory the three schedule producers named in the starting-architecture table and prove which is authoritative on each posture. Produce a same-state **hook-diff matrix** across all three, reusing the Plan 2 C1-E6 matrix harness pattern. Determine whether both encode the same stages, and disposition the known vocabulary delta (`spl_postprocessor`, `reference_finalize`). State plainly whether maintaining both constitutes dual scheduling authority. Present the authority-model options and fill every A0 decision field. Do not disable dispatch-v2, do not make the compiler authoritative without parity proof, and do not implement any unification in this item.
  - **Why:** With dispatch-v2 enabled the execution-driven path stands down almost everywhere, so "which scheduler is authoritative" is currently answered by precedence accident rather than by decision.
  - **Surfaces:** plan evidence; `executor.py`; `contracts/pipeline_dispatch.py`; `pipeline_dispatch_builder.py`; observation script under `/tmp` (not committed).
  - **Depends on:** H0.
  - **Failing-first / observation:** Observation and decision only. If the matrix contradicts the three-producer premise, that is drift and stops the gate.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_pipeline_dispatch_phase6b.py app/tests/test_dispatch_authority_wiring.py app/tests/test_resource_plan_execution_wiring.py -q`; then `rg -n 'selected_authority_model|approved_by|approved_at|predicate_hook_disposition|dispatch_v2_disposition'` on this plan; plan audit; manifest `--check`.
  - **Evidence:** **OBSERVATION COMPLETE 2026-08-11 — awaiting the user/COE authority decision.** No runtime change; manifest `protected artifacts unchanged (13 checked)`; targeted tests **35 passed** (`test_pipeline_dispatch_phase6b.py`, `test_dispatch_authority_wiring.py`, `test_resource_plan_execution_wiring.py`). Matrix produced by a non-committed `/tmp` script driving all three producers as pure functions over the same state, across four postures (`v2 off/on` × `exec-driven off/on`), five probes. No connector, LLM, or graph call.

    **Same-state hook-diff matrix** (`v2` = `imperative_hook_schedule_from_state`, `legacy` = `_legacy_predicate_dispatch_schedule`, `compiled` = `_execution_driven_schedule`):

    | Probe | Posture | v2 producer | legacy producer | compiled | authoritative |
    |---|---|---|---|---|---|
    | T0 SMB / T1 SPL / novel identity | `v2 off, exec off` | `None` | `workflow_spl, spl_source_resolve, execution` | `None` | legacy predicates |
    | " | `v2 off, exec on` | `None` | same | **same** | **compiler** |
    | " | `v2 on, exec off` | `workflow_spl, spl_postprocessor, spl_source_resolve, execution` | **identical to v2** | `None` | v2 projection via legacy |
    | " | `v2 on, exec on` | same | **identical to v2** | `None` (`dispatch_v2_projected_schedule`) | v2 projection via legacy |
    | T1 knowledge SOP | all four | `prepare_rag_only, rag_early` (v2 on) | `prepare_rag_only, rag_early` | matches when reached | as above |
    | T2 MITRE | `v2 on` | `prepare_rag_only, rag_early, reference_finalize` | **identical to v2** | `None` | v2 projection via legacy |

    **Finding 1 — the legacy predicate schedule is not an independent producer.** In **10/10** v2-on rows `legacy_equals_v2 == True`: `_legacy_predicate_dispatch_schedule` returns the v2 projection unchanged (its first branch at `executor.py:199` consumes it, and the blocked-filter/append rules did not alter it on any probe). So there are three *code paths* but only **two authorities**: dispatch-v2 and the execution-driven compiler, with legacy acting as pass-through when v2 is present and as the genuine fallback only when v2 is off.

    **Finding 2 — this is not dual authority today, but it is dual authority waiting to happen.** Exactly one schedule is authoritative per posture, under a deterministic precedence: **v2 > compiler > legacy predicates**. Nothing arbitrates that precedence explicitly; it emerges from the order of guards in `_execution_driven_schedule` and `_legacy_predicate_dispatch_schedule`. Two independent producers plus an unstated precedence is the structural risk A1's tests are meant to pin.

    **Finding 3 — the vocabulary delta is material, not cosmetic.** `SCHEDULABLE_HOOKS` = `{ensure_workflow_plan, execution, prepare_rag_only, rag_early, spl_source_resolve, workflow_spl}`. v2 additionally emits `spl_postprocessor` on every SPL probe (T0 SMB, T1 SPL, novel identity) and `reference_finalize` on the MITRE probe. Measured `v2_only` minus `compiler_only` per probe: `['spl_postprocessor']`, `['spl_postprocessor']`, `[]`, `['reference_finalize']`, `['spl_postprocessor']` — and `compiler_only` is empty everywhere. **Consequence: making the compiler authoritative *today* would silently drop a stage on 4 of 5 probes.** That is a regression, not a migration, and it is why the predicate-hook disposition below is a precondition of any unification rather than a footnote.

    **Decision-evidence fields, filled except the model itself:**

    | Field | Value |
    |---|---|
    | `authority_evidence` | The matrix above: 5 probes × 4 postures; `legacy_equals_v2` true in 10/10 v2-on rows; compiler downgrades with `dispatch_v2_projected_schedule` in every v2-on row; `v2_only` hooks non-empty on 4/5 probes. |
    | `predicate_hook_disposition` | **Unresolved by design — this is the decision's precondition.** `spl_postprocessor` and `reference_finalize` are stage-predicate-driven, not plan-step-driven, so the compiler cannot emit them from a `ResourcePlan` without either (a) new plan steps whose purposes map to them, or (b) an explicit post-compile append rule mirroring today's predicates. Neither may be adopted silently; whichever the decision picks must be named in the record. |
    | `dispatch_v2_disposition` | Dispatch-v2 is **not** disabled under any option. On hosts where it is enabled (including COE) it currently determines every composed-turn schedule, and the execution-driven compiler never activates there. |
    | `selected_authority_model` | **BLANK — user/COE decision.** |
    | `approved_by` / `approved_at` | **BLANK — user/COE decision.** |

    **Options, each with the nine required fields, are recorded in the A0 decision block above.**

    **DECISION RECORDED 2026-08-11T15:01:05Z (Anurag): `PHASE_POLICY_PLUS_RESOURCE_PLAN_SCHEDULING`** — the fourth, "other named model" branch. It accepts neither producer as authoritative in its current form: dispatch-v2's stage logic becomes Phase Policy (system-owned lifecycle), the ResourcePlan compiler keeps evidence-work scheduling, and a deterministic merge seam is the single producer of the runnable schedule. `predicate_hook_disposition: SYSTEM_OWNED_LIFECYCLE_HOOKS` closes the measured stage-drop risk by construction — the two hooks never become plan steps, so the compiler can never omit them. Flag stays default false; no default-on behavior authorized. Full decision block above.
  - **Invariant / manifest:** No runtime change; manifest check.
  - **Commit boundary:** Optional plan-only decision commit.
  - **Stop:** **Always stops for the decision.** Also stops if the matrix contradicts the premise or an option would weaken a locked gate.

- [x] **A1 — Inventory and pin canonical seam coverage (no rewiring)**
  - **Do:** Inventory **every production-reachable** path that bypasses `execute_plan_dispatch`, from current-code inspection, and re-verify each candidate below plus anything further found: `composed_dispatch` (the control case that *does* reach the seam), `rag_only` (`_rp_dispatch_route:487`), `workflow_spl` (`:491`), `non_planned_finalize` (`:485`), guided-hybrid (`pipeline.py:652`), session SPL refinement (`pipeline.py:646` → `_run_legacy_dispatch_fallback:5740`), v2 cursor trace synthesis (`pipeline.py:5118` → `build_plan_dispatch_trace_from_pipeline_dispatch`, which synthesizes a `plan_dispatch` trace exactly when LangGraph v2 cursor routing skips executor dispatch), and the EC demo fixture (`demo/ec_pipeline_fixture.py:12`). For each record: runtime reachability · why it bypasses · current scheduling/execution authority · whether it is safe to adopt · whether it holds a legitimate separate safety/authority boundary · what would change if adopted. Classify each as `ADOPT_CANDIDATE` / `KEEP_SEPARATE` / `DECISION_REQUIRED`. Add structural tests pinning the current topology, which paths do and do not reach the seam, and explicitly guarding against accidental creation of multiple scheduling authorities. **Do not rewire any path in this item** (user decision, 2026-08-11).
  - **Why:** The seam can only become canonical if what currently bypasses it is known, classified and pinned; the graph-spine bypasses materially expand the originally assumed scope and must not stay hidden.
  - **Surfaces:** `backend/app/graph/resource_planner_graph.py` and `backend/app/chat/pipeline.py` as read anchors; `backend/app/tests/test_execution_seam_coverage.py` (**NEW**).
  - **Depends on:** A0 decision recorded.
  - **Failing-first / observation:** Structural tests must fail when a fabricated extra scheduling authority or an unlisted bypass is injected; record those mutation results.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_execution_seam_coverage.py app/tests/test_dual_runtime_single_orchestration.py app/tests/test_dispatch_authority_wiring.py app/tests/test_resource_planner_topology_contract.py -q`; manifest `--check`.
  - **Evidence:** **COMPLETE 2026-08-11; runtime commit `97b43dd`.** Inventory + structural tests only; **nothing rewired**. New `backend/app/tests/test_execution_seam_coverage.py` (14 tests).

    **Bypass inventory — ten production-reachable paths, verified against current code:**

    | Path | Reachability | Current authority | Why it bypasses / reaches | Should adopt? | Legitimate separate boundary? | If adopted | Class |
    |---|---|---|---|---|---|---|---|
    | `graph:composed_dispatch` | graph spine (default), composed plan present | executor seam | **Reaches** — `rp_node_composed_dispatch` → `graph_node_composed_dispatch` → `execute_plan_dispatch` | n/a | n/a | n/a | **SEAM** |
    | `imperative:composed_plan` | imperative rollback, composed plan present | executor seam | **Reaches** — `pipeline.py:655` | n/a | n/a | n/a | **SEAM** |
    | `graph:rag_only` | graph spine, `answer_mode == "rag_only"` | v2/legacy stage nodes | Routed before the composed check, so a knowledge answer is never widened into an investigation | Eventually yes — it is ordinary governed evidence work | No — the ordering is lifecycle, not safety | Phase Policy would own the RAG terminal; plan work would order within it | **DECISION_REQUIRED** |
    | `graph:workflow_spl` | graph spine, planned turn without composed plan | v2/legacy stage nodes | Fallback lane when no ResourcePlan was composed | Yes, once a plan always exists on this lane | No | Same skeleton, plan-ordered work | **DECISION_REQUIRED** |
    | `graph:non_planned_finalize` | graph spine, outcome not `planned` | canonical failure/non-planned builder | There is no plan to schedule | **No** | **Yes** — failure/clarification lane must not depend on a scheduler | — | **KEEP_SEPARATE** |
    | `imperative:guided_hybrid` | imperative, `_uses_guided_hybrid_dispatch` | `_run_guided_hybrid_dispatch` + its own collection loop | Runs a bounded collect/refine loop the executor does not model | Yes in the long run | Partly — the round loop is a real capability the seam lacks | Needs round semantics in the seam first (B0 is the prerequisite) | **DECISION_REQUIRED** |
    | `imperative:session_spl_refine` | imperative, `_session_spl_refine_active` | `_run_legacy_dispatch_fallback` | **Runs its own `hook_nodes` execution loop** (`pipeline.py:5767+`) over the v2 projection — a *duplicate executor*, not merely a scheduler bypass | Yes — this is the strongest adopt candidate | No | Would delete a second executor outright | **DECISION_REQUIRED** |
    | `imperative:non_planned` | imperative, outcome not `planned` | canonical failure/non-planned builder | Same as the graph equivalent | No | Yes | — | **KEEP_SEPARATE** |
    | `trace:v2_cursor_synthesis` | `pipeline.py:5122`, v2 cursor routing skipped the executor | none — **trace only** | Synthesizes a `plan_dispatch` trace so a skipped dispatch still reports; produces no execution | No | Yes — it is observability, not authority | — | **KEEP_SEPARATE** |
    | `fixture:ec_demo` | EC demo path | fixture builder | EC purity is a hard boundary; must never gain live scheduling | **Never** | **Yes** — locked invariant | — | **KEEP_SEPARATE** |

    **New finding beyond the planned candidate list.** `_run_legacy_dispatch_fallback` (`pipeline.py:5744`) does not merely bypass the seam — it **duplicates the executor**, holding its own `hook_nodes` map (`prepare_rag_only`, `rag_early`, `workflow_spl`, `spl_postprocessor`, `spl_source_resolve`, `reference_finalize`, `execution`) and running the v2 projection itself. That is a second execution engine, materially different from the other bypasses, and it is pinned by test so it cannot silently spread or silently vanish. It is also the clearest `ADOPT_CANDIDATE` on merit — but classified `DECISION_REQUIRED` because collapsing it changes production-default behavior on session-refine turns.

    **Classification summary:** 2 `SEAM` · 4 `DECISION_REQUIRED` (`graph:rag_only`, `graph:workflow_spl`, `imperative:guided_hybrid`, `imperative:session_spl_refine`) · 4 `KEEP_SEPARATE` (both non-planned lanes, v2 cursor trace synthesis, EC fixture) · **0 adopted in A1**. Every `DECISION_REQUIRED` entry would change production-default execution authority if adopted, which is exactly the item's stop condition, so none was rewired.

    **Structural pins (14 tests):** exactly two seam reachers; `execute_plan_dispatch` has exactly two call sites; the graph route has exactly four destinations; the graph contains **no** guided-hybrid branch; the schedule-producer set is closed to five known functions; the compiler has **no** entry point outside the executor; the v2 projection is consumed **before** predicates in the legacy schedule (encoding the A0 "legacy mirrors v2" finding as a test); `_HOOK_BY_NAME` exists only in the executor; and the known duplicate hook loop is pinned in place.

    **Mutation-negative proof (real mutations against live source, both reverted):** injecting a second `compile_execution_schedule` entry point into `pipeline.py` → `test_compiler_is_only_reached_through_the_executor_seam` **FAILED** (1 failed, 13 passed); injecting a `guided_hybrid` branch marker into `resource_planner_graph.py` → `test_graph_has_no_guided_hybrid_branch` **FAILED** (1 failed, 13 passed). Worktree verified clean after each.

    **Gates.** Item slice **58 passed** (`test_execution_seam_coverage.py`, `test_dual_runtime_single_orchestration.py`, `test_dispatch_authority_wiring.py`, `test_resource_planner_topology_contract.py`). Manifest `protected artifacts unchanged (13 checked)`. Invariant **7/7 PASS** — test-only addition, no runtime behavior, no flag, no state channel.
  - **Invariant / manifest:** Full invariant check; prove no dispatch/authority behavior changed.
  - **Commit boundary:** Inventory tests only; no rewiring.
  - **Stop:** Adopting the LangGraph branches would change production-default execution authority — surface as an architecture decision instead of folding it into a later item.

- [x] **B0 — Wire bounded guided refinement onto real gap state**
  - **Do:** Replace the dead gate; do not redesign the mechanism. Build an `ExecutionContract` from `validation.validated_resource_plan` and drive Plan 2's `refinement_decision(contract, previous_produced_keys=…, current_produced_keys=…, rounds_used=…, max_rounds=MAX_GUIDED_INVESTIGATION_ROUNDS)` from the real produced-evidence delta returned by `collect_guided_hybrid_evidence`, replacing `validated_plan.refinement_recommended` as the round gate. Add the plan-fingerprint stop that Plan 2's mechanism does not have: re-plan, compare fingerprints, stop when the next deterministic plan equals the previous one. Reuse the existing idempotency machinery (`plan_step_operation_identity`, `HookReplayEnvelope`, `build_safe_catalog_fingerprint`) so completed steps never rerun. Emit a trace reason for every outcome: `new_evidence_with_open_gap`, `no_new_evidence`, `evidence_satisfied`, `round_bound_reached`, `plan_unchanged`. No retired LLM proposer, no `collected_count`-only heuristic, no extra round merely because evidence is empty.
  - **Why:** The refinement mechanism exists and is tested but is unreachable, so guided investigation is permanently one-round — the capability gap B2-R2 recorded and C0 deferred here.
  - **Surfaces:** `backend/app/chat/pipeline.py` (guided-hybrid loop); `backend/app/chat/guided_hybrid_refinement.py`; `backend/app/planner/resource_plan_execution_handoffs.py` (consumed, not modified); `backend/app/tests/test_guided_bounded_refinement.py` (**NEW**).
  - **Depends on:** A1.
  - **Failing-first / observation:** Write the round matrix first — it must prove today's loop is one-round before the wiring makes multi-round possible.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_guided_bounded_refinement.py app/tests/test_guided_hybrid_refinement.py app/tests/test_guided_hybrid_collection.py app/tests/test_resource_plan_execution_handoffs.py app/tests/test_execution_idempotency.py -q`; manifest `--check`.
  - **Evidence:** **COMPLETE 2026-08-11; runtime commit `5426956`.** New `backend/app/tests/test_guided_bounded_refinement.py` (21 tests); helper functions added to `guided_hybrid_refinement.py`; the loop gate in `_run_guided_hybrid_dispatch` swapped. Failing-first: the suite failed at collection (absent symbols), then **20 passed / 1 failed** with the helper implemented but the loop unwired — the single failure being the wiring pin — then 21 green after the swap.

    **What was actually wrong:** the loop gated on `validated_plan.refinement_recommended`, hardcoded `False` at `investigation_plan_builder.py:159` since the proposer retired, so `refinement_cap_reached` / `should_run_refinement_pass` could never fire. The cap was unreachable rather than enforced.

    **Round matrix (all pinned by test):**

    | Situation | Outcome | Reason |
    |---|---|---|
    | New produced keys, reachable gap remains, plan differs | **refine** | `new_evidence_with_open_gap` |
    | Produced-key set unchanged | stop | `no_new_evidence` |
    | New evidence closes every reachable gap | stop | `evidence_satisfied` |
    | New evidence but the re-plan fingerprint is identical | stop | `plan_unchanged` |
    | `rounds_used >= MAX_GUIDED_INVESTIGATION_ROUNDS` | stop | `round_bound_reached` |
    | No execution contract | stop | `no_execution_contract` |
    | Empty channels only (`[]`, `{}`) | stop | counted as *not produced*, so empty evidence buys no round |

    **Cap precedence is explicit:** the round bound is evaluated **first**, and a test drives `rounds_used = cap + 5` with new evidence and a changed fingerprint to prove no signal can talk past it. `MAX_GUIDED_INVESTIGATION_ROUNDS` stays 3.

    **Round-varying input is real.** `produced_evidence_keys_from_state(contract, state)` reads the contract's `produces_evidence_keys` against actual state channels, treating empty containers as unpopulated. The contract comes from the guided rail's own `validated_resource_plan` — the source confirmed during research, so nothing was invented to make the wiring fit.

    **Fingerprint deliberately excludes status and provenance** (`step_id:purpose:resource_id` only): a re-plan that changes only bookkeeping is the same plan and must not buy a round.

    **Side effects never repeat:** collection continues through the existing `HookReplayEnvelope` / `plan_step_operation_identity` / `build_safe_catalog_fingerprint` machinery; B0 added no retry and no new execution path.

    **Trace:** `plan_dispatch_trace.guided_refinement_reasons` records why every round ran or stopped, in order — so a one-round turn is now *explained* rather than merely short. This is a key inside the existing trace dict, not a new state channel.

    **Runtime-scope note (recorded, not chased):** guided-hybrid is imperative-only — A1's `test_graph_has_no_guided_hybrid_branch` pins that the graph has no such branch — so "both runtimes" means where guided actually runs. No graph coverage was manufactured for a branch that does not exist.

    **Governance:** tests assert the module contains no `propose_investigation_plan_llm`, `run_resource_plan_shadow`, `llm_plan_bridge` or `collected_count`, and imports nothing from `app.llm` / `app.connectors` / `app.mcp` / `httpx` / `requests`.

    **Gates.** Item slice **74 passed**; broader guided sweep **216 passed, 4822 deselected**. Manifest `protected artifacts unchanged (13 checked)`. Invariant **7/7 PASS**.
  - **Invariant / manifest:** Full invariant check; no LLM planning authority, no MCP/HIL/RBAC change, cap remains hard.
  - **Commit boundary:** Refinement wiring only.
  - **Stop:** The contract source cannot carry collection targets without inventing a mapping; a round could repeat a side effect; the cap could be exceeded.
  - **Scope note to record, not chase:** guided-hybrid is imperative-only (no graph dispatch branch), so "both runtimes" means *where guided actually runs*. Do not manufacture graph coverage for a branch that does not exist.

- [x] **B1 — Controlled flag OFF vs ON evaluation**
  - **Do:** Run a bounded in-process matrix (Plan 2 C1-E6 harness style) over representative and difficult SOC queries with the flag off (control) and on. Compare selected resources/tools, schedule, unnecessary work, evidence completeness, final-answer support, refinement behavior, failures/fallback, and analyst-visible differences. Classify every difference as intended improvement · neutral · regression · safety/authority change. The matrix **must** include turns where the execution-driven path actually activates — with dispatch-v2 enabled on this host it otherwise measures nothing. **Method:** in-process only, no live `/chat` probe arm; latency and model/tool-call counts are coarse secondary evidence, never a gate, because this host's LLM throughput is bound by shared-VPS CPU steal. Do not enable the flag by default from this item.
  - **Why:** Adoption is only justified if the difference it makes is measured and classified rather than assumed.
  - **Surfaces:** observation script under `/tmp` (not committed); plan evidence.
  - **Depends on:** A0 decision, A1, B0.
  - **Failing-first / observation:** Observation only; no feature work. Fix only in-scope defects the matrix exposes.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_resource_plan_execution_wiring.py app/tests/test_resource_plan_execution_activation.py -q`; from root with the host DB export: `TELEMETRY_MODE=none PYTHONPATH=backend:. python3 scripts/audit_reference_probes.py --check`; `PYTHONPATH=backend:. python3 scripts/run_production_parity_eval.py --out-dir /tmp/plan3-b1-parity --check`; manifest `--check`.
  - **Evidence:** **COMPLETE 2026-08-11 — no default change proposed.** Bounded in-process matrix, 10 probes × 2 arms (control flag OFF, candidate flag ON). No live `/chat` arm, per the recorded method assumption.

    **Posture caveat, stated up front:** dispatch-v2 is forced **OFF in both arms** so the execution-driven path can actually activate. On the real host v2 is **ON**, where the compiler never runs at all (A0 finding). This matrix therefore measures the compiler's behavior in a posture production does not currently run — it is a comparison of the two schedulers, not a prediction of production impact. Presenting it as the latter would be dishonest.

    **Activation coverage:** 10 probes → 9 composed a ResourcePlan (1 clarification-mode probe composes none) → **7 of 9 actually activated the compiler**. That satisfies the item's requirement that the matrix contain real activations.

    **Result: 0 schedule differences across all 9 composed probes.** Flag ON produced a byte-identical authoritative schedule to flag OFF on every one — SPL probes `workflow_spl, spl_source_resolve, execution`; knowledge/MITRE/CVE probes `prepare_rag_only, rag_early`. Nothing was compared on resources/tools, unnecessary work, evidence completeness, answer support, refinement behavior or fallback, because the schedule — the only thing the flag governs — did not move.

    **Per-difference classification:** there are no differences to classify. **Neutral**, with zero entries under intended improvement, regression, or safety/authority change.

    **Finding that matters more than the deltas.** The two probes that did **not** activate both downgraded with `no_schedulable_step`, and inspecting them exposed a genuine inconsistency between the two planning surfaces:

    | Probe | `needs_*` booleans | Composed ResourcePlan steps | Legacy schedule |
    |---|---|---|---|
    | T1 alert summary | `needs_spl=True` | **only** `narration` | `workflow_spl, spl_source_resolve, execution` |
    | novel OT | `needs_spl=True`, `needs_mcp=True` | `mcp_execution` (blocked by the guided skill contract) + `narration` | `workflow_spl, spl_source_resolve, execution` |

    Plan-derived scheduling concludes "nothing schedulable"; predicate-derived scheduling builds a full SPL lane. **The EvidencePlan booleans and the composed ResourcePlan disagree about what the turn should do.** Today the disagreement is invisible because the compiler downgrades to legacy — the safe outcome — but it is exactly the latent inconsistency that would surface as dropped work if the compiler ever became authoritative. Classified **neutral today, `DECISION_REQUIRED` for the A0 target architecture**, and carried into G0/G1 as a known gap rather than folded into this item.

    **Default-change proposal: none.** The evidence supports neither direction — flag ON demonstrates no benefit (identical schedules) and the boolean/plan inconsistency above is unresolved. `AI_SOC_RESOURCE_PLAN_EXECUTION_ENABLED` stays default **false**. No stop condition fired: no regression, no safety or authority change, and nothing supporting a default flip.

    **Gates.** Item pytest **22 passed** (`test_resource_plan_execution_wiring.py`, `test_resource_plan_execution_activation.py`); reference probes **10/10** `all probes match the frozen baseline`; production parity **`total=120 base_105=105 exact=120 approved=0 critical=0`**; manifest `protected artifacts unchanged (13 checked)`. No runtime change in this item, so the invariant check is N/A.
  - **Invariant / manifest:** Full invariant check; flag default unchanged by this item.
  - **Commit boundary:** Evidence/test-only commit if needed.
  - **Stop:** Any regression or safety/authority change; or evidence supports a default change — record the proposal and **STOP** for explicit user/COE approval.

- [ ] **G0 — Align documentation with the selected outcomes**
  - **Do:** Update only claims this plan changed: the scheduling-authority model from A0, seam coverage and its deliberate exceptions from A1, and guided refinement becoming live and bounded from B0. Preserve historical evidence. Keep published doc mirrors byte-identical and rebuild the frontend only if a served copy changes.
  - **Why:** Operators must see the selected architecture, not the pre-Plan-3 description.
  - **Surfaces:** `docs/architecture/mcp_tool_routing.md`; `docs/architecture/chat_pipeline_state_v2_and_node_trace.md`; `docs/architecture/architecture_review_2026-08-08.md`; `CLAUDE.md`.
  - **Depends on:** B1.
  - **Failing-first / observation:** `rg` the current claims before editing; only edit what actually changed.
  - **Verify:** `PYTHONPATH=backend:. python3 -m pytest backend/app/tests/test_architecture_details_flow_contract.py -q`; `cmp -s docs/architecture/details.html frontend/public/docs/architecture/details.html`; manifest `--check`.
  - **Evidence:** _(changed claims/files, mirror/build result, manifest disposition, commit)_
  - **Invariant / manifest:** Documentation-only invariant review; never recapture eval/golden/registry drift.
  - **Commit boundary:** Documentation only.
  - **Stop:** Historical evidence would need rewriting; the selected posture is ambiguous.

- [ ] **G1 — Final Plan 3 closure gate**
  - **Do:** Re-audit every checkmark. Each executed item must carry observed evidence; each rejected conditional must carry an explicit N/A with its decision reference. Review the cumulative diff for secrets, authority expansion, baseline noise and unrelated dirt. Run the full gate set and record exact counts. Set frontmatter `status: done` and `implementation_readiness: COMPLETE` only after all pass, and update the `CLAUDE.md` Plans row.
  - **Why:** Adoption is not closed until implementation and evidence agree.
  - **Surfaces:** whole Plan 3 diff and this plan.
  - **Depends on:** G0.
  - **Failing-first / observation:** Re-walk inherited checkmarks skeptically; a missing or undecided N/A fails closure.
  - **Verify:** From root with the host DB export: `.cursor/hooks/audit-plan-discipline.sh plans/2026-08-11_0915_execution-driven-adoption-and-guided-refinement.md`; `python3 scripts/freeze_execution_baseline.py --check --in /tmp/plan3-execution-baseline.json`; `TELEMETRY_MODE=none PYTHONPATH=backend:. python3 scripts/audit_reference_probes.py --check`; `PYTHONPATH=backend:. python3 scripts/run_production_parity_eval.py --out-dir /tmp/plan3-final-parity --check`; `PYTHONPATH=backend:. python3 scripts/eval_out_of_set_intent_probe.py --check`; `./scripts/run_stage3_governance_regression.sh`; `cd backend && PYTHONPATH=../backend:.. python3 -m pytest`; frontend build if G0 changed served docs; re-run the manifest check.
  - **Evidence:** _(item disposition, decisions, targeted/full counts, probe rows, parity tuple, governance counts, manifest before/after, cumulative invariant verdict, commits, known gaps)_
  - **Invariant / manifest:** Cumulative invariant check across `9ee21fd`→HEAD; all seven groups PASS.
  - **Commit boundary:** Final test/evidence/plan-closure commit only.
  - **Stop:** Any unchecked or undecided item; invariant FAIL; protected drift; baseline refresh; unapproved authority; same valid gate failing twice.

## Protected artifacts and baseline policy

P0 captures `/tmp/plan3-execution-baseline.json` with the existing 13-artifact guard. Eval/reference baselines and the 105 golden answers are immutable; all probes use `--check`. Governed registries are immutable unless a decision explicitly needs a new contract and the user separately authorizes registry scope. Published doc mirrors stay mutually identical. Run the manifest before and after every runtime item; unexpected drift is a stop condition, never a warning. `/tmp` observation artifacts are not committed.

## Global stop conditions

1. An explicit architecture or default-on decision is required (A0 always; B1 if a default change is proposed).
2. Protected artifacts drift unexpectedly.
3. The same valid verification gate fails twice on one item.
4. Execution authority would expand beyond explicit approval.
5. Dual scheduling authorities require a product/COE choice.
6. A safety boundary cannot be preserved.
7. A relevant concurrent writer changes a relevant file or HEAD during an item.
8. A baseline/golden/registry would need refreshing.
9. An advisory specialist would perform live I/O or authorize execution.
10. LLM output could carry SPL/query/credentials/raw evidence or reach MCP directly.
11. A side-effecting or uncertain execution would be retried automatically.

Do not silently adapt, skip, weaken a test, or change a recorded decision.

## Verification gaps

Tests marked **NEW** are created in their owning item. A0's and B1's observation scripts are intentionally not prewritten; their exact bodies are recorded in the owning item's Evidence before execution.

## Drift log

| Date | Note |
|------|------|
| 2026-08-11 | Plan created at `9ee21fd`; no runtime implementation performed. Existing user-owned dirt recorded and excluded. |
| 2026-08-11 | Research found the Plan 2 H0 defect **still live**, at `pipeline.py:3643` rather than the recorded `:3669` (lines shifted). Reachability is broader than the enclosing `or` suggests: the `.get()` is an argument expression evaluated before `run_mitre_evidence_branch` is called. |
| 2026-08-11 | Research found **three** schedule producers, not two: the legacy predicate schedule consumes the dispatch-v2 projection as its first branch (`executor.py:199`), so "fixed fallback" and "v2" are not independent on a dispatch-v2 host. A0 is framed accordingly. |
| 2026-08-11 | Research found the graph spine bypasses the seam on `rag_only`, `workflow_spl` and `non_planned_finalize`; only `composed_dispatch` reaches `execute_plan_dispatch`, and no guided-hybrid branch exists in the graph. This materially expands the brief's assumed A1 scope. |
| 2026-08-11 | **User decision: A1 is inventory + structural test only.** No rewiring of `rag_only`, `workflow_spl`, guided-hybrid or session-refine in A1; each bypass is classified `ADOPT_CANDIDATE` / `KEEP_SEPARATE` / `DECISION_REQUIRED`, and adoption that would change production-default execution authority stops for an architecture decision. |
| 2026-08-11 | **Correction to a Plan 2 note:** Plan 2's C0 evidence recorded "guided composes no ResourcePlan". That was a test-harness artifact (`compose_resource_plan_testutil.py:31-35`); production composes guided steps, and guided-hybrid holds a real `validated_resource_plan`. B0's contract source therefore exists and needs no invention. |
| 2026-08-11 | **B1 COMPLETE — no default change proposed.** 10 probes × 2 arms, dispatch-v2 forced off in both so the compiler could activate (7 of 9 composed probes activated). **Zero schedule differences**; flag ON is neutral. Recorded caveat: production runs v2 ON, where the compiler never activates, so this measures the two schedulers rather than production impact. **Finding beyond the deltas:** the two non-activating probes downgraded `no_schedulable_step` and exposed a real inconsistency — `needs_spl=True` while the composed plan carries only `narration` (T1 alert summary) or only a contract-blocked `mcp_execution` plus `narration` (novel OT). EvidencePlan booleans and the composed ResourcePlan disagree about the turn's work; the downgrade currently masks it, but it would become dropped work under a compiler-authoritative model. Carried to G0/G1 as a known gap, `DECISION_REQUIRED` for the A0 target. Flag stays default false. |
| 2026-08-11 | **B0 COMPLETE at `5426956` — guided investigation is no longer permanently one-round.** The dead gate (`refinement_recommended`, hardcoded False since the proposer retired) is replaced by an evidence-driven decision over produced-key deltas from the guided rail's own `validated_resource_plan`, plus a new plan-fingerprint stop so an identical re-plan never runs. Cap is checked first and stays 3, so no evidence signal can talk past it; empty channels count as unproduced, so empty evidence buys no round; side-effect replay protection is the existing `HookReplayEnvelope` machinery, unchanged. Every outcome is traced via `plan_dispatch_trace.guided_refinement_reasons`. Guided sweep 216 passed. |
| 2026-08-11 | **A1 COMPLETE at `97b43dd` — inventory only, nothing rewired.** Ten production-reachable paths classified: 2 `SEAM`, 4 `DECISION_REQUIRED` (`graph:rag_only`, `graph:workflow_spl`, `imperative:guided_hybrid`, `imperative:session_spl_refine`), 4 `KEEP_SEPARATE`. **New finding beyond the planned candidate list:** `_run_legacy_dispatch_fallback` (`pipeline.py:5744`) does not merely bypass the seam — it holds its own `hook_nodes` map and executes the v2 projection itself, i.e. a **second execution engine**, not just a scheduler bypass. Strongest adopt candidate on merit, but classified `DECISION_REQUIRED` because collapsing it changes production-default behavior. All four `DECISION_REQUIRED` entries would change production-default execution authority, which is the item's stop condition, so none was adopted. 14 structural pins added; proven real by two live mutations (second compiler entry point; graph guided-hybrid branch), each detected and reverted. |
| 2026-08-11 | **A0 DECIDED: `PHASE_POLICY_PLUS_RESOURCE_PLAN_SCHEDULING`, approved by Anurag at `2026-08-11T15:01:05Z`.** The "other named model" branch: neither producer is authoritative in its current form. Dispatch-v2's stage logic becomes **Phase Policy** (system-owned lifecycle/answer-shape phases), the ResourcePlan compiler keeps evidence-work scheduling, and a deterministic merge seam is the single producer of the runnable schedule. `predicate_hook_disposition: SYSTEM_OWNED_LIFECYCLE_HOOKS` — `spl_postprocessor` and `reference_finalize` never become plan steps, which closes the measured stage-drop risk by construction rather than by parity work. Dispatch-v2 is not disabled; a compatibility adapter over its `stage_schedule` is permitted as a migration mechanism only. Legacy stays fallback-only. Flag remains default false; no production-default scheduling change authorized. **Decided, not built:** no remaining Plan 3 item constructs the phase contract, so the target lands in a follow-up plan and G0 must say so. |
| 2026-08-11 | Plan self-consistency fix: the starting-architecture **H0 reachability** row still asserted that the enclosing `or` does not protect the unguarded read. H0 execution disproved that. Row corrected in place so the plan does not contradict its own evidence. |
| 2026-08-11 | **A0 OBSERVATION COMPLETE — STOPPED for the authority decision.** Three findings from a 5-probe × 4-posture matrix. (1) The legacy predicate schedule is **not** an independent producer: `legacy_equals_v2` in 10/10 v2-on rows, so there are three code paths but two authorities, with legacy acting as pass-through. (2) Not dual authority today — exactly one schedule is authoritative per posture under an **implicit** precedence `v2 > compiler > legacy` that nothing arbitrates explicitly. (3) The vocabulary delta is material: v2 emits `spl_postprocessor` on every SPL probe and `reference_finalize` on the MITRE probe, and `compiler_only` is empty everywhere — so making the compiler authoritative today would **drop a stage on 4 of 5 probes**. Predicate-hook disposition is therefore a precondition of any compiler-authoritative option, not a footnote. Three options recorded with all nine fields; `selected_authority_model`, `approved_by`, `approved_at` deliberately left blank. |
| 2026-08-11 | **H0 COMPLETE at `8a3073b`, with a premise correction.** The plan claimed the enclosing `or` "does not protect" the unguarded read. Measurement showed `or` **does** short-circuit within the argument expression, so true reachability is narrower than recorded: a query with **no** alert markers **and** a missing/non-dict `query_to_intent`. Still live and production-reachable; the corrected condition is now pinned by two tests. `pipeline.py:3622` was the only unguarded assignment of eight; the four kwarg pass-throughs are correct as-is because every callee accepts `None`. Three hand-rolled state fixtures were discarded in favour of the production seam (`run_canonical_flow` + `graph_node_shadow_tail`) after finalize's nine hard `state[...]` reads defeated each one. |
| 2026-08-11 | H0 observation, deliberately **not** fixed: finalize's nine direct `state[...]` reads raise rather than degrade when canonical planning is incomplete — the same defect class as H0 but outside its brief. Needs its own correctness item plus a decision on whether finalize should degrade or fail closed. Also recorded: the plan's Verify named `test_mitre_branch_contract.py`, which does not exist; `test_mitre_evidence_branch_phase5b.py` + `test_mitre_decision_runtime.py` were substituted. |
| 2026-08-11 | **P0 COMPLETE at HEAD `728bd76`.** Baseline→HEAD is plan/docs only, so runtime content equals `9ee21fd`. Manifest 13/13 before and after, reference probes 10/10, parity `120 exact / 0 approved / 0 critical`. Host posture confirms the A0 premise: `ai_soc_pipeline_dispatch_v2_enabled=True` with `ai_soc_resource_plan_execution_enabled=False`. The known import-time stray newline in `backend/app/chat/detail_tools/__init__.py` reappeared during research and was reverted before capture — third occurrence, always the same one-blank-line append to an empty file, never a code change. |
| 2026-08-11 | B1 method assumption recorded without asking back: in-process matrix only, latency/call counts coarse secondary evidence, because this host's LLM throughput is bound by shared-VPS CPU steal. |
