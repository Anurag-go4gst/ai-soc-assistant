---
name: architecture-audit-query-understanding-and-plan-creation
overview: "Read-only audit of how a landing query is tiered (T0–T4) and decomposed, how the LLM is (not) used to plan across MCP/knowledge/reference/SPL on the T4 guided path, and which node findings genuinely feed later nodes — cross-referenced against the 2026-08-08 corrective-actions plan."
status: audit
date: 2026-08-10
canonical_plan: plans/2026-08-10_0555_architecture-audit-query-understanding-and-plan-creation.md
source_plan: plans/2026-08-08_1824_architecture-review-corrective-actions.md
source_plan_status: done (e5c1937, 2026-08-10)
source_review: docs/architecture/architecture_review_2026-08-08.md
current_disposition: "see the Post-G1 disposition section — it supersedes the body for open/closed status"
---

# Audit — query understanding, tier assignment, T4 planning, node-to-node coupling

> **Read the [Post-G1 disposition](#post-g1-disposition-2026-08-10) section at the end first.**
> The body below is the audit **as written on 2026-08-10 while the corrective plan was still
> executing**, and is preserved unedited as the historical record. Several of its statements were
> overtaken by that plan's own execution (notably the B1 premise and the "A1 blocked" framing in
> Context). The disposition section is the only authority on what is still open.

## Context

Read-only audit, not an implementation plan. Three questions:

1. When a query lands, how is it identified as T1–T3 vs T4, and how is it decomposed so we
   know what is being asked?
2. On the T4 guided plan, how is the LLM used to combine multiple resources (MCP,
   knowledge/RAG, reference registry, SPL) into one comprehensive answer?
3. Do findings of one node actually feed a later node?

Cross-referenced against the in-flight corrective plan
[`plans/2026-08-08_1824_architecture-review-corrective-actions.md`](2026-08-08_1824_architecture-review-corrective-actions.md)
(P0 + A0 closed; **A1 blocked twice**, premise revised 2026-08-10; B0→G1 unstarted) and its
source review [`docs/architecture/architecture_review_2026-08-08.md`](../docs/architecture/architecture_review_2026-08-08.md).

No runtime edits were made producing this audit.

### Host posture (read from `.env` — matters, because it differs from repo defaults)

`AI_SOC_LLM_MODE=local`, `AI_SOC_LLM_FINAL_SYNTHESIS_ENABLED=true`,
`AI_SOC_LLM_LIVE_SYNTHESIS_ENABLED=true`, `AI_SOC_GUIDED_LLM_ENABLED=true`,
`AI_SOC_LLM_INTENT_ADVISOR_ENABLED=true`, `AI_SOC_LLM_SPL_FALLBACK_ENABLED=true`,
`AI_SOC_GUIDED_HYBRID_INVESTIGATION_ENABLED=true`, **`AI_SOC_PIPELINE_DISPATCH_V2_ENABLED=true`**,
`MCP_MODE=mock` + `MCP_GLOBAL_EXECUTION_ENABLED=true`, `ROUTING_MODE=llm_assisted_semantic`,
`LANGGRAPH_ORCHESTRATION_ENABLED=true`, turn deadline 210s and
`AI_SOC_LLM_T2_TURN_DEADLINE_SECONDS=210` (T2 clamp fix applied).

Several of these are `False` in `config.py`. Any analysis written from repo defaults will be
wrong on this box — one finding below flips because of it.

---

## Q1 — Query intake → decomposition → tier

`backend/app/config.py:398` — `langgraph_orchestration_enabled: bool = True`. The Resource
Planner LangGraph is the live spine; `docs/architecture/chat_pipeline_state_v2_and_node_trace.md`
(9-node imperative, flag default False) is **stale** and must not be read as current.

**Tier vocabulary — authoritative path** (`backend/app/chat/lane_router.py:9–61`):
`initial_tier` is a pure function of the parser's `deterministic_match_path`:
T1 = `exact_105_question` / `exact_105_plus_use_case_catalog`; T2 = `use_case_catalog`;
T3 = `near_105_question` / `semantic_105_question` / **`fuzzy_alias_catalog`**;
everything else (incl. empty) = T4. `processing_lane_for_initial_tier` (`:36`) maps
T1–T3 → `known`, T4 → `guided`, and `resolved_tier == "T0"` → `knowledge_short_circuit`.
Docstring at `:53` is explicit: **T0 is never returned from a parser match_path** — it only
appears after T4 reference qualification, at `canonical_planning_orchestrator.py:413–428`,
which also forces `routed["skill"] = "knowledge_recall"`. Consequence: **T0 is reachable only
from T4**; a T1/T2/T3 catalogue hit never becomes T0.
`RoutingContext.catalogue_tier` is set from the resolved tier at
`backend/app/chat/canonical_handoff_builder.py:126` — an alias of `resolved_tier`, not a
recomputation.

**Tier and skill are siblings, not a chain.** Both are derived from the same `match_path`:
`select_route_from_understanding.py:33–66` dispatches directly off it (T1 → runtime-map row's
skill; T2 → catalogue row; T3 → near/semantic row; T4 → the `_route_out_of_registry` ladder).

**Second, non-authoritative tier implementation** (`backend/app/catalogue/match_tiers.py:158`):
`match_catalogue_tier()` checks `_reference_match()` **first** (`:160`, regex `:25`), so *any*
query containing a CVE/T####/AML id returns `T0` regardless of hunt intent — exactly the
confirmed `Hunt for T1059 execution in our estate` disagreement, and the reason plan decision
**D7** exists. Its `_T3_PATHS` (`:32`) omits `fuzzy_alias_catalog` (present in
`lane_router.T3_PATHS`), but it reaches T3 independently via
`_use_case_catalog_match(alias_applied=True)` (`:146`), driven by a 7-entry typo table
`_TYPO_ALIASES` (`:34`).

**Non-test importers of the second implementation** (grep):

