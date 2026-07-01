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

## COE Foundation-Sec 8B reasoning (`:8002`)

Verified smoke test — full notes: [`docs/coe/COE_FOUNDATION_SEC_8B_REASONING_HANDOFF.md`](../coe/COE_FOUNDATION_SEC_8B_REASONING_HANDOFF.md).

```env
AI_SOC_LLM_ENABLED=true
AI_SOC_LLM_MODE=local
AI_SOC_LLM_LOCAL_BASE_URL=http://10.52.1.13:8002/v1
AI_SOC_LLM_LOCAL_API_KEY=not-needed
AI_SOC_LLM_LOCAL_MODEL=foundation-sec-8b-reasoning
AI_SOC_LLM_FOUNDATION_SEC_REASONING_BASE_URL=http://10.52.1.13:8002/v1
AI_SOC_LLM_FOUNDATION_SEC_REASONING_MODEL=foundation-sec-8b-reasoning
AI_SOC_LLM_MAX_INPUT_TOKENS=12000
AI_SOC_LLM_TIMEOUT_SECONDS=120
```

**Caveats from smoke test:** JSON `response_format` returned `{}`; reasoning tags may appear in `content`. SPL LLM failover needs infra JSON fix before production reliance.
