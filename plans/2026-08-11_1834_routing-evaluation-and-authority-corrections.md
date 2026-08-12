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
| `D2_FALLBACK_RULE` | R3.0 | STOP if the narrowest safe rule cannot be expressed from existing deterministic signals and would require a new classifier, a new flag, or an LLM hop. |
| `D1_SKILL_OWNERSHIP` | R2.0 | STOP with options if correcting a pattern class requires deciding which skill *owns* a capability (all `alert_summary` rows are presumed to be in this class until proven otherwise). |

## Dependency order

`P0 → R1.1 → R1.2 → R1.3 (STOP on ambiguity) → R1.4 → R1.5 → R1.6 → R3.0 (STOP on rule) → R3.1 → R3.2 → R2.0 (STOP on ownership) → R2.1 → R2.2 → E0 → G0 → G1`

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

- [ ] **R1.3 — Adjudicate labels independently — STOP gate `ROUTING_LABEL_AMBIGUITY`**
  - **Do:** Label every row's expected fields **without consulting** `legacy_router_intent_hint`, `proposed_primary_skill`, or the observed route; derive each label from the query text plus documented policy (`HUNT_PATTERNS`, the analytics severity guard, skill capability contracts, the unsafe/action lane). Use `acceptable_skills` sets wherever more than one route is legitimately valid. Set `ambiguous=true` + `label_confidence=low` and record both candidate readings for any row whose label depends on an unresolved architecture question — do **not** guess. **STOP and present options** if any row's label cannot be settled without a skill-ownership or capability-ownership decision.

    **Label independence is procedural, not structural — three mechanisms make it checkable.** The labeller has already seen production routes for many of these rows in the audit that produced this plan, so `labeled_without_registry_hint=true` is a self-attestation and nothing more. (1) **Order commitment:** write the completed label file, record its SHA256 in Evidence, and only then run the evaluator; any later label edit must be recorded as an explicit relabel with its reason, never as a silent correction. (2) **Blind second labeller:** have an independent labeller (a subagent given the queries and the contract, but **not** this plan, the audit report, or any observed route) label a ~20-row subset; record inter-labeller agreement as a number. Disagreements are findings to adjudicate, not rows to overwrite. (3) **Forced ambiguity:** the 7 `alert_summary` D1 rows (`notable_risk_lookup` ×5, `case_state_lookup` ×2) are set `ambiguous=true` **by rule**, because their label *is* the R2.0 ownership question — labelling them confidently here would pre-decide the gate that R2.0 exists to escalate.
  - **Why:** The benchmark's whole value is independence from the thing it measures.
  - **Surfaces:** `docs/evals/routing_truth_set_v1.json` (expected fields populated).
  - **Depends on:** R1.2.
  - **Failing-first / observation:** Record, before labelling, that observed routes were not read for the rows being labelled. After labelling, compute and record agreement with the current production route — as an **observation**, never as a correction step; a low agreement rate is a finding, not a reason to relabel.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_routing_truth_set_schema.py -q` (all rows now complete); every `ambiguous=true` row carries two documented readings; the 7 `alert_summary` D1 rows are `ambiguous=true`; label-file SHA256, blind-subset inter-labeller agreement, and the count of `label_confidence=low` rows recorded in Evidence.
  - **Evidence:** _(fill when done)_

- [ ] **R1.4 — Build the routing evaluator**
  - **Do:** Add `scripts/eval_routing_truth_set.py` — in-process, deterministic, no LLM, no live backend. Per row: `understand_query` → `select_route_from_understanding` → `build_query_to_intent` → `plan_evidence` → `plan_path_and_tools`; then score `route_ok` against `acceptable_skills`. Evaluate the capability invariant against the **labelled** `required_capabilities` (not the classifier's intent family) by asking the selected skill's contract, per capability, through the same permit primitive Plan 3 B2 uses — `skill_intent_compatibility._contract_grants` / `composer._skill_permits`. Note the API shape: `resolve_capability_compatibility(routed_skill, intent_family, skill_contract)` has **no** parameter for labelled capabilities, so call it for the *observed* pairing (to report the runtime's own resolution) and check the labelled capabilities separately through the permit primitive. Do not create a second capability table. Emit per-row JSON and the `EVAL_CONTRACT.md` verdict line `RESULT: PASS (n/m rows, …)`, and `--json <path>` for per-row results.

    **`--check` semantics are NO-REGRESSION, not identity.** `--check --baseline <file>` passes when, relative to the baseline: no row flips `route_ok` → `route_wrong`, and no row gains `capability_inconsistent`. Improvements pass. Identity-checking would make the gate pass trivially at R1.5 and fail by construction at G1, since R3/R2 exist to improve on the baseline. `ambiguous` rows report but never gate.
  - **Why:** A benchmark that cannot be re-run identically is an anecdote.
  - **Surfaces:** `scripts/eval_routing_truth_set.py` (NEW); `backend/app/tests/test_routing_truth_set_eval.py` (NEW).
  - **Depends on:** R1.3.
  - **Failing-first / observation:** Unit-test the invariant against a synthetic row whose labelled `required_capabilities={spl}` meets a `knowledge_recall` contract — must report `capability_inconsistent` **while** `route_ok` is true, proving the two axes are independent. Record that output.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_routing_truth_set_eval.py -q`; `PYTHONPATH=backend:. python3 scripts/eval_routing_truth_set.py --json /tmp/plan4-r1-baseline.json` prints a conforming `RESULT:` line; running it twice produces byte-identical per-row verdicts.
  - **Evidence:** _(fill when done)_

