# Routing authority map (Plan 5)

B0 wrote this as a pre-change audit at baseline `2f678b9` + Phase A. **The sections below that audit remain as the B0 snapshot.** Live authority after Phases B–D is the current-state section first.

Related: [`phase_contract_and_schedule.md`](phase_contract_and_schedule.md), [`docs/evals/plan5_architecture_and_routing_report.md`](../evals/plan5_architecture_and_routing_report.md).

## Current live flow (post Plan 7 / Plan 8)

```
POST /chat
  → T1–T3 understand_query
  → UNDERSTANDING sufficiency (optional T4; default OFF in repo, ON on this host's development profile)
  → deterministic T4 validation/merge → FINAL ResolvedQueryContract
  → clarification decision → final owner/route
  → ResourcePlan + PhaseContract → existing Resource Planner hub
  → knowledge / SPL / MCP / validation / HIL ordered by the compiled schedule
```

Authoritative seams:

| Concern | Authority | Default |
|---|---|---|
| Understanding | Final `ResolvedQueryContract` before clarification, ownership, and ResourcePlan | Always on canonical turns |
| Final skill | Ownership/entry signal only; not a capability veto (`ai_soc_live_capability_enforcement_enabled`) | enforcement **false** |
| T4 semantic hop | Bounded interpreter only; no tools/MCP/route/capability grants | repo **false** @ 2.0s; F3 serving still a blocker |
| Schedule merge | `AI_SOC_RESOURCE_PLAN_EXECUTION_ENABLED` | repo **false**; **normal** when on. dispatch-v2 cannot win while this is on |
| PlanDelta | Conditional Plan 8 extension | `NOT_REQUIRED_FOR_CURRENT_SCOPE` |
| Capability satisfaction | schedule-level, not "one skill grants everything" | Diagnostic/deny only |

Live `build_query_to_intent` at `canonical_planning_orchestrator.py:447` and `:516` does **not** pass `routed_skill`. Known-lane `primary_intent` is not overwritten with the routed skill. Frozen truth-set arms still call `select_route_from_understanding` / `route_skill` and therefore do **not** observe L4/L5.

D1 (closed): the 7 measured live-posture rows that commit `spl_generation` are `RATIFIED_FOR_MEASURED_ROWS` — not a family-wide ownership rule. Eight T4 paraphrases (`para.003/004/005/006/007/008/012/015`) are `DEFERRED_T4_SEMANTIC_SERVING_LIMIT`.

---

# B0 audit snapshot (pre-change)

Live `/chat` routing authority as of baseline `2f678b9` + Phase A (`b9ec0cc`). Runtime code is authoritative; classifications guided Phase B/C work: **PRESERVE** · **MOVE** · **ADAPT** · **RETIRE** · **DEFER**.

## Canonical call order (query → final skill)

```
POST /chat
  routes_chat.py:116-124
    └─ run_chat_via_resource_planner_graph()     [default: langgraph on]
         resource_planner_graph.py:328-340 rp_node_bootstrap
           ├─ graph_node_init_routing             pipeline.py:984-1065
           │    ├─ understand_query              parser.py:86-170
           │    ├─ route_skill                    skill_router.py:50-236
           │    │    └─ select_route_from_understanding  select_route_from_understanding.py
           │    └─ apply_live_catalogue_bind      pipeline.py:1032-1039 → live_router_bind.py
           └─ run_canonical_planning              canonical_planning_orchestrator.py:89-114
                └─ _resolve_lane_intent_and_details  :299-646
                     ├─ build_query_to_intent (routed_skill=…)  :445-452, :518-525  ← contamination
                     ├─ qualify_reference_query → T0 promotion  :543-565
                     └─ intent_classification assembly
           rp_node_route_resolution → graph_node_route_resolution  pipeline.py:2302-2372
             └─ adjudicate_route                   route_adjudication.py:90+
           graph_node_route_contract               pipeline.py:2375-2385  ← FINAL skill commit
             └─ routed["skill"] = route_contract.canonical_skill  :2380
           dispatch (composed / guided / session_spl_refine)  pipeline.py:648-687
```

**Rollback path** (`LANGGRAPH_ORCHESTRATION_ENABLED=false`): `pipeline.py:554-641` — same canonical seam after `init_routing`. **PRESERVE**.

## `routed["skill"]` writers (production)

