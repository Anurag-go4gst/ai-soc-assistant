---
canonical_plan: plans/2026-08-14_1130_resource-plan-authority-and-t4-integration.md
canonical_architecture: architecture.md
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
AI_SOC_T4_SEMANTIC_UNDERSTANDING_TIMEOUT_SECONDS = 120   (VPS_T4_REMEDIATION_TIMEOUT; not a universal value)
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
  prohibited. The bound was 2.0 s until C3; C3 recorded `VPS_T4_REMEDIATION_TIMEOUT = 120 s` for
  the VPS only. Do not raise it again automatically if 120 s fails, and do not treat it as the
  COE/production target or as an architectural invariant.

## STOPs (user decision required; do not self-approve)

- `P7_SPL_LIFECYCLE_OWNERSHIP` (A2) — before changing where `spl_postprocessor` is owned.
- `P7_DISPATCH_V2_RETIREMENT` (A6) — before making v2 OFF the normal authority.
- `P7_T4_SERVING_POSTURE_V2` (C3) — before changing serving config or the 2.0 s bound.
- `P7_PRODUCTION_GO_LIVE_V2` (E2) — the new go-live gate.

## Approved decisions

### A2 — `P7_SPL_LIFECYCLE_OWNERSHIP` (2026-08-14)

**OPTION A — the PhaseContract lifecycle is honoured independently of merge reachability.**

`ResourcePlan` / `compile_execution_schedule` owns compilation of schedulable resource work.
`PhaseContract` / `PhasePolicy` owns mandatory lifecycle obligations. A compiler downgrade such
as `no_schedulable_step` must **not** erase applicable mandatory lifecycle phases:

```
ResourcePlan compilation result  +  PhaseContract mandatory lifecycle obligations
                                 ↓
                    final governed schedule / downgrade

A resource-plan downgrade may remove unavailable resource work.
It may not silently remove applicable mandatory lifecycle work.
```

Rejected — **B** (re-couples compilation to lifecycle ownership; two insertion authorities;
duplicate-ordering risk), **C** (upstream plan can itself be vetoed/narration-only, so it does
not solve the early return, and churns SPL fingerprints/baselines), **D** (broader and later than
the defect, highest duplicate risk, turns the execution seam into a compensating lifecycle
reconciler — seams may still be audited in A5). **E** retained as migration framing only, not the
implementation site.

Artifact: `docs/evals/plan7/a2_stop_decision_packet.md`.

### A6 — `P7_DISPATCH_V2_RETIREMENT` (2026-08-15)

**`V2_OFF_PENDING_WIDER_EVIDENCE`.**

dispatch-v2 stays **OFF** for the remainder of Plan 7 and is **not** restored as normal
authority. ResourcePlan + PhaseContract + the deterministic merge/compiler remain the
architecture under remediation and validation. **v2-OFF is not yet claimed as proven
production-normal authority.**

A3/A4 did fix the measured lifecycle-ownership defect: affected population **6 → 0**, corpus rows
losing mandatory lifecycle **2 → 0**, merge authoritative **6/12 → 8/12**, duplicate execution
**0**, merge + old-engine double-run **0**, route/tier/fingerprint regressions **0**,
deterministic SPL validation preserved, HIL/RBAC preserved. The `bb38d292` change to
`spl_validation_failed` + HIL `source_profile_slots_missing` is a **governed safety correction,
not a regression** — validation now runs where it previously did not.

Outstanding evidence before production-normal authority may be claimed:

1. `_run_legacy_dispatch_fallback` remains reachable through `session_spl_refine` and skips
   `spl_postprocessor`; it was **not** exercised in A4. Given A3's finding that losing the merge
   can lose deterministic SPL validation, this path must not be assumed safe.
2. End-to-end authority evidence is primarily the 12-row corpus; the 175-row sweep is
   planning-layer structural coverage, not end-to-end execution coverage.
3. Goldens / Cisco have not been exercised end-to-end under the target ResourcePlan authority.
4. Live MCP remains `live_mcp_unproven`.
5. T4 is ON but has produced no accepted contract at 2.0 s; it remains a separate **hard GO**
   requirement.
6. Bounded pre-SPL discovery remains unproven and must not be removed merely because current
   corpus paths succeed.

Therefore: keep ResourcePlan execution **ON**, dispatch-v2 **OFF**, T4 **ON @ 2.0 s**, live
capability enforcement **OFF**; do not change repo defaults; do not restore v2; do not retire the
fallback; do not claim production-normal authority.

Artifact: `docs/evals/plan7/a6_stop_decision_packet.md`.

### C3 — `P7_T4_SERVING_POSTURE_V2` (2026-08-15)

**`REMEDIATE_EXISTING_T4_IN_PLACE`.** This supersedes the four options offered in the C3 packet,
because additional same-VPS evidence arrived after the packet was written.

Keep the existing T4 architecture and the current Cisco Foundation-Sec 8B model. **Do not** add a
sidecar, add Redis/cache work, change provider, introduce Gemini into the production T4 path,
download another model, redesign T4, add routing keywords, or restore dispatch-v2.

Reclassification:

```
T4 semantic role                 VIABLE
Cisco 8B semantic capability     VIABLE / PROVISIONALLY PROVEN
current production T4 prompt     NEEDS HARDENING
few-shot prompting               MATERIALLY BENEFICIAL
structured output                USE CONSTRAINED JSON
current 2-second VPS timeout     NON-VIABLE
VPS model runtime stability      NEEDS EXISTING RELIABILITY HANDLING
```

