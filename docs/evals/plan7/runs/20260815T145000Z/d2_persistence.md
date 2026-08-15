# Plan 7 D2 — persist the target profile and prove restart/recreate persistence

Git SHA at run: `589bf63`. No secret values appear below — only the Plan 7 flag names and their
non-secret booleans/numbers.

## PRE_RECREATE

**Active profile.** `AI_SOC_ENV_PROFILE=development` (`.env:7` and `env/active.profile` agree).

**Persistent config source — the P0.1-proven chain** (`docs/evals/plan7/env_authority_chain.md`):

```yaml
env_file:
  - env/profiles/${AI_SOC_ENV_PROFILE:-coe}.env.example   # loaded first
  - .env                                                   # loaded second, wins on conflict
```

So the file that actually decides is **`.env`**, and the profile file in effect is
`env/profiles/development.env.example` — *not* `coe.env.example`. No target flag is overridden
at compose service level.

**Effective flags before recreate** (read from inside the running container):

| Flag | Value |
|---|---|
| `LANGGRAPH_ORCHESTRATION_ENABLED` | `true` |
| `AI_SOC_RESOURCE_PLAN_EXECUTION_ENABLED` | `true` |
| `AI_SOC_PIPELINE_DISPATCH_V2_ENABLED` | `false` |
| `AI_SOC_T4_SEMANTIC_UNDERSTANDING_ENABLED` | `true` |
| `AI_SOC_T4_SEMANTIC_UNDERSTANDING_TIMEOUT_SECONDS` | `120` |
| `AI_SOC_LIVE_CAPABILITY_ENFORCEMENT_ENABLED` | `false` |
| `MCP_MODE` | `mock` |

**Execution authority before recreate:** 3/3 sampled rows `resource_plan_step_walk`,
`merge_active=true`, `downgrade_reason=null`, schedule
`workflow_spl → spl_postprocessor → spl_source_resolve → execution`.

## PERSISTED_CONFIGURATION

All six approved target values were already durably present in the P0.1-proven winning path and
were verified key-by-key rather than assumed:

| Flag (in `.env`) | Persisted value |
|---|---|
| `LANGGRAPH_ORCHESTRATION_ENABLED` | `true` |
| `AI_SOC_RESOURCE_PLAN_EXECUTION_ENABLED` | `true` |
| `AI_SOC_PIPELINE_DISPATCH_V2_ENABLED` | `false` |
| `AI_SOC_T4_SEMANTIC_UNDERSTANDING_ENABLED` | `true` |
| `AI_SOC_T4_SEMANTIC_UNDERSTANDING_TIMEOUT_SECONDS` | `120` |
| `AI_SOC_LIVE_CAPABILITY_ENFORCEMENT_ENABLED` | `false` |

Exact path: **`/var/www/ai-soc-assistant/.env`** (VPS-only, uncommitted, secret-bearing — values
above are the only keys quoted).

Nothing else was changed: no `config.py` default, no model/provider, no Cisco serving
configuration, no MCP scope, no capability policy, no routing rule, no new environment variable,
and `architecture.md` untouched.

### Persistence rests on an uncommitted file — recorded, not fixed

The committed profile that loads *first* holds the **opposite** posture:

| Flag | `development.env.example` (tracked) | `.env` (untracked, wins) |
|---|---|---|
| `AI_SOC_RESOURCE_PLAN_EXECUTION_ENABLED` | **`false`** | `true` |
| `AI_SOC_PIPELINE_DISPATCH_V2_ENABLED` | **`true`** | `false` |
| `AI_SOC_T4_SEMANTIC_UNDERSTANDING_ENABLED` | *absent* | `true` |
| `AI_SOC_T4_SEMANTIC_UNDERSTANDING_TIMEOUT_SECONDS` | *absent* | `120` |

The target posture therefore survives a recreate (proven below) but would **not** survive loss or
rebuild of `.env` — the host would silently fall back to exec OFF / v2 ON, i.e. the pre-Plan-7
authority. Committing the remediation values into the tracked profile would be a repo-default
change, which D2 is explicitly not permitted to make, so this is recorded for D3/E2 rather than
corrected here.

## RECREATE

Command: `docker compose up -d --force-recreate backend` — the application container only, the
procedure already used by the Plan 7 deployment workflow.

