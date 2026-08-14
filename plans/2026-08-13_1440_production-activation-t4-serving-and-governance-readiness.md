---
name: production-activation-t4-serving-and-governance-readiness
overview: "Move Plan 5's built-but-default-off architecture onto the real VPS: measure test arms, approve a production flag profile, persist it, prove restart/reliability/rollback, then stop at P6_PRODUCTION_GO_LIVE. Repo code defaults may stay conservative false while the VPS profile is persistently ON."
status: active
date: 2026-08-13
canonical_plan: plans/2026-08-13_1440_production-activation-t4-serving-and-governance-readiness.md
loop_runner: plans/LOOP_RUNNER_production-activation-t4-serving-and-governance-readiness.md
source_plan: plans/2026-08-12_1230_production-readiness-understanding-phase-contract.md
baseline_head: 1d32ac6
plan5_merge: 3d22260
implementation_readiness: READY
checklist_items: 37
---

# Plan 6 — Production activation, T4 serving, and governance readiness

## Objective

Plan 5 built the target architecture and left it inactive. Plan 6 does **not** stop at “activation was successfully tested.” It proceeds:

`test arms → approved production flag profile → persistent VPS configuration → restart / reliability / rollback tests → P6_PRODUCTION_GO_LIVE`

ResourcePlan execution is the **primary** activation candidate. T4 is activated only if `P6_T4_SERVING_POSTURE` passes. Live capability enforcement stays **OFF** unless completely new evidence reopens Plan 5 B5. Flags stay independently controllable. Production readiness does **not** require flipping conservative `config.py` defaults to true — the approved VPS/production environment may keep ResourcePlan (and T4, if gated) **persistently ON** in the env profile while repo defaults remain false.

If ResourcePlan execution is declared authoritative, dispatch-v2 precedence **must** be resolved explicitly. `exec ON + v2 ON` while v2 still wins is **not** Plan-5 merge activation.

Mock MCP may validate architecture. Live Splunk/MCP **cannot** be called production-ready without a controlled real read-only connectivity/execution test.

Done means every success question has a committed artifact, every named STOP has a recorded user decision, the production flag profile is persisted and rollback-tested, and `P6_PRODUCTION_GO_LIVE` is recorded (including GO LIVE, DEFER, or KEEP OFF).

**This is not a routing-rule plan.** Do not add keyword heuristics, reopen Plan 4 D2, widen `knowledge_recall` / `alert_summary`, or raise the T4 timeout as a first move.

## Success questions (must be answered with evidence)

1. Does the Plan 5 merged execution architecture work correctly on the actual VPS?
2. Is it better/equivalent to the current production path?
3. What latency/quality/safety cost does activation introduce?
4. Can ResourcePlan execution become authoritative?
5. Can any legacy/duplicate execution path be retired?
6. Can T4 resolve `para.003/004/005/006/007/008/012/015` within an acceptable SLO?
7. What **persistent** flag profile should the VPS/production environment use after Plan 6 (distinct from repo `config.py` defaults)?
8. Are declared PhaseContracts faithful to what actually executes?
9. Which governance debts close now vs stay deferred?
10. If ResourcePlan execution is authoritative, is dispatch-v2 precedence resolved so v2 cannot silently win?
11. Does the approved profile survive restart/recreate, meet reliability/capacity, and roll back cleanly?
12. Has live Splunk/MCP been proven with a controlled read-only test, or is MCP honestly `live_mcp_unproven`?

## Stop conditions

- All checklist items checked with recorded evidence, **or**
- Same verification gate fails twice on one item, **or**
- A named decision gate below is reached — **stop and ask**

## User directives

- Branch from `1d32ac6` (`origin/master`). Use `3d22260` only when measuring the Plan 5 architecture delta.
- Keep Plan 5 activation flags independently controllable. Testable ON on VPS ≠ repo default ON. Persistent VPS ON also ≠ repo default ON.
- ResourcePlan execution is the primary activation candidate. T4 only if its serving gate passes. Live capability enforcement stays OFF unless new evidence reopens Plan 5 B5.
- If exec is declared authoritative, resolve dispatch-v2 precedence in the same decision. Do not call `exec ON + v2 ON` Plan-5 activation while v2 wins.
- Mock MCP validates architecture only. Live Splunk/MCP production-ready requires a controlled real read-only test.
- VPS is a first-class test surface. Local/CI cannot substitute for serving/latency/schedule/persistence evidence.
- Do not implement until this draft is approved. After approval: `loop-asap` from P0.
- Do not commit unrelated working-tree dirt.
- Git: follow **Commit / PR / merge** below. Never commit to `master`. Never squash-merge. Never merge past a STOP that the included commits depend on.

## Governance invariants

- No direct LLM→MCP path. LLM has no execution authority. Plan 4 D3 advisory-finality preserved.
- Routing authority stays deterministic. Primary skill is ownership/compatibility, not sole capability authority. Required capabilities are satisfied by the complete governed schedule.
- Candidate SPL never executable. Validated non-null `normalized_spl` before MCP. HIL/RBAC/MCP gate authoritative.
- Side-effecting/uncertain steps never auto-repeat. Bounded refinement. No automatic capability widening.
- Plan 2 B1 `RETIRE` (planning-model rails stay retired). Plan 3 A0 architecture is built, not redesigned.
- `UNDERSTANDING_ROUTER_ON_LOW_CONFIDENCE` stays retired. `B_LIVE_CAPABILITY_ENFORCEMENT = DEFAULT_OFF_ARCHITECTURALLY_DEFERRED` (`cisco.ot.029`). Preserve the flag; do not make ON an activation arm.
- `D1_LIVE_POSTURE_ROUTE = RATIFIED_FOR_MEASURED_ROWS` (7 rows only). `D1_PARAPHRASE_RESIDUE = DEFERRED_T4_SEMANTIC_SERVING_LIMIT`.
- `A2.5 = DEFERRED_SEPARATE_GOVERNED_PROMOTION` (E2 recorded **KEEP DEFERRED**; do not promote in Plan 6).
- **No new env flags.** Ride existing Plan 5 flags. If a new flag appears unavoidable, STOP and ask.
- New `state["key"]` values must be declared on `ChatPipelineState`. Verify on the RP graph `.invoke()` path, not only by calling node functions. Cover imperative rollback too.
- Debug/trace additions go on `debug_summary` (metadata priority keep-list). Do not rely on a new `control_plane_trace` section surviving `_slim_control_plane_trace` (`backend/app/connectors/telemetry/db.py`).
- After governance runs, revert **only** the six stale reports. Never `git checkout -- docs/evals/`.
- EC/demo path stays fixture-only. No secret exposure.

## Named STOP gates (do not preselect outcomes)

- `P6_RESOURCE_PLAN_EXECUTION_ACTIVATION` (C0) — before declaring ResourcePlan execution production-authoritative **or** changing `config.py` defaults. Must also record **dispatch-v2 precedence**. Outcomes for exec: KEEP OFF / **VPS PERSISTENT ON** (repo default stays false) / DEFAULT ON WITH FALLBACK / DEFAULT ON + begin fallback retirement. Outcomes for v2 (required if exec is any ON): `V2_WINS` (honest: this is **not** Plan-5 merge activation) / `V2_OFF_ON_VPS` (merge actually runs) / `CHANGE_LADDER` (code change so merge is authoritative even when v2 projects — needs evidence, do not self-select).
- `P6_EXECUTION_SEAM_ADOPTION` (C3) — before adopting any `DECISION_REQUIRED` seam or retiring `_run_legacy_dispatch_fallback`.
- `P6_T4_SERVING_POSTURE` (D3) — before changing T4 default, timeout, serving posture, or adding T4 to the persistent VPS profile. T4 is activated only if this gate passes.
- `P6_MITRE_DRAFT_PROMOTION` (E2) — before promoting the 11-row MITRE DRAFT delta.
- `P6_STALE_REPORT_DISPOSITION` (E3) — before refreshing/rebaselining/restructuring the six committed stale governance reports.
- `P6_PRODUCTION_GO_LIVE` (F5) — after persistent config, reliability/capacity (including failure classes, not smoke), rollback, and live-MCP honesty. Present the full readiness matrix. Outcomes: GO LIVE with recorded profile / DEFER / ROLL BACK AND KEEP OFF. **GO LIVE requires zero critical blockers** and an explicit user choice. This is the plan’s production decision, not C0/D3 test-arm approval.

After **B-GATE** and **D2** are both checked, present **C0 and D3 together** in one handoff. Do not start C1 or D4 until the matching decision is recorded. Do not call the VPS “production-ready” until **F5**.

## Commit / PR / merge