**`VPS_T4_REMEDIATION_TIMEOUT = 120 seconds`** — deployed as
`AI_SOC_T4_SEMANTIC_UNDERSTANDING_TIMEOUT_SECONDS=120` on the VPS only. It is **not** the final
COE/production latency target and must **not** be written into the architectural invariant as a
universal value. Repo defaults stay unchanged. Rationale is measured VPS behaviour: 2.0 s times
out essentially every useful invocation; useful same-VPS responses were observed around **76 s**;
earlier probes reached ~**109 s**. 120 s gives the existing model room while staying bounded.
**Do not automatically raise it again if 120 s fails.**

Minimum T4 prompt correction only — no second semantic service. T1–T3 must supply: original
query, locked deterministic fields, explicit unresolved semantic fields, a short relevant
semantic/capability vocabulary, 1–3 compact curated few-shot examples, and a strict
structured-output schema. The prompt must tell the model to resolve only unresolved semantic
meaning, not rewrite locked fields, preserve competing hypotheses, clarify instead of inventing
facts, never generate/execute SPL, never call MCP, never make RBAC/HIL/policy decisions, and
return structured JSON only. Few-shot examples are **prompt assets**, not a RAG system or agent.
Use constrained JSON/schema decoding where the serving stack supports it.

**Deterministic authority is unchanged.** T4 remains reasoning-only: it may not select an
execution route, grant capabilities, invoke MCP, execute SPL, authorize remediation, change
RBAC/HIL, clear deterministic prohibitions, or overwrite locked T1–T3 facts. Any accepted
structured result must still pass deterministic validation/merge.

Manual same-VPS evidence recorded separately in `docs/evals/plan7/c3_manual_vps_evidence.md`;
earlier C2 evidence is **not** rewritten. Artifacts: `c2_serving_viability.md`,
`c3_stop_decision_packet.md`, `c3_manual_vps_evidence.md`, `c3_remediation_evidence.md`.

**C3 implementation outcome (2026-08-15): `T4_PROMPT_INTERFACE_STILL_BLOCKING`.** The remediation landed in the seam, not the prompt: a response-shape adapter (one wrapper hop, echoed scaffolding dropped, unknown non-authority keys dropped, authority keys fail closed), the three-uncertainty rule enforced deterministically (clarification only for an unresolved referent), concrete-entity and grounded-time-scope guards, and `intent_family`/`answer_goal` made genuinely immutable. Measured POST-C3: accepted **2/9** then **1/4** at 78.3 / 111.7 / 115.1 s, with host swap-thrash — not the prompt — driving the run-to-run variance (>360 s while thrashing both with and without constrained decoding; 83.4 s immediately after a model restart). T4 stays a **hard GO requirement** and therefore a CRITICAL BLOCKER until re-measured against the corrected interface. **Consequence to carry:** with locked fields now immutable, T4 can no longer re-classify a paraphrase into an SPL-capable family — upstream locked-field quality is the binding constraint, deferred to Plan 8.

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

- [x] **A1** — Enumerate every structurally equivalent case
  - **Do:** Sweep the corpus, the 105 goldens and the Cisco 50 for the same structural
    condition (contract declares a mandatory lifecycle phase; compiler emits no schedulable
    step; merge therefore never re-inserts). Classify by mechanism, never by query ID.
  - **Verify:** `docs/evals/plan7/a1_structural_population.md` with counts per mechanism and
    the query set each covers; explicitly states whether the population is larger than the two
    known rows.
  - **Depends on:** A0
  - **Evidence:** `docs/evals/plan7/a1_structural_population.md` + `.json`, from `scripts/eval_plan7_a1_population.py` (planning layer only — no LLM, MCP or HTTP call). **175 rows swept**: Plan 6 corpus 20, goldens 105, Cisco 50. Compiler verdicts: **158** merged cleanly, **11** `empty_resource_plan`, **6** `no_schedulable_step`. **Affected: 5 offline** (1 plan6 + 4 goldens `q0.q055/094/095/103`, **0 Cisco**) **+ 1 runtime-only** (`p6.multi.knowledge_spl_mcp`, trace `4e048382…`) = **6 distinct rows, a lower bound**. Classified by mechanism, not query ID: **M1 skill-contract veto empties the plan** (5 rows — `spl_generation_only` intent routed to a skill that vetoes `spl_artifact`, leaving `narration` only → no hook → downgrade → contract discarded); **M2 no lifecycle owed** (11 clarification-lane rows — benign); **M3 narration-only `alert_summary`** (1 row — benign). **0** rows where the merge applied the contract and still dropped a phase. Every affected row loses the **same four** hook-backed phases together — `workflow_spl`, `spl_postprocessor`, `spl_source_resolve` and **`execution`** — so the defect is **not** `spl_postprocessor`-specific; inline phases (`mitre_finalize`/`cve_adapter`) are latent-but-unmeasured because the early return is phase-agnostic. Limitations stated in the artifact: the sweep routes deterministically while the runtime uses full adjudication (which is why one row is runtime-only), models `blocked_step_ids=∅`, and enters `resource_plan_authority()` to use the runtime's own composer without committing anything.

