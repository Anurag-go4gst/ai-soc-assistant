# Plan — Governed MCP Execution Orchestration

**Status:** In Progress (Phase 0–2 partial; Phase 1 discovery planning landed; Phase 3 search scaffold landed — live COE still required)  
**Date:** 2026-06-13 (updated 2026-06-13)  
**Commits:** `567fe62` (COE source profiles + MCP discovery resolve), `ae88760` (execution confirmation + contract args), orchestration Phase 1 (composer hybrid discovery)
**Related:** `docs/architecture/details.html` §3, `docs/architecture/spl_mcp_execution_controls.md`, `plans/2026-05-30_1845_query-to-answer-live-mcp-llm-readiness.md`, `contracts/splunk_mcp_connection_contract.md`

## Purpose

Define how Splunk MCP tools are **planned**, **selected**, **executed**, and **interpreted** in the live `/chat` pipeline — including who decides (not the LLM), what runs by default, and what happens when results are missing, empty, partial, or need analyst review.

This plan closes the gap documented in `details.html`: **multi-tool discovery planning at step 5 exists only for `guided_investigation` today**; search execution at step 7S.3 is a separate gated phase.

---

## 1. Design principles (non-negotiable)

| Principle | Rule |
|-----------|------|
| LLM never calls MCP | MCP access is backend-only via `evaluate_mcp_execution` / future discovery executor |
| Deterministic authority | Route, SPL validation, tool selection, execution flags, MITRE, severity stay policy-driven |
| LLM advisory only | Tool recommendations, slot wording, narration — never override gates |
| Fail closed | Missing envelope, failed job, timeout, schema mismatch → no fabricated evidence |
| Separate plan vs execute | Step 5 plans *what could run*; step 7 executes *only what passed gates* |
| No route skill for MCP | MCP planning is a **Resource Planner sub-phase**, not a sixth live route skill |

---

## 2. MCP tool surface (7 tools)

Confirmed air-gapped registry (`backend/app/tests/test_airgapped_splunk_tool_surface.py`):

| Tool | Capability | Auto-execute? | Default role |
|------|------------|---------------|--------------|
| `splunk_get_indexes` | Metadata | **No** (planned checklist) | Discovery planning |
| `splunk_get_metadata` | Metadata | **No** | Discovery planning |
| `splunk_get_index_info` | Metadata | **No** | Discovery planning (when index known) |
| `splunk_get_knowledge_objects` | Knowledge discovery | **No** | Discovery planning |
| `splunk_get_info` | Server info | **No** | Registry/status only |
| `splunk_get_user_info` | Admin/sensitive | **Never** | Blocked |
| `splunk_run_query` | Read-only SPL search | **Only if all gates pass** | Search execution (7S.3) |

**Mutating / SAIA / write tools:** discoverable for status, always blocked (`DISALLOWED_MUTATING_TOOLS`).

---

## 3. Two-phase MCP model

```text
Phase A — MCP discovery planning (Step 5, Resource Planner)
  Input:  path_type, intent, evidence_plan, entities (index/host/user), use_case_id
  Output: resource_decisions.mcp.planned_discovery_calls[]
          optional PlanStep purpose=mcp_discovery (planned-only)
  Execute: NEVER by default — analyst checklist OR explicit Phase B when COE enables

Phase B — MCP search execution (Step 7S.3, execution gate)
  Input:  approved normalized_spl, execution flags, HIL approval
  Output: SplunkResultEnvelope → SourceEvidence → sufficiency → answer
  Execute: splunk_run_query ONLY (single search per turn unless COE approves multi-step)
```

**Hybrid paths (`spl_review_plus_rag`, `hybrid_investigation`):** use investigation sequence 7S — SPL → optional pre-MCP RAG → Phase B gate. They need Phase A planning extended beyond guided rescue.

---

## 4. Who decides what (authority matrix)

