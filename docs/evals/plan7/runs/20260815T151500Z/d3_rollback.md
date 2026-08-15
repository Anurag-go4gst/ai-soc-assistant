# Plan 7 D3 — rollback drill on the new authority

Git SHA at run: `c4e5814`. Runbook updated: `docs/evals/plan7/rollback_runbook.md`.
No secret values appear here — only Plan 7 flag names and their non-secret values.

**Cisco restart performed: NO.** **Final host posture: TARGET.**

## PRE_ROLLBACK_TARGET

Effective flags read from inside the running backend:

| Flag | Value |
|---|---|
| `LANGGRAPH_ORCHESTRATION_ENABLED` | `true` |
| `AI_SOC_RESOURCE_PLAN_EXECUTION_ENABLED` | `true` |
| `AI_SOC_PIPELINE_DISPATCH_V2_ENABLED` | `false` |
| `AI_SOC_T4_SEMANTIC_UNDERSTANDING_ENABLED` | `true` |
| `AI_SOC_T4_SEMANTIC_UNDERSTANDING_TIMEOUT_SECONDS` | `120` |
| `AI_SOC_LIVE_CAPABILITY_ENFORCEMENT_ENABLED` | `false` |
| `MCP_MODE` | `mock` |

Health 200. Non-secret target flag block hash **`9613fc2cea1e4c77`**; `.env` 138 lines; reversible
backup taken to scratchpad (never committed). Authority: `merge_active` on the ResourcePlan rows,
`degrade_reason` null.

## ROLLBACK_VALUES (recorded Plan 6 posture, taken from committed evidence)

From `docs/evals/plan6/rollback_runbook.md` ("Arm A / pre-F2") — not inferred:

| Flag | Rollback value |
|---|---|
| `AI_SOC_RESOURCE_PLAN_EXECUTION_ENABLED` | `false` |
| `AI_SOC_PIPELINE_DISPATCH_V2_ENABLED` | `true` |
| `AI_SOC_T4_SEMANTIC_UNDERSTANDING_ENABLED` | unset → `false` |
| `AI_SOC_T4_SEMANTIC_UNDERSTANDING_TIMEOUT_SECONDS` | unset → `2.0` (code default) |
| `AI_SOC_LIVE_CAPABILITY_ENFORCEMENT_ENABLED` | `false` |
| `LANGGRAPH_ORCHESTRATION_ENABLED` | `true` |

## ROLLBACK_RECREATE

Four Plan 7 override lines in `.env` commented with a `#D3_ROLLBACK ` prefix — file not
recreated, unrelated keys and secrets untouched — so the tracked seed and code defaults supply the
posture. Then `docker compose up -d --force-recreate backend` (application container only).

`llama-server` PID **217320**, uptime continuous `01:48:39 → 01:49:25`. No systemctl, no watcher
request.

## ROLLBACK_EFFECTIVE_FLAGS

Read from inside the running backend — exact match to the recorded posture:

| Flag | Expected | Observed |
|---|---|---|
| `LANGGRAPH_ORCHESTRATION_ENABLED` | `true` | ✅ `true` |
| `AI_SOC_RESOURCE_PLAN_EXECUTION_ENABLED` | `false` | ✅ `false` |
| `AI_SOC_PIPELINE_DISPATCH_V2_ENABLED` | `true` | ✅ `true` |
| `AI_SOC_T4_SEMANTIC_UNDERSTANDING_ENABLED` | unset | ✅ `<unset>` |
| `AI_SOC_T4_SEMANTIC_UNDERSTANDING_TIMEOUT_SECONDS` | unset → 2.0 | ✅ `<unset>`, app reports `2.0` |
| `AI_SOC_LIVE_CAPABILITY_ENFORCEMENT_ENABLED` | `false` | ✅ `false` |

Health 200.

## ROLLBACK_AUTHORITY_SMOKE (5 rows) — `EXPECTED_ROLLBACK_AUTHORITY`

App-reported flags: `resource_plan_execution: false`, `dispatch_v2: true`, `t4_enabled: false`,
`t4_timeout_s: 2.0`.

| row | dispatch source | merge_active | t4_invoked | execution_eligible |
|---|---|---|---|---|
| `d0.explain_spl` | `resource_plan_step_walk` | **false** | false | null |
| `d0.generate_spl` | `resource_plan_step_walk` | **false** | false | null |
| `d0.alert_review` | `resource_plan_step_walk` | **false** | false | null |
| `d0.knowledge` | **`langgraph_v2_cursor`** | false | false | null |
| `d0.spl_mcp` | `resource_plan_step_walk` | **false** | false | null |

- New authority **not active**: `merge_active` **0/5**, no `inserted_phases`, T4 invoked **0**.
- v2 path visible on the knowledge row — this is the recorded rollback posture, labelled
  **`EXPECTED_ROLLBACK_AUTHORITY`**, not a defect.
- No mixed posture, no duplicate execution, `execution_eligible` null throughout, health green.

**Important reading caveat, recorded so it cannot be misread later:** `dispatch_source` still
says `resource_plan_step_walk` on four rows *with execution OFF*. That label is the step-walk
dispatch name, not the execution-contract authority — with the flag off,
`_execution_driven_schedule_detailed` returns at `planner/executor.py:247` and the fixed predicate
schedule is used. The reliable discriminators are `merge_active`, `inserted_phases` and
`t4_invoked`.

