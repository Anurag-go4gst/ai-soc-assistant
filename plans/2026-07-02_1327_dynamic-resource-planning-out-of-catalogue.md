---
name: dynamic-resource-planning-out-of-catalogue
overview: "Rev 2.2 — LLM-primary resource planning for every control-plane path with deterministic safety guardrails: MCP eligibility on all tiers through existing gates, hardened SPL vigilance, CVE/MITRE skill utilization, LLM output pre-processor, canonical fact spine across nodes, post-answer agentic actions, and flag rightsizing."
status: draft
date: 2026-07-02
canonical_plan: plans/2026-07-02_1327_dynamic-resource-planning-out-of-catalogue.md
loop_runner: plans/LOOP_RUNNER_TEMPLATE.md
---

# Dynamic resource planning — LLM-primary planner, deterministic guardrails (rev 2.2)

## User directives (2026-07-02, supersede rev 1 decision gates)

1. **DG-1 resolved: MCP eligible on all control-plane paths**, including out-of-catalogue — the planner may request discovery/search resources on every tier, but backend execution still requires existing operator flags, validator-approved `normalized_spl`, and per-call analyst confirmation. Extra vigilance ensures harmful SPL never reaches the MCP gate.
2. **DG-2 resolved: do not design around VPS LLM speed.** Target production runs ~6000 tok/s; VPS ~6 tok/s is a dev-infra constraint expressed in config (budgets), never in architecture. Raise VPS budgets; remove artificial call caps where safe.
3. **LLM takes active planning decisions** (which tools, when MCP, when RAG, how many calls); deterministic layer becomes the safety guardrail, not the decision maker. Take the LLM plan bridge out of shadow.
4. **LLM never calls MCP directly** — backend mediates all tool access (unchanged).
5. **Intelligent pre-processor** so LLM output is actually used: robust extraction/repair instead of dropping imperfect JSON.
6. **CVE and MITRE skills** become planner-selectable resources; their utilization must measurably increase.
7. **Flag rightsizing:** ~199 env flags is confusing; audit and consolidate — **with extreme caution on any deletion; start deleting only when fully satisfied** (see DG-4 and 7.x).
8. **Post-answer agentic actions:** after the final answer, the system may propose and (with approval) execute action tools — ticket generation first, **mock ITSM adapter** (DG-3 resolved).
9. **Canonical fact spine:** facts collected by node 1 must reach nodes 2 and 3; all plan/execution telemetry stored per turn. Today facts are dropped or ignored between nodes.

## Governance invariants (unchanged)

- LLM proposes plans/queries/actions as data; deterministic code validates, binds, gates. Executability, severity, MITRE status stay deterministic authority.
- `candidate_spl` never executable; only validator-approved `normalized_spl` enters the MCP execution gate; per-call analyst confirmation stays for evidence search and for every post-answer action.
- LLM never calls MCP or action tools directly.
- Safety invariants (SPL blocklist, redaction, no-prompt-to-MCP, injection defense) are code, not flags — they cannot be configured off. Flag rightsizing must convert any safety-relevant flag into hardcoded behavior, not merely delete it.
- Mock connector remains fixture-only; live Splunk activation stays env + credentials (operator-owned).
- "MCP eligible" in this plan means evidence-plan eligibility and planner reachability. It does **not** flip `MCP_GLOBAL_EXECUTION_ENABLED` / per-server defaults, does not bypass HIL, and does not permit discovery/search when the connector is unavailable or blocked by policy.

## Decision gates

- **DG-3 — RESOLVED (2026-07-02): mock ITSM adapter.** Phase 6 ships `action_tool:create_ticket` against the mock adapter only. A real ServiceNow/Jira/other connector is out of scope until the user names the target system + credentials path; when that happens it becomes a new plan item, not a silent extension.
- **DG-4 (flag removal batches):** the flag-audit doc (0.4) proposes dispositions; the user approves **each batch** before it is implemented. Deletion starts only when the satisfaction criteria in 7.1 are met for that batch. When in doubt about any single flag, keep it and record the doubt in the audit doc — never delete to hit the key-count target.

## Stop conditions

- All checklist items checked with recorded evidence, **or**
- Same verification gate fails twice on one item, **or**
- Decision gate reached (DG-4 before each Phase 7 batch; any new real-ITSM request) — **stop and ask**

## Dependency order

`0.1 → 0.2 → 0.3 → 0.4 → 1.1 → 1.2 → 1.5 → 1.3 → 1.4 → 2.1 → 2.2 → 2.3 → 2.4 → 3.1 → 3.2 → 3.3 → 5.1 → 5.2 → 5.3 → 5.4 → 5.5 → 6.1 → 6.2 → DG-4 approval → 7.1 → 7.2 → 8.1 → 8.2`

Parallel-safe: 4.1 → 4.2 after 0.3; 4.3 joins only after both 4.2 and 1.3 (planner-selectable CVE/MITRE resources need the live promoted-plan path). 1.1 (pre-processor) can start immediately after 0.2; 1.5 (budgets) after 0.2; 0.4 (flag audit doc) independent after 0.1.

## Checklist

### Phase 0 — Baseline, guards, flag audit (no behavior change)

