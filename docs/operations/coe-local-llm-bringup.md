# COE local-LLM bring-up (Kimi-style OpenAI-compatible model)

How to point the AI-SOC backend at a model COE deploys locally — vLLM, sglang,
llama.cpp, or TGI. The backend only needs an **OpenAI-compatible
`/v1/chat/completions` endpoint**. It never touches the model host, GPUs, or
weights; the LLM never calls MCP. All SOC facts stay deterministic — the model
only narrates / answers in the Ask LLM page.

## 1. The only settings that change

Copy [`.env.coe-llm.example`](../../.env.coe-llm.example) into `.env`. The five
that matter:

| Key | Value | Notes |
|-----|-------|-------|
| `AI_SOC_LLM_ENABLED` | `true` | Master on switch. |
| `AI_SOC_LLM_MODE` | `local` | Use `local`, not `openai_compatible` — the health probe + Ask LLM debug cards read the `LOCAL_*` keys. |
| `AI_SOC_LLM_LOCAL_BASE_URL` | `http://HOST:PORT/v1` | **Must end in `/v1`.** Must be reachable *from inside the backend container* (see §3). |
| `AI_SOC_LLM_LOCAL_MODEL` | served model id | Exactly as `GET /v1/models` returns it. |
| `AI_SOC_LLM_LOCAL_API_KEY` | blank or token | Blank if the server has no auth. |

Then `docker compose up -d` (or restart the backend). Open **Ask LLM** — the
health cards (reachable / throughput / status / model) tell you immediately if
it connected.

## 2. What COE must give you (ask for these specifically)

1. **Base URL + port** of the model server, reachable from the AI-SOC host.
2. **Served model id** — the string in `GET /v1/models` (vLLM uses the full
   repo path, e.g. `moonshotai/Kimi-K2-Instruct`). The model name in `.env`
   must match this byte-for-byte or every call 404s.
3. **Auth** — none, or a bearer token.
4. Confirm it is **OpenAI-compatible** (`/v1/chat/completions`, streaming SSE).
   vLLM/sglang/llama.cpp/TGI all are. If COE serves a non-OpenAI API, it needs a
   shim — flag this early.
5. Confirm **`GET /health` returns 200** at the server root (used by the live
   throughput probe). vLLM/sglang/llama.cpp expose it by default.

## 3. Docker networking (the #1 cause of connection errors)

The backend runs in Docker. `127.0.0.1` inside the container is the *container*,
not the host or the model box. Pick the URL accordingly:

| Where the model runs | `AI_SOC_LLM_LOCAL_BASE_URL` |
|----------------------|------------------------------|
| Another server / VM on the LAN | `http://<lan-ip>:<port>/v1` |
| Same host, outside Docker | `http://host.docker.internal:<port>/v1` (the backend service already declares `extra_hosts: host.docker.internal:host-gateway`) |
| A sibling Docker container | `http://<service-name>:<port>/v1` on a shared compose network |

Open the model port on the firewall to the AI-SOC host only — do **not** expose
it publicly.

## 4. Debugging a connection error

Work top-down; each step isolates the layer.

1. **Ask LLM page** — read the `Status` card:
   - `llm_disabled` → `AI_SOC_LLM_ENABLED`/`AI_SOC_LLM_MODE` not set; backend not
     restarted after the `.env` edit.
   - `unreachable` → URL wrong, port closed, or `/health` not 200. Almost always
     Docker networking (§3) or firewall.
   - `probe_timeout` → reached it, but no token in time. Model loading, cold
     cache, or undersized hardware. Raise `AI_SOC_LLM_TIMEOUT_SECONDS`.
   - `no_tokens` → endpoint replied but empty — wrong model id, or not actually
     OpenAI-compatible.
   - `measured` → connected; `tok_per_s` is real throughput.

2. **From the backend container**, prove reachability and the contract. The
   container ships `python3` (no `curl`) — use the same stack the app uses:
   ```bash
   docker compose exec backend python3 - <<'PY'
   import json, urllib.request
   HOST = "http://COE-LLM-HOST:PORT"   # no /v1
   print("health:", urllib.request.urlopen(HOST + "/health", timeout=5).status)
   print("models:", urllib.request.urlopen(HOST + "/v1/models", timeout=5).read().decode()[:400])
   PY
   ```
   - `/health` fails → network/firewall (§3).
   - `/v1/models` returns ids → copy the exact id into `AI_SOC_LLM_LOCAL_MODEL`.

3. **One real completion** from the container:
   ```bash
   docker compose exec backend python3 - <<'PY'
   import json, urllib.request
   url = "http://COE-LLM-HOST:PORT/v1/chat/completions"
   body = json.dumps({"model": "SERVED_ID",
                      "messages": [{"role": "user", "content": "ping"}],
                      "max_tokens": 8}).encode()
   req = urllib.request.Request(url, data=body,
                                headers={"Content-Type": "application/json"})
   print(urllib.request.urlopen(req, timeout=30).read().decode()[:600])
   PY
   ```
   A JSON body with `choices[0].message.content` → the app will work. HTTP 401 →
   set `AI_SOC_LLM_LOCAL_API_KEY`. HTTP 404 → wrong model id or missing `/v1`.

4. **Backend trace** — the live path is best-effort and never crashes chat;
   inspect with `AI_SOC_DEBUG_API_ENABLED=true` + `/debug/readiness`
   (LLM/MCP/RAG/sink) and per-LLM latency/outcome in the trace timeline. See
   [`debugging.md`](../observability/debugging.md).

## 5. Common mistakes (tell COE)

- **Forgetting `/v1`.** The client appends `/chat/completions`; without `/v1`
  the URL is wrong. Base URL must end `/v1`.
- **Model-id mismatch.** Must equal `GET /v1/models` exactly.
- **Using `127.0.0.1` in the URL.** That's the container, not the model box.
- **Restart.** `.env` changes need a backend restart to load.
- **Hardware reality.** A large model on modest hardware is correct-but-slow;
  that is `probe_timeout` / low `tok_per_s`, not a bug. Raise the timeout.

## 6. What stays the same regardless of model

- MCP execution flags stay `false`; the model never calls MCP or sees raw
  events.
- SOC facts (severity, MITRE, actions, SPL, `execution_eligible=false`) remain
  deterministic authority; any LLM failure falls back to the deterministic
  answer.
- The Experience Center fixture path never calls a live model.
