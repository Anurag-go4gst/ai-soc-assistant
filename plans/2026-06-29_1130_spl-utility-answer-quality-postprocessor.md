# SPL Utility Answer Quality + Context-Aware Postprocessor (PR56 follow-up)

**Status:** In Progress (branch `fix/spl-utility-answer-quality-postprocessor`)
**Date:** 2026-06-29
**Baseline:** PR #56 (merged `9eb4880`) — explicit SPL authoring route fix, `app/chat/spl_authoring_intent.py`, `universal_spl_phrasing()`, `source_profile_required_for_authoring()=false` for universal asks, lighter `universal_spl_authoring_review_only` HIL, `/chat/stream` trace lifecycle.

Scoped follow-up: **answer quality + SPL hygiene + traceable postprocessing only. Do NOT reopen routing.**

---

## Review verdict on the loop prompt

Corrected prompt is **sound** — fixes the 6 bugs found in the first draft:
1. ~~phantom postprocessor~~ → now says *build new* `app/spl/review_only_spl_postprocessor.py`.
2. ~~redo PR56~~ → now references PR56 as baseline.
3. ~~duplicate weekend path~~ → now says *reconcile existing skeleton in `draft_preview.py`*.
4. ~~LLM-preservation untestable~~ → now mock/fixture tested, live LLM not a success condition.
5. ~~live LLM hang~~ → Phase 12 wraps `ask_chat.sh` in `timeout 180`.
6. ~~strip shared authority constants~~ → explicit guard: don't touch `AUTHORITY_HIERARCHY_RULES`/`REVIEW_ONLY_SAFETY_RULES`.

**One nit:** module is `backend/app/chat/spl_authoring_intent.py` (not `app/spl/`). Prompt Phase 1/2 mislabels the dir.

**Repo facts confirmed before coding:**
- Weekend skeleton lives in `backend/app/spl/draft_preview.py` family `universal_timestamp_spl` (was `index=*`, `earliest=-7d`, `sort 0 -_time` before filter, short fields `hour`/`dow`).
- `match_detection_family()` (`draft_preview.py:2452`) routes weekend/universal phrasing → `universal_timestamp_spl`.
- `pipeline.py` already special-cases `universal_timestamp_spl` (lines ~4240, ~5581–5626): lab-draft labels, `review_only_universal_spl` warning, `universal_spl_authoring_review_only` review reason, suppresses placeholder/source-profile clarification.
- `_universal_spl_authoring_review()` HIL (`pipeline.py:5580`) already lighter than generic SPL clarification.
- Existing test `test_explicit_spl_authoring.py::test_universal_spl_weekend_block_routes_spl_generation` asserts `'strftime(_time,"%w")'` + `'dow IN ("0","6")'` → **must update** for reconciled field names (same file, not a dup path).
- `app/spl/source_profile_resolver.py` holds `extract_placeholder_slots` / `substitute_placeholders` + index-stem alias logic → reuse for Phase 4 index resolution.

---

## WHAT IS DONE (this session)

Branch `fix/spl-utility-answer-quality-postprocessor` off `master`.

**Phase 3 — skeleton reconciled (DONE).** `draft_preview.py` `universal_timestamp_spl.draft_spl` rewritten:
```spl
search index=<your_index> earliest=-24h latest=now
| eval hour_of_day=strftime(_time,"%H")
| eval day_of_week_num=strftime(_time,"%w")
| eval day_of_week=strftime(_time,"%A")
| where day_of_week_num IN ("0","6")
| table _time hour_of_day day_of_week sourcetype host
| head 100
```
- `index=*` → `<your_index>` placeholder
- `earliest=-7d` → `earliest=-24h latest=now`
- removed `sort 0 -_time` (was expensive cmd before filter)
- added optional `%A` display eval `day_of_week`
- full field names `hour_of_day` / `day_of_week_num`
- assumptions text updated to match.

> NOTE: the `search ` prefix is the draft_preview convention; renderer strips/normalizes. Keep it.

---

## WHAT IS LEFT (to complete next session)

Ordered, with risk:

### Phase 10a — fix existing test (LOW risk, do FIRST)
`test_explicit_spl_authoring.py::test_universal_spl_weekend_block_routes_spl_generation`
change assertions:
- keep `'strftime(_time,"%H")'`, `'strftime(_time,"%w")'`
- replace `'dow IN ("0","6")'` → `'day_of_week_num IN ("0","6")'`
- add `'index=<your_index>'`, `'earliest=-24h latest=now'`, assert `'sort 0'` NOT in spl, assert `'strftime(_time,"%A")'` in spl.

