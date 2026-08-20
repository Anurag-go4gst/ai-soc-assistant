# LLM endpoint wiring

Single switch for COE Qwen. Everything else stays on existing `AI_SOC_LLM_*` vars.

## Qwen flag (COE only)

```env
AI_SOC_LLM_QWEN_PRIMARY_ENABLED=false   # default — this dev environment
# When COE network can reach Qwen:
# AI_SOC_LLM_QWEN_PRIMARY_ENABLED=true
# AI_SOC_LLM_QWEN_BASE_URL=http://10.52.1.13:8000/v1
# AI_SOC_LLM_QWEN_MODEL=./qwen72b
# AI_SOC_LLM_QWEN_API_KEY=not-needed
```

When the flag is **false**, Qwen is never called — even if `QWEN_*` URLs are set.

When **true**, the failover chain prepends Qwen before `LOCAL_*` and Foundation-Sec Instruct failover.

## Default chain (flag false — this environment)

| Hop | Env | Typical dev value |
|-----|-----|-------------------|
| `LOCAL_*` | Foundation-Sec on host | `http://host.docker.internal:8081/v1` |
| `FOUNDATION_SEC_INSTRUCT_*` | Failover | same host or unset |

No Qwen hop. Sidecars and narration use Instruct via `LOCAL_*` (or instruct vars if `LOCAL_*` empty).

## Fail-closed

If no endpoint is configured, sidecars skip and answers stay deterministic.

Code: `backend/app/llm/clients/endpoint_resolver.py`.

## COE Velocis-LAN deployments (current — `:8004` instruct, `:8003` reasoning)

Two OpenAI-compatible endpoints, reachable **only from the office network**. Committed
in `env/profiles/coe.env.example`; unreachable from the VPS dev host, so nothing here
is smoke-verified outside the LAN.

| Role | Served name | Base URL |
|------|-------------|----------|
| Foundation-Sec-8B Instruct | `foundation-sec-instruct` | `http://10.52.1.13:8004/v1` |
| Foundation-Sec-8B Reasoning | `foundation-sec-reasoning` | `http://10.52.1.13:8003/v1` |

```env
AI_SOC_LLM_ENABLED=true
AI_SOC_LLM_MODE=local
AI_SOC_LLM_LOCAL_BASE_URL=http://10.52.1.13:8004/v1
AI_SOC_LLM_LOCAL_API_KEY=
AI_SOC_LLM_LOCAL_MODEL=foundation-sec-instruct
# AI_SOC_LLM_FOUNDATION_SEC_INSTRUCT_* intentionally unset — see note below
AI_SOC_LLM_FOUNDATION_SEC_REASONING_BASE_URL=http://10.52.1.13:8003/v1
AI_SOC_LLM_FOUNDATION_SEC_REASONING_MODEL=foundation-sec-reasoning
AI_SOC_LLM_MAX_INPUT_TOKENS=6500
AI_SOC_LLM_TIMEOUT_SECONDS=120
```

`model` must equal the served name exactly — an OpenAI-compatible server rejects an
unknown model id. No API key is issued; leave the key vars empty rather than setting
a placeholder.

Resolved chain on this profile: reasoning roles get `:8003` → `:8004`; every other role
gets `:8004` once.

`AI_SOC_LLM_FOUNDATION_SEC_INSTRUCT_*` is deliberately left unset. Chain dedup
(`candidates_equivalent`) keys on `config_identity`, which is the **provider label** —
so `local_primary` and `foundation_sec_instruct_fallback` pointing at the same
base URL and model are *not* deduplicated. Setting both would append a second
identical hop and double failover latency to 2 × `AI_SOC_LLM_TIMEOUT_SECONDS` when
`:8004` is unreachable. Set the instruct vars only when instruct is served from a
different host than `AI_SOC_LLM_LOCAL_BASE_URL`.

**Acceptance gate is a COE-side smoke, not a repo test:**

```bash
curl http://10.52.1.13:8004/v1/chat/completions -H 'Content-Type: application/json' \
  -d '{"model":"foundation-sec-instruct","messages":[{"role":"user","content":"hi"}]}'
```

### Prior `:8002` deployment (historical)

The earlier COE endpoint was a single `:8002` reasoning server — full notes:
[`docs/coe/COE_FOUNDATION_SEC_8B_REASONING_HANDOFF.md`](../coe/COE_FOUNDATION_SEC_8B_REASONING_HANDOFF.md).
Its smoke found JSON `response_format` returning `{}` and reasoning tags leaking into
`content`. **Both caveats are unverified on `:8003`/`:8004`** — re-check them before
relying on SPL LLM failover or any JSON-mode role at COE.