| Order | Writer | Location | Effect | Class |
|------:|--------|----------|--------|-------|
| 1 | `route_skill` → `state["routed"]` | `pipeline.py:1014-1059` | Initial provisional skill | **PRESERVE** |
| 2 | `select_route_from_understanding` | `select_route_from_understanding.py` | Builds route dict consumed by `route_skill` | **PRESERVE** |
| 3 | `clarification_route` / `LOW_CONFIDENCE_ROUTE` | `governance.py:173-180`, `deterministic_router.py:72` | `knowledge_recall` + needs_clarification | **PRESERVE** |
| 4 | `normalize_assisted_selection` | `governance.py:252-263` | LLM advisory replace (Plan 4 D3 gate) | **ADAPT** (narrow gate preserved) |
| 5 | T0 reference qualification | `canonical_planning_orchestrator.py:550-554` | `routed["skill"] = "knowledge_recall"` | **MOVE** — belongs in pre-route qualification, not intent stage (B3) |
| 6 | `graph_node_route_contract` | `pipeline.py:2379-2380` | `routed["skill"] = route_contract.canonical_skill` | **PRESERVE** — **authoritative final commit** |

Final skill resolution chain: `run_contract_builder.py:280-293` — `route_adjudication.final_route` → `routing_skill_resolution.effective_skill` → `routed.skill` fallback.

**Non-writers:** `apply_live_catalogue_bind` (`live_router_bind.py:128-195`) updates provenance only. **PRESERVE**.

## `build_query_to_intent` inputs and call sites

Signature: `intent_classifier.py:1147-1155` — `query`, `query_understanding`, `routed_skill`, `routing_provenance`, `llm_intent_advisory`, `answer_shape_override`.

| Call site | Location | `routed_skill` passed? | LLM advisory? | Class |
|-----------|----------|------------------------|---------------|-------|
| Known lane (T1–T3) | `canonical_planning_orchestrator.py:445-452` | **Yes** | No | **ADAPT** — remove route contamination (B3) |
| Guided/T4 lane | `canonical_planning_orchestrator.py:518-525` | **Yes** | No | **ADAPT** |
| Handoff resume | `canonical_query_to_intent_resume.py:141-148` | Yes | No | **ADAPT** |
| Dead node | `graph_node_query_to_intent` `pipeline.py:1395-1404` | Yes | Yes (+ shape override) | **RETIRE** from live |
| Eval harness | `scripts/eval_routing_truth_set.py:133` | varies | No | **DEFER** |

**Known contamination (B3 target):**

- `routed_skill` flows into `build_candidate_mappings` (`intent_classifier.py:1157-1160`).
- Known lane overwrites `primary_intent` with routed skill (`canonical_planning_orchestrator.py:479`).
- T0 promotion writes `routed["skill"]` inside intent stage (`:550-554`).

## Clarification decision points

| Layer | Trigger | Location | Outcome | Class |
|-------|---------|----------|---------|-------|
| Routing | Context refs without alert markers | `governance.py:166-170` | `clarification_route` | **PRESERVE** |
| Routing | Low-confidence / weak QU | `select_route_from_understanding.py:515-534` | `knowledge_recall` default | **PRESERVE** |
| Intent | Destructive + run-SPL, block/contain, non-SOC, MITRE w/o alert | `intent_classifier.py:257-362`, `:670-682` | `human_review` / clarification families | **PRESERVE** |
| Intent | Terminal ambiguity floor | `intent_classifier.py:1120-1128` | clarification | **PRESERVE** |
| Canonical | Known lane missing user-only fields | `canonical_planning_orchestrator.py:482-494` | `clarification_required` | **PRESERVE** |
| Adjudication | `intent.requires_clarification` | `route_adjudication.py:203-209` | `knowledge_recall` + `intent_clarification` | **PRESERVE** |
| Adjudication | SPL-authoring exception | `route_adjudication.py:141-149` | May override clarification for `spl_generation` | **ADAPT** |
| Planning gate | `clarification_required` | `canonical_planning_orchestrator.py:904-945` | No EvidencePlan | **PRESERVE** |

## Answer-shape signals influencing routing

