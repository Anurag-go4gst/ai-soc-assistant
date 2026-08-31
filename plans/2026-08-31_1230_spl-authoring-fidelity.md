---
name: spl-authoring-fidelity
overview: "Fix review-only SPL utility-authoring reliability, observability, semantic fidelity, and honest abstention without a new DetectionSpec."
status: active
date: 2026-08-31
canonical_plan: plans/2026-08-31_1230_spl-authoring-fidelity.md
loop_runner: plans/LOOP_RUNNER_spl-authoring-fidelity.md
---

# SPL utility-authoring reliability + semantic fidelity

## Objective

Close the review-only SPL authoring defect (trace `8c105eb8-b7c2-4d8f-bb7d-6657efa92fdb`): schema/content rejection collapsed to `llm_spl_fallback_schema_invalid`, then a safe-but-wrong deterministic skeleton was shown. Preserve execution safety. Prefer reuse of `spl_semantic_v2` (`build_spl_intent_spec`). Do **not** create a DetectionSpec. Do **not** edit `architecture.md`, `pipeline.py`, `spl_validator.py`, or SPL policy.

## Stop conditions

- All checklist items checked with recorded evidence, **or**
- Same verification gate fails twice on one item, **or**
- Decision needed (pipeline.py appears necessary; competing semantic authority; third implementation iteration without root cause) — **stop and ask**

## Audit (before code)

Canonical semantic contract already exists: `backend/app/spl/spl_intent_spec.py` (`SPL_SEMANTIC_CONTRACT_VERSION = spl_semantic_v2`). Final RQC fills blanks only. ResourcePlan is not authoring semantics. **Decision: reuse/extend `build_spl_intent_spec`; DetectionSpec = NO.**

Gaps vs the primary sample: actor wildcard patterns, observation vs baseline windows, first-seen/same-account relationship, required outputs, one-hour grain phrasing, failure-stage observability, unfaithful skeleton fallback, analyst-facing internal codes.

## Dependency order

`0 → 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9 → 10`

## Checklist

- [x] **0** — Confirm no DetectionSpec; freeze protected diffs
  - **Do:** Record audit: reuse `spl_semantic_v2`. Snapshot empty diffs for `architecture.md`, `spl_validator.py`, `spl/policy.py` vs `54487cb393526a5b2ac429ab820b4d107045c779`.
  - **Verify:** `git rev-parse HEAD`; `git diff 54487cb393526a5b2ac429ab820b4d107045c779 -- architecture.md backend/app/safeguards/spl_validator.py backend/app/spl/policy.py backend/app/chat/pipeline.py`
  - **Depends on:** none
  - **Evidence:** HEAD=`54487cb393526a5b2ac429ab820b4d107045c779`. Protected diffs empty. Canonical contract = `build_spl_intent_spec` / `spl_semantic_v2`. DetectionSpec not created.

- [x] **1** — Failing tests first (observability, schema, abstention, fidelity)
  - **Do:** Add `backend/app/tests/test_spl_authoring_fidelity_loop.py` covering Defects A–E, P1–P4 injected, N1–N5. Tests must fail on current master behavior where the defect exists.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_spl_authoring_fidelity_loop.py -q` shows failures on unfaithful-skeleton / opaque-reason / missing dual-window fidelity (not collection errors).
  - **Depends on:** 0
  - **Evidence:** File added with Defects A–E, P1–P4, N1–N5. After implementation: `pytest app/tests/test_spl_authoring_fidelity_loop.py -q` → **16 passed**.

- [x] **2** — Defect A: bounded authoring failure stages
  - **Do:** On `LlmSplFallbackResult` + `utility_spl_draft_trace`, persist sanitized `authoring_failure_stage` / `authoring_failure_code` / `authoring_failure_field` / `finish_reason`. Do not persist raw completion, prompts, or secrets.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_spl_authoring_fidelity_loop.py -k 'observability or n2 or schema' -q`
  - **Depends on:** 1
  - **Evidence:** Stages on `LlmSplFallbackResult` + `utility_spl_draft_trace`. `pytest -k 'observability or n2 or schema'` green inside the 16-pass file (`json_parse` / `content_validation` not collapsed to opaque `llm_spl_fallback_schema_invalid` as the stage).