- [x] **0.1** — Out-of-catalogue answer-quality probe set + scorecard
  - **Do:** Create `backend/app/evals/out_of_catalogue_probes.json`. Harvest probes from existing assets rather than inventing: `backend/app/evals/out_of_catalog_ot_probe.py`, `backend/app/evals/out_of_set_eval.py`, `scripts/run_power_industry_probe_v3.py`, `scripts/eval_out_of_catalog_ot_probe.py`, `scripts/run_live_efficacy_100.py` (the 75-probe wide sweep and 100-turn live-efficacy baselines came from these). Per-probe expected properties: route, answer shape, evidence classes used (`rag | mcp_discovery | mcp_search | cve | mitre | none`), 0–3 usefulness rubric (0=wrong/harmful, 1=generic boilerplate, 2=specific and correct, 3=specific + evidence-grounded + actionable). Add runner `backend/app/evals/run_out_of_catalogue_scorecard.py` (follow the structure of `out_of_set_eval.py`) emitting one JSONL row per probe: probe_id, match_path, resource_plan steps + statuses, LLM calls (role, latency, output-used-vs-dropped verdict), evidence classes present in final answer, answer text. Runner must run offline (no LLM, mock MCP) via in-process pipeline calls — see `conftest.py` live-LLM guard (`AI_SOC_TESTS_ALLOW_LIVE_LLM` opt-in; default blocked).
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_out_of_catalogue_scorecard.py -q` (NEW test, 3 pinned probes, offline mode) passes; `cd backend && PYTHONPATH=../backend:.. python3 app/evals/run_out_of_catalogue_scorecard.py --offline --jsonl /tmp/out_of_catalogue_scorecard.jsonl` produces one JSONL row per probe.
  - **Depends on:** none
  - **Evidence:** `pytest app/tests/test_out_of_catalogue_scorecard.py -q` → 5 passed; runner → 55 JSONL rows; bank harvests 55 probes (6 OT + 24 OOS + 10 pk + 11 eff) with 15 hand-score IDs; files: `out_of_catalogue_probes.json`, `run_out_of_catalogue_scorecard.py`, `test_out_of_catalogue_scorecard.py`.

- [x] **0.2** — Record baseline scorecard
  - **Do:** Run scorecard on live dev stack (LLM on, MCP mock) and offline; commit JSONL under `docs/evals/out_of_catalogue_baseline_2026-07-02/` with summary: evidence-class usage % (expected ≈0% MCP today), CVE/MITRE skill usage %, LLM-output utilization rate (parsed-and-used vs dropped), p50/p95 latency, usefulness on 15-probe hand-scored sample. Record `vmstat 1 5` steal% alongside latency (VPS CPU-steal noise is a known confounder).
  - **Verify:** Baseline files in git; summary table states the four numbers this plan must move (MCP evidence %, CVE/MITRE usage %, LLM-output utilization %, usefulness).
  - **Depends on:** 0.1
  - **Evidence:** `docs/evals/out_of_catalogue_baseline_2026-07-02/` committed (offline+live JSONL, summaries, README). Offline: MCP 0%, CVE/MITRE 0%, LLM util 14.67%, usefulness target 2.0 (15 probes), p50/p95 40/81 ms, steal avg 0.6%. Live in-process `--live` profile captured (docker stack not up on host; same probe bank).

- [x] **0.3** — In-catalogue contract-level regression guard (replaces rev-1 byte identity)
  - **Do:** MCP eligibility on all tiers intentionally changes in-catalogue envelopes, so byte identity is the wrong guard. Pin instead: per-question answer-contract invariants for the 105/50 set in offline mode — route, answer shape, severity, MITRE status, `execution_eligible=false`, required sections present, no fact regressions. New `backend/app/tests/test_in_catalogue_contract_guard.py` generated from a captured run (fixtures from live capture, not hand-rolled — capture script writes to `backend/app/tests/fixtures/in_catalogue_contract/`). The 105-question bank lives in the coverage/question-runtime registries (`backend/app/coverage/question_runtime_map.py`); reuse the same iteration the 105-Q eval uses (`backend/app/evals/stage3l_105_shadow_eval.py` shows the pattern).
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_in_catalogue_contract_guard.py -q` passes on current master; deliberately corrupting one fixture fact fails it.
  - **Depends on:** 0.1
  - **Evidence:** `pytest app/tests/test_in_catalogue_contract_guard.py -q` → 15 passed; `scripts/capture_in_catalogue_contract_fixtures.py --freeze` → 155 rows in `fixtures/in_catalogue_contract/baseline.json`; corrupt-route test fails as expected.

- [x] **0.4** — Flag inventory + rightsizing proposal (doc only)
  - **Do:** Audit all ~199 `.env.example` keys + ~166 config settings in `backend/app/config.py`, plus profile files `env/profiles/*.env.example` and `env/profiles/manifest.json`. Classify each flag with **evidence recorded per flag** (grep hits, git history of introduction, runtime read sites): (a) safety-invariant → hardcode behavior, then delete flag; (b) posture → keep, group under few master toggles; (c) operator/infra (URLs, credentials, budgets, timeouts) → keep as-is; (d) dead/duplicate/stage-scaffold → delete; (e) experiment flags whose feature is now permanent-on in the single SOC posture → fold in. Output `docs/architecture/flag_rightsizing_audit.md` with per-flag disposition table (flag, current default, live value, read sites, classification, evidence, risk note) and target end-state (goal: <60 keys in profiles). **Doubt rule:** any flag whose read sites or interactions are not fully understood is classified "keep — unresolved" and excluded from deletion batches.
  - **Verify:** Doc committed; every current flag appears exactly once in the disposition table; each `delete`/`fold-in` row carries grep + git evidence; **DG-4** — user approves batch list before 7.1.
  - **Depends on:** 0.1
  - **Evidence:** `docs/architecture/flag_rightsizing_audit.md` + `flag_rightsizing_audit_data.json` (260 rows, all 203 `.env.example` keys covered); `scripts/audit_flag_inventory.py`; `pytest app/tests/test_flag_rightsizing_audit.py -q` → 5 passed. DG-4 batches proposed: A=6, B=3, C=36, D=7 — **awaiting user approval before Phase 7.1**.

### Phase 1 — LLM-primary planner live (out of shadow) + output pre-processor + budgets