### Phase 2/4/5/6/7 — build postprocessor (MED risk)
New `backend/app/spl/review_only_spl_postprocessor.py`:
`normalize_review_only_spl(raw_spl: str, context: dict) -> NormalizedSplResult`
- Scoped to review-only utility/lab drafts ONLY (gate on `is_explicit_spl_authoring`/`is_universal_spl`). Do NOT touch governed templates.
- context keys: `is_explicit_spl_authoring, is_universal_spl, is_template_free, user_explicit_index, coe_environment_index, source_profile_index, target_log_family, user_explicit_time_window, llm_generated, deterministic_generated, execution_authorized`.
- returns `normalized_spl, trace, warnings`.
- **Index resolution (Phase 4):** order user_explicit → coe_environment → source_profile_resolver single approved → `<your_index>` → wildcard only if intentionally allowed + tight time. Never accept index just because LLM invented it. `wineventlog` only if Windows wording/COE; `scada_perf` only if SCADA/OT; ASA index only if firewall. Trace: `original_index, resolved_index, index_resolution_source, index_rewrite_applied, index_rewrite_reason, raw_llm_index_dropped, raw_llm_index_dropped_reason`.
- **Lookback (Phase 5):** placeholder/wildcard index → default `-24h latest=now`; shrink `-7d`+ → `-24h` unless user-explicit; preserve user-explicit + `broad_scope_warning`. Trace: `original_earliest, final_earliest, lookback_added, lookback_rewrite_applied, lookback_rewrite_reason, broad_scope_warning`.
- **Command hygiene (Phase 6):** remove unneeded `sort 0 -_time`; respect deps (`where hour_of_day` after `eval hour_of_day`, etc.); warn instead of risky reorder. Trace: `command_reorder_applied, removed_expensive_commands, blocked_reorder_reasons, dependency_preserved`.
- **Locale (Phase 7):** `%w` for filter logic; keep `%A` display; normalize LLM `%A`+Sat/Sun filter → `%w`; don't blind-replace all `%A`. Trace: `locale_normalization_applied, original_day_filter, normalized_day_filter, display_field_preserved`.
- **Wire (not dead code):** route the deterministic universal skeleton emission through it (idempotent on already-clean skeleton) at the `universal_timestamp_spl` draft build point; in mocked-LLM tests feed an LLM draft.

### Phase 8 — LLM boundary trace (MED)
Trace fields: `llm_advisory_invoked, llm_advisory_used, llm_spl_draft_used, llm_spl_draft_normalized, llm_advisory_dropped_reason, deterministic_postprocessor_applied, final_spl_authority`. Live LLM NOT required. Do NOT strip `AUTHORITY_HIERARCHY_RULES`/`REVIEW_ONLY_SAFETY_RULES`; any prompt change narrow to SPL-draft generation only.

### Phase 9 — renderer concision (HIGH risk — cross-cutting, do LAST, governance is safety net)
`backend/app/chat/review_only_spl_renderer.py`. Gate strictly on universal/template-free authoring (`universal_spl_phrasing()` / `explicit_spl_authoring` / `review_required_reason == universal_spl_authoring_review_only`). Do NOT change analytics/q046/T2 SCADA/Cisco/Winevent/investigation rendering.
For this mode only, main answer =
1. `Review-only universal SPL draft. This was not executed.`
2. SPL block immediately.
3. Short explanation (replace `<your_index>`; `%H` hour; `%w` weekends; `%A` display only; adjust time window).
Hide from main answer: severity, long SOC checklist, compromise caveat, source-profile-required warning, template-unavailable headline, "what to look for". Keep in trace/debug.
**If governance regresses → revert Phase 9, keep skeleton+postprocessor.**

### Phase 10 — tests (the 18 listed in prompt). Phase 11/12 gates. Phase 13 PR.

---

## Gates (Phase 11/12)
```bash
git diff --check
cd backend && PYTHONPATH=../backend:.. python3 -m pytest \
  app/tests/test_explicit_spl_authoring.py \
  app/tests/test_post_pr47_live_probes.py \
  app/tests/test_route_policy_smoke_fix.py \
  app/tests/test_t1_spl_native_routing.py \
  app/tests/test_spl_query_fidelity.py \
  app/tests/test_canonical_handoff_e2e_probes.py -q
timeout 300 bash -lc 'cd backend && PYTHONPATH=../backend:.. python3 -m pytest -q'
timeout 300 ./scripts/run_stage3_governance_regression.sh
PYTHONPATH=backend:. python3 scripts/eval_sentinel.py --check
git checkout -- docs/evals/ || true
git checkout -- .claude/settings.local.json || true
# live (timeout-wrapped):
timeout 180 scripts/ask_chat.sh "Without using any specific company templates, write a standard, universal SPL block that extracts the hour of the day and day of the week from an event timestamp, filtering only for weekend events."
```

## PR (Phase 13)
Branch `fix/spl-utility-answer-quality-postprocessor`; title/commit **"Improve SPL utility answer quality with context-aware postprocessing"**.