| Signal | Source | Routing effect | Flag | Class |
|--------|--------|----------------|------|-------|
| `soc_investigation_shaped` / `route_skill_candidate` | `parser.py:148-163` | QU rescue floors in `select_route_from_understanding` | — | **PRESERVE** |
| `hybrid_advisory_source_health` / `process_aware_ot` | `select_route_from_understanding.py:247-268` | `guided_investigation` | `ai_soc_t2_answer_shape_enabled` | **ADAPT** |
| `reference_taxonomy` shape | `select_route_from_understanding.py:293-302` | `knowledge_recall` | T2 flag | **ADAPT** |
| T2 shape floor (non-hunt) | `select_route_from_understanding.py:325-345` | `guided_investigation` | T2 flag | **ADAPT** |
| Detection / SPL artifact / live-data floors | `select_route_from_understanding.py:311-384` | `spl_generation` or `guided_investigation` | partial | **PRESERVE** |
| `hybrid_advisory_*` from `classify_answer_shape` | `query_signals.py:488-493` | feeds `classify_intent` | T2 | **ADAPT** |
| Shape advisor promotion (dead path) | `pipeline.py:1361-1384` | can set `routed["skill"]` | — | **RETIRE** from live |

`answer_shape_router.classify_answer_shape` (`answer_shape_router.py:284+`) is the deterministic signal source. **PRESERVE** as signal; **ADAPT** where it overrides registry-backed routes.

## Tier qualification authority (T0–T4)

Three distinct tier names — do not conflate:

| Name | Authority | Location | Meaning | Class |
|------|-----------|----------|---------|-------|
| `initial_tier` | **`lane_router.py`** | `:25-33` | Parser `match_path` → T1–T4 | **PRESERVE** — live-path tier authority (B2) |
| `resolved_tier` | reference qualification + orchestrator | `reference_qualification.py`, `canonical_planning_orchestrator.py:550-565` | T4 → T0 promotion | **PRESERVE** |
| `binding_candidate_tier` | **`match_tiers.py`** | `:179-220` | Catalogue bind *proposal* only | **MOVE** — retire duplicate vocabulary (B2) |

`lane_router` T-path sets (`lane_router.py:9-19`):

- **T1:** `exact_105_question`, `exact_105_plus_use_case_catalog`
- **T2:** `use_case_catalog`
- **T3:** `near_105_question`, `semantic_105_question`, `fuzzy_alias_catalog`
- **T4:** `out_of_registry`, weak paths, empty
- **T0:** not from parser — only via `qualify_reference_query.resolves_to_t0`

`match_tiers.py:23` duplicates T-path literals with T3 disagreement (`fuzzy_alias_catalog` placement). **RETIRE** duplicate in B2; import from `lane_router`.

## Dead / non-live nodes (not implementation seams)

| Node | Location | Production caller? | Class |
|------|----------|-------------------|-------|
| `graph_node_query_to_intent` | `pipeline.py:1079-1440` | **No** | **RETIRE** from live authority |
| `linear_graph_legacy` | `linear_graph_legacy.py:114` | Tests only | **RETIRE** |
| `planner_led_shadow_graph` | `planner_led_shadow_graph.py:111` | Parity harness only | **RETIRE** from prod docs |
| `graph_node_evidence_planning` | `pipeline.py:1795+` | Fenced when canonical on | **DEFER** |
| Split routing trace nodes | `routing_skill_nodes.py:16-80` | Trace-only flag | **PRESERVE** |

## Phase B target shape (B0; now shipped)

```
QUERY
  ↓ deterministic qualification / bounded semantic (T4 only, default OFF)
ResolvedQueryContract   ← no skill, no execution authority
  ↓ route adjudication
primary skill (route/ownership signal, not sole capability enumerator)
  ↓ ResourcePlan + PhaseContract → merge_schedule (default OFF)
one governed executable schedule
```

B3 removed: provisional `routed_skill` as input to understanding; `primary_intent` overwrite; T0 `routed["skill"]` write inside intent stage.

## Capability compatibility (current posture)

`resolve_capability_compatibility` (`skill_intent_compatibility.py:119`) — fail-closed, correct. Reused by `adjudicate_route` behind `ai_soc_live_capability_enforcement_enabled` (**default false**). Dispatch-v2 still consumes it at `pipeline_dispatch_builder.py:438` (also default off). Eval instrument: `evals/routing_truth_set.py:300`.

B5 measured ON: 0 truth-set route improvements, `cisco.ot.029` demoted `spl_generation`→`knowledge_recall`. Decision: `DEFAULT_OFF_ARCHITECTURALLY_DEFERRED`. Required capabilities are satisfied at **schedule** level; see [`phase_contract_and_schedule.md`](phase_contract_and_schedule.md).