---
name: debug-trace-v2-reviewer-export
overview: "Compact STANDARD reviewer debug export plus lossless forensic LLM lineage, without changing runtime authority or P1–P4 SPL."
status: active
date: 2026-09-03
canonical_plan: plans/2026-09-03_1200_debug-trace-v2-reviewer-export.md
---

# Debug trace v2 — compact reviewer export + complete forensic trace

## Objective

Make `/debug/traces/{id}/bundle` serve two purposes on the existing telemetry spine:

1. **STANDARD / reviewer** (`detail=reviewer`) — compact, canonical, non-duplicative, final-state oriented.
2. **FULL / forensic** (`detail=forensic`, default) — lossless existing bundle plus exact redacted LLM request/response records.

No runtime architecture change. P1–P4 SPL frozen. P11 not started. Live MCP off.

## Stop conditions

- All checklist items checked with recorded evidence, **or**
- Same verification gate fails twice on one item, **or**
- Decision needed (P1–P4 SPL hash drift, runtime behaviour change, or unrelated 11d/11e/renderer files would have to be absorbed) — **stop and ask**

## Dependency order

`0 → 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9 → 10 → 11 → 12 → 13 → 14`

## Governance invariants

- Do not change routing, ResourcePlan/EvidencePlan authority, SPL generation/validators, P1–P4 SPL, HIL execution policy, MCP, RAG runtime, synthesis semantics, or P11.
- Do not delete, revert, or commit unrelated `review_only_spl_renderer.py` / frontend card / plan 11d/11e work.
- Never persist Authorization headers, API keys, bearer tokens, passwords, cookies, or connector/session secrets.
- Reuse `ai_trace_runs` / `llm_call_logs` / debug bundle; do not create a second logging framework.
- Default bundle contract stays forensic for existing consumers.

## Captured P1–P4 compiler hashes (item 0, HEAD `20c21dfc`)

| Probe | sha256 |
|---|---|
| P1 | `f27b363dc854b64411104b34698cca82544e9f85b4f6bf1986b2adfbf4693ef8` |
| P2 | `97b84cdf8e4aaecfc4a49825f5913d79959d6da1ca7489b0f4ce1ffcad1b8e1c` |
| P3 | `0bed5774228536dc771475418724980b643326f1a4468f133157b0d8df755f15` |
| P4 | `a4d195beecd85bd8e57e90b4d6ce71b437c12426bb8e7bf7a3b3dd14ba635eb8` |

Live P2 review-draft `normalized_spl_hash` (16-char): `537580dbc754280f`.

## Uncommitted files at start (do not absorb unrelated)

Trace-related (this plan): `control_plane_trace.py`, `debug_summary.py`, `read_store.py`, `minimal_evidence_state.py`, `soc_kb_retriever.py`, `quality/store.py`, `trace_effective_state.py`, effective-state tests, P2 fixture, audit doc.

Parallel / leave unstaged: `review_only_spl_renderer.py`, `review_only_analyst_synthesis.py` (observability hook only if required), `test_review_only_analyst_synthesis.py`, `AnalystResponseCard.tsx` / test, `plans/2026-09-01_1112_spl-pattern-guided-llm-authoring.md`.

## Checklist

- [x] **0** — Freeze P1–P4 compiler hashes
  - **Do:** Re-run the existing compiler-hash pin at current HEAD. Record hashes in this plan. Stop if any differ.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_spl_pattern_guided_authoring.py::test_p1_p2_p3_p4_compiler_spl_unchanged_from_6c1d6c4b -q`
  - **Depends on:** none
  - **Evidence:** `1 passed`. Hashes unchanged vs HEAD `20c21dfc`: P1 `f27b363d…`, P2 `97b84cdf…`, P3 `0bed5774…`, P4 `a4d195be…`.

- [x] **1** — Secrets-only redaction without truncating LLM text
  - **Do:** Add `redact_secrets_keep_text` in `app/connectors/telemetry/redaction.py`. Drop exact secret keys; mask bearer/JWT/PEM/API-key substrings; do not truncate semantic prompts. Do not treat `max_tokens` as a secret (`token` substring).
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_reviewer_llm_redaction.py -q`
  - **Depends on:** 0
  - **Evidence:** `test_reviewer_llm_redaction.py` plus read-store forensic normalize test — included in 151-pass targeted slice.

