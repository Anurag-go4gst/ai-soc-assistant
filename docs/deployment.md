# Deployment

Docker Compose is the default local and runtime setup for this scaffold. Use `docker compose`, the Compose v2 Docker CLI plugin command.

## Current Production-Style Layout

- Public URL: `https://cisco-vai.vnudge.com`.
- Nginx site config path: `/etc/nginx/sites-available/ai-soc-assistant.conf`.
- Frontend static path: `/var/www/ai-soc-assistant/frontend/dist`.
- Backend local port: `127.0.0.1:8010`.
- Frontend dev port, if running: `127.0.0.1:3010`.
- Postgres local host port: `127.0.0.1:5434`.

Production access is intended to go through Nginx only. Docker service ports are bound to localhost so backend, frontend dev server, and Postgres are not directly exposed on public interfaces.

## Access Control

The site is publicly reachable through Nginx and protected by app-level login in the FastAPI backend. Nginx Basic Auth has been removed from the AI SOC site config, so browsers load the React login page without a native Basic Auth popup.

App auth credentials are read from `.env`:

```text
APP_AUTH_ENABLED=true
APP_AUTH_USER=analyst
APP_AUTH_PASSWORD=<secret>
APP_AUTH_SESSION_SECRET=<secret>
```

Do not commit `.env`, passwords, or session secrets. The backend and Postgres remain localhost-only.

## Frontend UI Foundation

The frontend uses Tailwind CSS with local shadcn-style components, Radix primitives, and lucide-react icons. Support Buddy at `/var/www/support-buddy` was used only as a read-only UI/UX reference for layout, cards, chat patterns, and shell structure. AI SOC does not import from Support Buddy at runtime and does not copy its secrets, localStorage auth, HR/customer data, ticket logic, or deployment configuration.

Current UI surfaces:

- Public app-level login page.
- Authenticated SOC cockpit shell.
- Scenario rail with brute-force, DB pool, and OT anomaly examples.
- Investigation chat workspace with starter prompts.
- Evidence, SOP, graph context, MITRE, approval, SPL trace, and routing debug panels.

## SSL Status

SSL is configured with Certbot for `cisco-vai.vnudge.com`. HTTP redirects to HTTPS.

Certbot renewal is handled by the existing `certbot.timer` systemd timer. `certbot renew --dry-run` succeeded for `cisco-vai.vnudge.com`.

## Rebuild Frontend And Reload Nginx

```bash
cd /var/www/ai-soc-assistant/frontend
npm install
npm run build

nginx -t
systemctl reload nginx
```

## Docker Restart

```bash
cd /var/www/ai-soc-assistant
docker compose up -d --build
```

## Verification Commands

```bash
dig +short cisco-vai.vnudge.com
curl -4 ifconfig.me
curl -s http://127.0.0.1:8010/health
ss -ltnp | grep -E '8010|3010|5434'
curl -I http://cisco-vai.vnudge.com
curl -I https://cisco-vai.vnudge.com
curl -s https://cisco-vai.vnudge.com/health
curl -i -X POST https://cisco-vai.vnudge.com/api/chat \
  -H 'Content-Type: application/json' \
  -d '{"query":"test"}'
certbot renew --dry-run
```

## UI Routing

The React app is now multi-page via `react-router-dom`. Top-level routes served from `frontend/dist`:

- `/cockpit` (default redirect from `/`)
- `/chat`, `/investigations`, `/scenarios`, `/knowledge`
- `/settings`, `/debug`

The Nginx config already serves `frontend/dist/index.html` as the SPA fallback, so client-side routes do not require additional Nginx changes.

## Settings Status Endpoint

`GET /api/settings/status` returns a JSON snapshot of MCP / RAG / LLM / Routing / Safeguards / Observability configuration. It is **read-only and non-secret**: tokens, passwords, and session secrets are never returned, only `*_configured: bool` flags. The Settings page in the SPA consumes this endpoint and falls back to a bundled mock if the backend is unreachable.

MCP, RAG, and LLM are still in mock mode in this scaffold. The endpoint reflects that state.
