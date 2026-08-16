# COE deployment runbook — Git clone to running stack

**Audience:** COE operator deploying AI SOC Assistant onto a COE host from the Git repository.

**Scope:** every step from a bare host to a verified running stack, plus the update and rollback flow. No code edits are required at any point — all environment differences live in repo-root `.env`.

**Related docs**

- Production readiness (qualification, smoke, rollback, GO matrix): [`COE_PRODUCTION_READINESS_RUNBOOK.md`](COE_PRODUCTION_READINESS_RUNBOOK.md)
- Profile loader and variable precedence: [`env/README.md`](../../env/README.md)
- COE feature-flag table: [`COE_ROLLOUT_CONFIGURATION.md`](COE_ROLLOUT_CONFIGURATION.md)
- Live/mock/EC testing layers: [`COE_LIVE_TESTING_GUIDE.md`](COE_LIVE_TESTING_GUIDE.md)
- Nginx/TLS production layout: [`../deployment.md`](../deployment.md)
- Live Splunk MCP connect: [`../../contracts/splunk_mcp_connection_contract.md`](../../contracts/splunk_mcp_connection_contract.md)

---

## 0. Prerequisites on the COE host

| Requirement | Check | Notes |
|-------------|-------|-------|
| Docker Engine + Compose **v2** | `docker compose version` | Must be the `docker compose` plugin, not legacy `docker-compose` |
| Git | `git --version` | |
| `ss` or `lsof` | `command -v ss lsof` | Required by the port preflight |
| `curl` | `curl --version` | Used by the health smoke |
| Disk | `df -h .` | ~6 GB for images + Postgres volume |
| Outbound access | — | Needed at build time for Docker Hub, PyPI, npm. Air-gapped hosts need a pre-seeded registry/mirror. |

The user running `docker compose` must be in the `docker` group (or use `sudo` consistently for every command in this runbook).

---

## 1. Get the code from Git

### 1a. Grant the host access to the repository

The repo is private. Pick one:

**SSH deploy key (recommended for a long-lived COE host)**

```bash
ssh-keygen -t ed25519 -C "coe-host-ai-soc" -f ~/.ssh/id_ed25519_ai_soc -N ""
cat ~/.ssh/id_ed25519_ai_soc.pub
```

Add the printed public key in GitHub under **Repo → Settings → Deploy keys → Add deploy key**. Leave *Allow write access* unchecked — the COE host only needs to pull.

Then map the key to GitHub in `~/.ssh/config`:

```
Host github.com
  IdentityFile ~/.ssh/id_ed25519_ai_soc
  IdentitiesOnly yes
```

Verify: `ssh -T git@github.com` → expect `Hi <user>! You've successfully authenticated`.

**HTTPS + personal access token** — use if outbound SSH (port 22) is blocked:

```bash
git clone https://<username>:<token>@github.com/Anurag-go4gst/ai-soc-assistant.git
```

The token is then stored in `.git/config` in cleartext. If you use this form, `chmod 600 .git/config` and prefer a fine-grained, read-only, expiring token.

### 1b. Clone

```bash
sudo mkdir -p /opt/ai-soc && sudo chown "$USER" /opt/ai-soc
cd /opt/ai-soc
git clone git@github.com:Anurag-go4gst/ai-soc-assistant.git
cd ai-soc-assistant
git log --oneline -1     # record this commit in your deployment log
```

Any parent directory works. The stack is not path-dependent.

> **Note on the directory name.** Compose derives its project name from the directory name. Step 2 pins `COMPOSE_PROJECT_NAME` in `.env` so that a rename later does not orphan the running containers.

### 1c. Confirm what Git does and does not carry

`.env`, `env/profiles/*.env`, and all secrets are **gitignored**. A fresh clone therefore has **no** credentials — Step 3 creates them. Only `*.env.example` profile templates are tracked. Never commit a filled-in `.env` back.

---

## 2. Resolve host ports and seed `.env`

This is the step that most often breaks a COE bring-up: default ports `8010` / `3010` / `5434` are frequently already taken by something else on the host.

```bash
./scripts/coe_preflight.sh --auto-port
```

What it does, in order:

1. Seeds repo-root `.env` from `env/profiles/<profile>.env.example` if `.env` is absent (default profile `coe`; override with `AI_SOC_ENV_PROFILE=<name>`).
2. Picks free host ports, walking upward from `8010` / `3010` / `5434` when they are in use.
3. Rewrites the **derived** keys in the same pass:
   - `AI_SOC_PUBLIC_API_BASE_URL` → follows the backend port
   - `AI_SOC_CORS_ALLOWED_ORIGINS` → follows the frontend port
