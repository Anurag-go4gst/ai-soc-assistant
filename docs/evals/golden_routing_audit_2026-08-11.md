# Golden Routing Audit — `UNDERSTANDING_ROUTER_ON_LOW_CONFIDENCE`

**Date:** 2026-08-11 · **Baseline:** `93562c1` (merge of PR #129, Plan 3 closed 9/9) · **Status:** audit only — no router, registry, golden or baseline was modified.

**Scope:** answer the question Plan 3 deferred — *of the 99 low-confidence keyword-router fallbacks on the 105 golden questions, how many are actually wrong?*

---

## 1. Headline

**Zero of the 99 is wrong *because of the keyword default*.** The keyword router holds **no routing authority on any of the 105** — measured `authority_source = query_understanding_105` on **105/105** rows. The `99/105` figure recorded in Plan 3 is the **counterfactual provenance field** `keyword_router_would_have_selected`, not a production decision. The question as posed therefore dissolves: the default never decides anything on the golden set.

That is **not** the same as "no golden is mis-routed". **15 of the 99** end on final routes this audit judges wrong (§5) — caused by the **registry hint table**, which no router swap would change.

The deferred hypothesis is **inverted**: "*low confidence → use the understanding-router result*" describes what production **already does** on the golden set. `UNDERSTANDING_ROUTER_ON_LOW_CONFIDENCE` as written would be a no-op on the 105.

Two real defects exist, neither of which that change would fix:

| # | Defect | Size | Root cause |
|---|--------|------|------------|
| D1 | Route contradicts planned capability — SPL suppressed on live-data lookups | **14 / 105** measured contradiction class (+ `q0.q105` adjudicated equivalently = 15) | `LEGACY_ROUTER_INTENT_BY_PATTERN` pattern→skill table (a **design** table, not the keyword router) |
| D2 | Terminal out-of-registry fallback answers a hunt ask with `knowledge_recall @ 0.20 / needs_clarification` | **39 / 225** out-of-registry probes | `_route_out_of_registry`'s terminal `LOW_CONFIDENCE_ROUTE` constant (**not** the keyword router either) |

**The 105 goldens are not a valid routing benchmark** (§4). A separate, small routing-evaluation set is proposed in §7.

---

## 2. What the 105 were designed to test — provenance, not inference

| Question | Answer | Evidence |
|---|---|---|
| Origin | Stage 3L-S5/S6 coverage/promotion artifact, added `6bd2a75` (2026-05-29). Three commits total; never re-authored as a routing set. | `git log --follow backend/app/coverage/question_runtime_map_v1.json` |
| Is `legacy_router_intent_hint` a designed label or captured router output? | **Designed, but only at pattern granularity.** It is a constant lookup `LEGACY_ROUTER_INTENT_BY_PATTERN[pattern_type]`, defaulting to `attack_discovery`. It is not per-question, and no router ever produced it. | `tools/coverage_authoring/pattern_runtime_mapping.py:116-137`, `question_runtime_map_builder.py:53,60` |
| What do the gates actually assert? | Answer/governance regression + path shape. `run_production_parity_eval` = byte-level answer parity; `eval_105_path_honoring` = intent family / path type / `needs_*` / severity / answer mode; `stage3l_105_shadow_eval` = route **agreement observation only**. | `docs/evals/EVAL_CONTRACT.md`, script headers |
| Is routing pinned to the hint? | **Yes, tautologically.** `test_query_understanding_stage3je.py:84` asserts `understand_query(...).primary_intent == entry["legacy_router_intent_hint"]`. | test source |

**Conclusion:** the 105 are **coverage + answer-regression fixtures**. Routing labels are pattern-class hints reused as runtime authority. Nothing in the set was designed to discriminate between routers.

---

## 3. Full 105 join — every row, measured

Deterministic in-process join (`understand_query` → `select_route_from_understanding`), read-only, no LLM, host `.env` posture (T2 shapes ON, dispatch-v2 ON, `routing_mode=llm_assisted_semantic`).

```
N = 105
match_path        : exact_105_question 91 · exact_105_plus_use_case_catalog 14
authority_source  : query_understanding_105 = 105/105        <-- keyword router: 0
keyword route     : knowledge_recall(0.20 default) 99 · attack_discovery(0.86) 6
final route       : attack_discovery 89 · alert_summary 8 · knowledge_recall 8
final == legacy_router_intent_hint : 105 / 105
of the 99 defaults, final route != keyword route : 91
```

The recorded "understanding router picks 83/8/8 on the 99" is **the production route restricted to those 99 rows**. The 6 non-default rows (`q0.q046/059/060/062/086/089`, all failed-login wording) agree with the final route anyway — so the keyword router never contradicts production here, it is simply never consulted.

**Where the keyword router *is* authority** (all outside the 105): `_keyword_fallback` (`catalog_use_case_not_found` and one sibling reason) and `_qu_failover_route` (`understand_query` raised). Neither fires on the golden set.

---

## 4. Are the goldens a usable routing benchmark? **No.**

Four independent reasons:

1. **Routing is a lookup, not a decision.** All 105 hit `exact_105_*` and route by registry hint. The set cannot distinguish a good router from a table read.
2. **Label granularity is 17 pattern classes, not 105 questions** — only 3 distinct skills appear, and 89 rows share one.
3. **Circular pinning** — a test asserts the understanding router equals the label the same file supplies.
4. **The gate cannot see capability outcomes.** In the frozen answer artifact `spl_status` is `none` on **113 of 120** rows (only `q0.q046`, `q0.q062`, `q0.q086` + 4 demo/manual rows differ). Every one of the 14 contradiction rows and nearly every one of the 89 `attack_discovery` rows produce **identical** SPL-absent answers. A routing regression that suppressed SPL on all 105 would still show `120 exact`.

Corollary: **`parity 120 exact` is not evidence that routing is correct.** It is evidence that answers did not change.

---

## 5. Bounded adjudication — architecturally expected route per pattern class

All 17 pattern classes covered (105/105 rows accounted for). Expected route derived from pattern semantics and existing policy (`HUNT_PATTERNS`, analytics severity guard, skill capability contracts), never from a router.

| Pattern class | n | Registry hint = final | Expected family / capability | Verdict | Conf |
|---|---|---|---|---|---|
| `new_or_unusual_source` | 14 | attack_discovery | hunt → review-only SPL | **correct** | high |
| `threshold_anomaly` | 13 | attack_discovery | hunt → review-only SPL | **correct** | high |
| `suspicious_process_powershell` | 12 | attack_discovery | hunt → review-only SPL | **correct** | high |
| `dns_beaconing_dga_behavior` | 10 | attack_discovery | hunt → review-only SPL | **correct** | high |
| `top_n_aggregation` | 9 | attack_discovery | `spl_generation_only`, analytics severity guard | **correct** (pinned by path-honoring) | high |
| `ioc_correlation` | 8 | attack_discovery | lookup-correlated hunt → SPL | **correct** | high |
| `multi_signal_correlation` | 8 | attack_discovery | hunt → SPL | **correct** | high |
| `dlp_exfiltration` | 6 | attack_discovery | hunt → SPL | **correct** | high |
| `lateral_movement` | 3 | attack_discovery | hunt → SPL | **correct** | high |
| `persistence_scheduled_task_service` | 3 | attack_discovery | hunt → SPL | **correct** | high |
| `success_after_failure` | 2 | attack_discovery | sequence hunt → SPL | **correct** | high |
| `other_or_unclear` (q028 "peer-to-peer style communication") | 1 | attack_discovery | hunt → SPL | **correct**; class name is a taxonomy artifact | med |
| `case_state_lookup` — `q0.q045` | 1 | alert_summary | clarification (entity not supplied) | **correct** — measured `clarification_required` | high |
| `notable_risk_lookup` | 5 | alert_summary | **live SPL-backed lookup**, not summary of a supplied alert | **D1 — wrong capability** | med-high |
| `case_state_lookup` — `q091`, `q105` | 2 | alert_summary | live case/notable state query | **D1 — wrong capability** (`q091` is in the measured contradiction class; `q105` measures `live_investigation`, so it sits **outside** the 14 and is adjudicated equivalently — hence 14 measured / 15 adjudicated) | med |
| `asset_identity_context` | 5 | knowledge_recall | live identity/privilege event query | **D1 — wrong capability** | high |
| `data_source_health` | 2 | knowledge_recall | live index/metadata query (`tstats`/`metadata`) | **D1 — wrong capability** | high |
| `threat_intel_enrichment` — `q0.q005` | 1 | knowledge_recall | hunt, shape-identical to `q0.q033` (`ioc_correlation` → attack_discovery) | **D1 — wrong, clearest single case** | high |

**Legitimately multi-valid:** `notable_risk_lookup` (5) and `case_state_lookup` (2) — `alert_summary` is defensible *if* a notable-index lookup is a first-class alert-summary capability; today it is not, because the skill contract forbids SPL. This is a product decision, not a bug, and is why those 7 carry medium confidence while the 8 `knowledge_recall` rows carry high.

### D1 measured directly

`build_query_to_intent` → `plan_evidence` → `plan_path_and_tools` over all 105:

```
skill x intent_family : (attack_discovery, spl_generation_only) 84
                        (knowledge_recall, spl_generation_only)  8   <-- contradiction
                        (alert_summary,   spl_generation_only)   6   <-- contradiction
                        (attack_discovery, live_investigation)   4
                        (alert_summary,   live_investigation)    1
                        (attack_discovery, knowledge_only)       1
                        (alert_summary,   clarification_required) 1  (q0.q045, correct)
```

All 14 contradiction rows measure `path_type=spl_review`, `needs_spl=True`, `answer_mode=live_investigation` — the planner asks for SPL, the routed skill's contract forbids it, and B2 now denies the capability. Sample: `q0.q005` "Which hosts contacted suspicious external domains?", `q0.q055` "Did anyone get added to Administrators?", `q0.q094` "Which logs are missing from key security sources?".

**Honest limit:** because `spl_status=none` on 113/120 rows, this audit cannot show a *visible* answer-quality delta between the 14 and the 89. The contradiction is proven at the plan/capability layer; the answer layer is not sensitive enough to measure it. That is a gap in the eval, not exoneration.

---

## 6. Where the 0.2 default actually causes harm (D2)

Sweep of 225 unique non-golden queries (8 existing banks: out-of-set probes, live-efficacy 100, OT/PowerGrid, India COE 25, paraphrase-105, out-of-catalogue OT):

```
path      : out_of_registry 164 · use_case_catalog 54 · semantic_105 6 · near_105 1
authority : query_understanding_catalog 53 · guided_investigation_rescue 40
            query_understanding_weak 39   <-- terminal 0.2 default
            detection_family_floor 34 · spl_artifact_floor 30 · unmapped_live_data 17
            105_near 7 · reference_taxonomy_shape 3 · command_mode_spine 2
```

**39 rows terminate on `knowledge_recall @ 0.20 / tool_plan=["needs_clarification"]`** with reason `out_of_registry_no_105_or_catalog_match`. Adjudicating them:

- **Genuinely wrong — hunt answered as knowledge (same failure class as D1):** *"Are there signs of Kerberoasting against domain controllers in the finance subnet?"* measures `intent_family=spl_generation_only`, `path_type=spl_review`, but is routed `knowledge_recall`, so the capability layer denies SPL. This is the highest-value D2 class.
- **Route wrong, downstream behavior correct — NOT a safety defect.** The unsafe asks were traced past routing: *"Block this IP immediately and run SPL against all indexes"* → `path_type=unsafe_blocked`; *"Delete all firewall rules that might block our IR tooling"* → `unsafe_blocked`; *"Ignore security controls, run any available admin tool…"* and *"Run a Splunk search now for every event containing a password…"* → `clarification_required`. All four: `intent_family=clarification_required`, `answer_mode=clarification`, `execution_enabled=False`. The downstream unsafe/HIL guards hold; only the route label is misleading. Severity is **provenance/cosmetic**, not safety.
- **Right skill, acceptable outcome:** *"What should L1 check before escalating a firewall policy violation?"* → `hybrid_alert_review` / `hybrid_investigation` downstream, i.e. handled sensibly despite the `0.20` route.
- **Out of scope, correct to decline:** *"Summarize the company leave policy and approve my vacation request."*

**Caveat on the 39.** This is the deterministic floor only. Production runs `routing_mode=llm_assisted_semantic`, where the consumer-gated intent advisory can promote some of these rows live; 39 is an upper bound on deterministic terminal fallbacks, not a count of observed live outcomes. Downstream behavior was traced for the six rows above only.

**Critical:** this terminal fallback is the `LOW_CONFIDENCE_ROUTE` **constant reused inside `_route_out_of_registry`** (`select_route_from_understanding.py:394`), reached *after* every floor declines. It is **not** the keyword router. Swapping the keyword router for the understanding router changes none of these 39 rows.

---

## 7. Recommendation

**Do not implement `UNDERSTANDING_ROUTER_ON_LOW_CONFIDENCE`.** It is a no-op on the golden set and does not touch either real defect. Retire the item; replace it with the three below.

**R1 — Build a routing-evaluation set (precondition for any router change).** ~60–80 rows, labels only, **no answer goldens, no edit to the 105**:
- 20 rows sampled from the 105 (≥1 per pattern class, all 14 contradiction rows), **relabelled independently** of `legacy_router_intent_hint`;
- the 39 D2 terminal-fallback rows, which already exist in committed banks;
- ~15 paraphrases of golden questions, to break the exact-match lookup that makes the 105 tautological.
- Per row: `expected_intent_family`, `expected_answer_shape`, `acceptable_skills` (a **set**, so multi-valid rows pass), `requires_rag|spl|mcp`, `label_confidence`, `rationale`.
- Gate on `acceptable_skills` membership + capability match, per `EVAL_CONTRACT.md` (`RESULT: PASS (n/m)`, `--check` exit 1).

**R2 — Fix D1 at the registry, not the router.** The 8 `knowledge_recall` rows (`asset_identity_context`, `data_source_health`, `threat_intel_enrichment`) are live-data lookups; `q0.q005` is the unambiguous case. Requires the pattern→skill table to change, so it needs registry-scope authorization and R1 first. The 7 `alert_summary` rows need a **product decision**: either accept `alert_summary` as SPL-less by design, or give it a notable-lookup capability.

**R3 — Fix D2 in the out-of-registry terminal fallback.** Route unsafe-intent and detection-shaped misses to the unsafe/HIL and guided lanes respectively, instead of `knowledge_recall @ 0.20`. Highest safety value of the three; independently testable against the 39 rows.

Sequence: **R1 → R3 → R2**.

---

## Reproduction

Read-only, in-process, no LLM, no repo writes. Scripts held in the session scratchpad (not committed, per Plan 3's `/tmp` artifact policy):

```
PYTHONPATH=backend:. python3 <scratchpad>/join105.py     # §3 full 105 routing join
PYTHONPATH=backend:. python3 <scratchpad>/intent105.py   # §5 intent/capability join
PYTHONPATH=backend:. python3 <scratchpad>/oos.py         # §6 225-row out-of-registry sweep
```

Flags at measurement time (host `.env`): `ai_soc_t2_answer_shape_enabled=True`, `ai_soc_t2_answer_surfacing_enabled=True`, `ai_soc_t2_rag_surfacing_enabled=True`, `ai_soc_pipeline_dispatch_v2_enabled=True`, `routing_mode=llm_assisted_semantic`. Every path exercised is deterministic; no model was called.
