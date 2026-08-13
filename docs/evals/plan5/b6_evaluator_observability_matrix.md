# Plan 5 B6 — evaluator observability matrix

**Question B6 answers:** for each routing/authority layer, *which committed evaluator actually observes it?*

B5 proved the question is not academic. Turning `ai_soc_live_capability_enforcement_enabled` ON produced
**0 route changes in `eval_routing_truth_set.py --arm both`** while changing a real in-catalogue product answer
(`cisco.ot.029`: `spl_generation` → `knowledge_recall`, candidate SPL and HIL gate lost). An instrument reporting
"no change" is only meaningful against the layer it observes.

No evaluator was modified for B6 and no frozen baseline was touched.
`docs/evals/routing_truth_set_baseline_v1.json` and `backend/app/evals/fixtures/…/baseline.json` are unchanged.

---

## The six layers (live path anchors, grep-verified at this commit)

| # | Layer | Anchor | What it decides |
|---|---|---|---|
| 1 | `select_route_from_understanding` | `backend/app/routing/select_route_from_understanding.py:28`, sole non-test caller `routing/skill_router.py:101` | Deterministic base route + provenance from the single `understand_query` parse |
| 2 | `route_skill` | `backend/app/routing/skill_router.py:50` | Layer 1 plus registry binding, threshold/floor resolution and the Plan 4 D3-gated LLM advisory (`routing/governance.py:398`) |
| 3 | `ResolvedQueryContract` | built `chat/resolved_query_builder.py:95`, emitted `chat/canonical_planning_orchestrator.py:888`, state key `resolved_query_contract` | Pre-route understanding: goal, family, answer goal, ambiguity, required/prohibited capabilities. Carries **no** skill and **no** execution authority |
| 4 | `adjudicate_route` | `backend/app/routing/route_adjudication.py:92`, live call `chat/pipeline.py:2347` inside `graph_node_route_resolution` (`:2303`), gated on `isinstance(state["intent_classification"], dict)` (`:2342`) | Ordered adjudication rules → `final_route` + `authority_source`; the B5 capability veto lives here |
| 5 | Final route commit | `graph_node_route_contract` (`chat/pipeline.py:2380`) via `run_contract_builder.py:280-286` — last writer of `routed["skill"]` | The skill the rest of the turn obeys |
| 6 | ResourcePlan / execution seam | `planner/executor.py:180` (single wiring seam), flag read `executor.py:218`, dispatch-v2 precedence `:221-222` | Schedule, evidence work, SPL→validate→MCP ordering, HIL/RBAC gate |

Layer 3 is new in Plan 5 (B1/B3); layer 4 began consuming it at B5.

---

## Matrix — which evaluator observes which layer

`Y` = observes and can fail on a change · `–` = does not reach the layer ·
`(Y)` = reaches it only transitively, as a final-surface effect, and cannot attribute the change to that layer.

| Evaluator / probe | Entry point | 1 | 2 | 3 | 4 | 5 | 6 |
|---|---|---|---|---|---|---|---|
| `eval_routing_truth_set.py --arm deterministic` | `select_route_from_understanding` (`:126,130`) | **Y** | – | – | – | – | – |
| `eval_routing_truth_set.py --arm live` | `route_skill` (`:72,75`) | (Y) | **Y** | – | – | – | – |
| `eval_b5_capability_enforcement.py` (Plan 5 B5 arm) | `select_route_from_understanding` → `build_resolved_query_contract` → `adjudicate_route` (`:110,113,126`) | **Y** | – | **Y** | **Y** | – | – |
| `backend/app/evals/in_catalogue_contract.py` (105 + Cisco 50, frozen fixture) | `app.api.routes_chat.chat` (`:10`) | (Y) | (Y) | (Y) | (Y) | **Y** | **Y** |
| `run_production_parity_eval.py` | `build_live_chat_response` **and** `run_chat_via_resource_planner_graph` (`production_runtime_parity.py:317-318`) | (Y) | (Y) | (Y) | (Y) | (Y) | (Y) — but only as *runtime-vs-runtime equivalence* |
| `eval_sentinel.py` | `routes_chat.chat` (`sentinel_eval.py:21`) | (Y) | (Y) | (Y) | (Y) | **Y** | (Y) |
| golden answers tier 0 (`golden_answer_runner`) | `routes_chat.chat` (`:14`) | (Y) | (Y) | (Y) | (Y) | **Y** | (Y) |
| `eval_out_of_catalog_ot_probe.py` | `routes_chat.chat` (`out_of_catalog_ot_probe.py:10`) | (Y) | (Y) | (Y) | (Y) | **Y** | (Y) |
| reference probes (`test_reference_answer_quality.py`) | `build_live_chat_response` (`:12`) | (Y) | (Y) | (Y) | (Y) | **Y** | (Y) |
| `run_soc_clean_answer_eval.py`, `spl_draft_preview_eval` | full pipeline | (Y) | (Y) | (Y) | (Y) | **Y** | (Y) |
| `run_cisco_powergrid_question_eval.py --profile deterministic` | `understand_query` + `match_question_runtime_entry` + `build_draft_preview` (`cisco_powergrid_soc_question_eval.py:14-16`) | (Y) | – | – | – | – | – |
| `eval_105_path_honoring.py` | `build_query_to_intent` + `plan_evidence` + `plan_path_and_tools` (`:33-35`) | – | – | (Y) | – | – | – |
| `eval_pipeline_dispatch_matrix.py` | dispatch stage builder | – | – | – | – | – | **Y** |
| `freeze_execution_baseline.py --check` | file hashes | – | – | – | – | – | – (artifact drift only) |

