# Workstream E — LLM call inventory (static trace)

**Date:** 2026-07-29  
**Plan:** [`plans/2026-07-28_1630_live-synthesis-performance-baseline-and-slo.md`](../../plans/2026-07-28_1630_live-synthesis-performance-baseline-and-slo.md)  
**Scope:** Static trace from `/api/chat` → `PlaceholderResponse` for benchmark cases **E-P1**, **E-P3**, **E-P5**, **E-P6** (production RP graph path with live synthesis flags on).

**Excluded from this document:** prompt text, credentials, endpoint URLs, raw answers.

## Global gates (all cases)

| Gate | Effect on LLM |
|------|-----------------|
| `AI_SOC_LLM_MODE=disabled` or `ai_soc_llm_enabled=false` | All calls skipped |
| `hybrid_role_graph` boundary (`unsafe_execution`, etc.) | All roles disabled |
| `TurnLlmBudget.sidecar_hop_blocked` / `insufficient_deadline_reserve` | Per-role skip |
| `should_skip_sidecar` (T0 frozen rows, draft preview, etc.) | Intent / ME / MITRE skip |
| EC / demo path | **No live LLM** (out of scope) |

## Failover chain (when configured)

Built by `build_failover_chat_client` (`endpoint_resolver.py`):

1. Optional `foundation_sec_reasoning` (reasoning roles only)
2. Optional `qwen_primary` (flag-gated)
3. `local_primary` (`AI_SOC_LLM_LOCAL_*` or OpenAI-compatible)
4. `foundation_sec_instruct_fallback` (deduped only when full **candidate-contract fingerprint** matches an earlier hop — endpoint identity hash, model, adapter, auth-source label, transport mode, config identity; unknown components retain both candidates)

Per-hop socket timeout: sidecar ≤120s; synthesis honors `AI_SOC_LLM_TIMEOUT_SECONDS`.  
Sidecar wrapper: `run_sidecar_llm_with_timeout` (role-specific, 10–120s).  
Synthesis lab: monotonic deadline via `narration_deadline` + `FailoverChatClient.generate(deadline=…)`.

---

## E-P1 — `knowledge_recall` (cold, knowledge pair / first)

**Query shape:** SOP / playbook guidance, no SPL execution.

| # | Purpose | Caller / path | Changes answer? | Class | Endpoint candidate | Model | Timeout source | Failover | Consumed | attribution_v2 | Duplicate risk |
|---|---------|---------------|-----------------|-------|-------------------|-------|----------------|----------|----------|------------------|----------------|
| 1 | routing | `graph_node_query_to_intent` → `generate_llm_intent_advisory` → `invoke_sidecar_role` | Advisory only | conditional / advisory | role `intent_shadow_classifier` chain | governance-resolved | `sidecar_timeout_seconds` (120s) + wrapper | FailoverChatClient + optional instruct-only wrapper retry | Normalized into `llm_intent_advisory`; deterministic route wins | Yes (`call_purpose=routing`) | B |
| 2 | shadow | `graph_node_query_to_intent` → `generate_shape_advisory` | Advisory only | conditional / advisory | `shape_advisor` | governance-resolved | 10s wrapper | Same chain | Shape promotion trace only | Yes (`shadow`) | B |
| 3 | shadow | `_route_plan_shadow_stage` → `generate_llm_route_plan_candidate` | Shadow only | shadow-only | `route_plan_candidate_generator` | governance-resolved | 120s wrapper | Same chain | `route_plan_shadow` trace; deterministic plan authority | Yes (`shadow`) | B |
| 4 | sufficiency | finalize → `run_missing_evidence_reasoner` | Limitations text only if bullets pass guard | conditional | `missing_evidence_reasoner` | governance-resolved | budget-capped ≤120s | Same chain + wrapper retry | Merged into `answer_contract.limitations` | Yes (`sufficiency`) | A |
| 5 | mitre | finalize → `run_mitre_risk_rationale` | Rationale prose only | conditional | `mitre_reasoner`, `risk_rationale_reasoner` | governance-resolved | 120s per internal call | Same chain | `severity_rationale` / `foundation_sec_analysis` if guard passes | Yes (`mitre`) | A |
| 6 | synthesis_lab | `run_governed_synthesis_lab` → `narrate_analyst_summary` | **Analyst summary prose** (facts deterministic) | mandatory when live synthesis + sufficiency ready | synthesis chain (`build_synthesis_client_from_settings`) | configured instruct/local | `live_synthesis_timeout_seconds` + hop cap | FailoverChatClient monotonic deadline | `analyst_summary` when success | Yes (`synthesis_lab`) | B |
| 7 | composer | `compose_governed_answer` | **Skipped** for strong knowledge profile | — | — | — | — | — | Deterministic RAG summary kept | — | — |

