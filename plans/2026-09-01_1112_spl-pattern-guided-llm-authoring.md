---
name: spl-pattern-guided-llm-authoring
overview: "Evolve review-only SPL authoring into pattern-guided LLM adaptation of one vetted topology per analysis_shape, starting with P1 first_seen."
status: active
date: 2026-09-01
canonical_plan: plans/2026-09-01_1112_spl-pattern-guided-llm-authoring.md
loop_runner: plans/LOOP_RUNNER_spl-pattern-guided-llm-authoring.md
---

# SPL pattern-guided LLM authoring (P1 → P2 → P3 → P4)

## Objective

Keep the existing utility-authoring path. Select one vetted semantic pattern from the existing `_AUTHORING_FEW_SHOTS` store, have `foundation-sec-instruct` adapt fields/filters/outputs only, thin-normalize, validate, one repair, then `compile_intent_spec_to_spl` as `LEGACY_COMPILER_RESCUE`. Do not build a second compiler or a second few-shot repository. P1 pattern work is closed (`P1_LLM_PATTERN_PASS=NO`, product PASS via compiler rescue). P2 starts as an independent sequence family; product PASS does not require LLM pattern success.

## Stop conditions

- All checklist items checked with recorded evidence, **or**
- Same verification gate fails twice on one item, **or**
- P1/P2/P3/P4 cannot pass within two correction iterations, **or**
- Architecture redesign, a second few-shot repo, a second compiler, semantic preprocessor rewrites, or validator weakening appears necessary — **stop and ask**

## Dependency order

`0 → 1 → … → 8e` then `9a → 9b → 9c → 9d → 9e` (P3) then `10a → 10b → 10c` (P4) then `11a → 11b → 11c → 11d → 11e` (mvmap exact-membership). Do not start P11 until 11e live cards pass human UI check and this phase is merged.

## Checklist

- [x] **0** — Phase 0 pin
  - **Do:** Record HEAD `207e7409250e19095985d2771f48576f6c944305`, clean worktree, existing prompt/few-shot/preprocessor/validator/repair/compiler paths. Confirm zero planned diffs in architecture.md, pipeline.py, spl_validator.py, policy.py.
  - **Verify:** `git rev-parse HEAD`; `git status --porcelain`; `git diff HEAD -- architecture.md backend/app/chat/pipeline.py backend/app/safeguards/spl_validator.py backend/app/spl/policy.py`
  - **Depends on:** none
  - **Evidence:** HEAD=`207e7409250e19095985d2771f48576f6c944305`, branch `fix/spl-authoring-fidelity`, porcelain empty at pin. Protected diffs empty. Prompt=`llm_fallback.spl_advisory_prompts`; store=`_AUTHORING_FEW_SHOTS`; preprocessor=`normalize_review_only_spl`; validator=`validate_semantic_fidelity`; repair=`MAX_SPL_LLM_REPAIRS=1`; compiler=`compile_intent_spec_to_spl`.

- [x] **1** — Extend existing first_seen asset into a vetted pattern (P1 only)
  - **Do:** On `_AUTHORING_FEW_SHOTS["first_seen"]` in `llm_fallback.py`, replace the stats/baseline_count topology with the compiler-proven streamstats + exact `mvfilter(==)` topology using generic subject/object fields (not EventCode 4624). Add pattern_id, invariants, allowed adaptations, prohibited structural changes. Enable only `first_seen`. Register FIRST_SEEN in `llm/policy/examples.py` catalog (metadata only). Prompt: PRESERVE PATTERN TOPOLOGY; skip the competing ranking system example for shapes that already have an authoring shot; include first_seen in skip_forced_head.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_spl_pattern_guided_authoring.py -k 'pattern or prompt or topology' -q`
  - **Depends on:** 0
  - **Evidence:** `test_spl_pattern_guided_authoring.py -k 'pattern or prompt or topology or preprocessor or authoring_source or rescue or render or synthesis'` → **10 passed**. Pattern is generic `subject_norm`/`object_norm` + streamstats/`mvfilter(==)`; no EventCode 4624. **Did not** add FIRST_SEEN to `examples.py` — that hashes into P8 `spl_advisory_generator` ACTIVE identity and broke frozen hashes; metadata stays on `_AUTHORING_FEW_SHOTS`.

- [x] **2** — Thin preprocessor + authoring_source traces
  - **Do:** In `review_only_spl_postprocessor.py`, add prefix-wildcard LIKE `*`→`%` only when `actor_patterns` establish a prefix. Do not rewrite 37d/7d/subject/object/algorithm. In `utility_spl_authoring.py` stamp `authoring_source` ∈ {LLM_PATTERN_PRIMARY, LLM_PATTERN_NORMALIZED, LLM_PATTERN_REPAIR, LEGACY_COMPILER_RESCUE, ABSTAIN} and the P1_* trace keys. Compiler rescue must be explicit; never count it as LLM success.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_spl_pattern_guided_authoring.py -k 'preprocessor or authoring_source or rescue' -q`
  - **Depends on:** 1
  - **Evidence:** Same 10-test slice includes preprocessor/rescue cases. Prefix `like(...,"*admin-*")` → `"admin-%"` only when actor_patterns are prefixes. Compiler path stamps `authoring_source=LEGACY_COMPILER_RESCUE` and `llm_pattern_success=false`.