1. `backend/app/graph/resource_planner_graph.py:398` — the Skill specialist **recomputes** the
   tier instead of reading canonical routing (→ plan item **B1**). *The only one that runs.*
2. `backend/app/catalogue/live_router_bind.py:86` — **not reachable in production**; see below.

`apply_live_catalogue_bind` also **stamps** the heuristic tier into
`routed["routing_provenance"]["catalogue_tier"]` (`live_router_bind.py:92`) and into
`candidate_mappings` (`:104`). So three surfaces are named `catalogue_tier`: canonical routing
(authoritative), routing provenance (bind heuristic), specialist report (recomputed). Only the
first is correct. Checked: the heuristic value does **not** reach the LLM —
`build_governed_context_package_v1` (`backend/app/llm/governed_context_package.py:155–172`)
reads only `match_path` and registry candidates from `candidate_mappings`.

### Correction to the corrective plan's own premise table

> **Superseded — read "Execution status" below before acting.** This was true when measured.
> The in-flight B1 change has since added a live call site in `graph_node_init_routing`
> (`pipeline.py:1018`), so the binding candidate now runs on the production path. The premise
> criticism stands as a documentation defect; the scope-shrink recommendation no longer applies.

**`apply_live_catalogue_bind` is NOT on a live path.** Both call sites
(`backend/app/chat/pipeline.py:1350`, `:1374`) sit inside `graph_node_query_to_intent`
(`pipeline.py:1042`, spans to `:1978`... verified enclosing function). Non-test importers of
that node: exactly two — `backend/app/chat/linear_graph_legacy.py:45` (test harness) and
`backend/app/graph/planner_led_shadow_graph.py:25`, which
`backend/app/evals/production_runtime_parity.py:9,251` documents as having **no production
caller** and actively tripwires. Neither production runtime reaches it: the RP graph enters via
`rp_node_bootstrap` → `run_canonical_planning`, and the imperative rollback
(`pipeline.py:632–639`) goes `graph_node_init_routing` → `run_canonical_planning` directly. The
canonical orchestrator calls `build_query_to_intent` itself, bypassing the node.

Consequence: plan premise row 1 ("`match_catalogue_tier()` … also feeds
`app/catalogue/live_router_bind.py`; production use must be migrated before any compatibility
surface is retired") and the review's Correction 2 (which *withdrew* the "delete it"
recommendation on those grounds) are **both stale** against the RP-graph-default cutover.
Today `match_catalogue_tier` has exactly **one** production consumer. Once **B1** makes the
Skill specialist read canonical routing, the second implementation has zero production
consumers and B1's "compatibility wrapper while callers are migrated" clause is unnecessary
work. **Re-verify before executing B1** — this shrinks its scope.

(The twice-per-turn invocation and the `setdefault` ordering trap in that node are therefore
latent, not live.)

### Decomposition stages (all deterministic — no model hop)

`understand_query` (`query_understanding/parser.py:86`, `deterministic_match_path` at `:384`)
→ `route_skill` → `lane_for_match_path` → `extract_query_signals` (`chat/query_signals.py:406`)
→ `build_query_to_intent` (`chat/intent_classifier.py:1147`; sub-stages
`build_candidate_mappings` `:223`, `classify_intent` `:249` — a long precedence ladder over
signals, closed enums `IntentFamily`/`AnswerGoal`/`ActionMode`) → answer-shape router
(`chat/answer_shape_router.py:284`, regex floor `:261`) → `evaluate_known_detail_completion`
(`chat/known_detail_completion.py:83`) → guided detail resolution when diverted →
`build_canonical_planning_input` (`chat/canonical_handoff_builder.py:29`) →
`plan_evidence_from_canonical` (`:51`).

The orchestrator states it outright at `canonical_planning_orchestrator.py:306–307`:
*"`build_query_to_intent` is deterministic — the LLM advisory is an injected argument, never
called here."* On the RP path it is passed `llm_intent_advisory=None`.

### Reference qualification → T0

`backend/app/chat/reference_qualification.py`: `qualify_reference_query()` (`:75`) extracts ids
by regex (`:10`), then scans five substring marker lists (`:15–62`) to build `requested_scopes`.
`knowledge_only` is granted only if a knowledge phrase matches **and** no
status/correlation/action/investigation marker fired (`:109`); more than one scope collapses to
`composite` (`:115`); a bare id with no knowledge phrase is deliberately `composite`
(`:120–122`) so it stays T4. The predicate is
`ReferenceQueryQualification.resolves_to_t0` (`chat/contracts/reference_qualification.py:36–44`).

Confirmed defects — all bare `in`-substring, all fail-safe (can only deny T0, never grant it):

- `:99` `environment_scope = status_check or "our " in normalized` → fires on
  "f**our h**ours", "an h**our** ago" (→ **C0**).
- `:32,33` bare `vulnerable` / `exposure` in `_STATUS_MARKERS` → "explain the vulnerable
  component in CVE-…" is treated as an environment status check (→ **C0**).
- **Additional, not in the review:** `_ACTION_MARKERS` (`:46`) contains bare `"block"`, which
  substring-matches `blocked`, `blocklist`, `blockchain`; `_INVESTIGATION_MARKERS`
  (`"unusual"/"anomaly"/"suspicious"`) are likewise unbounded. Same defect class, fixed by the
  same boundary-aware matcher — but C0's Do-list names only `vulnerable`/`exposure`. **Widen
  C0's sweep to all five lists in the file.**

---

## Q2 — T4 guided plan, LLM multi-resource use

### Headline: on the live path, T4 plan creation is 100% deterministic

No LLM composes a resource plan that is used in production today. Every LLM planning surface is
unreachable, shadow-only, or not wired into the production graph. Verified:

- `is_canonical_authoritative()` is **hardcoded `return True`** (`chat/canonical_mode.py:21–22`).
- `graph_node_evidence_planning` (`pipeline.py:1755`) fails closed under canonical mode —
  `build_canonical_failure_state(reason="canonical_forbids_legacy_evidence_planning")`
  (`:1758–1768`) — unless `loop_initialized(state)` or the test-only `legacy_langgraph_harness`.
