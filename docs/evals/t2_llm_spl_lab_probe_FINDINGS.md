# T2 LLM SPL Producer — Lab Probe Findings (2026-06-19)

Probe: `scripts/run_t2_llm_spl_lab_probe.py` — isolates the governed LLM SPL
producer (`generate_llm_spl_fallback`) on out-of-catalogue T2 hunts and proves the
gate chain. Producer flags are enabled **inside the probe process only**; global
posture unchanged, MCP execution off, candidate SPL never executable.

## Results

| Mode | Questions | Producer fired | Governance invariants held |
|------|-----------|----------------|----------------------------|
| mock | 6 | 6/6 | 6/6 |
| live (post-restart) | 2 | 2/2 | 2/2 |

Governance invariant on **every** fired row: `validation.approved=false`,
`normalized_spl=null`, `execution_eligible=false`. Candidate SPL is review-only.

## What the gate chain did

- **Mock** (deterministic injected JSON): all 6 ran the full chain
  (strict JSON → role adapter → deterministic validation → SOC-STD-SPL-001 lint).
  A thin SPL is **blocked** by the quality lint; a SOC-STD-compliant SPL passes the
  lint and is then held non-executable by the execution validator. The lint and
  validator both work — no weak/free-form SPL leaks.
- **Live** (on-host Foundation-Sec 8B q8 at :8081):
  - `pj.002` (Modbus) returned in **~77s** but the model emitted **malformed JSON**
    (`strict_json_parse_failed: Expecting ',' delimiter`) → the strict parser
    fail-closed to `needs_clarification`. No SPL exposed.
  - `pj.001` (DNP3) exceeded the **200s** client timeout → `needs_clarification`.

## LLM health note

The on-host llama-server had degraded to **0.6 tok/s** (process up ~3 days). A
`systemctl restart llama-server.service` restored **~5.7 tok/s** (clean range).
Even healthy, generation is latency-marginal for 400-token SPL prompts
(~70–130s) and one prompt still exceeded 200s.

## Conclusion

Two independent blockers prevent live T2 SPL breadth on current hardware — both
fail closed (safe), neither leaks SPL:

1. **Latency** — single-slot 8B is marginal; some prompts exceed a usable budget.
2. **JSON strictness** — the 8B emits non-strict JSON (missing commas / fences);
   the governed strict parser rejects it (matches prior instruct-role findings).

The deterministic floor (WS-0 answer-shape router + WS-1 signal-class guidance +
WS-2/WS-7 surfacing) remains the actual T2 answer source today.

## Next steps (not in this slice)

- Pass `response_format={"type":"json_object"}` into the producer's
  `LocalChatClient.generate` call to force valid JSON on llama.cpp (the client
  already supports the hint; the producer does not pass it).
- Add a tolerant JSON repair pass before the strict parser (strip ```json fences,
  trailing-comma / missing-comma repair) — or few-shot the SPL-advisory prompt.
- Move the producer off the blocking path (async sidecar) given latency, or use a
  faster/served model before enabling T2 LLM SPL in any live posture.
- Per plan T-1: keep `AI_SOC_LLM_ENABLED=false` / `mode=mock` in `.env.example`
  until the above land; flag-on alone does not deliver breadth.