- [ ] **R1.5 — Record the OFF (baseline) routing measurement**
  - **Do:** Run the evaluator at unmodified `93562c1` runtime and freeze the result as `docs/evals/routing_truth_set_baseline_v1.json` — this is a **new** baseline for a new artifact, not a refresh of a protected one. Record the full matrix: route-correct rate, capability-contradiction rate, knowledge-only false-escalation count, hunt/detection under-routing count, unsafe-containment count, ambiguous count.

    **Record the benchmark's coverage limit in the baseline file itself.** The evaluator is deterministic-only, but production runs `routing_mode=llm_assisted_semantic`, where the consumer-gated intent advisory can promote a route live. A green truth-set run is therefore evidence about the **deterministic floor**, not about production routing. Additionally run a ~10-row **live-arm observation** through the production routing mode and record the delta as observation only — never a gate, never a reason to relabel. If the live arm diverges materially from the deterministic arm, that is a finding for E0, not a blocker here.
  - **Why:** R3 and R2 are only acceptable if they move these numbers in the right direction; without a frozen OFF arm there is nothing to compare.
  - **Surfaces:** `docs/evals/routing_truth_set_baseline_v1.json` (NEW); add it to `PROTECTED["eval_baselines"]` in `scripts/freeze_execution_baseline.py` so later items cannot silently rewrite it.
  - **Depends on:** R1.4.
  - **Failing-first / observation:** Confirm the baseline reproduces D1 (≥14 `capability_inconsistent` rows among the D1 subset) and D2 (≥1 hunt row terminating on `knowledge_recall @ 0.20`). If it does not, the evaluator is wrong — stop and fix it before proceeding.
  - **Verify:** `PYTHONPATH=backend:. python3 scripts/eval_routing_truth_set.py --check --baseline docs/evals/routing_truth_set_baseline_v1.json`; `python3 scripts/freeze_execution_baseline.py --capture --out /tmp/plan4-routing-baseline.json` re-captured to include the new artifact (14 artifacts) and `--check` passes.
  - **Evidence:** _(fill when done)_

