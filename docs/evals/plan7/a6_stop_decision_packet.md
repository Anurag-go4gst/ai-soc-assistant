# Plan 7 A6 — `P7_DISPATCH_V2_RETIREMENT` decision packet

**STOP. The decision is the user's. No outcome is selected here.**

Question: may **dispatch-v2 remain OFF as the normal execution authority**, with
ResourcePlan + PhaseContract + the deterministic compiler carrying production dispatch?

Evidence: `a3_ownership_fix.md`, `a4_authority_acceptance.md`, `a5_old_path_audit.md`,
`a1_structural_population.md`, `runs/target_profile_baseline.md`.

## Exact effective flags (read back from the running backend)

```
LANGGRAPH_ORCHESTRATION_ENABLED                  = true
AI_SOC_RESOURCE_PLAN_EXECUTION_ENABLED           = true
AI_SOC_PIPELINE_DISPATCH_V2_ENABLED              = false
AI_SOC_T4_SEMANTIC_UNDERSTANDING_ENABLED         = true
AI_SOC_T4_SEMANTIC_UNDERSTANDING_TIMEOUT_SECONDS = 2.0
AI_SOC_LIVE_CAPABILITY_ENFORCEMENT_ENABLED       = false
MCP_MODE                                         = mock
```

Repo `config.py` defaults unchanged. Host profile still `AI_SOC_ENV_PROFILE=development`.

## Remaining missed mandatory work

**0 measured.**

| Measure | Before A3 | After A3 |
|---|---|---|
| Structural population (175 rows swept) | 5 affected offline + 1 runtime-only | **0 affected** |
| Target-posture corpus (12 rows) | 2 rows lost the SPL lifecycle | **0 rows** |
| Merge authoritative | 6/12 | **8/12** |

Residual **risk** (not measured loss): `_run_legacy_dispatch_fallback` still skips
`spl_postprocessor` and remains reachable via `session_spl_refine`. It executed **0 times** in
this corpus, so its behaviour on the target posture is *unexercised*, not proven safe.

## Duplicate work

**0.** No repeated hook in `executed_hooks` on any of the 12 traces; no trace carries both a
merged schedule and a legacy/predicate schedule; `canonical_execution_idempotency` unchanged.

## Structural population after the fix

`scripts/eval_plan7_a1_population.py --corpus all` — 175 rows: **0 affected**, 163 merged (was
158). Benign classes unchanged: 11 `empty_resource_plan` (clarification lane), 1 narration-only
`alert_summary`. Compiler verdicts identical — A3 did not touch resource compilation.

## A4 corpus result

12/12 exit 0, `missing_qualification_tier` none, **0 route/tier/fingerprint deltas** vs the
pre-fix run on the same posture. All 12 acceptance criteria pass: 0 missed work, 0 duplicates,
0 double-run, SPL validation preserved, `execution_eligible` null everywhere, MCP gate never
allowed without validation, HIL required where owed, RBAC untouched, contract phases honoured,
inline `mitre_finalize` represented **and** executed.

Two findings worth the user's attention:

1. **`spl_postprocessor` is contract-inserted on every SPL row, healthy ones included** (4 rows
   beyond the 2 defect rows). The compiler never schedules it by design — so any path that loses
   the merge loses deterministic SPL validation. This raises the stakes of item 2 below.
2. **A new governed refusal appeared** on `bb38d292`: the restored phase produced
   `spl_validation_failed` + HIL `source_profile_slots_missing`. That row previously reached the
   gate with validation never having run. Work being done, not a regression.

## Any old path still active

| Path | Rows | Status |
|---|---|---|
| `resource_plan_step_walk` (target architecture) | 8 | active, merge authoritative |
| `canonical_non_planned` | 2 | legitimately separate |
| knowledge/rag-only (no `plan_dispatch`) | 2 | legitimately separate |
| `legacy_predicate` | 0 | not exercised |
| `session_spl_refine` → `_run_legacy_dispatch_fallback` | **0** | **reachable but unexercised** |
| `guided_hybrid` | 0 | not exercised |

## Migration debt / legitimate separation / regressions (A5)

- **Migration debt — 1:** `_run_legacy_dispatch_fallback` skips `spl_postprocessor` and stays
  reachable via `session_spl_refine`.
- **Legitimately separate — 4:** `canonical_non_planned`, rag-only lane, `v2_cursor_synthesis`,
  `ec_demo`.
- **Regressions — 0.**
- Seam inventory unchanged: **2 SEAM / 4 DECISION_REQUIRED / 4 KEEP_SEPARATE, 0 adopted.**

## Can dispatch-v2 remain OFF?

**Evidence in favour:** on the measured corpus the target architecture carried every planned row
with 0 missed mandatory work, 0 duplicates, 0 double-runs and 0 route/tier/fingerprint drift; the
one structural defect that justified Plan 6's `KEEP OFF` is closed and pinned by tests; the
population sweep finds no remaining instance across 175 rows.

**Evidence against / not yet in hand:**

1. `_run_legacy_dispatch_fallback` is unexercised on this posture and still skips a phase now
   known to be mandatory on every SPL row.
2. Coverage is 12 corpus rows + a 175-row planning-layer sweep — **not** the 105 goldens or
   Cisco 50 executed end-to-end on the target posture.
3. MCP remains `mock`; `live_mcp_unproven` from Plan 6 still stands.
4. T4 is ON and still failing at the 2.0 s bound (0 accepted contracts) — a Plan 7 **hard GO
   requirement** at E2, untouched by this decision.
5. dispatch-v2 supplies bounded pre-SPL MCP discovery; with v2 OFF that enrichment is absent.
   No corpus row required it, but no measurement here proves it is unnecessary in production.

## Rollback cost

Low and proven: restore the backed-up `.env` and `docker compose up -d --force-recreate backend`
(`docs/evals/plan6/rollback_runbook.md`, executed for real in Plan 6 F4). The A3 code change is
inert when `AI_SOC_RESOURCE_PLAN_EXECUTION_ENABLED=false` — `executor.py:247` returns before any
execution-contract code, so flag-OFF is byte-identical by construction. Reverting the flag does
not require reverting the code.

## Decision required

Record one:

1. **`V2_OFF_IS_NORMAL_AUTHORITY`** — dispatch-v2 stays OFF; ResourcePlan + PhaseContract carry
   production dispatch, with items 1–5 above tracked as open risks.
2. **`V2_OFF_PENDING_WIDER_EVIDENCE`** — keep v2 OFF in the remediation posture but do not yet
   call it normal authority; require the goldens/Cisco corpora end-to-end and/or a
   `session_spl_refine` exercise first.
3. **`RESTORE_V2`** — turn dispatch-v2 back ON pending further work.

Not decided here, and not affected by this STOP: T4 stays ON at 2.0 s, live capability
enforcement stays OFF, no seam is adopted or retired, and `config.py` defaults stay unchanged.
