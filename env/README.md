# Environment profiles for AI-SOC

Stop maintaining multiple full `.env` copies. Use **one profile** + **one secrets file**.

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

## Switch profile

**CLI**

```bash
./scripts/select_env_profile.sh development
docker compose up -d --force-recreate backend
```

**UI**

Settings → **Deployment** → choose profile → Apply. Then restart the backend container
(profile changes require a restart; the UI cannot hot-reload env vars).

## COE LLM endpoint

| Field | Value |
|-------|--------|
| Base URL | `http://10.52.1.13:8002/v1` |
| Model | `foundation-sec-8b-reasoning` |
| Qwen failover (optional) | `http://10.52.1.13:8000/v1` / `./qwen72b` |

See `docs/coe/COE_FOUNDATION_SEC_8B_REASONING_HANDOFF.md` for smoke-test notes.

## Deprecated files

Use `env/profiles/coe.env.example` instead of:

- `.env.coe-live-testing.example` (subset)
- `.env.coe-llm.example` (LLM-only)
- `docs/coe/coe-8b-reasoning.env.example` (duplicate)

Those remain as pointers; the canonical COE profile is `env/profiles/coe.env.example`.