## Constraints (hard)
No live MCP, no execution, no promotion `--apply`, no RunContract/FinalEvidenceGate weakening, no docs/evals or rollout-snapshot commits, no new flags, no global authority-constant edits, no second weekend path, live LLM never a success condition.

---

## APPENDIX — corrected loop prompt (verbatim, for re-run)

> Paste back into `/loop` or a fresh agent to resume. Adjust Phase 1/2 path note: module is `app/chat/spl_authoring_intent.py`.

```
You will run the PR56 Follow-Up: SPL Utility Quality + Context-Aware Postprocessor loop.

TASK: Improve explicit SPL utility answer quality after PR #56 without reopening routing architecture. Scoped follow-up to PR #56.

Do not redo PR #56. Do not add a second competing weekend SPL path. Do not strip/weaken global LLM authority/safety prompt constants. Do not make live LLM usage a required success condition. Do not fix LSASS. Do not change promotion status. Do not run promotion --apply. Do not enable live Splunk MCP. Do not execute candidate SPL. Do not weaken RunContract/FinalEvidenceGate. Do not commit docs/evals drift. Do not commit rollout snapshots.

BASELINE — PR #56 shipped: explicit SPL authoring route fix; spl_authoring_intent.py; universal_spl_phrasing(); source_profile_required_for_authoring()=false for universal/template-free; clarification override suppression; /chat/stream admission row/trace-id/LangGraph trace closure; weekend route reaches spl_generation; weekend skeleton in draft_preview.py used index=*, earliest=-7d, strftime %w. Do not re-solve routing. This loop = answer quality, SPL hygiene, traceable postprocessing.

TARGET SPL for weekend utility:
index=<your_index> earliest=-24h latest=now
| eval hour_of_day=strftime(_time,"%H")
| eval day_of_week_num=strftime(_time,"%w")
| eval day_of_week=strftime(_time,"%A")
| where day_of_week_num IN ("0","6")
| table _time hour_of_day day_of_week sourcetype host
| head 100
%w filters weekends (0=Sun,6=Sat); %A display only; <your_index> placeholder only when no user/COE/source-profile index; never invent index; no sort 0 before filter; no inline // comments; no execution/findings claims.

PHASE 1 Inspect PR56 baseline (files: app/chat/spl_authoring_intent.py, app/spl/draft_preview.py, app/chat/query_signals.py, app/chat/intent_classifier.py, app/routing/route_adjudication.py, app/chat/pipeline.py, app/chat/review_only_spl_renderer.py, app/llm/prompts.py, app/llm/sidecar_clients.py, app/tests/test_explicit_spl_authoring.py). Answer: where skeleton generated; does PR56 set source_profile_required=false for universal; which renderer makes SOC-heavy answer; any LLM SPL draft path in tests; which tests cover deterministic/LLM-rescue/timeout/conflict; safest postprocessor insertion point; trace structure for postprocessor trace. No new paths until inspection done.

PHASE 2 Build narrow context-aware postprocessor — new app/spl/review_only_spl_postprocessor.py: normalize_review_only_spl(raw_spl, context) -> NormalizedSplResult. Scoped to review-only utility/lab drafts, not all governed templates. Context: is_explicit_spl_authoring, is_universal_spl, is_template_free, user_explicit_index, coe_environment_index, source_profile_index, target_log_family, user_explicit_time_window, llm_generated, deterministic_generated, execution_authorized. Return normalized_spl, trace, warnings. No global default index.

PHASE 3 Reconcile existing weekend skeleton in draft_preview.py (no second generator): index=<your_index> when no user/COE/source-profile index; earliest=-24h latest=now; %H; %w numeric filter; optional %A display; no sort 0 before filter; no source-profile clarification for universal/template-free.

PHASE 4 Index resolution rule: never invent; never blindly placeholder; resolve from user/COE else placeholder. Order: 1 user explicit index, 2 trusted COE Environment KB index, 3 source-profile resolver single approved index, 4 placeholder <your_index>, 5 wildcard only when intentionally allowed + tight time. wineventlog only if Windows wording/COE; scada_perf only if SCADA/OT; ASA index only if ASA/firewall; preserve explicit safe user index; if user asks index=* preserve intent + tight time + broad-scope warning. Trace: original_index, resolved_index, index_resolution_source, index_rewrite_applied, index_rewrite_reason, raw_llm_index_dropped, raw_llm_index_dropped_reason.

PHASE 5 Lookback hygiene: universal/template-free + placeholder/wildcard index → default earliest=-24h latest=now; shrink -7d+ → -24h when not user-explicit; preserve user-explicit long lookback + broad-scope warning. Trace: original_earliest, final_earliest, lookback_added, lookback_rewrite_applied, lookback_rewrite_reason, broad_scope_warning.

PHASE 6 Dependency-aware command hygiene (no naive line swap): remove unnecessary sort 0 -_time from universal utility drafts; keep where hour_of_day after eval hour_of_day, where day_of_week_num after eval day_of_week_num; no reorder of complex commands unless dep clear; warn instead of risky rewrite. Trace: command_reorder_applied, removed_expensive_commands, blocked_reorder_reasons, dependency_preserved.

PHASE 7 Locale-safe: %w for filter logic; optionally keep %A display; normalize raw LLM %A + Sat/Sun filters → %w logic; don't blind-replace all %A. Trace: locale_normalization_applied, original_day_filter, normalized_day_filter, display_field_preserved.

PHASE 8 LLM boundary (live LLM NOT required; test via mock/fixture): preserve safe LLM structure; %A→%w normalize; drop invented index unless matches user/COE/source-profile; normalize index=* earliest=-7d; user wins on conflict; timeout/disabled → deterministic skeleton works. Trace: llm_advisory_invoked, llm_advisory_used, llm_spl_draft_used, llm_spl_draft_normalized, llm_advisory_dropped_reason, deterministic_postprocessor_applied, final_spl_authority. Do not strip global AUTHORITY_HIERARCHY_RULES/REVIEW_ONLY_SAFETY_RULES; narrow any prompt change to SPL-draft generation only.

PHASE 9 Renderer (review_only_spl_renderer.py) — change ONLY explicit universal/template-free SPL utility authoring; gate on universal_spl_phrasing()/explicit_spl_authoring/source_profile_required_for_authoring=false/universal review reason; do not change analytics/q046/T2 SCADA/Cisco/Winevent/investigation. Main answer: 1) "Review-only universal SPL draft. This was not executed." 2) SPL block. 3) short explanation (replace <your_index>; %H hour; %w weekends; %A display only; adjust time window). Hide severity/long SOC checklist/compromise caveat/source-profile-required warning/template-unavailable headline/"what to look for"; keep governance in trace/debug.

PHASE 10 Tests (no live LLM): 1 weekend uses existing skeleton not dup; 2 <your_index> when no mapping; 3 earliest=-24h latest=now; 4 user explicit index preserved; 5 COE/source-profile index used; 6 LLM-invented index dropped; 7 wineventlog only if Windows mapping; 8 %A weekend LLM draft → %w; 9 %A display preserved; 10 sort 0 removed/not before filter; 11 dependency order preserved; 12 concise SPL utility, no severity/long checklist; 13 conceptual strftime stays knowledge_recall; 14 unsafe execute/delete blocked; 15 LLM timeout/disabled → deterministic; 16 conflicting LLM cannot override explicit user SPL; 17 q046 unchanged; 18 existing 9-probe smoke unchanged.

PHASE 11 git diff --check; focused tests (test_explicit_spl_authoring, test_post_pr47_live_probes, test_route_policy_smoke_fix, test_t1_spl_native_routing, test_spl_query_fidelity, test_canonical_handoff_e2e_probes); timeout 300 full backend pytest -q; timeout 300 ./scripts/run_stage3_governance_regression.sh; PYTHONPATH=backend:. python3 scripts/eval_sentinel.py --check; then git checkout -- docs/evals/ and .claude/settings.local.json.

PHASE 12 Live (timeout 180 each) ask_chat.sh weekend query + strftime concept + delete-events unsafe + excessive failed logins. Expect: route spl_generation; concise SPL-first; <your_index>; earliest=-24h latest=now; %H; %w; optional %A; no sort 0 before where; no severity; no long checklist; no source-profile clarification; execution_authorized=false; conceptual stays knowledge; unsafe blocked; q046 unchanged.

PHASE 13 If PR56 merged create branch fix/spl-utility-answer-quality-postprocessor. Commit/PR "Improve SPL utility answer quality with context-aware postprocessing".

SUCCESS: no phantom postprocessor; PR56 baseline respected; weekend skeleton reconciled not duplicated; live LLM not required; global authority constants intact; renderer gated to universal/template-free only; full backend passes; governance passes; sentinel passes; no eval drift; PR ready.

LOOP PROTOCOL: PLAN one next step; DO; VERIFY score 1-10 each (PR56 baseline awareness, skeleton reconciliation, postprocessor impl, index resolution, no-invented-index, placeholder correctness, lookback hygiene, command hygiene, locale, mocked LLM preservation, live LLM independence, renderer scoping, q046 safety, regression coverage, artifact hygiene, PR readiness) + list branch/files/tests/before-after/mocked-LLM result/postprocessor trace/execution_authorized/eval drift/PR status; DECIDE — all >=8 print FINAL + summary, else print ITERATING + fix weakest. Do not ask questions. Do not wait. BEGIN.
```