Matches Plan 5 (PR #131, `--merge` not squash, commits preserved) and `AGENTS.md` Commit Hygiene. `loop-asap` on this plan **authorizes** the cadence below on the feature branch only. Push, PR, and merge still need the user the first time they happen; after a PR exists, further pushes to that branch are allowed. **Merge to `master` always requires an explicit user ask.**

### Branch

```bash
git checkout -b feat/plan6-production-activation 1d32ac6
```

Never commit on `master`. If already on `master` when loop-asap starts, create this branch before the first commit. Do not rebase onto a rewritten `3d22260`; `1d32ac6` is the branch point.

### When to commit

Commit after a **scoped batch** whose Verify passed, not after every keystroke and not as one giant Plan 6 commit.

| Batch | Items | What lands |
|-------|--------|------------|
| docs/inventory | P0, P0.1, P0.2 | `docs/evals/plan6/` schema + maps (no runtime) |
| observability | A0, A1 | `debug_summary` / trace fields + tests |
| harness | A2, A3 | corpus, `eval_plan6_vps_harness.py`, shadow-compare tests |
| gate A | A-GATE | no extra commit unless the gate produced a fix |
| VPS evidence | A4, B0, B1, B2, D0, D1, D2 | `docs/evals/plan6/runs/` and T4 reports only |
| activation apply | C1 | **only after C0**; VPS/profile persistence docs and/or `config.py` default — never mixed with T4; must record v2 precedence |
| T4 apply | D4 | **only after D3 passes**; omit if D3 keeps T4 deferred; independent commit from C1 |
| go-live ops | F2, F3, F4 | persistent profile, reliability/capacity, rollback runbook — no `config.py` default required |
| go-live STOP | F5 | no code unless a documented rollback fix; merge still user-only |
| seam proof | C2 | `docs/evals/plan6/seam_equivalence.md` (+ code only if C3 later approves) |
| seam apply | after C3 | **only if approved**; otherwise no commit |
| MITRE provenance | E0 | provenance accuracy; no promoter |
| MITRE promote | after E2 | **only if approved** + protected-manifest recapture |
| stale reports | after E3 | **only if approved** |
| closure | G0, G1 | report + docs; README Active-work → Done |

One commit per row is the default. Combine only when the diff is docs-only and the items share one concern. Never mix: runtime observability + flag-default change; C1 + D4; protected-artifact promotion + unrelated docs; governance stale-report refresh + anything else.

### Commit message

```text
plan6(<item>): imperative summary under ~72 chars

Why this batch exists. Verify command + result. STOP name if this commit
is gated (C0/C3/D3/E2/E3/F5).
```

Examples: `plan6(A0): surface qualification_tier on debug_summary`, `plan6(C1): keep resource-plan execution default off`.

### Never commit

- `.env`, tokens, passwords, session secrets, MCP payloads, raw SPL with credentials
- Unrelated dirt: `.claude/settings.local.json`, `backend/app/chat/detail_tools/__init__.py`, `.playwright-mcp/`, `g0-*.png`, `output/`
- The six stale governance reports unless E3 approved that refresh
- Protected artifacts (`question_runtime_map_v1.json`, `use_cases/catalog.json`, frozen eval baselines) unless the matching STOP approved it and `freeze_execution_baseline.py --check` is green after recapture
- Flag-default changes in `config.py` until C0 / D3 is recorded in Approved decisions
- Eval baseline refreshes to hide a regression

Pre-commit for any runtime/planner/SPL/MCP/LLM/debug-trace diff: `/invariant-check` must be 7/7 PASS. One FAIL blocks the commit.

### PR

**Default: one PR**, like Plan 5.

```bash
git push -u origin feat/plan6-production-activation
gh pr create --title "Plan 6: production activation, T4 serving, governance readiness" --body "..."
```

Open a **draft PR after A-GATE** (observability is reviewable, no defaults changed). Mark ready for review after B-GATE + D2 evidence is on the branch, still **before** C1/D4 if those STOPs are not yet decided.

PR body must include:

- Branch point `1d32ac6`; Plan 5 merge `3d22260` for architecture delta only
- Checklist progress (N/37)
- Flag matrix: repo default vs VPS vs proposed (no secrets)
- Named STOPs and whether they are open or recorded
- Test evidence: targeted pytest, and forecast-rule set if defaults/authority moved
- Explicit: frozen `--arm both` does not observe L4/L5; parity 120 exact is not routing correctness

**Optional split** (only if the user asks, or C0/D3 land on different dates):

1. PR-A — A0–A-GATE (observability; safe to merge with defaults unchanged)
2. PR-B — remaining measurement + docs
3. PR-C — C1 and/or D4 **after** the matching STOP

Do not open a PR that contains an unapproved flag-default or promoter run.

### Merge

- **Method:** merge commit, not squash, not rebase-onto-master. Same as Plan 5 PR #131.

```bash
gh pr merge <n> --merge
```

- **Who:** user only. Agents never merge to `master` unless the user explicitly says to merge this PR.
- **When:** after G2 Verify is green **or** after an optional PR-A if the user wants observability on `master` early.
- **Block merge if:** a STOP that the PR depends on is still open (including `P6_PRODUCTION_GO_LIVE` if the PR claims production go-live); `/invariant-check` failed; protected manifest is not N/N; stale reports were committed without E3; unrelated dirt is in the diff; `config.py` defaults changed without C0/D3 in Approved decisions; the PR claims Plan-5 execution activation while v2 still wins.
- No force-push to `master`. No `--no-verify`. Amend only under the existing user git-safety rules.

After merge: record the merge SHA in G2 Evidence and set plan `status: done`. Update `plans/README.md` Active-work like Plan 5.

## Approved decisions

### C0 — `P6_RESOURCE_PLAN_EXECUTION_ACTIVATION` (2026-08-13)

**Field 1 — exec posture: KEEP OFF.** Repo `config.py` `ai_soc_resource_plan_execution_enabled` stays false. ResourcePlan execution is not added to the persistent VPS/production profile.

Arm C proved Plan-5 `merge_schedule` is reachable and executes when ResourcePlan execution is ON and dispatch-v2 is OFF (merge **5/12**; **7/12** legitimately `merge_not_reachable`). KEEP OFF is an evidence-based production decision, **not** a failure of Arm C. Production authority is not yet safe to move to that path: with v2 OFF, two `workflow_spl` / `no_schedulable_step` rows lose `spl_postprocessor` even though merge does not run, so `V2_OFF_ON_VPS` would introduce known missed work. Exec ON + v2 ON would be `V2_WINS` and must not be represented as ResourcePlan activation. No evidence supports changing the repo default. **Do not self-select `CHANGE_LADDER`.**

**Field 2 — dispatch-v2 precedence: N/A** because ResourcePlan execution remains OFF. Keep dispatch-v2 **ON** in the current VPS/COE posture.

A future ResourcePlan activation requires either (1) evidence that the v2-OFF missed-work cases are correctly covered, or (2) an explicitly approved `CHANGE_LADDER` / execution-seam change. Do not implement that change as part of this STOP.

Artifact: `docs/evals/plan6/c0_d3_stop_decisions.md`.

### D3 — `P6_T4_SERVING_POSTURE` (2026-08-13)

**KEEP 2.0s / DEFAULT-OFF.** Omit T4 from the persistent production profile.

`D1_PARAPHRASE_RESIDUE = DEFERRED_T4_SEMANTIC_SERVING_LIMIT`.

Qualification/routing is correct. 9/9 baseline T4 attempts timed out at ~2s; 0 accepted contracts; 0 false capability widening. No viable alternate serving option exists in the current environment. Raising timeout is not supported by evidence (90s/180s probes still did not return the required JSON). N=2 worsens slot pressure. Do not add keyword heuristics.

Live capability enforcement remains **OFF**.

Artifact: `docs/evals/plan6/c0_d3_stop_decisions.md`.

### C3 — `P6_EXECUTION_SEAM_ADOPTION` (2026-08-13)

**KEEP 0 ADOPTED.** Inventory stays **2 SEAM / 4 DECISION_REQUIRED / 4 KEEP_SEPARATE / 0 adopted**.

Do not retire `_run_legacy_dispatch_fallback`. Do not adopt any `DECISION_REQUIRED` execution seam. Do not implement `CHANGE_LADDER`.

C0 KEEP OFF is the production-authority context. Arm C proved `merge_schedule` is reachable, but v2-OFF missed `spl_postprocessor` on `p6.multi.knowledge_spl_mcp` and `p6.live_posture.d1_003`. C2 reconfirmed the legacy fallback skips `spl_postprocessor`; safety remains the existing validation/execution gates. Plan 6 has evidence to retain the present seams, not to adopt, consolidate, or retire them.

This is a **deferred architectural follow-up**, not a Plan 6 production blocker: the approved profile keeps ResourcePlan execution OFF and dispatch-v2 ON.

Future seam adoption / fallback retirement requires (1) measured equivalence or improvement, (2) explicit coverage of the known missed-work cases, and (3) a separately approved execution-authority / change-ladder decision.

Artifact: `docs/evals/plan6/c3_stop_decision.md`.

### E2 — `P6_MITRE_DRAFT_PROMOTION` (2026-08-13)

**KEEP DEFERRED.** Retain `DEFERRED_SEPARATE_GOVERNED_PROMOTION`.

Do not run the existing promoter CLI. Do not modify the 11-row drift ledger, the runtime map, or the catalog. Do not recapture the protected manifest for a promotion.

E1 confirmed the candidate mappings and measured their analyst-visible effect, but also showed that the existing promoter CLI is broader than an 11-question-row promotion and would rewrite four catalog use cases, including dropping `T1110.003` on `auth_failed_login_spike`. Plan 6 does not have approval to broaden this governed metadata change. Preserve current hashes and the 15/15 protected freeze. E1 remains evidence for a future separate governed MITRE promotion decision.

Artifact: `docs/evals/plan6/e2_stop_decision.md`. E1 measurement: `docs/evals/plan6/mitre_11row_promotion_delta.md`.

### E3 — `P6_STALE_REPORT_DISPOSITION` (2026-08-13)

**CONTINUE PRESERVING.** Keep the six committed governance/eval reports tracked exactly as they are today.

Do not regenerate and commit them as a new baseline. Do not change `ARTIFACT_REFRESH_POLICY.md`. Do not move them out of source control, add gitignore rules, modify governance harness paths, or turn this into a report-lifecycle redesign.

Plan 5 already classified this as `STALE_REPORT_REFRESH` outside activation work. The reports are clean vs HEAD and are not protected artifacts. Governance `--check` writes before validation (known worktree dirt). That does not justify broadening Plan 6. After governance, revert **only** those six files so unrelated report drift is not committed. This is a deliberate preservation decision, not an unresolved gap.

Artifact: `docs/evals/plan6/e3_stop_decision.md`. Inventory: `docs/evals/plan6/e3_stale_report_inventory.md`. Policy file unchanged.

### F5 — `P6_PRODUCTION_GO_LIVE` (2026-08-14)

**DEFER — intended architecture not yet production-authoritative.**

Recorded by the user after the F5 evidence matrix was presented. `GO LIVE WITH RECORDED PROFILE` was available (critical blockers **0**) and was **not** taken.

Reason: Plan 6 proved the new architecture **experimentally** but did not make it production-authoritative. Production go-live must not be declared while normal execution authority remains dispatch-v2. The intended production architecture is `ResolvedQueryContract → ResourcePlan + PhaseContract → deterministic compiler → governed executable schedule`, with bounded T4 semantic understanding for genuinely unresolved T4 queries. Go-live is deferred until that architecture is corrected and passes its own production gates.

This is **not** a rollback decision and **not** a decision to stay permanently on the old architecture. `ResourcePlan OFF + dispatch-v2 ON + T4 OFF` is a safe baseline and rollback posture, **not** the destination; `exec ON + v2 ON` (`V2_WINS`) is **not** ResourcePlan activation either.

Plan 6's measurements stand as correct discovery work: it found the blockers. Do not rewrite them as failures.

Follow-on (user-approved, narrowly scoped — **not** a broad redesign): reopen the deferred execution-authority / `CHANGE_LADDER` work only as far as measured evidence requires, in a separate focused plan. Live capability enforcement stays OFF; no routing keyword heuristics; the rejected "one primary skill owns all capabilities" model is not resurrected.

Artifact: `docs/evals/plan6/f5_go_live_decision_packet.md`. Continuation plan: `plans/2026-08-14_1130_resource-plan-authority-and-t4-integration.md`.

## Brief vs current code (do not silently absorb)

1. **Dispatch-v2 beats ResourcePlan execution.** `backend/app/planner/executor.py` (`_execution_driven_schedule_detailed`): if execution is ON **and** a v2 projected schedule exists, merge stands down with `dispatch_v2_projected_schedule`. COE profile sets `AI_SOC_PIPELINE_DISPATCH_V2_ENABLED=true` (`env/profiles/coe.env.example`). Flipping execution ON on today’s VPS does **not** exercise Plan 5 merge. **Arm C (exec ON, v2 OFF) is the only VPS arm that does.**
2. **Merge only runs on the `execute_plan_dispatch` seam.** RP-graph `rag_only` / `workflow_spl` (no composed plan), guided hybrid, and session-SPL-refine do not hit `merge_schedule`. Corpus rows must be classified by actual path.
3. **No shadow schedule-compare mode exists.** `ROUTE_AUTHORITY_COMPARE_ENABLED` compares routes, not schedules. Dual-parity compares runtimes.
4. **VPS cannot currently see Plan 5 architecture.** `ResolvedQueryContract` / qualification tier are not on `PlaceholderResponse` or `/debug` `debug_summary`. Canonical planning events are not joined into `/debug`.
5. **64KiB metadata trim.** `_slim_control_plane_trace` drops sections not in its keep list. New observability must live on `debug_summary` (priority-kept) or be added to the slim keep list.
6. **Live capability enforcement is not a Plan 6 activation arm.** Plan 5 B5 already rejected default ON.
7. **COE MCP doc vs profile drift:** rollout doc says MCP execution false; `coe.env.example` sets mock execution true with `MCP_MODE=mock`. Default VPS evidence path is mock MCP. Live Splunk is optional and must not block the plan.
8. **Frozen truth-set `--arm both` still does not observe L4/L5.** Use `scripts/eval_residual_routing_after_architecture.py`, `scripts/eval_b5_capability_enforcement.py`, in-catalogue contract, and the VPS corpus.
9. **T4 timeout is already independently configurable** (`AI_SOC_T4_SEMANTIC_UNDERSTANDING_TIMEOUT_SECONDS`, default 2.0). Not an invitation to raise it first.
10. **One VPS cannot run Arms B/C/D in parallel.** They mutate the same env. Serialize; restore Arm A between T4 and execution arms as specified below.

## Architecture to preserve

```
QUERY → T1–T3 qualification OR bounded T4
     → ResolvedQueryContract (no skill, no execution authority)
     → deterministic adjudication
     → primary skill (ownership/compatibility, not sole capability authority)
     → ResourcePlan + PhaseRegistry → PhasePolicy → PhaseContract
     → deterministic merge → ONE dependency-valid schedule
     → Knowledge / SPL / MCP / validation / HIL (zero..N, ordered by dependencies)
     → bounded evidence-driven refinement → ANSWER
```

Knowledge / SPL / MCP are not mutually exclusive. Ordering comes from dependencies, never a fixed Knowledge→SPL→MCP sequence.

## Current production / VPS execution-path map

- Default `/chat`: `langgraph_orchestration_enabled=true` → `run_chat_via_resource_planner_graph`.
- SEAM (2): `graph:composed_dispatch`, `imperative:composed_plan` → `execute_plan_dispatch`. **0 adopted.**
- DECISION_REQUIRED (4): `graph:rag_only`, `graph:workflow_spl`, `imperative:guided_hybrid`, `imperative:session_spl_refine`.
- KEEP_SEPARATE (4): non-planned finalize, EC demo fixture, v2 cursor synthesis, imperative non-planned.
- `_run_legacy_dispatch_fallback` (`pipeline.py`): sole call site session-SPL-refine. Legacy branch **skips `spl_postprocessor`**. Safe because MCP gate refuses unapproved/null `normalized_spl` plus RP-graph `spl_validate`. Proof: `docs/evals/plan5/c3_fallback_equivalence.md`.
- `mitre_finalize` / `cve_adapter`: PhaseRegistry `pipeline_inline`; run inside `graph_node_context_finalize`; dropped from hook schedules.
- Merge ladder: flag off → zero merge code; v2 projected schedule present → v2 wins; else `merge_schedule`.

## Flag matrix (preserve independent control)

Live VPS values are **UNKNOWN until A4**. Never print secrets.

**Plan 5 activation flags**

- `AI_SOC_RESOURCE_PLAN_EXECUTION_ENABLED` — `config.py` default **false**; COE profile absent/false. Merge/compiler only when no v2 projection. **Primary activation candidate.** Persistent VPS ON is allowed while repo default stays false. Candidate final: **undecided (C0 + F5)**.
- `AI_SOC_T4_SEMANTIC_UNDERSTANDING_ENABLED` — default **false**; COE absent/false. T4-only advisory hop. **Activate only if D3 passes.** Candidate final: **undecided (D3 + F5)**.
- `AI_SOC_T4_SEMANTIC_UNDERSTANDING_TIMEOUT_SECONDS` — default **2.0**. Independent of enable. Do not raise first. Candidate: **undecided (D3)**.
- `AI_SOC_LIVE_CAPABILITY_ENFORCEMENT_ENABLED` — default **false**. **Not a VPS activation arm. Stays OFF** unless completely new evidence reopens Plan 5 B5.
- `AI_SOC_PIPELINE_DISPATCH_V2_ENABLED` — repo default **false**; **COE profile true**. Beats ResourcePlan execution today. If C0 chooses any exec ON, C0 **must** pick `V2_WINS` / `V2_OFF_ON_VPS` / `CHANGE_LADDER`. `V2_WINS` cannot be labelled Plan-5 merge activation.

**Already-on VPS/COE (do not silently change)**

- `LANGGRAPH_ORCHESTRATION_ENABLED` default true (COE true).
- `AI_SOC_GUIDED_HYBRID_INVESTIGATION_ENABLED` repo false / COE true.
- `AI_SOC_GUIDED_LLM_ENABLED` repo false / COE true (budget/deadline only).
- `AI_SOC_LLM_FINAL_SYNTHESIS_ENABLED` + `AI_SOC_LLM_LIVE_SYNTHESIS_ENABLED` repo false / COE true (both required for live composer).
- T2 shape/surfacing/RAG: repo false / COE true.
- MCP: repo execution false; COE profile mock execution true with `MCP_MODE=mock`.

**Retired / not flags:** `UNDERSTANDING_ROUTER_ON_LOW_CONFIDENCE`, `CONTROL_PLANE_ENABLED`, `AI_SOC_CANONICAL_PLANNING_ENABLED`. No schedule-shadow flag exists.

## Minimum useful VPS test matrix

- **Arm A — current VPS production.** v2 ON (COE), exec OFF, T4 OFF. Baseline.
- **Arm B — exec ON, v2 ON, T4 OFF.** Expected: merge does **not** run on composed turns that project a v2 schedule. Success is seeing `dispatch_v2_projected_schedule` in trace, not a silent no-op with no reason.
- **Arm C — exec ON, v2 OFF, T4 OFF.** The only arm that runs `merge_schedule` on VPS for composed-plan turns.
- **Arm D — T4 ON** on restored Arm A. Measures serving, not execution.

Do not add live-capability-ON as an activation arm.

**MCP honesty:** mock MCP may validate architecture (Arm B/C, F0). Live Splunk/MCP is **not** production-ready until F3’s controlled read-only test. Missing credentials → record `live_mcp_unproven`; F5 must not claim live MCP.

After each VPS flag change: `docker compose restart backend`. F2 is the item that makes the **approved** profile persist across restart/recreate — test-arm env toggles are not persistence.

## VPS corpus

`docs/evals/plan6/vps_corpus_v1.json` — one query each unless noted:

- T1 exact / known knowledge
- T2/T3 known-but-nontrivial
- T4 out-of-registry investigation
- SPL-only draft/review
- SPL + MCP evidence (mock MCP)
- knowledge → SPL → MCP multi-step
- clarification-required
- unsafe/action request
- supplied-alert summarization
- live posture query (one of the 7 ratified rows, not a family-wide rule)
- repeated evidence/refinement
- failure/degraded dependency
- the 8 residual paraphrases (Arm D only): `para.003/004/005/006/007/008/012/015`

Per query compare: route, ResolvedQueryContract, ResourcePlan, PhaseContract, schedule, executed phases, final answer, grounding/evidence, safety, HIL, execution eligibility, latency, errors/fallbacks, duplicate work, extra LLM hops.

Environment capture (no secrets): git SHA, enabled flags (booleans/names only), model endpoint host/role without tokens, DB reachability, MCP mode + connectivity boolean, environment identity, test account/role, timestamp, corpus version.

## Forecast-rule gate set (any routing / execution-authority / flag-default change)

Targeted failing-first tests; full backend pytest; layer-correct residual/B5/in-catalogue instruments (not frozen truth-set alone); frozen truth-set `--check` no-regression; production parity; path honoring; sentinel; Cisco; reference probes; protected manifest `15/15` (or N/N after explicit add); governance regression; `/invariant-check`. Then the VPS corpus if a live surface moved.

After governance: revert only:

- `docs/evals/langgraph_dual_parity_report.json`
- `docs/evals/langgraph_dual_parity_summary.md`
- `docs/evals/soc_clean_answer_eval_report.json`
- `docs/evals/soc_clean_answer_eval_report.csv`
- `docs/evals/soc_clean_answer_eval_summary.md`
- `docs/evals/llm_template_audit_report.md`

## Dependency order

```
P0 → P0.1 → P0.2 → A0 → A1 → A2 → A3 → A-GATE
A4 (VPS) depends on A0, A1, A2
B0 depends on A-GATE, A4
B1 depends on B0   (NOT parallel with B0 — same VPS)
D0 depends on A4, B1   (B1 restores Arm A first)
D1 → D2
B2 depends on B0, B1
B-GATE depends on B2
C0 depends on B-GATE          STOP (present with D3 when D2 is also done)
D3 depends on D2              STOP
C1 depends on C0
D4 depends on D3
C2 depends on C0
C3 depends on C2              STOP
E0 depends on C0, A1
E1 depends on C0
E2 depends on E1              STOP
E3 depends on C0              STOP
E4 depends on E2, E3, P0.1
F0 depends on C1, D4
F1 depends on F0
F-GATE depends on F1
F2 depends on F-GATE, C1, D4
F3 depends on F2
F4 depends on F3
F5 depends on F4              STOP P6_PRODUCTION_GO_LIVE
G0 depends on F5, E0, E2, E3, E4
G1 depends on G0
G2 depends on G1
```

Preferred single-agent walk is in the LOOP_RUNNER.

---

## Checklist (37 items)

### P0 — baseline + inventory (LOCAL)

- [x] **P0** — Freeze local baseline at `1d32ac6`
  - **Do:** Record git SHA, `origin/master` alignment, pytest count, protected manifest `15/15`, and that Plan 5 flags still default false. Write `docs/evals/plan6/P0_BASELINE.md`. Surface: LOCAL.
  - **Why:** Plan 6 measurements need a frozen starting point distinct from `3d22260`.
  - **Failing-first:** file absent, or `HEAD` ≠ `1d32ac6`, fails the item.
  - **Verify:** `git rev-parse HEAD origin/master`; `python3 scripts/freeze_execution_baseline.py --check`; `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_phase_merge_activation.py app/tests/test_semantic_t4_understanding.py app/tests/test_execution_seam_coverage.py -q`; grep `config.py` defaults false for `ai_soc_resource_plan_execution_enabled`, `ai_soc_t4_semantic_understanding_enabled`, `ai_soc_live_capability_enforcement_enabled`, `ai_soc_pipeline_dispatch_v2_enabled`.
  - **Depends on:** none
  - **Evidence:** HEAD=`1d32ac66dd6c707789db8b44574bd566af401952` = origin/master; freeze `--check` 15/15; pytest 37 passed; config.py defaults false at 403/410/413/417. Artifact `docs/evals/plan6/P0_BASELINE.md`. No commit (loop-asap follow-up: do not commit unless asked).

- [x] **P0.1** — Commit flag matrix + execution reachability map
  - **Do:** Write `docs/evals/plan6/flag_matrix.md` and `docs/evals/plan6/execution_path_map.md` from code + COE profile. Live VPS values stay `UNKNOWN` until A4. State explicitly that v2 projection beats merge, and which query shapes never hit `execute_plan_dispatch`. Surface: LOCAL.
  - **Failing-first:** map omits v2-wins or the four DECISION_REQUIRED paths → fail.
  - **Verify:** `rg dispatch_v2_projected_schedule backend/app/planner/executor.py`; `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_execution_seam_coverage.py app/tests/test_fallback_lifecycle_equivalence.py -q`; every flag in the User directives / flag matrix section appears in `flag_matrix.md`.
  - **Depends on:** P0
  - **Evidence:** `rg` hit `return None, "dispatch_v2_projected_schedule", None` in executor.py; pytest 19 passed; all 20 flag-matrix names present. Artifacts `flag_matrix.md` (VPS=UNKNOWN) + `execution_path_map.md` (v2-wins + 4 DECISION_REQUIRED).

- [x] **P0.2** — Evidence directory + env-capture schema
  - **Do:** Create `docs/evals/plan6/` README + env-capture JSON schema that **rejects** keys matching `token|password|secret|api_key`. LOOP_RUNNER already exists — do not recreate it. Surface: LOCAL.
  - **Failing-first:** NEW schema test fails if those secret keys are accepted.
  - **Verify:** schema unit test (NEW under `backend/app/tests/` or `tools/`) rejects secret keys; `ls docs/evals/plan6/`; `test -f plans/LOOP_RUNNER_production-activation-t4-serving-and-governance-readiness.md`.
  - **Depends on:** P0
  - **Evidence:** `pytest app/tests/test_plan6_env_capture_schema.py -q` → 6 passed (token/password/secret/api_key rejected, nested password rejected). LOOP_RUNNER present; schema at `docs/evals/plan6/env_capture.schema.json`.

### A — observability + harness

- [x] **A0** — Surface qualification tier + ResolvedQueryContract on VPS debug
  - **Do:** Add a redacted summary to **`debug_summary`** (required; survives metadata priority) and optionally `control_plane_trace` **only if** the section is added to `_slim_control_plane_trace` keep list: `qualification_tier`, intent family, answer goal, required/prohibited caps, ambiguity, provenance source. IDs/status only. No skill field, no execution authority, no raw query beyond existing preview policy. Cover RP-graph default path **and** imperative rollback. Do not add a new env flag. If a new state key is required, declare it on `ChatPipelineState` and prove it survives RP graph `.invoke()`. Surface: LOCAL.
  - **Why:** Contract exists in pipeline state (`canonical_planning_orchestrator.py`) but is absent from `debug_summary.py` / `PlaceholderResponse`. Slim-trace would drop a new CP-only section.
  - **Failing-first:** extend `backend/app/tests/test_debug_summary.py` so it fails without `qualification_tier` on `build_debug_summary`, then passes. Add an RP-graph invoke assertion, not only a node-function call.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_debug_summary.py app/tests/test_debug_summary_phase2c.py -q`; redaction: summary has no skill/execution_eligible; `rg qualification_tier backend/app/chat/debug_summary.py`.
  - **Depends on:** P0.1
  - **Evidence:** pytest test_debug_summary.py + test_debug_summary_phase2c.py → 7 passed (incl. RP graph invoke). `rg qualification_tier` hits `redact_resolved_query`. resolved_query has no skill/execution_eligible. Slim keep list includes `resolved_query`. No new flag; reused existing `resolved_query_contract` state key. No commit.

- [x] **A1** — Surface schedule provenance on debug_summary
  - **Do:** Extend `debug_summary` with: ResourcePlan fingerprint/id, PhaseContract names (`trace_payload` already exists), planned `dispatch_schedule`, executed hook/node list, unified `degrade_reason` (`dispatch_v2_projected_schedule` / merge / fallback / compiler downgrade / none), `session_role`/RBAC decision, major-phase `duration_ms` from existing `node.*` steps. Prefer structured IDs. Do not dump SPL text, tokens, or raw MCP rows. Same dual-path + TypedDict + no-new-flag rules as A0. Surface: LOCAL.
  - **Failing-first:** NEW assertions on `build_debug_summary` for these keys on a flag-on in-process turn; flag-off omits phase_merge except planned dispatch.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_debug_summary.py app/tests/test_phase_merge_activation.py -q`; grep that fingerprint / `degrade_reason` reach `debug_summary`; `/invariant-check` on the diff.
  - **Depends on:** A0
  - **Evidence:** pytest test_debug_summary.py + test_phase_merge_activation.py → 23 passed (with telemetry connector). `rg` hits `resource_plan_fingerprint` and `degrade_reason` in debug_summary.py. Flag-off omits phase_names; v2-wins reason preserved. No new flag. No commit.

- [x] **A2** — VPS corpus + harness
  - **Do:** `docs/evals/plan6/vps_corpus_v1.json` + `scripts/eval_plan6_vps_harness.py` (**NEW**) wrapping existing `scripts/ask_chat.sh` (do not invent a second chat client). Captures env (P0.2 schema), POSTs `/chat` per row, writes redacted evidence under `docs/evals/plan6/runs/<timestamp>/`. Surface: LOCAL (harness); VPS run is A4.
  - **Failing-first:** harness refuses to start without env capture; writing a secret key fails closed.
  - **Verify:** `python3 scripts/eval_plan6_vps_harness.py --help`; `python3 scripts/eval_plan6_vps_harness.py --dry-run`; corpus covers every class listed above; `test -x scripts/ask_chat.sh`.
  - **Depends on:** P0.2
  - **Evidence:** `--help` ok; `--dry-run` ok=true, 13 classes including 8 paraphrases (Arm D) and 12 Arm A rows; `--env-capture-json` with `splunk_token` exits 1; `scripts/ask_chat.sh` executable. No live `/chat` in A2.

- [x] **A3** — Shadow/replay schedule compare (execute once)
  - **Do:** Smallest safe mechanism: compute **both** the current production schedule and the Plan 5 merged schedule as **pure functions**; execute **only** the production schedule. Record a redacted diff (hooks, inserted phases, capability satisfaction, downgrade reason). Reuse `scripts/eval_phase_merge_probe.py` / `merge_schedule` — do not dual-call `evaluate_mcp_execution` / `call_tool`. **No new env flag.** If runtime compare cannot be proven side-effect-free, ship offline-only compare and sequential Arm C. Surface: LOCAL.
  - **Failing-first:** NEW `backend/app/tests/test_plan6_schedule_shadow_compare.py` asserts the helper never imports/calls MCP execution; AST or grep guard.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_plan6_schedule_shadow_compare.py app/tests/test_phase_merge_activation.py -q`.
  - **Depends on:** A1, P0.1
  - **Evidence:** Offline-only helper wraps `scripts/eval_phase_merge_probe.run_probes` (`execute_mcp=False`); AST/grep guard forbids MCP imports/calls. Direct `ResourcePlan()` in the helper failed `test_resource_plan_direct_construction_classified` on A-GATE attempt 1 — helper now constructs nothing. pytest shadow+merge+authority 19 passed. Runtime compare not proven side-effect-free → offline-only as plan allows.

- [x] **A-GATE** — Phase A local full gates
  - **Do:** Forecast-rule set at repo default (execution/T4 still false). Revert only the six stale reports. Surface: LOCAL. **Does not wait for A4.**
  - **Verify:** `./scripts/run_stage3_governance_regression.sh` PASS; `python3 scripts/freeze_execution_baseline.py --check`; `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_debug_summary.py app/tests/test_phase_merge_activation.py app/tests/test_semantic_t4_understanding.py app/tests/test_plan6_schedule_shadow_compare.py -q`; `git status --porcelain` shows no accidental stale-report commits under `docs/evals/`.
  - **Depends on:** A3
  - **Evidence:** Attempt 1 FAILED (`test_resource_plan_direct_construction_classified` on A3 helper). Attempt 2 PASS (`stage3_governance_regression: PASS`, dual_parity 120 exact, Cisco 50/0/0). freeze `--check` 15/15. targeted pytest 34 passed. Six stale reports reverted; porcelain `docs/evals/` is only `?? docs/evals/plan6/`. Repo defaults still false at config.py 403/410/413/417.

- [x] **A4** — Arm A observability smoke on VPS
  - **Do:** Run harness on Arm A (current VPS flags). Fill live flag values into `flag_matrix.md`. Confirm `/debug` bundle `explainability.debug_summary` shows A0/A1 fields. One query per major lane: T1, T3, T4, clarification. Restart not required if flags unchanged. Surface: VPS.
  - **Failing-first:** missing `qualification_tier` on bundle fails the smoke.
  - **Verify:** committed `docs/evals/plan6/runs/arm_a_smoke.md` with SHA, flags (no secrets), trace_ids, and field-presence list.
  - **Depends on:** A0, A1, A2
  - **Evidence:** Harness `--arm A` 12/12 exit 0, `missing_qualification_tier=[]`. Live flags: exec/T4/capability unset→false, v2 true, MCP mock. All bundles have `qualification_tier` + `schedule`. File written at `docs/evals/plan6/runs/arm_a_smoke.md` (not committed; user said do not commit). Corpus t1 knowledge row resolved T2; T1 seen on `p6.live_posture.d1_003`.

### B — ResourcePlan / PhaseContract OFF vs ON (VPS serial)

- [x] **B0** — Arm B: exec ON + v2 ON
  - **Do:** VPS env: `AI_SOC_RESOURCE_PLAN_EXECUTION_ENABLED=true`, leave dispatch-v2 ON, T4 OFF. `docker compose restart backend`. Run corpus (not the 8 paraphrases). Expect `degrade_reason=dispatch_v2_projected_schedule` on composed turns that project. If merge runs while a v2 projected schedule is present, **STOP** (ladder broken). Surface: VPS.
  - **Failing-first:** merge-while-v2-projects is a regression, not a success.
  - **Verify:** `docs/evals/plan6/runs/arm_b_v2_wins.md`; `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_phase_merge_activation.py -q`.
  - **Depends on:** A-GATE, A4
  - **Evidence:** exec true after `--force-recreate` (plain `restart` did not load a newly appended `.env` key). 7 composed rows `degrade_reason=dispatch_v2_projected_schedule`; 0 merge. pytest 9 passed. Not Plan-5 merge activation. File `arm_b_v2_wins.md` written, not committed.

- [x] **B1** — Arm C: exec ON + v2 OFF, then restore Arm A
  - **Do:** From B0 env, set dispatch-v2 **OFF**, keep exec ON. Restart backend. Run the same corpus. Classify each row: seam / rag_only / workflow_spl / guided / refine / non-planned. Rows that never hit the seam must be labelled `merge_not_reachable`, not “activation equivalent.” **Then restore Arm A flags** (exec OFF, v2 ON, T4 OFF) and restart. Surface: VPS.
  - **Why:** Without v2 OFF, Plan 6 cannot answer success question 1. Restore is required so D0 does not confound T4 with execution.
  - **Verify:** `docs/evals/plan6/runs/arm_c_merge.md` includes path classification + PhaseContract vs executed hooks; `flag_matrix.md` records restored Arm A.
  - **Depends on:** B0
  - **Evidence:** Arm C `20260813T125517Z` 12/12. Merge on 5 rows; 7 `merge_not_reachable` (3 rag_only, 2 non-planned, 2 `no_schedulable_step`). `p6.spl.mcp` PhaseContract includes `mitre_finalize` not in dispatch_schedule. Restored exec=false v2=true T4 unset; health_ok. `arm_c_merge.md` + flag_matrix updated. Not committed.

- [x] **D0** — Current-config T4 serving benchmark on VPS
  - **Do:** On restored Arm A, enable T4 in VPS env only (timeout stays 2.0s). Restart backend. Measure cold/warm latency, p50/p95, concurrency 1 and a small realistic N, timeout rate, empty-output rate, `llm_model_slot_busy` rate, accepted-contract rate, overall `/chat` latency impact. Use existing local primary endpoint only (`semantic_t4_understanding.py` `resolve_local_primary_endpoint`). Follow `.claude/skills/llm-live-probe/SKILL.md`. Then restore T4 OFF. Artifact: `docs/evals/plan6/t4_serving_baseline.md` + JSON. Surface: VPS.
  - **Why:** Plan 5 D0 was 8/8 invoked, 0/8 accepted (6 timeout @ 2.0s, 2 empty/slot-busy).
  - **Failing-first:** if the hop is not invoked on the 8 paraphrases, the serving experiment is invalid.
  - **Verify:** JSON includes all metrics above; T1–T3 corpus rows show **zero** T4 invocations; `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_semantic_t4_understanding.py -q`.
  - **Depends on:** A4, B1
  - **Evidence:** 8/8 paraphrases + guided T4 invoked; 0 accepted; 9/9 serial timed_out ~2000ms. T1–T3 invocations 0/3. N=2: 1 timeout + 1 `llm_model_slot_busy`. pytest 14 passed. T4 restored false. `t4_serving_baseline.md` + JSON. Not committed.

- [x] **D1** — Compare 2–3 in-environment serving options
  - **Do:** Compare only options already available (local primary vs already-configured Foundation-Sec/Qwen; slot count 1 vs small N). Do not raise timeout as the first experiment; a bounded timeout trial is allowed only if D0 shows p95 just above 2.0s. No new vendor. No new env flag unless D3 later approves a timeout/SLO change. T4 still cannot select skill, execute SPL/MCP, drop clarification, grant execution, or widen capabilities. Restore Arm A when finished. Surface: VPS.
  - **Failing-first:** any option that widens capabilities or sets a skill fails closed (`test_semantic_t4_understanding.py`).
  - **Verify:** `docs/evals/plan6/t4_serving_options.md` with the same metrics as D0 per option; `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_semantic_t4_understanding.py -q`.
  - **Depends on:** D0
  - **Evidence:** All four in-env options non-viable at 2.0s. A: D0 9/9 hop timeout + D1 2s replica 2022/2004 ms timeout; off-path 90s 8/8 paraphrases timeout; clean 180s still timeout. B/C not configured (local IS Foundation-Sec; Qwen unset). D N=2 worse (D0 1/2 llm_model_slot_busy; direct 2/2 timeout). 0 accepted, 0 widening. Production timeout unchanged. pytest 14 passed. T4 stayed false. `t4_serving_options.md` + JSON. Not D3.

- [x] **D2** — Semantic accuracy on 8 paraphrases + false-widening
  - **Do:** For each serving option that produces accepted contracts: score the 8 residual paraphrases; run a small set of genuinely ambiguous T4 cases and assert no false widening / no dropped clarification. Measure `/chat` end-to-end latency. Use `scripts/eval_residual_routing_after_architecture.py` for L3–L5, not frozen `--arm both` as the T4 observer. Surface: VPS + LOCAL residual probe.
  - **Verify:** `docs/evals/plan6/t4_paraphrase_accuracy.md`; residual probe JSON; zero capability-widening events.
  - **Depends on:** D1
  - **Evidence:** No option produced accepted contracts (D1). 0/8 parsed, 0/8 accepted, 0 widening, 0 dropped clarification. L3–L4 residual probe 25 rows (`t4_residual_routing_l3l4.json`): eight residue still L4 `knowledge_recall`/`clarification_required` unchanged. L5 = D0 VPS `/chat` same route; p50 38784 ms / p95 42320 ms. `t4_paraphrase_accuracy.md` + JSON. Not D3.

- [x] **B2** — A/B/C comparison report
  - **Do:** Write `docs/evals/plan6/execution_off_on_comparison.md`: route, contract, plan, schedule, executed phases, answer, grounding, safety, HIL, `execution_eligible`, latency, errors/fallbacks, duplicate work, extra LLM hops, missed/duplicate lifecycle phases, residual second-engine use. Surface: LOCAL.
  - **Failing-first:** any safety delta (`execution_eligible` true, HIL dropped, capability widened) blocks C0 presentation.
  - **Verify:** every corpus row appears; every Arm A/B/C cell filled or explicitly `n/a` with reason; no secrets.
  - **Depends on:** B0, B1
  - **Evidence:** `execution_off_on_comparison.md` + JSON from stored traces (36/36 bundles). Route/fingerprint/answer_mode stable. Safety: execution_enabled false, execution_eligible never true, HIL not dropped, caps unchanged, MCP never executed. C merge 5/12; B v2_wins 7/12; C not-reachable 7/12 not counted as failures. Paraphrase rows n/a (Arm D). Latency n/a (A/B/C harness lacked wall_ms). Llama ping 12.85s idle; Arm A flags confirmed. No secrets.

- [x] **B-GATE** — Phase B local gates (no default change)
  - **Do:** Confirm `ai_soc_resource_plan_execution_enabled` still defaults false. Re-run targeted merge/seam tests + frozen truth-set `--check`. Do not change production defaults. Surface: LOCAL.
  - **Verify:** grep default false in `backend/app/config.py`; `PYTHONPATH=backend:. python3 scripts/eval_routing_truth_set.py --arm both --check --baseline docs/evals/routing_truth_set_baseline_v1.json`; `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_phase_merge_activation.py app/tests/test_execution_seam_coverage.py -q`.
  - **Depends on:** B2
  - **Evidence:** `config.py:410` still `ai_soc_resource_plan_execution_enabled: bool = False`. Truth-set `--arm both --check` PASS (64/76, 0 regressions). pytest merge+seam **23 passed**. T4 default still false / 2.0. No production default change. Combined C0+D3 presented; not decided.

### C / D3 — activation STOPs (combined handoff)

- [x] **C0** — `P6_RESOURCE_PLAN_EXECUTION_ACTIVATION` **STOP**
  - **Do:** Present B2 evidence. Record **two** fields: (1) exec posture KEEP OFF / **VPS PERSISTENT ON** (repo `config.py` stays false) / DEFAULT ON WITH FALLBACK / DEFAULT ON + begin fallback retirement; (2) if exec is any ON, dispatch-v2 precedence `V2_WINS` / `V2_OFF_ON_VPS` / `CHANGE_LADDER`. `V2_WINS` must be labelled “not Plan-5 merge activation.” Do not treat test-arm success as go-live. If D2 is also done, present D3 in the same handoff. Surface: DECISION.
  - **Verify:** both fields recorded under Approved decisions; flags still independently controllable; `config.py` execution default unchanged until C1 (and C1 may still leave it false).
  - **Depends on:** B-GATE
  - **STOP:** `P6_RESOURCE_PLAN_EXECUTION_ACTIVATION`
  - **Evidence:** User recorded Field 1 **KEEP OFF** (Arm C merge 5/12 is success; production authority not yet safe — v2-OFF drops `spl_postprocessor` on two `workflow_spl`/`no_schedulable_step` rows; `V2_WINS` is not Plan-5 activation; no repo-default change; CHANGE_LADDER not selected). Field 2 **N/A** (exec remains OFF); keep dispatch-v2 ON in current VPS/COE posture. Future activation needs missed-work coverage or an approved CHANGE_LADDER/seam change — not implemented here. `config.py:410` still `= False`. Five Plan-5 flags remain independent Settings fields. Artifact `docs/evals/plan6/c0_d3_stop_decisions.md`.

- [x] **D3** — `P6_T4_SERVING_POSTURE` **STOP**
  - **Do:** Present D0–D2. T4 is activated **only if this gate passes**. Options: keep 2s/default-OFF (omit T4 from persistent profile) / VPS PERSISTENT ON with recorded timeout/serving / change timeout/SLO / enable more broadly / keep deferred. Do not pre-approve repo default ON. Independent of C0. Surface: DECISION.
  - **Verify:** decision recorded; `ai_soc_t4_semantic_understanding_enabled` default unchanged until D4 (D4 may still leave it false).
  - **Depends on:** D2
  - **STOP:** `P6_T4_SERVING_POSTURE`
  - **Evidence:** User recorded **KEEP 2.0s / DEFAULT-OFF**; omit T4 from persistent profile. `D1_PARAPHRASE_RESIDUE = DEFERRED_T4_SEMANTIC_SERVING_LIMIT`. D0 9/9 timeout ~2s, 0 accepted, 0 widening; D1 90s/180s still no required JSON; N=2 worsens slot pressure; no keyword heuristics. Live capability enforcement stays OFF. `config.py:413` still `= False`, `:414` still `2.0`. Artifact `docs/evals/plan6/c0_d3_stop_decisions.md`.

- [x] **C1** — Apply approved execution posture (not go-live)
  - **Do:** Write `docs/evals/plan6/production_flag_profile.md` from C0+D3 (D3 may still be open — exec fields only until D4). Apply **only** the approved option. VPS PERSISTENT ON: document profile flags including v2 precedence; **do not** flip `config.py` unless DEFAULT ON was chosen. KEEP OFF: pin tests that default remains false. DEFAULT ON: change default **and keep the flag**. `CHANGE_LADDER` is a code change — implement only if C0 selected it; otherwise do not. Live capability enforcement stays false. This is not F2 persistence and not F5 go-live. Surface: LOCAL.
  - **Failing-first:** if claiming Plan-5 merge activation, a test must fail when v2 still wins (`dispatch_v2_projected_schedule` on a composed turn).
  - **Verify:** profile artifact lists exec, v2, T4 (or T4 pending), live-capability=false; `grep` `config.py` matches the C0 default decision; `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_phase_merge_activation.py -q`; forecast-rule set only if `config.py` or ladder changed.
  - **Depends on:** C0
  - **Evidence:** Profile `docs/evals/plan6/production_flag_profile.md` lists exec KEEP OFF, v2 N/A/keep COE ON, T4 omit/OFF + 2.0s, live-capability=false. `config.py` still false at 403/410/413/417; timeout 2.0 at 414. No `config.py` or CHANGE_LADDER edit (forecast-rule n/a). pytest `test_phase_merge_activation.py` + `test_plan6_c0_keep_off.py` → 15 passed (v2 still wins when exec ON; COE profile has no exec/T4 `=true`). Not F2/F5.

- [x] **D4** — Apply approved T4 posture (not go-live)
  - **Do:** Only if D3 passed an ON option. Keep enable and timeout flags independent. T1–T3 must still never invoke the hop. Update `production_flag_profile.md` T4 fields. If D3 kept T4 deferred/OFF, pin default false and skip VPS T4 persistence. Do not flip `config.py` unless D3 chose DEFAULT ON. Surface: LOCAL.
  - **Failing-first:** existing `test_semantic_t4_understanding.py` T1–T3 tests must remain failing-if-invoked.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_semantic_t4_understanding.py -q`; if default/timeout changed, full forecast-rule set + residual probe.
  - **Depends on:** D3
  - **Evidence:** D3 KEEP OFF → skipped VPS T4 persistence; `config.py:413` false, `:414` 2.0 unchanged (forecast-rule n/a). Profile omits T4 from persistent VPS profile; `D1_PARAPHRASE_RESIDUE = DEFERRED_T4_SEMANTIC_SERVING_LIMIT`. pytest `test_semantic_t4_understanding.py` + `test_plan6_d3_t4_deferred.py` → 17 passed (T1–T3 never-invoke pins intact).

- [x] **C2** — Seam/fallback equivalence proof
  - **Do:** For any adoption/retirement candidate, prove behavioral equivalence on: mandatory phases, SPL validation, MCP gate, HIL, RBAC, MITRE/CVE finalization, reference finalization, failure handling, refinement, telemetry/provenance. Write `docs/evals/plan6/seam_equivalence.md` (do not overwrite Plan 5 `c2_phase_merge_probe.json`). If C0 was KEEP OFF, refresh the reachability map; do not retire anything. Surface: LOCAL.
  - **Failing-first:** `test_fallback_lifecycle_equivalence.py` still fails if `spl_postprocessor` is claimed present on the legacy branch.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_fallback_lifecycle_equivalence.py app/tests/test_execution_seam_coverage.py -q`; proof committed.
  - **Depends on:** C0
  - **Evidence:** C0 KEEP OFF → map refreshed (`execution_path_map.md` Arm C 5 merge / 7 not-reachable / two `workflow_spl` rows drop `spl_postprocessor`). Nothing retired. Inventory still 2 SEAM / 4 DECISION_REQUIRED / 4 KEEP_SEPARATE, 0 adopted. Proof `docs/evals/plan6/seam_equivalence.md` (does not claim `spl_postprocessor` on legacy). pytest fallback+seam → **19 passed**. Proof written; not git-committed (same as prior Plan 6 items unless asked).

- [x] **C3** — `P6_EXECUTION_SEAM_ADOPTION` **STOP**
  - **Do:** Present C2. No seam adoption and no fallback retirement without measured proof **and** approval. If not approved, inventory stays 2 SEAM / 4 DECISION_REQUIRED / 4 KEEP_SEPARATE, 0 adopted. Surface: DECISION.
  - **Verify:** decision recorded; if no adoption, pins still green; if adoption, forecast-rule set + VPS corpus.
  - **Depends on:** C2
  - **STOP:** `P6_EXECUTION_SEAM_ADOPTION`
  - **Evidence:** User recorded **KEEP 0 ADOPTED** (2 SEAM / 4 DECISION_REQUIRED / 4 KEEP_SEPARATE / 0 adopted). Fallback not retired; no DECISION_REQUIRED seam adopted; CHANGE_LADDER not implemented. Deferred follow-up, not a Plan 6 production blocker (C0 KEEP OFF + v2 ON). Artifact `docs/evals/plan6/c3_stop_decision.md`. pytest `test_fallback_lifecycle_equivalence.py` + `test_execution_seam_coverage.py` + `test_plan6_c3_keep_zero_adopted.py` → **22 passed**.

### E — governance / execution cleanup (after C0)

- [x] **E0** — MITRE/CVE schedule vs actual execution
  - **Do:** Measure declared PhaseContract `inline_mandatory` vs what `graph_node_context_finalize` actually ran. **Default implementation:** keep `pipeline_inline` ownership and make provenance accurate (A1 debug fields + PhaseContract `inline_mandatory`). Do **not** duplicate execution into the hook loop. If measurement shows hook-loop execution is required, **STOP and ask** — do not self-select. Surface: LOCAL.
  - **Failing-first:** NEW test that provenance lists `mitre_finalize`/`cve_adapter` when those functions ran, and does not list them when they did not.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_phase_registry.py app/tests/test_phase_contract.py -q` plus the new provenance test.
  - **Depends on:** C0, A1
  - **Evidence:** Kept `pipeline_inline` ownership; did not add `mitre_finalize`/`cve_adapter` to `_HOOK_BY_NAME` or fallback `hook_nodes`. Provenance: `pipeline_inline_executed` on `ChatPipelineState` + `plan_dispatch.inline_executed`; `debug_summary.schedule` now surfaces `inline_mandatory` (PhaseContract) and `inline_executed` (what actually ran). RP `.invoke()` playbook query: `inline_executed=['mitre_finalize']`, CVE omitted. pytest `app/tests/test_phase_registry.py app/tests/test_phase_contract.py app/tests/test_plan6_e0_inline_provenance.py -q` → **32 passed**. Hook-loop execution not required.

- [x] **E1** — 11-row MITRE promotion analyst-visible measurement (no promote)
  - **Do:** Dry-run / offline measure exact analyst-visible delta if DRAFT candidates were promoted for `q0.q021/028/040` (T1071), `q0.q046/047/060/062/089` (T1110), `q0.q050/063/083` (T1059.001). Do **not** run the promoter against committed artifacts. Do **not** edit `docs/input/mitre_enrichment/unpromoted_draft_drift_v1.json` to silence drift. Surface: LOCAL.
  - **Verify:** `docs/evals/plan6/mitre_11row_promotion_delta.md`; `cd /var/www/ai-soc-assistant && python3 -m pytest tools/coverage_authoring/tests/test_question_runtime_map_draft_drift.py tools/coverage_authoring/tests/test_question_runtime_map_mitre_containment.py -q`; `python3 scripts/freeze_execution_baseline.py --check` still 15/15 (runtime map + catalog unchanged).
  - **Depends on:** C0
  - **Evidence:** Promoter not run; ledger not edited; runtime map + catalog + ledger hashes unchanged. Artifact `docs/evals/plan6/mitre_11row_promotion_delta.md`. In-memory patch blast radius: exactly the 11 question rows, plus 4 catalog use cases if the existing CLI were used. Group 1 (`q021/028/040`): new `T1071` metadata-only candidate, live `answer_visible` stays false. Group 2 (8 rows): already-visible technique list widens (`T1110.001`+`T1110` or `T1059`+`T1059.001`). pytest draft-drift + containment → **19 passed**. `freeze_execution_baseline.py --check` → **protected artifacts unchanged (15 checked)**.

- [x] **E2** — `P6_MITRE_DRAFT_PROMOTION` **STOP**
  - **Do:** Present E1. Promote only with explicit approval + protected-manifest recapture. Otherwise keep `DEFERRED_SEPARATE_GOVERNED_PROMOTION`. Surface: DECISION.
  - **Verify:** decision recorded; if not promoted, drift ledger still matches; if promoted, `python3 scripts/freeze_execution_baseline.py --capture` for `question_runtime_map_v1.json` and `use_cases/catalog.json` then `--check`.
  - **Depends on:** E1
  - **STOP:** `P6_MITRE_DRAFT_PROMOTION`
  - **Evidence:** User recorded **KEEP DEFERRED**; retain `DEFERRED_SEPARATE_GOVERNED_PROMOTION`. Promoter not run; ledger/runtime map/catalog not modified; manifest not recaptured. Artifact `docs/evals/plan6/e2_stop_decision.md`. pytest `test_question_runtime_map_draft_drift.py` → **5 passed**. `freeze_execution_baseline.py --check` → **protected artifacts unchanged (15 checked)**. Hashes unchanged from E1.

- [x] **E3** — Stale reports inventory + `P6_STALE_REPORT_DISPOSITION` **STOP**
  - **Do:** Inventory the six reports Plan 5 left stale. Options: refresh as a declared new baseline; replace with generated/non-committed reports; move out of source control; continue preserving. **Do not simply regenerate and commit.** Surface: DECISION.
  - **Verify:** decision recorded; `docs/evals/ARTIFACT_REFRESH_POLICY.md` updated only if disposition changes.
  - **Depends on:** C0
  - **STOP:** `P6_STALE_REPORT_DISPOSITION`
  - **Evidence:** User recorded **CONTINUE PRESERVING**. Six reports stay tracked; policy file **unchanged** (`git diff -- docs/evals/ARTIFACT_REFRESH_POLICY.md` empty of Plan 6 edits). No regen, gitignore, harness-path, or lifecycle redesign. Artifact `docs/evals/plan6/e3_stop_decision.md`. After governance, revert only those six files.

- [x] **E4** — Protected-artifact review for new Plan 6 artifacts
  - **Do:** Keep fail-closed `15/15` semantics. Any new **runtime-authoritative generated** artifact introduced in Plan 6 is considered for `PROTECTED` explicitly. Eval reports under `docs/evals/plan6/` are evidence, not automatically protected. Surface: LOCAL.
  - **Failing-first:** `python3 scripts/freeze_execution_baseline.py --check` fails if a declared member is missing.
  - **Verify:** `python3 scripts/freeze_execution_baseline.py --check`; list any added members in the Plan 6 report.
  - **Depends on:** E2, E3, P0.1
  - **Evidence:** **0 members added.** Plan 6 `docs/evals/plan6/` reports/corpus/schema stay evidence-only. Artifact `docs/evals/plan6/e4_protected_artifact_review.md`. `freeze_execution_baseline.py --check` → **15 checked**. Durability pytest → **5 passed** (missing declared member still fails closed). Runtime map + catalog unchanged.

### F — integrated VPS readiness → persistent go-live

- [x] **F0** — Full corpus on the approved flag matrix
  - **Do:** Re-run the corpus (plus 8 paraphrases if T4 enabled) on the post-C1/D4 **intended** profile (may still be a session env, not yet F2-persisted). Capture env. Compare to Arm A. Mock MCP is acceptable here. Do **not** declare production-ready. Surface: VPS.
  - **Verify:** `docs/evals/plan6/runs/integrated_vps.md`; no secrets; success questions 1–7 each cite an artifact; degrade_reason matches C0 v2 precedence (if `V2_OFF_ON_VPS` / `CHANGE_LADDER`, composed turns must not show `dispatch_v2_projected_schedule` as the winner unless labelled not-activation).
  - **Depends on:** C1, D4
  - **Evidence:** Harness `--arm F` exit 0, 12/12, no missing qualification_tier. Run `docs/evals/plan6/runs/20260813T183145Z/`. Routes/fingerprints/tiers match Arm A. `degrade_reason=null` all 12 (exec OFF; not v2-wins, not merge). T4 paraphrases omitted. Artifact `runs/integrated_vps.md`. Not production-ready.

- [x] **F1** — VPS safety invariants
  - **Do:** On F0 traces assert: no LLM→MCP, candidate SPL not executed, `execution_eligible=false` unless a separately approved live-MCP arm, HIL/RBAC present when owed, T4 did not set a skill or widen caps, no duplicate side-effecting steps, live capability enforcement still OFF. Surface: LOCAL review of VPS traces.
  - **Verify:** `docs/evals/plan6/vps_safety_invariants.md` all pass; `/invariant-check` on the Plan 6 diff.
  - **Depends on:** F0
  - **Evidence:** All seven invariants PASS on F0 `/debug` bundles. `execution_eligible` None; MCP never allowed; `execution_enabled=false`. Artifact `docs/evals/plan6/vps_safety_invariants.md`. Invariant check 7/7 PASS on Plan 6 runtime diff.

- [x] **F-GATE** — Phase F local gates (code defaults vs profile)
  - **Do:** If C1 or D4 changed a `config.py` default or adopted a seam: run the complete forecast-rule set. Else: grep repo defaults still false unless a gate approved otherwise; targeted tests + residual probe. Revert only the six stale reports. Confirm `production_flag_profile.md` exists and distinguishes repo default vs VPS profile. Surface: LOCAL.
  - **Verify:** commands in “Forecast-rule gate set” if defaults moved; else grep + `python3 scripts/freeze_execution_baseline.py --check`; profile artifact present.
  - **Depends on:** F1
  - **Evidence:** C1/D4 did not change `config.py` defaults or adopt a seam — skipped forecast-rule set. grep `config.py` 403/410/413/417 still false. freeze `--check` **15/15**. `production_flag_profile.md` present (repo default vs VPS). Six stale reports clean vs HEAD (not regenerated).

- [x] **F2** — Persist the approved production flag profile on the VPS
  - **Do:** Write the C0+D3 profile into the **persistent** VPS config (`env/profiles/coe.env.example` and/or operator `.env` via `scripts/select_env_profile.sh` — booleans only in git; secrets stay in uncommitted `.env`). Include exec, v2 precedence, T4 (or explicit OFF), live-capability=false. Recreate/restart backend. Capture **effective** flags after restart (P0.2 schema). Prove the intended execution authority (`degrade_reason` vs C0 v2 decision) is still active. Rerun representative smoke/corpus. Test-arm shell exports are not persistence. Surface: VPS.
  - **Why:** Production readiness is a persistent environment, not a successful one-shot arm.
  - **Failing-first:** after recreate, if `AI_SOC_RESOURCE_PLAN_EXECUTION_ENABLED` (and T4 if approved) do not match `production_flag_profile.md`, F2 fails.
  - **Verify:** `docs/evals/plan6/runs/f2_persistence.md` with pre/post-recreate flag booleans (no secrets); representative smoke recorded; `debug_summary.degrade_reason` still matches C0 v2 decision; `config.py` defaults unchanged unless C0/D3 chose DEFAULT ON.
  - **Depends on:** F-GATE, C1, D4
  - **Evidence:** Recreate `docker compose up -d --force-recreate backend`; health 200. Post-recreate docker: exec `false`, T4 `false`, live-cap `false` (was unset), v2 `true`. T4 omitted from git profiles. 4-row smoke `runs/20260813T190118Z/` exit 0; routes/fingerprints match Arm A; `degrade_reason=null`; `semantic_t4=null`. `config.py` defaults still false. Artifact `runs/f2_persistence.md`.

- [x] **F3** — Reliability, capacity, failure behaviour, and live Splunk/MCP honesty
  - **Do:** On the **persisted** profile, F3 is **not** a smoke test. Record each of: (1) restart/recreate + representative corpus smoke; (2) concurrent `/chat` (N matching T4 slot reality if T4 ON) and repeated identical requests; (3) latency vs Arm A (p50/p95, extra LLM hops); (4) **failure behaviour** — LLM timeout/unavailable, malformed LLM output, DB failure/recovery, MCP/Splunk unavailable or timeout, model-slot pressure; assert no duplicate side effects and safe bounded fallback/degradation (no fabricated live rows, no execution_eligible flip, HIL/RBAC still owed); (5) **controlled live Splunk/MCP read-only test** if credentials exist: `/chat` → generated SPL → deterministic validation → HIL/RBAC/MCP gate → real Splunk read-only query → evidence → grounded answer. Allowlisted tool only; no write/admin tools; fail closed on unapproved SPL. If credentials/network absent: record `live_mcp_unproven` and do **not** replace missing live evidence with mocks. Mock-only architecture success may proceed to F4/F5 with that honest label. Surface: VPS.
  - **Failing-first:** any write/admin MCP tool invocation, live rows claimed from mock, or a missing failure-class row in `f3_reliability.md`, fails the item. Do not weaken these tests to get a PASS.
  - **Verify:** `docs/evals/plan6/runs/f3_reliability.md` lists every failure class above with observed outcome; `docs/evals/plan6/runs/f3_live_mcp.md` (or `live_mcp_unproven` with reason); no secrets; HIL present on the live search if it ran; no duplicate side-effecting steps on repeated requests.
  - **Depends on:** F2
  - **Evidence:** Ran **on the persisted F2 profile**; injections transient and external (`systemctl stop llama-server`, stub on host `:8081`) — no env key edited. (1) Force-recreate → health 200; 12-row corpus `runs/20260814T031208Z/` exit 0, **0 route/tier/fingerprint drift vs Arm A**, `degrade_reason`/`semantic_t4` null on all 12. (2) Latency post-recreate p50 **92,931 ms** / p95 **182,120 ms** vs pre-recreate F0 p50 92,587 / p95 182,638 (Δp50 +0.4 %); Arm A run predates `wall_ms`, stated honestly. (3) Failure classes all recorded: LLM unavailable **1,072 ms** fail-closed; malformed LLM output **1,822 ms** fail-closed; LLM timeout **181,754 ms** bounded, HTTP 200 deterministic fallback, no hang; model-slot pressure ×3 (2,699/2,693/62,548 ms) + HIL short path ×3; DB failure → auth 401 fail-closed, `ready=true` after restart. Every class: `execution_eligible=null`, `execution_enabled=false`, HIL raised when owed, no fabricated live rows. (4) No duplicate side effects — `ai_trace_runs` **21/21** distinct, **0** executed MCP events, `canonical_execution_idempotency` **0** rows. (5) Live Splunk/MCP **not run** — `SPLUNK_MCP_BASE_URL`/`TOKEN` empty ⇒ **`live_mcp_unproven`**, mock not substituted; fail-closed coverage `47 passed`. Recovery smoke `runs/20260814T045547Z/` 2/2 exit 0, fingerprints identical to Arm A. Final health `ok` / `ready=true` / `write_failures=0`, `llama-server` active. Artifacts `runs/f3_reliability.md`, `runs/f3_live_mcp.md`, `runs/f3/*.json`.

- [x] **F4** — Rollback test
  - **Do:** Revert VPS persistent profile to Arm A (exec OFF, T4 OFF, v2 restored to pre-F2 COE value). Restart. Smoke corpus matches Arm A (route, no unexpected merge, T4 not invoked on T1–T3). Document the rollback runbook in `docs/evals/plan6/rollback_runbook.md`. Then **re-apply** the approved F2 profile and restart so F5 decides on the intended production state, not the rolled-back state. Surface: VPS.
  - **Failing-first:** if Arm A smoke after rollback still shows merge-authoritative or T4 invocations on T1–T3, rollback failed.
  - **Verify:** runbook committed; rollback smoke + re-apply smoke both recorded; no secrets.
  - **Depends on:** F3
  - **Evidence:** Executed, not simulated. **Finding:** compose loads `env/profiles/${AI_SOC_ENV_PROFILE:-coe}.env.example` **then** `.env`, and this host sets `AI_SOC_ENV_PROFILE=development` (`.env:7`) — so the profile in effect is `development.env.example`, not `coe`. A `.env`-only rollback did **not** reach Arm A (two keys still resolved `false` from the profile); rollback had to touch the active profile too. Rollback: all three flags **unset**, v2 `true`, health `ok`/`ready=true`; smoke `runs/20260814T100338Z/` 3/3 exit 0 with route **and** `resource_plan_fingerprint` identical to Arm A (`54643926bb51081e`, `fd65002b17c46fa0`, `99ccd9213e2f0b37`), `degrade_reason` null, `semantic_t4` null, `phase_names` empty — failing-first satisfied (no merge authority, no T4 on T1–T3). Re-apply: profile restored via `git checkout`, `.env` restored from backup, force-recreate; effective flags `exec=false`, `T4=false`, `live-cap=false`, `v2=true`, `MCP_MODE=mock`; health `ok`, `write_failures=0`; smoke `runs/20260814T104455Z/` 3/3 exit 0, same fingerprints. **Host left in the approved production profile, not the rollback state**; `env/profiles/*.env.example` clean in git. Runbook `docs/evals/plan6/rollback_runbook.md`.

- [x] **F5** — `P6_PRODUCTION_GO_LIVE` **STOP**
  - **Do:** Do **not** auto-declare production ready. Present a final matrix covering at least: Functional; Safety; Performance; Reliability; Security/RBAC; Observability; Deployment/restart; Rollback; VPS corpus; Production flags persistence; Live MCP scope (`proven` vs `live_mcp_unproven`); Critical blockers. Also cite `production_flag_profile.md`, C0 v2 precedence, D3 T4 posture, F2 persist evidence, F3, F4 re-applied intended state. Outcomes: **GO LIVE with recorded profile** / **DEFER** / **ROLL BACK AND KEEP OFF**. `GO LIVE` requires **zero critical blockers**. Do not imply live Splunk is production-ready if F3 is `live_mcp_unproven`. Do not call `exec ON + v2 ON` Plan-5 activation if C0 was `V2_WINS`. Repo defaults may remain false. Surface: DECISION.
  - **Verify:** decision recorded under Approved decisions only after the user chooses; matrix present in the F5 handoff; profile, v2, T4, live-MCP honesty, rollback runbook, and critical-blocker count (must be 0 for GO LIVE) all cited; `config.py` matches the recorded default decision.
  - **Depends on:** F4
  - **STOP:** `P6_PRODUCTION_GO_LIVE`
  - **Evidence:** Matrix presented in `docs/evals/plan6/f5_go_live_decision_packet.md` across all required categories, citing `production_flag_profile.md`, C0 v2 precedence, D3 T4 posture, `runs/f2_persistence.md`, `runs/f3_reliability.md`, `runs/f3_live_mcp.md`, `rollback_runbook.md` and the F4 re-applied intended state. Critical blockers **0**; accepted risks **3** (shared-VPS latency, deferred MITRE promotion, mock-only MCP lane). Live MCP scope stated as **`live_mcp_unproven`**; ResourcePlan merge stated as experimentally proven but **not** production-authoritative; authority remains dispatch-v2 per C0 KEEP OFF; T4 deferred for want of a viable serving posture. Also disclosed: host runs `AI_SOC_ENV_PROFILE=development`, so the effective profile is `development.env.example`, not `coe`. **User recorded `DEFER`** — see Approved decisions § F5. `config.py` defaults unchanged (repo default decision honoured).

### G — report / docs / closure

- [x] **G0** — Plan 6 report
  - **Do:** Write `docs/evals/plan6_activation_and_t4_report.md` answering the twelve success questions with artifact citations. State the **persistent VPS/production flag profile** separately from repo defaults. Honest about KEEP OFF, `V2_WINS`, `live_mcp_unproven`, and deferred T4. Surface: LOCAL.
  - **Verify:** every number traces to `docs/evals/plan6/`; no claim that frozen `--arm both` observed L4/L5; parity 120 exact not cited as routing correctness.
  - **Depends on:** F5, E0, E2, E3, E4
  - **Evidence:** `docs/evals/plan6_activation_and_t4_report.md` answers all twelve success questions with artifact citations. Persistent VPS profile stated separately from repo `config.py` defaults (unchanged); env-profile correction (`AI_SOC_ENV_PROFILE=development`) recorded. Honest on KEEP OFF (Q4), `V2_WINS` never called activation (Q10), `live_mcp_unproven` (Q12), deferred T4 as a **serving** limit (Q6), and 0 seams adopted (Q5). Explicit non-claims section: frozen `--arm both` did not observe L4/L5; parity 120 exact is not routing correctness.

- [x] **G1** — Docs alignment
  - **Do:** Update `CLAUDE.md`, `docs/architecture/phase_contract_and_schedule.md`, routing authority map if needed, `plans/README.md` Active-work (Plan 6 status). Edit `AGENTS.md` only if an operating rule changed. Surface: LOCAL.
  - **Verify:** `.cursor/hooks/audit-plan-discipline.sh plans/2026-08-13_1440_production-activation-t4-serving-and-governance-readiness.md` → 0 gaps; doc claims grep-anchored.
  - **Depends on:** G0
  - **Evidence:** `plans/README.md` Active-work: Plan 6 **Done (37/37) — `F5 = DEFER`**, Plan 7 added as active. `CLAUDE.md`: Plan 6 + Plan 7 rows added; the misleading "COE host" flag claim corrected — compose loads `env/profiles/${AI_SOC_ENV_PROFILE:-coe}.env.example` then `.env`, and this host sets `AI_SOC_ENV_PROFILE=development`, so `development.env.example` is in effect. `docs/architecture/phase_contract_and_schedule.md`: E0 `inline_executed` provenance recorded next to `inline_mandatory`; Arm C measurement (merge 5/12, 7/12 not reachable, two rows lose `spl_postprocessor`) recorded as the KEEP-OFF reason and handed to Plan 7; COE warning rewritten with the profile-chain fact and the DEFER outcome. `routing_authority_map.md` needed no change (no routing authority moved). `AGENTS.md` untouched (no operating rule changed). Plan-discipline audit → **0 gaps**.

- [ ] **G2** — Final closure gates
  - **Do:** Re-run the complete forecast-rule set twice if any authority/default changed; otherwise once plus targeted re-audit of every checkmark. Confirm F5 `P6_PRODUCTION_GO_LIVE` is recorded (GO LIVE / DEFER / KEEP OFF) and that the PR does not claim live MCP or Plan-5 merge activation unless F3/C0 evidence supports it. Confirm no unrelated dirt committed. Update or mark ready the Plan 6 PR per **Commit / PR / merge**. Do **not** merge to `master` in this item. Surface: LOCAL.
  - **Verify:** governance PASS; pytest green vs P0 baseline; truth-set `--check` 0 regressions; parity `120 exact`; Cisco `50/0/0`; probes `10/10`; sentinel `17/17`; path `105/105`; manifest N/N; invariants 7/7; plan-discipline 0 gaps; F5 decision present in Approved decisions; re-walk every item’s Verify with skepticism; `gh pr view` shows the Plan 6 PR with STOP decisions recorded; merge SHA absent until the user asks to merge.
  - **Depends on:** G1
  - **Evidence:** _(fill when done)_

## Verification gaps

None — every item has a concrete Verify. Live VPS flag values are `UNKNOWN` until A4; that is an execution input, not a missing Verify.

`A-GATE` Verify names `app/tests/test_plan6_schedule_shadow_compare.py`, which is **NEW in A3**. If A3 falls back to offline-only without that file, update A-GATE Verify in the Drift log before running A-GATE.

## Drift log

- 2026-08-13 — Plan 6 authored from repo audit at `1d32ac6`. Ten brief-vs-code contradictions recorded above.
- 2026-08-13 — **Review / loop conversion.** Bugs found and fixed in this document (not in runtime code): (1) A-GATE no longer depends on VPS A4; (2) B0/B1/D0 serialized on one VPS — B1 depends on B0 and restores Arm A before D0; (3) observability must land on `debug_summary` because `_slim_control_plane_trace` drops unknown CP sections; (4) A0/A1 require TypedDict + RP graph `.invoke()`, not node-only tests; (5) no new env flags; (6) A3 is compute-both/execute-once, no MCP dual-call; (7) Arm B success is the recorded v2-wins degrade reason, not “flag is not a no-op”; (8) E0 defaults to provenance accuracy, not duplicated hook-loop execution; (9) A2 wraps `scripts/ask_chat.sh`; (10) C2 writes `seam_equivalence.md` so it does not collide with Plan 5 `c2_phase_merge_probe.json`; (11) VPS flag changes require `docker compose restart backend`; (12) C0+D3 presented together after B-GATE and D2.
- 2026-08-13 — **Commit / PR / merge** section added. One feature branch `feat/plan6-production-activation` from `1d32ac6`; phase-scoped commits; one PR (draft after A-GATE); merge commit not squash, user-only, blocked on open STOPs. C1 and D4 stay separate commits. G2 opens/updates the PR and does not merge.
- 2026-08-13 — **Go-live extension.** Plan does not stop at test-arm success. Added F2 persistence, F3 reliability/capacity + live Splunk honesty, F4 rollback, F5 `P6_PRODUCTION_GO_LIVE`. C0 now requires dispatch-v2 precedence (`V2_WINS` is not Plan-5 merge activation). Production profile may be persistently ON while `config.py` stays false. T4 only if D3 passes. Live capability enforcement stays OFF. Checklist 33 → 37.
- 2026-08-13 — **F3/F5 tightening (plan-only, not implemented).** F3 must cover LLM timeout/unavailable, malformed LLM output, DB failure/recovery, MCP/Splunk unavailable or timeout, concurrent `/chat`, repeated requests, model-slot pressure, no duplicate side effects, and bounded degrade — not smoke alone. Live path if credentials exist is `/chat` → SPL → validation → HIL/RBAC/MCP gate → real read-only Splunk → evidence → grounded answer. F5 handoff must include the full readiness matrix; `GO LIVE` requires zero critical blockers. Loop-asap was started then paused before any Plan 6 commit.
- 2026-08-13 — **C0 + D3 recorded.** Exec **KEEP OFF** (Field 2 N/A; keep COE dispatch-v2 ON). Arm C merge 5/12 is reachability proof, not production authority — v2-OFF missed `spl_postprocessor` on two `workflow_spl`/`no_schedulable_step` rows blocks `V2_OFF_ON_VPS`; `CHANGE_LADDER` not selected. T4 **KEEP 2.0s / DEFAULT-OFF**; omit from persistent profile; `D1_PARAPHRASE_RESIDUE = DEFERRED_T4_SEMANTIC_SERVING_LIMIT`. Live capability enforcement stays OFF.
- 2026-08-13 — **C3 recorded KEEP 0 ADOPTED.** No seam adoption, no fallback retirement, no CHANGE_LADDER. Deferred architectural follow-up; not a Plan 6 production blocker because C0 kept ResourcePlan execution OFF and dispatch-v2 ON.