- [x] **1.1** — Intelligent LLM output pre-processor (shared layer)
  - **Do:** Build `backend/app/llm/adapter/output_preprocessor.py` on top of existing `backend/app/llm/adapter/json_extractor.py` (`extract_first_json_object`). Public API: `preprocess_llm_output(raw: str, schema: dict, *, allow_retry: bool, retry_fn: Callable | None) -> PreprocessResult` where `PreprocessResult` carries `payload | None`, `verdict` (`used | repaired_used | retried_used | dropped:<reason>`), and `repairs: list[str]`. Pipeline of tolerant steps: strip code fences/prose wrappers → JSON extraction → schema-aware repair (trailing commas, case-normalized enums, coercible scalar types only; **never repair or synthesize SPL/raw query strings**) → optional single retry that feeds the validation error back to the model. Route consumers through it: `llm_plan_bridge`, `llm_plan_compiler`, `guided_investigation_plan_llm`, synthesis/action-proposal parsers. **Exemption (do not break the q046 fix):** `llm_intent_advisor` keeps its 2s hard bound and no-failover contract — it may use fence-strip + extraction + repair, but `allow_retry=False` always. Inventory remaining direct `extract_first_json_object` callers; migrate or list explicit legacy exemptions in the test docstring. Per-call utilization verdict flows to telemetry (consumed by 0.1 scorecard field `llm_output_utilization`). Known failure modes from live findings: ```json fences, echo-of-input, truncation.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_output_preprocessor.py -q` (NEW) green on a fixture corpus captured from real 8B outputs in `backend/app/tests/fixtures/llm_outputs/` (fenced, truncated, echoed, valid); wiring test shows plan bridge + compiler route through it; intent-advisor exemption test proves `allow_retry=False` and unchanged 2s bound; scorecard field `llm_output_utilization` populated.
  - **Depends on:** 0.2
  - **Evidence:** `pytest app/tests/test_output_preprocessor.py -q` → 8 passed; wired `llm_plan_bridge`, `llm_plan_compiler`, `guided_investigation_plan_llm`, `llm_intent_advisor` (allow_retry=False), `role_results`; bridge provenance `llm_output_utilization`; legacy exemptions in test module docstring; fixtures `tests/fixtures/llm_outputs/preprocessor_corpus.json`.

- [x] **1.2** — Plan-proposal validation for live promotion
  - **Do:** In `backend/app/planner/llm_plan_bridge.py`: promotion preconditions — proposed steps may add only purposes allowed by the selected skill/resource contract on dispatchable resources (`availability in {"available", "fixture_only"}` now; after registry v2 lands, also require the 4.1 onboarding status); may order phases; may request `mcp_execution` (Phase 2 gates decide executability); may never remove policy checks, never mark anything executable, never carry SPL/raw query text (`_FORBIDDEN_ARG_KEYS` already enforces this — keep). Emit `provenance.llm_bridge="promoted" | "rejected:<reason>"`. Widen `_ALLOWED_PURPOSES` for `cve_lookup` and `action_proposal` only after their registry rows/contracts exist (4.3 / 6.1); until then those proposed steps are rejected as `unknown_resource_id` / `unknown_purpose`.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_llm_plan_bridge_promotion.py -q` (NEW): invented resource id → step dropped; blocked/not-implemented resource → step dropped; SPL text in args → step dropped; empty/garbage proposal → deterministic plan unchanged; valid multi-tool proposal → promoted.
  - **Depends on:** 1.1
  - **Evidence:** `validate_llm_plan_proposal()` + `PlanPromotionResult`; dispatchability gate (`available`/`fixture_only`); `llm_bridge` provenance `promoted`/`rejected:*`; deferred `cve_lookup`/`action_proposal`; purpose↔resource contract checks. `pytest app/tests/test_llm_plan_bridge_promotion.py -q` → 8 passed; `test_llm_plan_bridge.py` → 10 passed (18 total).

- [x] **1.5** — Budget rightsizing for dev and target throughput *(runs before 1.3 by design)*
  - **Do:** Budgets are config, not architecture: raise VPS dev profile (`env/profiles/development.env.example` + live profile) — `AI_SOC_LLM_TURN_DEADLINE_SECONDS`, `AI_SOC_GUIDED_LLM_MAX_CALLS` 1→3, `AI_SOC_LLM_INTENT_ADVISOR_RESERVE_SECONDS`, `AI_SOC_LLM_MAX_OUTPUT_TOKENS` — sized to allow planner + producer + synthesis hops per turn on ~6 tok/s. Add a documented production-profile block sized for ~6000 tok/s (sub-second hops, generous call counts) in `env/profiles/production.env.example`. Record the per-hop budget model (who gets how many seconds, reserve rules, what is skipped first under pressure) in `docs/architecture/llm_budget_model.md`. Note: backend must be restarted after profile edits for settings to load.
  - **Verify:** Live dev turn with planner+synthesis completes within raised deadline (measure 5 probes, record p95 + `vmstat` steal); pytest suite stays LLM-free (conftest guard untouched); doc committed.
  - **Depends on:** 0.2
  - **Evidence:** Dev/COE profiles: `TURN_DEADLINE=210`, `GUIDED_LLM_MAX_CALLS=3`, `INTENT_ADVISOR_RESERVE=25`, `MAX_OUTPUT_TOKENS=512`, `LLM_TIMEOUT=120`. Production scaffold LLM block added. `docs/architecture/llm_budget_model.md` + `_MAX_TURN_DEADLINE=300` in `hybrid_role_graph.py`. `pytest app/tests/test_llm_budget_profile.py -q` → 4 passed; conftest `block_live_llm_network` unchanged. `vmstat 1 5` steal avg **1.0%** max **2.0%** at capture. Live 5-probe p95 pending operator `docker compose restart backend` after merging profile (stack up 10h on prior env).

- [ ] **1.3** — LLM-primary planning on all control-plane paths, deterministic fallback
  - **Do:** In `backend/app/chat/pipeline.py` evidence-planning stage (search for `deferred_not_inline`, currently set in `evidence_planner.py:~738`, consumed near `pipeline.py:3524`): replace shadow behavior with an inline bridge call as the **primary** plan proposal for every control-plane path. Deterministic composition remains the mandatory floor: exact-105/use-case paths must retain required template/RAG/MITRE/HIL policy steps; a promoted plan is applied as floor + validated additions/reordering, never floor removal. **Budget skip rule (explicit, deterministic):** skip the planner hop and use the deterministic plan when `TurnLlmBudget` remaining < (bridge cap 20s + final-synthesis reserve), recording `provenance.llm_bridge="skipped:budget"`. Timeout/rejection falls back to today's deterministic plan. Do **not** delete `backend/app/planner/resource_plan_shadow.py` until all consumers are migrated (`pipeline.py:3524` call site, EC/demo capture builders, `test_resource_plan_shadow.py`, docs); keep a compatibility shim if any surface still reads `control_plane_trace.resource_plan_shadow`.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_pipeline_dispatch* app/tests/test_control_plane_trace.py app/tests/test_resource_plan_shadow.py -q` green; NEW tests in `app/tests/test_llm_primary_planning.py`: out-of-registry query with fake client → dispatch order follows promoted plan; exact-105 query with fake client proposing floor removal → floor retained, proposal partially rejected; LLM unavailable/timeout → today's deterministic behavior; exhausted budget → `skipped:budget` provenance; 0.3 guard green.
  - **Depends on:** 1.2, 1.5, 0.3
  - **Evidence:** _(fill when done)_

