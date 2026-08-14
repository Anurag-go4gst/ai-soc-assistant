# Plan 7 P0.3 — architecture-remediation posture applied

Applied through the path proven in P0.1 (`docs/evals/plan7/env_authority_chain.md`): the
repo-root `.env`, which is the **last** `env_file` compose loads and therefore wins over
`env/profiles/development.env.example`. The host profile was **not** switched —
`AI_SOC_ENV_PROFILE` stays `development`, because P0.1 gave no reason to change it.

Pre-change `.env` backed up before any edit. Restart: `docker compose up -d --force-recreate
backend` (settings load at process start — `restart` alone can leave a stale env).

## Read-back from the running backend (`docker compose exec -T backend printenv`)

| Flag | Intended | Effective after recreate | |
|---|---|---|---|
| `LANGGRAPH_ORCHESTRATION_ENABLED` | `true` | **`true`** | ✅ |
| `AI_SOC_RESOURCE_PLAN_EXECUTION_ENABLED` | `true` | **`true`** | ✅ |
| `AI_SOC_PIPELINE_DISPATCH_V2_ENABLED` | `false` | **`false`** | ✅ |
| `AI_SOC_T4_SEMANTIC_UNDERSTANDING_ENABLED` | `true` | **`true`** | ✅ |
| `AI_SOC_T4_SEMANTIC_UNDERSTANDING_TIMEOUT_SECONDS` | `2.0` | **`2.0`** | ✅ |
| `AI_SOC_LIVE_CAPABILITY_ENFORCEMENT_ENABLED` | `false` | **`false`** | ✅ |
| `MCP_MODE` | unchanged | `mock` | — |

Health after recreate: `status=ok`, `database_migrations.ready=true`.

**All six target values read back exactly as intended, so P0.3 passes** and Plan 7 measurements
may be recorded against this runtime.

## Notes

- The T4 timeout was previously **unset** and resolved from the `config.py:414` default. It is
  now written explicitly at the same value `2.0` — the bound is unchanged, only made visible
  and auditable. It must not be raised before C3.
- T4 is **ON** and stays ON for the whole remediation phase. Turning it off to make results
  green is prohibited by the plan's locked decisions.
- Live capability enforcement remains **OFF** (Plan 5 B5 not reopened).
- Repo `config.py` defaults were **not** changed.
- This is a **remediation/test posture**, not a production profile. Nothing here is a go-live
  claim; `P7_PRODUCTION_GO_LIVE_V2` (E2) is the only gate that can make one.
- Rollback to the Plan 6 recorded profile: restore the `.env` backup and force-recreate
  (`docs/evals/plan6/rollback_runbook.md`); the profile file was not modified by P0.3.