- [x] **A2** — `P7_SPL_LIFECYCLE_OWNERSHIP` **STOP**
  - **Do:** Present the ownership options with their blast radius: (a) PhaseContract lifecycle
    honoured independently of merge reachability; (b) compiler learns to emit contract-only
    schedules; (c) `spl_postprocessor` becomes a real ResourcePlan step; (d) execution-seam
    responsibility; (e) migrate the legacy/v2-only behaviour explicitly. Recommend one with
    evidence. Do **not** implement before the decision. Surface: DECISION.
  - **Verify:** decision recorded under Approved decisions with the chosen option and the
    rejected ones; artifact `docs/evals/plan7/a2_stop_decision.md`.
  - **Depends on:** A1
  - **STOP:** `P7_SPL_LIFECYCLE_OWNERSHIP`
  - **Evidence:** Packet presented: `docs/evals/plan7/a2_stop_decision_packet.md` — population, deterministic applicability condition, current ownership map, why `no_schedulable_step` prevents it, all five options (A–E) each with ownership / applicability / blast radius / population covered / effect on other lifecycle phases / flag-OFF compatibility / duplicate-execution risk / seam interaction / tests required, plus recommendation (**A, framed as E**) and reasoned rejections of B, C, D. **User recorded OPTION A** — PhaseContract lifecycle is honoured independently of merge reachability. `ResourcePlan`/`compile_execution_schedule` owns schedulable resource work; `PhaseContract`/PhasePolicy owns mandatory lifecycle obligations; a resource downgrade may remove unavailable resource work but may not silently remove applicable mandatory lifecycle work. **B rejected** (re-couples compilation to lifecycle, two insertion authorities); **C rejected** (upstream plan can be vetoed/narration-only, so it does not solve the early return, and churns SPL fingerprints); **D rejected for this fix** (broader and later than the defect, highest duplicate risk, turns the execution seam into a compensating reconciler — seams may still be audited in A5); **E retained as migration framing only**. Recorded in Approved decisions § A2.

- [x] **A3** — Implement the approved ownership fix
  - **Do:** Implement exactly the approved option. No query-ID special cases, no keyword
    heuristics, no skill widening, no one-off branch. The deterministic applicability condition
    from A0 is the only trigger. Surface: LOCAL.
  - **Failing-first:** the A0 test goes green; add a structural test covering the full A1
    population, not the two examples.
  - **Verify:** targeted pytest green; `/invariant-check` 7/7; flag-OFF behaviour byte-identical.
  - **Depends on:** A2
  - **Evidence:** `docs/evals/plan7/a3_ownership_fix.md`. One function changed (`phase_schedule_merge.merge_schedule`, ~20 lines) plus `MergedSchedule.resource_downgrade` provenance and its executor-trace passthrough. Trigger is structural — compiler downgraded **and** the execution contract is still valid **and** `hook_bound_mandatory` is non-empty — with **no** query ID, intent, capability name or `spl_postprocessor` special case. **Deliberate narrowing during implementation:** the first version turned safety refusals into schedules and four existing tests caught it (`test_absent_plan_downgrades_to_the_fixed_schedule`, `test_unsupported_purpose_downgrades`, `test_side_effecting_step_may_not_declare_a_retry`, `test_cyclic_plan_is_rejected_not_scheduled`); the **fix was narrowed, the tests were not edited**. All seven required properties evidenced. Failing-first test now green with strict-xfails removed: **15 passed**, covering affected `workflow_spl`, latent non-SPL phases (`execution`, `reference_finalize`), multiple mandatory phases + ordering, inline representation, both benign downgrade classes, normal merge unchanged, no duplicate insertion, and three safety-refusal fail-closed cases. A1 population re-run after the fix: **0 affected / 175** (merged 158 → 163; compiler verdicts unchanged). Gates: merge/contract/seam suites **65 passed**; planner/dispatch/executor/phase/seam slice **997 passed**; `/invariant-check` **7/7**; flag-OFF byte-identical by construction (`executor.py:247`). PhasePolicy rules unchanged, capabilities not widened, v2 not re-enabled, T4 ON at 2.0 s, live capability enforcement OFF. Open observation flagged to A4: lifecycle-only insertion orders `spl_source_resolve` before `spl_postprocessor` (registry leaves them mutually unordered) — pre-existing `_apply_phase_contract` behaviour, pinned by test, to be confirmed on the real posture.

- [x] **A4** — Re-measure authority on the target profile
  - **Do:** Re-run the P0.4 corpus with exec ON, v2 OFF, T4 ON. Surface: VPS.
  - **Verify:** against the acceptance criteria below — **0** missed mandatory phases, **0**
    duplicate execution, **0** merge + old-engine double-run, SPL validation preserved,
    candidate SPL never executable, only validated non-null `normalized_spl` reaching the
    gate, HIL preserved, RBAC preserved, PhaseContract mandatory phases honoured, inline
    phases correctly represented **and** executed, every route/tier/fingerprint delta vs
    Plan 6 Arm A either fixed or explained. Artifact
    `docs/evals/plan7/runs/<ts>/a4_authority_acceptance.md`.
  - **Depends on:** A3
  - **Evidence:** `docs/evals/plan7/a4_authority_acceptance.md`, run `docs/evals/plan6/runs/20260814T134610Z/` on the verified target posture (exec ON, v2 OFF, **T4 ON @ 2.0 s**, live-cap OFF, LangGraph ON). 12/12 exit 0, `missing_qualification_tier` none. **All 12 acceptance criteria pass:** missed mandatory work **0** (merge authoritative 6/12 → **8/12**), duplicate execution **0**, merge+old-engine double-run **0**, SPL validation preserved, `execution_eligible` **null** on every row, MCP gate `allowed=false` with explicit `block_reason` on both fixed rows, HIL required where owed, RBAC untouched, contract phases honoured, inline `mitre_finalize` both represented and executed, **0 route/tier/fingerprint deltas**, no query-specific fixes. Both defect rows now `degrade=merge` with `resource_downgrade=no_schedulable_step` and `inserted_phases=[workflow_spl, spl_postprocessor, spl_source_resolve, execution]` — the A3 path firing exactly where measured and nowhere else. **New governed refusal** on `bb38d292`: restored `spl_postprocessor` produced `spl_validation_failed` + HIL `source_profile_slots_missing`, where before the phase never ran. **Wider finding:** `spl_postprocessor` is contract-inserted on **4 healthy rows too**, so every SPL row depends on the merge for deterministic validation. A3's ordering question answered: lifecycle-only insertion resolves source slots **before** post-processing, which matches the governed post-slot-resolution validation rule; recorded as an accepted pinned difference, no ordering code changed.

