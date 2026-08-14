# Plan 6 F2 — persist the approved production flag profile

Surface: VPS (`environment_identity=coe-vps`). Not F5 go-live.

Approved profile (`production_flag_profile.md`): ResourcePlan execution **OFF**, T4 **omitted / OFF**, dispatch-v2 **ON**, live capability enforcement **OFF**. Repo `config.py` defaults unchanged (all four still false).

This host’s Compose `env_file` is `env/profiles/${AI_SOC_ENV_PROFILE}.env.example` then operator `.env`. Live `AI_SOC_ENV_PROFILE=development`. Test-arm shell exports were not used.

## Persistent writes (booleans only)

| Location | What was written |
|---|---|
| `env/profiles/coe.env.example` | `AI_SOC_PIPELINE_DISPATCH_V2_ENABLED=true` (already); **added** `AI_SOC_RESOURCE_PLAN_EXECUTION_ENABLED=false`; **added** `AI_SOC_LIVE_CAPABILITY_ENFORCEMENT_ENABLED=false`; **T4 omitted** (comment only: do not add `=true`) |
| `env/profiles/development.env.example` | Same KEEP-OFF lines so this VPS’s loaded profile matches COE persist |
| operator `.env` (uncommitted) | exec `false`; v2 `true`; live-cap **added** `false`; T4 already explicit `false` (F2 allows explicit OFF; D3 still omits T4 from the git profile) |

No `AI_SOC_RESOURCE_PLAN_EXECUTION_ENABLED=true` or `AI_SOC_T4_SEMANTIC_UNDERSTANDING_ENABLED=true` was added. `select_env_profile.sh` was **not** used to switch this host to `coe` (would change unrelated flags).

## Pre / post recreate flags (docker `printenv`, no secrets)

Recreate: `docker compose up -d --force-recreate backend`. Health 200 immediately after start.

| Flag | Pre-recreate | Post-recreate | Matches profile? |
|---|---|---|---|
| `AI_SOC_RESOURCE_PLAN_EXECUTION_ENABLED` | `false` | `false` | yes (KEEP OFF) |
| `AI_SOC_T4_SEMANTIC_UNDERSTANDING_ENABLED` | `false` | `false` | yes (explicit OFF in `.env`; omitted from git profiles) |
| `AI_SOC_T4_SEMANTIC_UNDERSTANDING_TIMEOUT_SECONDS` | unset → 2.0 | unset → 2.0 | yes |
| `AI_SOC_LIVE_CAPABILITY_ENFORCEMENT_ENABLED` | **unset** → false | **`false`** (now persisted) | yes |
| `AI_SOC_PIPELINE_DISPATCH_V2_ENABLED` | `true` | `true` | yes |
| `MCP_MODE` | `mock` | `mock` | unchanged (architecture mock; live Splunk is F3) |

Failing-first: post-recreate exec and T4 match `production_flag_profile.md` (both OFF). Live-cap is now an explicit docker `false`, not merely a missing key.

`config.py` still: v2 false (`:403`), exec false (`:410`), T4 false (`:413`), live-cap false (`:417`).

## Representative smoke

Harness (after recreate): exit 0, 4/4, no missing `qualification_tier`.
Run dir: `docs/evals/plan6/runs/20260813T190118Z/`.

```bash
python3 scripts/eval_plan6_vps_harness.py --arm F --environment-identity coe-vps \
  --row-id p6.t1.knowledge --row-id p6.clarify \
  --row-id p6.live_posture.d1_003 --row-id p6.unsafe
```

| row_id | route | tier | fingerprint | `degrade_reason` | `semantic_t4` | `execution_enabled` | wall_ms | Arm A match |
|---|---|---|---|---|---|---|---|---|
| p6.t1.knowledge | knowledge_recall | T2 | `54643926bb51081e` | null | null | false | 92908 | yes |
| p6.clarify | knowledge_recall | T4 | none | null | null | false | 91676 | yes |
| p6.live_posture.d1_003 | spl_generation | T1 | `59ad8ff3369b83a3` | null | null | false | 182187 | yes |
| p6.unsafe | knowledge_recall | T4 | none | null | null | false | 91663 | yes |

`degrade_reason` is **null** on every row. That matches C0: exec OFF, so merge does not run and `dispatch_v2_projected_schedule` is not the winner. T1–T3 did not invoke T4 (`semantic_t4=null`). `phase_names` empty.

Env capture after recreate: exec/T4/live-cap **docker false**, v2 **docker true**, T4 timeout unset → 2.0. Schema-valid; no secret-shaped keys.

## `config.py`

Unchanged. Defaults remain false. Persistent VPS profile is env, not a repo-default flip.
