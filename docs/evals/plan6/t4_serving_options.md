# Plan 6 D1 — T4 serving options (evidence only)

Production T4 timeout stayed **2.0s**. `AI_SOC_T4_SEMANTIC_UNDERSTANDING_ENABLED` stayed **false** after D0 restore (Arm A). No new env flag. No routing keywords. No D3 decision.

JSON: `docs/evals/plan6/t4_serving_options.json` (run `docs/evals/plan6/runs/20260813T155057Z_d1/`). Git SHA `1d32ac6`. Probe: `scripts/eval_plan6_t4_serving_options.py` (same T4 system/user contract as `_live_single_hop_provider`).

D0 already showed the hop is invoked on T4 and never accepted at 2.0s. D1 asks whether any **already-configured** serving option changes that. It does not.

## Inventory (in-environment only)

| Option | Configured? | What it is |
|---|---|---|
| **A** local primary | **yes** | Foundation-Sec-1.1-8B-Instruct Q8 at `:8081` (`AI_SOC_LLM_LOCAL_*`, `llama-server -np 1 -c 4000 -t 4`) |
| **B** Foundation-Sec instruct failover URL | **no** | `AI_SOC_LLM_FOUNDATION_SEC_INSTRUCT_BASE_URL` unset. Local primary **is** this model — not a second endpoint |
| **C** Qwen primary | **no** | `AI_SOC_LLM_QWEN_PRIMARY_ENABLED` unset/false; no `QWEN_BASE_URL` / `MODEL` |
| **D** slot count small N | **yes, as a test** | App sidecar is single-flight; llama-server is `-np 1`. N=2 cannot create a second decode slot |

T4 live path is hardcoded to `resolve_local_primary_endpoint(sidecar=True)`. Switching models would be a new flag or a local-URL swap that affects every LLM role. Neither was done.

Host at follow-up: load `4.68 4.69 4.42`, llama RSS **8.6 GB**, **swap 4096/4096 MB used**. That is the box the 8B Q8 actually runs on.

## Verdict

| Option | Viable at current 2.0s production posture? | Why |
|---|---|---|
| **A** local primary, N=1, 2.0s | **Non-viable** | D0: 9/9 T4 hops timed out ~2000 ms, 0 accepted. D1 direct replica: 2.0s cold **2022 ms** timeout, 2.0s warm **2004 ms** timeout, empty output. Off-path 90s and a clean 180s `max_tokens=400` call also returned **no JSON**. |
| **B** Foundation-Sec failover URL | **Non-viable (unavailable)** | Not configured. Same weights as A even if it were. |
| **C** Qwen | **Non-viable (unavailable)** | Not configured. No already-configured second model to measure. |
| **D** N=2 on A | **Non-viable (worse)** | D0 `/chat` N=2: 1 timed_out + 1 `empty_output`/`llm_model_slot_busy`. Direct llama N=2 at 2.0s: **2/2 timed_out**. Raising app concurrency cannot add a model slot. |

No option produced an accepted T4 contract. Fail-closed: deterministic `clarification_required` + prohibited `{spl,mcp}` kept. **Zero** capability-widening events, **zero** skill keys, **zero** dropped clarification (nothing arrived to merge).

D0 hop p95 **is** the 2.0s cap (all timed out), not “just above 2.0s”. A production timeout raise was **not** the first experiment and was **not** applied.

## Same metrics as D0, per option

### A — local primary, N=1, production 2.0s (`/chat` from D0; hop replica from D1)

| Metric | `/chat` T4 ON (D0) | Direct hop replica (D1, T4 flag off) |
|---|---|---|
| invoked (T4 rows) | **9/9** | n/a (off-path) |
| accepted contract | **0/9** | **0** (2s cold + 2s warm) |
| timeout rate | **9/9** hop ~2000–2003 ms | **2/2** (2022 ms cold, 2004 ms warm) |
| empty output | 0 on serial `/chat` (timeout, not empty) | 2/2 empty (client timeout, no body) |
| `llm_model_slot_busy` | 0 serial | 0 (no sidecar semaphore on direct path) |
| hop p50 / p95 | 2001 / 2003 ms (censored at 2.0s) | 2004 / 2022 ms (censored) |
| paraphrase `/chat` p50 / p95 | **38784 / 42320 ms** | n/a |
| cold vs warm `/chat` | 39294 ms first; remaining still 33–42s | hop still times out; no warm win at 2.0s |
| T1–T3 T4 invocations | **0/3** | n/a (flag off; D0 already proved qualification) |
| correctness on 8 paraphrases | 0/8 accepted | 0/8 accepted (see below) |
| false widening | none (no merge) | none (no merge) |

End-to-end `/chat` is dominated by the rest of the pipeline (~33–42s paraphrases, 92s guided T4). The 2.0s hop is a bounded add-on on T4 turns only.

### B / C — not configured

All D0 metrics **n/a**. No second endpoint to point the T4 hop at without a new flag or hijacking `AI_SOC_LLM_LOCAL_*`.

### D — N=2

| Metric | `/chat` (D0, app semaphore) | Direct llama `-np 1` (D1) |
|---|---|---|
| pair | para.003 + para.004 | same pair |
| accepted | 0/2 | 0/2 at 2.0s; 0/2 at 90s |
| timeout | 1/2 (para.003 hop 2002 ms, `/chat` 34641 ms) | **2/2** at 2.0s (~2002–2003 ms); **2/2** at 90s |
| empty + `llm_model_slot_busy` | **1/2** (para.004, `/chat` 1344 ms) | 0 busy notes (no sidecar); both timed out |
| pair wall | 34786 ms | 2004 ms at 2.0s; ~90s at complete-gen |