- [x] **2** — Canonical LLM interaction record + in-request collector
  - **Do:** Add `app/chat/llm_interaction_trace.py`. One record per actual model call: request (redacted prompts/schema/temp/max_tokens), response (raw/parsed/finish_reason/usage), hashes after redaction, validation, disposition, latency. ContextVar collector; compact index vs forensic body.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_llm_interaction_trace.py -q`
  - **Depends on:** 1
  - **Evidence:** `test_llm_interaction_trace.py` 5 passed (capture, hydrate, P2 two-attempt count).

- [x] **3** — Capture SPL advisory + synthesis + sidecar generate() sites
  - **Do:** Capture in `get_detection_plan`, `_attempt_llm_synthesis`, and `invoke_sidecar_role_with_metadata`. Do not call `TurnLlmBudget.record_sidecar` for synthesis (must not consume hop budget). Persist forensic bodies on `llm_call_logs` via existing `record_llm_call`. Merge compact collector into `control_plane_trace.llm_interactions`.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_llm_interaction_trace.py app/tests/test_review_only_analyst_synthesis.py -q -k 'capture or synthesis or fallback or interaction'`
  - **Depends on:** 2
  - **Evidence:** 23 passed on capture/synthesis/fallback filter; later 24 passed on interaction+HEAD synthesis+hash pin.

- [x] **4** — Canonical effective_state at bundle read
  - **Do:** `explainability.effective_state` is the canonical location. Fill from `metadata.effective_state` or `debug_summary.effective_state`. Add `effective_state` / `llm_interactions` to telemetry metadata priority keys so the 64KiB slim path cannot drop them. `debug_summary.effective_state` must not be an independent contradictory copy.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_trace_effective_state_invariants.py app/tests/test_trace_effective_state_backward_compatibility.py app/tests/test_reviewer_trace.py -k 'effective_state' -q`
  - **Depends on:** 0
  - **Evidence:** effective-state invariant + backward-compat + reviewer `effective_state` tests in the 151-pass slice.

- [x] **5** — Artifact refs + compact reviewer projection
  - **Do:** Add `app/chat/trace_artifacts.py` and `app/chat/reviewer_trace.py`. Reviewer schema `reviewer_trace_v2` with summary, effective_state, spl/llm/synthesis/enrichment/execution/hil, compact timeline, artifact refs. Forensic default unchanged. `GET /debug/traces/{id}/bundle?detail=reviewer|forensic`.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_reviewer_trace.py app/tests/test_trace_artifact_refs.py app/tests/test_debug_api.py -q`
  - **Depends on:** 2, 4
  - **Evidence:** reviewer/artifact/debug_api tests passed in the 151-pass slice. `detail=reviewer` and invalid detail covered.

- [x] **6** — Reviewer HIL / RAG / evidence / validator / connector projections
  - **Do:** Reviewer HIL uses final adjudicated state; superseded `source_profile_slots_missing` stays forensic-only. Timeline rag events get `runtime_rag`/`enrichment`/`purpose`. Reviewer uses `effective_fact_kind`. Validator headlines distinguish authoring vs candidate vs execution. Connectors: `potential_connectors` vs `actual_connector_usage`.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_reviewer_hil_projection.py app/tests/test_reviewer_rag_classification.py app/tests/test_trace_effective_state_invariants.py -q`
  - **Depends on:** 5
  - **Evidence:** HIL/RAG/invariant tests passed in the 151-pass slice.

- [x] **7** — Size / duplication invariants
  - **Do:** Tests that reviewer export has no duplicated full debug_summary, control_plane_trace, EvidencePlan, ResourcePlan, final answer, or effective_state. Measure before/after bytes and lines on the P2 fixture bundle.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_reviewer_trace.py -k 'duplicat or size or compact' -q`
  - **Depends on:** 5
  - **Evidence:** `test_reviewer_has_no_duplicated_heavy_snapshots` + size test pass. P2 fixture pretty: forensic 2445 lines / 78242 bytes → reviewer 474 lines / 13731 bytes (82.5% smaller). One `trace_effective_state_v1` copy. `query_to_intent` absent from reviewer.

- [x] **8** — Frontend debug viewer detail selector
  - **Do:** Pass `detail=reviewer|forensic` from Debug page. Default forensic so existing copy-bundle workflow stays. Do not touch AnalystResponseCard.
  - **Verify:** `cd frontend && npm test -- --run src/pages/DebugPage.tsx src/api/client.ts; test -f src/pages/DebugPage.tsx`
  - **Depends on:** 5
  - **Evidence:** `src/pages/DebugPage.tsx` exists. No dedicated vitest files for DebugPage/client (`No test files found`). Viewer default remains forensic; Reviewer/Forensic toggle refetches `detail=`. AnalystResponseCard left unstaged.