**Cisco model restart: NO.** `llama-server` PID **217320** unchanged, uptime continuous across the
operation (`01:36:20` → `01:36:48`). No `systemctl`, no control-watcher request, no scheduled or
approved restart. `HUMAN_RESTART_REQUIRED` did not arise.

## POST_RECREATE

Health: **200**.

Effective flags re-read from inside the running container — **all six match exactly, 0 failures**:

| Flag | Target | Observed |
|---|---|---|
| `LANGGRAPH_ORCHESTRATION_ENABLED` | `true` | ✅ `true` |
| `AI_SOC_RESOURCE_PLAN_EXECUTION_ENABLED` | `true` | ✅ `true` |
| `AI_SOC_PIPELINE_DISPATCH_V2_ENABLED` | `false` | ✅ `false` |
| `AI_SOC_T4_SEMANTIC_UNDERSTANDING_ENABLED` | `true` | ✅ `true` |
| `AI_SOC_T4_SEMANTIC_UNDERSTANDING_TIMEOUT_SECONDS` | `120` | ✅ `120` |
| `AI_SOC_LIVE_CAPABILITY_ENFORCEMENT_ENABLED` | `false` | ✅ `false` |

`MCP_MODE` unchanged at `mock`.

### Representative smoke (6 rows, recorded T4 proposal — no semantic corpus)

| row | route | dispatch source | merge | degrade | inserted phases | T4 | `execution_eligible` |
|---|---|---|---|---|---|---|---|
| `d0.explain_spl` | `spl_generation` | `resource_plan_step_walk` | ✅ | null | `spl_postprocessor` | invoked+accepted | null |
| `d0.generate_spl` | `spl_generation` | `resource_plan_step_walk` | ✅ | null | `spl_postprocessor` | invoked+accepted | null |
| `d0.alert_review` | `attack_discovery` | `resource_plan_step_walk` | ✅ | null | `spl_postprocessor` | — | null |
| `d0.knowledge` | `knowledge_recall` | — | — | null | — | — | null |
| `d0.spl_mcp` | `attack_discovery` | `resource_plan_step_walk` | ✅ | null | `spl_postprocessor` | — | null |
| `d0.t4_semantic` | `knowledge_recall` | `canonical_non_planned` | — | null | — | invoked+accepted | null |

All five required proofs hold:

1. simple / canonical-non-planned request works (`d0.knowledge`, `d0.t4_semantic`);
2. ResourcePlan-authoritative rows reach the ResourcePlan path — **4 rows** `resource_plan_step_walk`;
3. mandatory PhaseContract lifecycle survives — `spl_postprocessor` present on **every** seam row;
4. T4 remains enabled on T4-tier cases — **3 rows** invoked and accepted;
5. dispatch-v2 never becomes execution authority.

### Authority assertions

- `RESOURCE_PLAN_EXECUTION = active` ✅
- `DISPATCH_V2 = off` ✅
- **`V2_WINS` / dispatch-v2 ownership: 0 rows.** No `dispatch_v2_projected_schedule`, no
  v2 `downgrade_reason`.
- **A3 preserved** — `inserted_phases: ['spl_postprocessor']` on every seam row is the contract
  re-inserting mandatory lifecycle work the compiler does not schedule. Unit invariant green:
  `test_plan7_a0_mandatory_phase_survives_no_schedulable_step` + C3/D1 suites, **42 passed**.
- **Candidate SPL remains non-executable** — `execution_eligible` null on all 6 rows.

## KNOWN_OPEN_FINDINGS (carried forward unchanged — D2 fixed none of them)

- **F1** — DB loss silently downgrades execution authority to `canonical_non_planned` while still
  answering. `KNOWN_PLAN8_DEPENDENCY` / E2 visibility.
- **F2** — Cisco `/v1/models` liveness does not prove usable inference health.
  `KNOWN_PLAN8_DEPENDENCY` / Plan 8 REL0 detection; restart stays human-only.
- **F3** — Cisco serving stability unresolved; C3's
  `T4_SEMANTICALLY_VIABLE_BUT_VPS_SERVING_BLOCKER` stands.

**New for D3/E2:** the persisted posture depends on an uncommitted `.env` whose tracked
counterpart holds the opposite authority. D2 proves persistence across recreate, not across
config rebuild.

D2 PASS does not imply any of the above is closed, and is not production GO.
