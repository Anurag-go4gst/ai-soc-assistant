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
