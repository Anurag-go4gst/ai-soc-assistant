# Plan 7 P0.1 — effective configuration chain (evidence, no changes)

Read-only. **No flag was changed and no profile was switched during P0.1 or P0.2.**
Git SHA at capture: `dae51eb`. Host identity recorded as `vps-development-profile` — *not*
assumed to be COE.

## 1. Compose `env_file` order (service `backend`, `docker-compose.yml:7-9`)

```yaml
env_file:
  - env/profiles/${AI_SOC_ENV_PROFILE:-coe}.env.example   # loaded first
  - .env                                                   # loaded second, wins on conflict
```

Later `env_file` entries override earlier ones. The compose default is `coe`, but the default
is **not** what this host uses.

## 2. `AI_SOC_ENV_PROFILE`

| Source | Value |
|---|---|
| `.env:7` | `development` |
| `env/active.profile` | `development` |

The variable is consumed by compose **substitution** (choosing the profile file) and is also
present in `.env` as an ordinary key. Both agree.

## 3. Profile file actually selected

`env/profiles/development.env.example` — **not** `env/profiles/coe.env.example`.

`env/profiles/development.env` exists but is a scaffold and is deliberately **not referenced by
compose**; its own header says so. `coe.env`, `production.env` are likewise unreferenced.
Editing any of them changes nothing.

## 4. `.env` overrides

`.env` is loaded second, so any key present there wins over the profile file. It also holds the
secrets and is uncommitted by design.

## 5. Service-level `environment:` (highest precedence)

```yaml
environment:
  PYTHONPATH: /app:/workspace
  AI_SOC_REPO_ROOT: /workspace
  AI_SOC_ENV_PROFILES_DIR: /app/env_profiles
```

**None of the six target flags (nor `MCP_MODE`) is overridden at service level.** So for the
target flags the precedence that matters is: profile file → `.env`.

## 6. Source file per target flag

Values as committed/present at capture time; "effective" read from the running container via
`docker compose exec -T backend printenv`.

| Flag | `development.env.example` | `.env` | Service `environment:` | Effective | Winning source |
|---|---|---|---|---|---|
| `LANGGRAPH_ORCHESTRATION_ENABLED` | `true` | `true` | — | **true** | `.env` (profile agrees) |
| `AI_SOC_RESOURCE_PLAN_EXECUTION_ENABLED` | `false` | `false` | — | **false** | `.env` (profile agrees) |
| `AI_SOC_PIPELINE_DISPATCH_V2_ENABLED` | `true` | `true` | — | **true** | `.env` (profile agrees) |
| `AI_SOC_T4_SEMANTIC_UNDERSTANDING_ENABLED` | *absent* | `false` | — | **false** | **`.env` only** |
| `AI_SOC_T4_SEMANTIC_UNDERSTANDING_TIMEOUT_SECONDS` | *absent* | *absent* | — | **unset → 2.0** | **`config.py:414` default** |
| `AI_SOC_LIVE_CAPABILITY_ENFORCEMENT_ENABLED` | `false` | `false` | — | **false** | `.env` (profile agrees) |
| `MCP_MODE` | `mock` | `mock` | — | **mock** | `.env` (profile agrees) |

Code defaults for reference: `config.py:398` `langgraph_orchestration_enabled = True`,
`:413` T4 enabled `False`, `:414` T4 timeout `2.0`.

## Consequences for Plan 7

1. **P0.3 must write through `.env` and `env/profiles/development.env.example`** — the two files
   compose actually reads. Editing `coe.env.example` alone changes nothing on this host.
2. **`.env` wins**, so a value left in `.env` masks any profile edit. Both must agree, or the
   `.env` value must be the intended one.
3. The T4 **timeout** currently comes from the code default, not from any file. Writing `2.0`
   explicitly makes the bound visible and auditable; the value does not change.
4. Rollback must touch the profile named by `AI_SOC_ENV_PROFILE`, not just `.env` — the Plan 6
   F4 finding, confirmed here from the compose file rather than by symptom.
5. Documentation calling this "the COE host" is misleading about **which file supplies flags**.
   Corrected in `CLAUDE.md` and `docs/architecture/phase_contract_and_schedule.md` (Plan 6 G1).
   The host is not assumed to be COE anywhere in Plan 7.

## P0.2 — pre-change effective capture

`docs/evals/plan7/runs/20260814T125151Z/env_capture.json`, produced with
`eval_plan6_vps_harness.capture_env()` and validated by
`app.evals.plan6_env_capture.validate_env_capture` (rejects secret-shaped keys).

| Flag | Effective | Presence |
|---|---|---|
| `AI_SOC_RESOURCE_PLAN_EXECUTION_ENABLED` | `false` | docker |
| `AI_SOC_T4_SEMANTIC_UNDERSTANDING_ENABLED` | `false` | docker |
| `AI_SOC_T4_SEMANTIC_UNDERSTANDING_TIMEOUT_SECONDS` | `2.0` | **unset** (code default) |
| `AI_SOC_LIVE_CAPABILITY_ENFORCEMENT_ENABLED` | `false` | docker |
| `AI_SOC_PIPELINE_DISPATCH_V2_ENABLED` | `true` | docker |
| `LANGGRAPH_ORCHESTRATION_ENABLED` | `true` | docker |
| `MCP_MODE` | `mock` | docker |

Also captured: `db_reachable=true`, `mcp_connectivity=true`, `mcp_mode=mock`,
`environment_identity=vps-development-profile`, `git_sha=dae51eb`. No secrets.

This is the **pre-change** state — the Plan 6 recorded production profile, unchanged.
