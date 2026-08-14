---
canonical_plan: plans/2026-08-14_1130_resource-plan-authority-and-t4-integration.md
supersedes_open_gaps_of: plans/2026-08-13_1440_production-activation-t4-serving-and-governance-readiness.md
baseline: Plan 5 merge SHA `3d22260`; Plan 6 evidence on branch `feat/plan6-production-activation` (PR #132, unmerged)
---

# Plan 7 — ResourcePlan/PhaseContract execution authority and T4 integration

Opened by Plan 6's recorded STOP **`P6_PRODUCTION_GO_LIVE = DEFER`**: the architecture was
proven **experimentally** but is not production-authoritative, and go-live must not be declared
while normal execution authority remains dispatch-v2.

**Done means:** `ResolvedQueryContract → ResourcePlan + PhaseContract → deterministic compiler
→ governed executable schedule` carries production authority with dispatch-v2 **OFF**, zero
missed mandatory work, T4 integrated **ON** with a serving posture that passes its own gate,
and a new production go-live decision recorded by the user.

## Intended end state

```
LANGGRAPH_ORCHESTRATION_ENABLED            = ON
AI_SOC_RESOURCE_PLAN_EXECUTION_ENABLED     = ON     (PhaseContract + compiler authoritative)
AI_SOC_PIPELINE_DISPATCH_V2_ENABLED        = OFF    (retired from normal authority)
AI_SOC_T4_SEMANTIC_UNDERSTANDING_ENABLED   = ON     (serving posture must pass its gate)
AI_SOC_T4_SEMANTIC_UNDERSTANDING_TIMEOUT_SECONDS = 2.0
AI_SOC_LIVE_CAPABILITY_ENFORCEMENT_ENABLED = OFF
```

Flags stay independently controllable for testing and rollback **after** activation. Repo
`config.py` defaults do **not** have to change to reach the production profile.

## Not the destination

- `ResourcePlan OFF + dispatch-v2 ON + T4 OFF` — Plan 6's safe baseline and rollback posture.
- `ResourcePlan ON + dispatch-v2 ON` — that is `V2_WINS`; it is **not** ResourcePlan activation
  and must never be reported as one.

## Locked decisions (do not reopen without contradictory measured evidence)

- Live capability enforcement stays **OFF** (Plan 5 B5 not reopened).
- No routing keyword heuristics — including for the eight T4 paraphrases.
- The rejected "one primary skill owns all capabilities" model is not resurrected; required
  capabilities are satisfied by the complete governed schedule.
- MITRE 11-row DRAFT promotion stays `DEFERRED_SEPARATE_GOVERNED_PROMOTION`.
- The six stale governance reports stay preserved; revert **only** those six after governance
  runs. Never `git checkout -- docs/evals/`.
- Plan 6 history is not rewritten. Its measurements were correct discovery work.
- Execution-authority / `CHANGE_LADDER` work is reopened **only** as far as measured evidence
  requires. This is not a licence for a broad redesign.
- T4 stays **ON** through the whole remediation phase. Turning it OFF to make results green is
  prohibited. The 2.0 s bound stays until Workstream C evidence justifies otherwise.

## STOPs (user decision required; do not self-approve)

- `P7_SPL_LIFECYCLE_OWNERSHIP` (A2) — before changing where `spl_postprocessor` is owned.
- `P7_DISPATCH_V2_RETIREMENT` (A6) — before making v2 OFF the normal authority.
- `P7_T4_SERVING_POSTURE_V2` (C3) — before changing serving config or the 2.0 s bound.
- `P7_PRODUCTION_GO_LIVE_V2` (E2) — the new go-live gate.

## Success questions (must be answered with evidence)

1. Why are `p6.multi.knowledge_spl_mcp` and `p6.live_posture.d1_003` `no_schedulable_step`?
2. Who *should* own `spl_postprocessor` — ResourcePlan step, PhaseContract lifecycle,
   compiler, execution seam, or a legacy behaviour needing migration?
3. What is the deterministic applicability condition under which it must execute?
4. How many rows share that structural condition — beyond the two examples?
5. With exec ON + v2 OFF + T4 ON: is mandatory work missed anywhere? Duplicated anywhere?
6. Can dispatch-v2 stay OFF as the normal authority?
7. Does any old path still execute where ResourcePlan + PhaseContract should own the job?
8. With T4 ON, what is the measured invoked/accepted/timeout/fallback profile?
9. Does a viable T4 serving posture exist, and what does it prove?
10. Does the target profile survive restart, reliability, persistence and rollback?
11. Which Plan 6 accepted risks close, and which persist?
12. Is live Splunk/MCP still `live_mcp_unproven`?

---

## P0 — environment authority (do this before trusting any flag)

- [x] **P0.1** — Identify the effective configuration chain
  - **Do:** Trace exactly what the running backend consumes: `docker-compose.yml` `env_file`
    order, the value of `AI_SOC_ENV_PROFILE`, which `env/profiles/*.env.example` that selects,
    and which keys `.env` overrides. Do **not** assume `coe.env.example`. Surface: LOCAL+VPS.
  - **Verify:** `docs/evals/plan7/env_authority_chain.md` names the exact files in precedence
    order with the observed `AI_SOC_ENV_PROFILE`; every target flag is traced to the file that
    supplies it.
  - **Depends on:** —
  - **Evidence:** `docs/evals/plan7/env_authority_chain.md`. Chain: compose `env_file` = `env/profiles/${AI_SOC_ENV_PROFILE:-coe}.env.example` **then** `.env` (later wins); `.env:7` and `env/active.profile` both say **`development`**, so `development.env.example` is selected — `coe.env.example`, `development.env`, `coe.env`, `production.env` are **not read**. Service-level `environment:` sets only `PYTHONPATH`, `AI_SOC_REPO_ROOT`, `AI_SOC_ENV_PROFILES_DIR` — **no target flag is overridden there** (`docker compose config`). Per-flag winning source traced: LangGraph/exec/v2/live-cap/`MCP_MODE` from `.env` with the profile agreeing; `AI_SOC_T4_SEMANTIC_UNDERSTANDING_ENABLED` from **`.env` only** (absent from the profile); `AI_SOC_T4_SEMANTIC_UNDERSTANDING_TIMEOUT_SECONDS` **unset in both files → `config.py:414` default 2.0**. Host recorded as `vps-development-profile`; **not** assumed COE. No flag changed.

- [x] **P0.2** — Capture current effective values
  - **Do:** `docker compose exec -T backend printenv` for the six target flags plus
    `MCP_MODE`, `LANGGRAPH_ORCHESTRATION_ENABLED`. Booleans/names only. Surface: VPS.
  - **Verify:** capture passes `app.evals.plan6_env_capture.validate_env_capture` (no
    secret-shaped keys); stored under `docs/evals/plan7/runs/<ts>/env_capture.json`.
  - **Depends on:** P0.1
  - **Evidence:** `docs/evals/plan7/runs/20260814T125151Z/env_capture.json`, produced with `eval_plan6_vps_harness.capture_env()` and **validated** by `app.evals.plan6_env_capture.validate_env_capture` (secret-shaped keys rejected). Pre-change effective: exec `false`, T4 `false`, T4 timeout `2.0` (**presence `unset`** — code default), live-cap `false`, v2 `true`, LangGraph `true`, `MCP_MODE=mock`; `db_reachable=true`, `mcp_connectivity=true`; `git_sha=dae51eb`. No secrets. Flags unchanged — this is the Plan 6 recorded production profile.

- [x] **P0.3** — Apply the remediation posture through the real configuration path
  - **Do:** Set exec **ON**, v2 **OFF**, T4 **ON** @ 2.0 s, live capability enforcement **OFF**,
    LangGraph **ON** via the file the backend actually consumes (P0.1). Do **not** switch the
    host to a different profile unless P0.1 proves it is required. `--force-recreate`.
    Surface: VPS.
  - **Failing-first:** if any of the six flags does not read back as intended after recreate,
    P0.3 fails and no measurement may be recorded against it.
  - **Verify:** post-recreate `printenv` shows all six target values; health 200;
    `docs/evals/plan7/runs/<ts>/remediation_profile.md`.
  - **Depends on:** P0.2
  - **Evidence:** Applied through the P0.1-proven path — repo-root `.env` (last `env_file`, wins over the profile). Host profile **not** switched (`AI_SOC_ENV_PROFILE=development` unchanged); pre-change `.env` backed up first. `docker compose up -d --force-recreate backend`; health `ok`, `db_ready=true`. Read-back from the running backend: LangGraph `true`, exec `true`, v2 `false`, **T4 `true`**, T4 timeout `2.0`, live-cap `false`, `MCP_MODE=mock` — **all six exactly as intended, P0.3 passes**. The T4 timeout was previously unset (code default) and is now written explicitly at the same `2.0`: bound unchanged, only made auditable. Repo `config.py` defaults untouched. Artifact `docs/evals/plan7/runs/remediation_profile.md`. This is a remediation/test posture, not a production profile.

- [x] **P0.4** — Baseline the target profile before any code change
  - **Do:** Run the Plan 6 corpus (12 rows + the 8 T4 paraphrases) on the remediation posture,
    unchanged code. This is the "before" for every later claim. Surface: VPS.
  - **Verify:** `docs/evals/plan7/runs/<ts>/target_profile_baseline.md`; per row record route,
    tier, fingerprint, `degrade_reason`, `phase_names`, `inline_executed`, T4 fields, latency.
  - **Depends on:** P0.3
  - **Evidence:** `docs/evals/plan7/runs/target_profile_baseline.md`. Arm F `docs/evals/plan6/runs/20260814T125340Z/` (12 rows) + arm D `…/20260814T130605Z/` (9 rows — 8 paraphrases plus the shared `p6.t4.out_of_registry`) = **21 row-runs / 20 distinct rows**, harness exit 0 both, `missing_qualification_tier` none, **code unchanged**. Per row: route, tier, fingerprint, `degrade_reason`, `phase_names`, `inline_executed`, T4 fields, latency. **Merge executed on 6/12**; `no_schedulable_step` on **exactly 2/12** (`p6.multi.knowledge_spl_mcp`, `p6.live_posture.d1_003`); remaining 4 are rag_only-shaped turns that never reach the seam. **T4 ON and failing visibly, not suppressed:** invoked on **12/12** T4-tier row-runs and **0** T1–T3 rows (qualification correct), **0** accepted contracts, **12/12** timeouts at 2000–2003 ms against the 2.0 s bound, **0** false capability widening, clarification preserved. Arm F p50 ≈ **55.5 s** vs Plan 6's 92.9 s — attributed to v2 being OFF (no pre-SPL discovery), **not** claimed as an improvement.

---

## Workstream A — make ResourcePlan + PhaseContract authoritative

- [x] **A0** — Reproduce the missed work structurally
  - **Do:** On the P0.3 posture, capture full traces for `p6.multi.knowledge_spl_mcp` and
    `p6.live_posture.d1_003`. Establish *why* the compiler returns `no_schedulable_step` and
    what work is lost relative to the v2-ON run. Anchors: `resource_plan_execution_scheduler.py`
    `SCHEDULABLE_HOOKS` (deliberately excludes `spl_postprocessor` / `reference_finalize`),
    `phase_schedule_merge.py` (re-inserts contracted lifecycle phases — but only when merge
    runs), `phase_policy.py:143` (`spl_postprocessor` marked "spl candidate must be
    deterministically validated"), `phase_registry.py:128`. Surface: VPS + LOCAL.
  - **Failing-first:** write a failing test that asserts the mandatory lifecycle phase is
    honoured on a `no_schedulable_step` plan. It must fail before the fix.
  - **Verify:** `docs/evals/plan7/a0_missed_work_analysis.md` states the mechanism, not the
    symptom; the failing test is committed and red.
  - **Depends on:** P0.4
  - **Evidence:** `docs/evals/plan7/a0_missed_work_analysis.md`. Runtime: both rows show `degrade_reason=no_schedulable_step`, `phase_names=[]`, and an executed `dispatch_schedule` of `workflow_spl → spl_source_resolve → execution` — **`spl_postprocessor` absent** though `workflow_spl` ran, so a candidate SPL exists that never passed the mandatory deterministic post-processing. Control row `p6.spl.draft` has an **identical contract shape** (`spl_generation_only` / `spl_artifact` / `required=['spl']`, T2) and merges correctly with `spl_postprocessor` present — proving the discriminator is the **ResourcePlan's schedulable purposes**, not the query. Mechanism: `_compile_hooks` returns `[]` → `no_schedulable_step`; `merge_schedule:204-206` returns on that downgrade **before** `_apply_phase_contract` / `validate_schedule`, so the resolved contract is discarded unread; `spl_postprocessor` is excluded from `SCHEDULABLE_HOOKS` by design, making the merge its only re-inserter; `phase_policy.py:143` marks it mandatory from `required_capabilities`/`candidate_spl` **without** needing a schedulable `spl_artifact` step; with v2 OFF the predicate fallback never adds it (v2's projected schedule did, `pipeline_dispatch_builder.py:38,286`). **Failing-first test committed before any fix:** `backend/app/tests/test_plan7_a0_mandatory_phase_survives_no_schedulable_step.py` → **2 passed, 2 xfailed(strict)**; asserts the architectural invariant, names no query ID, and a second test proves the early return is **phase-agnostic**. No fix implemented.

- [ ] **A1** — Enumerate every structurally equivalent case
  - **Do:** Sweep the corpus, the 105 goldens and the Cisco 50 for the same structural
    condition (contract declares a mandatory lifecycle phase; compiler emits no schedulable
    step; merge therefore never re-inserts). Classify by mechanism, never by query ID.
  - **Verify:** `docs/evals/plan7/a1_structural_population.md` with counts per mechanism and
    the query set each covers; explicitly states whether the population is larger than the two
    known rows.
  - **Depends on:** A0
  - **Evidence:** _(fill when done)_

- [ ] **A2** — `P7_SPL_LIFECYCLE_OWNERSHIP` **STOP**
  - **Do:** Present the ownership options with their blast radius: (a) PhaseContract lifecycle
    honoured independently of merge reachability; (b) compiler learns to emit contract-only
    schedules; (c) `spl_postprocessor` becomes a real ResourcePlan step; (d) execution-seam
    responsibility; (e) migrate the legacy/v2-only behaviour explicitly. Recommend one with
    evidence. Do **not** implement before the decision. Surface: DECISION.
  - **Verify:** decision recorded under Approved decisions with the chosen option and the
    rejected ones; artifact `docs/evals/plan7/a2_stop_decision.md`.
  - **Depends on:** A1
  - **STOP:** `P7_SPL_LIFECYCLE_OWNERSHIP`
  - **Evidence:** _(fill when done)_

- [ ] **A3** — Implement the approved ownership fix
  - **Do:** Implement exactly the approved option. No query-ID special cases, no keyword
    heuristics, no skill widening, no one-off branch. The deterministic applicability condition
    from A0 is the only trigger. Surface: LOCAL.
  - **Failing-first:** the A0 test goes green; add a structural test covering the full A1
    population, not the two examples.
  - **Verify:** targeted pytest green; `/invariant-check` 7/7; flag-OFF behaviour byte-identical.
  - **Depends on:** A2
  - **Evidence:** _(fill when done)_

- [ ] **A4** — Re-measure authority on the target profile
  - **Do:** Re-run the P0.4 corpus with exec ON, v2 OFF, T4 ON. Surface: VPS.
  - **Verify:** against the acceptance criteria below — **0** missed mandatory phases, **0**
    duplicate execution, **0** merge + old-engine double-run, SPL validation preserved,
    candidate SPL never executable, only validated non-null `normalized_spl` reaching the
    gate, HIL preserved, RBAC preserved, PhaseContract mandatory phases honoured, inline
    phases correctly represented **and** executed, every route/tier/fingerprint delta vs
    Plan 6 Arm A either fixed or explained. Artifact
    `docs/evals/plan7/runs/<ts>/a4_authority_acceptance.md`.
  - **Depends on:** A3
  - **Evidence:** _(fill when done)_

- [ ] **A5** — Old-path audit
  - **Do:** Identify any path still executing work that ResourcePlan + PhaseContract should own
    (including `_run_legacy_dispatch_fallback` and the four `DECISION_REQUIRED` seams).
    Classify each as **migration debt**, **legitimately separate**, or **regression**.
    Adoption of any seam remains its own decision. Surface: LOCAL.
  - **Verify:** `docs/evals/plan7/a5_old_path_audit.md`; `test_execution_seam_coverage.py`
    updated to reflect reality, never loosened.
  - **Depends on:** A4
  - **Evidence:** _(fill when done)_

- [ ] **A6** — `P7_DISPATCH_V2_RETIREMENT` **STOP**
  - **Do:** Present whether dispatch-v2 can remain OFF as the normal authority: missed work
    count, duplicate execution count, regressions fixed vs outstanding, migration debt from A5,
    and rollback cost. **Dispatch-v2 taking authority back is not an acceptable "fix".**
    Surface: DECISION.
  - **Verify:** decision recorded; artifact `docs/evals/plan7/a6_stop_decision.md`.
  - **Depends on:** A5
  - **STOP:** `P7_DISPATCH_V2_RETIREMENT`
  - **Evidence:** _(fill when done)_

### ResourcePlan authority acceptance criteria (A4 gate)

Measured with exec **ON**, v2 **OFF**, T4 **ON**, live capability enforcement **OFF**:

| Criterion | Required |
|---|---|
| Missed mandatory phases / work | **0** |
| Duplicate execution | **0** |
| Merge + old-engine double-run | **0** |
| Deterministic SPL validation | preserved |
| Candidate SPL as executable evidence | **never** |
| Reaching the MCP gate | only validated non-null `normalized_spl` |
| HIL / RBAC | preserved |
| Route / tier / fingerprint regressions | fixed or explained |
| PhaseContract mandatory phases | honoured |
| Inline phases | correctly represented **and** executed |
| Query-ID-specific fixes | **none** |

---

## Workstream B — keep T4 ON and measure the real target architecture

- [ ] **B0** — T4-ON instrumentation on every run
  - **Do:** For every corpus/regression run in this plan capture per row: T4 invoked, contract
    accepted, timeout, malformed/empty output, slot-busy, clarification preserved, capability
    widening, selected route after failure, total latency. Ride the existing
    `debug_summary.resolved_query.semantic_t4` block — no new env flag. Surface: LOCAL+VPS.
  - **Verify:** the harness emits all nine fields per row; `docs/evals/plan7/b0_t4_fields.md`.
  - **Depends on:** P0.3
  - **Evidence:** `docs/evals/plan7/runs/target_profile_baseline.md`. Arm F `docs/evals/plan6/runs/20260814T125340Z/` (12 rows) + arm D `…/20260814T130605Z/` (9 rows — 8 paraphrases plus the shared `p6.t4.out_of_registry`) = **21 row-runs / 20 distinct rows**, harness exit 0 both, `missing_qualification_tier` none, **code unchanged**. Per row: route, tier, fingerprint, `degrade_reason`, `phase_names`, `inline_executed`, T4 fields, latency. **Merge executed on 6/12**; `no_schedulable_step` on **exactly 2/12** (`p6.multi.knowledge_spl_mcp`, `p6.live_posture.d1_003`); remaining 4 are rag_only-shaped turns that never reach the seam. **T4 ON and failing visibly, not suppressed:** invoked on **12/12** T4-tier row-runs and **0** T1–T3 rows (qualification correct), **0** accepted contracts, **12/12** timeouts at 2000–2003 ms against the 2.0 s bound, **0** false capability widening, clarification preserved. Arm F p50 ≈ **55.5 s** vs Plan 6's 92.9 s — attributed to v2 being OFF (no pre-SPL discovery), **not** claimed as an improvement.

- [ ] **B1** — T4-ON diagnostic baseline
  - **Do:** Record the current expected outcome honestly — T4 invoked → ~2 s bounded failure →
    deterministic safe fallback/clarification. Acceptable as diagnostic evidence; **not**
    sufficient for production activation. Surface: VPS.
  - **Failing-first:** a run reporting zero T4 invocations on T4 rows means T4 is not actually
    ON — investigate rather than record a pass.
  - **Verify:** `docs/evals/plan7/b1_t4_on_baseline.md`; **0** false capability widening; **0**
    clarification losses; failures visible, not suppressed.
  - **Depends on:** B0, A4
  - **Evidence:** _(fill when done)_

---

## Workstream C — T4 serving remediation (only after authority is correct)

- [ ] **C0** — Intended production/COE serving option
  - **Do:** Investigate the intended serving posture rather than rescuing the current llama
    configuration with arbitrary timeout increases. The T4 interface/contract stays stable
    while serving underneath may change. Surface: LOCAL.
  - **Verify:** `docs/evals/plan7/c0_serving_options.md` — each option with what it would take
    and what it would prove; no timeout change proposed as a first move.
  - **Depends on:** A6
  - **Evidence:** _(fill when done)_

- [ ] **C1** — Stand up the candidate serving posture (non-destructive)
  - **Do:** Bring up the candidate without disturbing the persisted production profile or the
    existing LLM roles. Surface: VPS.
  - **Verify:** existing roles unaffected (probe); candidate reachable; no new env flag beyond
    what the serving change genuinely requires.
  - **Depends on:** C0
  - **Evidence:** _(fill when done)_

- [ ] **C2** — Serving-viability measurement
  - **Do:** Measure accepted structured-contract rate; semantic accuracy on the eight residual
    paraphrases (`para.003/004/005/006/007/008/012/015`); false widening on ambiguous T4
    queries; cold/warm latency; p50/p95; concurrency; slot pressure; malformed/empty behaviour;
    bounded failure behaviour; end-to-end `/chat` impact. Surface: VPS.
  - **Verify:** `docs/evals/plan7/c2_serving_viability.md` with every metric above; no metric
    omitted because it looked bad.
  - **Depends on:** C1, B1
  - **Evidence:** _(fill when done)_

- [ ] **C3** — `P7_T4_SERVING_POSTURE_V2` **STOP**
  - **Do:** Present C2. Only here may the 2.0 s timeout or the serving configuration change,
    and only with evidence that specifically justifies it. Surface: DECISION.
  - **Verify:** decision recorded; artifact `docs/evals/plan7/c3_stop_decision.md`; if the
    posture stays non-viable, T4 remains ON in the architecture profile with the failure
    visible and documented.
  - **Depends on:** C2
  - **STOP:** `P7_T4_SERVING_POSTURE_V2`
  - **Evidence:** _(fill when done)_

---

## Workstream D — integrated target-profile readiness

- [ ] **D0** — Target-architecture regression corpus
  - **Do:** Full corpus + paraphrases + in-catalogue contract on the final target posture.
    Surface: VPS.
  - **Verify:** `docs/evals/plan7/runs/<ts>/target_corpus.md`; every delta vs Plan 6 Arm A
    explained; no regression accepted silently.
  - **Depends on:** A6, C3
  - **Evidence:** _(fill when done)_

- [ ] **D1** — Reliability and failure behaviour on the target posture
  - **Do:** Repeat the Plan 6 F3 classes against the new authority: restart/recreate,
    concurrency, repeated identical requests, latency p50/p95, LLM unavailable, malformed LLM
    output, LLM timeout, DB failure/recovery, MCP unavailable, model-slot pressure. Assert no
    duplicate side effects and bounded safe degradation. Surface: VPS.
  - **Failing-first:** a missing failure-class row fails the item. Do not weaken tests.
  - **Verify:** `docs/evals/plan7/runs/<ts>/d1_reliability.md`, one row per class.
  - **Depends on:** D0
  - **Evidence:** _(fill when done)_

- [ ] **D2** — Persist the target profile and prove restart persistence
  - **Do:** Write the approved target flags into the configuration path proven in P0.1;
    `--force-recreate`; re-capture effective flags; re-run representative smoke. Surface: VPS.
  - **Failing-first:** post-recreate flags not matching the approved target profile fails D2.
  - **Verify:** `docs/evals/plan7/runs/<ts>/d2_persistence.md` with pre/post booleans and the
    observed execution authority (`degrade_reason` must not show v2 winning).
  - **Depends on:** D1
  - **Evidence:** _(fill when done)_

- [ ] **D3** — Rollback drill on the new authority
  - **Do:** Roll back to the Plan 6 recorded profile (exec OFF, v2 ON, T4 OFF), verify, then
    re-apply the target profile and verify again. Update
    `docs/evals/plan7/rollback_runbook.md`; it must touch the profile named by
    `AI_SOC_ENV_PROFILE`, not just `.env`. Surface: VPS.
  - **Failing-first:** if rollback smoke still shows the new authority active, rollback failed.
  - **Verify:** both directions recorded; host left in the **target** profile.
  - **Depends on:** D2
  - **Evidence:** _(fill when done)_

---

## E — new go-live gate

- [ ] **E0** — Plan 7 report
  - **Do:** `docs/evals/plan7_architecture_authority_report.md` answering the twelve success
    questions with artifact citations. State the persistent profile separately from repo
    defaults. Honest about anything still unproven. Surface: LOCAL.
  - **Verify:** every number traces to `docs/evals/plan7/`; no claim that frozen `--arm both`
    observed L4/L5; parity `120 exact` never cited as routing correctness; `V2_WINS` never
    described as activation.
  - **Depends on:** D3
  - **Evidence:** _(fill when done)_

- [ ] **E1** — Closure gates
  - **Do:** Full forecast-rule set: governance regression, backend pytest, parity, Cisco,
    probes, sentinel, path, protected manifest, invariants, plan-discipline audit. Revert only
    the six stale reports. Surface: LOCAL.
  - **Verify:** governance PASS; pytest green vs the P0 baseline; truth-set `--check` 0
    regressions; parity `120 exact`; Cisco `50/0/0`; probes `10/10`; sentinel `17/17`; path
    `105/105`; manifest N/N; invariants 7/7; plan audit 0 gaps.
  - **Depends on:** E0
  - **Evidence:** _(fill when done)_

- [ ] **E2** — `P7_PRODUCTION_GO_LIVE_V2` **STOP**
  - **Do:** Present the full matrix: Functional, Safety, Performance, Reliability,
    Security/RBAC, Observability, Deployment/restart persistence, Rollback, Corpus, Production
    flags, **ResourcePlan production authority**, **T4 serving posture**, **Execution seam
    posture**, MITRE governance, **Live MCP/Splunk scope**, Critical blockers, Accepted risks.
    Verdicts are only PASS / BLOCKER / ACCEPTED RISK / NOT IN PRODUCTION SCOPE ⋅ UNPROVEN.
    `GO LIVE` requires **zero** critical blockers, ResourcePlan authority actually active with
    v2 OFF, **and all three T4 conditions below**. Do **not** choose the outcome.
    Surface: DECISION.
  - **T4 is a hard GO requirement.** `GO LIVE` additionally requires: (1)
    `AI_SOC_T4_SEMANTIC_UNDERSTANDING_ENABLED=ON`; (2) C3 approved a **viable** serving
    posture; (3) the T4 accepted-contract, semantic-accuracy and safety criteria from C2 pass.
    **If C3 remains NON-VIABLE, T4 is a CRITICAL BLOCKER for Plan 7 production GO — it must
    not be downgraded to NOT IN PRODUCTION SCOPE.** Unlike Plan 6, T4 is part of the intended
    production architecture here; reaching this gate and reporting "everything is fine except
    T4 is out of scope" is not an available outcome.
  - **Verify:** decision recorded under Approved decisions only after the user chooses; live
    MCP honesty stated; merge to `master` remains user-only.
  - **Depends on:** E1
  - **STOP:** `P7_PRODUCTION_GO_LIVE_V2`
  - **Evidence:** _(fill when done)_

---

## Stop conditions

Stop and report when: a named STOP is reached; the same Verify fails twice on one item; new
evidence contradicts a locked decision; or all items are checked with Evidence.

## Drift / evidence discipline

Evidence is **observed output**, not intent. A failing Verify is recorded as failing. Never
check an item off on a partial pass. Baselines and fixtures change only when a named gate makes
the old value wrong. VPS evidence records SHA, flag booleans/names and trace_ids — never
tokens, passwords, SPL secrets or MCP payloads. T4 failures are never hidden, and T4 is never
switched off to make a run green.

## Commit / PR / merge

**Stacked on Plan 6, not on `master`.**

| | |
|---|---|
| Plan 7 branch | `feat/plan7-resource-plan-authority-t4` |
| Base branch during Plan 7 development | `feat/plan6-production-activation` |
| Plan 7 PR | opened **against `feat/plan6-production-activation`**, stacked on PR #132 |

A Plan 7 PR opened directly against `master` while #132 is unmerged would carry every Plan 6
commit in its diff and make review confusing. Do not do that. Plan 6's evidence stays
preserved on its own branch and PR.

Final merge order to `master` is **user-only**: #132 first, then the Plan 7 PR (rebasing or
retargeting it only when the user asks).

Phase-scoped commits after each Verify (`plan7(<item>): …`). `/invariant-check` 7/7 before any
runtime commit. Draft PR after A2. **Never merge to `master`** — `--merge`, never squash.