- The **only** non-test call site of `apply_llm_primary_resource_plan` is `pipeline.py:1842`,
  inside that fenced node (function spans 1755–1978).
- The live plan authority — `plan_evidence_from_canonical.py`,
  `canonical_planning_orchestrator.py`, `planner/composer.py` — contains **zero** references to
  the bridge (grepped).
- `planner/resource_plan_shadow.py:98` always returns `promotion_blocked=True`; trace-only.
- The guided-hybrid rail (`propose_investigation_plan_llm` → Validator A
  `validate_investigation_plan` → Validator B `compose_guided_resource_plan`) is real and
  well-built, but is wired **only into the imperative pipeline** (`pipeline.py:650`). The RP
  graph's `_rp_dispatch_route` (`resource_planner_graph.py:483–494`) has only four branches and
  no guided-hybrid entry. Note `AI_SOC_GUIDED_HYBRID_INVESTIGATION_ENABLED=true` **on this
  host** — so the flag is on and the rail still does not run, because production uses the RP
  graph. The unreachability is structural, not flag-dependent.

So the honest answer to "how does the LLM use MCP + knowledge + resources on T4": **it
currently does not.** The LLM's live role is narration/composition at the end of the turn plus
advisory route suggestions. Plan composition is deterministic (`plan_evidence` →
`compose_resource_plan` under a `resource_plan_authority()` contextvar).

**One important nuance — an LLM planning call *does* fire on this host, it just cannot be
used.** `run_resource_plan_shadow` is called at `pipeline.py:4538`, and the enclosing function
is `graph_node_context_finalize` (`pipeline.py:3527`) — which **is** on the live RP path via
`rp_node_finalize`. Its gate `resource_plan_shadow_enabled()` (`resource_plan_shadow.py:38–44`)
is `final_synthesis AND live_synthesis`, and **both are `true` here**. So on every eligible turn
a real model call hits the ~6 tok/s endpoint, is recorded as `resource_plan_shadow_trace` plus a
sidecar budget entry, and is then discarded. Precise claim: *no LLM plan is ever promoted* — not
*no LLM planning call happens*. Worth knowing before attributing T4 latency to synthesis alone.

### The LLM plan bridge (built, validated, unreachable)

`backend/app/planner/llm_plan_bridge.py` — read as design intent, currently inert:

- System prompt (`:50–62`) asks for one JSON object of ordered steps, each
  `{resource_id, purpose, args}` with `purpose ∈ {knowledge_retrieval, spl_artifact,
  mcp_execution, mitre_mapping, cve_lookup, narration}` (`:43`).
- User prompt (`:238–244`) is **only** `{question, catalog}`, catalog being
  `resource_id + capabilities` filtered to `availability ∈ {available, fixture_only}` and
  `policy_tier <= 1`. No SPL, no RAG text, no credentials.
- `_FORBIDDEN_ARG_KEYS` (`:48`) strips `spl/search_query/query/raw_spl/search` — plans bind
  resource families, never query strings. `_TIME_BOUND` (`:45`) rejects unbounded windows.
- Every step re-validated deterministically against the registry (`validate_llm_plan_proposal`
  `:78–136`, per-step verdicts `:264`); capped at 8 steps (`:93`); survivors carry
  `policy_checks=["llm_proposed_deterministically_validated"]` (`:111`). Zero survivors →
  `rejected:all_steps_dropped` → deterministic plan stands.
