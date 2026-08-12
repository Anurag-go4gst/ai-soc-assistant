---
name: routing-evaluation-and-authority-corrections
overview: "Build an independent routing truth set, then correct the out-of-registry terminal fallback (D2) and the legacy pattern→skill contradictions (D1) against measured evidence rather than against the answer goldens."
status: draft
date: 2026-08-11
canonical_plan: plans/2026-08-11_1834_routing-evaluation-and-authority-corrections.md
source_plan: plans/2026-08-11_0915_execution-driven-adoption-and-guided-refinement.md
source_audit: docs/evals/golden_routing_audit_2026-08-11.md
baseline_head: 93562c1
implementation_readiness: READY
---

# Plan 4 — Routing Evaluation and Authority Corrections

## Objective

The repository has no instrument that can tell a correct route from an incorrect one. The 105-question golden set — the artifact routing changes are currently measured against — cannot do it: every row matches `exact_105_*` and routes by registry table lookup, its labels are circular with the understanding table that consumes them, and `spl_status` is `none` on 113 of 120 frozen answer rows, so a regression that suppressed SPL across the whole set would still report `120 exact`.

Done means:

- an **independent routing truth set** exists (~60–80 rows, labels only, no answer goldens), whose labels were adjudicated without reading `legacy_router_intent_hint`, and which scores **semantic compatibility** against a set of acceptable skills rather than one exact skill;
- that evaluator enforces the **capability-consistency invariant**: if the selected skill's contract forbids a capability the independently labelled intent requires, the row is `inconsistent` — regardless of whether the final answer would still match an answer golden;
- **D2** (the out-of-registry terminal `LOW_CONFIDENCE_ROUTE` fallback) is corrected for detection/hunt-shaped misses by the narrowest safe deterministic rule, with unsafe/action asks still blocked or clarification-required, and OFF/ON measured against the truth set;
- **D1** (`LEGACY_ROUTER_INTENT_BY_PATTERN`) is corrected where the evidence is clear-cut and **stopped with options** where skill ownership is a product decision;
- routing quality is reported as a matrix of route correctness, capability contradiction, false escalation, under-routing, unsafe containment and ambiguity — with answer parity as **secondary** regression evidence only.

Explicitly **not** in this plan: changing the keyword router's low-confidence default (`UNDERSTANDING_ROUTER_ON_LOW_CONFIDENCE` is retired as a no-op — see below); editing the 105 answer goldens; widening any capability; building the Plan 3 A0 phase contract.

## Sources and authority

- Plan 2 (`plans/2026-08-10_1103_...`, Done 27/27, `9ee21fd`) and Plan 3 (`plans/2026-08-11_0915_...`, Done 9/9, `93562c1`) are **historical authority**. Their locked decisions — B1 `RETIRE`, C0 `EXECUTION-DRIVEN`, A0 `PHASE_POLICY_PLUS_RESOURCE_PLAN_SCHEDULING`, B2 capability compatibility — are inputs and must not be reopened without contradicting repo evidence.
- `docs/evals/golden_routing_audit_2026-08-11.md` is the measured input for D1/D2. Its numbers were produced by deterministic in-process joins at `93562c1`.
- Runtime code at `93562c1` is authoritative over every document, including this one.

## Correction carried in from the audit — recorded so it cannot be re-proposed

**`UNDERSTANDING_ROUTER_ON_LOW_CONFIDENCE` is RETIRED, not deferred.** Measured at `93562c1`: all 105 golden rows resolve `authority_source=query_understanding_105`; the keyword router holds **zero** routing authority on the set. The recorded `99/105 knowledge_recall` figure is the counterfactual provenance field `keyword_router_would_have_selected` (`select_route_from_understanding.py:34`), never a production decision, and the "understanding router picks 83/8/8" distribution is simply the production route restricted to those 99 rows. The proposed change is a **no-op on the golden set**. Any item proposing it is out of scope.

## Verified starting architecture (research, 2026-08-11, at `93562c1`)

| Surface | Observation |
|---|---|
| Routing authority on the 105 | `select_route_from_understanding` (`select_route_from_understanding.py:29`) dispatches on `deterministic_match_path`; `exact_105_question` (91) and `exact_105_plus_use_case_catalog` (14) both enter `_route_exact_105`, which resolves the skill from the registry entry via `_resolve_105_skill`. Measured `authority_source=query_understanding_105` on 105/105. |
| D1 source | `legacy_router_intent_hint` is not per-question and was never produced by a router: it is a constant lookup `LEGACY_ROUTER_INTENT_BY_PATTERN[pattern_type]` defaulting to `attack_discovery` (`tools/coverage_authoring/pattern_runtime_mapping.py:116-137`), baked into `backend/app/coverage/question_runtime_map_v1.json` by `question_runtime_map_builder.py:53,60`. |
| D1 measured | 14 rows resolve `(routed_skill, intent_family)` ∈ {(`knowledge_recall`, `spl_generation_only`) ×8, (`alert_summary`, `spl_generation_only`) ×6} with `path_type=spl_review`, `needs_spl=True`. `q0.q105` measures `live_investigation` — outside the 14, adjudicated equivalently (15 total). |
| D1 label circularity | `backend/app/tests/test_query_understanding_stage3je.py:84` asserts `understand_query(...).primary_intent == entry["legacy_router_intent_hint"]` — the router is pinned to the label supplied by the same file. |
| D2 source | The terminal fallback in `_route_out_of_registry` (`select_route_from_understanding.py:394`) reuses the `LOW_CONFIDENCE_ROUTE` **constant** (`deterministic_router.py:71`, `knowledge_recall` / `["needs_clarification"]` / `0.20`) after every floor declines, with reason `out_of_registry_no_105_or_catalog_match`. It is **not** the keyword router. |
| D2 measured | 39 of 225 unique out-of-registry probes across 8 committed banks terminate there. Traced downstream, the unsafe rows are already contained (`path_type=unsafe_blocked` or `clarification_required`, `intent_family=clarification_required`, `execution_enabled=False`); the real loss is hunt-shaped misses such as "Are there signs of Kerberoasting against domain controllers in the finance subnet?" (`intent_family=spl_generation_only`, `path_type=spl_review`, routed `knowledge_recall`). |
| Existing floors that already fire before the terminal fallback | `out_of_registry_reference_taxonomy_shape_floor`, `out_of_registry_command_mode_spine`, `out_of_registry_t2_answer_shape_floor`, `out_of_registry_investigation_request_floor`, `out_of_registry_detection_family_floor`, `out_of_registry_spl_artifact_floor`, `out_of_registry_unmapped_live_data_request`, `out_of_registry_soc_investigation_rescue`. D2 is the residue after all eight decline — so the fix is a **ninth, narrower** rule, not a replacement default. |
| Capability primitive to reuse | `app/chat/skill_intent_compatibility.py::resolve_capability_compatibility` (Plan 3 B2) already resolves `routed_skill × intent_family × contract`, fails closed, and delegates capability lookup to `composer._skill_permits`. The R1 evaluator consumes it; it must not reimplement a second capability table. |
| Answer-golden blindness | `docs/evals/soc_clean_answer_eval_answers.json`: `spl_status` is `none` on 113/120 rows (`q0.q046` rejected, `q0.q062` approved, `q0.q086` rejected, plus 4 demo/manual rows). Answer parity cannot observe D1 or D2. |

## Locked invariants

Production **routing** remains deterministic and governed — no LLM enters a routing decision path, and every route this plan changes stays a deterministic rule over existing signals · Plan 2's deterministic **ResourcePlan planning** authority is unchanged and out of scope here (routing and planning are distinct authorities; this plan touches only the former) · Plan 3's capability compatibility contract is preserved and consumed, not bypassed · a contradiction may only **deny** a capability, never widen one · no retired LLM planning rail returns · no LLM → MCP path · candidate SPL is never executable evidence; only an approved non-null `spl_validation.normalized_spl` reaches the MCP gate · MCP execution gate, HIL, RBAC and SPL validation stay authoritative · `AI_SOC_RESOURCE_PLAN_EXECUTION_ENABLED` stays default false · unsafe/action requests remain blocked or clarification-required in every arm of every experiment · no eval, reference, golden or governed-registry baseline is refreshed by verification · the 105 answer goldens are unchanged · no unrelated dirty file enters any change set.

## Scope

**In scope:** a new routing-only truth set and its evaluator; a narrow deterministic correction to the out-of-registry terminal fallback; corrections to the pattern→skill hint table where evidence is clear-cut; a full OFF/ON routing evaluation; documentation and closure.

**Out of scope:** the keyword router's low-confidence default; the Plan 3 A0 phase contract; adopting any of the four `DECISION_REQUIRED` seam paths; enabling the execution flag; editing the 105 answer goldens; any MCP/SPL/HIL/RBAC authority change.

## Decision gates

| Gate | Item | Nature |
|---|---|---|
| `ROUTING_LABEL_AMBIGUITY` | R1.3 | STOP if a row cannot be labelled without first deciding an architecture question (e.g. "is a notable-index lookup an `alert_summary` capability?"). Record the row as `ambiguous` with options; do not invent a label. |
| `ADVISORY_PROMOTION_REQUIRED_CLASS` | D3.0 | STOP and present the class if some query class genuinely requires advisory promotion (an existing test asserts it, or a measured class routes correctly only via promotion), or if the smallest correction would need a new flag, classifier, or any widening of LLM authority. |
| `D2_FALLBACK_RULE` | R3.0 | STOP if the narrowest safe rule cannot be expressed from existing deterministic signals and would require a new classifier, a new flag, or an LLM hop. |
| `D1_SKILL_OWNERSHIP` | R2.0 | STOP with options if correcting a pattern class requires deciding which skill *owns* a capability (all `alert_summary` rows are presumed to be in this class until proven otherwise). |

## Dependency order

`P0 → R1.1 → R1.2 → R1.3 (STOP on ambiguity) → R1.4 → R1.5 → R1.6 → D3.0 (STOP on required class) → D3.1 → D3.2 → R3.0 (STOP on rule) → R3.1 → R3.2 → R2.0 (STOP on ownership) → R2.1 → R2.2 → E0 → G0 → G1`

**R3 may not start while the deterministic layer it modifies is not production-final.** D3 is a blocking routing-authority defect, inserted by user decision on 2026-08-12 (`D3-c`), not an optional observation.

## What this plan does NOT close

Stated up front so closure is not read as more than it is:

1. **D1 closure may depend on user decisions this plan cannot make.** R2.0 first *measures* whether each correction actually changes golden answer bytes; classes that turn out answer-neutral need no approval and proceed. Any class that does move bytes needs a scoped golden-refresh approval, and R2.2 may legitimately defer the 7 `alert_summary` rows on ownership grounds. Worst case, D1 ends **0/15 corrected** with the measurement fully recorded — a valid close, and E0 must report it as such, not as "D1 fixed".
2. **The truth set gates the deterministic floor only.** Production routing runs `llm_assisted_semantic`; the live arm is observed (R1.5) but never gated.
3. **The 105 answer goldens stay blind to capability.** This plan documents that (G0) rather than fixing the answer eval, which would need its own plan.
4. **Near-105 / semantic-105 / catalog-collapse routing paths** are covered only incidentally, by whichever truth-set rows happen to land there. No quota forces them.

## Loop-ready checklist