App N=2 **skips** the second hop (`llm_model_slot_busy`). Direct N=2 **queues** on `-np 1` and still dies at the client timeout. Neither yields an accepted contract.

## Effect isolations (same T4 contract, production 2.0s unchanged)

Measured on `p6.para.003` unless noted. Tiny/short calls prove the model process is alive; long T4 JSON calls do not return inside the budgets below.

| Effect | What we changed | Result |
|---|---|---|
| **1. Warm-up** | 2.0s cold vs 2.0s after prior T4 prompt; 90s cold vs 90s warm | 2.0s: 2022 vs 2004 ms, both timeout. 90s: 90094 vs 90099 ms, both timeout. Short ping after cache: 13.3s then 8.7s then 7.4s. Warm KV cache helps **short** completions, not a 2.0s T4 JSON hop. |
| **2. Timeout budget** | Off-path 90s and a **clean** 180s `max_tokens=400` after an idle ping. Production timeout **not** raised | 90s: every production-shaped T4 call timed out (8/8 paraphrases + 3 ambiguous + isolations). Clean 180s: **180123 ms** timeout, 0 chars. Hop p95 is not “just above 2.0s”; a 2→3s SLO tweak would not have helped. `stream:false` + `max_tokens=400` does not return until generation finishes. |
| **3. Prompt / context overhead** | Production user JSON is **319 chars**. Variants: `max_tokens=80`, query-only user prompt, tiny 10-token classification | User-contract size is not the prefill problem. Tiny classification **succeeded**: 14007 ms, 52 prompt / 3 completion tokens, text `Suspicious`. Streamed production T4 prompt: **TTFT 4.74 s**, first token **`To`** (not `{`), then decode crawled; client killed at ~268 s without finishing 80 tokens. Production `max_tokens=400` is a long-output role on this box. |
| **4. Serving / model choice** | Only A exists | 8B Q8, 4 threads, 8.6 GB RSS, **swap full**. Short pings work. JSON-shaped T4 generation does not complete in 2s / 90s / 180s non-stream. No Qwen/other vendor in env. |
| **5. Concurrency / slot pressure** | N=1 vs N=2; llama `-np 1` | D0 `/chat` N=2 → 50% `llm_model_slot_busy`. Direct N=2 → both timeout. Client timeouts leave the single llama slot occupied (orphan decode). That contaminated the serial 90s series; the clean 180s after idle ping **still** timed out. |

## Correctness on the 8 residual paraphrases

Off-path complete-gen (90s, production prompt, `max_tokens=400`), same merge rules as `maybe_enrich_t4_semantic`:

| row | expected family | parsed | accepted | proposal family | widening | notes |
|---|---|---|---|---|---|---|
| p6.para.003 | `spl_generation_only` | no | no | — | no | timed_out 90076 ms |
| p6.para.004 | `spl_generation_only` | no | no | — | no | timed_out 90099 ms |
| p6.para.005 | `spl_generation_only` | no | no | — | no | timed_out 90094 ms |
| p6.para.006 | `spl_generation_only` | no | no | — | no | timed_out 90096 ms |
| p6.para.007 | `spl_generation_only` | no | no | — | no | timed_out 90098 ms |
| p6.para.008 | `spl_generation_only` | no | no | — | no | timed_out 90091 ms |
| p6.para.012 | `spl_generation_only` | no | no | — | no | timed_out 90091 ms |
| p6.para.015 | `spl_generation_only` | no | no | — | no | timed_out 90090 ms |

**0/8** parsed, **0/8** accepted, **0/8** family match. Semantic accuracy of a T4 proposal is **not measurable** until some option returns JSON. Deterministic floor on all eight is `clarification_required` / prohibited `{spl,mcp}` / T4 `out_of_registry` — D0 already showed the hop **invokes**; it does not repair the route inside 2.0s.

Contract observation (not a serving option; do not treat as D3): `_family_change_permitted` refuses an intent-family change while `clarification_required` is already true. Even a later accepted JSON hop could not retarget these eight to `spl_generation_only` without a separate merge-rule decision. D1 does not change that.

## False widening on ambiguous T4 cases

| row | class | parsed | false widening | why |
|---|---|---|---|---|
| p6.clarify (`Look into it.`) | underspecified T4 | no (90s timeout) | **no** | nothing merged; clarification kept |
| rt.para.009 | ownership-deferred ambiguous | no | **no** | nothing merged; prohibitions kept |
| rt.para.013 | ownership-deferred ambiguous | no | **no** | nothing merged; prohibitions kept |

Zero widening, zero dropped clarification, zero skill keys. Fail-closed under timeout is the observed safety property. It is **not** evidence the model would stay inside the contract if a hop ever completed — that remains D2/D3, and D2 has no accepted contracts to score.

## Restore

Unchanged Arm A: `AI_SOC_T4_SEMANTIC_UNDERSTANDING_ENABLED=false`, exec `false`, v2 `true`. Timeout env unset → effective **2.0**. pytest `app/tests/test_semantic_t4_understanding.py` **14 passed**. llama-server was **not** restarted.

## What D3 should see (not decided here)

- Routing/qualification works (D0: T4 invoked on paraphrases, 0/3 on T1–T3).
- Every in-environment serving option is non-viable at the current 2.0s posture.
- Raising the timeout is not a small correction: 90s and 180s off-path still did not yield an accepted contract on this host.
- N=2 is harmful, not helpful, while `-np 1`.
- Qwen / a distinct Foundation-Sec URL are not available to compare.
- Do not add paraphrase keywords to paper over this.
