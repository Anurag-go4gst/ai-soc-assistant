---
name: dev-up
description: Build and start the AI SOC Assistant Docker stack (backend, frontend, postgres) and verify backend health. Use when the user says "start the app", "run dev", "bring it up", "spin up the stack", or `/dev-up`.
---

Bring up the full dev stack via Docker Compose and verify it's healthy.

## Steps

1. Resolve host ports and validate config in one step:
   ```bash
   ./scripts/coe_preflight.sh --auto-port
   ```
   This seeds `.env` from `env/profiles/<profile>.env.example` if missing, picks free host ports (walking up from 8010/3010/5434 when they are taken), and rewrites the derived keys `AI_SOC_PUBLIC_API_BASE_URL` and `AI_SOC_CORS_ALLOWED_ORIGINS` to match. Ports already published by this compose project are kept, so re-running is a no-op.

   Drop `--auto-port` to check without modifying `.env` (exit 2 = a port is in use).

2. If `.env` was just seeded, tell the user to fill the secrets (`APP_AUTH_PASSWORD`, `APP_AUTH_SESSION_SECRET`, Splunk/LLM tokens if enabled) before continuing. Do not start with placeholder secrets.

3. From repo root, run:
   ```bash
   docker compose build
   docker compose up -d
   ```

4. Wait briefly, then verify backend health at the port preflight reported:
   ```bash
   curl -s http://127.0.0.1:${AI_SOC_BACKEND_HOST_PORT:-8010}/health
   ```
   Expect a JSON OK response. If it fails, run `docker compose logs backend --tail=80` and report the error.

   `./scripts/coe_deploy_verify.sh` does build + up + this smoke in one command.

5. Report bound URLs, using the ports preflight resolved (defaults shown):
   - Backend: http://127.0.0.1:8010
   - Frontend dev: http://127.0.0.1:3010
   - Postgres: 127.0.0.1:5434
   - Public (via Nginx): https://cisco-vai.vnudge.com

5. If the user wants to follow logs: `docker compose logs -f backend frontend`. Don't tail logs by default — only on request.

## Notes

- All service ports are bound to `127.0.0.1` (`AI_SOC_HOST_BIND`). Don't suggest changing that without confirming — production access is via Nginx only.
- Never hand-edit a single `AI_SOC_*_HOST_PORT` key. The backend port is mirrored into `AI_SOC_PUBLIC_API_BASE_URL` and the frontend port into `AI_SOC_CORS_ALLOWED_ORIGINS`; changing one alone yields a stack that starts but whose UI cannot call the API. Use `scripts/coe_port_autoselect.sh`, which moves all of them together.
- On a host with a non-default port set, Nginx's `proxy_pass` upstream must be updated to match the new backend port.
- Helper scripts read `.env` via `scripts/lib/dotenv.sh`, not `source`. `.env` holds unquoted JSON (`AI_SOC_SOURCE_PROFILE_MAP`) that Docker's `env_file` parser accepts but bash cannot evaluate. Don't reintroduce `set -a; source .env`.
- Production UI is served from `frontend/dist` by Nginx (not the Vite dev container). After UI changes: `cd frontend && npm run build` — `postbuild` chmods `dist` for `www-data`. If the public site shows **403 Forbidden**, run `chmod -R a+rX frontend/dist` and check `/var/log/nginx/ai-soc-assistant.error.log`.
- Backend runs uvicorn with `--reload`; code edits take effect without rebuild. Rebuild only for dependency changes (`pyproject.toml`, `package.json`) or Dockerfile edits.
- For a clean reset: `docker compose down -v` drops volumes including Postgres data. Confirm with the user before running.