- [x] **3** — Pattern-guided review-only synthesis
  - **Do:** When `utility_spl_draft_trace` has a vetted pattern and a validated SPL, `render_user_bound_spl_utility_answer` emits What-this-query-does + SPL + mappings from spec/validated SPL/bindings only. Do not invent facts. Leave user-bound skeleton answers (`Review-only - not executed`) unchanged.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_spl_pattern_guided_authoring.py -k 'render or synthesis' app/tests/test_t1_t4_authority_boundary.py app/tests/test_universal_spl_utility_render.py -q`
  - **Depends on:** 2
  - **Evidence:** Combined targeted slice with authority/render tests **252 passed**. Live `/api/chat` message uses title `Review-only SPL draft — not executed` + What this query does + SPL + Mappings; skeleton path unchanged.

- [x] **4** — P1 positive + mutant tests
  - **Do:** Injected compiler-topology draft → LLM_PATTERN_* not rescue; mutants fail (regex membership, 7d-only retrieval, wrong subject, missing outputs). Pattern template contains no EventCode 4624 / admin-*/svc-*.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_spl_pattern_guided_authoring.py app/tests/test_spl_authoring_fidelity_loop.py -q`
  - **Depends on:** 3
  - **Evidence:** After compact: **76 passed** (`test_spl_pattern_guided_authoring.py` + `test_spl_authoring_fidelity_loop.py`). Mutants: mvfind, -7d-only, missing streamstats.

- [x] **5** — Targeted then full gates after product-code change
  - **Do:** Targeted authoring/fidelity/render slices, full backend pytest, RACES isolation, protected baseline `--check`, SPL authority freeze, invariant review. Protected files remain zero-diff vs `207e7409` for architecture.md / pipeline.py / spl_validator.py / policy.py.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_spl_pattern_guided_authoring.py app/tests/test_spl_authoring_fidelity_loop.py app/tests/test_utility_spl_llm_authoring.py app/tests/test_llm_spl_fallback.py app/tests/test_prompt_policy_examples.py app/tests/test_universal_spl_utility_render.py app/tests/test_t1_t4_authority_boundary.py -q`; then `cd backend && python3 -m pytest -q`; `python3 scripts/freeze_execution_baseline.py --check`
  - **Depends on:** 4
  - **Evidence:** Targeted combined slice **252 passed**. Full backend **7329 passed, 45 skipped, 6 xfailed, 0 failed**. Freeze `--check` **15/15**. RACES G1 + live-path + SPL authority freeze **18 passed**. Protected diffs vs HEAD empty for architecture.md / pipeline.py / spl_validator.py / policy.py.

- [x] **6** — Live P1 /api/chat twice (MCP off)
  - **Do:** Two `/api/chat` P1 calls. Capture pattern/raw/preprocessor/validator/repair/authoring_source. Inspect rendered message. If P1 does not pass, STOP — do not start P2. Max two P1 correction iterations.
  - **Verify:** Both calls: semantic fidelity PASS, execution_eligible=false, normalized_spl=null, MCP/Splunk=0. Record authoring_source honestly (compiler rescue ≠ LLM success).
  - **Depends on:** 5
  - **Evidence:** Product P1 **PASS** on 4/4 live calls (2 before compact + 2 after). All `authoring_source=LEGACY_COMPILER_RESCUE`, `finish_reason=length`, `raw_llm_spl` empty, repair unused, `fidelity_passed=true`, `execution_eligible=false`, `approved=false`, `normalized_spl=null`, `mcp_executed=false`. LLM pattern success **0/4**. Two correction iterations (vetted topology + compact few-shot) did not produce a closed instruct JSON. **STOP P2.**

- [x] **7** — P1 human UI check gate
  - **Do:** Confirm READY_FOR_HUMAN_UI_CHECK. READY_TO_MERGE stays NO. P11 not started. Live MCP off.
  - **Verify:** Rendered answer has review-only title, what-this-query-does, SPL, mappings; no MITRE/remediation/investigation steps.
  - **Depends on:** 6
  - **Evidence:** `/api/chat` `message` is the ChatPanel payload: review-only title, 5 validated bullets, compiler SPL (37d / 7d split / streamstats / mvfilter / 1h / outputs), mappings, “No query was executed.” No MITRE/remediation/investigation steps. Browser tab is `http://127.0.0.1:3013/chat` (login wall; credentials not dumped). READY_FOR_HUMAN_UI_CHECK=YES. READY_TO_MERGE=NO. P11 not started. Container `mcp_global_execution_enabled=false`.

