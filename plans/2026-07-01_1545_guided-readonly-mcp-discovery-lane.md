---
name: guided-readonly-mcp-discovery-lane
overview: "Give guided_investigation a read-only MCP discovery lane (5 metadata tools) without opening execution or SPL, behind a default-off COE flag; enrich-in-turn, promote-by-HIL."
status: draft
date: 2026-07-01
canonical_plan: plans/2026-07-01_1545_guided-readonly-mcp-discovery-lane.md
loop_runner: plans/LOOP_RUNNER_guided-readonly-mcp-discovery-lane.md
---

# Guided read-only MCP discovery lane

## Objective

`guided_investigation` (the out-of-registry rescue) currently blocks **all** of MCP with one boolean (`mcp_allowed=False`), which discards the 5 safe read-only Splunk discovery tools along with the single execution tool. This plan splits that boolean into **execution authority** (stays off) vs a **read-only discovery lane** (new, opt-in). When enabled, guided answers can plan/collect metadata context (`splunk_get_info`, `splunk_get_indexes`, `splunk_get_metadata`, `splunk_get_index_info`, `splunk_get_knowledge_objects`) to make hunt guidance concrete — while `splunk_run_query`, SPL generation, MITRE/severity claims, and route promotion all remain gated exactly as today.

"Done" = guided can drain read-only discovery hops through the existing Stage-4B loop, the hops land in the canonical `RunContract` + telemetry spine, the answer surfaces an **HIL promotion offer** (never an automatic route change), and with the flag OFF the entire live pipeline is byte-identical to today.

## Design decisions (answering the open questions)

### D1 — How MCP is used on guided
Read-only lane only. The 5 tools carry `read_only=true, blocked=false` in `mcp_tool_playbook.json`; they return instance/index/sourcetype/knowledge-object metadata and need **no SPL**. `splunk_run_query` (`read_only=false, execution_gated=true`, precondition = approved `normalized_spl`) is **not** in the lane and is structurally unreachable from a metadata read. Posture inherits the global gate: `MCP_GLOBAL_EXECUTION_ENABLED=false` (default) → hops are `planned` (analyst checklist); flags on → hops are `collected` (sanitized metadata rows into `source_evidence`). No new execution capability is created.

### D2 — Can a guided question move "up" to a governed node, or is it HIL?
**HIL. Never automatic in-turn promotion.** Rationale:
- Out-of-registry means *no governed 105/catalog contract exists* for the question — there is nothing deterministic to promote *to* mid-turn, and letting discovery output pick a governed route would violate "deterministic route selection is authority; the LLM/evidence never selects the final route."
- Instead: **in-turn = enrich only.** If `splunk_get_knowledge_objects` reveals a vetted saved search / macro / data model that plausibly covers the hunt, the answer emits an **HIL promotion offer** in the card (e.g. "governed saved search `X` may cover this — an analyst can re-run under `spl_generation`/`attack_discovery` with confirmation"). It is a suggestion recorded as an HIL decision, not a route switch.
- **Cross-turn promotion is analyst-driven:** the analyst confirms/rephrases; the follow-up turn re-enters the pipeline through session context and may then match a governed route on its own merits. The pipeline never silently escalates a turn out of guided.
- The promotion offer is metadata on the answer contract; it changes no authority field.

### D3 — Telemetry & canonical flow
- Discovery hops flow through the **existing** Stage-4B machinery: `graph_node_mcp_call` → `execute_loop_discovery_hop` → `append_mcp_loop_source_evidence` (`source_type=mcp_discovery`). No new I/O path.
- **Canonical `RunContract`:** hops respect the existing separation — `collection_status=planned` rows are **excluded** from `collected_evidence_count`; only `collected` rows increment it and feed `structured_facts`. The promotion offer records under the single `effective_hil` surface, not a second gate.
- **Trace:** the `control_plane_trace.evidence_loop` block already records hop chronology/outcome/delivered keys; the guided lane reuses it. Debug spine (`ai_trace_runs` + `mcp` events) captures hops with `duration_ms`. `llm_turn_budget` is untouched (discovery is deterministic, not an LLM hop).

### D4 — Do not change already-running paths
- Everything behind a new default-off flag `AI_SOC_GUIDED_MCP_DISCOVERY_ENABLED`.
- Only the `guided_investigation` evidence-plan family is touched; the other 8 families and all governed routes keep `mcp_allowed`/`needs_mcp` unchanged.
- Flag OFF ⇒ `discovery_allowed=False` ⇒ loop-entry gate behaves exactly as today ⇒ **byte-identical**. Governance regression must confirm 120/120·50/50·16/16 and byte-identity, same bar as Dispatch V2.
- Experience Center fixture path (`coe_synthetic_fixture`) stays isolated — no live discovery.

## Stop conditions

- All checklist items checked with recorded evidence, **or**
- Same verification gate fails twice on one item, **or**
- Decision needed (COE posture sign-off for the flag, or the promotion-offer copy) — **stop and ask**.

## Dependency order

`1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9`

## Checklist

