# Plan 6 — combined STOP record (C0 + D3)

Recorded 2026-08-13. These are **production decisions**, not test-arm failures.
Test-arm success is not go-live. `P6_PRODUCTION_GO_LIVE` (F5) remains open.

Arm C successfully proved Plan-5 `merge_schedule` reachability. KEEP OFF at C0
is because production execution authority is not yet safe to move off dispatch-v2.

## C0 — `P6_RESOURCE_PLAN_EXECUTION_ACTIVATION`

### Field 1 — exec posture

**KEEP OFF**

Repo `config.py` default stays `ai_soc_resource_plan_execution_enabled = False`.
Do **not** persist ResourcePlan execution ON in the VPS/production profile.

Reason: Arm C proved that Plan-5 `merge_schedule` is reachable and executes when
ResourcePlan execution is ON and dispatch-v2 is OFF, but production authority is
not yet safe to move to that path.

Evidence:

- Arm C merge executed on **5/12**.
- **7/12** were legitimately `merge_not_reachable`.
- With v2 OFF, two `workflow_spl` / `no_schedulable_step` rows lose
  `spl_postprocessor` even though merge does not run
  (`p6.multi.knowledge_spl_mcp`, `p6.live_posture.d1_003`).
- Therefore `V2_OFF_ON_VPS` would introduce **known missed work**.
- Exec ON + v2 ON would be `V2_WINS` and must **not** be represented as
  ResourcePlan / Plan-5 merge activation.
- No evidence supports changing the repo default.
- **Do not self-select `CHANGE_LADDER`.** It was not selected.

Sources: `docs/evals/plan6/runs/arm_c_merge.md`,
`docs/evals/plan6/execution_off_on_comparison.md`.

### Field 2 — dispatch-v2 precedence

**N/A** because ResourcePlan execution remains OFF.

Keep dispatch-v2 **ON** in the current VPS/COE posture
(`AI_SOC_PIPELINE_DISPATCH_V2_ENABLED=true` in `env/profiles/coe.env.example`).

A future ResourcePlan activation requires either:

1. evidence that the v2-OFF missed-work cases are correctly covered, or
2. an explicitly approved `CHANGE_LADDER` / execution-seam change.

Do **not** implement such a change as part of this STOP.

## D3 — `P6_T4_SERVING_POSTURE`

**KEEP 2.0s / DEFAULT-OFF.** Omit T4 from the persistent production profile.

Record: `D1_PARAPHRASE_RESIDUE = DEFERRED_T4_SEMANTIC_SERVING_LIMIT`

Reason:

- Qualification/routing is correct.
- 9/9 baseline T4 attempts timed out at ~2s.
- 0 accepted contracts.
- 0 false capability widening.
- No viable alternate serving option exists in the current environment.
- Raising timeout is not supported by evidence: 90s/180s probes still did not
  return the required JSON.
- N=2 worsens slot pressure.
- Do not add keyword heuristics.

Live capability enforcement remains **OFF**
(`B_LIVE_CAPABILITY_ENFORCEMENT = DEFAULT_OFF_ARCHITECTURALLY_DEFERRED`).

Sources: `docs/evals/plan6/t4_serving_baseline.md`,
`docs/evals/plan6/t4_serving_options.md`,
`docs/evals/plan6/t4_paraphrase_accuracy.md`.

## What this is not

- Not F2 persistence (that item still writes the approved profile into VPS config).
- Not F5 go-live.
- Not a failure of Arm C.
- Not Plan-5 merge activation.
- Not a T4 timeout raise, keyword heuristic, or skill-contract widening.