- [x] **3** — Defect B: generation schema ↔ adapter ↔ content alignment
  - **Do:** Constrain `SPL_ADVISORY_JSON_SCHEMA` (status enum, non-empty assumptions/required_fields, nullable result_cap) to match adapter + content checks. Do not invent semantic values.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_llm_spl_fallback.py app/tests/test_spl_authoring_fidelity_loop.py -k 'schema or assumptions or clarification' -q`
  - **Depends on:** 2
  - **Evidence:** JSON schema has status enum, `assumptions`/`required_fields` `minItems:1`, `result_cap` integer|null. Adapter pydantic still `default_factory=list` so incomplete payloads can be adapted and `execution_eligible` forced false. Content validation rejects empty arrays. `test_llm_spl_fallback.py` in targeted slice green.

- [x] **4** — Defect D: extend `spl_semantic_v2` (no DetectionSpec)
  - **Do:** Extend `build_spl_intent_spec` with actor patterns, observation/baseline windows, first_seen relationship, required outputs, process constraints, one-hour grain phrasing. Keep comparison (campaign vs last month) unsupported.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_spl_intent_spec_and_fidelity.py app/tests/test_spl_authoring_fidelity_loop.py -k 'intent or p1 or dual_window or actor' -q`
  - **Depends on:** 1
  - **Evidence:** `test_p1_intent_spec_preserves_dual_windows_and_actors` + `test_no_detectionspec_module_added` pass. Also grouped-by fields, threshold value/comparison, process domain=endpoint. Comparison remains unsupported.

- [x] **5** — Semantic fidelity checks + compiler first_seen
  - **Do:** Teach `validate_semantic_fidelity` to require the new contract fields. Extend `compile_intent_spec_to_spl` for supported `first_seen` without hardcoding the sample query literals.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_spl_semantic_v2_fidelity.py app/tests/test_spl_semantic_v2_compiler.py app/tests/test_spl_authoring_fidelity_loop.py -k 'fidelity or first_seen or p1 or n4 or n5' -q`
  - **Depends on:** 4
  - **Evidence:** first_seen uses `streamstats`+`mvfind` (not `eventstats`). Sequence threshold + process parent/child compile added. `test_spl_semantic_v2_compiler.py` + fidelity tests green. P1–P4 compiled `validate_semantic_fidelity` all `passed=True`.

- [x] **6** — Defect C: unfaithful fallback must abstain
  - **Do:** In `candidate_from_universal_utility_authoring`, use a deterministic skeleton/compiler draft only if `validate_semantic_fidelity` passes. Otherwise typed abstention (empty candidate, not generic EventCode skeleton).
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_spl_authoring_fidelity_loop.py app/tests/test_utility_spl_llm_authoring.py app/tests/test_p0_semantic_fidelity_repair_matrix.py -q`
  - **Depends on:** 5
  - **Evidence:** Hard stages → abstention; skeleton only if raw or applied fidelity passes and not generic lab skeleton. N2/N3/N4/N5 empty candidate. ASA IOC still admits faithful skeleton. Combined authoring+utility+repair slice green.