4. Pins `COMPOSE_PROJECT_NAME`.
5. Validates config (empty or wildcard CORS is rejected) and renders `docker compose config`.

> **Do not hand-edit a single `AI_SOC_*_HOST_PORT` key.** The backend port is mirrored into `AI_SOC_PUBLIC_API_BASE_URL` and the frontend port into `AI_SOC_CORS_ALLOWED_ORIGINS`. Moving one alone yields a stack that starts cleanly but whose UI cannot call the API — a failure that looks like an application bug. `--auto-port` moves all of them together.

Re-running is safe. Ports already published by this compose project are kept, so the command is a no-op against a stack that is already up.

Read-only variants:

```bash
./scripts/coe_preflight.sh                     # check only; exit 2 = a port is in use
./scripts/coe_port_autoselect.sh --dry-run     # show the port plan, write nothing
```

Note the three ports printed at the end — later steps refer to them as `<BACKEND_PORT>` and `<FRONTEND_PORT>`.

**Container-side ports never change.** Only the host side moves. Inside the containers it is always backend `8010`, frontend `3010`, postgres `5432`.

---

## 3. Fill in operator secrets

Open `.env` and set at minimum:

```dotenv
APP_AUTH_ENABLED=true
APP_AUTH_USER=analyst
APP_AUTH_PASSWORD=<choose a strong password>
APP_AUTH_SESSION_SECRET=<random 32+ byte string>
```

Generate the session secret:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(48))"
```

Lock the file down:

```bash
chmod 600 .env
```

Do not commit `.env`, and do not paste secrets into tickets, chat, or plan documents.

---

## 4. Point the backend at the COE LLM endpoint

In `.env`:

```dotenv
AI_SOC_LLM_ENABLED=true
AI_SOC_LLM_MODE=local
AI_SOC_LLM_LOCAL_BASE_URL=http://<llm-host>:<port>/v1
AI_SOC_LLM_LOCAL_MODEL=<model-id-as-served>
AI_SOC_LLM_TIMEOUT_SECONDS=120
# Required when the COE profile enables T4. Do not leave unset (code default 2.0s
# is rejected). Do not copy the VPS 120s T4 bound as a COE SLO; measure on COE.
AI_SOC_T4_SEMANTIC_UNDERSTANDING_TIMEOUT_SECONDS=<operator-supplied-seconds>
```

Reachability rule: the URL must resolve **from inside the backend container**, not just from the host shell.

| LLM runs on | Use |
|-------------|-----|
| A separate COE server | Its routable IP/hostname, e.g. `http://10.52.1.13:8002/v1` |
| The same host, bound to `127.0.0.1` | `http://host.docker.internal:<port>/v1` — compose already maps `host.docker.internal` to the host gateway |

`host.docker.internal` does **not** resolve from the host shell, so the preflight's optional vLLM probe reports `Could not resolve host` in that configuration. That warning is expected and does not block deployment. Verify from inside the container instead, after Step 5:

```bash
docker compose exec backend curl -fsS "${AI_SOC_LLM_LOCAL_BASE_URL%/v1}/health"
```

If no LLM is available yet, set `AI_SOC_LLM_ENABLED=false`. The stack still runs — deterministic routing, SPL validation, and the Experience Center all work without a model.

---

## 5. Build, start, and verify

One command does build + up + health smoke:

```bash
./scripts/coe_deploy_verify.sh
```

Or run the steps manually:

```bash
docker compose build
docker compose up -d
docker compose ps
curl -s http://127.0.0.1:<BACKEND_PORT>/health
```

Expect a JSON OK response from `/health`.

First build pulls base images and installs dependencies — allow 5–15 minutes depending on network. Database migrations run automatically from the backend entrypoint; if a migration fails the backend **refuses to start** rather than serving against a bad schema, and the error appears in `docker compose logs backend`.

Then open the UI at `http://127.0.0.1:<FRONTEND_PORT>` and log in with `APP_AUTH_USER` / `APP_AUTH_PASSWORD`.

**Security posture:** all three ports bind to `127.0.0.1` via `AI_SOC_HOST_BIND`. Do not change this to `0.0.0.0` to "make it reachable" — Postgres and the backend would be exposed on the network. For access beyond the host, put a reverse proxy in front (Step 6).

