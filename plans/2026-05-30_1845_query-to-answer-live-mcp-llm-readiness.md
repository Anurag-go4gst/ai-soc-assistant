# Plan — Query→Answer Readiness for Live MCP + LLM

**Status:** In Progress (Phase A done; Phase C partially landed; SPL audit H done; Phase B blocked on COE)  
**Date:** 2026-05-30 (audited 2026-06-13)  
**Author:** COE review (Anurag + Claude)  
**Related:** [`2026-06-13_mcp-execution-orchestration-plan.md`](2026-06-13_mcp-execution-orchestration-plan.md), [`contracts/splunk_mcp_connection_contract.md`](../contracts/splunk_mcp_connection_contract.md), [`/root/.cursor/plans/llm_optimization_strategy_3a311ebc.plan.md`](/root/.cursor/plans/llm_optimization_strategy_3a311ebc.plan.md), [`/root/.cursor/plans/llm_lab-tier_spl_exposure_0c7c3c33.plan.md`](/root/.cursor/plans/llm_lab-tier_spl_exposure_0c7c3c33.plan.md) (Phase G/H — SPL lab exposure + placeholder resolution)

---

## Audit summary (2026-06-13)

Honest read against current `master` — several plan claims were **stale** when written; some work landed under WS-PRE / Stage 3M / P6 without updating this doc.

| Claim in original plan | Actual state | Verdict |
|------------------------|--------------|---------|
| `routes_chat.py:114` hard-disables synthesis | Live path is `build_live_chat_response()` → `app/chat/pipeline.py`; synthesis runs via `run_governed_synthesis_lab()` when flagged | **Outdated** |
| "No answer sentence is ever composed" | Deterministic analyst draft always built when `AI_SOC_LLM_FINAL_SYNTHESIS_ENABLED=true`; optional live narration when `AI_SOC_LLM_LIVE_SYNTHESIS_ENABLED=true` | **Outdated** (default flags still off) |
| Phase A1 empty-result bug | Rule 3b in `context_sufficiency.py`; `test_negative_result_sufficiency.py` (T4.1) green | **Done** |
| Phase A2 injection defense | `splunk_result_adapter.sanitize_result_envelope` + `mcp_result_safeguard.scan_mcp_preview_rows` → `prompt_injection_filter`; `test_mcp_result_injection_defense.py` (T4.2) green | **Done** |
| Phase A3 lineage placeholders | `lineage/builder.py` has `llm_raw_output_placeholder`, `adapter_overrides_placeholder`, `guard_overrides_placeholder` | **Done** (placeholders only; not populated on live narration yet) |
| Phase C scaffold "never called" | `build_governed_synthesis_package` + `run_answer_guard_lab` wired in `pipeline.py` | **Done** behind flags |
| `mcp_execution_gate.py:164` blocks real mode | Real block is `_gate_review` at **`:239`** (`registry.mode != "mock"`); `NotImplementedError` catch at **`:118`** if gate is bypassed | **Stale line refs** |
| Gate passes only `{"query": normalized_spl}` | Still true at `mcp_execution_gate.py:115`; `build_splunk_search_inputs()` exists in `splunk_mcp_readiness.py` but is **not** used by the gate yet | **Open — B2** |
| Phase D route shadow | `_route_plan_shadow_candidate()` in `pipeline.py` still returns `None`; inject via test monkeypatch or `generate_llm_route_plan_candidate` | **Still valid** |

### Missed cases (add to scope)

1. **`CONTROL_PLANE_ENABLED` vs live narration.** `lab_runner.py` skips live model narration when `control_plane_enabled` is true — even if both synthesis flags are on. `.env.example` defaults `CONTROL_PLANE_ENABLED=true`. COE must define which composer owns narration before enabling live LLM in production posture.
2. **LangGraph path.** `routes_chat.py` can delegate to `run_chat_via_langgraph()` when `langgraph_orchestration_enabled`; parity and synthesis wiring must be verified on both paths.
3. **Two answer validators.** `run_answer_guard_lab` (flag-gated, runs on synthesis draft) vs `final_answer_validator` (deterministic contract validator on composed card). Plan C3 must not conflate them.
4. **Mock execution HIL.** Successful mock runs can still require analyst review (`ai_soc_require_hil_for_mock_execution`); empty-result and synthesis readiness do not bypass HIL.
5. **Hybrid / partial MCP evidence.** Empty search is handled (A1); **timeout**, **failed job**, and **envelope schema mismatch** need explicit sufficiency modes — see MCP orchestration plan §interpretation.
6. **Contract vs code tool names.** Contract draft uses `splunk.search` / `search_splunk`; gate and registry use `splunk_run_query` alias — B2 must map aliases before COE sign-off.
7. **Lineage population on live narration.** Placeholders exist but `llm_raw_output_placeholder` stays `None` when narration runs; audit reproducibility gap for Phase C production enablement.

