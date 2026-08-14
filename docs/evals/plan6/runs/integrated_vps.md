# Plan 6 F0 — integrated VPS corpus on the intended profile

Surface: VPS (`environment_identity=coe-vps`). **Not production-ready.** Not F2 persist. Not F5 go-live.

Harness: `python3 scripts/eval_plan6_vps_harness.py --arm F --environment-identity coe-vps`  
Run dir: `docs/evals/plan6/runs/20260813T183145Z/`  
Exit: 0. Rows: **12**. `missing_qualification_tier`: none. Wall clock ~25.4 min (LLM instruct timeouts on most turns).

T4 paraphrases **omitted** (D3 KEEP DEFAULT-OFF). Mock MCP.

## Intended profile (already effective on this host)

| Flag | Effective |
|---|---|
| `AI_SOC_RESOURCE_PLAN_EXECUTION_ENABLED` | **false** (docker) |
| `AI_SOC_T4_SEMANTIC_UNDERSTANDING_ENABLED` | **false** (docker) |
| `AI_SOC_T4_SEMANTIC_UNDERSTANDING_TIMEOUT_SECONDS` | unset → **2.0** |
| `AI_SOC_LIVE_CAPABILITY_ENFORCEMENT_ENABLED` | unset → **false** |
| `AI_SOC_PIPELINE_DISPATCH_V2_ENABLED` | **true** |
| `MCP_MODE` | **mock** |

Matches `production_flag_profile.md` (C0 KEEP OFF + D3 T4 OFF + keep COE v2 ON). Session env, not yet F2-recaptured across recreate.

## Compare to Arm A

All 12 primary skills, qualification tiers, and ResourcePlan fingerprints **match** Arm A (`docs/evals/plan6/runs/arm_a_smoke.md`, `runs/20260813T114521Z/`).

| row_id | route | tier | `execution_enabled` | `degrade_reason` | `semantic_t4` | `phase_names` |
|---|---|---|---|---|---|---|
| p6.t1.knowledge | knowledge_recall | T2 | false | null | null | empty |
| p6.t2.known_nontrivial | knowledge_recall | T2 | false | null | null | empty |
| p6.t4.out_of_registry | guided_investigation | T4 | false | null | null | empty |
| p6.spl.draft | attack_discovery | T2 | false | null | null | empty |
| p6.spl.mcp | attack_discovery | T2 | false | null | null | empty |
| p6.multi.knowledge_spl_mcp | spl_generation | T2 | false | null | null | empty |
| p6.clarify | knowledge_recall | T4 | false | null | null | empty |
| p6.unsafe | knowledge_recall | T4 | false | null | null | empty |
| p6.alert.summary | knowledge_recall | T2 | false | null | null | empty |
| p6.live_posture.d1_003 | spl_generation | T1 | false | null | null | empty |
| p6.repeat.refinement | spl_generation | T4 | false | null | null | empty |
| p6.fail.degraded | attack_discovery | T2 | false | null | null | empty |

`degrade_reason` is **null** on every row. That matches C0: exec OFF so merge does not run and `dispatch_v2_projected_schedule` is not the winner (Field 2 N/A). No composed turn is labelled Plan-5 merge activation.

Latency p50 **92714 ms**, max **236013 ms** (`p6.spl.mcp`). Backend logs `llm_failover … url_error:timeout` on several turns. This is serving-slot cost on the **current** path, not ResourcePlan/T4 activation cost.

## Success questions 1–7 (cite-only; F0 does not close go-live)

1. **Plan 5 merged execution on the VPS?** Arm C proved merge **5/12** (`runs/arm_c_merge.md`). F0 on the **approved** profile does **not** run merge (`phase_names` empty). C0 KEEP OFF: `c0_d3_stop_decisions.md`.
2. **Better/equivalent to current production path?** F0 **equivalent to Arm A** (routes/fingerprints/tiers). Not a merge-on comparison.
3. **Latency/quality/safety cost of activation?** Activation is OFF. No extra merge/T4 hop. Safety: `execution_enabled=false` all 12. Cost vs Arm A is LLM timeout noise, not exec/T4.
4. **Can ResourcePlan execution become authoritative?** **No** in Plan 6. C0 KEEP OFF. Missed `spl_postprocessor` on v2-OFF `p6.multi.knowledge_spl_mcp` / `p6.live_posture.d1_003` (`execution_off_on_comparison.md`).
5. **Can a legacy/duplicate path be retired?** **No.** C3 KEEP 0 ADOPTED (`c3_stop_decision.md`). Fallback retained.
6. **Can T4 resolve the eight paraphrases in SLO?** **No.** D3 KEEP 2.0s/DEFAULT-OFF (`t4_paraphrase_accuracy.md`). F0 omitted paraphrase rows.
7. **Persistent flag profile?** Intended profile: `production_flag_profile.md` (exec OFF, T4 omitted/OFF, v2 ON, live-capability OFF). F2 still owes recreate persistence.

Env capture: `runs/20260813T183145Z/env_capture.json` (schema-validated; no secret keys).
