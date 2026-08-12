# Plan 4 — Routing Evaluation Report

**Date:** 2026-08-12 · **Baseline:** `93562c1` · **Head at measurement:** `a0dca6a` · **Plan:** [`plans/2026-08-11_1834_routing-evaluation-and-authority-corrections.md`](../../plans/2026-08-11_1834_routing-evaluation-and-authority-corrections.md)

Every figure here is reproducible by `PYTHONPATH=backend:. python3 scripts/eval_routing_truth_set.py --arm both`, except where another command is named.

---

## 1. Headline

Plan 4 built the instrument the repository lacked, then used it to fix two routing-authority defects and to **disprove** the third. It did not fix everything it set out to, and the residue is larger than the part that was fixed.

| Metric (deterministic arm, gating rows only) | Baseline `93562c1` | After Plan 4 |
|---|---|---|
| route-correct | 56 / 77 (0.727) | **64 / 76 (0.842)** |
| `capability_inconsistent` | 21 | **13** |
| hunt/detection under-routing | 21 | **13** |
| knowledge-only false escalation | 0 | **0** |
| unsafe containment | 13 / 13 | **12 / 12** |
| ambiguous (reported, non-gating) | 10 | **11** |

| Live arm — the production-final route | Baseline | After |
|---|---|---|
| final route chosen by the LLM advisory | 49 / 77 | **44 / 76** |
| divergences from the deterministic floor | 10 | **5** |
| of those, degradations / improvements | 10 / 0 | **5 / 0** |
| **advisory-caused capability downgrades** | **5** | **0** |
| live route-correct | 46 / 77 | **59 / 76** |

The denominator moved 77 → 76 and unsafe rows 13 → 12 because one row (`q0.q045`) was reclassified non-gating; that is a smaller gate, not a containment loss.

---

## 2. What D3 fixed — LLM advisory could override deterministic routing

**Measured defect.** With `routing_mode=llm_assisted_semantic`, a validated LLM advisory selected the final route on **49 of 77** rows and, on **10**, replaced a deterministic route with a worse one — **5 of them dropping a capability** the deterministic skill had. **Zero of the 10 were improvements.** This contradicted the documented invariant that final route selection stays deterministic.

**Two root causes**, both from reusing `_deterministic_uncertain` (which answers "would an advisory add value?") as the test for "may an advisory overrule?":

1. every `out_of_registry` row is uncertain **by match path alone**, so a specific decision from one of the eight deterministic floors was replaceable;
2. on registry-backed paths `llm_advisory_recommended` alone satisfied uncertainty, so an `exact_105` match at **0.75** confidence was replaceable too.

**Correction** (`a66540c`): a distinct predicate restricts *replacement* to a route that reached no conclusion — the low-confidence fallback, marked by its existing `["needs_clarification"]` tool plan. `_deterministic_uncertain` is untouched, so the advisory still runs, still agrees, still warns, still reports. Semantic understanding is not disabled, and a genuinely unresolved route stays promotable — both sides pinned by test.

**Result:** capability downgrades **5 → 0**; divergences **10 → 5**; live route-correct **46 → 51** at the time of the change. The 5 remaining divergences are all terminal-fallback rows.

## 3. What R2.1 fixed — legacy pattern → skill contradictions (D1)

**Measured defect.** 15 golden rows routed to a skill whose contract denies SPL while the planner measured `intent_family=spl_generation_only`, `path_type=spl_review`, `needs_spl=True` — the lane ran and contributed nothing.

**Correction** (`913ac11`): three pattern classes in `LEGACY_ROUTER_INTENT_BY_PATTERN` → `attack_discovery` — `notable_risk_lookup` and `case_state_lookup` (user decision B: live retrieval is hunt semantics, not alert summary) and `threat_intel_enrichment` (clear-cut; shape-identical to the `ioc_correlation` rows).

**Result, by quota:**

| quota | baseline route-ok | after |
|---|---|---|
| `d1` | **0 / 8** | **8 / 8** |
| `d1` capability_inconsistent | **8** | **0** |

Refreshed behavior is **more constrained, not more permissive**: `execution_eligible None → False`, `human_review_required False → True`, `execution_status skipped → requires_human_review`, plus a validator-checked **review-only** SPL artifact where the question asks for one.

## 4. What was disproved — the D2 39-row premise

The source audit framed D2 as *"39 of 225 out-of-registry probes terminate on the 0.20 fallback"*, implying a 39-row defect. Independent labelling disproves that.

| D2 rows (39, gating) | |
|---|---|
| already `route_ok` | **38 / 39** — `knowledge_recall` *is* an acceptable skill for these guidance, policy and out-of-scope asks |
| `route_wrong` | **1** (`rt.d2.003`) |
| `capability_inconsistent` | **3** (`rt.d2.003`, `rt.d2.010`, `rt.d2.017`) |

**D2 is a 3-row defect, of which 1 is a wrong route.** The row-count framing measured how often a code path was taken, not how often it was wrong.

**D2 is NOT fixed.** No ninth routing rule was added and no contract correction was applied — both were blocked for measured reasons (§6).