| Decision | Authority | LLM role |
|----------|-----------|----------|
| Whether MCP is needed at all | Evidence plan + `path_type` (deterministic) | None |
| Which discovery tools to *plan* | `plan_splunk_discovery_calls()` + path policy | None |
| Which search tool to *select* | `select_mcp_tool()` — allowlist + intent `spl_search` | Advisory hint only if `LLM_TOOL_RECOMMENDATION_ENABLED` (default off) |
| Whether search may run | `evaluate_mcp_execution` gate: global flag, server flag, SPL approval, HIL | None |
| Search arguments (time window, limit) | `build_splunk_search_inputs()` + SPL policy env vars | None — LLM slot values must pass same validator |
| Interpret empty vs failed | `validate_mcp_result_envelope()` + context sufficiency gate | Narration of deterministic conclusion only |
| MITRE / severity from MCP rows | Deterministic MITRE decision + severity policy | None |
| Final analyst prose | Optional LLM narration of **fixed** authority fields | Rewrite only; adapter overrides on conflict |

**User-requested MCP server/tool:** preference only — re-validated by deterministic selector (`mcp_tool_selector.py`).

---

## 5. LLM usage boundaries

### LLM must NOT

- Choose or invoke MCP tools directly
- Approve SPL or bypass `spl_validation`
- Convert failed MCP into “no attack found”
- Sum/distinct-user counts across sources without policy
- Auto-chain discovery → search without gate + HIL

### LLM may (when explicitly enabled)

| Flag / mode | Use |
|-------------|-----|
| `LLM_TOOL_RECOMMENDATION_ENABLED` (default false) | Shadow log: suggested tool category vs deterministic pick |
| Live synthesis flags | Narrate analyst summary from `GovernedSynthesisPackage` — facts fixed by authority |
| Shadow routing | Advisory route/intent — adjudication stays deterministic |

**Recommendation:** keep tool recommendation **off** until Phase D telemetry shows value; if enabled, log disagreements in `llm_advisory_trace` only.

---

## 6. Implementation architecture — node vs skill

**Recommended:** extend **Resource Planner / composer** (step 5), not a new route skill.

### New functions (target shape)

```python
# composer.py (or mcp_planning.py called from composer)
build_mcp_discovery_resource_decisions(path_type, evidence_plan, entities) -> dict
compose_mcp_discovery_plan_step(...) -> PlanStep | None  # purpose=mcp_discovery

# splunk_mcp_readiness.py (existing)
plan_splunk_discovery_calls(target_index=..., include_knowledge_objects=...)
plan_splunk_search_call(...)  # already exists — search planning record

# executor.py
# Optional Phase C: execute_planned_discovery(state) — gated, ordered, bounded
# Phase B unchanged: hooks.execution(state) → evaluate_mcp_execution
```

### When to emit Phase A (discovery plan)

| path_type | Discovery plan |
|-----------|----------------|
| `guided_investigation` | Yes (already) |
| `hybrid_investigation`, `spl_review_plus_rag` | Yes — index/entity from QU |
| `spl_review` | Optional — when index unknown or source profile missing |
| `rag_only`, `unsafe_blocked` | No |

### Optional catalog resource

Register `skill:mcp_discovery_planning` as a **pipeline resource skill** (like `evidence_collection`) for trace/UI — **not** a route skill.

---

## 7. Execution outcomes — what the user sees

Use `validate_mcp_result_envelope()` + sufficiency gate + honest answer templates.