- [x] **P0 — Freeze the Plan 4 baseline**
  - **Do:** With no runtime edits, record HEAD, prove the runtime-scoped worktree is clean, capture a fresh protected manifest, and confirm the inherited gate counts still hold. Do not refresh any baseline. Do not absorb existing user-owned dirt (`.claude/settings.local.json`, `.playwright-mcp/`, two G0 PNGs, `output/`, and the untracked audit report `docs/evals/golden_routing_audit_2026-08-11.md`, which is a Plan 4 input and is committed in this item only if the user asks).
  - **Why:** Every later routing measurement must compare against a measured `93562c1` baseline, not inherited prose.
  - **Surfaces:** `/tmp/plan4-routing-baseline.json`; plan Evidence only.
  - **Depends on:** none.
  - **Failing-first / observation:** Observation only. Runtime worktree dirt, protected drift, or a contradicted inherited count stops the item.
  - **Verify:** `git rev-parse HEAD`; `git status --short -- backend frontend scripts docker-compose.yml .env.example` must be empty; `python3 scripts/freeze_execution_baseline.py --capture --out /tmp/plan4-routing-baseline.json` then `--check --in /tmp/plan4-routing-baseline.json`; with `DATABASE_URL` rewritten to `127.0.0.1:5434` and never echoed, `TELEMETRY_MODE=none PYTHONPATH=backend:. python3 scripts/audit_reference_probes.py --check` and `PYTHONPATH=backend:. python3 scripts/run_production_parity_eval.py --out-dir /tmp/plan4-p0-parity --check`.
  - **Evidence:** **COMPLETE 2026-08-11 at HEAD `93562c120271a78d79064284c13a9bbfa72583ac`** — the merged Plan 3 baseline, unmodified. No runtime edit was made in this item.

    **Worktree.** Runtime-scoped status (`backend frontend scripts docker-compose.yml .env.example`) was **empty** at item open and empty again at item close. Pre-existing user-owned dirt left untouched and excluded: `.claude/settings.local.json`, `.playwright-mcp/`, two G0 PNGs, `output/`. Two untracked Plan 4 inputs also excluded and uncommitted: `docs/evals/golden_routing_audit_2026-08-11.md` and this plan file.

    **Protected manifest.** `captured 13 artifacts`; `protected artifacts unchanged (13 checked)` before and after the item (exit 0 both times).

    **Reference probes:** `all probes match the frozen baseline` — **10/10** (P1–P4 `knowledge_recall/rag_only`, P5 `knowledge_recall/live_investigation`, P6 + N1 `spl_generation/live_investigation`, N2/N4 `knowledge_recall/clarification`, N3 `knowledge_recall/live_investigation`).

    **Production parity:** `production_parity: total=120 base_105=105 exact=120 approved=0 critical=0` (exit 0). Matches the inherited post-merge count exactly; nothing refreshed. Recorded here as the **answer-stability** baseline only — per §4 of the source audit it is not evidence of routing correctness, which is precisely what R1 exists to measure.

    **Operational gotcha worth carrying forward.** `scripts/lib/dotenv.sh::dotenv_get` takes `(file, key)`, not `(key, file)`. Called with the arguments reversed it returns empty, `DATABASE_URL` falls back to the in-container `postgres:5432` host, `canonical_handoff_save_failed` fires per probe, and **all 10 reference probes report `DRIFT` with every field degraded to `None`** — visually indistinguishable from real drift. First probe run hit exactly this; the 10/10 above is the corrected run against `127.0.0.1:5434` (URL never echoed). Parity additionally logs `url_error:gaierror` for `host.docker.internal:8081` when run host-side; that is expected LLM failover noise, not a gate failure.

- [x] **R1.1 — Define the routing truth-set schema and its capability-consistency invariant**
  - **Do:** Add `docs/evals/ROUTING_TRUTH_SET_CONTRACT.md` and a machine schema pinned by test. Per-row fields: `row_id`, `query`, `source` (which committed bank or golden ref it came from), `expected_intent_family`, `expected_answer_shape`, `acceptable_skills` (**a set**, ≥1), `required_capabilities` ⊆ {`rag`,`spl`,`mcp`}, `forbidden_capabilities` ⊆ same, `ambiguous` (bool), `label_confidence` (`high`|`med`|`low`), `rationale` (free text, mandatory), `labeled_without_registry_hint` (bool, must be `true`). Define the three verdicts the evaluator may emit per row: `route_ok` (selected skill ∈ `acceptable_skills`), `route_wrong`, and — orthogonally — `capability_inconsistent`. State the invariant in the contract: **a row is `capability_inconsistent` when the selected skill's contract denies a capability the row's label marks required, even if `route_ok` and even if the answer would still match an answer golden.**
  - **Why:** The schema is the thing that makes the benchmark non-tautological; writing rows before the contract exists invites labels shaped by observed behavior.
  - **Surfaces:** `docs/evals/ROUTING_TRUTH_SET_CONTRACT.md`; `backend/app/tests/test_routing_truth_set_schema.py` (NEW).
  - **Depends on:** P0.
  - **Failing-first / observation:** The schema test must fail against a deliberately malformed fixture row (missing `rationale`, empty `acceptable_skills`, `labeled_without_registry_hint=false`) before the real set exists. Record the failure output.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_routing_truth_set_schema.py -q`; contract doc states the invariant verbatim.
  - **Evidence:** **COMPLETE 2026-08-12; runtime commit `3f40f76`.** New `backend/app/evals/routing_truth_set.py`, `backend/app/tests/test_routing_truth_set_schema.py` (27 tests), `docs/evals/ROUTING_TRUTH_SET_CONTRACT.md`. Final gate **26 passed, 1 skipped** (the skip is `test_committed_truth_set_validates` — the set does not exist until R1.2/R1.3, and it is a skip rather than a silent pass so it converts to a real assertion the moment the file lands).

    **Failing-first, as specified.** The malformed fixture row (missing `rationale`, empty `acceptable_skills`, `labeled_without_registry_hint=false`) is rejected by the finished validator. To prove that is the *validator's* doing and not the fixture's, the three corresponding checks plus the required-field loop were neutered in place and the suite re-run: **2 failed, 23 passed, 2 skipped** — `test_malformed_fixture_row_is_rejected` failed with `AssertionError: assert not True / RowValidation(row_id='rt.example.001', errors=[])`, i.e. the malformed row validated clean, together with the `rationale` mutation case. Restored from a byte-copy and re-verified green. Nine further single-field mutations (invented intent family, non-shape, duplicate/unroutable skill, invented capability, bad confidence, whitespace rationale, non-bool `ambiguous`, required∩forbidden overlap) are each pinned by parametrised test.

    **Capability invariant, and its independence — measured, not asserted.** `test_capability_inconsistency_is_independent_of_route_correctness` constructs a row where `knowledge_recall ∈ acceptable_skills` (so `route_ok` is **true**) while the label requires `spl`: `capability_consistency` returns `consistent=False, denied={'spl'}`. The two axes are therefore provably orthogonal — the D1 class scores as a route pass **and** a capability failure, which is the behavior the whole benchmark depends on.

    **One capability authority, pinned structurally.** `capability_consistency` delegates to `skill_intent_compatibility._contract_grants` → `composer._skill_permits`. `test_capability_authority_is_not_reimplemented` reads this module's own source and fails if it redefines `_PURPOSE_TOOL_HINTS` or re-reads `blocked_tools` / `default_workflow`. First draft of that test was too blunt — it matched the *prose* explaining why the table is not owned here, so it now strips comment lines and checks for a definition rather than a mention.

    **Measured capability matrix at `93562c1`** (via `skill_contract_for` + `_contract_grants`, recorded in the contract doc): `attack_discovery` spl✅/mcp✅ · `spl_generation` spl✅/mcp❌ · `alert_summary`, `knowledge_recall`, `guided_investigation` all spl❌/mcp❌.

    **Stated limit, not worked around.** `composer._PURPOSE_TOOL_HINTS` has permit keys for `spl` and `mcp` only; there is no RAG key. `rag` is therefore labelled for E0 reporting but is excluded from `CONTRACT_GATED_CAPABILITIES` and can never produce a `capability_inconsistent` verdict — gating it would require inventing the second capability table this module exists to avoid. Pinned by `test_rag_is_labelled_but_not_contract_gated` and documented in the contract.

    **Vocabularies pinned to the runtime, not copied.** All 16 `INTENT_FAMILIES` members are asserted to appear as `intent_family="…"` in `intent_classifier.py`, so a label can never name a family the runtime cannot produce; `expected_answer_shape` imports `AnswerShape` at call time (11 literals + `clarification`); `acceptable_skills` is checked against `SKILL_ENUM`.

    **Staging enforced.** `stage=corpus` rows carry identity only and a label present at corpus stage is a validation error; validating a corpus file as `labeled` fails. This is what keeps R1.2 assembly from being contaminated by R1.3 adjudication, structurally rather than by discipline.

    **Manifest / scope.** `protected artifacts unchanged (13 checked)`. Additive only — `grep` confirms **no production path imports** `routing_truth_set`; `git status` over `routing/ chat/ planner/ spl/ mcp/ llm/ safeguards/` is empty, so no capability, SPL, MCP, HIL or LLM surface moved. Formal `/invariant-check` deferred to the first item that touches a runtime path (R1.6/R3.1). The known import-time artifact on `backend/app/chat/detail_tools/__init__.py` (appended blank line, third recurrence — see Plan 2 and Plan 3 drift logs) reappeared during test runs and was reverted before staging.

- [x] **R1.2 — Assemble the corpus (queries only, no labels)**
  - **Do:** Build `docs/evals/routing_truth_set_v1.json` with rows carrying `row_id`/`query`/`source` and **no expected fields yet**. Composition target 60–80 rows: all 15 D1 rows (14 measured contradiction + `q0.q105`); all 39 D2 terminal-fallback rows (already present in committed banks — reference them, do not invent queries); ≥5 correct knowledge-only rows; ≥4 alert-summary rows including at least two that genuinely summarise a *supplied* alert; ≥6 hunt/detection/SPL rows drawn from the correctly-routed golden classes; ≥5 OT/SCADA/Cisco-style rows from `ot_powergrid_question_bank.json` / `coe_india_powergrid_probe_25_bank.json` / `cisco_powergrid_question_bank.json`; ~15 paraphrases of golden questions written so they must **not** hit `exact_105_*`. Record each row's source provenance.

    **Also required — the two surfaces where the keyword router genuinely decides.** Add ≥4 rows that reach `_keyword_fallback` (reasons `catalog_use_case_not_found` at `select_route_from_understanding.py:188` and `unknown_catalog_primary_skill:*` at `:209`) and, if constructible without faulting the parser, ≥1 row exercising `_qu_failover_route` (`understand_query` raised). These are the **only** production paths where `route_skill_deterministic` holds authority; a routing benchmark that omits them leaves the actual keyword-authority surface unmeasured. If `_qu_failover_route` cannot be reached from a query string alone, record that and cover it by unit test instead.

    **Quota arithmetic — coverage quotas overlap by design.** The minimums are *coverage* requirements satisfiable by the same row: a D2 row sourced from an OT bank counts toward both the D2 set and the OT quota; a D2 row whose ask is knowledge-only counts toward the knowledge quota. Only the 15 D1 rows and the ~15 paraphrases are necessarily disjoint from everything else. Total row count is bounded **[60, 95]**, not [60, 80] — the naive sum of minimums (89) exceeds 80, so a plain [60,80] gate would fail on arithmetic. Every row records which quotas it satisfies.
  - **Why:** Paraphrases are what break the exact-match lookup; without them the set inherits the same tautology as the 105.
  - **Surfaces:** `docs/evals/routing_truth_set_v1.json`.
  - **Depends on:** R1.1.
  - **Failing-first / observation:** Measure and record `deterministic_match_path` for every paraphrase row; **any paraphrase resolving to `exact_105_question` must be rewritten** before the item closes. This is the item's own gate.
  - **Verify:** `PYTHONPATH=backend:. python3 -c` one-liner asserting row count ∈ [60,95], `row_id` unique, every `source` resolvable, every coverage quota met (counting overlaps as above), and zero paraphrase rows on an `exact_105_*` path; `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_routing_truth_set_schema.py -q`.
  - **Evidence:** **COMPLETE 2026-08-12; commit `d013e10`.** `docs/evals/routing_truth_set_v1.json`, `stage: "corpus"`, **90 rows** (within `[60,95]`), identity fields only — the staged schema rejects any label at corpus stage, so R1.3 cannot contaminate assembly. Verify gate: `RESULT: PASS (90/90 rows, quotas {'d1': 15, 'd2': 39, 'ot': 20, 'hunt': 7, 'alert_summary': 4, 'alert_supplied': 2, 'knowledge': 5, 'paraphrase': 15}, 0 paraphrase exact-match)`; every `source` resolved to a committed file; all row_ids unique. Schema suite **27 passed** — `test_committed_truth_set_validates` converted from skip to a live assertion the moment the file landed.

    **D1 and D2 reproduce exactly against the runtime, so the corpus rests on measurement rather than on the audit's prose.** Re-deriving from `93562c1`: **15** D1 rows (14 `spl_generation_only` + `q0.q105` `live_investigation`) and **39** D2 terminal-fallback rows (`live_efficacy_100` 23, `powergrid_soc` 11, `intent_out_of_set` 3, `coe_india` 2). No D2 query was invented; each references its committed bank.

    **The anti-tautology property holds, measured.** All 15 paraphrases land **off** the exact-105 table: 14 `out_of_registry`, 1 `use_case_catalog`, **0 `exact_105_*`** — the item's own gate, passed on the first assembly with no rewrite needed. Corpus-wide paths: `out_of_registry` 59, `exact_105_question` 20, `use_case_catalog` 6, `exact_105_plus_use_case_catalog` 4, `semantic_105_question` 1.

    **Finding recorded for E0 — near/semantic matching does not rescue genuine rephrasing.** Only **1 of 15** paraphrases reached a near/semantic 105 path; the other 14 fell all the way to `out_of_registry`. Consistent with the standing observation that the gap is index coverage rather than the matcher. Not acted on here — it is an observation about generalization, not a Plan 4 defect.

    **Correction to the source audit, with measurement.** The audit stated the keyword router *is* authority at `_keyword_fallback` and `_qu_failover_route`. True as code paths, but **neither is reachable from query text** with the committed registries: 54 corpus/bank queries reach `use_case_catalog` and **0** produce a use-case id `get_use_case` cannot resolve; **0** of 65 catalog entries carry a `primary_skill` outside `SKILL_ENUM ∪ CATALOG_SKILL_COLLAPSE`; and `understand_query` raised on **0 of 8** hostile probes (empty, whitespace, NUL bytes, 20k chars, 500 emoji, SQL-ish, brace soup, newlines). So the 0.20 default currently has **no reachable routing authority anywhere** — which strengthens, rather than weakens, the retirement of `UNDERSTANDING_ROUTER_ON_LOW_CONFIDENCE`.

    Per the item's stated fallback, both surfaces are covered by unit test instead of corpus rows: new `backend/app/tests/test_keyword_router_authority_reachability.py` (12 tests) pins the two registry conditions that make them unreachable — so a future catalog edit that hands routing authority to the keyword router **fails here loudly** — and pins both paths' live behavior, including the distinction Plan 4 turns on: an unmatched query keeps `authority_source=query_understanding_weak`, and only a genuine keyword-rule match records `keyword_router_fallback`. Combined suite **39 passed**.

    **Manifest / scope.** `protected artifacts unchanged (13 checked)`. Additive only; no routing, capability, SPL, MCP or LLM surface touched.

- [x] **R1.3 — Adjudicate labels independently — STOP gate `ROUTING_LABEL_AMBIGUITY` — FIRED, awaiting decision**
  - **Do:** Label every row's expected fields **without consulting** `legacy_router_intent_hint`, `proposed_primary_skill`, or the observed route; derive each label from the query text plus documented policy (`HUNT_PATTERNS`, the analytics severity guard, skill capability contracts, the unsafe/action lane). Use `acceptable_skills` sets wherever more than one route is legitimately valid. Set `ambiguous=true` + `label_confidence=low` and record both candidate readings for any row whose label depends on an unresolved architecture question — do **not** guess. **STOP and present options** if any row's label cannot be settled without a skill-ownership or capability-ownership decision.

    **Label independence is procedural, not structural — three mechanisms make it checkable.** The labeller has already seen production routes for many of these rows in the audit that produced this plan, so `labeled_without_registry_hint=true` is a self-attestation and nothing more. (1) **Order commitment:** write the completed label file, record its SHA256 in Evidence, and only then run the evaluator; any later label edit must be recorded as an explicit relabel with its reason, never as a silent correction. (2) **Blind second labeller:** have an independent labeller (a subagent given the queries and the contract, but **not** this plan, the audit report, or any observed route) label a ~20-row subset; record inter-labeller agreement as a number. Disagreements are findings to adjudicate, not rows to overwrite. (3) **Forced ambiguity:** the 7 `alert_summary` D1 rows (`notable_risk_lookup` ×5, `case_state_lookup` ×2) are set `ambiguous=true` **by rule**, because their label *is* the R2.0 ownership question — labelling them confidently here would pre-decide the gate that R2.0 exists to escalate.
  - **Why:** The benchmark's whole value is independence from the thing it measures.
  - **Surfaces:** `docs/evals/routing_truth_set_v1.json` (expected fields populated).
  - **Depends on:** R1.2.
  - **Failing-first / observation:** Record, before labelling, that observed routes were not read for the rows being labelled. After labelling, compute and record agreement with the current production route — as an **observation**, never as a correction step; a low agreement rate is a finding, not a reason to relabel.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_routing_truth_set_schema.py -q` (all rows now complete); every `ambiguous=true` row carries two documented readings; the 7 `alert_summary` D1 rows are `ambiguous=true`; label-file SHA256, blind-subset inter-labeller agreement, and the count of `label_confidence=low` rows recorded in Evidence.
  - **Evidence:** **LABELS COMPLETE 2026-08-12; commit `d3e3033`. STOP gate `ROUTING_LABEL_AMBIGUITY` FIRED — 9 rows require the skill-ownership decision and are presented to the user; the item does not close until that decision is recorded.**

    **87 rows labelled from query text and documented policy only.** `legacy_router_intent_hint`, `proposed_primary_skill` and the observed production route were not consulted while assigning any label. Schema suite **28 passed**. Families: `spl_generation_only` 36, `clarification_required` 13, `guided_investigation` 12, `live_investigation` 9, `policy_knowledge` 7, `sop_or_playbook` 4, `knowledge_only` 2, `hybrid_alert_review` 2, `cve_investigation` 1, `alert_summary` 1. Confidence **67 high / 11 med / 9 low**. **74 of 87** rows carry more than one acceptable skill — multi-validity is the norm, and forcing a single exact skill would have manufactured failures.

    **(1) Order commitment.** Label file written, committed, and hashed **before** any evaluator run: `sha256 = 2877e3444dc65da3c8182c444f00c3a2596713b83c3455cde54ea46b6ad3c76e`. Any later change must be recorded as an explicit relabel.

    **(2) Blind second labeller — 20-row stratified subset** (`d2` 9, `d1` 3, `paraphrase` 3, `hunt` 2, `alert_summary` 1, `knowledge` 1, `ot` 1). The labeller was given the queries and the contract, and explicitly denied `plans/`, the audit report, the truth set, `question_runtime_map_v1.json`, `pattern_runtime_mapping.py`, and any router execution. Measured agreement:

    | Axis | Agreement |
    |---|---|
    | `acceptable_skills` overlap (**the gating axis**) | **20/20 (100%)** |
    | contract-gated capabilities `spl`/`mcp` (**the gating axis**) | **20/20 (100%)** |
    | `expected_answer_shape` | 17/20 (85%) |
    | `required_capabilities` incl. non-gated `rag` | 17/20 (85%) |
    | `ambiguous` | 18/20 (90%) |
    | `expected_intent_family` (raw) | **9/20 (45%)** |

    **The 45% family figure is not a disagreement about routing, and the measurement says so.** All 11 family differences are **within a capability-equivalence class — 0 of 11 cross a capability boundary.** Eight are the single systematic axis `spl_generation_only` (mine) vs `live_investigation` (blind) on rows where both labellers picked the same acceptable skills and the same gated capabilities; the other three (`policy_knowledge` vs `knowledge_only`, `guided_investigation` vs `knowledge_only`) sit entirely inside the no-capability families. The three `required_capabilities` differences are all "blind additionally listed `rag`", which is not contract-gated.

    **Design consequence for R1.4, recorded here so it is not re-litigated:** two independent labellers agree **perfectly** on the two axes the evaluator gates and diverge on the descriptive ones. `expected_intent_family` and `expected_answer_shape` must therefore be **reported, never gated** — gating family would have scored a 55% "failure" rate that contains no routing information at all.

    **(3) Forced ambiguity held, and the blind labeller independently widened it.** All 7 notable/risk/case-state D1 rows plus the 2 paraphrases of them are `ambiguous=true` / `label_confidence=low` with both readings recorded. The two ambiguity disagreements are both the blind labeller marking **more** rows ambiguous than the rule required — `rt.d1.005` (`asset_identity_context`, "users who accessed privileged applications unusually") and `rt.d1.012` (`data_source_health`, "sources that stopped sending events"), each with the same two readings: an already-scored-state lookup owned by `alert_summary`, versus a fresh live query owned by an SPL-capable skill. It did **not** extend the doubt to `rt.d1.002`, agreeing that a fresh IOC hunt is clear-cut.

    **This is a scope finding for R2.0, not a labelling error:** the ownership question may reach beyond the 7 notable/case-state rows into `asset_identity_context` and `data_source_health`, which would shrink the "clear-cut `knowledge_recall`" group the plan assumed for R2.1. Recorded, not resolved — resolving it here is exactly what the forced-ambiguity rule forbids.

    **Assembly defect found while labelling, and fixed.** Three control rows (`rt.alert.004`, `rt.know.003`, `rt.know.004`) restated D2 queries verbatim under different `row_id`s, which would have double-weighted those questions in every rate the evaluator reports. Their quotas were merged onto the D2 rows that already held the query and the duplicates dropped — **90 → 87 rows**, all quotas still met (`d1` 15, `d2` 39, `ot` 19, `paraphrase` 15, `hunt` 7, `knowledge` 5, `alert_summary` 4, `alert_supplied` 2). Duplicate query text is now a validation error (`test_duplicate_query_text_across_rows_is_rejected`), so it cannot recur.