- [x] **A5** — Old-path audit
  - **Do:** Identify any path still executing work that ResourcePlan + PhaseContract should own
    (including `_run_legacy_dispatch_fallback` and the four `DECISION_REQUIRED` seams).
    Classify each as **migration debt**, **legitimately separate**, or **regression**.
    Adoption of any seam remains its own decision. Surface: LOCAL.
  - **Verify:** `docs/evals/plan7/a5_old_path_audit.md`; `test_execution_seam_coverage.py`
    updated to reflect reality, never loosened.
  - **Depends on:** A4
  - **Evidence:** `docs/evals/plan7/a5_old_path_audit.md`, from `dispatch_source` on all 12 A4 traces. **8** rows `resource_plan_step_walk` with merge active (target architecture); **2** `canonical_non_planned`; **2** no `plan_dispatch` (rag-only lane); **0** `legacy_predicate`, **0** `session_spl_refine`, **0** `guided_hybrid`. **`_run_legacy_dispatch_fallback` executed zero times** — no old engine ran beside the merge. Classification: **migration debt ×1** (the fallback still skips `spl_postprocessor` and stays reachable via `session_spl_refine` — unexercised here, so unproven rather than safe); **legitimately separate ×4**; **regressions ×0**. Seam inventory unchanged at **2 SEAM / 4 DECISION_REQUIRED / 4 KEEP_SEPARATE, 0 adopted** — nothing adopted, nothing retired in A5.

- [x] **A6** — `P7_DISPATCH_V2_RETIREMENT` **STOP**
  - **Do:** Present whether dispatch-v2 can remain OFF as the normal authority: missed work
    count, duplicate execution count, regressions fixed vs outstanding, migration debt from A5,
    and rollback cost. **Dispatch-v2 taking authority back is not an acceptable "fix".**
    Surface: DECISION.
  - **Verify:** decision recorded; artifact `docs/evals/plan7/a6_stop_decision.md`.
  - **Depends on:** A5
  - **STOP:** `P7_DISPATCH_V2_RETIREMENT`
  - **Evidence:** Packet presented: `docs/evals/plan7/a6_stop_decision_packet.md` — exact effective flags, remaining missed mandatory work (**0 measured**), duplicate work (**0**), post-fix structural population (**0/175**), A4 corpus result, active old paths, A5 classification, rollback cost, and five stated gaps (unexercised `session_spl_refine` fallback; coverage limited to 12 corpus rows + a planning-layer sweep rather than goldens/Cisco end-to-end; MCP still `mock`/`live_mcp_unproven`; T4 still failing at the 2.0 s bound; no measurement that bounded pre-SPL discovery is unnecessary). Options offered: `V2_OFF_IS_NORMAL_AUTHORITY` / `V2_OFF_PENDING_WIDER_EVIDENCE` / `RESTORE_V2`. **User recorded `V2_OFF_PENDING_WIDER_EVIDENCE`** — v2 stays OFF for the remainder of Plan 7 and is not restored as normal authority; v2-OFF is not yet claimed proven. Six outstanding evidence items recorded in Approved decisions § A6, and a new mandatory pre-GO item **A7** added for the `session_spl_refine` / `_run_legacy_dispatch_fallback` path.

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

- [x] **A7** — Prove the `session_spl_refine` / `_run_legacy_dispatch_fallback` path (required before the GO gate)
  - **Do:** Exercise that path under the target architecture, or prove deterministically that it
    cannot bypass required SPL lifecycle validation. Required by A6. Surface: LOCAL + VPS.
  - **Prove specifically:** whether PhaseContract/merge owns the lifecycle before the fallback
    runs; whether `spl_postprocessor` executes; whether candidate SPL is deterministically
    validated; whether only validated non-null `normalized_spl` can reach the MCP gate; whether
    HIL/RBAC remain authoritative; whether duplicate execution occurs.
  - **Failing-first:** if the path still bypasses mandatory lifecycle ownership, that is a **Plan 7
    regression/blocker** and must be fixed **structurally**. It must **not** be solved by
    re-enabling dispatch-v2.
  - **Verify:** `docs/evals/plan7/a7_fallback_lifecycle_proof.md` answers all six questions with
    observed output or a deterministic proof; targeted tests committed; `/invariant-check` 7/7.
  - **Depends on:** A6
  - **Evidence:** `docs/evals/plan7/a7_fallback_lifecycle_proof.md`. Disposition **B —
    `LEGACY_FALLBACK_ROLLBACK_ONLY_RETAIN_TEMPORARILY`**. Production `/chat` on the target
    Resource Planner graph neither imports nor calls the fallback; it has exactly one imperative
    rollback caller. The retained branch now runs `workflow_spl → spl_postprocessor →
    spl_source_resolve → execution`; the exercised mutation fails deterministic revalidation
    closed (`approved=false`, `normalized_spl=null`, execution not live). ResourcePlan execution
    fences v2 projections even if both flags are accidentally true. Focused verification: A7 /
    topology **66 passed**, authority/lifecycle **208 passed**, compatibility/probe/profile **46
    passed**, MCP gate/contract **43 passed**, reference probes **10/10**, invariants **7/7**.

## Workstream B — keep T4 ON and measure the real target architecture

