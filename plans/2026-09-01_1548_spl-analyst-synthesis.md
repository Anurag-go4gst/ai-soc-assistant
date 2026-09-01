---
name: spl-analyst-synthesis
overview: "Post-validation analyst synthesis for review-only SPL drafts. Validated SPL is immutable. Presentation only."
status: active
date: 2026-09-01
canonical_plan: plans/2026-09-01_1548_spl-analyst-synthesis.md
---

# SPL analyst synthesis — post-validation UX

## Objective

After the FINAL VALIDATED SPL is already accepted, add a bounded analyst explanation card so P1–P4 review-only responses are useful. Synthesis has zero authority over SPL, execution, MCP, or authoring.

## Stop conditions

- All checklist items checked with recorded evidence, **or**
- Same verification gate fails twice on one item, **or**
- Fixing this would require changing P1–P4 compiler SPL, prompts/few-shots/patterns, pipeline.py, architecture.md, MCP, HIL, RAG, or P11 — **stop and ask**

## Dependency order

`0 → 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8`

## Governance invariants

- Validated SPL entering synthesis is immutable and rendered byte-for-byte from upstream.
- LLM must never emit or replace SPL.
- Fail closed to `DETERMINISTIC_SYNTHESIS_FALLBACK`; never fail authoring.
- `execution_eligible=false`, `approved=false`, `normalized_spl=null`, MCP=0.
- Do not include `plans/2026-09-01_1112_spl-pattern-guided-llm-authoring.md` or P11 files in the synthesis commit.

## Captured compiler hashes at `6c1d6c4b` (item 0)

| Probe | sha256 |
|---|---|
| P1 | `f27b363dc854b64411104b34698cca82544e9f85b4f6bf1986b2adfbf4693ef8` |
| P2 | `97b84cdf8e4aaecfc4a49825f5913d79959d6da1ca7489b0f4ce1ffcad1b8e1c` |
| P3 | `0bed5774228536dc771475418724980b643326f1a4468f133157b0d8df755f15` |
| P4 | `a4d195beecd85bd8e57e90b4d6ce71b437c12426bb8e7bf7a3b3dd14ba635eb8` |

## Checklist

- [x] **0** — Capture P1–P4 compiler SPL hashes
  - **Do:** Record sha256 of `compile_intent_spec_to_spl(build_spl_intent_spec(P*))` at HEAD `6c1d6c4b`. Pin them in a regression test. Do not change compilers.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. ../.venv/bin/python3 -m pytest app/tests/test_spl_pattern_guided_authoring.py::test_p1_p2_p3_p4_compiler_spl_unchanged_from_6c1d6c4b -q`
  - **Depends on:** none
  - **Evidence:** P1 `f27b363d…`, P2 `97b84cdf…`, P3 `0bed5774…`, P4 `a4d195be…`. `test_p1_p2_p3_p4_compiler_spl_unchanged_from_6c1d6c4b` passed.

- [x] **1** — Synthesis schema, grounding validator, deterministic fallback
  - **Do:** Add `backend/app/spl/review_only_analyst_synthesis.py` with compact JSON schema (`summary`, `what_it_does`, `mappings_assumptions`, `expected_result`), grounding/forbidden-content validator, and deterministic fallback from `spl_semantic_v2` + final SPL + governed mappings. No compiler changes.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. ../.venv/bin/python3 -m pytest app/tests/test_review_only_analyst_synthesis.py -q -k 'schema or deterministic or grounding or fallback'`
  - **Depends on:** 0
  - **Evidence:** `test_review_only_analyst_synthesis.py` 18 passed including schema, deterministic fallback, and grounding negatives.

- [x] **2** — Instruct LLM hop with fail-closed fallback
  - **Do:** Call existing `build_synthesis_client_from_settings` + sidecar timeout. Ask for JSON explanation only. Never accept model SPL. On timeout/malformed/grounding-fail → `DETERMINISTIC_SYNTHESIS_FALLBACK`. Trace source internally only.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. ../.venv/bin/python3 -m pytest app/tests/test_review_only_analyst_synthesis.py -q -k 'llm or fallback or reject'`
  - **Depends on:** 1
  - **Evidence:** Injected grounded JSON → `LLM_SYNTHESIS`. Fenced/malformed/datamodel/join/MITRE/SPL payloads → `DETERMINISTIC_SYNTHESIS_FALLBACK`. Validated SPL unchanged in the rendered card.

- [x] **3** — Wire presentation into existing review-only renderer
  - **Do:** Extend `render_pattern_guided_review_answer` / `apply_review_only_spl_render` so the card injects `final_validated_spl` deterministically and uses synthesis for summary/what_it_does/mappings/expected_result. Do not call compiler again. Do not edit `pipeline.py`.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. ../.venv/bin/python3 -m pytest app/tests/test_spl_pattern_guided_authoring.py -k 'renderer or synthesis or compiler_spl_unchanged' app/tests/test_review_only_spl_renderer.py -q`
  - **Depends on:** 2
  - **Evidence:** Pattern-guided renderer tests plus `test_review_only_spl_renderer.py` green as part of the 105-file authoring slice. `pipeline.py` untouched.