- [ ] **1.4** — Planner-informed shape adjudication
  - **Do:** Keep `backend/app/chat/answer_shape_router.py` regex as deterministic floor; promoted plan's validated purpose set adjudicates shape emphasis via a deterministic mapping table (e.g. `{mcp_discovery, spl_artifact} → hunt`, `{knowledge_retrieval only} → regulatory_knowledge/ti_advisory per regex`); regex wins on high-confidence match (existing `_SHAPE_PRECEDENCE` order stays authoritative on conflict).
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_answer_shape_router.py -q` green incl. NEW adjudication cases; scorecard shows shape corrections only on probes hand-marked mis-shaped.
  - **Depends on:** 1.3
  - **Evidence:** _(fill when done)_

### Phase 2 — MCP evidence lane for all tiers, hardened SPL vigilance

- [ ] **2.1** — Evidence-plan grants: MCP available on every path
  - **Do:** In `backend/app/chat/evidence_planner.py` (the out-of-registry / guided branches around lines 238–330 currently hard-set `needs_mcp=False, mcp_allowed=False`): under control plane, make read-only discovery eligibility (`discovery_allowed=True`) available to every SOC family where the connector has a dispatchable read-only resource; set `mcp_allowed=True` only when a validator-approved SPL artifact exists (governed template family or plan-plus-compiler output with all slots resolved) — for in-catalogue AND out-of-catalogue. Reason strings must distinguish tiers: `discovery_only`, `mock_fixture_search`, `validated_search`. `freeform_spl_execution_allowed` stays False everywhere. Per-call analyst confirmation (`ai_soc_require_spl_execution_confirmation`) and global/per-server execution flags remain required.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_evidence_planner*.py app/tests/test_mcp_execution_gate*.py app/tests/test_mcp_allowed_normalization.py -q` green; NEW tests in `app/tests/test_evidence_planner_all_tier_grants.py`: unknown query without resolvable SPL → discovery only; resolved template with execution flags off → `mcp_allowed=True` in plan but execution gate blocks; resolved template with mock flags + HIL approval → mock search path allowed.
  - **Depends on:** 1.3
  - **Evidence:** _(fill when done)_

- [ ] **2.2** — Evidence loop reachable for all tiers
  - **Do:** Confirm `_mcp_evidence_loop_enabled` (`backend/app/chat/pipeline.py:~1410`) admits granted turns; extend `mcp_tool_playbook.json` chronology for hunt/source_health/baselining shapes (discovery hops — `splunk_get_indexes`, `splunk_get_index_info`, sourcetype sampling — before any gated search); `MAX_MCP_HOPS=6` in `backend/app/chat/evidence_loop.py` unchanged.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_evidence_loop*.py app/tests/test_mcp_loop_source_evidence.py -q` green; integration: out-of-catalogue hunt probe in mock mode runs >=1 discovery hop + 1 HIL-confirmed mock search; envelope carries `evidence_source: mock` rows.
  - **Depends on:** 2.1
  - **Evidence:** _(fill when done)_

- [ ] **2.3** — T2 SPL producer feeds the lane
  - **Do:** `backend/app/spl/llm_plan_compiler.py` output that passes adapter, SPL validator, relevance/quality gates, and slot resolution (`graph_node_spl_source_resolve`: `AI_SOC_SOURCE_PROFILE_MAP` → RAG → session pins) may produce an approved `normalized_spl` artifact for 2.1. The candidate envelope itself remains `execution_eligible=false` / review-only; only the separate validator-approved normalized artifact can enter the MCP gate. Unresolved slots → existing HIL clarification (never lab-draft fallback for analytics clarification — that degrade is deliberate).
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_llm_plan_compiler*.py app/tests/test_spl_source_resolve*.py app/tests/test_t2_governed_producer.py -q` green; scorecard probe with compilable detection ask reaches confirmation HIL with approved normalized SPL.
  - **Depends on:** 2.1
  - **Evidence:** _(fill when done)_