## 5. Deterministic vs live routing quality

The two arms measure different layers and Plan 4 gates the deterministic one:

- **deterministic arm** — `select_route_from_understanding`, the layer Plan 4's corrections modify. **64 / 76**.
- **live arm** — `route_skill`, the production-final path including the advisory. **59 / 76**.

The 5-row gap is the advisory still replacing a route on terminal-fallback rows, all `degraded`, none a capability downgrade: `rt.d2.012`, `rt.d2.023` (→ `spl_generation`), `rt.d2.030`, `rt.d2.037` (→ `attack_discovery`), `rt.d2.034` (→ `alert_summary`). These rows remain replaceable *by design* — D3 deliberately left genuinely-unresolved routes promotable, and these are exactly that. Had D2's contract correction been possible, they would have resolved as a side effect.

---

## 6. What remains unresolved

### 6.1 Paraphrase handling — the largest remaining defect, and it was not on Plan 4's list

| paraphrase quota (12 gating rows) | |
|---|---|
| `route_ok` | **2 / 12** |
| `route_wrong` | **10** |
| `capability_inconsistent` | **10** |

**10 of the 13 remaining `capability_inconsistent` rows and 10 of the 12 remaining `route_wrong` rows are paraphrases.** Rephrased hunt questions — "hosts talking to an unusually wide spread of external addresses", "machines opening SMB sessions against a lot of different peers" — fall off the exact-match table to `knowledge_recall`, which denies the SPL their labels require.

Measured at assembly: **14 of 15** paraphrases land `out_of_registry` and only **1** reaches a near/semantic-105 path. Near-match does not rescue genuine rephrasing.

This is now the dominant routing defect by volume. It is the same mechanism as D2 (no deterministic signal survives rephrasing) and was surfaced *by* the truth set — the 105 goldens cannot see it at all, because they are the exact strings.

### 6.2 Three SPL-routing semantic misses

`rt.d2.003` (Kerberoasting hunt), `rt.d2.010`, `rt.d2.017`. Labels require `spl`; routed `knowledge_recall` denies it. **No safe deterministic discriminator exists today**: `rt.d2.010` and `rt.d2.017` have an *empty* signal set, and `rt.d2.003`'s only distinguishing signal fires on 9 rows of which 1 needs SPL (precision 1/9). Must not be approximated by heuristic.

### 6.3 `asset_identity_context` + `data_source_health` ownership — deferred

**10 truth-set rows** (7 golden + 3 paraphrases), all routed `knowledge_recall`, all labelled `spl`-requiring, **10/10 `capability_inconsistent`**, all `ambiguous` and therefore **non-gating**. The defect is measured but deliberately uncounted, because the label is honestly unresolved. Closing it one way widens a skill contract (forbidden without separate approval); the other way is a hint-table correction. **These rows are not asserted to be correct.**

### 6.4 One supplied-alert row

`rt.alert.002` routes `attack_discovery` where the label accepts `alert_summary` / `guided_investigation` — a summarise-this-alert ask reaching the hunt skill. Single row, reported not actioned.

### 6.5 Carried findings

- **`UNDERSTANDING_BEFORE_FINAL_ROUTE`** — future architecture candidate, **not approved**. The clarification determination lives only in `build_query_to_intent`, which consumes `routed_skill` and so cannot run before routing. That ordering is why §6.2's contract fix had no predicate.
- **`RUNTIME_MAP_BUILDER_IDEMPOTENCY`** — re-running the map authoring tool nulls all 11 MITRE registry fields on all 105 rows. Carried as its own correctness item.
- **`ROUTING_CHANGE_FORECAST_METHOD`** — forecast a routing change with the **full backend suite inside the temporary arm**. Two forecast misses in this plan came from using narrower instruments.

---

## 7. Answer parity — secondary evidence only

`production_parity: total=120 base_105=105 exact=120 approved=0 critical=0`.

**This means the imperative and ResourcePlanner runtimes produce the same answer as each other.** It is runtime equivalence. It is **not** answer correctness, **not** routing correctness, and **not** agreement with the frozen 105-answer file — that file is never read by the parity evaluator.

Measured separately: the 105 golden cases assert `expected.selected_skill`, self-describe as *"Auto-generated shallow expectation"*, and match production routing on **1 of 105** at unmodified baseline. They are tier 2; the governance regression runs tier 0.

Parity is reported here because a routing change that broke runtime equivalence would matter. It is not evidence that any route is right.

---

## 8. What this report does not claim

- **D2 is not fixed.** Its premise was disproved and its correction was blocked twice; §4 and §6.2 stand as findings, not repairs.
- **The 10 ambiguous ownership rows are not correct.** They are unresolved and non-gating.
- **Paraphrase routing is not fixed** and is the largest remaining defect.
- **The truth set gates the deterministic floor.** The live arm is measured and reported, never gated.
- The set is 87 rows with a recorded label-confidence distribution; near-105, semantic-105 and catalogue-collapse paths are covered only incidentally.