- [x] **7a** — Pattern-adaptation transport/response contract
  - **Do:** For vetted-pattern authoring only, constrain generation to `{status, candidate_spl}` (`additionalProperties: false`). Keep the full `SPL_ADVISORY_JSON_SCHEMA` for non-pattern advisory. Compact the enabled-pattern few-shot envelope to those keys. Change the pattern-path user closer to ask only those keys. If `finish_reason=length` but JSON still parses with a non-empty `candidate_spl`, do not discard at transport; truncated/incomplete JSON still fails closed. Compiler rescue stays. Do not raise max_tokens in this item. Do not start P2.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_spl_pattern_guided_authoring.py -k 'compact_schema or complete_length or truncated_length or compact_prompt' app/tests/test_llm_spl_fallback.py::test_fallback_rejects_length_finish_reason_before_validation -q`
  - **Depends on:** 7
  - **Evidence:** Compact `{status, candidate_spl}` schema (`additionalProperties: false`) on vetted-pattern path only. Length+complete JSON accepted; truncated JSON still `finish_reason_length`. Compact few-shot envelope + compact user closer. Hydrate assumptions/required_fields after parse for the existing adapter. Verify: **4 passed**. Broader authoring slice **102 passed**. Full backend **7333 passed**. Did not raise max_tokens.

- [x] **7b** — Live P1 LLM candidate through preprocessor/validator/repair vs compiler
  - **Do:** Two `/api/chat` P1 calls with MCP off. Require a complete `raw_llm_spl`. Then preprocessor → validator → at most one repair. Compare topology to `compile_intent_spec_to_spl` (not byte-identical). Compiler remains the product safety floor if LLM still fails. Do not start P2 unless LLM path yields a complete raw candidate.
  - **Verify:** Both live calls: `raw_llm_spl` non-empty; `authoring_source` in {LLM_PATTERN_PRIMARY, LLM_PATTERN_NORMALIZED, LLM_PATTERN_REPAIR} **or** explicit `LEGACY_COMPILER_RESCUE` if LLM still truncated. Record preprocessor changes, validator losses, repair used. `execution_eligible=false`, `normalized_spl=null`, MCP=0.
  - **Depends on:** 7a
  - **Evidence:** Transport PASS. Both live calls: `raw_llm_spl` ~855 chars, complete first_seen topology tokens. Preprocessor: `time_bound_injected` only. Validator initial: `first_seen_subject_accumulation_missing` (`values(baseline_host)` vs required `values(baseline_object)`) + `disallowed_index`. Repair attempted+completed, not used. Final `authoring_source=LEGACY_COMPILER_RESCUE`. Safety: execution_eligible=false, normalized_spl=null, MCP=0. **P2 not started** — LLM pattern success still false.

- [x] **7c** — P1 final validator/preprocessor correction (one iteration)
  - **Do:** Semantic first_seen accumulation (baseline-period object field + streamstats values of that field by subject; aliases OK). Extra partition keys (src_ip on user-only first_seen) remain a loss with the specified repair sentence. Detect late `bin` after stats as `required_temporal_grain_unreachable` with the specified repair sentence. Preprocessor: infix `field LIKE "admin-*"` → `like(user_norm,"admin-%")` only for contract prefix actors; record `actor_prefix_wildcard_normalized`. Do not drop src_ip from streamstats; do not reorder bin/stats. Compiler rescue unchanged.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_spl_pattern_guided_authoring.py -q`
  - **Depends on:** 7b
  - **Evidence:** `../.venv/bin/python -m pytest app/tests/test_spl_pattern_guided_authoring.py` → **21 passed**. Broader fidelity slice (`test_spl_pattern_guided_authoring.py` + `test_spl_authoring_fidelity_loop.py` + `test_spl_intent_spec_and_fidelity.py` + `test_review_only_spl_postprocessor.py`) → **82 passed**. Captured live P1 SPL no longer false-positives on `values(baseline_host)`; extra `src_ip_norm` partition and late `bin` still fail; infix `LIKE "admin-*"` records `actor_prefix_wildcard_normalized`. Host `python3` lacks `pydantic_settings`; used repo `.venv`.