**E-P1 typical VPS latency:** Multiple conditional sidecars + one synthesis_lab hop dominate; infrastructure-sensitive (class **B**).

---

## E-P3 — `alert_summary` (cold, alert pair / first)

| # | Purpose | Caller / path | Changes answer? | Class | Notes |
|---|---------|---------------|-----------------|-------|-------|
| 1–3 | routing / shadow | Same as E-P1 | Advisory / shadow | C–D | Intent may be budget-capped on frozen rows |
| 4 | sufficiency | `run_missing_evidence_reasoner` | Limitations | A | Enabled when contract has `missing_evidence` |
| 5 | mitre | `run_mitre_risk_rationale` | MITRE/severity prose | A | Enabled when MITRE + severity context present |
| 6 | shadow | `_attach_evidence_observer` (if MCP rows) | Observer trace only | shadow-only | `evidence_observer` role; 120s |
| 7 | synthesis_lab | `run_governed_synthesis_lab` | Summary prose | B | Primary user-visible LLM when lab path wins |
| 8 | composer | `compose_governed_answer` | Usually **skipped** (not weak-case / not guided) | — | Weak-case OT paths excepted |

**Composer gap (E5-run-4):** E-P3 spent ~180s in `final_synthesis` with **zero** `endpoint_attempts` because `compose_governed_answer` used `run_sidecar_llm_with_timeout` around `FailoverChatClient.generate` without recording wrapper-bound timeouts; orphan socket work continued after wrapper expiry. **Fixed (schema v3):** `wrapper_events[]` records composer/sidecar wrapper timeout without synthetic `endpoint_attempts`; session frozen on `finalize_turn_timing`.

---

## E-P5 — `guided_investigation` (cold-intent, standalone)

| # | Purpose | Caller | Changes answer? | Class |
|---|---------|--------|-----------------|-------|
| 1–5 | routing / shadow / sufficiency / mitre | Same family as E-P1 | Advisory / limitations / rationale | B |
| 6 | synthesis_lab | `run_governed_synthesis_lab` | Often **skipped** or degraded — guided uses composer path | C |
| 7 | composer | `compose_governed_answer` | **Direct answer prose** when weak-case / guided | B | `governed_composer` 120s wrapper + failover chain |

**E-P5 dominant cost:** `composer` (not `synthesis_lab`).

---

## E-P6 — `spl_generation` (cold-intent, standalone, generation_only)

| # | Purpose | Caller | Changes answer? | Class |
|---|---------|--------|-----------------|-------|
| 1–3 | routing / shadow | Intent + shape + route-plan shadow | Advisory | B |
| 4 | spl | `generate_llm_spl_via_plan` / `generate_llm_spl_fallback` (when failover flag on) | **Candidate SPL only** (non-executable) | conditional | `spl_advisory_generator` / synthesis client | Flag-gated `AI_SOC_LLM_SPL_FALLBACK_ENABLED` |
| 5 | sufficiency / mitre | finalize specialists | Prose / limitations | A |
| 6 | synthesis_lab | lab narration | Summary prose if mode allows | B |
| 7 | composer | usually skipped for in-catalogue SPL | — | — |

Benchmark harness sets `generation_only`; SPL LLM may still run when template miss + flag on.

---

## Reconciliation: 6 attribution timeouts vs 9 `llm_failover` logs (E5-run-4)

**Confidence:** **High** that the six attributed rows are real endpoint hops inside an open `TurnTimingSession` before `finalize_turn_timing`. **Medium** on the +3 orphan-log hypothesis below — static trace + E5-run-4 log shapes support it, but **no one-to-one row mapping** from the nine log lines to six attempts was recoverable from archived telemetry alone.

| Layer | E5-run-4 count | What it measures |
|-------|----------------|------------------|
| Distinct quality-purpose `generate()` / wrapper invocations per turn | **6–8** (case-dependent) | Separate routing, shadow, sufficiency, mitre, synthesis_lab, composer calls — not deduplicated across purposes |
| Failover **candidates** inside one `generate()` chain | **1–2** typical on VPS | Chain-build dedup + within-chain timeout suppression |
| `attribution_v2.endpoint_attempts[]` (real HTTP/model hops) | **6** timeout rows across six probes | Recorded only while session unfrozen |
| `attribution_v2.wrapper_events[]` | **not present in E5-run-4** (schema v3) | Composer/sidecar wrapper wall-clock without synthetic endpoint rows |
| `llm_failover attempt failed … timeout` log lines | **9** | Logger inside `FailoverChatClient` — includes post-finalize orphan completions |
| Late/orphan completion logs | **≤3 inferred** | Socket still running after wrapper deadline or session freeze |

