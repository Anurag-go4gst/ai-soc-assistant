# COE Foundation-Sec 8B reasoning — smoke test handoff (2026-06-29)

Verified by Velocis smoke script against `http://10.52.1.13:8002/v1` (vLLM).

## Verified endpoint facts

| Field | Value |
|-------|--------|
| Base URL (use in `.env`) | `http://10.52.1.13:8002/v1` |
| Model ID | `foundation-sec-8b-reasoning` |
| Server | vLLM (`owned_by: vllm`) |
| Max context | **16,384** tokens (`max_model_len`) |
| Auth | None (internal network; same as Qwen) |
| Qwen 72B (unchanged) | `http://10.52.1.13:8000/v1`, model `./qwen72b` |

**Do not** put `/chat/completions` in `AI_SOC_LLM_*_BASE_URL` — the client appends that path.

## Smoke test results (summary)

| Step | Result | Notes |
|------|--------|-------|
| 1 List models | **PASS** | Single model `foundation-sec-8b-reasoning` |
| 2 Plain chat | **PARTIAL** | HTTP 200; did not return literal `OK`; `finish_reason: length` at 32 tokens; **327 prompt tokens** on a one-line user message (large baked-in system prompt on server) |
| 3 System + user | **PARTIAL** | Answer cut off; **`` leaked into `message.content`** |
| 4 JSON mode | **FAIL** | `response_format: json_object` returned `{}` only — not usable for SPL plan compiler |

Connectivity is good. **Structured JSON and clean content channel need infra follow-up** before relying on LLM SPL failover.

## COE `.env` block (copy into operator `.env`)

See also [`env/profiles/coe.env.example`](../../env/profiles/coe.env.example) and [`env/README.md`](../../env/README.md).

```env
AI_SOC_LLM_ENABLED=true
AI_SOC_LLM_MODE=local

AI_SOC_LLM_LOCAL_BASE_URL=http://10.52.1.13:8002/v1
AI_SOC_LLM_LOCAL_API_KEY=not-needed
AI_SOC_LLM_LOCAL_MODEL=foundation-sec-8b-reasoning

AI_SOC_LLM_ACTIVE_MODEL=foundation-sec-8b-reasoning
AI_SOC_LLM_AVAILABLE_MODELS=foundation-sec-8b-reasoning

AI_SOC_LLM_TIMEOUT_SECONDS=120
AI_SOC_LLM_MAX_INPUT_TOKENS=12000
AI_SOC_LLM_MAX_OUTPUT_TOKENS=1024
AI_SOC_LLM_TURN_DEADLINE_SECONDS=120

AI_SOC_LLM_FOUNDATION_SEC_REASONING_BASE_URL=http://10.52.1.13:8002/v1
AI_SOC_LLM_FOUNDATION_SEC_REASONING_API_KEY=not-needed
AI_SOC_LLM_FOUNDATION_SEC_REASONING_MODEL=foundation-sec-8b-reasoning

# Optional Qwen failover (off by default)
AI_SOC_LLM_QWEN_PRIMARY_ENABLED=false
AI_SOC_LLM_QWEN_BASE_URL=http://10.52.1.13:8000/v1
AI_SOC_LLM_QWEN_API_KEY=not-needed
AI_SOC_LLM_QWEN_MODEL=./qwen72b

AI_SOC_LLM_DEFAULT_PROVIDER=local
```

Leave `AI_SOC_LLM_FOUNDATION_SEC_INSTRUCT_*` **unset** unless a separate instruct port is provided.

After editing: `docker compose up -d` (restart backend). Confirm from AI-SOC host:

```bash
curl -sS http://10.52.1.13:8002/v1/models
```

## AI-SOC behavior with this model

| Path | Expected |
|------|----------|
| Live failover chain (`LOCAL` → optional Qwen → optional Instruct) | **Works** — uses `AI_SOC_LLM_LOCAL_*` |
| Reasoning sidecars (`mitre_reasoner`, `missing_evidence_reasoner`, …) | **Works** when `FOUNDATION_SEC_REASONING_*` set |
| Instruct sidecars (`template_match`, `route_plan`, narration roles) | **Skipped** if resolved model id contains `reasoning` (governance by design) |
| SPL LLM plan compiler (`AI_SOC_LLM_SPL_FALLBACK_ENABLED`) | **At risk** until JSON mode returns real objects |
| Deterministic answers | **Unchanged** — LLM failure always falls back |

## Follow-up requests for Velocis

1. **JSON mode** — re-run step 4; we need `{"status":"ok"}` (or equivalent non-empty JSON), not `{}`.
2. **Thinking tags** — step 3 showed `` inside `message.content`. Either route reasoning to a separate field (OpenAI `reasoning` / vLLM config) or strip before returning content.
3. **Prompt token overhead** — why does `"Reply with exactly: OK"` cost 327 prompt tokens? Document default system/chat template.
4. **Concurrency** — how many parallel requests does `:8002` support (claimed 16q / ~8000 tok/s)?
5. **Instruct endpoint** — is 1.1 8B instruct retired, or still on another port?

### JSON re-test curl

```bash
curl -sS -m 120 http://10.52.1.13:8002/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "foundation-sec-8b-reasoning",
    "messages": [{"role": "user", "content": "Return only this JSON object with no other text: {\"status\": \"ok\"}"}],
    "temperature": 0,
    "max_tokens": 128,
    "stream": false,
    "response_format": {"type": "json_object"}
  }'
```

## Raw smoke output (archive)

```
=== 1) List models ===
{"object":"list","data":[{"id":"foundation-sec-8b-reasoning",...,"max_model_len":16384,...}]}
Using MODEL=foundation-sec-8b-reasoning
=== 2) Plain chat ===
... finish_reason":"length" ... completion_tokens":32 ... prompt_tokens":327 ...
=== 3) System + user ===
... \nBrute force is an attack" ... finish_reason":"length" ...
=== 4) JSON mode ===
..."content":"{}"... finish_reason":"stop"...
=== 5) Done ===
```
