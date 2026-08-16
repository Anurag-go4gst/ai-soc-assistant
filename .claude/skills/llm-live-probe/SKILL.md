---
name: llm-live-probe
description: Probe the local Foundation-Sec LLM (llama-server :8081) empirically before wiring or changing any LLM role/prompt — measure accuracy on a closed case set and warm/cold latency, and record results as evidence. Use when adding an LLM role, editing a role prompt, deciding shadow-vs-main-path promotion, or when the user says "test the LLM", "probe the model", or /llm-live-probe.
---

# llm-live-probe — measure before you wire

Never promote, demote, or re-prompt an LLM role on intuition. Probe the live model, record numbers, then decide. (Measured precedent: zero-shot shape classification 4/8; few-shot 8/8 at 1–2s warm — the decision flipped on data.)

**T4 semantic understanding:** read [`docs/ai/t4_semantic_prompting_playbook.md`](docs/ai/t4_semantic_prompting_playbook.md) first (repo root). Do not iterate T4 prompts against Cisco on this VPS; emit-prompts only. Prompt changes need a general failure class plus unseen validation, not a query-specific few-shot.

## Endpoint facts

- llama-server, Foundation-Sec-1.1-8B-Instruct, `http://127.0.0.1:8081/v1/chat/completions` (OpenAI-compatible). From Docker: `host.docker.internal:8081`.
- Decode ≈ 3–5 tok/s. Prefill of a NEW system prompt ≈ 10s; repeated STATIC system prompt is KV-cached → ~1–2s for short outputs.
- Shared VPS: check contention first — `vmstat 1 3` (steal column) + `uptime`. Note load in your results; idle-box numbers are best-case.
- Service: `systemctl status llama-server`. Do NOT restart it casually — UI restarts go through `llm-control-watcher`.

## Probe protocol

1. **Build a closed case set** (≥8 cases) with expected outputs BEFORE calling the model. Include negatives/confusables, not just happy path.
2. **Call with `temperature: 0`, minimal `max_tokens`** (10 for classification, ≤220 for structured JSON), 180s timeout.
3. **Run zero-shot AND few-shot variants** when testing classification — the delta is the finding.
4. **Measure per-call wall time**; separate cold (first call, prefill) from warm.
5. **Record**: accuracy n/N, warm/cold latency, failure pattern (e.g. label bias), box load. Paste into plan Evidence or memory.

Template script (adapt cases; run with plain `python3`, never inside pytest — conftest guards block live LLM in tests):

```python
import json, time, urllib.request
URL = "http://127.0.0.1:8081/v1/chat/completions"
def call(system, user, max_tokens=10):
    body = json.dumps({"messages": [{"role": "system", "content": system},
                                    {"role": "user", "content": user}],
                       "max_tokens": max_tokens, "temperature": 0}).encode()
    req = urllib.request.Request(URL, data=body, headers={"Content-Type": "application/json"})
    t0 = time.monotonic()
    with urllib.request.urlopen(req, timeout=180) as resp:
        payload = json.load(resp)
    return payload["choices"][0]["message"]["content"].strip(), time.monotonic() - t0
```

## Prompt rules validated on this model

- Few-shot mandatory for classification: one-line label definitions + ≥6 worked examples covering confusable pairs.
- Static system prompt (zero per-turn content) to keep the KV cache warm.
- Hard output constraint: "Reply ONLY the <X> word" or strict JSON schema WITH a worked example.
- Expect ```json fences on JSON outputs — parse with fence-tolerant extraction (`extract_first_json_object` in app code).

## Decision rubric (from the measured intensity policy, plan 2026-07-04_1736)

- Short-output role (≤10 tok) + static prompt + ≥7/8 accuracy → eligible for main-path advisory.
- Long-output role → budget-capped advisory on this VPS regardless of quality; lift caps only on COE-class serving.
- <7/8 accuracy → fix the prompt (few-shot, definitions) and re-probe; do not ship and hope.
- Deterministic authority is never transferred: LLM output stays advisory/guarded-promotion no matter the score.