- [x] **4** — Bounded frontend card order
  - **Do:** For review-only utility synthesis cards, render title → summary → what this query does → SPL from `draft_spl_code` → mappings → expected result → no-execution footer. Do not add investigation/MITRE/remediation sections.
  - **Verify:** `cd frontend && npm test -- --run src/components/AnalystResponseCard.test.tsx`
  - **Depends on:** 3
  - **Evidence:** `AnalystResponseCard.test.tsx` 5 passed, including the new synthesis-order test.

- [x] **5** — P1–P4 goldens, negatives, SPL equality
  - **Do:** Add P1–P4 synthesis goldens and negative mutants. Re-prove compiler hashes unchanged from item 0.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. ../.venv/bin/python3 -m pytest app/tests/test_review_only_analyst_synthesis.py app/tests/test_spl_pattern_guided_authoring.py::test_p1_p2_p3_p4_compiler_spl_unchanged_from_6c1d6c4b -q`
  - **Depends on:** 4
  - **Evidence:** 18 synthesis tests passed; compiler hashes unchanged from `6c1d6c4b`.

- [x] **6** — Authoring/fidelity + full backend + frontend build
  - **Do:** Run authoring/compiler/fidelity slice, full backend pytest, frontend tests/build if UI changed.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. ../.venv/bin/python3 -m pytest app/tests/test_spl_pattern_guided_authoring.py app/tests/test_spl_authoring_fidelity_loop.py app/tests/test_review_only_spl_renderer.py app/tests/test_review_only_analyst_synthesis.py -q`; then full `cd backend && PYTHONPATH=../backend:.. ../.venv/bin/python3 -m pytest -q`; `cd frontend && npm test -- --run && npm run build`
  - **Depends on:** 5
  - **Evidence:** Authoring slice 105 passed. Full backend **7377 passed, 45 skipped, 6 xfailed**. Frontend **129 passed**. `npm run build` passed after fixture TS fix.

- [x] **7** — Protected gates
  - **Do:** freeze_execution_baseline `--check`, freeze_spl_optimization_authority `--check`, RACES G1 + live-path + freeze tests. Confirm architecture.md / pipeline.py / policy.py / MCP/HIL/RAG untouched.
  - **Verify:** `python3 scripts/freeze_execution_baseline.py --check`; `PYTHONPATH=backend:. .venv/bin/python3 scripts/freeze_spl_optimization_authority.py --check`; `cd backend && PYTHONPATH=../backend:.. ../.venv/bin/python3 -m pytest app/tests/test_live_path_untouched_by_ec.py app/tests/test_races_g1_backend_isolation.py -q`
  - **Depends on:** 6
  - **Evidence:** Freeze 15/15. SPL authority 49 rows. RACES G1 + live-path + G2 **18 passed**. Diff vs `6c1d6c4b` empty for architecture.md / pipeline.py / policy.py / spl_validator.py.

- [x] **8** — Live `/api/chat` P1–P4 twice each
  - **Do:** Eight live calls, MCP off. Require SPL hashes match `6c1d6c4b`, truthful explanations, safety flags unchanged. Do not merge. Do not start P11.
  - **Verify:** Capture authoring_source, synthesis_source, final SPL sha256, execution_eligible, approved, normalized_spl, MCP count for all 8 calls.
  - **Depends on:** 7
  - **Evidence:** 8/8 HTTP 200. Pair SPL hashes identical. P2 live sha256 `537580db…` matches `6c1d6c4b` live form. `generation_mode=deterministic_compiler_draft`. `synthesis_source=DETERMINISTIC_SYNTHESIS_FALLBACK` 8/8 (`no_balanced_json_object`). `execution_eligible=false`, `approved=false`, `normalized_spl=null`, MCP=0. No MITRE/remediation/datamodel/tstats/join. PRODUCT_SYNTHESIS_SUCCESS=8/8. LLM_SYNTHESIS_SUCCESS=0/8.


## Drift log

- HEAD at start: `6c1d6c4b`. Uncommitted `plans/2026-09-01_1112_spl-pattern-guided-llm-authoring.md` stays out of this commit.
- Live instruct hop returned non-JSON (`no_balanced_json_object`) on all 8 calls; product used `DETERMINISTIC_SYNTHESIS_FALLBACK`. That is accepted: PRODUCT_SYNTHESIS_SUCCESS does not require LLM_SYNTHESIS 8/8.