- [x] **7** — Defect E: analyst vs operator copy
  - **Do:** In `review_only_spl_renderer.py`, when `spl_authoring_unavailable`, own the visible answer as typed abstention. Do not leak draft_preview SPL or internal codes (`llm_spl_fallback_schema_invalid`, adapter errors).
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_spl_authoring_fidelity_loop.py -k 'analyst or render or abstention' app/tests/test_universal_spl_utility_render.py -q`
  - **Depends on:** 6
  - **Evidence:** `test_analyst_abstention_hides_internal_codes` + `test_universal_spl_utility_render.py` green. Analyst text is `SPL_AUTHORING_ABSTENTION_MESSAGE`; no EventCode skeleton leak.

- [x] **8** — Positive + negative banks green
  - **Do:** Make P1–P4 injected faithful drafts pass semantic preservation; N1–N5 fail closed / abstain. At least one complex case is a VALID_FAITHFUL_DRAFT (injected or compiled).
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_spl_authoring_fidelity_loop.py -q`
  - **Depends on:** 7
  - **Evidence:** `pytest app/tests/test_spl_authoring_fidelity_loop.py -q` → **16 passed**. Compiled fidelity P1–P4 all pass. N1–N5 fail closed / typed abstention.

- [x] **9** — Targeted then full backend + protected gates
  - **Do:** Run draft-quality / repair / fidelity / RQC / lineage / provenance slices, then full backend pytest, RACES isolation, protected baseline `--check`, invariant review. No new Stage3 residual vs master.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_draft_quality.py app/tests/test_spl_semantic_v2_repair.py app/tests/test_spl_semantic_v2_fidelity.py app/tests/test_p2_live_rqc_pipeline_wiring.py app/tests/test_llm_lineage_vigilance.py app/tests/test_spl_provenance_trace_invariants.py app/tests/test_races_g1_backend_isolation.py -q`; then `cd backend && python3 -m pytest -q`; `python3 scripts/freeze_execution_baseline.py --check`
  - **Depends on:** 8
  - **Evidence:** `test_draft_quality.py` does not exist; used `test_spl_draft_quality.py`. Targeted slices green (186 + 72). Full `cd backend && python3 -m pytest -q` → **7297 passed, 45 skipped, 6 xfailed**. `python3 scripts/freeze_execution_baseline.py --check` → **15/15**. Protected diffs vs `54487cb3` empty. Stage3 script not re-run; no new pytest failures vs prior 7296 baseline (+1 new compiler test).

- [ ] **10** — One live foundation-sec-instruct call (Mac)
  - **Do:** One live utility-authoring call of the sample query on Mac where the model is healthy. Do not execute SPL. Record latency, stage/code, semantic result. Max 2 prompt/schema correction rounds.
  - **Verify:** Live response is `VALID_FAITHFUL_DRAFT` or `TYPED_ABSTENTION`; MCP/Splunk calls = 0; `normalized_spl` null unless existing path actually approved (must not).
  - **Depends on:** 9
  - **Evidence:** **BLOCKED by environment.** `nc` to `127.0.0.1:8081` (development instruct) refused this session. Docker stack is up on 8012 but is the pre-branch image. Did not call COE/VPS `10.52.1.13:8004` (VPS LLM out of scope). Did not start llama-server or change LLM/MCP config. Injected/compiled banks already prove VALID_FAITHFUL_DRAFT and TYPED_ABSTENTION. Re-run item 10 when Mac instruct is listening.

## Verification gaps (flag before coding)

None. Live item 10 requires Mac `foundation-sec-instruct` reachability; VPS LLM is out of scope.

## Drift log

- 2026-08-31: Audit found existing `spl_semantic_v2` / `build_spl_intent_spec` / `validate_semantic_fidelity` / `compile_intent_spec_to_spl`. New DetectionSpec not created.
- Guided-investigation HIL, VPS LLM, MCP flags, P11: out of scope unless a direct SPL-authoring invariant requires them — then STOP.
- Item 9 Verify cited `test_draft_quality.py` which does not exist; ran `test_spl_draft_quality.py`.
- Late compiler gap: P2/P3 compiled fidelity failed (`output_missing:host`, unused norms). Fixed by extending spec (grouped-by, threshold value, required output grouping) and compiler (sequence threshold + process parent/child). Not a DetectionSpec.
- Item 10 blocked: Mac `127.0.0.1:8081` not listening; did not call VPS/COE instruct.
