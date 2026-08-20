# Mac staging Docker deployment

Clone the repo, place operator secrets and deployment overrides in **repo-root `.env` only** — no code edits required.

## Quick start (Mac → COE vLLM)

1. Copy the profile example and merge operator values:

```bash
cp env/profiles/mac-staging.env.example .env
# Add APP_AUTH_PASSWORD, APP_AUTH_SESSION_SECRET, and any port overrides below.
```

2. Example repo-root `.env` for Mac staging:

```dotenv
AI_SOC_ENV_PROFILE=mac-staging

AI_SOC_HOST_BIND=127.0.0.1
AI_SOC_BACKEND_HOST_PORT=8110
AI_SOC_FRONTEND_HOST_PORT=3100
AI_SOC_POSTGRES_HOST_PORT=5434

AI_SOC_PUBLIC_API_BASE_URL=http://127.0.0.1:8110/api
AI_SOC_CORS_ALLOWED_ORIGINS=http://localhost:3100,http://127.0.0.1:3100

AI_SOC_LLM_ENABLED=true
AI_SOC_LLM_MODE=local
AI_SOC_LLM_LOCAL_BASE_URL=http://10.52.1.13:8004/v1
AI_SOC_LLM_LOCAL_MODEL=foundation-sec-instruct
AI_SOC_LLM_FOUNDATION_SEC_REASONING_BASE_URL=http://10.52.1.13:8003/v1
AI_SOC_LLM_FOUNDATION_SEC_REASONING_MODEL=foundation-sec-reasoning
AI_SOC_LLM_TIMEOUT_SECONDS=120
AI_SOC_LLM_MAX_INPUT_TOKENS=12000
AI_SOC_LLM_MAX_OUTPUT_TOKENS=1024

AI_SOC_LLM_FINAL_SYNTHESIS_ENABLED=true
AI_SOC_LLM_LIVE_SYNTHESIS_ENABLED=true
AI_SOC_LLM_SPL_FALLBACK_ENABLED=false
LLM_TOOL_RECOMMENDATION_ENABLED=false

APP_AUTH_PASSWORD=<operator-secret>
APP_AUTH_SESSION_SECRET=<operator-secret>
```

3. Preflight (no containers started):

```bash
./scripts/coe_preflight.sh
```

4. Deploy and verify:

```bash
./scripts/coe_deploy_verify.sh
```

5. Open:

- Frontend: `http://127.0.0.1:3100` (or your `AI_SOC_FRONTEND_HOST_PORT`)
- Backend API: `http://127.0.0.1:8110/api` (or your `AI_SOC_BACKEND_HOST_PORT`)

The backend container calls COE vLLM at `AI_SOC_LLM_LOCAL_BASE_URL` (default profile: `http://10.52.1.13:8004/v1`, served name `foundation-sec-instruct`; reasoning roles use `http://10.52.1.13:8003/v1` / `foundation-sec-reasoning`). COE vLLM must be reachable from the Mac host and from inside the backend container.

## Changing ports

1. Edit **repo-root `.env` only** — pick free host ports on your machine.
2. Keep **internal container ports unchanged** (`8010` backend, `3010` frontend, `5432` postgres).
3. Set matching cross-service URLs:
   - `AI_SOC_PUBLIC_API_BASE_URL` → `http://127.0.0.1:<backend-host-port>/api`
   - `AI_SOC_CORS_ALLOWED_ORIGINS` → frontend origin(s) on the new host port
4. Run `./scripts/coe_preflight.sh` to render Compose and check for port collisions.
5. Run `./scripts/coe_deploy_verify.sh` to build, start, and smoke-test.

## Compose variable reference

| Variable | Default | Purpose |
|----------|---------|---------|
| `AI_SOC_ENV_PROFILE` | `coe` | Profile file under `env/profiles/` |
| `AI_SOC_HOST_BIND` | `127.0.0.1` | Host interface for published ports |
| `AI_SOC_BACKEND_HOST_PORT` | `8010` | Host port → container `8010` |
| `AI_SOC_FRONTEND_HOST_PORT` | `3010` | Host port → container `3010` |
| `AI_SOC_POSTGRES_HOST_PORT` | `5434` | Host port → container `5432` |
| `AI_SOC_PUBLIC_API_BASE_URL` | `http://127.0.0.1:8010/api` | Vite `VITE_API_BASE_URL` in frontend container |
| `AI_SOC_CORS_ALLOWED_ORIGINS` | `http://localhost:3010,http://127.0.0.1:3010` | FastAPI CORS allowlist (comma-separated) |

## COE deployment

The same scripts read repo-root `.env`. Use `AI_SOC_ENV_PROFILE=coe` (or operator-provided COE profile) and set host ports / API base URL for the target environment. Preflight optionally probes vLLM `/health` and `/v1/models` from the host when `AI_SOC_LLM_LOCAL_BASE_URL` is set.