- [ ] **R1.6 — De-circularize the 105 routing pin (independent of any hint change)**
  - **Do:** Rewrite `backend/app/tests/test_query_understanding_stage3je.py:84` so it asserts a **contract** — the resolved route is a valid skill and, for rows present in the truth set, is a member of that row's `acceptable_skills` — instead of asserting identity with `legacy_router_intent_hint`, the label the same file supplies. Keep whatever coverage the existing assertion legitimately provides (registry match source, match path) and record what the identity assertion was actually protecting.
  - **Why:** The circularity is a defect on its own: it makes the router unfalsifiable against its own registry. In the first draft this fix lived inside R2.1, so a withheld golden-refresh approval would have left the circular pin in place indefinitely. It does not depend on any hint value changing, so it is its own item.
  - **Surfaces:** `backend/app/tests/test_query_understanding_stage3je.py`.
  - **Depends on:** R1.5.
  - **Failing-first / observation:** Prove the new assertion has teeth: mutate one row's `legacy_router_intent_hint` in memory to an out-of-set skill and confirm the rewritten test fails. Record the output, then revert the mutation.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_query_understanding_stage3je.py -q`; `PYTHONPATH=backend:. python3 scripts/eval_105_path_honoring.py --check`; `python3 scripts/freeze_execution_baseline.py --check --in /tmp/plan4-routing-baseline.json`.
  - **Evidence:** _(fill when done)_

- [ ] **R3.0 — Decide the D2 rule — STOP gate `D2_FALLBACK_RULE`**
  - **Do:** Inventory the deterministic signals already available at the terminal fallback in `_route_out_of_registry` (the eight floors above it, `extract_query_signals`, `classify_answer_shape`, `detect_spl_artifact_request`, `_detection_family_match`, `is_unsafe_execution`, `soc_investigation_shaped`). For each of the 39 D2 rows, record which signals are present and which of the eight floors declined it and why. Propose the **narrowest** rule that rescues hunt/detection-shaped misses only. Record explicitly why a blanket `attack_discovery` default is rejected. **Disposition the non-hunt residue explicitly:** rows that keep `knowledge_recall @ 0.20 / tool_plan=["needs_clarification"]` after the fix — including rows where `knowledge_recall` is the *correct* skill but `0.20` and `needs_clarification` still misrepresent a confident answer downstream — must be either accepted with a written reason or covered by a second narrow rule. Leaving the residue unmentioned is not a disposition. **STOP** if the rule cannot be expressed from existing signals without a new classifier, a new flag, or an LLM hop.

    **Also required output — frozen-baseline collision forecast.** The 39 D2 rows overlap `docs/evals/intent_out_of_set_probes.json`, whose frozen baseline `intent_out_of_set_probes_baseline.json` sits in `PROTECTED["eval_baselines"]`, and R3.2's Verify runs `eval_out_of_set_soc.py --check`. The D2 fix is *designed* to change routes on exactly those rows. Before implementing, measure and record the predicted impact on that frozen baseline and on the reference probes (the reference-taxonomy floor fires before the new branch, so probes are expected safe — **prove it, do not assume it**). If any pinned row would change, that is a foreseen re-baseline decision surfaced **here**, for the user, not drift discovered at R3.2.
  - **Why:** Replacing a universal default with a different universal default trades one blunt instrument for another; the 39 rows are heterogeneous (hunt, guidance, out-of-scope, unsafe).
  - **Surfaces:** Plan Evidence + an options table; no runtime edit in this item.
  - **Depends on:** R1.5.
  - **Failing-first / observation:** Observation only. The rule must be stated with its predicted per-row effect on all 39 rows **before** implementation, so R3.2 can falsify it.
  - **Verify:** Options table records, per candidate rule, predicted rescued / unchanged / newly-wrong counts across the 39; the selected rule names the exact signals it reads and the exact position it occupies relative to the eight existing floors; the frozen-baseline collision forecast is recorded with measured per-row predictions for `intent_out_of_set_probes_baseline.json` and the reference probes.
  - **Evidence:** _(fill when done)_

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

