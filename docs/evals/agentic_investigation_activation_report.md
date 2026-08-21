# Agentic investigation — architecture activation report

**Branch:** `feat/agentic-investigation-production` · **PR #156**
**COE runtime:** `/var/www/ai-soc-assistant` · **Implementation checkout:** `/var/www/ai-soc-mcp`
**COE runtime commit observed by final audit:** `f1bf40d30a2a8f188564dd21ee02e49193511fc8`
**Date:** 2026-08-21

Every phase is reported on three independent axes. A missing external dependency
defers a **live proof**; it never defers implementation and never disables a feature.

---

## 1. Architecture implementation

| Phase | Implementation | Feature activation | Live external proof |
|---|---|---|---|
| P0 plan-before-ResourcePlan | PASS | ENABLED | n/a |
| P1 CapabilitySnapshot | PASS | ENABLED | n/a |
| P2 guided unveto + composable planning | PASS | ENABLED | n/a |
| P3 investigation planner + DET validation | PASS | **ENABLED** | `LIVE_REASONING_PROOF = DEFERRED_COE_CONFIGURATION` |
| P4 Run/Edit/Cancel + envelope | PASS | ENABLED (rides P0) | n/a |
| P5 compiler + RP execution/sufficiency seam | PASS | ENABLED | n/a |
| P6 repeated tools + exact-call AUTH0 | PASS | ENABLED | `LIVE_SPLUNK_PROOF = DEFERRED_COE_CONFIGURATION` |
| P7 bounded read-only PlanDelta | PASS after audit correction | pre-audit shared seam enabled; corrected independent seam requires deploy | `LIVE_REASONING_PROOF`, `LIVE_SPLUNK_ITERATION_PROOF` = DEFERRED |
| P8 InvestigationOutcome v2 | PASS | ENABLED | n/a |
| P9 domain workers | `SKIPPED_NOT_REQUIRED` | no flag exists | n/a |
| P10 remediation plan + Approve/Edit/Cancel | PASS | **ENABLED** | `LIVE_REMEDIATION_REASONING_PROOF = DEFERRED_COE_CONFIGURATION` |
| P11 governed action connectors + verify | PASS | **ENABLED** (email) | `LIVE_OUTBOUND_SEND_PROOF = PENDING_OPERATOR_STEP` |
| P12 SOP/policy seed | PASS | published | n/a |
| P13 E2E acceptance | PASS | n/a | live lifecycle driven; see §5 |

The final conformance audit restored the approved independent
`AI_SOC_PLAN_DELTA_ENABLED` default-false runtime seam. It is a phase rollback control,
not an infrastructure-readiness flag. The currently deployed pre-audit runtime does not
read this key and must be redeployed before its P7 state can be reported against the corrected code.

---

## 2. Active feature state (COE)

```
AI_SOC_INVESTIGATION_PLAN_BEFORE_RESOURCE_PLAN_ENABLED = true
AI_SOC_CAPABILITY_SNAPSHOT_ENABLED                     = true
AI_SOC_GUIDED_COMPOSABLE_PLANNING_ENABLED              = true
AI_SOC_INVESTIGATION_PLANNER_ENABLED                   = true    # P3
AI_SOC_PLAN_DELTA_ENABLED                              = absent  # corrected code not yet deployed
AI_SOC_RESOURCE_PLAN_EXECUTION_ENABLED                 = true
AI_SOC_INVESTIGATION_OUTCOME_V2_ENABLED                = true
AI_SOC_REMEDIATION_PLANNER_ENABLED                     = true    # P10
AI_SOC_ACTION_EMAIL_ENABLED                            = true    # P11
MCP_GLOBAL_EXECUTION_ENABLED                           = true
MCP_MODE                                               = mock
```

No infrastructure-readiness flag exists. `AI_SOC_REASONING_READY`, `AI_SOC_SPLUNK_LIVE`,
`AI_SOC_MODEL_AVAILABLE` and `AI_SOC_MCP_AVAILABLE` are absent by construction and pinned
absent by `test_p13_investigation_e2e.py::test_no_infrastructure_readiness_flags_were_introduced`.

---

## 3. Live COE dependency state

| Dependency | State | How it is represented |
|---|---|---|
| Foundation-Sec **instruct** | reachable, heavily CPU-starved (~0.87 tok/s measured) | `local_primary` in the failover chain |
| Foundation-Sec **reasoning** | **not configured** | reasoning roles degrade to the chain's next hop; planner records `llm_timed_out` / `circuit_open` / `turn_budget_exhausted` and falls back to the DET baseline |
| Splunk MCP | `MCP_MODE=mock`, `SPLUNK_MCP_BASE_URL` empty | CapabilitySnapshot availability + execution gate; no live claim made |
| Email (SMTP) | configured, allowlist resolves | `email_send` adapter registered; send still needs an approved envelope + allowlisted recipient |
| Agilius / SOAR / firewall / ITSM | **not onboarded** | no adapter row ⇒ `UNAVAILABLE` / manual step; never `SUCCESS` |

---

## 4. Deferred live proofs

- `LIVE_REASONING_PROOF` — plan quality, warm/cold latency, model-specific timeout and
  circuit behaviour, for P3, P7 and P10.
- `LIVE_SPLUNK_PROOF` / `LIVE_SPLUNK_ITERATION_PROOF` — one governed search under envelope
  + AUTH0, and an adaptive second hop.
- `LIVE_OUTBOUND_SEND_PROOF` — one real allowlisted remediation email after approval.
- Agilius / SOAR / firewall — not onboarded; deferred until each is registered, discovered
  and allowlisted.

---