- [x] **B0** — T4-ON instrumentation on every run
  - **Do:** For every corpus/regression run in this plan capture per row: T4 invoked, contract
    accepted, timeout, malformed/empty output, slot-busy, clarification preserved, capability
    widening, selected route after failure, total latency. Ride the existing
    `debug_summary.resolved_query.semantic_t4` block — no new env flag. Surface: LOCAL+VPS.
  - **Verify:** the harness emits all nine fields per row; `docs/evals/plan7/b0_t4_fields.md`.
  - **Depends on:** P0.3
  - **Evidence:** `docs/evals/plan7/runs/target_profile_baseline.md`. Arm F `docs/evals/plan6/runs/20260814T125340Z/` (12 rows) + arm D `…/20260814T130605Z/` (9 rows — 8 paraphrases plus the shared `p6.t4.out_of_registry`) = **21 row-runs / 20 distinct rows**, harness exit 0 both, `missing_qualification_tier` none, **code unchanged**. Per row: route, tier, fingerprint, `degrade_reason`, `phase_names`, `inline_executed`, T4 fields, latency. **Merge executed on 6/12**; `no_schedulable_step` on **exactly 2/12** (`p6.multi.knowledge_spl_mcp`, `p6.live_posture.d1_003`); remaining 4 are rag_only-shaped turns that never reach the seam. **T4 ON and failing visibly, not suppressed:** invoked on **12/12** T4-tier row-runs and **0** T1–T3 rows (qualification correct), **0** accepted contracts, **12/12** timeouts at 2000–2003 ms against the 2.0 s bound, **0** false capability widening, clarification preserved. Arm F p50 ≈ **55.5 s** vs Plan 6's 92.9 s — attributed to v2 being OFF (no pre-SPL discovery), **not** claimed as an improvement.

- [x] **B1** — T4-ON diagnostic baseline
  - **Do:** Record the current expected outcome honestly — T4 invoked → ~2 s bounded failure →
    deterministic safe fallback/clarification. Acceptable as diagnostic evidence; **not**
    sufficient for production activation. Surface: VPS.
  - **Failing-first:** a run reporting zero T4 invocations on T4 rows means T4 is not actually
    ON — investigate rather than record a pass.
  - **Verify:** `docs/evals/plan7/b1_t4_on_baseline.md`; **0** false capability widening; **0**
    clarification losses; failures visible, not suppressed.
  - **Depends on:** B0, A4
  - **Evidence:** `docs/evals/plan7/b1_t4_on_baseline.md`, across **33 row-runs** (P0.4 arm F + arm D, A4 arm F). T4 **invoked 17/17** on every T4-tier row; **0** T4-tier rows without invocation (failing-first: T4 really is ON); **0** invocations on T1–T3 (qualification correct); **0 accepted contracts**; **17/17 timeouts** with `elapsed_ms` **2000–2005 ms**; only note observed is `llm_assist_timed_out`; **0** malformed/empty (bound reached before any parse); **0** slot-busy; **0** false capability widening; clarification preserved; route after failure identical to the Plan 6 Arm A baseline. Recorded outcome: `T4 invoked → ~2 s bounded failure → deterministic safe fallback/clarification`. Acceptable as diagnostic evidence, **not** sufficient for production activation — per the E2 amendment T4 is a hard GO requirement, so a non-viable C3 makes it a CRITICAL BLOCKER. Failures visible, nothing suppressed, T4 never switched off.

---

## Workstream C — T4 serving remediation (only after authority is correct)

- [x] **C0** — Intended production/COE serving option
  - **Do:** Investigate the intended serving posture rather than rescuing the current llama
    configuration with arbitrary timeout increases. The T4 interface/contract stays stable
    while serving underneath may change. Surface: LOCAL.
  - **Verify:** `docs/evals/plan7/c0_serving_options.md` — each option with what it would take
    and what it would prove; no timeout change proposed as a first move.
  - **Depends on:** A6
  - **Evidence:** `docs/evals/plan7/c2_serving_viability.md` § C0. The hop is one `LocalChatClient` call to `resolve_local_primary_endpoint(sidecar=True)` — the **shared** local primary — at `max_tokens=400`. Host: Foundation-Sec 8B **Q8**, RSS **9.4 GB** of 16 GB, **185 MB free**, **swap 4095/4095 exhausted**, `-np 1` (no second decode slot), **one** model on disk, no failover endpoint, no Qwen. Options inventoried with what-it-would-take: **A** JSON-schema constrained decoding (free, in-environment, fixes shape only); **B** Q4 requantisation (~4.7 GB download); **C** small dedicated sidecar model (download **plus a new sidecar endpoint config surface**, needs approval); **D** raise the bound (forbidden pre-C3, and unsupported); **E** free host memory (operator action). No timeout change proposed as a first move.

- [x] **C1** — Stand up the candidate serving posture (non-destructive)
  - **Do:** Bring up the candidate without disturbing the persisted production profile or the
    existing LLM roles. Surface: VPS.
  - **Verify:** existing roles unaffected (probe); candidate reachable; no new env flag beyond
    what the serving change genuinely requires.
  - **Depends on:** C0
  - **Evidence:** Only **Option A** could be stood up without a download or a new config surface, so that is the candidate. Exercised **per request against the existing endpoint** — the persisted profile, the `llama-server` unit and the application code were **not** modified, and no new env flag was added. Existing LLM roles unaffected (the shared endpoint was never reconfigured).

- [x] **C2** — Serving-viability measurement
  - **Do:** Measure accepted structured-contract rate; semantic accuracy on the eight residual
    paraphrases (`para.003/004/005/006/007/008/012/015`); false widening on ambiguous T4
    queries; cold/warm latency; p50/p95; concurrency; slot pressure; malformed/empty behaviour;
    bounded failure behaviour; end-to-end `/chat` impact. Surface: VPS.
  - **Verify:** `docs/evals/plan7/c2_serving_viability.md` with every metric above; no metric
    omitted because it looked bad.
  - **Depends on:** C1, B1
  - **Evidence:** `docs/evals/plan7/c2_serving_viability.md`. **6 probes**, deliberately few (representative, not exhaustive). Accepted-contract rate on the production path **0/17**; with constrained decoding the shape is valid **3/3** but semantically empty. Semantic accuracy on **3 representative residual paraphrases: 0/3** — every response **echoes the deterministic contract** and invents out-of-vocabulary capabilities the governed normalizer discards. False widening **0**. Cold latency **50.72 s for 2 tokens** (25× the budget); warm 4.1–4.5 tok/s → **19–109 s** per contract; p50 ≈ 36 s, p95 ≈ 109 s. Concurrency not measurable (`-np 1`); slot pressure inherent. Malformed/empty: prose without constraint, valid shape with it, truncation at low caps. Bounded failure behaviour **correct** (2.0 s timeout → deterministic fallback, clarification preserved). End-to-end impact if the bound were raised: **+19–109 s on a blocking turn**. **Three independent failures — latency, shape, semantic value — and only shape is fixable in-environment; no metric was omitted for looking bad.**