- [x] **7d** — Live P1 twice; LLM pattern gate (not compiler)
  - **Do:** Two `/api/chat` P1 calls. Require authoring_source in {LLM_PATTERN_PRIMARY, LLM_PATTERN_NORMALIZED, LLM_PATTERN_REPAIR}. Capture raw/preprocessor/validator-before/repair/validator-after. If still LEGACY_COMPILER_RESCUE, STOP P1 pattern work. Do not start P2 until this passes.
  - **Verify:** Both calls: LLM pattern source, fidelity pass, execution_eligible=false, normalized_spl=null, MCP=0. Invariants: 37d, 7d, 30d baseline, EventCode=4624, prefix LIKE, streamstats by user only, mvfilter ==, bin before stats, outputs.
  - **Depends on:** 7c
  - **Evidence:** **P1 PATTERN CLOSED.** LLM gate FAIL (`LEGACY_COMPILER_RESCUE` both calls). Product P1 PASS via compiler. User 2026-09-01 authorized P2 as an independent family with product pass allowed via rescue. Do not reopen P1.

- [x] **8a** — Vet sequence burst-then-follow topology in the existing compiler
  - **Do:** In `compile_intent_spec_to_spl` sequence path: prove EVENT_A burst inside WINDOW_A (snapshot count/first/last on EVENT_A), carry qualified burst forward, then match later EVENT_B by subject+src_ip after last EVENT_A within FOLLOW_WINDOW. Destination host from EVENT_B only. Do not count EVENT_A in a window that ends at EVENT_B. Not a second compiler.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_spl_semantic_v2_compiler.py::test_sequence_threshold_and_process_parent_child_compile app/tests/test_spl_authoring_fidelity_loop.py -k 'p2 or sequence' -q`
  - **Depends on:** 7d
  - **Evidence:** Compiler emits `time_window=15m` count on EVENT_A, then `streamstats last(...)` burst snapshot, then EVENT_B with `_time>burst_last_epoch` and `<=600`. Verify: **6 passed**. Host `python3` lacks deps; used repo `.venv`.

- [x] **8b** — Generic sequence pattern + mutants A–J
  - **Do:** Enable `_AUTHORING_FEW_SHOTS["sequence"]` with generic EVENT_A/EVENT_B topology (no EventCode 4625/4624). Validator rejects: implicit AND; host over-correlation; `>=` vs `>`; success before burst; 601s gap; missing first_failure / success_time; failure-only; success-only; burst not proven in WINDOW_A. Host repair sentence: correlate by user and source IP only; dest host is EVENT_B output.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_spl_pattern_guided_authoring.py -k 'sequence or p2' -q`
  - **Depends on:** 8a
  - **Evidence:** Sequence pattern enabled; body has no 4624/4625. Mutants A–J fail as specified. Verify: **4 passed**. Broader authoring slice **102 passed**.

