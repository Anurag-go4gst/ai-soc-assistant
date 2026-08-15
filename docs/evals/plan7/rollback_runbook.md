# Plan 7 — rollback runbook after dispatch-v2 authority retirement

The earlier D3 drill rolled the VPS between the Plan 7 target and the recorded Plan 6 flag
posture; its historical evidence remains in
`docs/evals/plan7/runs/20260815T151500Z/d3_rollback.md`. After the user's A7 convergence
decision, dispatch-v2 is no longer an approved alternative normal runtime authority. This
runbook therefore separates reversible **runtime feature rollback** from an orchestration
**code/release rollback**.

Supersedes `docs/evals/plan6/rollback_runbook.md` for Plan 7 work. That file remains valid for
the Plan 6 posture it documents.

## Configuration ownership — read this first

Two different things decide the posture, and confusing them is the classic failure:

```yaml
# docker-compose.yml, service `backend`
env_file:
  - env/profiles/${AI_SOC_ENV_PROFILE:-coe}.env.example   # TRACKED PROFILE / SEED — loaded first
  - .env                                                   # EFFECTIVE VPS OVERRIDE — loaded second, wins
```

| Role | Path | Tracked in git? | Decides the running posture? |
|---|---|---|---|
| **TRACKED PROFILE / SEED** | `env/profiles/development.env.example` | yes | **only for keys `.env` does not set** |
| **EFFECTIVE VPS OVERRIDE** | `/var/www/ai-soc-assistant/.env` | **no** (secret-bearing) | **yes — this is the authority** |

This host sets `AI_SOC_ENV_PROFILE=development` (`.env:7`, and `env/active.profile`), so the seed
in play is `development.env.example` — **not** `coe.env.example`.

> **Editing `development.env.example` alone does NOT change this already-running host** while the
> same keys exist in `.env`, because `.env` wins. The tracked development seed now reconstructs
> the target posture when those overrides are absent.

`--force-recreate` is required: settings are read at process start, so `restart` alone can leave
a stale environment in the container.

## Approved target posture

| Flag | Plan 7 target |
|---|---|
| `LANGGRAPH_ORCHESTRATION_ENABLED` | `true` |
| `AI_SOC_RESOURCE_PLAN_EXECUTION_ENABLED` | `true` |
| `AI_SOC_PIPELINE_DISPATCH_V2_ENABLED` | `false` |
| `AI_SOC_T4_SEMANTIC_UNDERSTANDING_ENABLED` | `true` |
| `AI_SOC_T4_SEMANTIC_UNDERSTANDING_TIMEOUT_SECONDS` | `120` |
| `AI_SOC_LIVE_CAPABILITY_ENFORCEMENT_ENABLED` | `false` |
| `MCP_MODE` | `mock` |

`AI_SOC_RESOURCE_PLAN_EXECUTION_ENABLED=true` plus
`AI_SOC_PIPELINE_DISPATCH_V2_ENABLED=false` is the one approved normal execution authority.
Code also fences v2 projection whenever ResourcePlan execution is enabled, so accidentally
setting both true cannot stand down ResourcePlan/PhaseContract.

## Runtime flag rollback

Runtime rollback is limited to independently reversible features that do not select a second
orchestrator. For example, an operator may disable T4 after preserving evidence of a serving
incident; deterministic T1–T3 fallback remains fail-closed. MCP execution and live capability
enforcement remain independently default-off.

Changing the pair to `ResourcePlan=false` / `dispatch-v2=true` is **not** an approved routine
runtime rollback. It selects the retired duplicate authority and is retained only for focused
rollback-compatibility tests and recovery of an older release.

**Do not restart `llama-server`.** Cisco model restart is human-only under the frozen
architecture; the application recreate above never requires it.

## Code/release rollback

If the ResourcePlan orchestration itself must be rolled back, deploy the last fully proven
release/commit together with that release's versioned development profile, then run that
release's health, governance, and smoke gates. Do not synthesize an old authority by editing only
the current release's flags. This preserves rollback capability without keeping two normal
production orchestrators live in one release.

The older Plan 6 flag posture and the executed D3 transition remain historical recovery evidence,
not a current approval to make v2 normal authority. Keep `.env` secret-bearing and off git; back it
up through the operator's secret/configuration process before any release rollback.

After either rollback type, recreate the backend (settings are process-start configuration),
verify health, capture the six non-secret target flags, and prove which release/authority is
running. Do **not** restart `llama-server` as part of an application rollback.

### Authority discriminators

| Signal | Current target |
|---|---|
| `execution_order.active` / phase merge | present on applicable ResourcePlan rows |
| mandatory `spl_postprocessor` | represented in PhaseContract and dispatch schedule |
| dispatch-v2 authority | absent |
| candidate executability | never inferred; only approved non-null `normalized_spl` reaches MCP gate |

Any v2 authority trace on the current Plan 7 target is a regression. It is expected only while
actually running the separately identified older rollback release.

## Config reconstruction

| Flag | Current effective | Tracked seed | Repo default | Rebuild preserves target? |
|---|---|---|---|---|
| `LANGGRAPH_ORCHESTRATION_ENABLED` | `true` | `true` | `True` | yes |
| `AI_SOC_RESOURCE_PLAN_EXECUTION_ENABLED` | `true` | `true` | `False` | yes |
| `AI_SOC_PIPELINE_DISPATCH_V2_ENABLED` | `false` | `false` | `False` | yes |
| `AI_SOC_T4_SEMANTIC_UNDERSTANDING_ENABLED` | `true` | `true` | `False` | yes |
| `AI_SOC_T4_SEMANTIC_UNDERSTANDING_TIMEOUT_SECONDS` | `120` | `120` | `2.0` | yes |
| `AI_SOC_LIVE_CAPABILITY_ENFORCEMENT_ENABLED` | `false` | `false` | `False` | yes |

**`CONFIG_REBUILD_DRIFT = CLOSED` for the development profile.** The tracked profile plus
unchanged repo defaults reconstructs all six target values. This does not alter global
`config.py` defaults, the COE/production profiles, provider/model choice, or any secret.