- [ ] **2.4** — Harmful-SPL vigilance tier for LLM-produced SPL
  - **Do:** New module `backend/app/spl/llm_lineage_vigilance.py`, invoked before the execution gate for any SPL whose lineage includes an LLM producer: (a) allowlist bind must be explicit index+sourcetype (no wildcards); (b) mandatory time bounds + result cap injection if absent (`SPL_DEFAULT_EARLIEST/LATEST`, `SPL_MAX_RESULT_LIMIT`); (c) risk lint blocking data-exfil/state-change constructs (`outputlookup`, `collect`, `sendemail`, `delete`, `script`, `rest`, `map`, subsearch depth) — audit current `SPL_BLOCKED_COMMANDS` coverage first, extend where missing; (d) prompt-injection defense on producing prompt context (existing `safeguards/` filter) + refuse compile when user text contains SPL-fragment injection patterns; (e) immutable audit record (producer lineage, checks passed/failed) into trace spine. Always per-call HIL. **Implementation gotcha:** `validate_spl` splits on `|` — regex alternation inside `match()`/`regex` clauses reads as pipe-commands and gets rejected; vigilance lint must tokenize the same way the validator does, and adversarial fixtures must include that class.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_spl_validator*.py app/tests/test_harmful_spl_vigilance.py -q` (NEW) green with adversarial fixture set in `backend/app/tests/fixtures/spl_adversarial/` (exfil attempts, wildcard index, injection-in-question, pipe-in-regex evasion).
  - **Depends on:** 2.3
  - **Evidence:** _(fill when done)_

### Phase 3 — Multi-call orchestration wired (O5c)

- [ ] **3.1** — Scheduler/reconcile into the evidence-loop hub
  - **Do:** `backend/app/chat/evidence_loop.py` hub consults `backend/app/planner/orchestration_scheduler.py` `schedule`/`reconcile` when the turn carries a selected recipe (from `backend/app/planner/recipe_registry.py`); every scheduled **search** call flows through the execution-stage node and gates, read-only **discovery** flows through `graph_node_mcp_call` (`pipeline.py:1321`). Budget = min(`MAX_MCP_HOPS`, recipe budget); never raised at runtime. Hard failures (`failed/timeout/denied/blocked/schema_mismatch`) fail closed — no further scheduling, stop for review. Gate via `control_plane_enabled` + evidence-plan grants — **no new flag** (do not introduce `MCP_MULTI_CALL_ORCHESTRATION_ENABLED`).
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_orchestration_scheduler*.py app/tests/test_evidence_loop*.py -q` green; NEW fixture test: two-call recipe (search → `previous_empty` → broaden) executes call 1, stops at HIL for call 2; hard-failure fixture stops scheduling.
  - **Depends on:** 2.2
  - **Evidence:** _(fill when done)_

- [ ] **3.2** — Recipe selection from the promoted plan
  - **Do:** Deterministic selector (new function in `recipe_registry.py`): promoted plan purposes + answer shape → at most one governed recipe; add `hunt_baseline` recipe (discovery → bounded search → on-empty broaden edge to HIL) alongside the two shipped recipes. LLM never names recipes; selector maps validated plan data → registry id.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_recipe_registry*.py -q` green: no mcp purposes → none; hunt shape + grant → `hunt_baseline`; unknown shape → none.
  - **Depends on:** 3.1
  - **Evidence:** _(fill when done)_

- [ ] **3.3** — Multi-call lineage + trace
  - **Do:** `control_plane_trace.mcp_calls[]` per-call records (call_id, class, outcome, evidence keys resolved, block reason) + loop verdicts, redacted per existing rules. **Declare every new state key in the pipeline-state TypedDict** — LangGraph silently drops undeclared channels; verify on the live langgraph path (`backend/app/graph/chat_workflow.py`), not just in-process.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_control_plane_trace.py app/tests/test_evidence_loop_graph.py -q` green; `/debug` API shows populated `mcp_calls[]` on a 2-call mock turn via the langgraph path.
  - **Depends on:** 3.1
  - **Evidence:** _(fill when done)_

### Phase 4 — Registry extensibility + CVE/MITRE skill utilization (4.1/4.2 parallel after 0.3; 4.3 joins after 1.3)

- [ ] **4.1** — Registry schema v2 + onboarding contract
  - **Do:** `backend/app/planner/resource_registry.py` + `resource_registry_v1.json` → v2. Current kinds (verified 2026-07-02): `api`(3), `llm_role`(8), `mcp_tool`(20), `rag_corpus`(1), `skill`(19), `spl_lab_draft_family`(27), `spl_template_family`(4). Migration: keep all existing rows loadable (accept `api` as legacy alias of `http_api` or migrate in place); add kind `action_tool`; add fields `auth_contract` (env-var **names** only, never values), `read_only: bool`, `onboarding_status` lifecycle (`declared → contract_verified → fixture_tested → live_smoked`). **Dispatchability matrix (mock path must keep working):** mock/fixture dispatch requires `availability=fixture_only` + `onboarding_status ≥ fixture_tested`; live dispatch requires `availability=available` + `onboarding_status=live_smoked`; `declared`/`not_implemented` never dispatch anywhere. Write `docs/architecture/resource_onboarding.md` (how to add a new MCP server / HTTP API / action tool: registry row → policy-tier review → fixture tests → operator env → live smoke). Seed declared-only `http_api:cisco_api_placeholder` (real Cisco API name when user provides it; non-blocking).
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_resource_registry*.py -q` green with v2 schema validation and a backwards-compat fixture asserting every current v1 row still loads and keeps its dispatch behavior; declared-only resources never compose into dispatchable steps.
  - **Depends on:** 0.3
  - **Evidence:** _(fill when done)_

- [ ] **4.2** — Composer/executor bind by capability generically
  - **Do:** In `backend/app/planner/composer.py` / `executor.py`: replace Splunk-specific composition branches with capability + policy-tier binding from the registry. Resources below their tier's dispatch threshold (per the 4.1 matrix) compose as honest `not_onboarded` steps (visible in plan, never dispatched) — **mock-mode dispatch of `fixture_tested` resources must keep working**.
  - **Verify:** Parity test: current registry composes byte-identical plans to master (`cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_composer*.py app/tests/test_executor*.py app/tests/test_planner_composer_parity.py -q`); new-kind veto test green; mock-dispatch regression test green.
  - **Depends on:** 4.1
  - **Evidence:** _(fill when done)_

- [ ] **4.3** — CVE + MITRE skills as planner-selectable resources
  - **Do:** Add `skill:cve_lookup` (snapshot read model: `backend/app/cve/snapshot_store.py` + `evidence_adapter.py`; env `AI_SOC_CVE_SNAPSHOT_DIR`) and reuse/extend the **existing** `skill:mitre_mapping` registry row (`backend/app/threat/mitre_candidate_mapper.py` + `mitre_decision.py`) as planner-selectable resources with purposes the planner may propose (`cve_lookup`, `mitre_mapping`); planner system-prompt catalog includes them with when-to-use guidance; composer emits their steps; executor dispatches to existing skill nodes. MITRE evidence preconditions (`mitre_evidence_preconditions.py`) and visibility policy stay authoritative — planner proposes, deterministic decision still decides asserted-vs-candidate.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_composer*.py app/tests/test_mitre*.py app/tests/test_cve*.py -q` green; scorecard CVE/MITRE usage % rises vs 0.2 baseline on probes hand-marked CVE/MITRE-relevant; MITRE status authority unchanged (contract guard 0.3 green).
  - **Depends on:** 4.2, 1.3
  - **Evidence:** _(fill when done)_