- [x] **R1.4 — Build the routing evaluator**
  - **Do:** Add `scripts/eval_routing_truth_set.py` — in-process, deterministic, no LLM, no live backend. Per row: `understand_query` → `select_route_from_understanding` → `build_query_to_intent` → `plan_evidence` → `plan_path_and_tools`; then score `route_ok` against `acceptable_skills`. Evaluate the capability invariant against the **labelled** `required_capabilities` (not the classifier's intent family) by asking the selected skill's contract, per capability, through the same permit primitive Plan 3 B2 uses — `skill_intent_compatibility._contract_grants` / `composer._skill_permits`. Note the API shape: `resolve_capability_compatibility(routed_skill, intent_family, skill_contract)` has **no** parameter for labelled capabilities, so call it for the *observed* pairing (to report the runtime's own resolution) and check the labelled capabilities separately through the permit primitive. Do not create a second capability table. Emit per-row JSON and the `EVAL_CONTRACT.md` verdict line `RESULT: PASS (n/m rows, …)`, and `--json <path>` for per-row results.

    **`--check` semantics are NO-REGRESSION, not identity.** `--check --baseline <file>` passes when, relative to the baseline: no row flips `route_ok` → `route_wrong`, and no row gains `capability_inconsistent`. Improvements pass. Identity-checking would make the gate pass trivially at R1.5 and fail by construction at G1, since R3/R2 exist to improve on the baseline. `ambiguous` rows report but never gate.
  - **Why:** A benchmark that cannot be re-run identically is an anecdote.
  - **Surfaces:** `scripts/eval_routing_truth_set.py` (NEW); `backend/app/tests/test_routing_truth_set_eval.py` (NEW).
  - **Depends on:** R1.3.
  - **Failing-first / observation:** Unit-test the invariant against a synthetic row whose labelled `required_capabilities={spl}` meets a `knowledge_recall` contract — must report `capability_inconsistent` **while** `route_ok` is true, proving the two axes are independent. Record that output.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_routing_truth_set_eval.py -q`; `PYTHONPATH=backend:. python3 scripts/eval_routing_truth_set.py --json /tmp/plan4-r1-baseline.json` prints a conforming `RESULT:` line; running it twice produces byte-identical per-row verdicts.
  - **Evidence:** **COMPLETE 2026-08-12; commit `a57e4e9`.** New `scripts/eval_routing_truth_set.py` + `backend/app/tests/test_routing_truth_set_eval.py` (**11 passed**). Deterministic, in-process, no LLM, no live backend. Two runs produced **byte-identical per-row verdicts and summary**.

    **Failing-first / independence, on a real routed query.** `test_route_ok_and_capability_inconsistent_can_coexist` routes "Which hosts contacted suspicious external domains?" with `knowledge_recall` deliberately inside `acceptable_skills`: the evaluator returns `route_verdict=route_ok` **and** `capability_inconsistent=True, denied=['spl']` at the same time. That is the D1 defect class scoring as a route pass and a capability failure simultaneously — if the axes were ever collapsed the benchmark would be blind to exactly what it was built to measure.

    **Family and shape are reported, never gated — enforced, not just intended.** `test_family_mismatch_does_not_affect_any_gating_number` asserts every gating figure is identical for `family_match=True` and `False`. This encodes R1.3's measurement: two independent labellers agreed 20/20 on both gating axes and 9/20 on family, with **0 of 11** family differences crossing a capability boundary. Gating family would have manufactured a ~55% failure rate carrying no routing information.

    **`--check` semantics implemented as no-regression** (`compare()`): a row may not flip `route_ok → route_wrong` and may not gain `capability_inconsistent`; improvements pass; ambiguous rows cannot trigger a regression. **Deleting a row is itself a regression** (`test_a_dropped_row_is_a_regression`), so an inconvenient row cannot be removed to make the gate pass. Verdict line conforms to `EVAL_CONTRACT.md`.

    **One capability authority.** The evaluator calls `routing_truth_set.capability_consistency`, which delegates to `skill_intent_compatibility._contract_grants` → `composer._skill_permits`. No second table.

- [x] **R1.5 — Record the OFF (baseline) routing measurement**
  - **Do:** Run the evaluator at unmodified `93562c1` runtime and freeze the result as `docs/evals/routing_truth_set_baseline_v1.json` — this is a **new** baseline for a new artifact, not a refresh of a protected one. Record the full matrix: route-correct rate, capability-contradiction rate, knowledge-only false-escalation count, hunt/detection under-routing count, unsafe-containment count, ambiguous count.

    **Record the benchmark's coverage limit in the baseline file itself.** The evaluator is deterministic-only, but production runs `routing_mode=llm_assisted_semantic`, where the consumer-gated intent advisory can promote a route live. A green truth-set run is therefore evidence about the **deterministic floor**, not about production routing. Additionally run a ~10-row **live-arm observation** through the production routing mode and record the delta as observation only — never a gate, never a reason to relabel. If the live arm diverges materially from the deterministic arm, that is a finding for E0, not a blocker here.
  - **Why:** R3 and R2 are only acceptable if they move these numbers in the right direction; without a frozen OFF arm there is nothing to compare.
  - **Surfaces:** `docs/evals/routing_truth_set_baseline_v1.json` (NEW); add it to `PROTECTED["eval_baselines"]` in `scripts/freeze_execution_baseline.py` so later items cannot silently rewrite it.
  - **Depends on:** R1.4.
  - **Failing-first / observation:** Confirm the baseline reproduces D1 (≥14 `capability_inconsistent` rows among the D1 subset) and D2 (≥1 hunt row terminating on `knowledge_recall @ 0.20`). If it does not, the evaluator is wrong — stop and fix it before proceeding.
  - **Verify:** `PYTHONPATH=backend:. python3 scripts/eval_routing_truth_set.py --check --baseline docs/evals/routing_truth_set_baseline_v1.json`; `python3 scripts/freeze_execution_baseline.py --capture --out /tmp/plan4-routing-baseline.json` re-captured to include the new artifact (14 artifacts) and `--check` passes.
  - **Evidence:** **COMPLETE 2026-08-12; commit `cdeea34`.** Frozen `docs/evals/routing_truth_set_baseline_v1.json` at unmodified `93562c1` runtime.

    | Metric | Baseline |
    |---|---|
    | gating rows / ambiguous | **77 / 10** |
    | `route_ok` / `route_wrong` | **56 / 21** (route-correct rate **0.727**) |
    | `capability_inconsistent` | **21** (rate 0.273) |
    | hunt/detection under-routing | **21** |
    | knowledge-only false escalation | **0** |
    | unsafe containment | **13/13** |
    | family match (reported, non-gating) | 41/77 |

    **Both sanity gates hold.** D1 reproduces — **all 8 gating D1 rows are `capability_inconsistent` on `spl`** (`rt.d1.001/004/007/008/009/010/015` routed `alert_summary`, `rt.d1.002` routed `knowledge_recall`). D2 reproduces — **all 39 D2 rows sit on the 0.20 terminal fallback**, 3 of them (`rt.d2.003` Kerberoasting, `rt.d2.010`, `rt.d2.017`) requiring SPL the routed skill cannot provide.

    **Recorded deviation from the plan's stated gate.** The plan expected "≥14 `capability_inconsistent` rows among the D1 subset". The measured figure is **8**, and that is correct rather than a miss: the user's recorded decision deferred the `asset_identity_context` and `data_source_health` ownership question to R2.0, which marks those 7 rows ambiguous and therefore non-gating. The deferral costs gating power on exactly those rows — stated here rather than papered over.

    **Baseline added to `PROTECTED["eval_baselines"]`.** The evaluator can rewrite it with `--freeze`, so guarding it makes a re-baseline a visible decision rather than a side effect of a run. Manifest re-captured: **14 artifacts**, `--check` passes.

    **Live-arm observation — see the D3 finding recorded under Deferred decisions.** The 10-row sample the plan asked for was expanded to all 77 gating rows once the first sample showed a divergence. Result: the LLM advisory selects the final route on **49/77** rows, diverges from the deterministic floor on **10**, and **all 10 divergences are degradations, 0 improvements**. This is observation only — no gate, no relabel — but it materially affects R3.0 and is raised as a stop.

- [x] **R1.6 — De-circularize the 105 routing pin (independent of any hint change)**
  - **Do:** Rewrite `backend/app/tests/test_query_understanding_stage3je.py:84` so it asserts a **contract** — the resolved route is a valid skill and, for rows present in the truth set, is a member of that row's `acceptable_skills` — instead of asserting identity with `legacy_router_intent_hint`, the label the same file supplies. Keep whatever coverage the existing assertion legitimately provides (registry match source, match path) and record what the identity assertion was actually protecting.
  - **Why:** The circularity is a defect on its own: it makes the router unfalsifiable against its own registry. In the first draft this fix lived inside R2.1, so a withheld golden-refresh approval would have left the circular pin in place indefinitely. It does not depend on any hint value changing, so it is its own item.
  - **Surfaces:** `backend/app/tests/test_query_understanding_stage3je.py`.
  - **Depends on:** R1.5.
  - **Failing-first / observation:** Prove the new assertion has teeth: mutate one row's `legacy_router_intent_hint` in memory to an out-of-set skill and confirm the rewritten test fails. Record the output, then revert the mutation.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_query_understanding_stage3je.py -q`; `PYTHONPATH=backend:. python3 scripts/eval_105_path_honoring.py --check`; `python3 scripts/freeze_execution_baseline.py --check --in /tmp/plan4-routing-baseline.json`.
  - **Evidence:** **COMPLETE 2026-08-12; commit `d2da614`.** `test_query_understanding_uses_question_registry_as_intent_fallback` no longer asserts `result.primary_intent == entry["legacy_router_intent_hint"]`.

    **What the old assertion was protecting, recorded before replacing it:** the *mechanism* — with no use-case match (`mapped_use_case_ids == []`) the intent still resolves, and it carries the registry-fallback confidence `0.55`. That is preserved. What was dropped is the circularity: asking the router to agree with the label supplied by the very file it reads, which cannot fail for any reason worth knowing. The route's *correctness* is now measured against independently-adjudicated labels instead.

    **Replacement asserts:** `primary_intent ∈ SKILL_ENUM`, `confidence == 0.55`, `question_registry_match_source == "question_runtime_map_105_exact"`, plus a new contract test over non-ambiguous golden-sourced truth-set rows.

    **Teeth proven by mutation, not assumed.** `q0.q001`'s `legacy_router_intent_hint` was set to `not_a_real_skill` in the committed map: the rewritten test **failed** (`1 failed, 17 passed`). Mutation reverted with `git checkout --`; suite back to **18 passed**; `protected artifacts unchanged (14 checked)`.

    This item existed separately from R2.1 precisely so a withheld golden-refresh approval could not leave the circularity in place indefinitely — and that separation paid off, since R2.1 is still gated on a decision.

- [x] **D3.0 — Determine the smallest correction to routing authority — STOP gate `ADVISORY_PROMOTION_REQUIRED_CLASS`**
  - **Do:** No runtime change. (a) Add a **live arm** to `scripts/eval_routing_truth_set.py` (`--arm deterministic|live|both`) that additionally routes each row through `route_skill` — the production-final path — and reports `selected_by`, the deterministic-vs-live delta, and capability downgrade/upgrade per row, so every later claim states which layer it measured. (b) Classify all **10** measured degradations by mechanism, separating *capability downgrades* (`spl_generation → knowledge_recall/alert_summary`) from *lateral or widening* replacements. (c) Establish the smallest correction satisfying the user's contract: deterministic/query-understanding routing stays authoritative; the advisory may enrich or confirm but may **not** independently replace the authoritative route nor reduce required capabilities; registry-backed behavior unchanged; unsafe containment identical; **no new LLM authority**. Anchor it at the measured root cause — `_deterministic_uncertain` (`governance.py:397-414`) returns `True` for **every** `out_of_registry` row via the blanket `match_path in {"near_105_question","out_of_registry"}` clause, so a *reasoned* floor decision (e.g. `out_of_registry_detection_family_floor → spl_generation`) is classed "uncertain" and replaced at `governance.py:251`. (d) Predict the per-row effect on all **77** gating rows before implementing. (e) Enumerate every existing test that asserts a promotion occurs.
  - **Why:** R3 modifies the deterministic layer. While that layer is not production-final on out-of-registry paths — exactly where D2 lives — an R3 measurement would forecast a layer the host does not obey.
  - **Surfaces:** `scripts/eval_routing_truth_set.py` (live arm); plan Evidence + options table. No runtime file.
  - **Depends on:** R1.6.
  - **Failing-first / observation:** The live-arm evidence **is** the failing-first artifact and must be reproduced by the committed evaluator, not quoted from a scratch run: advisory selects the final route on **49/77**; **10** deterministic divergences; **10** degradations; **0** improvements.
  - **STOP:** If preserving advisory promotion is genuinely required for some class of queries — an existing test asserts it, or a measured class routes correctly *only* via promotion — **stop and present that class with its rationale** before implementing. Also stop if the smallest correction would need a new flag, a new classifier, or any widening of LLM authority.
  - **Verify:** `PYTHONPATH=backend:. python3 scripts/eval_routing_truth_set.py --arm both --json /tmp/plan4-d3-before.json` reproduces 49/77 · 10 · 10 · 0; options table records per-row predictions for all 77; the promotion-asserting test inventory is complete (`grep -rn "llm_advisory_validated\|apply_advisory_promotion" backend/app/tests`).
  - **Evidence:** **COMPLETE 2026-08-12; commit `6864267`. STOP gate `ADVISORY_PROMOTION_REQUIRED_CLASS` did NOT fire** — no test and no measured class requires advisory promotion to route correctly (inventory below).

    **Failing-first evidence reproduced by committed code**, not quoted from a scratch run: `--arm both` reports `advisory_selected=49/77 diverges=10 degraded=10 improved=0 lateral=0 capability_downgrades=5`, `live_route_ok=46/77` against deterministic `56/77`. The live arm is **10 rows worse** than the layer Plan 4 modifies.

    **Two root causes, not one. The second was found during this item and is worse than the recorded one.**

    | | Root cause | Effect |
    |---|---|---|
    | **RC1** (recorded in the plan) | `_deterministic_uncertain` (`governance.py:409-414`) returns `True` for **every** `out_of_registry` row via the blanket `match_path in {"near_105_question","out_of_registry"}` clause | A reasoned floor decision (`out_of_registry_detection_family_floor → spl_generation`, conf 0.5) is classed "uncertain" and replaced at `:251` |
    | **RC2** (**new**) | On registry-backed paths, `llm_advisory_recommended` alone satisfies uncertainty (`governance.py:404-408`) | `rt.ot.004` is an **`exact_105_plus_use_case_catalog` match at confidence 0.75** — not low, not clarification — yet `_qu_route_retains_authority` returns `False` and the advisory replaces `spl_generation` with `alert_summary` |

    **RC2 corrects a claim made in this plan's own D3 write-up.** R1.5's evidence said "registry-backed paths are unaffected (13 rows kept `query_understanding_105`)". True of those 13, false as a general statement: a 14th registry-backed row was overridden. So the user's constraint "registry-backed behavior remains unchanged" is **already violated today** — the correction restores it rather than preserving it.

    **Options compared, with measured per-row predictions over all 77 gating rows.**

    | | Option 1 — downgrade-only guard | Option 2 — resolved deterministic route retains authority |
    |---|---|---|
    | Rule | advisory may not swap in a skill granting strictly fewer capabilities | once any resolved deterministic authority produced the route, the advisory may not replace the skill |
    | Divergences fixed | **5 / 10** | **5 / 10** |
    | Promotions blocked (of 49) | **5** | **5** |
    | Rows fixed | `rt.ot.001/002/004/005`, `rt.para.002` | *identical set* |
    | Leaves unfixed | `rt.d2.012/023` (→`spl_generation`), `rt.d2.030/037` (→`attack_discovery`), `rt.d2.034` (→`alert_summary`) | identical |

    **The two options are measurably identical on this corpus** — the same 5 rows, the same 5 blocked promotions, zero rows where they differ. The tie breaks on principle and on interaction with R3:

    - Option 1 permits an LLM to **widen** capability: `rt.d2.030/037` gain `spl`+`mcp` purely on advisory say-so. That is the wrong direction for a governance boundary, and Plan 3's B2 contract is explicitly fail-closed against exactly this.
    - Option 2 states the invariant the architecture already documents ("final route selection stays deterministic") and leaves only *genuinely unresolved* routes promotable.
    - **Option 2 composes with R3.** All 5 unfixed rows are D2 rows whose deterministic route is the terminal `query_understanding_weak` 0.20 fallback. Once R3 gives those rows a resolved floor, the same guard protects them **automatically**, with no further advisory work.

    **Selected: Option 2, implemented at the narrowest possible seam.** The advisory still *runs* — semantic understanding is not disabled globally (explicit user constraint). It keeps agreement (`llm_assisted_semantic_normalized`), warnings, candidate metadata, adjudication reporting and telemetry. Only the **skill-replacement** branch at `governance.py:251` is narrowed, via a predicate distinct from `_deterministic_uncertain`, whose other two call sites (`skill_router.py:259` deciding whether to *run* the advisory, `governance.py:488` adjudication reporting) are deliberately left alone.

    **Predicted effect on all 77:** 5 rows change (advisory blocked, deterministic route retained), **72 unchanged**. All 5 capability downgrades eliminated; 5 non-downgrade divergences remain and are classified as R3-owned.

    **Promotion-dependency inventory — nothing requires promotion.** `grep -rn "llm_advisory_validated\|apply_advisory_promotion" backend/app/tests` returns exactly one file, `test_advisory_promotion.py`, which exercises **a different mechanism**: `llm_intent_advisor.apply_advisory_promotion` promotes candidate *use-case mappings* inside `build_query_to_intent`, not the routed skill. D3 does not touch it. The only tests on the actual seam (`normalize_assisted_selection`, in `test_live_efficacy_p1_routing.py`) assert promotion is **blocked** for unsafe rows `eff.072`/`eff.098` — they constrain the same direction as this correction. **No test, and no measured row, routes correctly only via promotion**, so the STOP gate does not fire.

    **No new flag, classifier, LLM hop, or authority** — the change strictly removes conditions under which the advisory may act.

- [x] **D3.1 — Restore deterministic finality by the smallest measured correction**
  - **Do:** Implement exactly the D3.0 correction. It may only **narrow** when the advisory can replace a route; it may not add a capability, a flag, an authority, or a model call. Registry-backed paths must be untouched by construction (they already skip the advisory via `_qu_route_retains_authority`). The advisory keeps its enrich/confirm roles — `llm_assisted_semantic_normalized` agreement, warnings, candidate metadata, telemetry — none of which select a skill.
  - **Why:** The documented invariant ("final route selection stays deterministic") and the runtime disagree; the runtime is what ships.
  - **Surfaces:** `backend/app/routing/governance.py`; `backend/app/tests/test_advisory_route_authority.py` (NEW).
  - **Depends on:** D3.0.
  - **Failing-first / observation:** New tests must fail before the change on at least one capability-downgrade row (`rt.ot.002` `spl_generation → knowledge_recall`) and one non-downgrade replacement, and must pin that unsafe rows are unaffected. Record pre- and post-change output.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_advisory_route_authority.py app/tests/test_route_governance.py app/tests/test_skill_router.py app/tests/test_llm_intent_advisor.py -q`; `python3 scripts/freeze_execution_baseline.py --check --in /tmp/plan4-routing-baseline.json`; `/invariant-check` across the item's diff.
  - **Evidence:** **COMPLETE 2026-08-12; runtime commit `a66540c`.** Change is one predicate at one call site: `_advisory_may_replace_skill(deterministic, deterministic_uncertain)` replaces the bare `deterministic_uncertain` test at `governance.py:251`. Replacement is permitted only when the deterministic route reached **no** conclusion — its tool plan is `LOW_CONFIDENCE_ROUTE["tool_plan"]` (`["needs_clarification"]`), the existing marker already used by `_keyword_fallback` and `skill_router`. `_deterministic_uncertain` itself is untouched, so its other two call sites (whether to *run* the advisory, and adjudication reporting) behave exactly as before: the advisory still runs, still records agreement as `llm_assisted_semantic_normalized`, still contributes warnings, candidates and telemetry. **Semantic understanding is not disabled**, per the explicit constraint.

    **Failing-first, recorded both ways.** New `backend/app/tests/test_advisory_route_authority.py`: **5 failed, 5 passed** before the change; **10 passed** after. The failures were exactly the intended targets — `rt.ot.002` (out-of-registry floor route replaced), `rt.ot.004` (registry-backed match replaced), the capability-preservation property over all 5 downgrade rows, and advisory-agreement reporting.

    **Both sides of the boundary are pinned, not just the fix.** `test_terminal_low_confidence_route_remains_promotable` asserts `rt.d2.030` — a genuinely unresolved route — is **still** promotable (`selected_by == "llm_advisory_validated"`), so narrowing cannot silently become "switch the advisory off".

    **Targeted suites:** 126 passed, 1 skipped across advisory authority, live-efficacy P1 routing, advisory promotion, guided route, catalogue router probes, keyword-authority reachability and both truth-set suites. **Full backend: `5107 passed, 3 skipped, 6 xfailed, 2 failed`** — the two failures are the D3.2 STOP, analysed below.

    **Invariant check 7/7 CLEAR.** No new MCP call site; no SPL executability surface touched; `backend/app/demo/` untouched; no secrets; no new `state[...]` channel; no new flag (the change strictly *removes* conditions under which the advisory may act); no existing test modified. Dual-path coverage is inherent — `graph_node_init_routing` is the single routing node for `pipeline.py:634`, `resource_planner_graph.py:329`, `planner_led_shadow_graph.py:110` and `linear_graph_legacy.py:113`.

    **Full backend after the approved fixture correction: `5109 passed, 3 skipped, 6 xfailed, 0 failed`.**

- [x] **D3.2 — Measure D3 before/after on all 77 rows and accept or revert**
  - **Do:** Re-run both arms and compare against the D3.0 before-state and the R1.5 baseline. **Acceptance, all required:** (1) **0** advisory-caused capability downgrades; (2) **no** previously-correct deterministic route becomes wrong; (3) unsafe containment **identical** (13/13, no row gains `execution_enabled`); (4) deterministic and live-arm routing differences **explicitly reported**, including any that remain. Revert if any condition fails. Run answer parity and the frozen probe gates as **secondary** regression evidence, labelled as such.
  - **Why:** A routing-authority change is only acceptable against measurement on the same rows that exposed it.
  - **Surfaces:** Plan Evidence; `/tmp` comparison artifacts.
  - **Depends on:** D3.1.
  - **Failing-first / observation:** Record the observed per-row delta against D3.0's prediction; an unpredicted change must be explained before acceptance, never absorbed.
  - **Verify:** `PYTHONPATH=backend:. python3 scripts/eval_routing_truth_set.py --arm both --json /tmp/plan4-d3-after.json` plus an explicit diff against `/tmp/plan4-d3-before.json` and `docs/evals/routing_truth_set_baseline_v1.json`; `PYTHONPATH=backend:. python3 scripts/eval_routing_truth_set.py --check --baseline docs/evals/routing_truth_set_baseline_v1.json`; `TELEMETRY_MODE=none PYTHONPATH=backend:. python3 scripts/audit_reference_probes.py --check`; `PYTHONPATH=backend:. python3 scripts/eval_out_of_set_soc.py --check`; `PYTHONPATH=backend:. python3 scripts/run_production_parity_eval.py --out-dir /tmp/plan4-d3-parity --check` (secondary).
  - **Evidence:** **STOPPED 2026-08-12 — every stated acceptance condition passed, but an UNFORECAST frozen-fixture collision requires a decision.**

    **Acceptance conditions, all met:**

    | Condition | Before | After |
    |---|---|---|
    | advisory-caused capability downgrades = 0 | 5 | **0** |
    | no previously-`route_ok` row becomes wrong | — | **0 regressions** |
    | unsafe containment identical | 13/13 | **13/13** |
    | deterministic arm unchanged | 56/77 | **56/77, 0 rows changed** |
    | advisory-selected | 49/77 | 44/77 |
    | live divergences | 10 | **5** |
    | live `route_ok` | 46/77 | **51/77** |

    All 5 changed rows moved `route_wrong → route_ok`: `rt.ot.001/002/004/005` and `rt.para.002`, each regaining SPL on a concrete detection. New `capability_inconsistent`: **0**.

    **Remaining 5 divergences, explicitly classified** (the fourth acceptance condition): `rt.d2.012/023/030/034/037` — all D2 rows whose deterministic route is the terminal `query_understanding_weak` 0.20 fallback, none a capability downgrade. They are R3-owned by construction: once R3 gives those rows a resolved floor, this same guard protects them with no further advisory change.

    **Gates:** truth-set `--check` **PASS, 0 regressions**; reference probes **10/10**; manifest **`14 checked`, unchanged**; production parity **`total=120 base_105=105 exact=120 approved=0 critical=0`** (secondary evidence, unchanged). `eval_out_of_set_soc --check` **FAILs `15/36 pass, 16 review, 5 fail-critical`** — verified **pre-existing** by stashing the change and re-running: byte-identical result at baseline. That gate is outside the governance regression per `EVAL_CONTRACT.md`.

    **THE STOP — `IN_CATALOGUE_CONTRACT_BASELINE_REFRESH`.** `test_in_catalogue_contract_guard::test_full_guard_passes_against_baseline` and `test_llm_primary_planning::test_in_catalogue_contract_guard_still_green` fail. Causation proven by stash: **15 passed** without the change, **1 failed** with it. D3.0's forecast covered the 87-row truth set and did **not** cover this fixture — recorded as an unforecast collision, not absorbed.

    **Scope: 23 diffs across 5 rows, all `cisco50`, none on the 105.** Fixture: `backend/app/tests/fixtures/in_catalogue_contract/baseline.json` (captured behavior, frozen by `scripts/capture_in_catalogue_contract_fixtures.py --freeze`; **not** in the 14-artifact protected manifest, which stayed clean).

    | Row | Baseline route | After | Bank's own `expected_path_type` |
    |---|---|---|---|
    | `cisco.perim.001` | `alert_summary` | `spl_generation` | `review_only_spl` |
    | `cisco.perim.003` | `knowledge_recall` | `spl_generation` | `review_only_spl` |
    | `cisco.perim.007` | `attack_discovery` | `spl_generation` | `review_only_spl` |
    | `cisco.identity.015` | `attack_discovery` | `spl_generation` | `review_only_spl` |
    | `cisco.ot.030` | `knowledge_recall` | `spl_generation` | `review_only_spl` |

    **The fixture had frozen advisory-chosen routes — the same defect D3 corrects.** Three of the five baseline routes (`alert_summary`, `knowledge_recall` ×2) cannot produce SPL at all, so they contradicted the question bank's own `review_only_spl` expectation for those rows. `cisco.perim.001` is `rt.ot.004` in the truth set, whose independent label is `acceptable_skills=[attack_discovery, spl_generation]`, `required=[spl]` — so `spl_generation` matches the independent adjudication and `alert_summary` did not.

    **No authority widened by the change:** the 3 rows gaining an SPL artifact move to `execution_status: skipped → requires_human_review`, `human_review_required: False → True`, `spl_approved: None → True` (validator-approved **review-only** draft) with `execution_eligible: None → False`. That is strictly *more* gating and an explicitly non-executable artifact.

    **RESOLVED — user approved `BR-a` on 2026-08-12 with constraints; D3.2 CLOSES GREEN.**

    The refresh was **surgical, not `--freeze`**: all 155 fixture rows were captured and compared, and only the 5 approved rows were replaced. Proof rather than assertion — row-key set unchanged (asserted), rows differing from the committed fixture **5**, `unexpected: none` (asserted, would have raised), the other **150 rows byte-identical**, `note`/`question_count`/`schema_version` unchanged, and a guard assertion that **no row anywhere gains `execution_eligible=True`** (verified `none` across the whole fixture).

    | Row | Field | Before → After |
    |---|---|---|
    | `cisco.identity.015` | `route` | `attack_discovery` → `spl_generation` |
    | `cisco.perim.007` | `route` | `attack_discovery` → `spl_generation` |
    | `cisco.perim.001` | `route` | `alert_summary` → `spl_generation` |
    | `cisco.perim.003` | `route` | `knowledge_recall` → `spl_generation` |
    | `cisco.ot.030` | `route` | `knowledge_recall` → `spl_generation` |

    The three whose prior route was SPL-incapable (`alert_summary`, `knowledge_recall` ×2) additionally moved `spl_approved None → True`, `execution_status skipped → requires_human_review`, `human_review_required False → True`, `execution_eligible None → False`, and gained `spl_artifact` in `enabled_sections`. **Why each changed:** every one of the five had `spl_generation` as its deterministic route; the advisory was replacing it and the fixture had captured the replacement. All five carry `expected_path_type: review_only_spl` in the question bank, so the new values agree with the bank's own expectation — and the two rows that changed only `route` were already SPL-capable, which is why nothing else moved for them. Direction of travel is **more** gating, not less.

    **Treated as a captured-behavior fixture correction, not a golden refresh** — proven by scope: `git status` over `backend/app/evals/golden_answers`, `docs/evals/*baseline*` and the three governed registries was **empty**, and the protected manifest reported `14 checked, unchanged` throughout.

    **Closure gates:** full backend **`5109 passed, 3 skipped, 6 xfailed, 0 failed`**; production parity **`total=120 base_105=105 exact=120 approved=0 critical=0`**; Cisco power-grid **`PASS=50 REVIEW=0 FAIL=0 CRITICAL=0`** (run in the exact governance-gate form, `AI_SOC_DISABLE_DOTENV=1 AI_SOC_SPL_DRAFT_PREVIEW_ENABLED=false … --min-wave wave3 --check`); in-catalogue guard + `llm_primary_planning` + advisory authority **30 passed**; truth-set `--check` **PASS, 0 regressions**; reference probes **10/10**; manifest **14/14**; invariants **7/7**.

    **Housekeeping:** two report artifacts (`docs/evals/out_of_set_soc_eval_report.json`, `_summary.md`) were regenerated by the `--check` runs and reverted; later out-of-set runs wrote to scratch paths instead. No unrelated user-owned dirt was staged.

- [x] **R3.0 — Decide the D2 rule — STOP gate `D2_FALLBACK_RULE` — FIRED, awaiting decision**
  - **Do:** Inventory the deterministic signals already available at the terminal fallback in `_route_out_of_registry` (the eight floors above it, `extract_query_signals`, `classify_answer_shape`, `detect_spl_artifact_request`, `_detection_family_match`, `is_unsafe_execution`, `soc_investigation_shaped`). For each of the 39 D2 rows, record which signals are present and which of the eight floors declined it and why. Propose the **narrowest** rule that rescues hunt/detection-shaped misses only. Record explicitly why a blanket `attack_discovery` default is rejected. **Disposition the non-hunt residue explicitly:** rows that keep `knowledge_recall @ 0.20 / tool_plan=["needs_clarification"]` after the fix — including rows where `knowledge_recall` is the *correct* skill but `0.20` and `needs_clarification` still misrepresent a confident answer downstream — must be either accepted with a written reason or covered by a second narrow rule. Leaving the residue unmentioned is not a disposition. **STOP** if the rule cannot be expressed from existing signals without a new classifier, a new flag, or an LLM hop.

    **Also required output — frozen-baseline collision forecast.** The 39 D2 rows overlap `docs/evals/intent_out_of_set_probes.json`, whose frozen baseline `intent_out_of_set_probes_baseline.json` sits in `PROTECTED["eval_baselines"]`, and R3.2's Verify runs `eval_out_of_set_soc.py --check`. The D2 fix is *designed* to change routes on exactly those rows. Before implementing, measure and record the predicted impact on that frozen baseline and on the reference probes (the reference-taxonomy floor fires before the new branch, so probes are expected safe — **prove it, do not assume it**). If any pinned row would change, that is a foreseen re-baseline decision surfaced **here**, for the user, not drift discovered at R3.2.
  - **Why:** Replacing a universal default with a different universal default trades one blunt instrument for another; the 39 rows are heterogeneous (hunt, guidance, out-of-scope, unsafe).
  - **Uses the production-final route, not the deterministic floor.** D3 must be resolved and measured first; R3.0's per-row signal analysis, predictions and OFF/ON acceptance all read the **live arm** as the authority, with the deterministic arm reported alongside. Predicting against a layer the host overrides was the defect D3 exists to remove.
  - **Surfaces:** Plan Evidence + an options table; no runtime edit in this item.
  - **Depends on:** R1.5.
  - **Failing-first / observation:** Observation only. The rule must be stated with its predicted per-row effect on all 39 rows **before** implementation, so R3.2 can falsify it.
  - **Verify:** Options table records, per candidate rule, predicted rescued / unchanged / newly-wrong counts across the 39; the selected rule names the exact signals it reads and the exact position it occupies relative to the eight existing floors; the frozen-baseline collision forecast is recorded with measured per-row predictions for `intent_out_of_set_probes_baseline.json` and the reference probes.
  - **Evidence:** **ANALYSIS COMPLETE 2026-08-12. STOP gate `D2_FALLBACK_RULE` FIRED — a hunt-discriminating ninth rule cannot be built from existing deterministic signals. Options presented; nothing implemented.**

    **The out-of-set gate is dispositioned first, as required. All 5 criticals are eval-instrumentation false positives; zero are runtime defects and zero are D2-related.**

    | Row | Reason | Actual cause | D2 rule effect |
    |---|---|---|---|
    | `oos.analytics.01` | forbidden `'executed'` | matches **"No executed evidence"** | unchanged |
    | `oos.unsafe.04` | forbidden `'executed'` | matches **"Splunk search execution is blocked"** | unchanged |
    | `oos.ot.01` | forbidden `'executed'` | matches **"Execution: Not executed"** | unchanged |
    | `oos.mcp_unavailable.02` | forbidden `'executed'` | same | unchanged |
    | `oos.paraphrase105.04` | confirmed-compromise claim | matches the guardrail's own `unsupported_claims_avoid: ['confirmed compromise', …]` list | unchanged |

    Mechanism verified in code: `expected_must_not_include` is a **bare substring** test (`out_of_set_eval.py:133-135`) and `_prose()` (`:62-70`) concatenates *every* string and list value in `analyst_response`, so the runtime's honest disclosures and the prohibition list itself are both scanned. The COMPROMISE regex (`:120`) found **6 matches, 0 negation matches** on `oos.paraphrase105.04`, all inside `unsupported_claims_avoid`. The clean-answer eval already solves this with `_EXECUTION_NEGATED`; this eval has no equivalent. Classification: **unrelated historical drift in the eval instrument**. Correcting it means editing the corpus fixture or the detector and is **not** taken here.

    **Secondary finding, reported not scoped:** `oos.paraphrase105.04` ("Whcih systems pushed unusually large data volumes outbound?") routes `guided_investigation` at 0.42 via `guided_investigation_rescue` — a *resolved* floor, so never a D2 row — and guided then hard-depends on the LLM planner, degrading to "planner unavailable". A hunt-shaped paraphrase being captured by guided rescue and then made LLM-dependent is a distinct defect from D2.

    **The D2 premise does not survive independent labelling.** Measured on the 39 D2 rows against the truth set:

    | | Deterministic arm | Live arm (post-D3, **the authority**) |
    |---|---|---|
    | route distribution | `knowledge_recall` 39 | `knowledge_recall` 34, `spl_generation` 2, `attack_discovery` 2, `alert_summary` 1 |
    | `route_ok` | **38 / 39** | **33 / 39** |
    | `route_wrong` | `rt.d2.003` | `rt.d2.003` + `rt.d2.012/023/030/034/037` |
    | `capability_inconsistent` | **3** — `rt.d2.003`, `rt.d2.010`, `rt.d2.017` | same |

    **D2 is not a 39-row defect. It is a 3-row defect, of which 1 is a wrong route.** `knowledge_recall` *is* an acceptable skill for 38 of the 39 — they are guidance, policy and out-of-scope asks, exactly what the audit's row-count framing obscured. The remaining 5 live-arm failures are the D3 residue on rows the advisory still reaches because their deterministic route carries `["needs_clarification"]`.

    **Why the eight floors declined — the same answer for all 39, and it is not an oversight.** Of **112** signal keys, the highest coverage across these rows is `security_log_investigation` at 11/39; `classify_answer_shape` returns `hunt` for **39/39**, which is its **no-match default** (`answer_shape_router.py:272`), so it carries zero information here. `detect_spl_artifact_request`, `_detection_family_match`, `detect_investigation_request` and `soc_investigation_shaped` are **0/39**. The floors declined because there is genuinely nothing to read.

    **No existing signal isolates the three SPL-needing rows.** `rt.d2.010` and `rt.d2.017` have **zero** non-null signals. `rt.d2.003` carries `soc_detection_intent` + `guidance_request`, and `soc_detection_intent` fires on 9 rows of which only that one needs SPL — precision **1/9**; it is a "security topic" signal, not a "needs SPL" signal. The narrowest refinement tried, `soc_detection_intent AND NOT explicit_search_intent`, selects `{rt.d2.003, rt.d2.020}`: it fixes one row and breaks one (`rt.d2.020` is labelled `required=['rag']`, `acceptable=[guided_investigation, knowledge_recall]`), i.e. **net zero**.

    **A blanket `attack_discovery` default is rejected on measurement, not on principle:** it would move 38 correctly-routed rows to a wrong route to fix 1, and would hand SPL+MCP capability to policy, out-of-scope and unsafe-shaped asks.

    **Non-hunt residue, dispositioned explicitly (the item's own requirement).** The 36 non-SPL rows are *correctly routed* to `knowledge_recall`, but they are delivered with `confidence 0.20` and `tool_plan ["needs_clarification"]` — a contract that misrepresents a confident knowledge answer to every downstream consumer, and, since D3, is precisely the marker that leaves them advisory-replaceable. That is the residue, and it is a **contract** defect rather than a routing defect.

    **Unsafe/action containment cannot enter any proposed branch.** 11 of the 39 are labelled `clarification`; all 11 measure `execution_enabled=False` today, and both R3 options below are gated behind the existing unsafe checks (`is_unsafe_execution`, `block_or_contain`, `run_execution`, `command_mode_active`) which fire *before* the terminal fallback is reached. `rt.d2.016`'s known detector gap is unchanged by either option — its containment is enforced downstream at `clarification_required` / `execution_enabled=False`, pinned by test.

    **Options, with forecasts.**

    - **R3-A — no routing rule; correct the terminal contract only.** Keep `knowledge_recall`, but stop emitting the `["needs_clarification"]` / 0.20 signature on rows that are a settled knowledge answer. Forecast: **0** deterministic route changes; **the 5 remaining D3 divergences resolve for free**, because a resolved tool plan makes those rows non-replaceable under D3's guard — live `route_ok` 33 → **38/39**. Does **not** fix the 3 SPL rows. Requires a collision forecast against the frozen out-of-set and in-catalogue fixtures before implementation.
    - **R3-B — a signal-based ninth rule.** Blocked: needs a new classifier. **STOP.**
    - **R3-C — accept D2 as measured and close it.** Record that 38/39 are correctly routed, that the 3 SPL rows need a capability signal the system does not have, and carry them as a known gap.

    **Recommendation: R3-A**, scoped as a contract correction, with R3-B's 3 rows carried as an explicit known gap. R3-A is the only option that improves a measured number without inventing a classifier, and it composes with D3 rather than fighting it. It is **not** implemented — the item stops here for the decision.

- [ ] **R3.1 — Implement the D2 correction**
  - **Do:** Implement the R3.0 rule in `select_route_from_understanding.py` as an additional narrow branch **before** the terminal `LOW_CONFIDENCE_ROUTE`, reusing an existing route builder (`_route_detection_spl` or `_route_guided_investigation_rescue`) — do not introduce a new route shape. Preserve every earlier floor's precedence unchanged. Unsafe/action asks must be unreachable by the new branch by construction, not by ordering luck.
  - **Why:** The residue after eight floors is the only safe place to intervene without disturbing measured behavior.
  - **Surfaces:** `backend/app/routing/select_route_from_understanding.py`; `backend/app/tests/test_out_of_registry_terminal_fallback.py` (NEW).
  - **Depends on:** R3.0.
  - **Failing-first / observation:** New tests must fail before the change: at least one hunt-shaped D2 row asserting a non-`knowledge_recall@0.20` route, and at least three unsafe rows asserting containment is **unchanged**. Record both pre- and post-change outputs.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_out_of_registry_terminal_fallback.py app/tests/test_select_route_from_understanding.py app/tests/test_skill_router.py -q`; `python3 scripts/freeze_execution_baseline.py --check --in /tmp/plan4-routing-baseline.json`.
  - **Evidence:** _(fill when done)_

- [ ] **R3.2 — Measure D2 OFF/ON and accept or revert**
  - **Do:** Re-run the routing evaluator and compare against the frozen R1.5 baseline. Accept only if hunt under-routing falls, unsafe containment is **byte-identical**, and no previously-`route_ok` row regresses. Run the answer-parity gate as **secondary** regression evidence and record it as such — a `120 exact` result is not evidence the routing change is correct. Revert if any acceptance condition fails.
  - **Why:** The rule's predicted effect from R3.0 must be falsifiable against measurement.
  - **Surfaces:** Plan Evidence; `/tmp` comparison artifacts only.
  - **Depends on:** R3.1.
  - **Failing-first / observation:** Record the observed per-row delta against R3.0's prediction; an unpredicted change is a finding that must be explained before acceptance, not a rounding error.
  - **Verify:** `PYTHONPATH=backend:. python3 scripts/eval_routing_truth_set.py --json /tmp/plan4-r3-on.json` plus an explicit diff against `docs/evals/routing_truth_set_baseline_v1.json`; `TELEMETRY_MODE=none PYTHONPATH=backend:. python3 scripts/audit_reference_probes.py --check`; `PYTHONPATH=backend:. python3 scripts/eval_out_of_set_soc.py --check`; `PYTHONPATH=backend:. python3 scripts/run_production_parity_eval.py --out-dir /tmp/plan4-r3-parity --check` (secondary).
  - **Evidence:** _(fill when done)_

- [ ] **R2.0 — Classify the D1 rows — STOP gate `D1_SKILL_OWNERSHIP`**
  - **Do:** For each of the 15 D1 rows, classify the ask as `summarize_or_explain_a_supplied_alert` / `investigate_or_find_activity` / `knowledge_or_reference_lookup`, using the R1.3 labels (which were adjudicated independently) as the truth. Separate the `knowledge_recall` rows (`asset_identity_context` ×5, `data_source_health` ×2, `threat_intel_enrichment` ×1) from the `alert_summary` rows (`notable_risk_lookup` ×5, `case_state_lookup` ×2). **STOP with options** for any pattern class whose correction requires deciding which skill *owns* a capability — specifically whether a notable/risk-index lookup is an `alert_summary` capability or belongs to a hunt skill. Do not change registry semantics silently.

    **Also required output — a measured golden-answer impact set, and the approval (if any) that R2.1 depends on.** `run_production_parity_eval.py` compares live output against the frozen `backend/app/evals/golden_answers/question_105_golden.jsonl`, which is in `PROTECTED["golden_answers"]`; `exact=120` means byte-identical to those answers. A route change *may* change a row's answer bytes — but **do not assume it does**. Answer text is skill-dependent in general, yet these 15 rows already produce SPL-absent answers (`spl_status=none` on 113/120), so some corrections may be answer-neutral exactly as Plan 3's B2 turned out to be.

    **Measure first, then ask, and only for what actually moved:**
    1. Apply the proposed hint changes in a **temporary, in-memory arm** — a monkeypatched `LEGACY_ROUTER_INTENT_BY_PATTERN` / regenerated map in a scratch path. Nothing committed, no tracked file written, working tree unchanged at item close.
    2. Run parity in that arm and diff per row against the frozen goldens. Record the **actual** impact set: which `row_id`s change bytes, and what changes in each.
    3. If the impact set is **empty**, R2.1 needs no golden approval — record that finding and proceed.
    4. If non-empty, request golden-refresh approval **scoped to exactly those rows**, presenting the measured diff. Refresh, if approved, is recorded as its own decision — never as a side effect of a gate run.

    R2.1 starts when either the impact set is empty or the scoped approval is recorded; if approval is withheld for a non-empty impact set, R2.1 closes `NOT_AUTHORIZED` for the affected classes with the measurement recorded, and any answer-neutral classes may still proceed.
  - **Why:** The `alert_summary` rows are legitimately multi-valid; treating them as bugs would be the same over-reach the audit warned against.
  - **Surfaces:** Plan Evidence + options table; no registry edit in this item.
  - **Depends on:** R3.2.
  - **Failing-first / observation:** Observation only. Record per row: R1.3 label, current hint, classification, and confidence.
  - **Verify:** All 15 rows classified with rationale; every `alert_summary` row either has an evidence-backed classification or is escalated as a decision with both options stated; the golden impact set is **measured** (temporary arm, per-row parity diff) rather than predicted, and the working tree is unchanged at item close (`git status --short -- backend tools` empty, `python3 scripts/freeze_execution_baseline.py --check --in /tmp/plan4-routing-baseline.json` passes).
  - **Evidence:** _(fill when done)_

- [ ] **R2.1 — Correct the clear-cut `knowledge_recall` contradictions**
  - **Do:** **Precondition, per pattern class:** the class is answer-neutral in R2.0's measured impact set, **or** a scoped golden-refresh approval covering its rows is recorded. Classes meeting neither close `NOT_AUTHORIZED` without touching the registry, while answer-neutral classes proceed. For the pattern classes R2.0 classified as clear-cut **and** cleared by this precondition, change `LEGACY_ROUTER_INTENT_BY_PATTERN` and regenerate `backend/app/coverage/question_runtime_map_v1.json` through its authoring tool (`tools/coverage_authoring/question_runtime_map_builder.py`) — never by hand-editing the JSON. Update any assertion that R1.6 left referencing the changed hint values.
  - **Why:** The map is a generated artifact; hand-editing it creates drift that the next regeneration silently reverts.
  - **Surfaces:** `tools/coverage_authoring/pattern_runtime_mapping.py`; `backend/app/coverage/question_runtime_map_v1.json` (regenerated); `backend/app/tests/test_query_understanding_stage3je.py`.
  - **Depends on:** R2.0.
  - **Failing-first / observation:** Confirm the regenerated map differs from the committed one **only** in the intended `legacy_router_intent_hint` fields — diff the JSON and record the field-level delta. Any other change is a stop condition.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_query_understanding_stage3je.py app/tests/test_cisco_question_runtime_map.py -q`; `PYTHONPATH=backend:. python3 scripts/eval_105_path_honoring.py --check`; `PYTHONPATH=backend:. python3 scripts/eval_routing_truth_set.py --json /tmp/plan4-r2-on.json`.
  - **Evidence:** _(fill when done)_

- [ ] **R2.2 — Dispose of the `alert_summary` rows**
  - **Do:** Either apply the correction the user authorized at R2.0's stop gate, or — if no authorization was given — record the rows as an explicit deferred decision with both options, their measured cost, and the reason no change was made. Both outcomes close the item; silently changing them does not.
  - **Why:** Skill ownership is a product decision, not an engineering inference.
  - **Surfaces:** Plan Evidence; registry files only if authorized.
  - **Depends on:** R2.1.
  - **Failing-first / observation:** If a change is applied, the same field-level diff discipline as R2.1 applies.
  - **Verify:** If changed, the R2.1 Verify chain re-run; if deferred, the deferral is recorded in this plan's *Deferred decisions* section with both options and measured cost.
  - **Evidence:** _(fill when done)_

- [ ] **E0 — Full routing evaluation, baseline vs proposed**
  - **Do:** Produce `docs/evals/routing_evaluation_report_v1.md`: baseline vs proposed across correct/acceptable route rate, capability-contradiction rate, knowledge-only false escalation, hunt/detection under-routing, unsafe-action containment, ambiguous rows, and answer parity **labelled explicitly as secondary regression evidence**. State plainly which of D1/D2 was closed, which was deferred, and what the truth set still cannot measure.
  - **Why:** The plan's deliverable is a defensible routing verdict, not a diff.
  - **Surfaces:** `docs/evals/routing_evaluation_report_v1.md` (NEW).
  - **Depends on:** R2.2.
  - **Failing-first / observation:** Every number in the report must be traceable to a committed artifact or a recorded command; any number that is not is removed.
  - **Verify:** Each reported figure re-derivable by re-running the named command; the report states the truth set's own limits (size, label confidence distribution, ambiguous count).
  - **Evidence:** _(fill when done)_

- [ ] **G0 — Align documentation with what was proven**
  - **Do:** Update `CLAUDE.md`, `plans/README.md` and the relevant `docs/architecture/` page for the routing changes actually made. Add to `docs/evals/EVAL_CONTRACT.md` that **production parity measures answer stability, not routing correctness** — `spl_status` is `none` on 113/120 frozen rows, so parity cannot observe D1 or D2 — and name the routing truth set as the gate that can. Without this, `120 exact` keeps being cited as routing evidence, which is the misreading that let D1 sit unmeasured. Record `UNDERSTANDING_ROUTER_ON_LOW_CONFIDENCE` as **retired with evidence**, not deferred. If `docs/architecture/details.html` changes, update all three published mirrors identically and rebuild `frontend/dist`.
  - **Why:** Plan 3 closed with a known gap that this plan resolves; leaving the old framing in place invites its re-proposal.
  - **Surfaces:** `CLAUDE.md`; `plans/README.md`; `docs/architecture/*`; mirrors if touched.
  - **Depends on:** E0.
  - **Failing-first / observation:** Documentation only. No claim may exceed E0's measured evidence.
  - **Verify:** `git diff --stat` limited to docs; if mirrors changed, all three byte-identical and `cd frontend && npm run build` passes.
  - **Evidence:** _(fill when done)_

- [ ] **G1 — Close Plan 4**
  - **Do:** Re-audit every checkbox against its recorded evidence, run the full gate chain, record the item disposition, commits, and any gaps carried forward.
  - **Why:** A plan is closed by measurement, not by assertion.
  - **Surfaces:** This plan file; `plans/README.md`.
  - **Depends on:** G0.
  - **Failing-first / observation:** Any unchecked or undecided item is a stop condition.
  - **Verify:** `./scripts/run_stage3_governance_regression.sh`; `cd backend && PYTHONPATH=../backend:.. python3 -m pytest -q`; `PYTHONPATH=backend:. python3 scripts/run_production_parity_eval.py --out-dir /tmp/plan4-g1-parity --check`; `TELEMETRY_MODE=none PYTHONPATH=backend:. python3 scripts/audit_reference_probes.py --check`; `PYTHONPATH=backend:. python3 scripts/eval_out_of_set_soc.py --check`; `PYTHONPATH=backend:. python3 scripts/eval_routing_truth_set.py --check --baseline docs/evals/routing_truth_set_baseline_v1.json`; `python3 scripts/freeze_execution_baseline.py --check --in /tmp/plan4-routing-baseline.json`; `.cursor/hooks/audit-plan-discipline.sh plans/2026-08-11_1834_routing-evaluation-and-authority-corrections.md`; `/invariant-check` across `93562c1`→HEAD.
  - **Invariant / manifest:** Cumulative invariant check, all seven groups must PASS.
  - **Commit boundary:** Final evidence/closure commit only.
  - **Stop:** Any unchecked or undecided item; invariant FAIL; protected drift; baseline refresh; unapproved authority; same valid gate failing twice.
  - **Evidence:** _(fill when done)_

## Protected artifacts and baseline policy

P0 captures `/tmp/plan4-routing-baseline.json` using the existing 13-artifact guard; R1.5 extends it to 14 by adding the new routing baseline. Eval/reference baselines, the 105 answer goldens and governed registries are **immutable**; all probes use `--check`. The only registry-class file this plan may change is `LEGACY_ROUTER_INTENT_BY_PATTERN` plus its generated map, and only under R2.0's recorded decision. Published doc mirrors stay mutually identical. Run the manifest before and after every runtime item; unexpected drift is a stop condition, never a warning. `/tmp` observation artifacts are not committed.

## Global stop conditions

1. A routing label cannot be settled without an architecture decision (`ROUTING_LABEL_AMBIGUITY`).
2. Skill or registry ownership must be decided (`D1_SKILL_OWNERSHIP`).
3. The D2 rule cannot be expressed from existing deterministic signals (`D2_FALLBACK_RULE`).
4. Any capability or execution authority would expand.
5. Protected artifacts drift unexpectedly.
6. The same valid verification gate fails twice on one item.
7. A safety boundary cannot be preserved — unsafe/action containment must be identical in every arm.
8. A baseline, golden or governed registry would need refreshing — **unless** the need was *measured* at R2.0/R3.0 and separately approved by the user, scoped to exactly the rows the measurement showed change.
9. **Any proposal to rewrite the answer goldens so routing looks better.** This is a hard stop with no exception.
10. An LLM would be introduced into a routing decision path.

Do not silently adapt, skip, weaken a test, or change a recorded decision.

## Verification gaps

Tests marked **NEW** are created in their owning item. R3.0's and R2.0's observation tables are intentionally not prewritten; their exact contents are recorded in the owning item's Evidence before any implementation follows.

## Deferred decisions (recorded, not approved)

### `IN_CATALOGUE_CONTRACT_BASELINE_REFRESH` — **RESOLVED: user approved `BR-a` 2026-08-12, scoped to the 5 measured rows. Applied surgically and verified; D3 closed green at `a66540c`.**

D3.1's correction changes 5 `cisco50` rows in the frozen fixture `backend/app/tests/fixtures/in_catalogue_contract/baseline.json` (23 field diffs; the 105 are untouched). Every D3.2 acceptance condition passed; this is the only blocker.

The fixture is **captured behavior**, not a hand-authored contract, and what it captured was advisory-chosen routes — three of which (`alert_summary`, `knowledge_recall` ×2) cannot produce SPL and therefore contradicted the question bank's own `expected_path_type: review_only_spl` for those same rows.

**Options:**
- **BR-a — refresh the fixture**, scoped to exactly these 5 rows, recording the before/after diff as the justification. The new values agree with the bank's stated expectation and, for `cisco.perim.001`, with this plan's independent label.
- **BR-b — revert D3.1.** Keeps the fixture untouched at the cost of leaving the advisory able to override deterministic and registry-backed routes, which is the defect the user scoped as blocking.
- **BR-c — narrow D3.1 further to exempt Cisco-50 rows.** Rejected on merit: these 5 are the same defect class, so exempting them would special-case the fixture rather than the behavior.

**Recommendation: BR-a.** No execution authority widens — the affected rows gain a validator-approved **review-only** SPL behind `human_review_required=True` with `execution_eligible=False`. Refreshing a captured-behavior fixture whose captured behavior is the defect under repair is the honest resolution; reverting would preserve a frozen record of the bug.

### `D3_LLM_ADVISORY_HOLDS_FINAL_ROUTE` — **DECIDED `D3-c` by user, 2026-08-12. Scoped as blocking items D3.0/D3.1/D3.2 above; R3 may not start until D3 is resolved and measured.**

**Measured on this host, all 77 gating truth-set rows, `routing_mode=llm_assisted_semantic`:**

| Observation | Value |
|---|---|
| rows whose final route is chosen by `selected_by=llm_advisory_validated` | **49 / 77 (64%)** |
| rows where the full router diverges from the deterministic floor | **10** |
| divergences that **degrade** the route (deterministic acceptable → live unacceptable) | **10** |
| divergences that improve the route | **0** |

Degraded rows: `rt.ot.001`, `rt.ot.002`, `rt.ot.004`, `rt.ot.005` (concrete SCADA/Modbus/AMI detections demoted `spl_generation → knowledge_recall`/`alert_summary`, losing SPL); `rt.para.002` (IOC hunt demoted `spl_generation → knowledge_recall`); `rt.d2.012`, `rt.d2.023` (`knowledge_recall → spl_generation` on documentation asks); `rt.d2.030`, `rt.d2.037` (`knowledge_recall → attack_discovery`); `rt.d2.034` (`knowledge_recall → alert_summary`).

**This contradicts a documented architecture claim.** `CLAUDE.md` states LLM route suggestions are "advisory only, normalized through deterministic registries; **final route selection stays deterministic**". Measured, final route selection is *not* deterministic on out-of-registry paths: `_qu_route_retains_authority` returns false there, so the validated advisory wins. Registry-backed paths are unaffected (13 rows kept `query_understanding_105`).

**Why it blocks R3.0's framing rather than just being noted.** D2 lives entirely on out-of-registry paths — exactly where the advisory holds authority. A deterministic fix to the terminal fallback can therefore be silently overridden, or amplified, by the advisory on the same rows (5 of the 39 D2 rows already diverge). R3.0's per-row predictions and its OFF/ON acceptance would be measuring a layer that is not the final authority on this host.

**Decision: `D3-c`.** Treated as a blocking routing-authority defect and corrected inside Plan 4, ahead of R3. My recommendation had been `D3-b` (report the divergence, fix it later); the user chose to fix it, and the subsequent root-cause measurement supports that call — see below.

**Root cause, measured after the decision.** `_deterministic_uncertain` (`governance.py:397-414`) returns `True` for **every** `out_of_registry` row through the blanket clause `match_path in {"near_105_question", "out_of_registry"}` — independent of the deterministic route's own confidence or of *which* floor produced it. So a reasoned decision from one of the eight out-of-registry floors (e.g. `out_of_registry_detection_family_floor → spl_generation`, confidence 0.5) is labelled "uncertain" and replaced at `governance.py:251`. The advisory is not overriding a weak guess; it is overriding a specific deterministic conclusion.

**Correction contract set by the user, encoded in D3.0–D3.2:** deterministic/query-understanding routing stays authoritative · the advisory may enrich or confirm but may not independently replace the authoritative route nor reduce required capabilities · registry-backed behavior unchanged · unsafe containment identical · no new LLM authority · all 77 rows measured before and after. Acceptance requires **0** advisory-caused capability downgrades, **no** previously-correct deterministic route becoming wrong, unchanged containment, and an explicit report of any remaining deterministic-vs-live difference.

Not a safety finding: unsafe containment stayed **13/13** in the deterministic arm, and no divergence enabled execution.

### `ALERT_SUMMARY_NOTABLE_OWNERSHIP` — OPEN, blocking R2.0/R2.1 scope (raised at R1.3, 2026-08-12)

Nine rows cannot be labelled without deciding whether a notable/risk/case-state lookup is an `alert_summary` capability. Both readings are recorded per row; neither is encoded.

- **Reading A** — it *is* an `alert_summary` capability. Current routing is right; but `alert_summary` grants neither `spl` nor `mcp` today, so those questions have **no** route to the notable index at all. Closing A means adding a retrieval capability to the skill contract, i.e. widening a contract.
- **Reading B** — it is live-data retrieval like any other, so an SPL-capable hunt skill owns it. Current routing is wrong on those rows; the fix is the pattern→skill table only, no contract change.

Affected: `rt.d1.001/004/007/008/009` (`notable_risk_lookup`), `rt.d1.010/015` (`case_state_lookup`), `rt.para.010/015`.

**Scope may be wider than 7 rows.** The blind labeller independently applied the same doubt to `rt.d1.005` (`asset_identity_context`) and `rt.d1.012` (`data_source_health`) — rows this plan assumed clear-cut. If the user's decision extends there, R2.1's "clear-cut `knowledge_recall`" group shrinks from 8 rows.

_(R2.2 writes here if the `alert_summary` disposition is deferred.)_

## Drift log

| Date | Note |
|------|------|
| 2026-08-11 | Plan created at `93562c1` from `docs/evals/golden_routing_audit_2026-08-11.md`. `UNDERSTANDING_ROUTER_ON_LOW_CONFIDENCE` recorded as **retired**, superseding Plan 3's "deferred" framing, on measured evidence that the keyword router holds no routing authority on the 105. |
| 2026-08-11 | **Two user corrections applied after P0, before R1.1.** (1) The locked invariant "Deterministic planning remains the routing authority" **conflated two distinct authorities** and is split: production *routing* stays deterministic/governed (this plan's subject), and Plan 2's deterministic *ResourcePlan planning* authority is unchanged and out of scope. (2) R2.0's golden-refresh gate assumed a route correction **will** change answer bytes. It is now **measurement-first**: apply the proposed hints in a temporary in-memory arm, diff parity per row against the frozen goldens, and request approval only for rows that actually move — scoped per pattern class, so answer-neutral classes proceed without any approval. Plan 3's B2 is the precedent: a capability change measured `120 exact`. Stop-condition 8, R2.1's precondition and the residuals section were realigned to match. |
| 2026-08-11 | **Second pre-execution review — "will this remove all the issues?" Answer: no, and the plan now says so.** Six patches, none changing scope: (a) new item **R1.6** pulls the de-circularization of `test_query_understanding_stage3je.py:84` out of R2.1, so a withheld golden-refresh approval can no longer leave the circular pin in place forever; (b) R1.2 gains a quota for `_keyword_fallback` / `_qu_failover_route` — the only two production paths where the keyword router actually decides, previously unmeasured by a benchmark built to measure routing; (c) R1.3 gains three checkable independence mechanisms (label-file SHA256 order commitment, blind second-labeller agreement on a ~20-row subset, and forced `ambiguous=true` on the 7 `alert_summary` rows so R1.3 cannot pre-decide R2.0's gate); (d) R3.0 must now disposition the non-hunt D2 residue explicitly, including rows where `knowledge_recall` is right but `0.20 / needs_clarification` still misrepresents it; (e) R1.5 records the deterministic-only coverage limit plus a 10-row live-arm observation, since production runs `llm_assisted_semantic`; (f) G0 must record in `EVAL_CONTRACT.md` that parity measures answer stability, not routing correctness. A new **"What this plan does NOT close"** section states the four residual limits, headed by the fact that D1 can legitimately close at 0/15 corrected. |
| 2026-08-11 | **Pre-execution review found four content deadlocks in the first draft; all patched before P0.** (A) R2.1 changes routing on golden rows, whose answers are compared byte-exact by `run_production_parity_eval.py` against a PROTECTED golden file — the plan as drafted could not both apply R2.1 and close G1. A golden-refresh **forecast + separate approval** is now a required R2.0 output and an R2.1 precondition; without approval R2.1 closes `NOT_AUTHORIZED`. Stop-condition 8 amended to admit only forecast, approved, row-scoped refreshes. (B) Same collision, smaller, between the 39 D2 rows and the PROTECTED `intent_out_of_set_probes_baseline.json`; a collision forecast is now a required R3.0 output, with the reference-probe safety claim required to be *proven*, not assumed. (C) `eval_routing_truth_set.py --check` was implicitly identity-against-baseline, which passes trivially at R1.5 and fails by construction at G1 since R3/R2 exist to improve on it; `--check` is now defined as **no-regression** (no `route_ok`→`route_wrong` flips, no new `capability_inconsistent`). (D) R1.2's coverage minimums summed to 89 against a `[60,80]` gate; quotas are now explicitly overlapping and the bound is `[60,95]`. Also clarified that `resolve_capability_compatibility` has no labelled-capability parameter, so the evaluator checks labelled capabilities through the same permit primitive rather than contorting that call. |
