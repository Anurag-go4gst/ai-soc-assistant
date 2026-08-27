# AI-SOC environment profiles

Stop maintaining multiple full `.env` copies. Use **one profile** + **one secrets file**.

**COE rollout (post S2–S6d):** [`docs/coe/COE_ROLLOUT_CONFIGURATION.md`](../docs/coe/COE_ROLLOUT_CONFIGURATION.md) — recommended flags, smoke checklist, status classification.

## Layout

```
env/
  active.profile          # current profile id (e.g. coe) — updated by UI or script
  profiles/
    manifest.json         # profile list for Settings → Deployment
    coe.env.example       # full COE config (committed)
    development.env.example
.env                      # secrets + AI_SOC_ENV_PROFILE override only (gitignored)
```

## Quick start (COE)

```bash
# 1) Root .env — secrets only (copy template)
cp .env.selector.example .env
# Edit: APP_AUTH_PASSWORD, APP_AUTH_SESSION_SECRET, optional SPLUNK_MCP_TOKEN, NVD_API_KEY

# 2) Select COE profile
./scripts/select_env_profile.sh coe

# 3) Start stack
docker compose up -d --force-recreate backend
```

## How loading works

`docker-compose.yml` loads **in order** (later overrides earlier):

1. `env/profiles/${AI_SOC_ENV_PROFILE}.env.example` — full posture flags
2. `.env` — secrets and optional per-operator overrides

`AI_SOC_ENV_PROFILE` is read from the repo-root `.env` for Compose variable substitution.
Default profile if unset: **coe**.

## COE Mock profile (test-only)

`coe-mock` (`env/profiles/coe-mock.env.example`) is a **non-default, test-only** profile for
isolated mock-MCP orchestration proofs (post-P10 Phase 5). It uses existing flag names only:

- `MCP_MODE=mock`
- `MCP_GLOBAL_EXECUTION_ENABLED=true`
- `MCP_SERVER_MOCK_EXECUTION_ENABLED=true`
- `SPLUNK_MCP_ENABLED=false` with empty URL/token

It is registered in `manifest.json` with `"test_only": true`. Compose and default COE stay on
`coe` with `MCP_GLOBAL_EXECUTION_ENABLED=false`. Do **not** select `coe-mock` as a production or
COE deployment profile. Mock results are simulated only — not live SourceEvidence, and they cannot
grant write/remediation/`live_mcp_proven`. P11 remains NOT STARTED.

## Switch profile

**CLI**

```bash
./scripts/select_env_profile.sh development
docker compose up -d --force-recreate backend
```

**UI**

Settings → **Deployment** → choose profile → Apply. Then restart the backend container
(profile changes require a restart; the UI cannot hot-reload env vars).

## COE guided hybrid Batch 1

With `AI_SOC_GUIDED_HYBRID_INVESTIGATION_ENABLED=true` (canonical planning always on),
out-of-catalog guided hunts use `guided_hybrid_dispatch` (not legacy `rag_early`).

Sample query: *How should I investigate unusual outbound traffic from an OT host overnight?*

Expected trace signals: `dispatch_source=guided_hybrid_dispatch`, `investigation_planning_enabled=true`,
`safe_spl_execution_allowed=false`, `execution.status=skipped`.

Batch 1 profile keeps `MCP_MODE=mock`. `MCP_GLOBAL_EXECUTION_ENABLED` /
`MCP_SERVER_MOCK_EXECUTION_ENABLED` on that mock lane are **not** live Splunk.
Live Splunk requires `MCP_MODE=registry` plus operator credentials.

## COE LLM endpoint

Office-network only — these IPs are unreachable from the VPS dev host, so the
`coe.env.example` values cannot be smoke-tested outside the Velocis LAN.

| Role | Base URL | Served model name |
|------|----------|-------------------|
| Instruct (primary) | `http://10.52.1.13:8004/v1` | `foundation-sec-instruct` |
| Reasoning (reasoning roles only) | `http://10.52.1.13:8003/v1` | `foundation-sec-reasoning` |
| Qwen failover (optional) | `http://10.52.1.13:8000/v1` | `./qwen72b` |

Both are OpenAI-compatible; `model` must match the served name exactly. No API key.

Reasoning is prepended to the failover chain only for `REASONING_ROLES`
(`backend/app/llm/clients/endpoint_resolver.py`); every other role uses instruct.

Smoke from inside the backend container before trusting a COE run:

```bash
curl http://10.52.1.13:8004/v1/chat/completions -H 'Content-Type: application/json' \
  -d '{"model":"foundation-sec-instruct","messages":[{"role":"user","content":"hi"}]}'
```

See `docs/coe/COE_FOUNDATION_SEC_8B_REASONING_HANDOFF.md` for the earlier `:8002`
smoke-test notes and the caveats that are still unverified on these endpoints.

### Switching endpoints without editing `.env`

**Settings → LLM Connection** has a *Deployment preset* picker (`VPS dev` /
`COE Velocis LAN`). Choosing one fills the form; **Save & apply** persists it to
`backend/data/llm_connection.json` and applies live — no restart, no redeploy. It
repoints the primary endpoint (every governed role **and** the Ask LLM lab) plus the
reasoning hop in one save, so switching sites cannot strand the other site's
reasoning URL in the failover chain.

Two operator gotchas:

- A saved override **shadows `.env` on every startup**. Editing the env profile after
  a save changes nothing until the override is re-saved or the JSON file removed.
- **Test connection** verifies the **saved** connection, not the form — so the order
  is pick preset → Save & apply → Test. It exercises the primary endpoint only;
  check the reasoning endpoint with the `curl :8003` step in
  [`docs/coe/COE_FOUNDATION_SEC_8B_REASONING_HANDOFF.md`](../docs/coe/COE_FOUNDATION_SEC_8B_REASONING_HANDOFF.md).

## Deprecated files

Use `env/profiles/coe.env.example` instead of:

- `.env.coe-live-testing.example` (subset)
- `.env.coe-llm.example` (LLM-only)
- `docs/coe/coe-8b-reasoning.env.example` (duplicate)

Those remain as pointers; the canonical COE profile is `env/profiles/coe.env.example`.