- [x] **8c** — Thin preprocessor stays non-semantic for sequence
  - **Do:** Confirm preprocessor does not drop correlation keys, reorder sequence stages, invent predicates, or move dest host into `by`. Compact pattern JSON transport reused.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_spl_pattern_guided_authoring.py -k 'sequence or p2 or preprocessor' -q`
  - **Depends on:** 8b
  - **Evidence:** `test_p2_preprocessor_does_not_rewrite_sequence_semantics` in the same slice: streamstats `by` keeps user+src_ip, no host, `last()` and `_time>burst_last_epoch` retained. Compact `{status, candidate_spl}` still used for vetted patterns. Broader slice **102 passed**.

- [x] **8d** — Live P2 /api/chat twice (MCP off)
  - **Do:** Two live P2 calls. Capture raw LLM, preprocessor, losses, repair, final LLM or compiler rescue, authoring_source, message. Max two LLM correction iterations. Product may PASS via LEGACY_COMPILER_RESCUE.
  - **Verify:** Both calls same semantic product; review-only; execution_eligible=false; approved=false; normalized_spl=null; MCP=0. Record P2_LLM_PATTERN_PASS and P2_PRODUCT_PASS separately.
  - **Depends on:** 8c
  - **Evidence:** Two `/api/chat` calls identical. Pattern `sequence` selected. RAW_LLM complete (~1068 chars, `finish_reason=stop`) but invented `join` + failure-only retrieve + missing `sort 0 + _time` (Q11 hard_fail). Quality abort: preprocessor/validator/repair not reached on LLM SPL. Product SPL = `LEGACY_COMPILER_RESCUE` burst-then-follow (union, `time_window=15m`, `last()` snapshot, `_time>burst_last_epoch` `<=600`, `by user_norm, src_ip_norm`, `latest(host_norm)`). Renderer describes union+burst+later success. Safety: `execution_eligible=false`, `approved=false`, `normalized_spl=null`, MCP skipped/`result_count=0`. **P2_LLM_PATTERN_PASS=NO**. **P2_PRODUCT_PASS=YES**. No LLM correction iteration spent (join is a forbidden semantic rewrite; compiler floor is honest).

- [x] **8e** — P2 gates then P3-allowed
  - **Do:** If P2_PRODUCT_PASS: targeted + full backend pytest, freeze `--check`, RACES isolation, invariant review. P3 may start even if LLM pattern failed. Do not merge. Do not start P11.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest -q`; `python3 scripts/freeze_execution_baseline.py --check`
  - **Depends on:** 8d
  - **Evidence:** Targeted `-k 'sequence or p2'` **6 passed**. Broader authoring slice **122 passed**. Full backend pytest (repo `.venv`): **7346 passed, 45 skipped, 6 xfailed**. `scripts/freeze_execution_baseline.py --check` → **protected artifacts unchanged (15 checked)**. RACES `test_live_path_untouched_by_ec.py` **8 passed**. Invariant PASS: no `call_tool`/MCP sites; `execution_eligible=False` on authoring path; demo/conftest untouched; no new flags; protected `architecture.md`/`pipeline.py`/`spl_validator.py`/`policy.py` empty vs `207e7409`. **P3_ALLOWED_TO_START=YES**. READY_TO_MERGE=NO. P11 not started. Live MCP off.

- [x] **9a** — Parent/child validator by semantic role + mutants A–H
  - **Do:** Validator reasons by CHILD_PROCESS / PARENT_PROCESS / COMMAND_LINE roles (mapped fields allowed). Reject inverted parent/child; powershell only in command_line; missing parent; join/unrelated branches; stats then fields of dropped columns; missing event_count/first_seen/last_seen; like()/eval in base search. Do not weaken checks. Analyst-grade repair sentences.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. ../.venv/bin/python3 -m pytest app/tests/test_spl_pattern_guided_authoring.py -k 'p3 or parent_child' -q`
  - **Depends on:** 8e
  - **Evidence:** Roles via Image/ParentImage/command_line haystacks. Mutants A–H reject with parent_child_inverted, child_process_not_proven, parent_process_missing, parent_child_relationship_missing, field_lineage_missing, output_missing:event_count, output_missing:first_seen/last_seen, command_context_invalid. Compiler P3 still fidelity-pass. Verify: **2 passed**.

- [x] **9b** — Enable generic parent_child pattern
  - **Do:** Enable `_AUTHORING_FEW_SHOTS["parent_child"]` with generic child/parent topology (no powershell/winword/excel/24h). Compact `{status, candidate_spl}` transport. Same-event parent AND child after role normalization, then stats by host+user preserving outputs.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. ../.venv/bin/python3 -m pytest app/tests/test_spl_pattern_guided_authoring.py -k 'p3 or parent_child' -q`
  - **Depends on:** 9a
  - **Evidence:** `pattern_enabled=True`, generic `child.exe`/`parent_a.exe`/`parent_b.exe`/`-12h`. Spec `analysis_shape=parent_child` so selection works. Adaptation block is pattern-specific (no first_seen streamstats order). Verify: **5 passed**.