_(R2.2 writes here if the `alert_summary` disposition is deferred.)_

## Drift log

| Date | Note |
|------|------|
| 2026-08-11 | Plan created at `93562c1` from `docs/evals/golden_routing_audit_2026-08-11.md`. `UNDERSTANDING_ROUTER_ON_LOW_CONFIDENCE` recorded as **retired**, superseding Plan 3's "deferred" framing, on measured evidence that the keyword router holds no routing authority on the 105. |
| 2026-08-11 | **Two user corrections applied after P0, before R1.1.** (1) The locked invariant "Deterministic planning remains the routing authority" **conflated two distinct authorities** and is split: production *routing* stays deterministic/governed (this plan's subject), and Plan 2's deterministic *ResourcePlan planning* authority is unchanged and out of scope. (2) R2.0's golden-refresh gate assumed a route correction **will** change answer bytes. It is now **measurement-first**: apply the proposed hints in a temporary in-memory arm, diff parity per row against the frozen goldens, and request approval only for rows that actually move — scoped per pattern class, so answer-neutral classes proceed without any approval. Plan 3's B2 is the precedent: a capability change measured `120 exact`. Stop-condition 8, R2.1's precondition and the residuals section were realigned to match. |
| 2026-08-11 | **Second pre-execution review — "will this remove all the issues?" Answer: no, and the plan now says so.** Six patches, none changing scope: (a) new item **R1.6** pulls the de-circularization of `test_query_understanding_stage3je.py:84` out of R2.1, so a withheld golden-refresh approval can no longer leave the circular pin in place forever; (b) R1.2 gains a quota for `_keyword_fallback` / `_qu_failover_route` — the only two production paths where the keyword router actually decides, previously unmeasured by a benchmark built to measure routing; (c) R1.3 gains three checkable independence mechanisms (label-file SHA256 order commitment, blind second-labeller agreement on a ~20-row subset, and forced `ambiguous=true` on the 7 `alert_summary` rows so R1.3 cannot pre-decide R2.0's gate); (d) R3.0 must now disposition the non-hunt D2 residue explicitly, including rows where `knowledge_recall` is right but `0.20 / needs_clarification` still misrepresents it; (e) R1.5 records the deterministic-only coverage limit plus a 10-row live-arm observation, since production runs `llm_assisted_semantic`; (f) G0 must record in `EVAL_CONTRACT.md` that parity measures answer stability, not routing correctness. A new **"What this plan does NOT close"** section states the four residual limits, headed by the fact that D1 can legitimately close at 0/15 corrected. |
| 2026-08-11 | **Pre-execution review found four content deadlocks in the first draft; all patched before P0.** (A) R2.1 changes routing on golden rows, whose answers are compared byte-exact by `run_production_parity_eval.py` against a PROTECTED golden file — the plan as drafted could not both apply R2.1 and close G1. A golden-refresh **forecast + separate approval** is now a required R2.0 output and an R2.1 precondition; without approval R2.1 closes `NOT_AUTHORIZED`. Stop-condition 8 amended to admit only forecast, approved, row-scoped refreshes. (B) Same collision, smaller, between the 39 D2 rows and the PROTECTED `intent_out_of_set_probes_baseline.json`; a collision forecast is now a required R3.0 output, with the reference-probe safety claim required to be *proven*, not assumed. (C) `eval_routing_truth_set.py --check` was implicitly identity-against-baseline, which passes trivially at R1.5 and fails by construction at G1 since R3/R2 exist to improve on it; `--check` is now defined as **no-regression** (no `route_ok`→`route_wrong` flips, no new `capability_inconsistent`). (D) R1.2's coverage minimums summed to 89 against a `[60,80]` gate; quotas are now explicitly overlapping and the bound is `[60,95]`. Also clarified that `resolve_capability_compatibility` has no labelled-capability parameter, so the evaluator checks labelled capabilities through the same permit primitive rather than contorting that call. |