- Hard 20s cap (`:41,68,212`); any exception returns `None` (`:233`, deliberate — "behave
  exactly as if the bridge does not exist").
- Merge is **floor-preserving**: `merge_floor_with_promoted`
  (`planner/plan_promotion_merge.py:30–87`) retains every floor step and only *adds* LLM steps
  before `narration`. The LLM can widen a plan, never narrow it.

**Three further limits that would still bind after any re-wiring** (none in the corrective plan):

1. **The bridge does not fire on most T4 paths.** `_TRIGGER_MATCH_PATHS = {"out_of_registry",
   "near_105_question"}` (`:40`). `lane_router.T4_PATHS` also contains
   `semantic_out_of_registry`, `query_understanding_weak`, `qu_unavailable`, `""`. A turn where
   query understanding failed (`qu_unavailable`, produced at `routing/skill_router.py:289`,
   `routing/routing_provenance.py:114`) is T4/guided but gets deterministic planning only —
   the case where an LLM planner would help most.
2. **Guided is excluded outright.** `apply_llm_primary_resource_plan`
   (`plan_promotion_merge.py:101–105`) returns the floor unchanged when
   `provenance.composer == "guided_hybrid_v1"` or `skill_id == "guided_investigation"`. The
   `guided_investigation` **skill** (deterministic rescue, review-only) is not the same thing
   as the T4 **lane** — conflating them is easy and wrong.
3. **Budget would skip the planner first.** `planner_hop_budget_blocked` (`:19–27`) skips when
   `remaining < 20s + composer_reserve`, stamping `llm_bridge="skipped:budget"`. Per
   `docs/architecture/llm_budget_model.md` the bridge is #1 in the skip order. Moot while the
   call site is fenced, but it means re-wiring alone would not make LLM planning reliable on a
   ~6 tok/s box. `bridge_enabled()` (`:168`) also has no dedicated flag — it piggybacks on
   `ai_soc_llm_intent_advisor_enabled AND ai_soc_llm_live_synthesis_enabled`.

### The documented MCP discovery machinery is not on the production spine

Verified four ways:

- `_compiled_resource_planner_graph()` (`resource_planner_graph.py:806–858`) registers 15 named
  nodes plus the governance chain. No `evidence_planning`, `mcp_call`, or discovery node;
  `grep -n discovery resource_planner_graph.py` returns nothing.
- `graph_node_evidence_planning` — the HUB that calls `initialize_loop`/`assess_loop` — is
  imported by exactly one non-test module: `chat/linear_graph_legacy.py:40`.
- `_run_discovery_loop_imperative` (`pipeline.py:2245–2257`, the `MAX_MCP_HOPS=6` drain) is
  called only from `pipeline.py:641` (imperative rollback) and early-returns unless
  `loop_initialized(state)` — which only the fenced HUB sets.
- `_dispatch_hooks()` (`pipeline.py:5852–5864`) exposes rag / spl / reference / execution
  stages only. No `mcp_call` hook.

So the chronology proposal, discovery hops, data-silence advisory, and the `evidence_observer` +
`next_hop_hint` governed ReAct described in `docs/architecture/mcp_tool_routing.md` **do not
run** on the live path. The only MCP touch is the gated SPL search via `graph_node_execution` →
`evaluate_mcp_execution`. That doc needs the same staleness warning as the node-trace doc, and
**D1's MCP specialist must not be built assuming discovery hops exist**.

### What actually produces a multi-resource answer today — deterministic assembly

1. **EvidencePlan** — `chat/evidence_planner.py:68 plan_evidence`, one hardcoded plan per intent
   family. T4 guided (`:310–372`) is deliberately narrow:
   `answer_mode="guided_investigation"`, `needs_rag=True`, `needs_spl=False`, `needs_mcp=False`,
   `spl_allowed=False`, `mcp_allowed=False`, `requires_hil=True`. Widenings are flag-gated.
2. **ResourcePlan** — `planner/composer.py:35 compose_resource_plan`; `mcp_allowed is not True`
   forces `blocked_policy` (`:73–78`). CVE/ATT&CK/ATLAS bind as `skill:cve_lookup` /
   `skill:mitre_mapping` steps (`:80–99`) via the offline `planner/reference_registry.py` (regex
   id extraction + vendored snapshots; fails closed to `[]`, never fabricates).
3. **Step walk** over `_DISPATCHABLE_PURPOSES = {knowledge_retrieval, spl_artifact,
   mcp_execution, cve_lookup, mitre_mapping}` (`planner/executor.py:95`) — but see Q3: the walk
   does **not** control execution order.
4. **CanonicalFacts spine** (`chat/canonical_facts_spine.py`) harvests entities, source
   evidence, RAG, MCP evidence, MITRE, CVE, plan steps, negative evidence.
5. **Grounding assembler** (`chat/grounding_assembler.py:219`) merges MITRE + RAG citations +
   executed-evidence citations with lineage; appends an honest limitation when no rows exist.
   Advisory, never authority; wrapped in try/except so it cannot break chat.
6. **Envelope floors** (`chat/skill_contribution.py`) — `apply_investigation_floor` guarantees an
   investigation card is never silently empty; `apply_evidence_summary_floor` fills the summary
   from the grounding block and **caps confidence at Medium when no executed evidence** exists.
   Scoped to `{out_of_registry, near_105_question}`.

The one place several resources are genuinely fused into a single LLM prompt is the weak-case
composer: `guided_hunt_grounding.to_prompt_block()` injected as `t2_grounding_block`
(`pipeline.py:4639–4641`).

---

## Q3 — Node-to-node finding propagation

**A1 landed as `d0f3ad9` during this audit.** `operator.add` is replaced by
`_reduce_specialist_reports` (`:137–160`, keyed on `(delegation_id, specialist_id)`, raises on
conflict, returns key-sorted), plus the previously missing
`resource_planner_delegate → specialist_*` edges added to
`_documented_resource_planner_edges()`. The blocking content-parity assertion was fixed the way
the 2026-08-10 drift-log entry prescribed — the test now captures the payload at fan-out
(`_fan_out_reports`) instead of re-invoking specialists on final state. Verify slice re-run
here: **32 passed**. Descriptions of the amplification below are therefore historical.

**The four specialists** (`resource_planner_graph.py:395–432`) each return *partial* state
`{"specialist_reports": [report]}` — the amplification was never from the specialists; it came
from post-merge nodes returning full state through `_record` (`:191`).

- `rp_node_specialist_skill` (`:395`) — recomputes tier via `match_catalogue_tier` (**B1**). No proposals.
- `rp_node_specialist_knowledge` (`:408`) — the **only** substantive one;
  `build_knowledge_audit_report` (`planner/knowledge_specialist.py:110`).
- `rp_node_specialist_mcp` (`:417`) — hard-coded `hop_count=0`. Reads no state (**D1**).
- `rp_node_specialist_spl` (`:426`) — hard-coded `spl_source="template_or_fallback"`. Reads no
  state (**D2**).

**The one real cross-specialist influence.** Knowledge emits a `SpecialistProposal` filling
`args_template["reference_domains"]` on a knowledge-owned step, but only when the step's args
are blank (`knowledge_specialist.py:131`). `apply_specialist_reports`
(`planner/planner_hierarchy.py:215–255`) applies it, then `validate_bundle_policy_parity`
rejects any merge that would add steps, drop policy checks, or relax a blocked status (`:252`).
The enrichment is later read by `_knowledge_reference_domains` (`pipeline.py:9530`) and gates
dataset scope in `_reference_dataset_allowed` (`:9522`). **Real data dependency**, deliberately
narrow — SOC-KB retrieval is explicitly *not* narrowed (`pipeline.py:9511–9515`), and exact-ID
extraction runs before the filter so it can never subtract an ID the query named.

**Gap the plan should tighten:** `apply_specialist_reports` uses
`enriched_args.update(proposal.args_template)` (`planner_hierarchy.py:240`) — an **overwrite**.
"Fill-blank only" is enforced by convention inside the Knowledge producer, not at the merge.
**D0** does call for this; flag it as the single load-bearing line, because D1/D2 add two more
proposal producers on top of an unenforced merge.

**The composed step-walk does NOT sequence execution.** `walk_plan_steps`
(`planner/executor.py:109`) produces `step_walk_order`, but `build_step_walk_dispatch_schedule`
(`:180–191`) says plainly: composition order "is preserved in `walk.step_walk_order` for
**lineage**, but dispatch still follows the legacy stage pipeline until parity proves a safe
reorder" — it returns `_legacy_predicate_dispatch_schedule` (`:194`), a fixed predicate schedule
that only *filters* stages by blocked step ids. So D2 `composed_dispatch` runs the same fixed
stage order regardless of the plan's composed order, and no step's output is ever injected into
a later step's `args_template`. **Not mentioned in the review or the corrective plan.**

### The graph edge contract is self-certifying — measured, not inferred

`resource_planner_graph_edges()` (`:979–983`) returns
`introspected | _documented_resource_planner_edges()` — a **union**. Running the compiled graph
(langgraph 0.6.11) and diffing:

```
len(compiled get_graph().edges) = 4
  __start__ -> bootstrap
  bootstrap -> route_resolution
  route_resolution -> resource_planner_delegate
  resource_planner_delegate -> __end__
```

All **30** remaining edges — every specialist fan-out and fan-in, every dispatch branch, the
whole governance chain — exist *only* in the hand-written documented set. Two consequences:

1. **A1's anti-regression pin is unfalsifiable as written.** The plan requires "all four `Send`
   branches appear in `resource_planner_graph_edges()`". Adding them to
   `_documented_resource_planner_edges()` — exactly what the uncommitted diff does at `:952` —
   makes the assertion pass without proving anything about the compiled graph. The pin should
   introspect `_compiled_resource_planner_graph().get_graph()` directly, or the helper should be
   split so documented-only edges are distinguishable.
2. **Stale documented edges already exist and are undetectable.** The set claims
   `bootstrap → route_setup → resource_planner_delegate` (`:948–949`), but the compiled graph
   wires `bootstrap → route_resolution → resource_planner_delegate` (`:828–829`). `route_setup`
   is registered as a node (`:811`) with **no incoming or outgoing edge** — an orphan, so
   `graph_node_shadow_enrichment` never runs in the RP graph. No functional loss
   (`run_canonical_planning` covers route resolution + contract, and `rp_node_route_resolution`
   `:348` runs `graph_node_shadow_tail`), but the topology guard reports a path that does not
   exist.

**Dispatch selection** (`:483–494`): not-`planned` → D4; `answer_mode == "rag_only"` → D1
(tested **before** the composed check, so a knowledge answer is never widened into an
investigation); `has_composed_plan` → D2; else D3.

### Real dependencies vs co-located writes

**Spine 1 — RAG → SPL slot-fill → execution gate.** `rag_early` writes `soc_kb_retrieval`
(`pipeline.py:3208`) → `spl_source_resolve` reads it (`:3266`) and passes it to
`resolve_spl_source_profile` (`:3296–3303`) to fill `<index>`/`<sourcetype>` slots → on full
resolution it **rewrites** `candidate_spl` and `spl_validation` (`:3316–3323`) →
`graph_node_execution` gates on that `spl_validation` (`:2917`, `:2993`). A genuine
step-N-output-into-step-N+1-input chain.

**Spine 2 — pre-SPL MCP discovery → SPL compiler. LIVE on this host.** The gate is
`ai_soc_pipeline_dispatch_v2_enabled`, `False` at `config.py:403` but
**`AI_SOC_PIPELINE_DISPATCH_V2_ENABLED=true` in this host's `.env`**.
`graph_node_workflow_spl` calls `graph_node_pre_spl_mcp_discovery` inline at `pipeline.py:2760`;
it writes `pipeline_dispatch["runtime_context"]["mcp_discovery_context"]` (`:2728`), read at
`:2829–2831` into the LLM SPL plan compiler and at `:2836–2841` into
`preference_from_discovery_context`, which can rewrite `candidate_spl`/`spl_validation` toward a
saved search (`:2852–2860`). `rp_node_workflow_spl` calls `graph_node_workflow_spl`, so this is
reachable. **This is the one place MCP output feeds SPL construction.** Note `CLAUDE.md` still
describes this flag as "default false, flag-off byte-identical".

**Other couplings:**

- `evidence_plan` policy booleans → `_apply_policy_veto` mutating `execution` / `spl_validation`
  (`resource_planner_graph.py:654–697`) — **real**, policy override.
- Broaden-on-empty (0 rows → broadened retry, `pipeline.py:3043–3060`) — **real
  evidence→re-plan**, but cross-turn, HIL-gated, default-off.
- `execution` / `mcp_evidence` / `soc_kb_retrieval` / `reference_resolution` → `source_evidence`
  / `structured_context` — **co-located writes into a shared bag**, fanned in exactly once at
  finalize (`pipeline.py:3556–3594`, `_context_stage` `:9677–9782`). No incremental accumulation;
  `source_evidence` and `structured_context` are each written exactly once.
- **No cycle exists.** The compiled RP graph is a strict DAG — no back-edge.

**`ChatPipelineState` has zero `Annotated` reducers** (`pipeline.py:359–477`, ~90 keys) — every
channel is last-write-wins. `decision_log` is documented as "append-only" but appends are manual
inside `emit_decision_record`, not reducer-enforced.

**Decision-record `inputs_ref`/`outputs_ref` are hand-written labels, not dataflow, and several
are wrong** — `rp_node_decide_facts` (`:640–649`) declares it outputs
`severity_decision`/`mitre_mappings` and writes neither; `rp_node_answer_guard` (`:699–708`)
declares `answer_guard` and writes nothing; `rp_node_mcp_execution_gate` (`:595–604`) declares an
input `normalized_spl` that is not a state channel. Do not read the decision log as a dependency
graph — relevant because **D3** proposes summarizing posture into decision records.

---

## Execution status — do not duplicate work (checked 2026-08-10, `master@d0f3ad9` + dirty tree)

The corrective plan is **being executed in this same worktree right now**. Before acting on
anything below, re-check `git status` — several findings here were already fixed while this
audit was being written.

| Audit finding | Corrective-plan item | Execution status |
|---|---|---|
| #7 specialist-report amplification | **A1** | ✅ **DONE — committed `d0f3ad9`** ("fix(planner): bound specialist report fan-in"). Verify slice re-run here: **32 passed**. |
| Gap #1 self-certifying edge contract | (none) | ⚠️ **OPEN, and now shipped.** `d0f3ad9` added the four `Send` edges to `_documented_resource_planner_edges()`; the assertion passes via the union. Still unverified against the compiled graph. |
| #1, #2 tier authority / binding candidate | **B0, B1** | 🔄 **IN FLIGHT, uncommitted.** `test_canonical_catalogue_tier_authority.py` untracked; `match_tiers.py`, `live_router_bind.py`, `canonical_handoff_builder.py`, `canonical_planning_orchestrator.py`, `canonical_planning_input.py`, `pipeline.py` all dirty. |
| #3 bare-ID regex grants T0 | **D7 / B0** | 🔄 In flight with B0. |
| #4, #5, #6 reference-qualification markers | **C0** | ⬜ Not started. Finding #6 (widen the sweep to `_ACTION_MARKERS` / `_INVESTIGATION_MARKERS`) is the only non-duplicative part. |
| #8 MCP/SPL specialist stubs | **D1, D2** | ⬜ Not started — see the D1 caveat below. |
| #9 `apply_specialist_reports` overwrite | **D0** | ⬜ Not started. |
| #10 subtype-field narrowing | **A2** | ⬜ Not started (correctly deferred out of A1). |
| #11–#14 answer-mode, telemetry, seam, docs | **E0, E1, F0, G0** | ⬜ Not started. |
| Gaps #2–#8 | (none) | ⬜ Open — the genuinely additive part of this audit. |

### Finding #2 is overtaken by events — the executor did better than the plan text

My audit said B1's premise was stale: `apply_live_catalogue_bind` was unreachable on both
production runtimes, so B1's "compatibility wrapper while callers are migrated" clause was
unnecessary work. The in-flight B1 change **resolved this correctly and went further** — it
added a *new* call site inside `graph_node_init_routing` (`pipeline.py:1018`, function at
`:969`), which **is** on the live path via `rp_node_bootstrap`. The binding candidate now
reaches state as `catalogue_binding_candidate` / `observed_catalogue_match_path` /
`effective_catalogue_match_path`, consumed at `canonical_planning_orchestrator.py:137`. All
three channels are declared in `ChatPipelineState` (`pipeline.py:470–472`), so LangGraph will
not drop them.

So the D6 guards (`reconcile_catalogue_binding_candidate` — non-SOC, unsafe, ambiguity,
exact-authority) now execute on a live path rather than a dead one. **Treat finding #2 as
closed in practice.** What remains is a documentation defect: the plan's premise table row 1
still asserts the old (incorrect) reason, so the recorded rationale no longer matches the
implementation.

Residual: the two older call sites at `pipeline.py:1372` and `:1396` remain inside
`graph_node_query_to_intent`, which is still unreachable in production. Dead, harmless,
and worth removing when B1 is finalized rather than left as a third invocation.

### Where the corrective plan is still wrong

Only two places, both narrow:

1. **B1 premise row (documentation).** As above — the stated justification for keeping the
   compatibility surface was wrong. The work landed correctly anyway; the plan's premise table
   and the review's "Correction 2" should be updated so the next reader does not re-derive a
   false reason.
2. **D1's `candidate_tool_names` field assumes discovery output that never exists.** The
   contract defines it as a "bounded intersection of safe **discovered** names, registry
   resources, plan purpose, and deterministic capability policy". Discovery hops do not run in
   production (fenced by `canonical_forbids_legacy_evidence_planning`), so the discovered-names
   input is always empty. Drop that input and source the field from registry + plan purpose +
   capability policy only, or the field will look richer than it is.
   **D1 is otherwise sound** — `planned_hop_count` is *not* a no-op: the live composer does emit
   `mcp_execution` steps (`planner/composer.py:511`), so counting them is real information.
   Only `mcp_discovery` steps are unreachable (`composer.py:200`, guided rail, unwired).

Nothing else in the plan is incorrect. D2, D0, A2, C0, E0, E1, F0, G0 all rest on premises this
audit independently confirmed.

## Findings vs corrective-plan coverage

| # | Finding | Plan item | Verdict |
|---|---|---|---|
| 1 | Skill specialist recomputes tier instead of reading canonical routing | **B1** | Covered; **scope shrinks** — see #2 |
| 2 | `match_catalogue_tier`'s only *other* consumer (`apply_live_catalogue_bind`) is unreachable on both production runtimes | **B1** premise | **Premise stale.** B1's compatibility-wrapper clause is unnecessary work |
| 3 | `match_tiers._reference_match` grants T0 on a bare ID regex, before any intent check | **D7 / B0** | Covered |
| 4 | `"our "` substring denies T0 on "four hours" / "an hour ago" | **C0** | Covered |
| 5 | Bare `vulnerable` / `exposure` markers over-trigger environment status | **C0** | Covered |
| 6 | Same unbounded-`in` defect in `_ACTION_MARKERS` (`"block"`) and `_INVESTIGATION_MARKERS` | **C0** | **Partial** — widen the sweep to all five lists |
| 7 | `specialist_reports` amplification (16,384 / 8,192) | **A1** | ✅ **DONE — committed `d0f3ad9`** |
| 8 | MCP + SPL specialists are constant stubs reading no state | **D1 / D2** | Covered |
| 9 | `apply_specialist_reports` uses `dict.update` — overwrite, not fill-blank | **D0** | Covered; single load-bearing line before D1/D2 add producers |
| 10 | `PlannerIteration` / `WorkBundle` narrow subclass reports to base | **A2** | Covered (correctly deferred out of A1) |
| 11 | Answer-mode ordered `if` chain; `alert_summary` + SPL contradiction | **E0 / D8** | Covered |
| 12 | `emit_planning_event` does not validate the event name | **E1** | Covered |
| 13 | `graph_node_lane_and_canonical_planning` is 569 lines | **F0** | Covered |
| 14 | Doc/diagram corrections | **G0** | Covered |

## Gaps NOT covered by the corrective plan

Ordered by how much they change the answer to the three questions.

1. **The graph edge contract is a union, so topology assertions are self-certifying.** Only 4 of
   34 edges are introspectable; the rest are hand-written. A1's own Send-edge pin passes by
   editing the documentation it is supposed to verify, and the stale `bootstrap → route_setup`
   pair plus the orphan `route_setup` node stay undetectable. **Fold into A1** — same helper,
   same commit.
2. **The composed step-walk does not sequence execution** (`executor.py:180–192`). Plan order is
   lineage only; the schedule is fixed legacy predicates. This directly caps how comprehensive a
   T4 multi-resource answer can be, and nothing in the plan addresses it.
3. **The MCP discovery/chronology/observer machinery is fenced off from production** by
   `canonical_forbids_legacy_evidence_planning` (`pipeline.py:1758–1768`), while
   `docs/architecture/mcp_tool_routing.md` documents it as the live flow. **D1 must not assume
   discovery hops exist**; G0's doc sweep should cover that file.
4. **Every LLM planning surface is unreachable, shadow-only, or unwired — T4 planning is
   deterministic.** Largest gap between documented architecture and running system; the
   corrective plan does not touch it. `llm_plan_bridge.py:15–19`'s own docstring still claims
   live promotion "during `graph_node_evidence_planning`". Related: the shadow runner still
   *calls* a model per eligible turn on this host and discards the result.
5. **`MAX_MCP_HOPS = 6` is not a live bound.** `initialize_loop` is only called inside the fenced
   node, so `loop_initialized(state)` is always False in production; the hop cap, the O5c recipe
   path, and `_run_discovery_loop_imperative` never execute. Live MCP is the single gated stage
   `rp_node_mcp_execution_gate` → `graph_node_execution`.
6. **`docs/architecture/chat_pipeline_state_v2_and_node_trace.md` is stale** — describes a 9-node
   imperative pipeline behind flags that now default the other way. Add to G0.
7. **`CLAUDE.md` describes `AI_SOC_PIPELINE_DISPATCH_V2_ENABLED` as default-off / byte-identical**,
   but it is `true` on this host and enables a real MCP→SPL data dependency. Doc/posture mismatch.
8. **Decision-record `inputs_ref`/`outputs_ref` are unverified labels and several are wrong.**
   D3 proposes putting posture summaries into decision records; worth a correctness pass first.

## Recommended sequencing

**Finish the corrective plan first. Do not re-open it mid-execution.** Reasons, in order of
weight:

1. B0/B1 are uncommitted in this worktree right now. Inserting new items would collide with
   live edits to six files, and this plan has already lost two execution attempts to
   concurrent-session drift (drift log, 2026-08-08 and 2026-08-09).
2. Nothing in the audit is a correctness or safety defect. The invariant check on the working
   tree came back clean across all seven groups, parity holds at 120/0/0, and every open gap is
   a *verification-strength* or *documentation-accuracy* problem, not a live bug.
3. The plan's own stop conditions require halting on premise drift. Six of the eight new gaps
   change premises for items that have **not started yet** (D1, G0), so they can be absorbed as
   scoped edits at the right moment rather than as new checklist items now.

### Two edits to make inside the existing plan, not as new work

- **D1 — remove the discovered-names input** from the `candidate_tool_names` contract row, and
  add a line stating discovery hops do not run on the live path. One table edit, before D1
  starts. Prevents building a field against a phantom input.
- **G0 — add two stale docs to the sweep**: `docs/architecture/mcp_tool_routing.md` (documents
  the fenced discovery loop as the live flow) and
  `docs/architecture/chat_pipeline_state_v2_and_node_trace.md` (9-node imperative pipeline,
  flags inverted). Also correct `CLAUDE.md`'s claim that
  `AI_SOC_PIPELINE_DISPATCH_V2_ENABLED` is default-off/byte-identical — it is `true` on this
  host and enables a real MCP→SPL dependency. G0 already owns doc corrections; this is three
  more files in the same item.

Also worth a one-line premise correction in the plan's own table (B1 row), so the recorded
rationale matches what shipped.

### What justifies a second plan, after this one closes

A separate plan, because these are architectural questions rather than corrections, they share
a single theme (*the running system is narrower than the documented one*), and each needs its
own COE decision about intended behaviour:

- **Gap #1** — make the edge contract falsifiable. Split `resource_planner_graph_edges()` so
  documented-only edges are distinguishable from introspected ones, then remove the orphan
  `route_setup` node and its two fabricated edges. Small, self-contained, and it retroactively
  gives A1's shipped pin real teeth.
- **Gap #2** — decide whether the composed step-walk should actually sequence dispatch, or
  whether the plan's step order stays lineage-only. Today `build_step_walk_dispatch_schedule`
  says "until parity proves a safe reorder"; nobody has since asked whether to prove it.
- **Gaps #3, #4, #5** — decide the intended posture for the fenced discovery loop, the
  unreachable LLM plan bridge, and the shadow planner call that still burns a model hop per
  turn and discards it. These are one decision, not three: *does canonical mode intend to
  retire this machinery, or re-wire it?* Until that is answered, D1's MCP specialist and any
  future "LLM plans across resources" claim rest on undefined ground.
- **Gap #8** — correctness pass on decision-record `inputs_ref`/`outputs_ref` before D3 adds
  more of them.

Recommended order: close the corrective plan through G1 → make the two in-plan edits above as
they come up → then open the second plan with gaps #1 and #8 first (cheap, mechanical) and the
posture decision (#3/#4/#5) raised to COE before any code.

## Verification

Audit only — no runtime edits. Method:

- Every claim anchored to a `file:line` read this session, not inferred from docs.
- Where a doc and the code disagreed, code won and the doc is listed as stale.
- Three claims checked by execution rather than reading:
  - compiled-graph edge introspection —
    `PYTHONPATH=../backend:.. python3 -c "…_compiled_resource_planner_graph().get_graph()"`
    → 4 edges, diffed against `_documented_resource_planner_edges()`;
  - reachability of `apply_llm_primary_resource_plan` and `run_resource_plan_shadow` — grep for
    call sites, then enclosing-function resolution by line span;
  - `is_canonical_authoritative()` → hardcoded `True`, read directly.
- Two sub-agent claims that contradicted an earlier reading were re-verified independently before
  adoption; the bridge-reachability finding overturned the first pass and is corrected in place.

**Not verified — deliberately out of scope for a read-only audit:** no `/chat` turn was run, so
runtime-behaviour claims rest on static reachability, not observed traces. Cheapest empirical
confirmation is a single T4 query with `control_plane_trace` inspected for
`provenance.llm_bridge`, `resource_plan_shadow_trace`, and `rp_graph_trace.visited_nodes`.

---

## Post-G1 disposition (2026-08-10)

The corrective plan
[`2026-08-08_1824`](2026-08-08_1824_architecture-review-corrective-actions.md) closed at
**16/16, `status: done`, final commit `e5c1937`**. Runtime work on it is accepted as complete
and is **not** reopened by anything below.

Everything above this line is the historical audit, preserved as written. This section is the
only authority on what remains open. Gap numbering matches "Gaps NOT covered by the corrective
plan".

| Gap | Subject | Disposition |
|---|---|---|
| **1** | Topology self-certification | **OPEN** |
| **2** | Composed step order vs execution sequencing | **OPEN** |
| **3** | Legacy discovery posture | **Documentation CLOSED (G0); retire-vs-rewire decision OPEN** |
| **4** | LLM planning / shadow architecture | **OPEN** |
| **5** | `MAX_MCP_HOPS` posture | **OPEN — coupled to Gap 3** |
| **6** | Stale pipeline-state documentation | **CLOSED by G0** |
| **7** | dispatch-v2 documentation mismatch | **CLOSED by G0** |
| **8** | Decision-record `inputs_ref`/`outputs_ref` | **OPEN** |

### Still open

**Gap 1 — the edge contract cannot fail.** `resource_planner_graph_edges()` returns
`introspected | _documented_resource_planner_edges()`. Only 4 of 34 edges are introspectable, so
an assertion against that union is satisfied by editing the documentation it checks. A1 shipped
under exactly that assertion (`d0f3ad9`), and the stale `bootstrap → route_setup` pair plus the
orphan `route_setup` node remain undetectable. Cheapest real fix: assert against
`_compiled_resource_planner_graph().get_graph()` directly, or split the helper so
documented-only edges are distinguishable.

**Gap 2 — the composed plan's order is lineage, not schedule.**
`build_step_walk_dispatch_schedule` preserves `step_walk_order` "for lineage" and returns a fixed
legacy predicate schedule; the plan's composed order contributes only `blocked_step_ids`. Its own
comment says "until parity proves a safe reorder" — nobody has since asked whether to prove it.
This caps how comprehensive a multi-resource answer can be.

**Gap 3 (decision half) + Gap 5 — one decision, not two.** The question is whether canonical mode
intends to **retire** the fenced legacy lane or **re-wire** it. `MAX_MCP_HOPS = 6` is inert for
the same reason the lane is (`initialize_loop` is only reached inside the fenced node), so
answering Gap 3 answers Gap 5. Needs a COE decision before any code.

**Gap 4 — LLM planning surfaces.** The plan bridge's only call site sits behind
`canonical_forbids_legacy_evidence_planning`; the shadow runner hard-sets
`promotion_blocked=True`; the guided-hybrid rail is wired only into the imperative pipeline.
Live consequence worth pricing: on this host the shadow planner still makes a real model call per
eligible turn and discards the result, and it cannot be switched off independently —
`resource_plan_shadow_enabled()` piggybacks on `final_synthesis AND live_synthesis`.

**Gap 8 — decision-record refs are labels, not dataflow**, and several are wrong
(`rp_node_decide_facts` declares outputs it does not write; `rp_node_mcp_execution_gate` declares
an input that is not a state channel). Worth a correctness pass before anything else writes to
those records.

### Closed, and the distinction that must survive

Gaps 6 and 7 were closed by **G0** (`a717d4c`), together with the documentation half of Gap 3.

**Do not collapse these two mechanisms — they are different, and both statements below are
load-bearing:**

- **Legacy multi-hop Resource Planner discovery is fenced.** `graph_node_evidence_planning` fails
  closed under canonical mode with `canonical_forbids_legacy_evidence_planning`. The chronology
  proposal, discovery hops, data-silence advisory, O5c recipe path and `evidence_observer` do not
  run on a canonical `/chat` turn.
- **Bounded pre-SPL MCP discovery is live** when `AI_SOC_PIPELINE_DISPATCH_V2_ENABLED` is true
  (it is, on the COE host). `graph_node_workflow_spl` calls `graph_node_pre_spl_mcp_discovery`
  inline, and the result **may feed the SPL plan compiler** and saved-search preference.

So "MCP discovery never runs" is wrong, and "the discovery loop runs" is also wrong. Any Plan 2
item, and the MCP specialist's `candidate_tool_names` contract, must respect that split.

### Sequencing for Plan 2 (not started)

Gaps **1** and **8** first — mechanical, self-contained, no policy question. Gap **2** is a design
call. Gaps **3/4/5** should be raised to COE as a single posture decision before any code, since
the MCP specialist contract and every future "the LLM plans across resources" claim depend on the
answer.