---

## 6. Optional — serve the UI through Nginx

The `frontend` container is the **Vite dev server**. For anything beyond a single operator on the host, serve the static production build instead.

```bash
cd frontend
npm install
npm run build       # postbuild chmods dist so Nginx (www-data) can read it
cd ..
```

Use [`docs/nginx-ai-soc-assistant.example.conf`](../nginx-ai-soc-assistant.example.conf) as the site template:

- `root` → `<repo>/frontend/dist`
- `proxy_pass` for `/api/` and `/health` → `http://127.0.0.1:<BACKEND_PORT>`

**If you changed the backend port in Step 2, the Nginx `proxy_pass` upstream must be updated to match.** This is the one port dependency the scripts cannot update for you, because the Nginx config lives outside the repo.

Add the browser-facing origin to CORS in `.env` (auto-port preserves non-loopback origins on later runs):

```dotenv
AI_SOC_CORS_ALLOWED_ORIGINS=http://localhost:<FRONTEND_PORT>,http://127.0.0.1:<FRONTEND_PORT>,https://<your-coe-hostname>
```

Then:

```bash
sudo nginx -t && sudo systemctl reload nginx
docker compose restart backend    # CORS is read at startup
```

---

## 7. Updating from Git

```bash
cd /opt/ai-soc/ai-soc-assistant
git pull --ff-only origin master
./scripts/coe_preflight.sh --auto-port     # picks up any new/renamed env keys
docker compose up -d --build
curl -s http://127.0.0.1:<BACKEND_PORT>/health
```

Notes:

- `--ff-only` is deliberate. Never rebase or merge on the COE host — it is a deployment target, not a development checkout.
- `.env` is untracked, so `git pull` never overwrites your secrets or ports.
- When a release adds new variables, they land in `env/profiles/*.env.example`. Diff and merge the ones you need:
  ```bash
  diff <(sed 's/=.*//' env/profiles/coe.env.example | sort) <(sed 's/=.*//' .env | sort)
  ```
- Backend runs uvicorn with `--reload`, so a pull that only touches Python is picked up without a rebuild. Rebuild is required for `pyproject.toml`, `package.json`, or Dockerfile changes — `up -d --build` covers both cases safely.
- UI changes require `npm run build` again if you serve via Nginx (Step 6).

**Rollback:**

```bash
git log --oneline -10
git checkout <last-known-good-commit>
docker compose up -d --build
```

Postgres data lives in the named volume `ai_soc_postgres_data` and survives `git checkout`, `docker compose down`, and rebuilds.

---

## 8. Everyday operations

```bash
docker compose ps                              # what is running
docker compose logs -f backend                 # follow backend logs
docker compose logs backend --tail=120         # recent backend errors
docker compose restart backend                 # apply .env changes
docker compose down                            # stop, keep database
docker compose down -v                         # stop AND DELETE the database volume
```

`docker compose down -v` destroys all Postgres data for this stack. It is not reversible without a backup — use it only for a deliberate clean reset.

Backup / restore the database:

```bash
docker compose exec postgres pg_dump -U ai_soc ai_soc_assistant > ai_soc_backup_$(date +%F).sql
cat ai_soc_backup_2026-08-05.sql | docker compose exec -T postgres psql -U ai_soc ai_soc_assistant
```

---