## 5. Degraded-mode full-stack test

All implemented P0–P12 features enabled **simultaneously**, with the reasoning endpoint
unconfigured and Splunk in mock.

| Requirement | Result |
|---|---|
| `/chat` remains healthy | PASS — `/api/health` 200 throughout |
| investigation-plan UX produced | PASS — readable plan + `awaiting_approval` |
| Run / Edit / Cancel works | PASS — Run → immutable envelope v2 |
| ResourcePlan only after approval | PASS — `resource_plan_present=false` pre-approval |
| unavailable model handled safely | PASS — timeout 90.1 s → DET baseline; circuit open → 0 ms skip; budget exhausted → 0 ms skip |
| unavailable MCP handled safely | PASS — execution `skipped`, no tool selected, no fabricated rows |
| EvidenceState preserved | PASS |
| honest incomplete/degraded outcome | PASS — `incomplete` / `inconclusive` |
| does not fabricate evidence | PASS — progress states when a step produced none |
| does not revert to RAG-only | PASS — `capability_snapshot_rows=11` with honest unavailable rows |
| no chain-of-thought exposed | PASS — progress is operational only |
| no writes executed | PASS — `execution_authorized=false`; no connector called |

Measured degraded latencies: planner timeout 90.1 s (inside a 235 s turn deadline);
circuit-open skip 0 ms → 1.2 s turn; budget-exhausted skip 0 ms; remediation hops 1.1 s.

---

## 6. Defects found by live probing

1. **Unbounded reasoning hop.** P3 (120 s) and P7 (30 s) ignored the turn wall clock. Both
   now cap to the remaining budget and skip with `turn_budget_exhausted`. (`16371f9e`)
2. **Fail-closed by crash.** A stale or foreign version-bound Run/Edit/Cancel raised to the
   unhandled backstop, so `/chat` answered HTTP 500. Now a governed 409 with a stable reason
   code. (`938b1006`)
3. **Wrong remediation vocabulary.** Tier-1 answer affordances (`summarize`, `explain`, …)
   were treated as remediation actions, producing steps like "Perform summarize manually".
   Now filtered; unrecognized identifiers are kept as honest manual steps. (`1c9bc084`)
4. **Approval lost between turns.** Create and Approve arrive on separate `/chat` turns and
   nothing carried the plan, so Approve failed with `remediation_plan_missing_for_approval`.
   The first attempt wrote session pins from the remediation runtime and did not survive:
   `pins_from_pipeline_state` rebuilds the whole pin record at the end of every turn and
   overwrote it. The pin builder now carries the shown plan forward — one writer — and
   clears it on approve/cancel/decline so a stale plan cannot be re-approved.
   (`1c9bc084`, `7f7ca7fc`, `f1bf40d3`)

   Every unit test passed throughout, because they called the runtime directly and never
   crossed a turn boundary. The test now exercises the real writer across that boundary.

**Live confirmation after the fix:** Create → 4 steps shown → Approve → immutable envelope
v1, `plan_fingerprint 416dff577da9`, approved steps identical to the shown steps.

---

## 7. Out of scope — measured, not fixed

`spl_t2_producer` turn latency. Two suite scenarios routing to `spl_generation_only` (not
investigation-shaped; P3 never fires) took **303 s** and **182 s**, with `llm_calls: []` in
the trace while three 90 s `local_primary` hops appear in the backend log. That role does not
participate in `TurnLlmBudget` accounting. It is a pre-existing latency defect in a role no
phase of this plan owns, and needs its own decision.

---

## 8. Gates

| Gate | Result |
|---|---|
| backend pytest (implementation checkout) | **6048 passed**, 0 failed, 6 skipped, 6 xfailed |
| P13 E2E acceptance suite | 38 passed |
| P0–P13 investigation slice | 90 passed |
| production frontend `npm run build` | PASS |
| governance regression `./scripts/run_stage3_governance_regression.sh` | **PASS** |
| ↳ soc_clean_answer_eval | 120/120 pass, 0 review, 0 fail, 0 critical |
| ↳ sentinel | 17 passed |
| ↳ SPL template audit | 19/19, 0 review_required |
| ↳ Cisco power-grid catalogue gate | 50 PASS / 0 REVIEW / 0 FAIL / 0 CRITICAL |
| ↳ pipeline dispatch matrix | 5/5 |
| ↳ protected-artifact manifest `--check` | ok |

The `audit_critical_planning_event_not_persisted` warnings in that run are expected: the
branch only logs when the reason is `canonical_db_disabled`, which is the eval harness's
own configuration. A genuine persistence failure raises
`AuditCriticalTelemetryPersistenceError` instead, so fail-closed is intact.

Baselines advanced during this work, each verified before touching and none advanced to
silence a finding:

- **RACES freeze → `9f1ec922`.** P10/P11/P13 changed `pipeline.py`, `responses.py` and
  `ChatPanel.tsx` as production investigation work; no EC/demo authority entered the live path.
- **Sentinel re-frozen.** The P12 Firewall Blocking SOP makes `pg.unsafe.001` cite policy and
  give procedural steps. Causation was confirmed against pre-seed fixtures, and the governance
  verdict is unchanged — still `out_of_registry` / `knowledge_recall` / `clarification_required`
  with `execution_eligible` null. Two additive sections on one row: the sanctioned re-freeze case.
- **Skill-KB fixture ordering re-normalized** through the existing importer after the P12 seed
  appended rows. Content unchanged (120 docs, seed present).

---

## 9. Production GO

Unchanged: **deferred**. Live reasoning, live Splunk, and a real outbound send remain
unproven on this host. The architecture is complete and active regardless.