- [x] **C3** — `P7_T4_SERVING_POSTURE_V2` **STOP**
  - **Do:** Present C2. Only here may the 2.0 s timeout or the serving configuration change,
    and only with evidence that specifically justifies it. Surface: DECISION.
  - **Verify:** decision recorded; artifact `docs/evals/plan7/c3_stop_decision.md`; if the
    posture stays non-viable, T4 remains ON in the architecture profile with the failure
    visible and documented.
  - **Depends on:** C2
  - **STOP:** `P7_T4_SERVING_POSTURE_V2`
  - **Evidence:** Packet presented: `docs/evals/plan7/c3_stop_decision_packet.md` — measurements, the three independent failures, the five options with cost and what each actually fixes, and the E2 consequence that a non-viable finding makes T4 a **CRITICAL BLOCKER** rather than out-of-scope. Options offered: `T4_SERVING_NON_VIABLE_IN_ENVIRONMENT` / `ADOPT_CONSTRAINED_DECODING_ONLY` / `PROCURE_SERVING_CAPACITY` / `RAISE_THE_BOUND` (unsupported, listed for completeness). **User recorded `REMEDIATE_EXISTING_T4_IN_PLACE`** — keep the existing architecture and Cisco 8B; harden the prompt (compact field-constrained few-shot + constrained JSON) and set `VPS_T4_REMEDIATION_TIMEOUT = 120 s` on the VPS only, repo defaults unchanged. No sidecar, no cache work, no provider change, no new model, no redesign, no keywords, no v2 restore. Recorded in Approved decisions § C3, with manual same-VPS evidence in `c3_manual_vps_evidence.md` and earlier C2 evidence left intact.

---

## Workstream D — integrated target-profile readiness