| Outcome | envelope / failure_mode | Evidence tier | Answer mode | HIL |
|---------|-------------------------|---------------|-------------|-----|
| **No response / connector error** | `error`, exception in gate | metadata_only | `analyst_review_required` or partial with limitation | Yes |
| **Timeout / job incomplete** | `timeout` | metadata_only | Partial — “submitted but did not complete in window” | Yes |
| **Permission denied** | `permission_denied` / blocked | metadata_only | Blocked + review | Yes |
| **Failed search (syntax, sourcetype)** | `validation_failed`, `schema_mismatch` | metadata_only | No evidence conclusion | Yes |
| **Success, 0 rows** | `empty_result`, `negative_result=true` | source_grounded | Partial/full — “no matching events in window” **not** “no threat” | Optional |
| **Success, truncated rows** | `partial_result` | source_grounded | Partial + “review truncated preview” | Yes |
| **Success, full schema confirmed** | valid, no failure_mode | source_grounded | Full/partial per sufficiency | Per policy |
| **Mock execution** | fixture / mock | fixture labeled | Review required by default | Yes (unless demo relax flag) |

**Critical rule (from spl_mcp_execution_controls §5):** empty ≠ failed. LLM must not treat failed execution as negative evidence.

### “Need more thinking and review” path

When results are received but insufficient for a confident answer:

1. **Context sufficiency gate** classifies: `partial_answer`, `analyst_review_required`, `spl_review_only` — `synthesis_allowed` stays false until COE enables narration.
2. **HIL card** surfaces: what ran, row count, truncation, missing fields, suggested next SPL (review-only).
3. **No auto re-query** in the same turn — analyst approves a follow-up turn or manual Splunk work.
4. Optional **Phase E (later):** bounded multi-step orchestration (Search A → extract entities → Search B) with separate validation + HIL per step — see spl_mcp_execution_controls §7.

---

## 8. Phased delivery

### Phase 0 — Document & align (this plan + details.html) ✅

- Honest gap: discovery planning guided-only → **closed for hybrid/spl_review paths** (Phase 1)
- Architecture: planner node, not route skill

### Phase 1 — MCP discovery planning for all investigation paths (no live I/O) ✅

**Scope:** `composer.py`, `planning_decision.py`, trace UI  
**Deliverables:**

- `build_hybrid_mcp_discovery_resource_decisions()` for hybrid/spl_review paths
- `resource_decisions.mcp.planned_discovery_calls` on `hybrid_investigation`, `spl_review_plus_rag`, `spl_review`
- Tests: `test_planner_path_selection_phase3.py` hybrid + spl_review_plus_rag carry discovery checklist
- Trace: `resource_plan_summary` on planning decision for eligible path types

**Gates:** none — planning only, `execution_disabled`

**Also landed (source-profile track, not Phase B execute):** `run_mcp_source_discovery()` + Settings UI persist discovery into COE slot map (`567fe62`); used at SPL placeholder resolve time, not auto-chained into search.

### Phase 2 — Result envelope hardening (pre-live) ✅

**Scope:** `splunk_result_adapter.py`, `context_sufficiency.py`, `source_evidence.py`  
**Deliverables:** empty vs failed (A1), injection filter (A2), envelope validation in sufficiency — see query→answer Phase A.

### Phase 3 — COE connection + real search adapter (single tool) 🟡 Partial

**Scope:** `splunk_mcp.py`, `mcp_execution_gate.py`, contract doc  
**Deliverables:**

| Item | Status |
|------|--------|
| Contract arg schema wired (`search_query`, `earliest_time`, `latest_time`, `max_results`) | ✅ `ae88760` |
| Analyst confirm-or-update before execute + safe re-validate | ✅ `ae88760` |
| COE source profile UI + persisted slot map | ✅ `567fe62` |
| MCP discovery at placeholder resolve (MCP > store > HIL) | ✅ `567fe62` |
| Real `call_tool` HTTP transport in `splunk_mcp.py` | ❌ COE S5 |
| `_gate_review` open for `registry.mode != "mock"` | ❌ COE S5 |
| `schema_confirmed=true` on contract | ❌ COE |

### Phase 4 — Optional live discovery execution (multi-tool, ordered)

**Scope:** new `execute_mcp_discovery()` in executor — **only if COE requests**  
**Deliverables:**

- Ordered execution: indexes → metadata → knowledge objects (max N calls/turn)
- Each call: timeout, redacted envelope, no raw dump to LLM
- Stops on first hard failure; surfaces checklist for remainder

