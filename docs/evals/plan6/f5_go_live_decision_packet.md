# Plan 6 F5 — `P6_PRODUCTION_GO_LIVE` decision packet

**STOP. The decision is the user's. No outcome is selected here.**

Plan: `plans/2026-08-13_1440_production-activation-t4-serving-and-governance-readiness.md`
— **33/37** items checked (F5, G0, G1, G2 remain). Branch `feat/plan6-production-activation`,
PR **#132** (draft), head `22b7055`. Not merged to `master`.

## Recorded production profile (persisted and re-applied)

| Flag | Repo default (`config.py`) | Persistent VPS profile | Effective now |
|---|---|---|---|
| `AI_SOC_RESOURCE_PLAN_EXECUTION_ENABLED` | false (`:410`) | **false** (explicit) | `false` |
| `AI_SOC_PIPELINE_DISPATCH_V2_ENABLED` | false (`:403`) | **true** | `true` |
| `AI_SOC_T4_SEMANTIC_UNDERSTANDING_ENABLED` | false (`:413`) | **false** (omitted from git profiles) | `false` |
| `AI_SOC_T4_SEMANTIC_UNDERSTANDING_TIMEOUT_SECONDS` | 2.0 (`:414`) | **2.0**, not raised | 2.0 |
| `AI_SOC_LIVE_CAPABILITY_ENFORCEMENT_ENABLED` | false (`:417`) | **false** (explicit) | `false` |
| `MCP_MODE` | — | `mock` | `mock` |

Repo `config.py` defaults were **not** changed. Reference: `production_flag_profile.md`,
`runs/f2_persistence.md`, `rollback_runbook.md`.

## Evidence matrix

