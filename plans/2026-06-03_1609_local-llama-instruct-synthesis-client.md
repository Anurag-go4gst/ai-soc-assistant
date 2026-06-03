# Plan — Local llama.cpp Foundation-Sec Instruct Synthesis Client

Status: Proposed (for review — plan only, no code)
Date: 2026-06-03
Author: Anurag + Claude

## Relationship to existing plans

This is a **focused delta** of `plans/2026-05-30_1845_query-to-answer-live-mcp-llm-readiness.md`
(the canonical query→answer plan). That plan covers two walls — Wall 1 (real MCP adapter)
and Wall 2 (synthesis). This plan addresses **only Wall 2**, and only for the concrete
endpoint now deployed: a local llama.cpp `llama-server` serving Foundation-Sec-1.1-8B-Instruct
(Q8_0 GGUF), OpenAI-compatible, on-VPS, no creds.

Do **not** duplicate here:
- Pre-live hardening (empty-result correctness, results→evidence injection defense, audit hooks)
  → see that plan's **Phase A**. A1/A2 are prerequisites for any live-MCP-results synthesis,
  but **not** for the knowledge-only/RAG-only first milestone below (no attacker-controlled
  Splunk fields in play yet).
- Answer guard reuse → see that plan's **Phase C3**.

What is genuinely new (the old plan predates this box and assumed a Cisco gateway):
a real HTTP client, a hard latency budget, no JSON mode, and a single model serving all roles.

## Current state (verified 2026-06-03)

- `.env`: `AI_SOC_LLM_MODE=local`, `AI_SOC_LLM_LOCAL_BASE_URL=http://host.docker.internal:8081/v1`,
  `AI_SOC_LLM_LOCAL_MODEL=foundation-sec-q8`, airgap enforced, cloud denied.
  `/api/settings/status` → local provider `base_url_configured=true`, `enabled=true`,
  `policy_allowed=true`, `deployment_mode=local`. Registry green.
- `docker-compose.yml`: backend has `extra_hosts: host.docker.internal:host-gateway`
  (resolves to `172.17.0.1`).
- **Reachability still blocked**: `llama-server` binds `127.0.0.1`; container reaches
  `172.17.0.1` → timeout. Unblock = rebind server to the bridge gateway
  (`--host 172.17.0.1 --port 8081`; reachable from container, not public). User action.
- **No live path consumes the model.** `synthesis/lab_runner.run_governed_synthesis_lab`
  produces a deterministic draft only. `AI_SOC_LLM_FINAL_SYNTHESIS_ENABLED` is inert.
- **Latent config**: `AI_SOC_LLM_*_PROVIDER` role maps still point at unconfigured
  `foundation_sec_instruct`/`foundation_sec_reasoning`. Must collapse to `local` (P2 below).

## Hard constraints from this deployment

| Constraint | Value | Consequence |
|---|---|---|
| Throughput | ~8.4 tok/s generation, ~31.8 tok/s prompt | ~33 s for a 278-tok answer |
| Context | 9000 (`-c 9000`) | input budget capped at 6500, output 400 |
| JSON mode | none (not vLLM guided_json) | prompt-contract JSON + deterministic repair/retry |
| Models | **one** Instruct GGUF for all roles | no separate reasoning model for the guard |
| Auth | none | `api_key` empty; keep 8081 off public |
| Parallel slots | `-np 1` | one in-flight request; serialize, no concurrency |

## Phases (plan only — each lands behind a default-off flag, needs sign-off)

### P0 — Observability first (no model call)
Per the LLM-app quality rule: observability is feature-zero. Before any synthesis-quality work,
capture per-turn JSONL of the would-be LLM exchange: trace id, prompt sent, raw response,
extracted JSON, adapter authority overrides, parse-repair attempts, latency, token counts.
- Reuse the existing lineage/trace surface; add an `llm_exchange` record.
- Ship this empty-but-wired even while the call is stubbed, so P3 fills it on first real call.
- Files (impl stage): `app/lineage/builder.py`, trace serializer.

### P1 — Role + provider hygiene (config, no model call)
- Collapse `AI_SOC_LLM_SYNTHESIS_PROVIDER` / `GUARD_PROVIDER` / `INTENT_PROVIDER` /
  `ROUTE_PLAN_PROVIDER` to `local` (single model), or make the synthesis stage fall back to
  `AI_SOC_LLM_DEFAULT_PROVIDER`. Decide one; document it.
