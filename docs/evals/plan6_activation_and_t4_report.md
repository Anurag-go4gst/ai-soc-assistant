# Plan 6 — production activation, T4 serving, and governance readiness

Plan: `plans/2026-08-13_1440_production-activation-t4-serving-and-governance-readiness.md`
Branch `feat/plan6-production-activation`, PR **#132** (draft, unmerged). Baseline `1d32ac6`
(Plan 5 merge SHA). Every number below traces to an artifact under `docs/evals/plan6/`.

**Outcome: `P6_PRODUCTION_GO_LIVE = DEFER`.** `GO LIVE WITH RECORDED PROFILE` was available
(critical blockers 0) and was **not** taken: Plan 6 proved the new architecture experimentally
but did not make it production-authoritative. See `docs/evals/plan6/f5_go_live_decision_packet.md`.

## Flag profiles — three different things

| Flag | Repo default (`config.py`) | Persistent VPS profile after Plan 6 | Plan 6 test arms |
|---|---|---|---|
| `AI_SOC_RESOURCE_PLAN_EXECUTION_ENABLED` | **false** (`:410`) — unchanged | **false** (explicit) | ON in Arms B/C |
| `AI_SOC_PIPELINE_DISPATCH_V2_ENABLED` | **false** (`:403`) — unchanged | **true** | OFF in Arm C |
| `AI_SOC_T4_SEMANTIC_UNDERSTANDING_ENABLED` | **false** (`:413`) — unchanged | **false** (omitted from git profiles) | ON in Arm D |
| `AI_SOC_T4_SEMANTIC_UNDERSTANDING_TIMEOUT_SECONDS` | **2.0** (`:414`) — unchanged | **2.0**, not raised | 2.0 / probes at 90 s, 180 s |
| `AI_SOC_LIVE_CAPABILITY_ENFORCEMENT_ENABLED` | **false** (`:417`) — unchanged | **false** (explicit) | never ON |
| `MCP_MODE` | — | `mock` | `mock` |

Repo defaults were **not** changed anywhere in Plan 6. No new env flag was introduced.

**Environment-profile correction:** `docker-compose.yml` loads
`env/profiles/${AI_SOC_ENV_PROFILE:-coe}.env.example` and then `.env`. This host sets
`AI_SOC_ENV_PROFILE=development`, so the committed profile actually in effect is
`env/profiles/development.env.example` — **not** `coe.env.example`, despite the standing
"COE host" framing. Found during the F4 drill; effective flags were still correct because the
F2 commit pinned the KEEP-OFF posture in both profiles.

## The twelve success questions

**1. Does the Plan 5 merged execution architecture work correctly on the actual VPS?**
Yes, where it is reachable. Arm C (exec ON, v2 OFF): `merge_executed` on **5/12** rows,
`merge_not_reachable` on **7/12** — the latter are `rag_only` / `no_schedulable_step` paths
that never hit `execute_plan_dispatch`, not activation failures. No HIL was dropped, SPL
validation held, MCP never executed. Artifact: `execution_off_on_comparison.md` / `.json`,
`runs/arm_c_merge.md`.

**2. Is it better/equivalent to the current production path?**
**Not yet equivalent.** With v2 OFF, two `workflow_spl` / `no_schedulable_step` rows
(`p6.multi.knowledge_spl_mcp`, `p6.live_posture.d1_003`) lose `spl_postprocessor` work that
dispatch-v2 supplies today. That is known missed work, and it is the reason C0 recorded
KEEP OFF. Artifact: `seam_equivalence.md`, `c0_d3_stop_decisions.md`.

**3. What latency/quality/safety cost does activation introduce?**
On the approved (exec OFF) profile: none measurable. Post-recreate corpus p50 **92,931 ms** /
p95 **182,120 ms** vs pre-recreate p50 92,587 / p95 182,638 — Δp50 **+0.4 %**, inside noise.
Zero route/tier/fingerprint drift. Safety unchanged: F1 seven invariants PASS,
`/invariant-check` 7/7. Artifacts: `runs/f3_reliability.md`, `vps_safety_invariants.md`.

**4. Can ResourcePlan execution become authoritative?**
**Not on this evidence.** C0 = **KEEP OFF**. Authority can move only after either the v2-OFF
missed-work cases are covered, or an explicitly approved execution-seam / `CHANGE_LADDER`
change. Both were out of Plan 6 scope. The F5 DEFER decision reopens exactly this work, in a
separate narrowly-scoped plan.

**5. Can any legacy/duplicate execution path be retired?**
**No.** C3 = **KEEP 0 ADOPTED**. Inventory unchanged: 2 SEAM, 4 DECISION_REQUIRED,
4 KEEP_SEPARATE, **0 adopted**. `_run_legacy_dispatch_fallback` retained — it still skips
`spl_postprocessor`, pinned by `test_fallback_legacy_branch_runs_no_spl_postprocessor`.
Artifact: `c3_stop_decision.md`, `seam_equivalence.md`.

**6. Can T4 resolve the eight residual paraphrases within an acceptable SLO?**
**No.** D0: T4 is invoked on T4 rows and skipped on T1–T3 (qualification is correct), but
**9/9** attempts timed out at ~2 s, **0** accepted contracts, **0** false capability widening.
D1: no viable alternate serving option exists in-environment — no second endpoint, Qwen not
configured, `llama-server -np 1` cannot yield a second decode slot, and the host is already at
swap 4096/4096 MB with 8.6 GB llama RSS. Probes at 90 s and 180 s still did not return the
required JSON, so raising the timeout is unsupported. `D1_PARAPHRASE_RESIDUE =
DEFERRED_T4_SEMANTIC_SERVING_LIMIT` — a serving limit, **not** a routing-table defect.
Artifacts: `t4_serving_baseline.md`, `t4_serving_options.md`, `t4_paraphrase_accuracy.md`,
`t4_residual_routing_l3l4.md`.