- [x] **9c** — Thin preprocessor + parent_child synthesis
  - **Do:** Preprocessor must not swap parent/child, move child into command_line, or invent relationship/aggregation. Renderer describes same-event parent→child over 24h, grouped by host and user. No 4624-only bullet.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. ../.venv/bin/python3 -m pytest app/tests/test_spl_pattern_guided_authoring.py -k 'p3 or parent_child or preprocessor' -q`
  - **Depends on:** 9b
  - **Evidence:** Preprocessor leaves inverted Image/ParentImage inverted (`parent_child_inverted` still fires). Renderer: same-event powershell launched by winword/excel, grouped by host and user, no 4624 bullet. Verify: **8 passed**.

- [x] **9d** — Live P3 /api/chat twice (MCP off)
  - **Do:** Two live P3 calls. Capture raw/preprocessor/losses/repair/authoring_source/message. Max two LLM correction iterations. Product may PASS via LEGACY_COMPILER_RESCUE.
  - **Verify:** Both calls identical semantic product; review-only; execution_eligible=false; approved=false; normalized_spl=null; MCP=0. Record P3_LLM_PATTERN_PASS and P3_PRODUCT_PASS separately.
  - **Depends on:** 9c
  - **Evidence:** Two `/api/chat` calls identical. Pattern `parent_child` selected. RAW_LLM complete (`finish_reason=stop`, ~897 chars) with same-event powershell child + winword/excel parent + stats outputs, but quality Q02 hard-fail on JSON `\n` as “Windows path backslash”; preprocessor/validator/repair not reached. Product SPL = `LEGACY_COMPILER_RESCUE` (Image/ParentImage likes, 24h, host+user stats, parent/child/command_line, earliest/latest, event_count). Renderer: same-event parent→child, no 4624/MITRE/investigation. Safety: `execution_eligible=false`, `approved=false`, `normalized_spl=null`, MCP skipped/0. **P3_LLM_PATTERN_PASS=NO**. **P3_PRODUCT_PASS=YES**. No LLM correction iteration spent.

- [x] **9e** — P3 targeted gates then P4-allowed
  - **Do:** If P3_PRODUCT_PASS: targeted authoring tests. P4 may start even if LLM pattern failed. Full pytest waits for P4 phase completion. Do not merge. Do not start P11.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. ../.venv/bin/python3 -m pytest app/tests/test_spl_pattern_guided_authoring.py app/tests/test_spl_semantic_v2_compiler.py -q`
  - **Depends on:** 9d
  - **Evidence:** `pytest app/tests/test_spl_pattern_guided_authoring.py app/tests/test_spl_semantic_v2_compiler.py -q` → **45 passed**. **P4_ALLOWED_TO_START=YES**. READY_TO_MERGE=NO. P11 not started.

- [x] **10a** — P4 first_seen mutants A–H on the same pattern
  - **Do:** Reuse pattern_id=first_seen. Reject: 24h-only (baseline_unreachable); 14d including observation (observation_baseline_overlap); streamstats by user (first_seen_subject_wrong); domain as new_host (output_entity_mismatch); regex membership; missing connection_count; missing first_seen; src_ip lost after stats. Do not reopen P1. No new first_seen algorithm.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. ../.venv/bin/python3 -m pytest app/tests/test_spl_pattern_guided_authoring.py -k 'p4 or first_seen' -q`
  - **Depends on:** 9e
  - **Evidence:** Same `pattern_id=first_seen` object as P1. Spec: subject=host, object=domain, 24h/14d/15d. Compiler fidelity-pass. Mutants A–H reject with baseline_unreachable, observation_baseline_overlap, first_seen_subject_wrong, output_entity_mismatch, regex_membership, output_missing:connection_count, output_missing:first_seen, output_missing:src_ip. Verify: **6 passed**.

- [x] **10b** — Live P4 /api/chat twice (MCP off)
  - **Do:** Two live P4 calls with the same first_seen pattern. Capture raw/preprocessor/losses/repair/compiler rescue/authoring_source. Max two LLM correction iterations.
  - **Verify:** Both calls identical semantic product; 15d/24h/14d host→domain; review-only; execution_eligible=false; approved=false; normalized_spl=null; MCP=0. Record P4_LLM_PATTERN_PASS, P4_PRODUCT_PASS, FIRST_SEEN_PATTERN_GENERALIZED.
  - **Depends on:** 10a
  - **Evidence:** Two `/api/chat` calls identical. Pattern `first_seen` selected (same P1 topology). RAW_LLM complete first-seen-shaped SPL but used `-1d` observation, `streamstats ... by host_norm, src_ip_norm`, `baseline_domain`, `count` not `connection_count`, `first_seen=min(_time)` after stats. Repair attempted; still invalid. Product SPL = `LEGACY_COMPILER_RESCUE` (15d envelope, 24h observation, host-only streamstats, exact mvfilter, domain not new_host, src_ip + first_seen + connection_count). Renderer: 24h+preceding 14d same host, domain absent from baseline. Safety: `execution_eligible=false`, `approved=false`, `normalized_spl=null`, MCP skipped/0. **P4_LLM_PATTERN_PASS=NO**. **P4_PRODUCT_PASS=YES**. **FIRST_SEEN_PATTERN_GENERALIZED=YES**. No extra LLM correction iteration.

- [x] **10c** — P3/P4 phase completion gates
  - **Do:** Full backend pytest, RACES, freeze `--check`, SPL authority freeze, invariant review. Protected zero-diff vs `207e7409` for architecture.md / pipeline.py / spl_validator.py / policy.py.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. ../.venv/bin/python3 -m pytest -q`; `python3 scripts/freeze_execution_baseline.py --check`
  - **Depends on:** 10b
  - **Evidence:** Full backend pytest **7353 passed, 45 skipped, 6 xfailed, 0 failed**. Freeze `--check` **protected artifacts unchanged (15 checked)**. SPL authority freeze **OK authority-identical rows=49**. RACES G1 + live-path + SPL freeze tests **18 passed**. Protected diffs vs `207e7409` empty for architecture.md / pipeline.py / spl_validator.py / policy.py. Invariant PASS: no new `call_tool`/MCP sites; demo/conftest/config.py untouched; no new flags; authoring remains review-only `execution_eligible=false`. READY_TO_MERGE=NO. P11 not started. Live MCP off.