- Confirm airgap-enforced continues to permit `local` (deployment_mode=local) while denying
  cloud — already true in status; assert it in a test so it can't regress.

### P2 — Local OpenAI-compatible client (the real new code)
- New `app/llm/clients/local_openai_client.py`: httpx POST `{base_url}/chat/completions`,
  non-streaming first, 120 s timeout, single-flight (respects `-np 1`), no api key.
- Maps `AI_SOC_LLM_*` limits → request body (`model`, `messages`, `max_tokens=400`,
  `temperature=0.1`, `stream=false`).
- Unhappy path is mandatory: timeout, connection refused, non-200, malformed body, empty
  `choices` → typed errors, never a silent fallback to a fabricated answer. On failure the
  pipeline returns the existing deterministic lab draft + a `synthesis_status=error` marker.
- Health probe reuse: `/settings/llm/test` should exercise this client against `/v1/models`.

### P3 — Knowledge-only / RAG synthesis (first live milestone, lowest risk)
- **Why first**: no live MCP exists, so the only attacker-controlled-field surface (live
  Splunk events) is absent. Synthesis over SOC-KB/RAG evidence and existing mock-MCP rows
  is the safest entry and needs no COE.
- Runs only when `AI_SOC_LLM_FINAL_SYNTHESIS_ENABLED=true` **and** sufficiency mode in
  `{knowledge_only_answer, full_answer, partial_answer}` over RAG/mock evidence.
- Reads `GovernedSynthesisPackage` **only** (precomputed aggregates, permitted MITRE,
  permitted actions, guard constraints) — never raw events. Wire
  `synthesis/models.build_governed_synthesis_package` into `chat()` (currently never called).
- Output via prompt-contract JSON → `app/llm/adapter/json_extractor` + `validators` →
  authority overrides (forces SPL `execution_eligible=false`, deterministic
  severity/MITRE/SOP/allowed-actions on conflict). No new adapter code — reuse Stage 3J-I.
- Evidence trimming so package fits 6500-token input budget; answer capped at 400 tokens.

### P4 — Latency / UX decision (architecture; decide before P3 ships to UI)
~33 s synchronous `/chat` is the open question. Pick one and state it:
- (a) sync + 120 s timeout + explicit UI "Foundation-Sec is composing…" expectation;
- (b) async job + poll/SSE;
- (c) token streaming (requires llama.cpp `stream=true` path — deferred, P2 is non-streaming).
Recommend (a) for the lab/Experience-Center milestone; revisit (b)/(c) if multi-user.

### P5 — Live-MCP-results synthesis (BLOCKED on Wall 1)
Feeding live Splunk result fields into the prompt requires the old plan's **Phase A2**
(results→evidence injection defense) and **Phase B** (real MCP adapter) first. Explicitly
out of scope here; tracked in `2026-05-30_1845_...`.

## Scope guardrails (per CLAUDE.md)
- One commit per concern; never combine client code, config hygiene, and UI in one commit.
- Candidate SPL stays non-executable; synthesis forces `execution_eligible=false`.
- LLM never calls MCP; backend mediates. No raw events into the prompt.
- All status output redacts secrets (`url_configured`/`api_key_configured` booleans only).
- Both synthesis/guard flags default false; `AI_SOC_LLM_MODE=disabled` forces off; airgap
  overrides cloud.

## Verification (per phase, impl stage)
- Governance regression `./scripts/run_stage3_governance_regression.sh` → PASS, harness 6/6,
  with flags **off** (proves current behavior preserved).
- P2: client unit tests with a stub server — timeout/refused/non-200/malformed → typed error,
  no fabricated answer.
- P3: flag off → deterministic lab draft unchanged; flag on (knowledge-only) → guarded answer
  citing `SourceEvidence` refs only, `execution_eligible=false`, MITRE from permitted set.
- P0: assert JSONL `llm_exchange` written with prompt+raw+parsed+overrides on a real call.

## Open decisions for review
1. P1: repoint role maps to `local` vs. fall back to default provider — which?
2. P4: latency strategy (a/b/c).
3. P3: include mock-MCP rows in first synthesis milestone, or RAG/knowledge-only strictly?