### Phase 5 — Canonical fact spine (node-to-node fact continuity + full telemetry)

- [ ] **5.1** — CanonicalFacts contract, single accumulation authority
  - **Do:** Extend RunContract (`backend/app/chat/contracts/run_contract.py`) with a sibling `CanonicalFacts` model: append-only list of typed facts — entities, timeframe, executed evidence keys + row summaries, negative evidence, CVE findings, MITRE candidates/decisions, RAG citations, plan step outcomes — each with provenance (`node`, `step_id`, `evidence_class`). Every evidence-producing node appends; downstream consumers (SPL slot binding, MITRE decision, sufficiency gate, synthesis) read from CanonicalFacts instead of ad-hoc state keys; retired ad-hoc keys become derived views or are deleted (list every retired key in the item's evidence).
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_canonical_facts.py -q` (NEW) green; migration test: for 5 representative turns, facts available to synthesis are a superset of master behavior; grep gate: no pipeline node reads the retired ad-hoc keys.
  - **Depends on:** 3.3
  - **Evidence:** _(fill when done)_

- [ ] **5.2** — State-channel integrity on the langgraph path
  - **Do:** Audit the pipeline-state TypedDict (`backend/app/chat/pipeline_state_v2.py` and the langgraph state in `backend/app/graph/chat_workflow.py`) against every `state["…"]` write in pipeline nodes; declare all missing channels (LangGraph silently drops undeclared keys — known failure). Runtime parity test: same turn through imperative and langgraph paths yields identical CanonicalFacts.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_state_channel_parity.py -q` (NEW) green on both dispatch paths; audit table committed in the test module docstring.
  - **Depends on:** 5.1
  - **Evidence:** _(fill when done)_

- [ ] **5.3** — Full per-turn telemetry persistence
  - **Do:** Trace spine (`ai_trace_runs`, see `docs/observability/debugging.md` + `backend/app/telemetry/`) stores the complete plan lifecycle per turn: proposed plan (LLM raw ref + validated form), promotion verdict, per-step dispatch outcomes, per-MCP-call records, CanonicalFacts snapshot at synthesis time, LLM call ledger (role, latency, utilization verdict). Redacted per existing rules; best-effort, never breaks chat; EC path still emits nothing.
  - **Verify:** `/debug` API returns full lifecycle for a live mock turn; `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_debug_api.py app/tests/test_telemetry_connector.py app/tests/test_redaction.py app/tests/test_trace_spine_lifecycle.py -q` green (last one NEW); redaction test proves no secrets/prompts in stored payloads.
  - **Depends on:** 5.1
  - **Evidence:** _(fill when done)_

- [ ] **5.4** — Grounding assembler consumes the spine
  - **Do:** Wire `backend/app/chat/grounding_assembler.py` (existing scaffold, currently unwired) to build answer/synthesis context from CanonicalFacts (evidence incl. honest negatives, citations, plan trace, capability gaps). When final-synthesis flags are enabled, live synthesis narrates from this package; when disabled, deterministic answer builders consume the same package. Deterministic facts remain overlay authority via existing adapter/validators.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_grounding_assembler*.py app/tests/test_final_answer_validator.py -q` green; probe with executed mock evidence quotes row-derived facts with lineage; probe with no evidence states the gap honestly (answer-guard test).
  - **Depends on:** 5.1
  - **Evidence:** _(fill when done)_

- [ ] **5.5** — Answer contract for evidence-bearing answers
  - **Do:** Extend contract floors (`backend/app/chat/guided_answer_contract.py`, `skill_contribution.py`): evidence-bearing answers render evidence summary, what-was-checked (incl. negatives), confidence bounded by evidence class, next steps; contract test enforces section presence, not wording.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_guided_answer_contract*.py app/tests/test_skill_contribution*.py -q` green.
  - **Depends on:** 5.4
  - **Evidence:** _(fill when done)_

### Phase 6 — Post-answer agentic actions (tickets first, mock ITSM — DG-3 resolved)

- [ ] **6.1** — Action lane contract + mock ITSM adapter
  - **Do:** After final answer: LLM may propose actions as data (`action_proposal` purpose) referencing `action_tool` registry entries only. Registry already has `skill:ticket_drafting` and `skill:action_planning` rows — reuse their lineage; add `action_tool:create_ticket` (kind `action_tool`, `read_only=false`, `onboarding_status=fixture_tested`, mock adapter). Deterministic validator checks: tool exists + dispatchable, args match `input_contract`, payload built solely from CanonicalFacts (never prompts/raw internals/RAG chunks). Actions are never auto-executed — each requires explicit analyst approval via an **authenticated** backend endpoint (existing FastAPI session auth; unauthenticated approval rejected 401), then a gated action executor runs the mock adapter (`backend/app/actions/itsm_adapter.py`, NEW — interface class + `MockItsmAdapter` implementation; real connector is a future plan item when user names the system). Full audit record per action (proposal, approver, timestamp, payload hash, outcome) into trace spine.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_action_lane.py -q` (NEW) green: proposal with invented tool → rejected; valid proposal → pending-approval state, no execution; unauthenticated approval → 401, nothing executed; approval → mock ticket created with CanonicalFacts-derived summary; denial → recorded, nothing executed.
  - **Depends on:** 5.1, 4.1
  - **Evidence:** _(fill when done)_

- [ ] **6.2** — UI surface for proposed actions
  - **Do:** Frontend (`frontend/src/`): proposed-actions panel under the final answer (action label, payload preview, approve/deny buttons); approve calls the authenticated backend action endpoint; result + audit ref rendered. Build via `cd frontend && npm run build` (postbuild `chmod -R a+rX dist` must remain, else Nginx 403).
  - **Verify:** `cd frontend && npm run build` passes; manual smoke on dev stack: propose → approve → mock ticket visible with audit id; deny path leaves audit record.
  - **Depends on:** 6.1
  - **Evidence:** _(fill when done)_

### Phase 7 — Flag rightsizing implementation **[DG-4 per-batch approval; maximum caution]**

- [ ] **7.1** — Staged flag dispositions, safest first
  - **Do:** Implement the 0.4-approved dispositions in **ordered risk batches, one batch per commit, full verification between batches**: Batch A dead/unread keys (grep-proven zero read sites); Batch B duplicates/aliases (consolidate, keep canonical name); Batch C permanent-on experiment flags (fold in, delete key); Batch D safety-invariant flags (hardcode behavior first, prove via test that the behavior survives with the flag absent, then delete key). **Satisfaction criteria per batch (all required before the batch starts):** disposition table row has grep + git evidence; no "keep — unresolved" items in the batch; user approved the batch list; rollback = single-commit revert documented. Config-compat shim logs (not crashes) on retired keys for one release. Never mix batches; never delete to hit the <60 target.
  - **Verify:** After each batch: `docker compose up -d` boots clean with regenerated profile; `./scripts/run_stage3_governance_regression.sh` PASS; one live `/chat` smoke turn OK. Grep proves the batch's retired keys absent from code (except compat shim).
  - **Depends on:** 0.4 (DG-4), 6.2 — runs last before close so consolidations capture the final flag set
  - **Evidence:** _(fill when done)_

- [ ] **7.2** — Regenerate profiles + migration doc
  - **Do:** Regenerate `env/profiles/*.env.example` + `.env.example` from the surviving flag set (target <60 keys, but correctness beats count); old→new migration table appended to `docs/architecture/flag_rightsizing_audit.md`; update `env/profiles/manifest.json` if key groups changed.
  - **Verify:** Fresh `cp` of regenerated profile boots the stack; key count recorded; migration table covers every retired key.
  - **Depends on:** 7.1
  - **Evidence:** _(fill when done)_

### Phase 8 — Close the loop

- [ ] **8.1** — Post-change scorecard vs baseline
  - **Do:** Re-run 0.1 scorecard (live dev, mock MCP). Comparison doc `docs/evals/out_of_catalogue_after_2026-07/`: MCP evidence usage %, CVE/MITRE usage %, LLM-output utilization %, promoted-plan rate, p50/p95 latency (+ steal%), usefulness on same 15-probe sample.
  - **Verify:** All four Phase-0.2 target numbers improved; usefulness not regressed on any probe class; latency within raised dev budget at p95. Any gate fail → drift log + stop.
  - **Depends on:** 1.4, 2.4, 3.3, 4.3, 5.5, 6.2, 7.2
  - **Evidence:** _(fill when done)_

- [ ] **8.2** — Full governance regression + docs
  - **Do:** `./scripts/run_stage3_governance_regression.sh`; `cd frontend && npm run build`; update `AGENTS.md` + `CLAUDE.md` stage-boundary bullets (LLM-primary planner, all-tier MCP eligibility, O5c, CVE/MITRE resources, canonical fact spine, action lane, flag set) and architecture docs cross-refs; update Plans table.
  - **Verify:** Regression PASS (0 pytest failures, harness 6/6); build passes; docs diffs reviewed.
  - **Depends on:** 8.1, 7.2
  - **Evidence:** _(fill when done)_

## Appendix A — Executor context (read before any item; written so a fresh agent can continue)

**Architecture spine (query → answer):** `/chat` (`backend/app/api/`) → intent (`chat/intent_classifier.py`, advisory LLM hop `chat/llm_intent_advisor.py`, 2s bound, never retry) → planning decision (`chat/planning_decision.py`) → evidence plan (`chat/evidence_planner.py`, authority for `needs_*`/`mcp_allowed`/`discovery_allowed` booleans) → resource plan composition (`planner/composer.py`, binds registry resources) → dispatch (`planner/executor.py` walking steps; node functions live in `chat/pipeline.py`, ~8200 lines) → evidence loop hub (`chat/evidence_loop.py`, deterministic routing, `MAX_MCP_HOPS=6`) → MCP gate (`evaluate_mcp_execution` inside pipeline execution node; per-call HIL) → sufficiency gate → synthesis (deterministic draft; live LLM narration only when synthesis flags on) → answer contracts (`chat/guided_answer_contract.py`, `skill_contribution.py`). Two dispatch paths exist — imperative (`chat/pipeline.py`) and LangGraph (`graph/chat_workflow.py`) — changes must work on **both**.

**Key invariant sources:** SPL validator + allowlists (`backend/app/safeguards/`, env `SPL_*`); MCP registry/readiness (`backend/app/connectors/mcp/`); LLM clients + roles (`backend/app/llm/clients/`, sidecar roles in `llm/sidecar_clients.py`); config = `backend/app/config.py` (pydantic settings; env via `.env` + `env/profiles/<AI_SOC_ENV_PROFILE>.env`).

**Operational gotchas (each has bitten before):**
- Backend must be restarted (`docker compose restart backend` or up -d) after any `.env`/profile edit; settings load at process start.
- Pytest inside the repo blocks live LLM calls via conftest autouse guard; `AI_SOC_TESTS_ALLOW_LIVE_LLM=1` opts in deliberately. Never remove the guard.
- LangGraph `StateGraph` silently drops any `state["key"]` not declared in the TypedDict — declare every new channel and verify on the langgraph path.
- `validate_spl` splits on `|`: regex alternation inside `match()` clauses parses as pipe-commands and is rejected — write base-search OR terms; new templates require regenerating `spl_template_review_sheet`.
- Frontend production is Nginx serving `frontend/dist`; `npm run build` + postbuild chmod publishes UI changes (docker frontend service is Vite dev only).
- VPS LLM: single-slot 8B, ~6 tok/s under CPU steal; measure with real generation probes + `vmstat` steal, not `/health`.
- The user works from multiple parallel chats/agents — before building, reconcile `git status` + `.env` against expectations.
- EC/demo path (`backend/app/demo/scenarios.py`) is fixture-only: never routes live LLM/MCP; never emits traces. Do not wire new behavior into it.

**Test commands:** backend suite `cd backend && PYTHONPATH=../backend:.. python3 -m pytest`; full gate `./scripts/run_stage3_governance_regression.sh`; harness `PYTHONPATH=backend:. python3 -m test_harness.harness.runner --json`.

## Appendix B — New test files this plan creates

| File (under `backend/app/tests/`) | Asserts |
|---|---|
| `test_out_of_catalogue_scorecard.py` | Scorecard runner: 3 pinned probes offline; JSONL row shape (contract, not values) |
| `test_in_catalogue_contract_guard.py` | 105/50 fact-level invariants from captured fixtures; corrupt-fixture fails |
| `test_output_preprocessor.py` | Fence/truncation/echo repair verdicts; SPL never synthesized; intent-advisor no-retry exemption |
| `test_llm_plan_bridge_promotion.py` | Invented id/blocked resource/SPL-in-args dropped; garbage → deterministic; valid → promoted |
| `test_llm_primary_planning.py` | Promoted plan drives dispatch; floor irremovable; timeout/budget-skip fallback provenance |
| `test_evidence_planner_all_tier_grants.py` | Tiered grants; plan-eligible ≠ gate-open (flags off → blocked); mock path allowed |
| `test_harmful_spl_vigilance.py` | Adversarial SPL corpus blocked (exfil, wildcard, injection, pipe-in-regex evasion) |
| `test_canonical_facts.py` | Append-only, provenance, superset-of-master migration on 5 turns |
| `test_state_channel_parity.py` | Imperative vs langgraph paths produce identical CanonicalFacts |
| `test_trace_spine_lifecycle.py` | Full plan lifecycle persisted + redacted per turn |
| `test_action_lane.py` | Proposal validation, pending state, 401 on unauth approval, mock ticket on approval, audited denial |

Existing test files cited in Verify commands were checked present on 2026-07-02: `test_resource_plan_shadow.py`, `test_mcp_allowed_normalization.py`, `test_mcp_loop_source_evidence.py`, `test_t2_governed_producer.py`, `test_evidence_loop_graph.py`, `test_planner_composer_parity.py`, `test_redaction.py`, `test_debug_api.py`, `test_telemetry_connector.py`.

## Verification gaps (flag before coding)

- Usefulness scoring (0.2 / 8.1) is hand-scored on a 15-probe sample — subjective; rubric pinned in 0.1.
- Latency numbers on VPS are noisy (hypervisor CPU steal); record `vmstat st` alongside, prefer p50 across ≥2 runs; budgets are the control, not architecture.
- 105/50 contract guard (0.3) is weaker than byte identity by design (MCP eligibility changes envelopes); fact-level pins are the accepted trade-off per user directive 1.
- Real ITSM connector out of scope (DG-3 resolved to mock); adapter interface is the deliverable.

## Drift log

- **2026-07-02 (rev 2.2):** Bug-fix + detail pass for executor handoff. Fixed: 4.1/4.2 dispatchability wording would have broken mock-mode dispatch (added explicit tier matrix: `fixture_tested`+`fixture_only` dispatches in mock; `live_smoked` required for live). Fixed: 1.1 retry loop would have violated the q046 intent-advisor bound (2s, no failover) — advisor exempted from retry. Loosened 1.5 dependency 1.2→0.2. Replaced fictional `test_trace_spine*.py` reference with real test files + one new one. DG-3 resolved: mock ITSM adapter. Phase 7 split into 7.1/7.2 with risk-ordered batches, per-batch DG-4 approval, and explicit satisfaction criteria (user: "be very cautious, start only when fully satisfied"). Added Appendix A (executor context) and Appendix B (new-test map); verified all cited existing test files, registry kinds (`api/llm_role/mcp_tool/rag_corpus/skill/spl_*`), `graph_node_mcp_call` (pipeline.py:1321), and existing `skill:mitre_mapping`/`skill:ticket_drafting` rows.
- **2026-07-02 (rev 2.1):** Review fixes tightened rev-2 scope: DG-1 means MCP eligibility/planner reachability on all tiers, while operator execution flags, validator-approved `normalized_spl`, HIL, and connector availability still gate every MCP call. Reordered budget rightsizing before inline planner promotion; made Phase 4 dependencies explicit; preserved `resource_plan_shadow.py` until consumers migrate; corrected repo paths and verification commands.
- **2026-07-02 (rev 2):** User directives superseded rev-1 gates: DG-1 → MCP eligibility for all tiers; DG-2 → budgets raised, architecture not sized to VPS throughput. Added: LLM-primary planning, output pre-processor, CVE/MITRE utilization, canonical fact spine, post-answer action lane, flag rightsizing. Rev-1 byte-identity guard replaced by contract-level guard (incompatible with MCP eligibility on all tiers).