**7. What persistent flag profile should the VPS use?**
The table above: exec **false**, v2 **true**, T4 **false** at 2.0 s, live capability
enforcement **false**, `MCP_MODE=mock` — persisted, force-recreated, and re-captured after the
F4 rollback. Repo defaults stay conservative and unchanged. Artifacts:
`production_flag_profile.md`, `runs/f2_persistence.md`.

**8. Are declared PhaseContracts faithful to what actually executes?**
Improved and now observable, but still partial. E0 added `pipeline_inline_executed`
provenance for the MITRE/CVE phases that run inside `graph_node_context_finalize` rather than
the hook loop, surfaced as `schedule.inline_executed` on `debug_summary` alongside
`inline_mandatory`. On the approved profile `phase_names` is empty on every row because
execution is OFF — faithfulness under exec ON is only shown for Arm C's 5 merged rows.
Artifacts: `backend/app/planner/inline_execution_provenance.py`, `runs/arm_c_merge.md`.

**9. Which governance debts close now vs stay deferred?**
Closed: protected-artifact manifest fail-closed at **15/15** (E4 added **0** members —
`docs/evals/plan6/` is evidence, not runtime-authoritative). Deferred: MITRE DRAFT promotion
(E2 = `DEFERRED_SEPARATE_GOVERNED_PROMOTION`; the promoter is broader than an 11-row change
and would rewrite four catalog use cases, including dropping `T1110.003` on
`auth_failed_login_spike`); stale report refresh (E3 = **CONTINUE PRESERVING**). Artifacts:
`e2_stop_decision.md`, `e3_stop_decision.md`, `e4_protected_artifact_review.md`,
`mitre_11row_promotion_delta.md`.

**10. Is dispatch-v2 precedence resolved so v2 cannot silently win?**
Resolved as a **recorded decision**, not as a code change: C0 Field 2 is N/A because execution
stays OFF, and v2 stays ON deliberately. Arm B (exec ON + v2 ON) is `V2_WINS` —
`degrade_reason=dispatch_v2_projected_schedule` on 7 composed rows, merge stood down. **Arm B
must never be described as ResourcePlan activation.** Artifact: `runs/arm_b_v2_wins.md`.

**11. Does the approved profile survive restart, meet reliability, and roll back cleanly?**
Yes. Four `--force-recreate` cycles, health 200 each; post-recreate corpus 12/12 with zero
drift. All F3 failure classes fail-closed: LLM unavailable 1.07 s, malformed output 1.82 s,
LLM timeout 181.8 s bounded, model-slot pressure ×3, DB failure → 401 → recovery. No duplicate
side effects (`ai_trace_runs` 21/21 distinct, **0** executed MCP events,
`canonical_execution_idempotency` 0 rows). F4 rollback executed for real and re-applied; host
left in the intended profile. Artifacts: `runs/f3_reliability.md`, `rollback_runbook.md`.

**12. Live Splunk/MCP proven, or honestly unproven?**
**`live_mcp_unproven`.** No endpoint or credentials on this host; the controlled read-only
live search was not run and mock evidence was **not** substituted. Fail-closed behaviour is
covered deterministically only (`47 passed`, `block_reason=splunk_mcp_not_configured`).
Live Splunk/MCP investigation **cannot** be claimed production-ready. Artifact:
`runs/f3_live_mcp.md`.

## Recorded STOP decisions

| STOP | Decision |
|---|---|
| C0 `P6_RESOURCE_PLAN_EXECUTION_ACTIVATION` | **KEEP OFF** (v2 precedence N/A) |
| C3 `P6_EXECUTION_SEAM_ADOPTION` | **KEEP 0 ADOPTED** |
| D3 `P6_T4_SERVING_POSTURE` | **KEEP 2.0 s / DEFAULT-OFF** |
| E2 `P6_MITRE_DRAFT_PROMOTION` | **DEFERRED_SEPARATE_GOVERNED_PROMOTION** |
| E3 `P6_STALE_REPORT_DISPOSITION` | **CONTINUE PRESERVING** |
| F5 `P6_PRODUCTION_GO_LIVE` | **DEFER — intended architecture not yet production-authoritative** |

## What this report does not claim

- Frozen truth-set `--arm both` did **not** observe L4/L5; no routing conclusion here rests on it.
- `production_parity: 120 exact` is dual-runtime equivalence — **not** routing correctness,
  **not** answer correctness, and it is not cited as either.
- Arm C's merged rows prove **reachability and execution**, not production authority.
- Mock MCP validated architecture only. No live rows are claimed anywhere.
- T4's deferral is a **serving** limit; the routing table is not implicated.

## Carried forward

The F5 DEFER decision opens a separate, narrowly-scoped continuation plan covering:
ResourcePlan/PhaseContract execution-authority completion, dispatch-v2 retirement from normal
authority, the structural fix for the missed `spl_postprocessor` work, a target-architecture
regression corpus, T4 integrated **ON**, T4 serving remediation, integrated reliability,
persistence, rollback, and a new production go-live gate.
See `plans/2026-08-14_1130_resource-plan-authority-and-t4-integration.md`.