| Source | Count | Explanation |
|--------|-------|-------------|
| `attribution_v2.endpoint_attempts` with `outcome=timeout` | **6** | Governed hops recorded before session freeze (primarily synthesis_lab / composer paths in E5 probes) |
| `llm_failover attempt failed … code=…timeout` log lines | **9** | **+3** explained by combinations of: (a) orphan socket after wrapper abandon, (b) second quality-purpose call in same turn (e.g. `routing` + `synthesis_lab`) where only one path was attributed, (c) sidecar slot-skip + orphan primary still logging |

**Plausible +3 breakdown (static trace; not proven line-by-line):**

1. **Orphan sidecar socket completion** — wrapper returns while `urlopen` blocks; later timeout logs with no `endpoint_attempts` row after freeze.
2. **Dual quality-purpose invocation** — routing sidecar timeout logged separately from synthesis/composer hop that attribution captured.
3. **Wrapper retry / slot saturation** — instruct-only retry or `NOTE_LLM_SLOT_BUSY` skip logs without a second attributed hop; orphan primary may still log.

**Not causes (high confidence):** Nginx 504 (none in E5-run-4); treating two `local_primary` ~90s rows as one failover retry (they are separate invocations with different `call_purpose`).

---

## Duplicate `local_primary` ~90s attempts (E-P1 / E-P5 / E-P6)

| Question | Answer |
|----------|--------|
| Two ~90s `local_primary` rows in one turn? | **Two separate LLM invocations**, not one failover retry — e.g. `routing` (120s wrapper, ~90s socket hop) + `synthesis_lab` or `composer` (second call). |
| Same endpoint? | On VPS, `local_primary` and `foundation_sec_instruct_fallback` often share URL+model but **different config identity**; they remain distinct candidates unless full contract fingerprint matches. |
| Why retry after timeout? | Duplicate **timeout** retry suppressed only for **proven equivalent** candidates within one `generate()` chain (full fingerprint match). Different provider labels with same URL are **not** suppressed. |
| Shadow repeat? | No — shadow roles use distinct prompts/contracts; no evidence of repeating an already-completed inference. |

---

## Classification summary (optimization lens)

| Class | Calls | Action |
|-------|-------|--------|
| **A — Required quality/safety** | MITRE reasoner, missing-evidence reasoner, sufficiency gate inputs, SPL lab producer (when flagged) | Keep |
| **B — Required but infrastructure-sensitive** | synthesis_lab, composer, routing/shadow sidecars on slow single-slot VPS | Keep logic; scale production LLM |
| **C — Conditionally useful** | shape_advisor, route_plan shadow, evidence_observer, intent advisor on frozen-T0 rows | Skip only when `hybrid_role_plan` / budget / `should_skip_sidecar` proves no consumer |
| **D — Proven duplicate/redundant** | Second failover hop proven equivalent by full candidate-contract fingerprint after primary timeout in same `generate()` | Suppress (implemented) |
| **E — Observability defect** | Composer wrapper time without endpoint rows; post-finalize mutation | Fixed in attribution v2 schema `3` (`wrapper_events[]`, `suppressed_candidate_count`) |

---

## attribution_v2 coverage (schema version 3)

**`endpoint_attempts[]`** — real network/model hops only:

- `call_purpose`, `provider_label`, `model` (bounded metadata; no URLs/tokens)
- `duration_ms`, `outcome`, `completed` / `timeout` / `failure`
- `candidate_position`
- Invariant: `endpoint_attempt_count == len(endpoint_attempts)`; `endpoint_attempt_ms_total` sums hop durations only

**`wrapper_events[]`** — sidecar/composer/narration wrappers (no synthetic endpoint rows):

- `call_purpose`, `wrapper_kind`, `duration_ms`, `outcome` (`completed` | `timeout` | `failure` | `saturated`)

**`suppressed_candidate_count`** — proven-equivalent duplicate candidates skipped within one `generate()` chain (not separate quality-purpose calls).

Session **freezes** on `finalize_turn_timing`; late worker completions cannot append endpoint or wrapper rows.
