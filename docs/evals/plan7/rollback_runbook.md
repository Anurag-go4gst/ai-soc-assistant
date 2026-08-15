# Plan 7 — rollback runbook (executed, not simulated)

Rolls the VPS between the **approved Plan 7 target posture** and the **recorded Plan 6 rollback
posture**, and back. Executed end-to-end 2026-08-15 (D3); evidence in
`docs/evals/plan7/runs/20260815T151500Z/d3_rollback.md`.

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

> **Editing `development.env.example` alone does NOT change the active target posture**, because
> every Plan 7 flag is set in `.env`, which loads later and wins. Conversely, editing `.env` alone
> does not change what a rebuilt-from-seed host would get. Both facts matter — see
> *Config-rebuild drift*.

`--force-recreate` is required: settings are read at process start, so `restart` alone can leave
a stale environment in the container.

## Postures

| Flag | Plan 7 TARGET | Plan 6 ROLLBACK (recorded) |
|---|---|---|
| `LANGGRAPH_ORCHESTRATION_ENABLED` | `true` | `true` |
| `AI_SOC_RESOURCE_PLAN_EXECUTION_ENABLED` | `true` | `false` (from seed) |
| `AI_SOC_PIPELINE_DISPATCH_V2_ENABLED` | `false` | `true` (from seed) |
| `AI_SOC_T4_SEMANTIC_UNDERSTANDING_ENABLED` | `true` | unset → `false` |
| `AI_SOC_T4_SEMANTIC_UNDERSTANDING_TIMEOUT_SECONDS` | `120` | unset → `2.0` (code default) |
| `AI_SOC_LIVE_CAPABILITY_ENFORCEMENT_ENABLED` | `false` | `false` |
| `MCP_MODE` | `mock` | `mock` |

The rollback values are the ones recorded in Plan 6 (`docs/evals/plan6/rollback_runbook.md`,
"Arm A / pre-F2"), not values chosen here.

## Rollback

Comment the Plan 7 override lines in `.env` — do **not** delete the file, and do not touch
unrelated keys or secrets. With those four lines inert, the seed and the code defaults supply the
Plan 6 posture exactly.

```bash
cp .env /root/env.plan7_target.bak          # reversible reference (keep off git)

python3 - <<'EOF'
import pathlib
keys = ["AI_SOC_PIPELINE_DISPATCH_V2_ENABLED",
        "AI_SOC_RESOURCE_PLAN_EXECUTION_ENABLED",
        "AI_SOC_T4_SEMANTIC_UNDERSTANDING_ENABLED",
        "AI_SOC_T4_SEMANTIC_UNDERSTANDING_TIMEOUT_SECONDS"]
p = pathlib.Path('.env')
p.write_text("\n".join(
    "#D3_ROLLBACK " + l if any(l.startswith(k + "=") for k in keys) else l
    for l in p.read_text().splitlines()) + "\n")
EOF

docker compose up -d --force-recreate backend
curl -s http://127.0.0.1:8010/health
docker compose exec -T backend printenv AI_SOC_RESOURCE_PLAN_EXECUTION_ENABLED   # expect false
docker compose exec -T backend printenv AI_SOC_PIPELINE_DISPATCH_V2_ENABLED      # expect true
docker compose exec -T backend printenv AI_SOC_T4_SEMANTIC_UNDERSTANDING_ENABLED # expect unset
```

**Do not restart `llama-server`.** Cisco model restart is human-only under the frozen
architecture; the application recreate above never requires it.

### How to tell the postures apart — `dispatch_source` will mislead you

Under rollback, four rows still report `dispatch_source=resource_plan_step_walk`. That label is
the step-walk dispatch name; it is **not** the execution-contract authority. With execution OFF,
`_execution_driven_schedule_detailed` returns immediately (`planner/executor.py:247`) and the
fixed predicate schedule is used.

The reliable discriminators are:

| Signal | TARGET | ROLLBACK |
|---|---|---|
| `merge_active` | **4/6 rows** | **0 rows** |
| `inserted_phases` | `['spl_postprocessor']` on seam rows | none |
| `t4_invoked` | 3 rows | **0 rows** |
| v2 path visible | never | `langgraph_v2_cursor` on the knowledge row |

A `langgraph_v2_cursor` / v2 path during a deliberate rollback is **EXPECTED_ROLLBACK_AUTHORITY**,
not a defect.

## Re-apply the target

```bash
python3 - <<'EOF'
import pathlib
p = pathlib.Path('.env')
p.write_text("\n".join(
    l[len("#D3_ROLLBACK "):] if l.startswith("#D3_ROLLBACK ") else l
    for l in p.read_text().splitlines()) + "\n")
EOF

docker compose up -d --force-recreate backend
```

Then verify all six flags read back exactly, health is 200, `merge_active` returns on the
ResourcePlan rows, and `execution_eligible` stays null.

D3 confirmed `.env` was byte-identical to the pre-rollback backup after restore, and the
non-secret flag block hashed identically (`9613fc2c…`) before and after.

## Config-rebuild drift — the limit of this runbook

| Flag | Current effective | Tracked seed | Repo default | Rebuild preserves target? |
|---|---|---|---|---|
| `LANGGRAPH_ORCHESTRATION_ENABLED` | `true` | `true` | `True` | yes |
| `AI_SOC_RESOURCE_PLAN_EXECUTION_ENABLED` | `true` | `false` | `False` | **NO** |
| `AI_SOC_PIPELINE_DISPATCH_V2_ENABLED` | `false` | `true` | `False` | **NO** |
| `AI_SOC_T4_SEMANTIC_UNDERSTANDING_ENABLED` | `true` | *absent* | `False` | **NO** |
| `AI_SOC_T4_SEMANTIC_UNDERSTANDING_TIMEOUT_SECONDS` | `120` | *absent* | `2.0` | **NO** |
| `AI_SOC_LIVE_CAPABILITY_ENFORCEMENT_ENABLED` | `false` | `false` | `False` | yes |

**`CONFIG_REBUILD_DRIFT = CONFIRMED`.** Recreate persistence is proven; **rebuild-from-seed
resilience is not**. If `.env` were lost or regenerated from the tracked profile, the host would
silently return to pre-Plan-7 authority — execution OFF, dispatch-v2 ON, T4 off at a 2 s bound —
with no error and no signal.

Aligning the seed would mean changing tracked deployment defaults, which Plan 7 does not
authorize in D3. Carried to **E2** as an operational blocker, not remediated here.
