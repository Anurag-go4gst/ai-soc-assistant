# LLM control watcher + how to query `/chat`

## A. LLM service control (UI Stop / Restart / Start)

Live **runtime health** (tok/s) works with no extra setup — open the LLM Registry
settings panel and use **Refresh**. The **Stop / Restart / Start** buttons are
default-OFF because they are a privileged control surface, and because the
Dockerized backend must never touch host systemd. Enabling them is host-side work.

### How it works

```
Browser → POST /api/settings/llm/control {action}
        → backend writes a JSON sentinel into the shared volume
            (container: /var/lib/ai-soc/llm-control  ==  host: <repo>/.llm-control)
        → host watcher (systemd) reads it, runs `systemctl <action> llama-server.service`,
          writes last_result.json
        → UI shows "Last action: … applied"
```

The web app holds **no** host privileges. Only `restart` / `stop` / `start` on the
single `llama-server.service` are permitted.

### Enable (one time, on the host)

1. **Backend flags** — in `.env`:
   ```
   AI_SOC_LLM_CONTROL_ENABLED=true
   AI_SOC_LLM_CONTROL_DIR=/var/lib/ai-soc/llm-control
   ```
   then `docker compose up -d backend`.

2. **Watcher user + control dir**:
   ```bash
   sudo useradd --system --no-create-home --shell /usr/sbin/nologin ai-soc-control
   sudo install -d -o ai-soc-control -g ai-soc-control /var/www/ai-soc-assistant/.llm-control
   ```
   (The docker-compose bind mount `./.llm-control:/var/lib/ai-soc/llm-control` shares
   this directory between host and container.)

3. **Sudoers** — grant only the three allow-listed systemctl actions:
   ```bash
   sudo install -m 0440 deploy/llm-control-watcher.sudoers /etc/sudoers.d/ai-soc-llm-control
   sudo visudo -c
   ```

4. **Systemd unit**:
   ```bash
   sudo install -m 0644 deploy/llm-control-watcher.service /etc/systemd/system/llm-control-watcher.service
   sudo systemctl daemon-reload
   sudo systemctl enable --now llm-control-watcher.service
   sudo systemctl status llm-control-watcher.service
   ```

### Verify
```bash
# Health (auth required):
curl -s -b cookies.txt https://cisco-vai.vnudge.com/api/settings/llm/runtime-health | jq

# Apply a restart, then watch the watcher log + last_result.json:
journalctl -u llm-control-watcher.service -f
cat /var/www/ai-soc-assistant/.llm-control/last_result.json
```

### Test the watcher without the UI
```bash
AI_SOC_LLM_CONTROL_DIR=/var/www/ai-soc-assistant/.llm-control \
  python3 scripts/llm_control_watcher.py --once
```

---

## B. Asking `/chat` (browser, curl, or backend)

`/chat` requires an authenticated session (`APP_AUTH_ENABLED=true`). Routes are served
both bare and under `/api`; **through Nginx in production use `/api/...`**. Local direct
backend (`127.0.0.1:8010`) accepts either.

Credentials are `APP_AUTH_USER` / `APP_AUTH_PASSWORD` from `.env`.

### 1. Browser / UI
Just log in at `https://cisco-vai.vnudge.com` and use the chat panel — the session
cookie is set on login and sent automatically. No tokens to manage.

### 2. Authenticated curl (production, through Nginx)
Login once to capture the session cookie, then post to `/chat`:
```bash
# 1) Login -> stores the session cookie in cookies.txt
curl -s -c cookies.txt -X POST https://cisco-vai.vnudge.com/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"<APP_AUTH_USER>","password":"<APP_AUTH_PASSWORD>"}'

# 2) (optional) confirm the session
curl -s -b cookies.txt https://cisco-vai.vnudge.com/api/auth/me | jq

# 3) Ask /chat — reuse the cookie
curl -s -b cookies.txt -X POST https://cisco-vai.vnudge.com/api/chat \
  -H 'Content-Type: application/json' \
  -d '{"message":"In the last hour, which users have abnormally high failed login counts?"}' | jq
```

> Live LLM narration runs on a single-slot on-prem model — a turn can take tens of
> seconds to minutes. Add a generous client timeout: `curl --max-time 180 …`.

### 3. Local direct backend (on the VPS, bypassing Nginx)
Same flow against `http://127.0.0.1:8010` (bare or `/api` prefix both work):
```bash
curl -s -c cookies.txt -X POST http://127.0.0.1:8010/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"analyst","password":"<APP_AUTH_PASSWORD>"}'
curl -s -b cookies.txt --max-time 180 -X POST http://127.0.0.1:8010/api/chat \
  -H 'Content-Type: application/json' -d '{"message":"<your SOC question>"}' | jq
```

### 4. From backend code / a script
Reuse the maintained client in `scripts/run_live_efficacy_100.py`:
```python
from scripts.run_live_efficacy_100 import LiveClient
c = LiveClient("http://127.0.0.1:8010", 180.0)
c.login()                                   # reads APP_AUTH_USER/PASSWORD from .env
status, body, _ = c.request("POST", "/api/chat", {"message": "<your SOC question>"})
```

### Reading the response
Useful fields on the `/chat` JSON:
- `selected_skill`, `workflow_plan.skill` — routing.
- `analyst_summary`, `message`, `note` — the analyst answer body.
- `response_mode` / `synthesis_mode` — e.g. `insufficient_evidence` / `synthesis_blocked`.
- `human_review.required` — whether a HIL gate fired.
- `trace_id` — pair with `/api/debug/traces/{trace_id}` (needs `debug_access`) for the
  full per-node timeline.

Notes: production posture keeps MCP execution OFF (no live Splunk rows — answers are
governed guidance + candidate SPL); all facts stay deterministic, the model only
narrates prose.