---

## Context

COE review of the live `/chat` pipeline (not the Experience Center / demo early-return path). Goal: make the system produce a **grounded final answer** when MCP (Splunk) and the LLM go live — safely, auditable, reviewable.

Today the pipeline is **evidence-rich; answer completeness depends on flags**:

- `routes_chat.py` → `build_live_chat_response()` in `app/chat/pipeline.py` routes → plans → generates+validates candidate SPL → `evaluate_mcp_execution` → `_context_stage` (RAG → SourceEvidence → StructuredContext → sufficiency) → severity/MITRE/lineage → **governed synthesis lab** → answer guard → response.
- `mcp_execution_gate.py` **already calls** `get_mcp_connector().call_tool()` in mock mode. Real execution is blocked at `_gate_review` when `registry.mode != "mock"` (`:239`) and by `NotImplementedError` in the connector (`:118`).
- **Synthesis defaults off** (`AI_SOC_LLM_FINAL_SYNTHESIS_ENABLED=false`). When enabled, a deterministic draft is composed; live narration is a second flag (`AI_SOC_LLM_LIVE_SYNTHESIS_ENABLED`) and is **suppressed when `CONTROL_PLANE_ENABLED=true`**.

Remaining walls for production query→answer:

| Wall | Blocker | Status |
|------|---------|--------|
| **1 — Real MCP** | COE contract + real `call_tool` + gate arg mapping | Blocked |
| **2 — Production synthesis** | COE sign-off on flags, narration path vs control plane, lineage population | Partially implemented |
| **3 — Security / audit** | A1/A2 done; lineage fill + multi-path parity pending | Mostly done |

This crosses the CLAUDE.md stage boundary for live synthesis — each enabling phase stays behind explicit flags and needs sign-off before production merge.

---

## Phase completion tracker

| Phase | Item | Status | Evidence |
|-------|------|--------|----------|
| **A** | A1 empty-result correctness | ✅ Done | `context_sufficiency.py` Rule 3b; `test_negative_result_sufficiency.py` |
| **A** | A2 results→evidence injection defense | ✅ Done | `splunk_result_adapter.py`, `mcp_result_safeguard.py`; `test_mcp_result_injection_defense.py` |
| **A** | A3 audit lineage hooks | ✅ Placeholders | `lineage/builder.py` synthesis/answer_guard stages |
| **B** | B1 COE connection contract | 🟡 Draft | `contracts/splunk_mcp_connection_contract.md` (`schema_confirmed=false`) |
| **B** | B2 real `call_tool` + arg schema | ❌ Open | Gate still sends `{"query": normalized_spl}` only |
| **B** | B2b SPL source resolution (config + RAG + optional discovery exec) | 🟡 Scaffold done | `graph_node_spl_source_resolve`, `source_profile_resolver.py`, `rag_source_profile_bridge.py` (`8f44eee`); H2 MCP discovery exec still COE-gated |
| **B** | B3 cost + allowlist safety | 🟡 Partial | `spl_validator.py` + `build_splunk_search_inputs()` exist; not wired to gate |
| **B** | B4 per-run approval workflow | 🟡 Partial | `_gate_review` + HIL reasons exist; COE SLA/UI TBD |
| **C** | C1 wire synthesis scaffold | ✅ Done | `pipeline.py` → `run_governed_synthesis_lab` |
| **C** | C2 synthesis stage + narration | 🟡 Flag-gated | `lab_runner.py`, `live_narration.py`; CP blocks live narration |
| **C** | C3 answer guard | 🟡 Flag-gated | `answer_guard/runner.py` wired; default off |
| **C** | C4 kill switches | ✅ Done | Flags + `AI_SOC_LLM_MODE=disabled` + air-gap |
| **D** | Route-plan shadow exercise | 🟡 Testable | Default hook returns `None`; tests inject candidates |