| Category | Verdict | Evidence |
|---|---|---|
| **Functional** | **PASS** | 12-row VPS corpus 12/12 exit 0 post-recreate (`runs/20260814T031208Z/`); zero route / `qualification_tier` / `resource_plan_fingerprint` drift vs Arm A; `missing_qualification_tier` none |
| **Safety** | **PASS** | F1 seven invariants PASS on F0 traces (`vps_safety_invariants.md`); `/invariant-check` **7/7** on the Plan 6 runtime diff; `execution_eligible` null and `execution_enabled=false` on every F3 turn; HIL raised whenever owed; no LLM→MCP path |
| **Performance** | **ACCEPTED RISK** | p50 **92.9 s**, p95 **182.1 s** post-recreate vs 92.6 s / 182.6 s pre-recreate (Δp50 +0.4 %). No Plan 6 regression, but absolute latency is the known shared-VPS CPU-contention envelope for the on-prem 8B — an accepted operating characteristic, not a fixed defect |
| **Reliability** | **PASS** | F3 all failure classes recorded (`runs/f3_reliability.md`): LLM unavailable 1.07 s, malformed output 1.82 s, LLM timeout 181.8 s bounded, model-slot pressure ×3, DB failure→recovery. Every class fail-closed, HTTP 200 deterministic fallback or honest 401, no hang, no fabricated rows |
| **Security / RBAC** | **PASS** | DB outage → session auth refuses (401), no unauthenticated answer; MCP never allowed to execute; HIL/`precondition_review` raised on gated turns; env capture rejects secret-shaped keys; no secrets in any artifact |
| **Observability** | **PASS** | Redacted `resolved_query` + `schedule` blocks on `/debug` `debug_summary`, retained through the 64 KiB telemetry slim keep-list; `ai_trace_runs` 21/21 distinct; `telemetry.write_failures=0` |
| **Deployment / restart persistence** | **PASS** | `--force-recreate` ×4 across F2/F3/F4, health 200 each time; post-recreate corpus reproduces pre-restart routing and schedule identity exactly |
| **Rollback** | **PASS** | Drill executed, not simulated (`rollback_runbook.md`): rollback → all three flags unset, smoke 3/3 identical to Arm A; re-apply → approved profile restored, smoke 3/3, host left in the **intended** state |
| **VPS corpus** | **PASS** | 12/12 with per-class coverage; success questions cite artifacts under `docs/evals/plan6/` |
| **Production flags** | **PASS** | Persisted, recreated, and re-captured after rollback; `config.py` defaults unchanged; no new env flag introduced anywhere in Plan 6 |
| **ResourcePlan production authority** | **NOT IN PRODUCTION SCOPE** | C0 = **KEEP OFF**. Arm C proved `merge_schedule` is reachable and executes (5/12; 7/12 legitimately `merge_not_reachable`), but v2-OFF would drop `spl_postprocessor` on two rows — known missed work. **Merge architecture is proven experimentally and is not production-authoritative.** Current production authority remains **dispatch-v2** |
| **T4 serving posture** | **NOT IN PRODUCTION SCOPE** | D3 = **KEEP DEFAULT-OFF**, timeout stays **2.0 s**. D0/D1 showed the hop is invoked on T4 and never accepted at 2.0 s, and **no viable serving posture exists in-environment** (no second endpoint, no Qwen, `-np 1` single decode slot, box already swapping 4096/4096 MB). Eight T4 paraphrases stay `DEFERRED_T4_SEMANTIC_SERVING_LIMIT` |
| **Execution seam posture** | **NOT IN PRODUCTION SCOPE** | C3 = **KEEP 0 ADOPTED**; `_run_legacy_dispatch_fallback` retained. Deferred architectural follow-up, not a go-live blocker while exec stays OFF |
| **MITRE governance posture** | **ACCEPTED RISK** | E2 = `DEFERRED_SEPARATE_GOVERNED_PROMOTION`. DRAFT stays one curation commit ahead on 11 rows; drift ledger matches measured drift both directions (`test_question_runtime_map_draft_drift.py` 5 passed); promoter not run; protected manifest **15/15** |
| **Live MCP / Splunk scope** | **UNPROVEN — `live_mcp_unproven`** | No endpoint or credentials on this host (`SPLUNK_MCP_BASE_URL`/`TOKEN` empty, `MCP_MODE=mock`). Controlled read-only live search **not run**; mock evidence **not** substituted. Fail-closed coverage only: `47 passed`, `block_reason=splunk_mcp_not_configured`. **Live Splunk/MCP investigation cannot be claimed production-ready** (`runs/f3_live_mcp.md`) |
| **Critical blockers** | **0** | No category is BLOCKER. Unproven and out-of-scope items are scope limits, not defects |
| **Accepted risks** | 3 | (1) absolute latency on the shared VPS; (2) MITRE DRAFT drift deferred to a separate governed promotion; (3) mock-MCP-only evidence for the MCP execution lane |

## Explicit statements required at this STOP

- **`live_mcp_unproven`.** Live Splunk/MCP investigation is **not** production-enabled or
  proven. Any GO decision covers only the capabilities Plan 6 actually proved.
- **ResourcePlan merge architecture was proven experimentally but is not
  production-authoritative.**
- **Current production authority remains dispatch-v2, because C0 selected KEEP OFF.**
  `exec ON + v2 ON` would be `V2_WINS` and must never be presented as Plan-5 activation.
- **T4 remains deferred because no viable serving posture was demonstrated** — not because
  the routing table is defective.

## Options (evidence-supported; choose one)

1. **`GO LIVE WITH RECORDED PROFILE`** — scoped to the proven capabilities only: deterministic
   routing, governed SPL drafting with HIL, RAG/knowledge answers, mock-MCP execution lane,
   `/debug` observability. Critical blockers = **0**, so this option is available. It must be
   published with `live_mcp_unproven` stated, and must not claim live Splunk investigation,
   ResourcePlan execution authority, or T4 semantic understanding.
2. **`DEFER`** — hold production sign-off until live Splunk/MCP is provable (credentials +
   endpoint), then re-run F3's controlled read-only test and re-present F5.
3. **`ROLL BACK AND KEEP OFF`** — apply `rollback_runbook.md` to return to the pre-F2 Arm A
   posture and keep the recorded profile unpublished.

Once the outcome is recorded, G0 (report), G1 (docs alignment) and G2 (closure gates) follow.
G2 must not merge; merge to `master` stays user-only.