- [x] **11a** — P1/P4 exact-membership primitive → documented mvmap
  - **Do:** Replace only `mvfilter(mv == scalar)` in `compile_intent_spec_to_spl` first_seen and the enabled `first_seen` few-shot with Splunk-documented `mvmap(baseline_objects, if(baseline_objects==<object>,1,0))` + `seen_before=coalesce(max(exact_matches),0)` + `where seen_before=0`. Do not change retrieve/period/streamstats/observation/stats topology.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. ../.venv/bin/python3 -m pytest app/tests/test_spl_pattern_guided_authoring.py app/tests/test_spl_authoring_fidelity_loop.py -k 'first_seen or p1 or p4 or mvmap or membership' -q`
  - **Depends on:** 10c
  - **Evidence:** Compiler `_compile_first_seen` emits `exact_multivalue_absence_commands` (`mvmap` + `max(exact_matches)` + `where seen_before=0`). Few-shot payload matches. Retrieve/period/streamstats/observation/stats unchanged. Verify `-k 'first_seen or p1 or p4 or mvmap or membership or mvfilter'` → **22 passed**. Broader authoring/compiler/fidelity files → **87 passed**.

- [x] **11b** — Reject mvfilter(fieldA == fieldB); accept mvmap form
  - **Do:** In `validate_semantic_fidelity`, treat cross-field `mvfilter(A == B)` as invalid (`mvfilter_cross_field` / not exact membership). Pass only the mvmap + max(exact_matches) + seen_before=0 primitive. mvfind stays regex_membership.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. ../.venv/bin/python3 -m pytest app/tests/test_spl_pattern_guided_authoring.py app/tests/test_spl_authoring_fidelity_loop.py -k 'first_seen or p1 or p4 or mvmap or membership or mvfilter' -q`
  - **Depends on:** 11a
  - **Evidence:** Cross-field `mvfilter(A == B)` is `mvfilter_cross_field` + `exact_membership_missing` even if mvmap is also present. Compiled P1/P4 mvmap form fidelity-pass. mvfind still `regex_membership`. Same 22-test slice **passed**.

