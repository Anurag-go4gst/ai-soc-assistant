# Plan 7 D0 — target-architecture regression corpus

Artifact: `d0_target_corpus.json` (30 rows). Harness:
`scripts/eval_plan7_d0_target_corpus.py`. Live integration sample:
`docs/evals/plan6/runs/20260815T130643Z` (T2) and `…/20260815T130733Z` (T4).

## Effective flags (read back from the running container at run start)

```
AI_SOC_RESOURCE_PLAN_EXECUTION_ENABLED     = true
AI_SOC_PIPELINE_DISPATCH_V2_ENABLED        = false
AI_SOC_T4_SEMANTIC_UNDERSTANDING_ENABLED   = true
AI_SOC_T4_SEMANTIC_UNDERSTANDING_TIMEOUT_SECONDS = 120.0
AI_SOC_LIVE_CAPABILITY_ENFORCEMENT_ENABLED = false
t4_mode                                    = recorded_proposal
```

## How D0 was executed, and why it does not weaken the gate

D0 requires the corpus **end-to-end under the target ResourcePlan authority**, and A6 forbids
satisfying it with planning-level classification alone.

The corpus runs **inside the backend container**, through
`run_chat_via_resource_planner_graph` — the same entrypoint `/chat` uses — with the real DB, real
canonical planning, real ResourcePlan commit, real dispatch seam and real PhaseContract merge.
Only the external model call is replaced by a recorded proposal.

**This was verified, not assumed, and it caught a trap.** Run *outside* the container, the same
entrypoint routes correctly but never reaches `execute_plan_dispatch`: the canonical handoff
cannot resolve Postgres, so no composed plan is committed and `has_composed_plan` is false. An
out-of-container sweep would have reported a clean run while exercising **none** of the
architecture under test — and is the reason the earlier A1 sweep saw zero seam calls. In-container
the same query yields `dispatch=1`, `merge_active=true`, merge reason `null`.

Substituting the model call is legitimate here **only** because D0 tests orchestration
correctness. C3 owns semantic quality; D1 owns serving reliability. **Nothing in the 30-row
corpus is evidence of live serving viability, latency or recovery**, and the runner records
`t4_mode: recorded_proposal` in its own output so the distinction cannot be lost downstream.

## Coverage

30 rows, **0 errors**: the ten required request classes plus the 20-row Plan 6 VPS corpus
(12 corpus rows + 8 residual paraphrases).

| class | row | route | dispatch source | merge |
|---|---|---|---|---|
| explain supplied SPL | `d0.explain_spl` | `spl_generation` | `resource_plan_step_walk` | ✅ |
| generate SPL, no execution | `d0.generate_spl` | `spl_generation` | `resource_plan_step_walk` | ✅ |
| supplied-alert review | `d0.alert_review` | `attack_discovery` | `resource_plan_step_walk` | ✅ |
| knowledge-only | `d0.knowledge` | `knowledge_recall` | — | — |
| SPL + MCP investigation | `d0.spl_mcp` | `attack_discovery` | `resource_plan_step_walk` | ✅ |
| T4-heavy semantic | `d0.t4_semantic` | `knowledge_recall` | `canonical_non_planned` | — |
| ambiguity / clarification | `d0.clarify` | `knowledge_recall` | `canonical_non_planned` | — |
| follow-up / context | `d0.followup` | `knowledge_recall` | `canonical_non_planned` | — |
| cross-capability | `d0.cross_capability` | `knowledge_recall` | — | — |
| negative / safety | `d0.unsafe` | `knowledge_recall` | `canonical_non_planned` | — |

Dispatch distribution: `resource_plan_step_walk` **11**, `canonical_non_planned` **14**, no plan
**5**. **Zero** `legacy_predicate`, **zero** `session_spl_refine`, **zero** guided-hybrid.

## Invariants — all hold

| Invariant | Result |
|---|---|
| `execution_eligible` non-null | **none of 30** |
| `execution_enabled` true | **none of 30** |
| MCP executed | **none** — only `skipped` / `requires_human_review` |
| approved SPL without `normalized_spl` | **none** |
| SPL rows reaching the seam missing `spl_postprocessor` | **none** — the A3 lifecycle invariant holds on every one |
| T4 invoked on a T1–T3 row | **none** — all 18 invocations are T4-tier |
| dispatch-v2 | OFF throughout |
| ResourcePlan authority | ON throughout |

## Delta classification vs the Plan 6 Arm A baseline

**Route deltas: 0** across all 12 corpus rows and all 8 paraphrases.

| Bucket | Count | Detail |
|---|---|---|
| **EXPECTED_ARCHITECTURE_CHANGE** | 11 | Rows now dispatch via `resource_plan_step_walk` with the merge active, and every SPL row carries a contract-inserted `spl_postprocessor`. Arm A ran exec OFF / v2 ON, so this *is* the target authority and the A3 fix appearing. |
| **KNOWN_PLAN8_DEPENDENCY** | 12 | T4 rows resolved to `intent_family=clarification_required` with `required_capabilities=[]` — including all 8 paraphrases and the lateral-movement semantic case. The recorded T4 proposal was accepted on each, yet the family is locked, so no SPL-capable downstream work can follow. Not patched: no keywords, no T4 route mutation. |
| **REGRESSION** | **0** | No route change, no invariant violation, no lost lifecycle phase. |
| **ENVIRONMENT/SERVING** | n/a | `wall_ms` spans 585 ms – 74 s (p50 **988 ms**, p95 **64.7 s**). The spread is RAG/embedding work and host load, not orchestration, and is **not** offered as evidence about serving. |
| **UNEXPLAINED** | **0** | — |

No baseline was refreshed and no test was weakened.

## Live integration sample (2 rows, deliberately small)

Per the live-T4 policy, the corpus was not sent live. Two HTTP turns verify the real chain
`T1–T3 → semantic_t4 → structured response → deterministic validation → merge/fallback →
downstream`:

| row | tier | result |
|---|---|---|
| `p6.spl.draft` | T2 | `attack_discovery`, `degrade=merge`, phases `workflow_spl, spl_postprocessor, spl_source_resolve, execution`, fingerprint `99ccd9213e2f0b37` **identical to Arm A**, 29.8 s |
| `p6.para.003` | T4 | T4 **accepted in 19.9 s**; proposed 6 fields, kept `normalized_goal` + `evidence_requirements`; `clarification_without_unresolved_referent` refused; 78.7 s total |

The live T4 bundle carries populated `proposed_fields` / `accepted_fields`, which closes the C3
instrumentation gap **end-to-end over HTTP**, not merely in unit tests.

## What D0 does and does not establish

Establishes: the target architecture — ResourcePlan + PhaseContract + deterministic compiler with
dispatch-v2 OFF — carries the full corpus with no regressions, no lost mandatory lifecycle work,
and every governance invariant intact.

Does **not** establish: serving reliability, latency under load, concurrency, model-unavailable or
malformed-model behaviour, or recovery. Those are **D1**, and the recorded-proposal substitution
means this run contributes no evidence toward them.