## TARGET_REAPPLY / TARGET_RECREATE

`#D3_ROLLBACK ` prefixes removed; `docker compose up -d --force-recreate backend`.

Reversibility proven exactly:
- non-secret flag block hash after restore **`9613fc2cea1e4c77`** — identical to pre-rollback;
- `.env` **byte-identical** to the pre-rollback backup (`diff` clean);
- line count 138 → 138.

`llama-server` PID **217320**, uptime continuous `01:49:25 → 01:52:36`. **No Cisco restart.**

## TARGET_EFFECTIVE_FLAGS

All six exact, **0 failures**; health 200:

`LANGGRAPH=true` · `RESOURCE_PLAN_EXECUTION=true` · `DISPATCH_V2=false` · `T4=true` ·
`T4_TIMEOUT=120` · `LIVE_CAPABILITY_ENFORCEMENT=false` · `MCP_MODE=mock`

## TARGET_AUTHORITY_SMOKE (6 rows)

| row | dispatch source | merge_active | inserted_phases | t4_invoked | execution_eligible |
|---|---|---|---|---|---|
| `d0.explain_spl` | `resource_plan_step_walk` | ✅ | `spl_postprocessor` | ✅ | null |
| `d0.generate_spl` | `resource_plan_step_walk` | ✅ | `spl_postprocessor` | ✅ | null |
| `d0.alert_review` | `resource_plan_step_walk` | ✅ | `spl_postprocessor` | — | null |
| `d0.knowledge` | — | — | — | — | null |
| `d0.spl_mcp` | `resource_plan_step_walk` | ✅ | `spl_postprocessor` | — | null |
| `d0.t4_semantic` | `canonical_non_planned` | — | — | ✅ | null |

- ResourcePlan authority restored: **`merge_active` 4 rows**.
- **`V2_WINS` / v2 authority: 0 rows**; `degrade_reason` null throughout.
- **A3 intact** — `spl_postprocessor` contract-inserted on every seam row.
- T4 enabled again: **3 rows** invoked.
- Candidate SPL non-executable: `execution_eligible` null on all 6.

## FINAL_HOST_STATE

**TARGET.** Flags exact, health 200, ResourcePlan authoritative, dispatch-v2 off, Cisco model
untouched throughout the entire drill (single PID, unbroken uptime).

## CONFIG_REBUILD_COMPARISON (read-only; `.env` never deleted or regenerated)

| FLAG | CURRENT_EFFECTIVE | TRACKED_DEVELOPMENT_PROFILE | REPO_DEFAULT_IF_ABSENT | WOULD_REBUILD_PRESERVE_TARGET |
|---|---|---|---|---|
| `LANGGRAPH_ORCHESTRATION_ENABLED` | `true` | `true` | `True` | **yes** |
| `AI_SOC_RESOURCE_PLAN_EXECUTION_ENABLED` | `true` | `false` | `False` | **no** |
| `AI_SOC_PIPELINE_DISPATCH_V2_ENABLED` | `false` | `true` | `False` | **no** |
| `AI_SOC_T4_SEMANTIC_UNDERSTANDING_ENABLED` | `true` | *absent* | `False` | **no** |
| `AI_SOC_T4_SEMANTIC_UNDERSTANDING_TIMEOUT_SECONDS` | `120` | *absent* | `2.0` | **no** |
| `AI_SOC_LIVE_CAPABILITY_ENFORCEMENT_ENABLED` | `false` | `false` | `False` | **yes** |

**`CONFIG_REBUILD_DRIFT = CONFIRMED`.**

## CONFIG_REBUILD_DRIFT_DISPOSITION

**A — `TARGET_PERSISTENCE_SUFFICIENT_FOR_CURRENT_VPS_OPERATION_BUT_CONFIG_REBUILD_DRIFT_REMAINS_E2_BLOCKER`.**

Recreate persistence is proven twice (D2, and both directions of this drill). Rebuild-from-seed
resilience is **not**: losing or regenerating `.env` would silently restore execution OFF /
dispatch-v2 ON / T4 off at a 2 s bound, with no error and no signal. Closing the gap means
changing tracked deployment defaults, which Plan 7 does not authorize in D3, so it is **not**
remediated here and **not** self-approved as an accepted risk. It travels to **E2**.

D3 must not be described as full configuration resilience. The mechanical rollback drill passed;
the drift is a separate, honestly recorded operational gap.

## OPEN_F1_F2_F3 (carried forward unchanged — D3 solved none)

- **F1** — DB loss silently downgrades execution authority to `canonical_non_planned`.
  `KNOWN_PLAN8_DEPENDENCY` / E2 visibility.
- **F2** — Cisco `/v1/models` liveness ≠ usable inference health. `KNOWN_PLAN8_DEPENDENCY` /
  Plan 8 REL0 detection; restart stays human-only.
- **F3** — Cisco serving stability unresolved; C3's
  `T4_SEMANTICALLY_VIABLE_BUT_VPS_SERVING_BLOCKER` stands.