## 9. Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `Bind for 127.0.0.1:8010 failed: port is already allocated` | Host port taken by another service | `./scripts/coe_preflight.sh --auto-port`, then `docker compose up -d` |
| Stack starts, UI loads, but every request fails with a CORS error | Frontend port moved, `AI_SOC_CORS_ALLOWED_ORIGINS` did not | Run `--auto-port`; add your external hostname if serving via Nginx; `docker compose restart backend` |
| UI loads but all API calls 404 or hit the wrong port | `AI_SOC_PUBLIC_API_BASE_URL` out of sync with the backend port | Run `--auto-port`, then `docker compose up -d` (the frontend reads it at container start) |
| A script exits with `line 52: pgcil_soc,: command not found` | Something reintroduced `source .env`. `.env` holds unquoted JSON (`AI_SOC_SOURCE_PROFILE_MAP`) that Docker's `env_file` parser accepts but bash cannot evaluate | Read `.env` via `scripts/lib/dotenv.sh` (`dotenv_get`), never `set -a; source .env` |
| Backend container exits immediately | Migration failure, or a required env var missing/invalid | `docker compose logs backend --tail=80` — the entrypoint prints the reason and refuses to start |
| Public site returns **403 Forbidden** | `frontend/dist` not readable by `www-data` (restrictive umask) | `chmod -R a+rX frontend/dist`; check `/var/log/nginx/ai-soc-assistant.error.log` |
| Preflight warns `vLLM /health unreachable` | Using `host.docker.internal`, which only resolves inside containers | Expected. Verify with `docker compose exec backend curl ...` (Step 4) |
| LLM answers time out or never return | Endpoint unreachable from the container, or model too slow for the timeout | Probe from inside the container; raise `AI_SOC_LLM_TIMEOUT_SECONDS`; check the LLM host's own load |
| `permission denied` on the Docker socket | User not in the `docker` group | `sudo usermod -aG docker "$USER"`, then log out and back in |
| Login page rejects correct credentials | `.env` edited but backend not restarted | `docker compose restart backend` |
| Containers from an older copy of the repo still hold the ports | Directory renamed, so Compose used a different project name | `COMPOSE_PROJECT_NAME` is pinned in `.env` by Step 2; stop strays with `docker ps` + `docker rm -f <id>` |

---

## 10. Post-deploy checklist

- [ ] `git log --oneline -1` recorded in the deployment log
- [ ] `.env` is `chmod 600` and **not** committed
- [ ] `APP_AUTH_PASSWORD` and `APP_AUTH_SESSION_SECRET` are real values, not placeholders
- [ ] `./scripts/coe_preflight.sh` exits `PREFLIGHT: OK`
- [ ] `/health` returns JSON OK on `<BACKEND_PORT>`
- [ ] UI login works
- [ ] One end-to-end question answered in chat
- [ ] `AI_SOC_HOST_BIND` is still `127.0.0.1`
- [ ] MCP execution flags still `false` unless a live Splunk rollout was explicitly approved (`MCP_GLOBAL_EXECUTION_ENABLED`, `MCP_SERVER_*_EXECUTION_ENABLED`) — see [`COE_ROLLOUT_CONFIGURATION.md`](COE_ROLLOUT_CONFIGURATION.md)
- [ ] Feature flags reviewed against the COE flag table in `COE_ROLLOUT_CONFIGURATION.md`

---

## 11. Quick reference

```bash
# First deploy
git clone git@github.com:Anurag-go4gst/ai-soc-assistant.git && cd ai-soc-assistant
./scripts/coe_preflight.sh --auto-port
$EDITOR .env                       # APP_AUTH_PASSWORD, APP_AUTH_SESSION_SECRET, LLM URL
chmod 600 .env
./scripts/coe_deploy_verify.sh

# Update
git pull --ff-only origin master
./scripts/coe_preflight.sh --auto-port
docker compose up -d --build
```

| Variable | Default | Purpose |
|----------|---------|---------|
| `AI_SOC_ENV_PROFILE` | `coe` | Profile file under `env/profiles/` |
| `AI_SOC_HOST_BIND` | `127.0.0.1` | Host interface for published ports — keep as loopback |
| `AI_SOC_BACKEND_HOST_PORT` | `8010` | Host port → container `8010` |
| `AI_SOC_FRONTEND_HOST_PORT` | `3010` | Host port → container `3010` |
| `AI_SOC_POSTGRES_HOST_PORT` | `5434` | Host port → container `5432` |
| `AI_SOC_PUBLIC_API_BASE_URL` | `http://127.0.0.1:8010/api` | Injected as `VITE_API_BASE_URL` — must track the backend port |
| `AI_SOC_CORS_ALLOWED_ORIGINS` | `http://localhost:3010,http://127.0.0.1:3010` | FastAPI CORS allowlist — must track the frontend port |
| `COMPOSE_PROJECT_NAME` | repo directory name | Pins the Compose project across directory renames |

| Script | Purpose |
|--------|---------|
| `scripts/coe_port_autoselect.sh` | Pick free host ports, rewrite derived API/CORS keys in `.env` |
| `scripts/coe_preflight.sh [--auto-port]` | Validate config and ports; `--auto-port` also fixes them |
| `scripts/coe_deploy_verify.sh` | Build, start, and smoke-test the stack |
| `scripts/lib/dotenv.sh` | Safe `.env` reader for scripts (no shell eval) |
