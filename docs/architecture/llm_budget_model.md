# LLM per-turn budget model

Budgets are **operator config** (env profiles), not architecture. Production targets ~6000 tok/s; the VPS dev profile (~6 tok/s) uses longer deadlines and the same hop ordering — never fewer governance gates.

**Restart required:** profile edits load at backend startup only (`docker compose restart backend`).

## Wall-clock layers

| Layer | Setting | Dev (VPS ~6 tok/s) | Production (~6000 tok/s) |
|-------|---------|--------------------|---------------------------|
| Turn deadline | `AI_SOC_LLM_TURN_DEADLINE_SECONDS` | 210s | 90s |
| Per-hop socket cap | `AI_SOC_LLM_TIMEOUT_SECONDS` | 120s | 25s |
| Max generation tokens | `AI_SOC_LLM_MAX_OUTPUT_TOKENS` | 512 | 1024 |
| Intent advisor reserve | `AI_SOC_LLM_INTENT_ADVISOR_RESERVE_SECONDS` | 25s | 5s |
| Guided narration calls | `AI_SOC_GUIDED_LLM_MAX_CALLS` | 3 | 5 |
| Guided turn deadline | `AI_SOC_GUIDED_LLM_TIMEOUT_SECONDS` | 210s | 90s |

Complexity bonus (out-of-registry / investigation-shaped) adds up to +50s on top of the turn deadline base, capped by `_MAX_TURN_DEADLINE` (300s) in `hybrid_role_graph.py`.

## Per-hop roles (live `/chat`)

| Hop | Role / entry | Hard cap | Reserve rule | Skipped when |
|-----|----------------|----------|--------------|--------------|
| Intent advisor | `intent_advisor` sidecar | 2s on frozen T0 rows; else `hop_reserve_seconds` | `AI_SOC_LLM_INTENT_ADVISOR_RESERVE_SECONDS` must remain before start | Guided route locked; budget exhausted |
| Resource planner | ~~`llm_plan_bridge`~~ **retired 2026-08-11** | — | — | Always: canonical planning is deterministic; there is no planning-model hop |
| SPL plan compiler | `spl_detection_plan` sidecar | `AI_SOC_LLM_TIMEOUT_SECONDS` capped to remaining turn | Sidecar slot + `max_sidecar_calls` (default 2) | SPL not on path; relevance gate |
| MITRE rationale / misc sidecars | various | Same sidecar cap | `TurnLlmBudget.sidecar_hop_blocked` | Role skip policy |
| Final synthesis | `governed_composer` narration | `composer_reserve_seconds()` = min(timeout, remaining) | Must fit inside remaining turn after reserves | `AI_SOC_LLM_FINAL_SYNTHESIS_ENABLED` off |
| Guided investigation | `build_guided_turn_budget()` | `AI_SOC_GUIDED_LLM_TIMEOUT_SECONDS` | `max_narration_calls` from `AI_SOC_GUIDED_LLM_MAX_CALLS` | `AI_SOC_GUIDED_LLM_ENABLED` off |

> **`AI_SOC_GUIDED_LLM_ENABLED` scope (2026-08-11, Plan 2 B1 = `RETIRE`).** This flag is now a
> **budget/deadline control only** — it sizes the guided turn budget and narration caps. It does
> **not** gate any planning-model call, because the imperative guided-hybrid LLM proposer was
> retired; guided planning is deterministic on every posture of this flag. Any older text
> implying it "enables guided LLM planning" is wrong. For the same reason the dispatch-step
> label `guided_investigation_plan_llm` no longer denotes a model hop and is not emitted.
>
> **Update (2026-08-11, Plan 3 B0).** Guided investigation is no longer one-round, and it
> regained multi-round behavior **without** any model hop. The round gate now runs on
> evidence actually collected — produced-evidence keys before/after collection, plus a plan
> fingerprint — so `MAX_GUIDED_INVESTIGATION_ROUNDS` (3) is enforced rather than merely
> unreachable. Refinement costs no LLM budget; every round's reason is traced in
> `plan_dispatch_trace.guided_refinement_reasons`.

## Skip order under pressure (deterministic)

When `TurnLlmBudget.remaining_seconds()` is tight, hops are skipped in this order (first match wins; deterministic path always retained):

1. **Planner bridge** — `provenance.llm_bridge="skipped:budget"` (needs bridge 20s + synthesis reserve).
2. **Optional sidecars** (MITRE rationale, shadow narration) — role skip policy / `sidecar_budget_exhausted`.
3. **Final synthesis** — falls back to deterministic draft prose (`narration_hop_blocked`).
4. **Intent advisor** — only on non-guided paths when reserve insufficient (guided path may skip advisor earlier by policy).

Never skipped: deterministic routing, SPL validation, MCP execution gates, human-review triggers.

## Dev sizing rationale (~6 tok/s)

At ~6 tok/s, 512 output tokens ≈ 85s wall time per hop. A turn with planner (20s) + SPL producer (~85s) + synthesis (~85s) needs ~190s plus intent reserve — hence `AI_SOC_LLM_TURN_DEADLINE_SECONDS=210` and `AI_SOC_GUIDED_LLM_MAX_CALLS=3`.

Record `vmstat 1 5` steal% alongside latency probes; high steal inflates wall time without changing these config targets.

## Production sizing rationale (~6000 tok/s)

Sub-second hops allow a 90s turn deadline with generous call counts (`AI_SOC_GUIDED_LLM_MAX_CALLS=5`). Per-hop timeout stays short so a wedged provider fails fast; tokens may be higher because throughput is not the bottleneck.

## Profiles

- **Development / COE lab:** `env/profiles/development.env.example`, `env/profiles/coe.env.example`
- **Production scaffold:** `env/profiles/production.env.example` (LLM block only — fill secrets elsewhere)
