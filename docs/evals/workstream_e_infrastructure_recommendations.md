# Workstream E — production LLM infrastructure recommendations

**Date:** 2026-07-29  
**Status:** advisory only — **not applied** in this change set  
**Context:** E5-run-4 exploratory measurement on VPS single-slot `llama-server`; production master @ `204d76b`.

## Purpose

Document how to improve end-to-end `/chat` latency **without** reducing prompts, context limits, model quality, or governance stages. Application-quality reductions are explicitly out of scope.

## Expected performance on higher-throughput production LLM

| Segment | VPS profile (E5-run-4) | Production expectation |
|---------|------------------------|----------------------|
| Sidecar hops (routing, MITRE, sufficiency) | 30–120s each; serial slot contention | 2–15s per hop with concurrent capacity |
| `synthesis_lab` narration | 60–120s+ | 5–20s at target token rates |
| `composer` (guided / weak-case) | 120–180s wall with wrapper timeout | 10–30s |
| Turn P95 (6-segment mix) | Dominated by LLM queue + single slot | Dominated by planning/RAG unless synthesis enabled |

Class **B** calls (see [`workstream_e_llm_call_inventory.md`](workstream_e_llm_call_inventory.md)) become fast automatically when throughput and concurrency match production targets — no prompt truncation required.

## Model warm-up and prompt / KV cache

- Keep **one dedicated inference service** per production role family (instruct for sidecars + synthesis) to avoid cold process start per request.
- Enable server-side **prompt/KV cache** (llama.cpp `--cache-type-k`, vLLM prefix caching, or equivalent) for repeated system prompts across sidecar roles.
- Run **warm-up completions** after deploy (fixed system prompt, short user message) before accepting benchmark traffic.
- Separate **benchmark session** from cold-process measurement: record `server_run_kind` when the inference layer exposes cache state.

## llama-server concurrency and hardware constraints

Current VPS posture:

- `AI_SOC_LLM_MODEL_SLOTS=1` — intentional single-flight guard matching one physical slot.
- Sidecar + synthesis executors are bounded; orphaned `urlopen` workers hold the slot until socket timeout.

Production recommendations:

- **Minimum 2 concurrent slots** for sidecar + synthesis overlap, or **separate endpoints** for sidecar vs synthesis.
- Size GPU/CPU for **sustained tokens/sec** at `AI_SOC_LLM_MAX_OUTPUT_TOKENS` without hitting socket timeouts.
- Set `AI_SOC_LLM_TIMEOUT_SECONDS` from measured P99 completion time + margin, not from Nginx ceiling alone.

## Quantization and model options (quality trade-offs explicit)

| Option | Latency | Quality risk |
|--------|---------|--------------|
| Same instruct model, better hardware | Lower | None if capacity sufficient |
| Q4_K_M vs Q8 | Faster | Possible reasoning / JSON adherence regression — requires `/llm-live-probe` |
| Smaller model for **shadow-only** roles | Lower | Must stay non-authoritative; parity tests required |
| Smaller model for synthesis/composer | Lower | **Rejected** for production without COE sign-off — changes analyst-visible prose |

Do not downgrade the governed composer or synthesis model without closed-case eval + parity gates.

## Production endpoint failover diversity

- Configure **distinct** `local_primary` and `foundation_sec_instruct_fallback` endpoints when true redundancy is required.
- When both resolve to the same URL+model, application dedupes the chain (URL+model); operators should treat that as **single point of failure**, not failover.
- Optional Qwen primary (`AI_SOC_LLM_QWEN_PRIMARY_ENABLED`) provides real diversity when URL/model differ.

## Capacity and concurrency requirements

Starting targets (to validate with production methodology below):

| Role family | Suggested concurrency | Notes |
|-------------|----------------------|-------|
| Sidecars (intent, MITRE, ME) | 2–4 parallel | Short JSON outputs |
| Synthesis + composer | 1–2 dedicated | Longer outputs; do not share single slot with sidecars |
| SPL LLM producer (flag-gated) | 1 | Lab-tier only |

Align `AI_SOC_SIDECAR_MAX_WORKERS` and `AI_SOC_LLM_MODEL_SLOTS` with physical capacity — raising workers without slots increases orphan timeouts.

## Recommended production performance baseline methodology

1. Deploy production LLM tier with concurrency ≥2 and warm-up complete.
2. Re-run **authorized** harness (`E-P1…E-P6`) only after COE approves next measurement phase — not required for this reconciliation PR.
3. Require **N≥30** samples per segment before SLO proposal (E5-run-4 N=6 is exploratory only).
4. Compare `attribution_v2.endpoint_attempts` to `llm_failover` logs 1:1 after schema v2 deploy.
5. Record cold vs warm **server** run_kind separately from matrix labels.
6. Gate SLO proposal on: parity 120/0/0, sentinel, clean-answer — unchanged from governance regression.

## What not to do

- Do not lower sidecar or synthesis timeouts to fit VPS measurements.
- Do not disable MITRE, sufficiency, composer, or shadow telemetry to improve scores.
- Do not infer production SLO from six VPS exploratory samples.