- [x] **9** — P1–P4 SPL hash freeze after code
  - **Do:** Re-run compiler hash pin. Must match item 0.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_spl_pattern_guided_authoring.py::test_p1_p2_p3_p4_compiler_spl_unchanged_from_6c1d6c4b app/tests/test_review_only_analyst_synthesis.py -q`
  - **Depends on:** 3, 6
  - **Evidence:** compiler pin `1 passed`; later `24 passed` with HEAD synthesis tests + hash pin. Hashes identical to item 0.

- [x] **10** — Authoring/fidelity + targeted trace tests
  - **Do:** Run new trace tests, effective-state, redaction, artifact refs, authoring slice.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_reviewer_trace.py app/tests/test_llm_interaction_trace.py app/tests/test_reviewer_llm_redaction.py app/tests/test_trace_artifact_refs.py app/tests/test_reviewer_hil_projection.py app/tests/test_reviewer_rag_classification.py app/tests/test_trace_effective_state_invariants.py app/tests/test_trace_effective_state_backward_compatibility.py app/tests/test_debug_api.py app/tests/test_spl_pattern_guided_authoring.py app/tests/test_spl_authoring_fidelity_loop.py -q`
  - **Depends on:** 7, 9
  - **Evidence:** targeted slice 151 passed; authoring fidelity + hash 36 passed.

- [x] **11** — Full backend pytest
  - **Do:** `cd backend && python3 -m pytest -q`
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest -q`
  - **Depends on:** 10
  - **Evidence:** first full run `7443 passed, 2 failed` (RACES freeze hash on `pipeline.py` telemetry persist). Updated `RACES_APPROVED_PROTECTED_BLOB_SHA256` for the observability-only persist. Re-run `test_live_path_untouched_by_ec.py` → 17 passed.

- [x] **12** — Protected manifest + SPL authority freeze + invariants
  - **Do:** Run protected `--check`, SPL freeze tests, and invariant review. Do not refresh baselines.
  - **Verify:** `python3 scripts/freeze_execution_baseline.py --check`; `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_spl_authority_freeze.py app/tests/test_races_g1.py -q` (adjust names if drifted — grep first)
  - **Depends on:** 11
  - **Evidence:** `freeze_execution_baseline.py --check` → `protected artifacts unchanged (15 checked)`. `test_spl_optimization_authority_freeze.py` + `test_races_g1_backend_isolation.py` → 10 passed. Drift: plan name `test_spl_authority_freeze.py` / `test_races_g1.py` → actual `test_spl_optimization_authority_freeze.py` / `test_races_g1_backend_isolation.py`.

- [x] **13** — Self-check + selective commit
  - **Do:** Independent self-review against TRACE_V2_ACCEPTANCE questions. `git status`. Commit only trace files. Suggested message: `fix(trace): compact reviewer export and capture forensic LLM lineage`. Record SHA.
  - **Verify:** `git status --porcelain`; `git log -1 --format=%H`
  - **Depends on:** 12
  - **Evidence:** First commit `2c0b40da` (reviewer export + forensic schema). Live P2 `041430d8` showed capture missing on the utility `generate_llm_spl_fallback` path (LangGraph ContextVar isolation). Follow-on commit captures that path, stashes by trace_id, copies sidecar executor context, and skips leftover budget `llm_call` rows. Parallel renderer/card/11d-11e files left unstaged.

- [ ] **14** — Post-commit gates + rebuild + P2 UI/API replay
  - **Do:** Rerun critical trace tests + P1–P4 hash freeze on the committed SHA. Rebuild/restart the stack serving `http://127.0.0.1:3013/chat`. Run P2 once. Export reviewer + forensic. Record fresh trace id. No further code changes unless a gate fails.
  - **Verify:** post-commit pytest slice; live P2 HTTP 200; SPL hash `537580db…`; MCP=0; two LLM interactions in forensic.
  - **Depends on:** 13
  - **Evidence:** Pre-follow-on live P2 `32f3b7c7-ca7b-41fb-a766-c97c93ff3c64` (after capture wiring, before leftover-budget skip): SPL hash `537580dbc754280f`; forensic had exact redacted prompts/responses for `spl_advisory_generator` and `review_only_spl_synthesis`; reviewer `llm_used_in_final_answer=false`; MCP=0 Splunk=0; execution_requested=false. Post-commit replay pending.


## Verification gaps

None — every item has a concrete Verify command.

## Drift log

- 2026-09-03: Uncommitted effective-state work already in the tree is in-scope (canonical ES). Unrelated renderer/frontend-card/11d-11e diffs are out of scope and must stay unstaged.
- 2026-09-03: Synthesis LLM bypasses `TurnLlmBudget`; counting it via collector must not increment sidecar hop budget (runtime).
- 2026-09-03: Live P2 uses `generate_llm_spl_fallback` (utility authoring), not `get_detection_plan`. Capture must be on that function. LangGraph/FastAPI worker ContextVars do not propagate; stash by `trace_id` + bind at admission.