**Gates:** separate flag `MCP_DISCOVERY_EXECUTION_ENABLED` (default false)

### Phase 5 — Multi-step search orchestration (Search A → B)

**Scope:** orchestration layer, template slots  
**Deliverables:**

- Entity extraction from bounded Search A preview
- Search B with slot-binding validation
- HIL between steps

**Gates:** COE + spl_mcp_execution_controls §7 exception policy

### Phase 6 — LLM narration of MCP-informed answers (optional)

**Scope:** synthesis path only — never tool calling  
**Deliverables:**

- Narration from `SourceEvidence` aggregates only
- Answer guard on output

**Gates:** existing `AI_SOC_LLM_FINAL_SYNTHESIS_ENABLED` + sufficiency ready modes

---

## 9. Configuration flags (summary)

| Flag | Default | Controls |
|------|---------|----------|
| `MCP_GLOBAL_EXECUTION_ENABLED` | false | Any live MCP call |
| `MCP_SERVER_*_EXECUTION_ENABLED` | false | Per-server execution |
| `MCP_SERVER_MOCK_EXECUTION_ENABLED` | false | Mock search in gate |
| `MCP_DISCOVERY_EXECUTION_ENABLED` | false (proposed) | Auto-run discovery tools |
| `LLM_TOOL_RECOMMENDATION_ENABLED` | false | Advisory tool hints |
| `AI_SOC_LLM_FINAL_SYNTHESIS_ENABLED` | false | Narration only |
| `SPL_VALIDATION_ENABLED` | true | Required before search |

---

## 10. COE decisions required before Phase 3+

1. Identity model: analyst pass-through vs scoped service account  
2. Approval workflow: who approves live search, SLA, UI surface  
3. Async search: sync `splunk_run_query` vs submit/poll job lifecycle  
4. Whether Phase 4 discovery auto-execution is in scope or checklist-only forever  
5. Max discovery + search calls per turn  
6. Index/sourcetype allowlist for production Splunk  

---

## 11. Success criteria

| Check | Target |
|-------|--------|
| Discovery plan on hybrid paths | `planned_discovery_calls` present in trace for failed-login hybrid |
| No LLM tool calls | Static audit: LLM modules never import MCP connector execute path |
| Empty result | 0 rows → honest negative wording, not INSUFFICIENT_EVIDENCE |
| Failed MCP | No MITRE/severity upgrade; HIL or limitation on card |
| Partial/truncated | `review_required=true`; analyst next steps listed |
| Governance regression | PASS after each phase |
| details.html | Stays aligned with implemented phase |

---

## 12. Trace / UI surfaces

Each `/chat` response should expose (control plane on):

- `evidence_plan.resource_plan.provenance.resource_decisions.mcp` — planned discovery + skip reasons  
- `execution` — selected tool, status, envelope summary, `result_count`, preview cap  
- `human_review` — when gate blocks or mock requires review  
- `control_plane_trace` — tool selection reason, gate block reason, envelope validation class  

Analyst card sections:

- **Manual Splunk discovery checklist** (from Phase A plan)  
- **Executed search** (if Phase B ran) with row count and limitation  
- **What we cannot conclude** on failure/timeout  

---

## 13. Out of scope for this plan

- Splunk telemetry writes  
- SAIA / generative Splunk tools  
- LLM-initiated follow-up searches without new analyst turn + HIL  
- Making MCP planning a sixth **route** skill  

---

## 14. Immediate next step (recommended)

**COE review Phase 3 gate items** before enabling live `splunk_run_query`: Splunk MCP URL/auth, `schema_confirmed=true`, flip execution flags in target environment.

Code-complete on mock path: contract args + analyst confirmation + source-profile resolve. Remaining engineering after COE sign-off: real `SplunkMcpConnector.call_tool` transport + open `_gate_review` for non-mock registry mode.