### Consequences that follow from the matrix

1. **Nothing in the frozen truth set observes layers 3–5.** The deterministic arm stops at layer 1 and the live arm at
   layer 2. Any Plan 5 change that lands in the contract or in adjudication is invisible to `--arm both --check` **by
   construction**, not by accident. This is exactly what B5 measured: `0/87` adjudication route changes reported by an
   evaluator that never calls `adjudicate_route`, alongside a genuine product regression.
2. **The only instrument that caught `cisco.ot.029` was the full-pipeline in-catalogue contract guard**
   (`in_catalogue_contract.py`, run by pytest against its frozen fixture), because it observes layer 5. Notably the
   Cisco *eval script* (`--profile deterministic`) did **not** catch it — it never reaches routing adjudication.
3. **Layer 6 is thinly covered at repo default.** `AI_SOC_RESOURCE_PLAN_EXECUTION_ENABLED=false` and
   `ai_soc_pipeline_dispatch_v2_enabled=false` mean the dispatch matrix probe is the main direct observer. Phase C must
   bring its own probes rather than assume the existing suite watches the merge seam.
4. **An instrument can nominally observe a layer and still be blind on a degrade path.** B5 recorded that when
   canonical-planning persistence fails (`handoff_load_failed`), the RP graph short-circuits, `route_adjudication` is
   absent from state, and the layer-4 veto is unreachable. Layer-4 coverage is therefore conditional on the planning
   handoff succeeding; a full-pipeline evaluator run on a degraded host silently measures layer 2 instead.
5. **The truth-set evaluator still builds its *reported* fields from a route-contaminated intent.**
   `evaluate_row` calls `build_query_to_intent(..., routed_skill=selected)` (`eval_routing_truth_set.py:133`) — the
   very argument B3 removed from the live path (`canonical_planning_orchestrator.py`). It feeds only the
   never-gated `observed_intent_family` / `observed_answer_mode` / `observed_path_type` columns, so it changes no
   verdict, but the evaluator's reported family is **not** the family the live contract now computes. Left unchanged
   deliberately: editing it would move reported columns inside a frozen-baseline file for zero gating benefit.
6. **Coverage is asymmetric in the direction that matters.** Layers 1–2 have a precise, row-attributable instrument;
   layers 3–5 have one Plan 5 arm plus end-to-end guards that detect a change but cannot say which layer caused it.

---

## Decision: extend the evaluator? **No.**

B6's Verify allows extending `eval_routing_truth_set.py` only after measuring the frozen-baseline diff, and requires a
STOP if any frozen expectation moves. That branch is avoidable and was avoided:

- `scripts/eval_b5_capability_enforcement.py` **already is** the layer 3–5 arm. It reads the same truth set, produces a
  per-row OFF/ON table, and writes only to `docs/evals/plan5/`.
- Adding an adjudication arm inside the frozen evaluator would change what `--check` compares against a baseline whose
  semantics Plan 4 froze. Preferring a separate arm keeps `routing_truth_set_baseline_v1.json` byte-identical (it is
  also a `PROTECTED` manifest member — drift would fail `freeze_execution_baseline.py --check`).

**No frozen baseline was refreshed, redefined or re-frozen in B6.**

## Pin

`backend/app/tests/test_evaluator_observability_matrix.py` pins the load-bearing claims so the matrix cannot rot
silently: the deterministic arm resolves through `select_route_from_understanding` and never through
`adjudicate_route`; the live arm resolves through `route_skill`; the B5 arm reaches contract **and** adjudication; the
full-pipeline guard reaches the final commit. It asserts call reachability, not routing outcomes, so it adds no new
routing authority and no new baseline.