---

## Phases (ordered by dependency + risk)

### Phase A — Pre-live hardening ✅ (complete; maintain regression)

**A1. Empty-result correctness** — **DONE**

Executed-but-empty MCP results → `full_answer`/`partial_answer` with `execution_negative_result`, never `insufficient_evidence`. Verified: `build_source_evidence` sets `collection_status=collected`, `result_count=0`, `execution_outcome=negative_result`.

**A2. Results→evidence injection defense** — **DONE**

Defense at adapter boundary: `data_minimizer` + `scan_mcp_preview_rows` (wraps `prompt_injection_filter`). Sensitivity flags → sufficiency Rule 1 → `blocked_by_policy`.

**A3. Audit lineage hooks** — **PLACEHOLDERS ONLY**

Populate `llm_raw_output_placeholder` / `adapter_overrides_placeholder` when live narration or guarded adapter runs (follow-up under Phase C production enablement).

---

### Phase B — Real MCP adapter (Wall 1) ❌ COE-gated

**B1. COE connection contract (gate; blocks B2).**

Draft exists: `contracts/splunk_mcp_connection_contract.md`. COE must confirm: server URL, transport, auth, discovered tool names, **exact arg schema** (`search_query`, `earliest_time`, `latest_time`, `max_results`), approval workflow. Set `schema_confirmed=true` after S5 sign-off.

**B2. Implement real `call_tool`.**

- Replace `{"query": normalized_spl}` in `mcp_execution_gate.py` with `build_splunk_search_inputs()` from `splunk_mcp_readiness.py` mapped to COE schema.
- Implement real transport in `app/connectors/mcp/splunk_mcp.py`; flip `_gate_review` `:239` branch once adapter + envelope validation pass.
- Reuse `live_schema_capture.py` + `discovery.py` for tool discovery.
- Align tool name aliases (`splunk_run_query` ↔ `search_splunk` ↔ contract `splunk.search`).

**B3. Cost + allowlist safety.**

Enforce bounded `earliest/latest` + `SPL_MAX_RESULT_LIMIT` at validation **before** execution. Align `SPL_ALLOWED_INDEXES` / `SPL_ALLOWED_SOURCETYPES` with live Splunk deployment.

**B4. Per-run approval workflow.**

`_gate_review` already requires `soc_lead` approval when execution flags are off. Define COE SLA + frontend HIL surface so live queries do not stall. Coordinate with [`2026-06-13_mcp-execution-orchestration-plan.md`](2026-06-13_mcp-execution-orchestration-plan.md) Phase B execution semantics.

**Missed: discovery vs search.** Orchestration plan separates Step 5 discovery planning (7 tools, never auto-run) from Step 7 `splunk_run_query` execution. B2 covers search only; extend Resource Planner for hybrid/guided paths per orchestration plan.

**B2b. SPL source resolution (cross-plan — does not replace B2).**

Prerequisite for LLM-generated SPL to reach `normalized_spl` and enter the search gate. Documented in [`llm_lab-tier_spl_exposure` plan](/root/.cursor/plans/llm_lab-tier_spl_exposure_0c7c3c33.plan.md) Phase H; **extends** this plan, does not contradict it.

| Step | Source | Pipeline node | Executes? |
|------|--------|---------------|-----------|
| G | Lab-tier LLM SPL exposure (placeholders visible) | ✅ Done | `validate_spl_lab_candidate`, pipeline exposure split (`8f44eee`) |
| H0 | Config / skills / `SPL_ALLOWED_*` env map | ✅ Done | `source_profile_resolver.py`, `AI_SOC_SOURCE_PROFILE_MAP` |
| H1 | **RAG / playbook** — KB `splunk_indexes`, `sourcetypes`, `fields` | ✅ Done | `rag_source_profile_bridge.py` |
| H2 | MCP discovery **execution** (`splunk_get_indexes`, `splunk_get_metadata`) | 🟡 Scaffold | `try_mcp_source_discovery()` — mock-only until COE + orchestration §6 |
| H3 | HIL `spl_source_profile_clarification` | ✅ Done | `build_spl_source_profile_review`, session `source_profile_slots` |
| H4 | `validate_spl` → `normalized_spl` | ✅ Done | Feeds `graph_node_execution`; B2 search adapter still open |

