# Plan 6 — production flag profile (C1 + D4)

This is the **approved intended profile** after C0 + D3. It is **not** F2
persistence and **not** F5 go-live. Repo `config.py` defaults stay conservative
false. Flags remain independently controllable. No new env flags.

Recorded STOPs: [`c0_d3_stop_decisions.md`](c0_d3_stop_decisions.md).

## Intended profile vs repo default vs current VPS/COE

| Flag | Repo default (`config.py`) | Persistent VPS/COE profile | Notes |
|---|---|---|---|
| `AI_SOC_RESOURCE_PLAN_EXECUTION_ENABLED` | **false** (`:410`) | **OFF** (omit / leave false) | C0 Field 1 **KEEP OFF**. Not Plan-5 merge activation. |
| `AI_SOC_PIPELINE_DISPATCH_V2_ENABLED` | false (`:403`) | **ON** (keep current COE `true`) | C0 Field 2 **N/A** (exec remains OFF). Keep v2 ON in current VPS/COE posture. |
| `AI_SOC_T4_SEMANTIC_UNDERSTANDING_ENABLED` | **false** (`:413`) | **OFF — omit from persistent profile** | D3 **KEEP DEFAULT-OFF**. |
| `AI_SOC_T4_SEMANTIC_UNDERSTANDING_TIMEOUT_SECONDS` | **2.0** (`:414`) | **2.0** (do not raise) | D3 **KEEP 2.0s**. |
| `AI_SOC_LIVE_CAPABILITY_ENFORCEMENT_ENABLED` | **false** (`:417`) | **OFF** | Stays OFF. Plan 5 B5 not reopened. |

## C0 — exec posture applied

- **KEEP OFF.** Do not flip `config.py`. Do not add
  `AI_SOC_RESOURCE_PLAN_EXECUTION_ENABLED=true` to `env/profiles/coe.env.example`.
- `CHANGE_LADDER` was **not** selected. Do not change
  `_execution_driven_schedule_detailed` precedence. `exec ON + v2 ON` remains
  `dispatch_v2_projected_schedule` (`V2_WINS`) and is **not** Plan-5 merge
  activation — unused while exec stays OFF.
- Future ResourcePlan activation still requires (1) evidence that the v2-OFF
  missed-work cases (`spl_postprocessor` dropped on
  `p6.multi.knowledge_spl_mcp` and `p6.live_posture.d1_003`) are correctly
  covered, or (2) an explicitly approved `CHANGE_LADDER` / execution-seam change.

## D3 — T4 posture applied

- **KEEP 2.0s / DEFAULT-OFF.** Skip VPS T4 persistence.
- `D1_PARAPHRASE_RESIDUE = DEFERRED_T4_SEMANTIC_SERVING_LIMIT`.
- Do not add keyword heuristics. Do not raise the timeout. T1–T3 must still
  never invoke the hop (existing `test_semantic_t4_understanding.py` pins).

## Independent control (must remain true)

Each flag above is a separate Settings field. Turning one ON must not force
another. C0 KEEP OFF does not retire dispatch-v2. D3 KEEP OFF does not change
the T4 timeout field’s independent existence.

## F2 persist status

F2 **done** (`docs/evals/plan6/runs/f2_persistence.md`). Profile persisted in
`env/profiles/coe.env.example`, `env/profiles/development.env.example` (this
host’s loaded profile), and operator `.env`. Recreate proved exec/T4/live-cap
OFF and v2 ON. T4 remains omitted from the git profiles (explicit OFF only in
operator `.env`). Not F5 go-live.