- [x] **D0** — Target-architecture regression corpus
  - **Do:** Full corpus + paraphrases + in-catalogue contract on the final target posture.
    **A6 requirement:** the goldens and Cisco populations must be exercised at the appropriate
    **end-to-end** layer under the target ResourcePlan authority — planning-level classification
    alone does not satisfy this. Surface: VPS.
  - **Verify:** `docs/evals/plan7/runs/<ts>/target_corpus.md`; every delta vs Plan 6 Arm A
    explained; no regression accepted silently.
  - **Depends on:** A6, C3
  - **Evidence:** `docs/evals/plan7/runs/20260815T131000Z/target_corpus.md` + `d0_target_corpus.json`. **30 rows, 0 errors** — the ten required request classes plus the 20-row Plan 6 corpus (12 + 8 paraphrases) — run **inside the container** through `run_chat_via_resource_planner_graph` with real DB, canonical planning, ResourcePlan commit, dispatch seam and PhaseContract merge; only the external model call substituted (`t4_mode: recorded_proposal`). **Verified prerequisite:** outside the container the canonical handoff cannot reach Postgres, so no composed plan commits and the seam never runs — an out-of-container sweep would have looked clean while exercising nothing (also explains A1's zero seam calls). Dispatch: `resource_plan_step_walk` **11**, `canonical_non_planned` **14**, none **5**; **zero** legacy/predicate/session-refine/guided-hybrid. **Invariants all hold:** `execution_eligible` null 30/30, `execution_enabled` false 30/30, MCP never executed, no approved SPL without `normalized_spl`, **no SPL row missing `spl_postprocessor`** (A3 invariant), T4 invoked only on T4 tier (18/18, zero on T1–T3). **Deltas vs Arm A: 0 route changes**; 11 EXPECTED_ARCHITECTURE_CHANGE (target authority + A3 insertion), 12 KNOWN_PLAN8_DEPENDENCY (`clarification_required` / `required_capabilities=[]` on T4 rows incl. all 8 paraphrases — recorded, **not** patched), **0 REGRESSION**, 0 UNEXPLAINED; no baseline refreshed, no test weakened. **Live sample (2 rows, small by policy):** `p6.spl.draft` T2 merge with `spl_postprocessor`, fingerprint `99ccd9213e2f0b37` identical to Arm A, 29.8 s; `p6.para.003` T4 **accepted in 19.9 s** with `proposed_fields`/`accepted_fields` populated in the live bundle — closing the C3 instrument gap end-to-end. Explicitly **not** established here: serving reliability, latency, concurrency, model-unavailable behaviour, recovery — those remain **D1**.

- [x] **D1** — Reliability and failure behaviour on the target posture
  - **Do:** Repeat the Plan 6 F3 classes against the new authority: restart/recreate,
    concurrency, repeated identical requests, latency p50/p95, LLM unavailable, malformed LLM
    output, LLM timeout, DB failure/recovery, MCP unavailable, model-slot pressure. Assert no
    duplicate side effects and bounded safe degradation. Surface: VPS.
  - **C3 model-health requirement (reliability, not a new workstream — no new sidecar or
    service):** `model unavailable/unhealthy → existing deterministic health detection →
    existing infrastructure/process recovery → model restart → health verification → at most one
    governed retry when retry-safe → otherwise deterministic fallback/clarification`. Rules: the
    LLM never decides to restart itself; restart uses the existing VPS process/container/service
    management mechanism; no uncontrolled restart loop; no full investigation replay merely
    because the model restarted; **cold-start/restart latency recorded separately from warm
    inference**; a failed restart degrades safely.
  - **Failing-first:** a missing failure-class row fails the item. Do not weaken tests.
  - **Verify:** `docs/evals/plan7/runs/<ts>/d1_reliability.md`, one row per class.
  - **Depends on:** D0
  - **Evidence:** `docs/evals/plan7/runs/20260815T140000Z/d1_reliability.md` + `d1_reliability.json` + `d1_db_failure.json`. **All ten mandatory classes measured**, target flags read back from the container (exec ON, v2 OFF, T4 ON @120, live-cap OFF, `MCP_MODE=mock`). **Taxonomy fixed first:** `sidecar_governance` reported every provider exception as `timed_out`; added `failure_kind` (`timeout`/`provider_unavailable`/`pool_rejected`/`slot_busy`) + note `llm_provider_unavailable`, keeping `timed_out` semantics for existing callers, exposed on `debug_summary`, 7 failing-first tests. Results: restart/recreate **PASS** (app container only, post-restart rows identical to D0, model untouched); concurrency **PASS** (3/3, 3 distinct traces); repeated identical **PASS** (identical schedules, gate delta 0/0); latency **PASS** (orchestration p50 **853 ms** / p95 **993 ms**; live-model latency remains C3's p50 ≈36 s); LLM unavailable **PASS** (`provider_unavailable`, `timed_out=False`); malformed **PASS** (`schema_invalid`); timeout **PASS** (`timed_out=True`, `failure_kind=timeout`) — the three now mutually distinguishable; DB failure/recovery **PASS with finding**; MCP unavailable **PASS** (`requires_human_review`, no exception to caller); model-slot pressure **PASS** (1 acquired, 2 shed `slot_busy` in ~2.4 s). **No duplicate side effects anywhere** — `gate_calls: 1, allowed: 0` for the whole run. **`HUMAN_RESTART_REQUIRED` did not occur**; the Cisco model was never restarted. Two flaws in my own harness were corrected rather than reported: the first slot-pressure row used an instant provider and never contended the semaphore, and rows were truncated at 900 chars then lost when the restart row wiped container `/tmp`. **Carried forward:** F1 DB loss silently downgrades authority to `canonical_non_planned` while still answering (`KNOWN_PLAN8_DEPENDENCY`, REL0); F2 `/v1/models`=200 through an unusable model (`KNOWN_PLAN8_DEPENDENCY`, REL0); F3 serving stability unresolved (C3 carry-over). D1 completion is not production GO.

- [x] **D2** — Persist the target profile and prove restart persistence
  - **Do:** Write the approved target flags into the configuration path proven in P0.1;
    `--force-recreate`; re-capture effective flags; re-run representative smoke. Surface: VPS.
  - **Failing-first:** post-recreate flags not matching the approved target profile fails D2.
  - **Verify:** `docs/evals/plan7/runs/<ts>/d2_persistence.md` with pre/post booleans and the
    observed execution authority (`degrade_reason` must not show v2 winning).
  - **Depends on:** D1
  - **Evidence:** `docs/evals/plan7/runs/20260815T145000Z/d2_persistence.md`. Persistent path is the **P0.1-proven** one: compose loads `env/profiles/${AI_SOC_ENV_PROFILE:-coe}.env.example` then `.env` (later wins); host profile is `development`, so `.env` decides. All six approved target values verified key-by-key as durably present there (no secret values recorded). Recreate: `docker compose up -d --force-recreate backend` — **application container only**; **Cisco model NOT restarted** (`llama-server` PID 217320, uptime continuous 01:36:20 → 01:36:48); `HUMAN_RESTART_REQUIRED` did not arise. Post-recreate health **200** and **all six effective flags match target exactly (0 failures)**: LangGraph `true`, exec `true`, v2 `false`, T4 `true`, T4 timeout `120`, live-cap `false`; `MCP_MODE=mock`. Representative smoke (6 rows, recorded T4 — no semantic corpus): **4 rows** `resource_plan_step_walk` with merge active, `spl_postprocessor` inserted on **every** seam row, **3 rows** T4 invoked+accepted, simple/non-planned rows work, `execution_eligible` null on all 6. **`V2_WINS` / dispatch-v2 ownership: 0 rows**, `downgrade_reason` null throughout. A3 preserved (contract re-insertion observed; 42 targeted tests pass). Repo `config.py` defaults, model/provider, serving config, MCP scope, capability policy and `architecture.md` all unchanged. **New finding for D3/E2:** persistence rests on the **uncommitted** `.env`, whose tracked counterpart (`development.env.example`) holds the opposite posture (exec `false`, v2 `true`, T4 keys absent) — so the target survives recreate but would not survive a config rebuild; committing those values would be a repo-default change D2 may not make. F1/F2/F3 carried forward unchanged; D2 PASS is not production GO.

- [x] **D3** — Rollback drill on the new authority
  - **Do:** Roll back to the Plan 6 recorded profile (exec OFF, v2 ON, T4 OFF), verify, then
    re-apply the target profile and verify again. Update
    `docs/evals/plan7/rollback_runbook.md`; it must touch the profile named by
    `AI_SOC_ENV_PROFILE`, not just `.env`. Surface: VPS.
  - **Failing-first:** if rollback smoke still shows the new authority active, rollback failed.
  - **Verify:** both directions recorded; host left in the **target** profile.
  - **Depends on:** D2
  - **Evidence:** `docs/evals/plan7/runs/20260815T151500Z/d3_rollback.md`; runbook created at `docs/evals/plan7/rollback_runbook.md`. Rollback values taken from committed Plan 6 evidence, not memory: exec `false`, v2 `true`, T4 unset→`false`, timeout unset→`2.0`, live-cap `false`. Applied by commenting the four Plan 7 override lines in `.env` (file not recreated, secrets and unrelated keys untouched) so the tracked seed + code defaults supply the posture, then `docker compose up -d --force-recreate backend`. **Rollback verified:** all six effective values exact, health 200, and the new authority genuinely inactive — `merge_active` **0/5**, no `inserted_phases`, `t4_invoked` **0**, `langgraph_v2_cursor` visible = **`EXPECTED_ROLLBACK_AUTHORITY`**, `execution_eligible` null, no mixed posture. **Recorded reading caveat:** `dispatch_source` still says `resource_plan_step_walk` with exec OFF — that is the step-walk label, not execution-contract authority (`executor.py:247` returns early); the real discriminators are `merge_active` / `inserted_phases` / `t4_invoked`. **Target re-applied** by removing the prefixes + recreate: `.env` **byte-identical** to the pre-rollback backup, flag-block hash `9613fc2cea1e4c77` before and after, 138→138 lines; all six flags exact, health 200, `merge_active` **4 rows**, A3 `spl_postprocessor` inserted on every seam row, T4 invoked **3 rows**, **`V2_WINS` 0 rows**, `execution_eligible` null on all 6. **Host left in TARGET posture.** **Cisco restart: NO** — `llama-server` PID 217320, unbroken uptime `01:48:39 → 01:52:36` across both recreates. **Config-rebuild comparison (read-only, `.env` never deleted):** `CONFIG_REBUILD_DRIFT = CONFIRMED` — 4 of 6 flags would NOT survive a rebuild from the tracked seed (exec→false, v2→true, T4→absent/false, timeout→2.0). Disposition **A — `TARGET_PERSISTENCE_SUFFICIENT_FOR_CURRENT_VPS_OPERATION_BUT_CONFIG_REBUILD_DRIFT_REMAINS_E2_BLOCKER`**; not remediated (would change tracked deployment defaults, unauthorized in D3) and not self-approved as accepted risk. F1/F2/F3 carried forward unchanged.

---

## E — new go-live gate

- [x] **E0** — Plan 7 report
  - **Do:** `docs/evals/plan7_architecture_authority_report.md` answering the twelve success
    questions with artifact citations. State the persistent profile separately from repo
    defaults. Honest about anything still unproven. Surface: LOCAL.
  - **Verify:** every number traces to `docs/evals/plan7/`; no claim that frozen `--arm both`
    observed L4/L5; parity `120 exact` never cited as routing correctness; `V2_WINS` never
    described as activation.
  - **Depends on:** D3
  - **Evidence:** `docs/evals/plan7_architecture_authority_report.md` answers all 12 success
    questions with the required verdict/evidence/explanation/gap structure and committed-artifact
    traceability; it separates effective VPS posture from tracked/code defaults, retains the D3
    `dispatch_source` caveat, F1/F2/F3, config-rebuild drift, A7, Plan 8 and live-MCP limits, and
    makes no GO/risk-acceptance decision. Structure check **12/12**; `git diff --check` and staged
    diff check clean; plan-discipline audit **0 gaps**.

- [x] **E1** — Closure gates
  - **Do:** Full forecast-rule set: governance regression, backend pytest, parity, Cisco,
    probes, sentinel, path, protected manifest, invariants, plan-discipline audit. Revert only
    the six stale reports. Surface: LOCAL.
  - **Verify:** governance PASS; pytest green vs the P0 baseline; truth-set `--check` 0
    regressions; parity `120 exact`; Cisco `50/0/0`; probes `10/10`; sentinel `17/17`; path
    `105/105`; manifest N/N; invariants 7/7; plan audit 0 gaps.
  - **Depends on:** E0
  - **Evidence:** `docs/evals/plan7/e1_closure_gates.md` — **11/11 gates PASS** in the isolated
    worktree `/var/www/ai-soc-assistant-plan7-e1` @ `6ecf6c4`: governance `stage3_governance_regression: PASS`
    (harness 6/6, dispatch matrix 5/5); pytest `5335 passed, 3 skipped, 6 xfailed, 0 failed`;
    truth set 0 regressions (64/76); parity `exact=120 approved=0 critical=0`; Cisco
    `PASS=50 REVIEW=0 FAIL=0 CRITICAL=0`; probes 10/10; sentinel 17/17; path 105/105; manifest
    15/15; invariants 7/7; plan audit 0 gaps. Attempt 2 was aborted by an external shared-worktree
    checkout (no Plan 7 commit lost) and resumed from an isolated worktree. The one repository
    change is an `INCOMPLETE_CONVERGENCE_COMMIT` manifest hash recapture for the artifact
    authorized by `5810000` (1 file, 1 line); no baseline refreshed, no test weakened. Two
    gitignored-only `ENVIRONMENT_DRIFT` reconstructions are disclosed in the evidence. A7,
    F1/F2/F3, `CONFIG_REBUILD_DRIFT=CLOSED (development)` and `live_mcp_unproven` carried
    forward unchanged; no GO/NO-GO decision.

- [ ] **E2** — `P7_PRODUCTION_GO_LIVE_V2` **STOP**
  - **Do:** Present the full matrix: Functional, Safety, Performance, Reliability,
    Security/RBAC, Observability, Deployment/restart persistence, Rollback, Corpus, Production
    flags, **ResourcePlan production authority**, **T4 serving posture**, **Execution seam
    posture**, MITRE governance, **Live MCP/Splunk scope**, Critical blockers, Accepted risks.
    Verdicts are only PASS / BLOCKER / ACCEPTED RISK / NOT IN PRODUCTION SCOPE ⋅ UNPROVEN.
    `GO LIVE` requires **zero** critical blockers, ResourcePlan authority actually active with
    v2 OFF, **A7 proven**, **and all three T4 conditions below**. Do **not** choose the outcome.
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