**Alignment rules (no contradiction with scope guardrails below):**
- Step 5 discovery **planning** (`plan_splunk_discovery_calls`) stays plan-only by default — unchanged.
- H2 discovery **execution** is the orchestration plan's optional Phase C executor — separate from B2 search.
- RAG slot values flow only through governed `SourceEvidence` / deterministic resolver — **no RAG→LLM direct path** for index substitution.
- B3 allowlist enforcement applies **after** substitution (resolved index must be in `SPL_ALLOWED_INDEXES`).
- B4 HIL reused for unresolved slots and execution approval.

---

### Phase C — Synthesis stage (Wall 2) 🟡 partially landed

**C1. Wire scaffold** — **DONE** (`pipeline.py` after context stage).

**C2. Synthesis + narration** — **FLAG-GATED**

- `run_governed_synthesis_lab` builds `GovernedSynthesisPackage` and deterministic draft.
- Live narration: `AI_SOC_LLM_FINAL_SYNTHESIS_ENABLED` + `AI_SOC_LLM_LIVE_SYNTHESIS_ENABLED` + sufficiency in `_LAB_READY_MODES` + **not** `CONTROL_PLANE_ENABLED`.
- **Gap:** populate lineage placeholders; resolve CP vs legacy narration ownership for production.

**C3. Answer guard** — **FLAG-GATED, WIRED**

`run_answer_guard_lab` runs dormant semantic guards when `AI_SOC_LLM_ANSWER_GUARD_ENABLED=true`. Distinct from `final_answer_validator` (always-on contract check on composed card).

**C4. Kill switches** — **DONE** (defaults false).

---

### Phase D — Route-suggestion LLM exercise (testable now, lowest risk) 🟡

Validate routing governance with supplied route-plan JSON — no live model required.

- Inject via `generate_llm_route_plan_candidate` or monkeypatch `_route_plan_shadow_candidate` (default `None` in `pipeline.py`).
- Confirm: `validate_route_plan_candidate` → `deterministic_route_plan_wins=True` → `disagreements` logged → deterministic skill reaches user. Shadow only.

---

## Scope guardrails (per CLAUDE.md)

- One commit per concern; do not combine execution changes with connector-readiness or UI-only changes.
- Candidate SPL stays non-executable; only approved `normalized_spl` enters the gate.
- LLM never calls MCP directly; backend mediates.
- All MCP/LLM status output redacts secrets (`url_configured`/`auth_configured` booleans only).
- Phases B/C production enablement stay flag-gated and need explicit COE sign-off.
- Experience Center (`coe_synthetic_fixture`) stays isolated — never route live synthesis through demo path.

## Verification (end-to-end)

- Governance regression: `./scripts/run_stage3_governance_regression.sh` → PASS, harness 6/6.
- Backend: `cd backend && PYTHONPATH=../backend:.. python3 -m pytest`.
- Frontend: `cd frontend && npm run build`.
- Per phase:
  - A1/A2 — `test_negative_result_sufficiency.py`, `test_mcp_result_injection_defense.py` (regression pins).
  - B2 — mock real transport; assert `build_splunk_search_inputs` arg mapping + envelope validation.
  - B2b — placeholder SPL → RAG/config resolution → `normalized_spl`; MCP discovery exec mock; HIL on ambiguous RAG.
  - C2/C3 — flag off = deterministic-only; flag on in lab = guarded answer; **also test `CONTROL_PLANE_ENABLED=true` blocks live narration**.
  - D — supplied route-plan JSON → deterministic wins + disagreement in trace.
  - Parity — repeat C/D checks on LangGraph path when `langgraph_orchestration_enabled`.

## Plan housekeeping

- SPL generation audit **closed** 2026-06-13 — see [`2026-06-13_spl-generation-audit-completion.md`](2026-06-13_spl-generation-audit-completion.md). B2b scaffold done; H2 discovery execution remains COE.
- `plan-reviewer` subagent before executing any non-trivial open phase (B2, C production enablement).
- `validator` after each phase.
- Keep MCP orchestration plan and this plan in sync on execution vs discovery semantics.