- [ ] **1** — Add the flag (default-off), no behavior yet
  - **Do:** Add `AI_SOC_GUIDED_MCP_DISCOVERY_ENABLED=false` to `.env.example` and the settings model (`ai_soc_guided_mcp_discovery_enabled: bool = False`).
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -c "from app.config import settings; print(settings.ai_soc_guided_mcp_discovery_enabled)"` → `False`. Grep `.env.example` shows the key with a COE comment.
  - **Depends on:** none
  - **Evidence:** _(fill when done)_

- [ ] **2** — Add `discovery_allowed` to the evidence-plan contract
  - **Do:** Add `discovery_allowed: bool = False` to `EvidencePlan` in `backend/app/chat/contracts/evidence_plan.py`; default preserves current behavior for all families.
  - **Verify:** `pytest app/tests -k evidence_plan -q`; construct an `EvidencePlan()` with no args → `discovery_allowed is False`.
  - **Depends on:** none
  - **Evidence:** _(fill when done)_

- [ ] **3** — Flip only the guided family, execution still off
  - **Do:** In `backend/app/chat/evidence_planner.py` guided_investigation branch (lines ~235-277), set `discovery_allowed=settings.ai_soc_guided_mcp_discovery_enabled`; keep `mcp_allowed=False`, `needs_spl=False`, `spl_allowed=False` unchanged. No other family edited.
  - **Verify:** unit test: guided plan with flag on → `discovery_allowed True, mcp_allowed False`; flag off → both False. Other families unchanged (assert `policy_knowledge`, `spl_generation`, etc. still `discovery_allowed False`).
  - **Depends on:** 1, 2
  - **Evidence:** _(fill when done)_

- [ ] **4** — Loop-entry gate: allow discovery without allowing execution
  - **Do:** In `backend/app/chat/pipeline.py` (~1336, `_mcp_allowed_decision_from_plan` consumers), enter the Stage-4B discovery loop when `mcp_allowed OR discovery_allowed`. Keep the `execute` route gated on **execution** allowance only.
  - **Verify:** trace: guided+flag-on enters `_run_discovery_loop_imperative`; guided+flag-off does not. Assert the imperative loop is reachable with `mcp_allowed=False, discovery_allowed=True`.
  - **Depends on:** 3
  - **Evidence:** _(fill when done)_

- [ ] **5** — Assessor: guided can pick `discovery_hop`/`finalize`, never `execute`
  - **Do:** In `backend/app/chat/evidence_loop.py` assessor, restrict route to `{discovery_hop, finalize, exhausted, capability_gap}` when `discovery_allowed and not mcp_allowed`. Guard so `execute`/`run_query` is impossible on the guided lane.
  - **Verify:** `pytest app/tests -k evidence_loop -q` + new test: with `discovery_allowed=True, mcp_allowed=False`, assessor never returns `execute` even when a candidate SPL is injected; returns `finalize` after `MAX_MCP_HOPS`.
  - **Depends on:** 4
  - **Evidence:** _(fill when done)_

- [ ] **6** — Emit the honest discovery resource-decisions block for guided
  - **Do:** Wire guided's `planning_decision` to build the mcp block via `_mcp_discovery_decision_block(discovery_calls, needed=True, allowed=False, skip_reason="Read-only discovery planned; execution + run_query stay gated.")` so `planned_discovery` lists the 5 read-only tools. Reuse `plan_splunk_discovery_calls(include_knowledge_objects=True)`.
  - **Verify:** guided resource_decisions JSON contains `mcp.planned_discovery == [5 read-only tool names]`, `mcp.allowed == False`, `mcp.needed == True` (flag on); flag off → unchanged from today.
  - **Depends on:** 3
  - **Evidence:** _(fill when done)_

- [ ] **7** — Canonical/telemetry: hops land correctly, counts honest
  - **Do:** Confirm `append_mcp_loop_source_evidence` maps guided hops to `source_type=mcp_discovery`; `planned` excluded from `collected_evidence_count`, `collected` included; `control_plane_trace.evidence_loop` + debug `mcp` events populated. No new fields on `RunContract`.
  - **Verify:** flag-on planned run → `collected_evidence_count` unchanged (planned excluded), `evidence_loop.hops` present; simulate exec-on collected hop → count increments, sanitizer applied (no raw rows in narration). Assert `effective_hil` single-valued.
  - **Depends on:** 5, 6
  - **Evidence:** _(fill when done)_

- [ ] **8** — HIL promotion offer (enrich-in-turn, no auto route change)
  - **Do:** When `splunk_get_knowledge_objects` returns a vetted saved-search/macro match, attach an HIL promotion **offer** to the answer contract (metadata only): suggested governed route + "analyst confirmation required". No route field, severity, MITRE, or `execution_eligible` changes. Copy is deterministic, not LLM.
  - **Verify:** test: guided turn with a knowledge-object hit → answer contract has `promotion_offer` metadata, `final_route` still `guided_investigation`, `effective_hil` reflects the offer; no authority field mutated. Absent hit → no offer.
  - **Depends on:** 7
  - **Evidence:** _(fill when done)_

- [ ] **9** — Regression + doc sync + flag-off byte-identity
  - **Do:** Run `./scripts/run_stage3_governance_regression.sh`; update `docs/architecture/details.html` §9/§12 + §4B to describe the guided read-only lane and HIL-promotion posture (replace the current overstated planned_discovery-on-guided text with flag-gated truth); republish to `frontend/public` + `frontend/dist`.
  - **Verify:** governance PASS (harness 6/6, 120/120·50/50·16/16); flag-off diff of a guided `/chat` response vs baseline = byte-identical; doc md5 identical across the 3 copies.
  - **Depends on:** 8
  - **Evidence:** _(fill when done)_

## Verification gaps (flag before coding)

- Item 5 assumes the `evidence_loop.py` assessor takes `discovery_allowed`/`mcp_allowed` from state; confirm the exact param names at implementation and adjust Verify commands.
- Item 8 promotion-offer copy + whether it renders in the analyst card or only the trace is a **UX/COE decision** — stop and confirm wording before finalizing.

## Drift log

- 2026-07-01: Plan created. Premise: guided currently sets `mcp_allowed=False` wholesale (verified in `evidence_planner.py:235-277`) and the doc's `planned_discovery`-on-guided is an overstatement (composer builds it only for hybrid/spl_review). Promotion decided as **HIL, not auto** (D2). COE sign-off required for the flag before enabling in any non-dev env.
