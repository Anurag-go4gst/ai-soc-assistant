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

## Update — json_object + tolerant parser slice (2026-06-19)

Shipped: producer now passes `response_format={"type":"json_object"}` and
`_strict_json_payload` gained a tolerant net (`_extract_first_json_object` +
trailing-comma repair; truncated output still fails closed).

Re-probe (post-restart, both within budget at ~100s/110s) **still failed**
`strict_json_parse_failed: Expecting ',' delimiter`. A direct diagnostic isolated
why:

- `finish_reason=stop`, `predicted_n=58` → **not truncation**.
- The on-host llama-server **ignores `response_format=json_object`** — it returned
  ` ```json ` fences. With a small (2-key) schema the fenced content was valid
  JSON; with the producer's large 15-key schema the 8B drops a delimiter.

So on this hardware: json_object is a no-op (server build), the parser handles
fences/prose/trailing-commas (proven by unit test) but cannot invent a missing
comma. Live SPL breadth is still not delivered — root cause is the 8B's JSON
reliability on a large schema, not latency or truncation.

## Update 2 — parsing SOLVED via constrained generation (2026-06-20)

A 4-mode diagnostic (`scripts/diag_llm_json_modes.py`) settled the root cause:

| mode | valid JSON | notes |
|------|-----------|-------|
| plain | no | ```json fences; truncated at 512 (finish_reason=length) |
| `json_object` | no | server **ignores** it — fences + dropped delimiter |
| **`json_schema`** | **yes** | clean object, no fences |
| **`grammar` (GBNF)** | **yes** | clean object, no fences |

So this llama-server honors `json_schema`/`grammar` but not `json_object`. And the
real truncation limit was **`min(ai_soc_llm_max_output_tokens, …)` = 400** (the
running setting), which cut the ~490–580-token SPL JSON mid-string.

Fixes shipped:
- Producer `response_format` → `json_schema` (with the SPL schema); falls back to a
  plain call + tolerant parser on HTTP 400 (server without json_schema).
- SPL output budget decoupled from the synthesis budget with a floor:
  `_spl_max_output_tokens() = max(640, min(setting, 768))` — narration tuning can no
  longer truncate SPL.
- Prompt: dropped the now-redundant "no markdown fences" prose (json_schema enforces
  format); **all SOC-STD-SPL-001 C–I policy rules kept** — no policy degrade.
- Tolerant parser kept as the secondary net.

Live re-probe result: **2/2 fired, no JSON parse errors, `quality_status=passed`**
(parsed → adapted → validated → SOC-STD lint passed). Governance invariants held
(approved=false, normalized_spl=null, execution_eligible=false). The response is now
reliably parsed.

Remaining (separate layer, not parsing): rows came back `status=blocked` rather than
`lab_tier` — the execution validator rejected the model's SPL for a non-placeholder
reason (so it is not subset-eligible for lab exposure). This is validator/SPL-content
tuning, not a parsing problem; `reject_reasons` is now captured in the probe summary
to drive that next slice.

## Update 3 — plan-plus-compiler PASSES live (2026-06-20)

The earlier "blocked" rows were not an 8B capability wall: pj.001 actually had
stats + head and failed only on `strftime(_time)` ordering (SOC-STD-U02); the large
15-field schema overloaded the model. Per the verdict, we split the work:

- **LLM → small detection plan** (data_domain, filters, group_by, metric) via a
  compact json_schema — easy for an 8B.
- **Deterministic compiler** (`app/spl/llm_plan_compiler.py`) assembles
  SOC-STD-compliant SPL: placeholders, time bound, coalesce-normalized stats,
  `strftime` AFTER stats, sort, `head 100`, allowlisted commands only, injection-
  sanitized values.
- Compiled SPL flows through the **existing** governed producer (validation,
  SOC-STD quality lint, adapter, lab-tier gating) unchanged — SOC-STD not weakened.
- A fixed **seed** (client now forwards `seed`) makes generation repeatable.

**Live `--plan` probe result (on-host 8B):** pj.001 + pj.002 →
`status=candidate_generated`, `lab_tier=True`, `quality=passed`,
`repeatable=True` (byte-stable across two seeded runs), rejects reduced to
placeholder-only (`disallowed_index`/`disallowed_sourcetype`). Governance
invariants held (approved=false, normalized_spl=null, execution disabled). The
analyst now receives a usable, validated, review-only lab SPL.

This is the path forward for live T2 SPL breadth. Free-form SPL generation on the
8B stays unreliable; the plan-plus-compiler is the reliable producer.

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
