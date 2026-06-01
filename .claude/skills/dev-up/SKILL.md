---
name: dev-up
description: Build and start the AI SOC Assistant Docker stack (backend, frontend, postgres) and verify backend health. Use when the user says "start the app", "run dev", "bring it up", "spin up the stack", or `/dev-up`.
---

Bring up the full dev stack via Docker Compose and verify it's healthy.

## Steps

1. Check `.env` exists at repo root. If missing, copy from `.env.example` and tell the user to fill in the secrets (especially `APP_AUTH_PASSWORD`, `APP_AUTH_SESSION_SECRET`, Splunk/LLM tokens if enabled) before continuing. Do not start with placeholder secrets.

2. From repo root, run:
   ```bash
   docker compose build
   docker compose up -d
   ```

3. Wait briefly, then verify backend health:
   ```bash
   curl -s http://127.0.0.1:8010/health
   ```
   Expect a JSON OK response. If it fails, run `docker compose logs backend --tail=80` and report the error.

4. Report bound URLs:
   - Backend: http://127.0.0.1:8010
   - Frontend dev: http://127.0.0.1:3010
   - Postgres: 127.0.0.1:5434
   - Public (via Nginx): https://cisco-vai.vnudge.com

5. If the user wants to follow logs: `docker compose logs -f backend frontend`. Don't tail logs by default — only on request.

## Notes

- All service ports are bound to `127.0.0.1`. Don't suggest changing that without confirming — production access is via Nginx only.
- Backend runs uvicorn with `--reload`; code edits take effect without rebuild. Rebuild only for dependency changes (`pyproject.toml`, `package.json`) or Dockerfile edits.
- For a clean reset: `docker compose down -v` drops volumes including Postgres data. Confirm with the user before running.