- [x] **11c** — Full regression and protected freezes
  - **Do:** Full backend pytest, RACES, freeze `--check`, SPL authority freeze. Protected zero-diff vs `207e7409` for architecture.md / pipeline.py / spl_validator.py / policy.py.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. ../.venv/bin/python3 -m pytest -q`; `python3 scripts/freeze_execution_baseline.py --check`
  - **Depends on:** 11b
  - **Evidence:** Full backend pytest **7355 passed, 45 skipped, 6 xfailed, 0 failed**. Freeze `--check` **protected artifacts unchanged (15 checked)**. SPL authority freeze **OK authority-identical rows=49**. RACES G1 + live-path + SPL freeze tests **18 passed**. Protected diffs vs `207e7409` empty for architecture.md / pipeline.py / spl_validator.py / policy.py. Invariant PASS: no new `call_tool`/MCP sites; demo/conftest/config.py untouched; no new flags; authoring remains review-only `execution_eligible=false`. READY_TO_MERGE=NO. P11 not started. Live MCP off.

- [ ] **11d** — Commit clean SHA
  - **Do:** One commit of the SPL-authoring phase including the mvmap primitive. Do not merge yet.
  - **Verify:** `git rev-parse HEAD`; `git status --short`
  - **Depends on:** 11c
  - **Evidence:** _(filled when done)_

- [ ] **11e** — Rebuild SHA and live P1–P4 twice
  - **Do:** Rebuild/restart backend at the commit SHA. Run P1–P4 twice through `/api/chat` with MCP off. Confirm compiler SPL uses mvmap, not mvfilter(A==B). Human UI check at 3013/chat remains required before merge/P11.
  - **Verify:** Two calls per family; review-only; execution_eligible=false; approved=false; normalized_spl=null; MCP=0; product SPL contains `mvmap(baseline_objects` and `seen_before=0`; no `mvfilter(.*==`.
  - **Depends on:** 11d
  - **Evidence:** _(filled when done)_

## Verification gaps (flag before coding)

Live item 6 requires the running Docker `/api/chat` with MCP off. Host pytest is `llm_mode=mock`; live authoring is the container.

## Drift log

- BASE_SHA=`207e7409250e19095985d2771f48576f6c944305`. Worktree clean at pin.
- Existing executable store is `_AUTHORING_FEW_SHOTS` in `llm_fallback.py` (not a new repo). `examples.py` remains metadata catalog.
- Current first_seen few-shot uses `baseline_count=0` stats, which fails `exact_membership` in `validate_semantic_fidelity`. Pattern body must match compiler topology (`streamstats values(baseline_object)` + `mvfilter(==)`).
- Did **not** extend `llm/policy/examples.py` SEMANTIC_SHAPES with FIRST_SEEN — P8 frozen `spl_advisory_generator` hash.
- Live P1: product PASS via `LEGACY_COMPILER_RESCUE`; instruct `finish_reason=length` after two prompt-compact iterations. **P2/P3/P4 not started.**
- Follow-on (authorized): keep compiler rescue; fix only the pattern-adaptation json_schema / response closer / few-shot envelope until a complete raw LLM candidate exists. Do not raise max_tokens in 7a.
- 7a/7b/7c/7d: compact schema produced complete `raw_llm_spl` on live P1. Final LLM pattern gate FAIL. Product P1 PASS via `LEGACY_COMPILER_RESCUE`. **P1 pattern work closed; do not reopen.**
- 2026-09-01 user override: start P2 as independent sequence family. Product PASS may use compiler rescue. P3 may start after P2 product PASS even if `P2_LLM_PATTERN_PASS=NO`.
- Live P2 (8d): product PASS via `LEGACY_COMPILER_RESCUE`; instruct emitted complete join-based SPL that quality-failed Q11. **P2_LLM_PATTERN_PASS=NO**. **P2_PRODUCT_PASS=YES**. P3 allowed after 8e.
- 8e gates green. P3 checklist split into 9a–9e after user 2026-09-01 P3→P4 loop. Validator role-based mutants A–H required before enabling the pattern.
- 9b/9c: `parent_child` pattern enabled (generic topology). Spec analysis_shape override from process_constraints. Renderer + preprocessor pins in place. Live P3 next.
- Live P3 (9d): product PASS via `LEGACY_COMPILER_RESCUE`; instruct emitted complete parent/child SPL that quality-failed Q02 on JSON `\n`. **P3_LLM_PATTERN_PASS=NO**. **P3_PRODUCT_PASS=YES**.
- Live P4 (10b): same `first_seen` pattern generalized host→domain / 24h+14d=15d. LLM draft incomplete/wrong subject keys; repair failed; product PASS via compiler rescue. **P4_LLM_PATTERN_PASS=NO**. **P4_PRODUCT_PASS=YES**. **FIRST_SEEN_PATTERN_GENERALIZED=YES**.
- 10c gates green. READY_TO_MERGE=NO. P11 not started. Live MCP off.
- 2026-09-01: Splunk documents that `mvfilter()` predicates may reference only one field. Cross-field `mvfilter(mv == scalar)` is not proven-valid SPL. Replace only the P1/P4 exact-membership primitive with documented `mvmap` + `max(exact_matches)` + `seen_before=0`. Surrounding first-seen topology unchanged. 11a–11c green; commit then live 11e before merge/P11.
