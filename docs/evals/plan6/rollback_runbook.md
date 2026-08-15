# Plan 6 F4 — rollback runbook (executed, not simulated)

Rolls the VPS between the **approved Plan 6 production profile** and the **prior proven
Arm A posture**, and back again. Executed end-to-end on 2026-08-14; evidence below.

## Where the flags actually come from

`docker-compose.yml` loads **two** env files, later wins:

```yaml
env_file:
  - env/profiles/${AI_SOC_ENV_PROFILE:-coe}.env.example
  - .env
```

**This host sets `AI_SOC_ENV_PROFILE=development` (`.env:7`), so the committed profile in
effect is `env/profiles/development.env.example` — not `coe.env.example`.** A rollback that
only edits `.env` leaves the profile-supplied keys in place and does **not** reach Arm A.
This was discovered during the F4 drill and is the single most important line in this runbook.

Flags in scope:

| Flag | Arm A (pre-F2) | Approved Plan 6 profile |
|---|---|---|
| `AI_SOC_RESOURCE_PLAN_EXECUTION_ENABLED` | unset → false | `false` (explicit) |
| `AI_SOC_T4_SEMANTIC_UNDERSTANDING_ENABLED` | unset → false | `false` (explicit; omitted from git profiles) |
| `AI_SOC_LIVE_CAPABILITY_ENFORCEMENT_ENABLED` | unset → false | `false` (explicit) |
| `AI_SOC_PIPELINE_DISPATCH_V2_ENABLED` | `true` | `true` (unchanged) |

The approved profile is **conservative**: it pins the same effective posture Arm A had by
default. The difference is *explicitness*, not behaviour — which is exactly why the drill has
to prove the procedure and the effective configuration, not just the answers.

## Rollback

```bash
cp .env /root/env.intended.bak                     # 1. capture intended profile

sed -i '/^AI_SOC_RESOURCE_PLAN_EXECUTION_ENABLED=/d;\
        /^AI_SOC_T4_SEMANTIC_UNDERSTANDING_ENABLED=/d;\
        /^AI_SOC_LIVE_CAPABILITY_ENFORCEMENT_ENABLED=/d' .env        # 2a. .env

sed -i 's|^AI_SOC_RESOURCE_PLAN_EXECUTION_ENABLED=false|#ROLLBACK &|;\
        s|^AI_SOC_LIVE_CAPABILITY_ENFORCEMENT_ENABLED=false|#ROLLBACK &|' \
        env/profiles/development.env.example                          # 2b. active profile

docker compose up -d --force-recreate backend                         # 3. restart
curl -s http://127.0.0.1:8010/health                                  # 4. verify
docker compose exec -T backend printenv AI_SOC_RESOURCE_PLAN_EXECUTION_ENABLED  # expect: unset
python3 scripts/eval_plan6_vps_harness.py --arm F --environment-identity coe-vps \
  --row-id p6.t1.knowledge --row-id p6.spl.draft --row-id p6.t4.out_of_registry
```

### Rollback evidence (`docs/evals/plan6/runs/20260814T100338Z/`)

Health `ok`, `database_migrations.ready=true`.

| Flag | Effective after rollback |
|---|---|
| `AI_SOC_RESOURCE_PLAN_EXECUTION_ENABLED` | **unset** |
| `AI_SOC_T4_SEMANTIC_UNDERSTANDING_ENABLED` | **unset** |
| `AI_SOC_LIVE_CAPABILITY_ENFORCEMENT_ENABLED` | **unset** |
| `AI_SOC_PIPELINE_DISPATCH_V2_ENABLED` | `true` (pre-F2 COE value, restored) |

Smoke 3/3 exit 0, every row matching Arm A on route **and** `resource_plan_fingerprint`:

| Row | Route | Tier | Fingerprint | Arm A match | `degrade_reason` | `semantic_t4` | `phase_names` |
|---|---|---|---|---|---|---|---|
| `p6.t1.knowledge` | `knowledge_recall` | T2 | `54643926bb51081e` | ✅ | null | null | `[]` |
| `p6.t4.out_of_registry` | `guided_investigation` | T4 | `fd65002b17c46fa0` | ✅ | null | null | `[]` |
| `p6.spl.draft` | `attack_discovery` | T2 | `99ccd9213e2f0b37` | ✅ | null | null | `[]` |

Failing-first condition satisfied: **no** merge-authoritative schedule and **no** T4 invocation
on T1–T3 rows after rollback.

## Re-apply the approved profile

```bash
git checkout -- env/profiles/development.env.example   # 6. restore committed profile
cp /root/env.intended.bak .env                          # 6. restore intended .env
docker compose up -d --force-recreate backend           # 7. restart
docker compose exec -T backend printenv <each flag>     # 8. capture effective flags
curl -s http://127.0.0.1:8010/health                    # 9. verify
python3 scripts/eval_plan6_vps_harness.py --arm F ... --row-id ...   # 9. smoke
```

### Re-apply evidence (`docs/evals/plan6/runs/20260814T104455Z/`)

Health `ok`, `database_migrations.ready=true`, `telemetry.write_failures=0`.

| Flag | Effective after re-apply |
|---|---|
| `AI_SOC_RESOURCE_PLAN_EXECUTION_ENABLED` | **false** (explicit) |
| `AI_SOC_T4_SEMANTIC_UNDERSTANDING_ENABLED` | **false** (explicit) |
| `AI_SOC_LIVE_CAPABILITY_ENFORCEMENT_ENABLED` | **false** (explicit) |
| `AI_SOC_PIPELINE_DISPATCH_V2_ENABLED` | **true** |
| `LANGGRAPH_ORCHESTRATION_ENABLED` | **true** |
| `MCP_MODE` | **mock** |

Smoke 3/3 exit 0, all rows still matching Arm A:

| Row | Route | Tier | Fingerprint | Arm A match | `degrade_reason` | `semantic_t4` |
|---|---|---|---|---|---|---|
| `p6.t1.knowledge` | `knowledge_recall` | T2 | `54643926bb51081e` | ✅ | null | null |
| `p6.t4.out_of_registry` | `guided_investigation` | T4 | `fd65002b17c46fa0` | ✅ | null | null |
| `p6.spl.draft` | `attack_discovery` | T2 | `99ccd9213e2f0b37` | ✅ | null | null |

Behaviour is identical across rollback and re-apply, as expected for a conservative profile —
the drill proves the *procedure* and the *effective configuration*, which do differ.

## Final state

**The host is left in the approved Plan 6 production profile, not the rollback state.**
`git status` shows `env/profiles/*.env.example` clean; `.env` is uncommitted by design and
matches `env.intended.bak`.

## Notes for the operator

- Rolling back **must** touch the profile named by `AI_SOC_ENV_PROFILE`, not just `.env`.
- Secrets never move: `.env` stays uncommitted; only booleans live in git.
- `--force-recreate` is required — settings are read at process start, so `restart` alone can
  leave a stale env in the container.
- If a future profile ever sets execution ON, rollback must also confirm
  `debug_summary.schedule.degrade_reason` returns to `null` and `phase_names` empties.
