# Plan — Query→Answer Readiness for Live MCP + LLM

**Status:** ✅ COMPLETE (+ post-review hardening) — O5a/b/c + Steps 0–3 + review fixes landed. Live Splunk MCP is credential drop-in: set URL + token, staging smoke, restart. **One caveat:** the streamable_http JSON-RPC transport framing is verified at first live connect — if the deployment uses a submit/poll job protocol (not inline rows), only `_StreamableHttpSearchTransport` changes (gate/lifecycle/envelope stay). Everything else is config-only.  
**Date:** 2026-05-30 (audited 2026-06-13; steps + review fixes 2026-06-14)  
**Branch tip:** `spl-generation-audit` @ `8625b63` + review-fix commit  
**Commits (orchestration spine):** `40d3251` (O5a), `4cbc8ec` (O5b), `f958aab` (O5c-core), `5e76f7b` (Step 0), `dde82c5` (Step 1), `97a973f` (Step 2), `8625b63` (Step 3), + post-review fixes

**Post-review fixes (2026-06-14):** live success now labels `evidence_source: live` + real adapter (`origin: real_mcp`) + no mock HIL (bugs #1/#2); `health()` reports `live_adapter_ready` when configured (#4); `execute_validated_spl` delegates to `call_tool` instead of raising (#5); full-gate live integration test + transport row-extraction test added; per-call `mcp_orchestration` lineage stage; poll flags added to `.env.example`.

**Post-review round 2 (2026-06-14):** httpx-mocked wire tests for `_StreamableHttpSearchTransport` (asserts `{BASE_URL}/mcp` path, `tools/call` method, canonical `splunk_run_query` name, `_`-prefixed args dropped, bearer auth header, 403→`PermissionError`, `rows`/`structuredContent` extraction). #3 now: the *coded* wire (path/method/auth/parsing) is unit-verified offline; only the **real server's actual responses** (inline rows vs job_id, exact field names) remain first-connect-verified — and only `_StreamableHttpSearchTransport` changes if they differ.
**Author:** COE review (Anurag + Claude)  
**Related:** [`contracts/splunk_mcp_connection_contract.md`](../contracts/splunk_mcp_connection_contract.md), [`2026-06-13_spl-generation-audit-completion.md`](2026-06-13_spl-generation-audit-completion.md), [`/root/.cursor/plans/llm_lab-tier_spl_exposure_0c7c3c33.plan.md`](/root/.cursor/plans/llm_lab-tier_spl_exposure_0c7c3c33.plan.md) (Phase G/H)

> **Single plan file.** All MCP orchestration rules, next implementation steps, and credential drop-in architecture live in **this document** (Appendix A + §Next implementation below). Do not maintain parallel handoff plans.
**External sources reconciled (A.17):** Splunk Lantern — [LLM reasoning + ML for Jira alert investigations](https://lantern.splunk.com/Security_Use_Cases/Automation_and_Orchestration/Leveraging_LLM_reasoning_and_ML_capabilities_for_Jira_alert_investigations), [Automating alert investigations with LLMs + Splunk + Confluence](https://lantern.splunk.com/Observability_Use_Cases/Troubleshoot/Automating_alert_investigations_by_integrating_LLMs_with_the_Splunk_platform_and_Confluence)

> **Plan management:** MCP orchestration rules live in **Appendix A** below (formerly a separate `2026-06-13_mcp-execution-orchestration-plan.md`). One file for COE tracking; architecture deep-dives remain in `docs/architecture/spl_mcp_execution_controls.md`.

---

## Status at a glance (2026-06-13)

### What is done

Work completed on `spl-generation-audit` that this plan depends on. **Do not redo these.**

| Area | What shipped | Why it matters | Evidence |
|------|--------------|----------------|----------|
| **Security hardening (Phase A)** | Empty-result ≠ insufficient evidence; MCP result injection defense | Honest negative results; no prompt injection via Splunk rows | `context_sufficiency.py` Rule 3b; `splunk_result_adapter.py`, `mcp_result_safeguard.py` |
| **SPL source resolution (B2b / Phase H)** | Config map, RAG bridge, MCP discovery resolve, HIL clarification, family-aware sourcetype pick | LLM/template SPL can reach `normalized_spl` before any search | `source_profile_resolver.py` (`3a39ed2`); Settings UI (`567fe62`) |
| **Execution gate scaffold (B2 partial)** | Bounded arg mapping, per-run SPL confirmation HIL, mock search path | Gate knows *what* to send to Splunk; analyst must approve | `splunk_search_tool_arguments()` (`ae88760`); `spl_execution_confirmation` |
| **SPL generation audit** | Relevance-first routing, LLM failover, catalogue coverage, post-validation simplifier | Correct SPL for asked questions before MCP runs | Closed in [`2026-06-13_spl-generation-audit-completion.md`](2026-06-13_spl-generation-audit-completion.md) |
| **O5a — orchestration contracts** | `ResourcePlanV2`, `mcp_orchestration` envelope, recipe registry (`single_search`, `broaden_scope_on_empty`), HIL approval gate | Multi-call turns have a governed data model | `40d3251`; 15 contract tests |
| **O5b — scheduler logic** | Pure `schedule_next` / `outcome_edge` — metadata-before-SPL, Search-A→Search-B | Proves dependency ordering without live Splunk | `4cbc8ec`; 9 fixture tests |
| **O5c-core — broaden on empty** | Imperative pipeline hook: empty primary → LLM-proposed broaden → validate → HIL → second search | Governed Lantern-style adapt loop; no open-ended LLM replanning | `f958aab`; `broaden_orchestration.py`; 10 tests |
| **Discovery planning (O1)** | Hybrid/spl_review/guided discovery checklists in resource plan | Analyst sees what discovery *could* run; no auto-execute | `390e2dc` |
| **Synthesis scaffold (Phase C partial)** | Governed synthesis lab + answer guard wired behind flags | Query→answer narration ready when flags enabled | `pipeline.py` → `run_governed_synthesis_lab` |
| **Regression baseline** | Governance regression PASS; sentinel 17/17 | Safe to continue on this branch | `5bfc025` |

**Governance decisions already locked (do not reopen without explicit approval):**

- No new orchestration flag — broaden gates on existing `MCP_*_EXECUTION_ENABLED` + `AI_SOC_LLM_SPL_FALLBACK_ENABLED`.
- LLM never calls MCP; broaden proposal is advisory → validate → HIL → gate.
- `candidate_spl` never executes; only approved `normalized_spl`.
- `.env.example` stays **default-off** (safe for every clone). The live flag set lives in a dedicated committed **`.env.splunk-live.example`** (Step 3) — go-live copies it and drops two secrets.
- Splunk search is **async** — submit/poll/fetch lives inside the connector, not the gate.
- **No external COE dependency.** Go-live decisions are **operator-owned** (this team). `schema_confirmed=true` flips after our own staging smoke. Identity model = **service-account bearer token** (`SPLUNK_MCP_TOKEN`). See §Go-live decisions (A.13).

### What remains (all steps complete ✅)

| Step | Work | Status |
|------|------|--------|
| **0** | Plan honesty pass — reframe COE→operator-owned; bake go-live decisions (A.13) | ✅ Done |
| **1** | LangGraph `spl_source_resolve` before `execution` | ✅ Done — graph rewired + parity test |
| **2** | Per-call `SourceEvidence` + cross-turn `mcp_orchestration` envelope | ✅ Done — finalize + per-call evidence |
| **3** | Production `splunk_mcp.py` async lifecycle; poll flags; `.env.splunk-live.example` | ✅ Done — credential drop-in ready |

**Go-live is now configuration only:** `cp .env.splunk-live.example .env`, set
`SPLUNK_MCP_BASE_URL` + `SPLUNK_MCP_TOKEN`, align allowlists, staging smoke,
`schema_confirmed=true`, restart. No code change.

**After Step 3 — go-live is configuration only:** copy `.env.splunk-live.example` → `.env`, set `SPLUNK_MCP_BASE_URL` + `SPLUNK_MCP_TOKEN`, set `schema_confirmed=true` after staging smoke, restart. No code change.

**Already decided (no longer pending):**
- Canonical search tool = **`splunk_run_query`** (the `splunk_*` 7-tool air-gapped surface from the Splunk MCP docs; `search_splunk`/`splunk.search` are contract aliases only).
- Identity = **service-account bearer token** (`SPLUNK_MCP_TOKEN`).
- Transport lifecycle = **async** submit/poll/fetch inside the connector.

### What is later (not blocking credentials)

| Item | Reason it can wait |
|------|-------------------|
| Full scheduler/reconcile graph (O5d) | Broaden already works via imperative hook; full loop is scale-up |
| Dedicated frontend broaden diff card | Generic HIL renderer is sufficient for v1 |
| O4 discovery auto-execution in chat | Separate COE decision; Settings discover already works |
| Phase C production synthesis enablement | Flag-gated; independent of MCP transport |
| O7 ops rollout playbook | Written after Step 3 staging smoke |

---

## Rationale — why this approach going forward

We are at a junction where one wrong choice (sync stub, parallel plans, deferring async, or rebuilding the adapter when credentials arrive) would break the whole governed pipeline. This section records **why** the remaining work is ordered and shaped this way.

### 1. One plan file, one implementation spine

Parallel handoff docs caused confusion about what was done, what was deferred, and what was “crucial.” Everything now lives in **this file**: status, rationale, next steps (§Next implementation), and orchestration rules (Appendix A). One place to manage, review, and commit against.

### 2. Build for credential drop-in, not “stub now, rebuild later”

The goal is not a demo adapter that gets thrown away. When COE supplies Splunk MCP URL and auth:

- Flip env flags and set `schema_confirmed=true`.
- Restart the backend.
- **Same code** runs live searches.

That requires Step 3 to ship a **production connector** — HTTP/MCP transport, error classification, envelope mapping, and async job lifecycle — behind default-off flags. Mock stays inline-sync for CI only.

### 3. Splunk search is async — not optional, not a follow-up phase

Splunk searches exceed normal HTTP timeouts. The architecture doc (`spl_mcp_execution_controls.md` §4) and Splunk MCP reality both require submit → bounded poll → fetch.

**Our model:** the gate calls `call_tool` **once** per investigation call; the **connector** runs the async lifecycle internally. Polls do not count as new investigation calls and do not touch the planner. A prior “sync v1, defer async” note was wrong and is removed.

### 4. Safety order: parity → evidence → transport

| Order | Reason |
|-------|--------|
| **Step 1 LangGraph parity first** | Two runtimes exist today. Fixing the adapter before parity means live searches could run on a graph that skips source resolution — different behavior per runtime. |
| **Step 2 evidence second** | `broaden_scope_on_empty` is already wired (O5c-core). Without per-call evidence, a two-search turn lies to sufficiency and the analyst card. |
| **Step 3 transport last** | Transport is useless if evidence and parity are wrong. But it must be **complete** (async included) when built — not a thin stub. |

### 5. Deterministic authority around adaptive intelligence

Lantern-style “adapt on empty” is valuable, but authority cannot move to the LLM:

- **Deterministic layer owns:** route, recipe trigger (`previous_empty`), bounds (indexes, sourcetypes, time cap, result cap), tool selection, validation, HIL, execution flags.
- **LLM owns:** *judgment* on what broadened SPL to propose within those bounds.
- **No open-ended replanning:** LLM cannot add calls, raise budgets, or pick tools.

This is why O5a–O5c-core landed before the live adapter — contracts and broaden hook exist; transport plugs into a governed loop.

### 6. Default-off preserves production safety

All new runtime behavior stays behind existing flags (`MCP_GLOBAL_EXECUTION_ENABLED`, per-server execution, mock execution, `AI_SOC_LLM_SPL_FALLBACK_ENABLED`). Default path stays byte-identical single-call mock-off. Governance regression must stay green after every commit.

### 7. What we are not doing (and why)

| Avoided | Why |
|---------|-----|
| New `MCP_MULTI_CALL_ORCHESTRATION_ENABLED` flag | Broaden already gates correctly; another flag adds confusion |
| LLM → MCP direct access | Stage boundary; backend gate is the only execution path |
| Sync live adapter | Would fail on real Splunk timeouts; would require rebuild |
| Full O5d scheduler graph before adapter | Broaden works today; scheduler is scale-up, not prerequisite for first live search |
| Enabling mock/execution in `.env.example` | Would change default posture for all deployments |

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
| `mcp_execution_gate.py:164` blocks real mode | Real block is `_gate_review` at **`:276`** (`registry.mode != "mock"`); `NotImplementedError` catch at **`:155`** if gate is bypassed | **Stale line refs** (updated 2026-06-13) |
| Gate passes only `{"query": normalized_spl}` | **Fixed** — gate uses `splunk_search_tool_arguments()` (`ae88760`) | **Done — B2 scaffold** |
| Phase D route shadow | `_route_plan_shadow_candidate()` in `pipeline.py` still returns `None`; inject via test monkeypatch or `generate_llm_route_plan_candidate` | **Still valid** |

### Implementation-readiness decision (2026-06-13)

The single-call live adapter work is ready to implement after COE confirms the connection contract. The former orchestration design was **not** ready for investigations that require more than one MCP call. Code review confirms five structural gaps:

| Severity | Finding | Code evidence |
|----------|---------|---------------|
| **High** | `PlanStep` has no `depends_on`, call budget, or per-call outcome fields — only one generic `mcp_execution` step is composed | [`resource_plan.py:36`](backend/app/planner/resource_plan.py) `PlanStep`; [`composer.py:313`](backend/app/planner/composer.py) `_mcp_step()` |
| **High** | `execute_plan_dispatch()` is a one-pass parity dispatcher (spl → optional rag → spl_source_resolve → execution); it annotates step status from a singular `execution` and must not own replanning | [`executor.py:62`](backend/app/planner/executor.py), [`executor.py:145`](backend/app/planner/executor.py) `_resolve_status` reads `state["execution"]` |
| **High** | `evaluate_mcp_execution()` performs exactly one `call_tool` and returns one execution dict | [`mcp_execution_gate.py:149`](backend/app/orchestration/mcp_execution_gate.py) |
| **High** | LangGraph omits `graph_node_spl_source_resolve` **and** never uses `execute_plan_dispatch()` — imperative path runs resolve before execution (or via dispatch hooks when a composed plan exists) | [`chat_workflow.py:49`](backend/app/graph/chat_workflow.py) edges; contrast [`pipeline.py:215`](backend/app/chat/pipeline.py) |
| **Medium** | Pipeline state exposes singular `execution`; lineage/evidence aggregation cannot represent multi-call turns without `mcp_orchestration` envelope | [`pipeline.py:521`](backend/app/chat/pipeline.py) `graph_node_execution` |

This revision makes the target explicit:

- `graph_node_evidence_planning` / `compose_resource_plan()` decide that MCP evidence is needed and may select a governed investigation recipe. They do **not** invoke MCP.
- A new deterministic `graph_node_resource_scheduler` selects the next ready plan step from explicit dependencies. An MCP step may therefore run before SPL generation, between searches, or after another evidence step.
- `graph_node_mcp_call_planning` materializes the selected MCP step into a concrete call. Search calls require resolved, approved SPL; metadata/discovery calls use their own deterministic argument validators and may unlock source resolution or another later step.
- `graph_node_mcp_execute_one` executes exactly one approved call through the existing gate.
- `graph_node_mcp_result_assess` records the envelope and produced evidence keys; `graph_node_plan_reconcile` then unlocks the next dependent resource step, selects a declared fallback, requests HIL, or stops.
- The LLM may narrate results or provide a shadow recommendation, but it cannot add a call, choose a tool, write executable SPL, increase a budget, or bypass validation/HIL.

### Production-ready posture (credential drop-in — no rebuild)

When COE supplies Splunk MCP URL, auth, and confirms the binding target, **activation is configuration only**:

1. Set env: `SPLUNK_MCP_BASE_URL`, `SPLUNK_MCP_TOKEN` (or equivalent), `MCP_GLOBAL_EXECUTION_ENABLED=true`, per-server execution flag.
2. Set `schema_confirmed=true` on [`contracts/splunk_mcp_connection_contract.md`](../contracts/splunk_mcp_connection_contract.md) after staging smoke test.
3. Restart backend — **no adapter rewrite**, no gate rewrite, no pipeline rewrite.

Code we build **now** must include:

| Layer | Responsibility | Must ship before credentials |
|-------|----------------|------------------------------|
| **Gate** (`mcp_execution_gate.py`) | One logical `call_tool` per investigation call; validation, HIL, arg mapping | ✅ Already wired |
| **Connector** (`splunk_mcp.py`) | **Async search lifecycle inside `call_tool`**: submit job → bounded poll → fetch envelope. Gate stays sync at the API boundary. | ❌ Build in Step 3 below |
| **Adapter** (`splunk_result_adapter.py`) | Normalize live JSON → `SplunkResultEnvelope` | ✅ Exists; extend for job states |
| **Orchestration** (`mcp_orchestration.py`) | One `McpCallRecord` per investigation call; polls are connector-internal, not new calls | ✅ Contract landed |
| **Evidence** | One `SourceEvidence` per logical call | ❌ Step 2 below |
| **LangGraph** | Same node order as imperative path | ❌ Step 1 below |

**What blocks activation (config only, not code):** missing URL/token, `schema_confirmed=false`, execution flags off, production allowlist env not aligned.

**What is NOT required for credential drop-in:** full scheduler/reconcile graph (O5d), dedicated frontend broaden card, COE ceremony doc.

### Splunk search is async (locked decision)

**Correction:** A prior handoff draft wrongly assumed “sync v1, defer async to Phase 4.” That was incorrect.

| Fact | Source |
|------|--------|
| Splunk searches exceed HTTP/agent timeouts | [`docs/architecture/spl_mcp_execution_controls.md`](../docs/architecture/spl_mcp_execution_controls.md) §4 |
| Planner must not assume `search_splunk` is one synchronous HTTP round-trip | Same doc: “The planner must not assume that `search_splunk` is a single synchronous call.” |
| Submit + polls = **one** logical investigation call | Appendix A §A.3 `job_lifecycle`; `mcp_orchestration.py` `McpCallRecord` comment |
| Mock path returns inline rows | Test convenience only — **not** the live transport model |

**Architecture (production):**

```text
evaluate_mcp_execution()
  └─ call_tool("splunk_run_query", args)     # ONE gate invocation
       └─ SplunkMcpConnector (live):
            submit_search_job → job_id
            poll_search_results (bounded: MCP_MAX_POLLS_PER_CALL, MCP_SEARCH_JOB_TIMEOUT_MS)
            fetch final rows → SplunkResultEnvelope
            return completed | empty | timeout | failed | denied
```

The gate does **not** implement polling. The connector does. Mock connector may keep inline results for CI; live connector **must** implement async lifecycle in the same `call_tool` method we ship in Step 3.

### Missed cases (add to scope)

1. **`CONTROL_PLANE_ENABLED` vs live narration.** `lab_runner.py` skips live model narration when `control_plane_enabled` is true — even if both synthesis flags are on. `.env.example` defaults `CONTROL_PLANE_ENABLED=true`. COE must define which composer owns narration before enabling live LLM in production posture.
2. **LangGraph path.** `routes_chat.py` can delegate to `run_chat_via_langgraph()` when `langgraph_orchestration_enabled`; parity gap is **confirmed today** — LangGraph skips `spl_source_resolve` and does not use `execute_plan_dispatch`. Multi-call nodes must be added to both runtimes.
3. **Two answer validators.** `run_answer_guard_lab` (flag-gated, runs on synthesis draft) vs `final_answer_validator` (deterministic contract validator on composed card). Plan C3 must not conflate them.
4. **Mock execution HIL.** Successful mock runs can still require analyst review (`ai_soc_require_hil_for_mock_execution`); empty-result and synthesis readiness do not bypass HIL.
5. **Hybrid / partial MCP evidence.** Empty search is handled (A1); **timeout**, **failed job**, **envelope schema mismatch**, and mixed outcomes across multiple calls — see Appendix A §execution outcomes.
6. **Contract vs code tool names.** Contract draft uses `splunk.search` / `search_splunk`; gate and registry use `splunk_run_query` alias — B2 must map aliases before COE sign-off.
7. **Lineage population on live narration.** Placeholders exist but `llm_raw_output_placeholder` stays `None` when narration runs; audit reproducibility gap for Phase C production enablement.

---

## Context

COE review of the live `/chat` pipeline (not the Experience Center / demo early-return path). Goal: make the system produce a **grounded final answer** when MCP (Splunk) and the LLM go live — safely, auditable, reviewable.

Today the pipeline is **evidence-rich; answer completeness depends on flags**:

- `routes_chat.py` → `build_live_chat_response()` in `app/chat/pipeline.py` routes → plans → generates+validates candidate SPL → `evaluate_mcp_execution` → `_context_stage` (RAG → SourceEvidence → StructuredContext → sufficiency) → severity/MITRE/lineage → **governed synthesis lab** → answer guard → response.
- `mcp_execution_gate.py` **already calls** `get_mcp_connector().call_tool()` in mock mode. Real execution is blocked at `_gate_review` when `registry.mode != "mock"` (`:276`) and by `NotImplementedError` in the connector (`:155`).
- **Synthesis defaults off** (`AI_SOC_LLM_FINAL_SYNTHESIS_ENABLED=false`). When enabled, a deterministic draft is composed; live narration is a second flag (`AI_SOC_LLM_LIVE_SYNTHESIS_ENABLED`) and is **suppressed when `CONTROL_PLANE_ENABLED=true`**.

Remaining walls for production query→answer:

| Wall | Blocker | Status |
|------|---------|--------|
| **1 — Real MCP** | Production async adapter + credential config | **3 steps remain** — gate scaffold done; `splunk_mcp.py` still `NotImplementedError` |
| **2 — Production synthesis** | Flag enablement + CP vs narration ownership + lineage fill | Partially implemented; independent of MCP Steps 1–3 |
| **3 — Security / audit** | A1/A2 done; LangGraph parity + per-call evidence pending | Mostly done |

This crosses the CLAUDE.md stage boundary for live synthesis — each enabling phase stays behind explicit flags and needs sign-off before production merge.

---

## Phase completion tracker

| Phase | Item | Status | Evidence |
|-------|------|--------|----------|
| **A** | A1 empty-result correctness | ✅ Done | `context_sufficiency.py` Rule 3b; `test_negative_result_sufficiency.py` |
| **A** | A2 results→evidence injection defense | ✅ Done | `splunk_result_adapter.py`, `mcp_result_safeguard.py`; `test_mcp_result_injection_defense.py` |
| **A** | A3 audit lineage hooks | ✅ Placeholders | `lineage/builder.py` synthesis/answer_guard stages |
| **B** | B1 COE connection contract | 🟡 Draft | `contracts/splunk_mcp_connection_contract.md` (`schema_confirmed=false`) |
| **B** | B2 real `call_tool` + arg schema | 🟡 Gate done; adapter open | Args + HIL (`ae88760`); live `splunk_mcp.py` = Step 3 (async inside connector) |
| **B** | B2b SPL source resolution | ✅ Done | Settings UI, MCP discovery resolve, orchestration order (`567fe62`) |
| **B** | B3 cost + allowlist safety | 🟡 Partial | Validator + bounded args at gate; production allowlist = COE env |
| **B** | B4 per-run approval workflow | ✅ Done (mock path) | `spl_execution_confirmation` HIL + chat confirm/update/reject (`ae88760`) |
| **B** | B-orch discovery planning (hybrid paths) | ✅ Done | `build_hybrid_mcp_discovery_resource_decisions` (`390e2dc`) — see Appendix A |
| **B** | B-orch live search adapter | 🟡 Partial | Contract args + confirmation; live `splunk_mcp.py` COE-gated — see Appendix A §O3 |
| **B** | B-orch dependency-aware resource scheduler | ✅ Design ready / code open | MCP may be prerequisite/intermediate/final; scheduler→resource→reconcile loop — see Appendix A §A.3–A.9 |
| **C** | C1 wire synthesis scaffold | ✅ Done | `pipeline.py` → `run_governed_synthesis_lab` |
| **C** | C2 synthesis stage + narration | 🟡 Flag-gated | `lab_runner.py`, `live_narration.py`; CP blocks live narration |
| **C** | C3 answer guard | 🟡 Flag-gated | `answer_guard/runner.py` wired; default off |
| **C** | C4 kill switches | ✅ Done | Flags + `AI_SOC_LLM_MODE=disabled` + air-gap |
| **D** | Route-plan shadow exercise | 🟡 Testable | Default hook returns `None`; tests inject candidates |

---

## Next implementation (ordered — one plan, three commits)

> **Pointers:** Full “what is done” → §Status at a glance. **Why this order** → §Rationale.

**Branch:** `spl-generation-audit` @ `5bfc025`  
**Baseline:** governance regression PASS, pytest green, frontend build PASS  
**Governance:** flags default-off; no new orchestration flag; LLM never calls MCP

Do **not** split this into parallel plan files. Execute in order; one commit per step; run `./scripts/run_stage3_governance_regression.sh` after each.

### Already landed (do not redo)

See §Status at a glance for full context. Commits on this spine:

| Commit | Deliverable |
|--------|-------------|
| `40d3251` | O5a: `recipe_registry.py`, `mcp_orchestration.py`, `ResourcePlanV2`, 15 tests |
| `4cbc8ec` | O5b: `orchestration_scheduler.py`, 9 fixture tests |
| `f958aab` | O5c-core: `broaden_orchestration.py`, `spl_broaden_confirmation` HIL, 10 tests |
| `3a39ed2` | Family-aware `source_profile_resolver.py` |
| `5bfc025` | Sentinel baseline |

### Step 0 — Plan honesty pass (no external COE)

**Why crucial:** "Go-live = credentials only" is only true if every other decision is already baked. With no COE to answer, undecided A.13 items would silently become go-live blockers.

Done in this revision (doc-only, no code):
- A.13 reframed COE→**operator-owned**; every item baked to Config / Decided / Later.
- Canonical search tool pinned: `splunk_run_query`. Identity = service-account bearer. Lifecycle = async.
- `.env.splunk-live.example` + poll flags declared as **Step 3** deliverables (not a parallel file pre-built against non-existent vars).
- `.env.example` stays default-off; live values live in the dedicated template.

**Commit:** `Bake go-live decisions; reframe COE to operator-owned (Step 0)`

### Step 1 — LangGraph parity (safety gap)

**Why crucial:** Imperative path runs `graph_node_spl_source_resolve` before `graph_node_execution`; LangGraph skips it. Wrong sourcetype/index can reach execution on one runtime only.

**Graph edge (non-rag-only):** `workflow_spl` → `spl_source_resolve` → `execution` → `context_finalize`

| File | Change |
|------|--------|
| `backend/app/graph/chat_workflow.py` | Add `spl_source_resolve` node and edges |
| `backend/app/tests/test_langgraph_dual_parity_phase13.py` | Assert resolve trace on LangGraph path |
| `backend/app/tests/test_spl_source_resolve.py` | Imperative vs LangGraph parity |

**Commit:** `Add LangGraph spl_source_resolve parity before execution`

### Step 2 — Per-call evidence + cross-turn envelope

**Why crucial:** `broaden_scope_on_empty` is two logical searches. Singular `execution` cannot represent both; broaden HIL spans turns.

| File | Change |
|------|--------|
| `backend/app/evidence/source_evidence.py` | One `SourceEvidence` per `mcp_orchestration.calls[]` entry |
| `backend/app/chat/pipeline.py` | Append call records on broaden second execution |
| `backend/app/lineage/builder.py` | Per-call orchestration lineage |
| `backend/app/chat/session_context.py` | Persist `mcp_orchestration` + pending confirm across broaden HIL |
| `backend/app/tests/test_broaden_orchestration.py` | Two-call + cross-turn fixtures |
| **New** `backend/app/tests/test_mcp_orchestration_evidence.py` | Empty/failed/mixed outcomes |

**Commit:** `Aggregate per-call MCP evidence and cross-turn orchestration envelope`

### Step 3 — Production Splunk MCP adapter (async lifecycle included)

**Why crucial:** This is the credential drop-in layer. Must ship **with async submit/poll/fetch inside `call_tool`** — not a follow-up phase.

| File | Change |
|------|--------|
| `backend/app/config.py` | Add `mcp_max_polls_per_call=60`, `mcp_search_job_timeout_ms=120000`, `mcp_search_poll_interval_ms=2000` |
| `backend/app/connectors/mcp/splunk_search_lifecycle.py` | **New** — pure async poll state machine (`submitted`/`running`/`completed`/`completed_empty`/`failed`/`timed_out`/`cancelled`/`permission_denied`/`schema_invalid`); bounded by the three config flags; transport calls injected so it is unit-testable without a live server |
| `backend/app/connectors/mcp/splunk_mcp.py` | Live `call_tool` for canonical `splunk_run_query`: streamable_http transport (bearer `SPLUNK_MCP_TOKEN`), drive lifecycle **submit → bounded poll → fetch**, map to `SplunkResultEnvelope`. Aliases (`search_splunk`/`splunk.search`) normalized to `splunk_run_query` at the boundary |
| `backend/app/orchestration/mcp_execution_gate.py` | `_gate_review` `:276` allows `registry.mode == "registry"` when adapter ready + `schema_confirmed` + exec flags; set `evidence_source: live` on real runs |
| `.env.splunk-live.example` | **New committed template** — every flag at live values (`MCP_MODE=registry`, `MCP_GLOBAL_EXECUTION_ENABLED=true`, per-server execution on, poll flags, `AI_SOC_LLM_SPL_FALLBACK_ENABLED=true`, `AI_SOC_REQUIRE_SPL_EXECUTION_CONFIRMATION=true`); only `SPLUNK_MCP_BASE_URL` + `SPLUNK_MCP_TOKEN` blank |
| `contracts/splunk_mcp_connection_contract.md` | Document async job states + poll caps; operator `schema_confirmed` checklist |
| `backend/app/tests/test_splunk_mcp_transport.py` | **New** — injected transport: submit, poll running→complete, empty, timeout, denied, schema-invalid → envelope outcomes |
| `backend/app/tests/test_ws4cd_mcp_adapter_readiness.py` | Extend arg mapping + flag gates |

**Mock stays sync inline** for CI. Live path uses async lifecycle. Same `call_tool` signature — gate unchanged.

**Activation when credentials arrive (no code change):**

```bash
SPLUNK_MCP_ENABLED=true
SPLUNK_MCP_BASE_URL=https://<coe-host>
SPLUNK_MCP_TOKEN=<secret>
MCP_MODE=registry
MCP_GLOBAL_EXECUTION_ENABLED=true
MCP_SERVER_<NAME>_EXECUTION_ENABLED=true
# contract: schema_confirmed=true after staging smoke
```

**Commit:** `Implement production Splunk MCP adapter with async search lifecycle`

### Later (not blocking credential drop-in)

| Item | Why deferred |
|------|--------------|
| Full scheduler/reconcile graph (O5d) | Broaden works via imperative hook today; full loop is scale-up |
| Dedicated frontend broaden diff card | Generic HIL + `safe_message_for_user` sufficient for v1 |
| O4 discovery auto-execution | Separate COE decision |
| O7 staged rollout playbook | Ops doc after Step 3 smoke test |

### Verification (every step)

```bash
./scripts/run_stage3_governance_regression.sh
cd backend && PYTHONPATH=../backend:.. python3 -m pytest \
  app/tests/test_broaden_orchestration.py \
  app/tests/test_orchestration_scheduler.py \
  app/tests/test_recipe_registry_contract.py \
  app/tests/test_langgraph_dual_parity_phase13.py -q
cd frontend && npm run build
```

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

### Phase B — Real MCP adapter (Wall 1) 🟡 Step 3 (operator-owned)

**B1. Connection contract (operator-owned; no external COE).**

Contract: `contracts/splunk_mcp_connection_contract.md`. Values are now **decided/config** (see §Go-live decisions A.13): URL/auth = deploy config; transport `streamable_http`; canonical tool `splunk_run_query`; arg schema `search_query`/`earliest_time`/`latest_time`/`max_results`; per-call approval. Operator sets `schema_confirmed=true` after our own staging smoke.

**B2. Implement real `call_tool` (production adapter — async lifecycle included).**

- ✅ Gate uses `splunk_search_tool_arguments()` / `build_splunk_search_inputs()` (`ae88760`).
- ❌ Live transport in `app/connectors/mcp/splunk_mcp.py` — **must implement async submit/poll/fetch inside `call_tool`**, not a sync stub. See §Next implementation Step 3.
- Flip `_gate_review` `:276` once adapter + `schema_confirmed=true` + exec flags.
- Reuse `live_schema_capture.py` + `discovery.py` for tool discovery.
- Align tool name aliases (`splunk_run_query` ↔ `search_splunk` ↔ contract `splunk.search`) at live boundary.
- **Credential drop-in:** when URL/auth supplied, activation is env + `schema_confirmed` only — no adapter rebuild.

**B4. Per-run approval workflow.**

- ✅ `AI_SOC_REQUIRE_SPL_EXECUTION_CONFIRMATION` (default true): analyst must confirm or paste updated SPL; safe `validate_spl` before `call_tool`.
- ✅ Chat UI: Confirm & run / Run updated SPL / Reject on `spl_execution_confirmation` card.
- Mock path complete; live path uses same gate after COE enables execution flags.

**B3. Cost + allowlist safety.**

Enforce bounded `earliest/latest` + `SPL_MAX_RESULT_LIMIT` at validation **before** execution (wired via `splunk_search_tool_arguments`). Align `SPL_ALLOWED_INDEXES` / `SPL_ALLOWED_SOURCETYPES` with live Splunk deployment (COE env).

**Missed: discovery vs search.** See **Appendix A** — Step 5 discovery planning (planned-only) vs Step 7 `splunk_run_query` execution (gated). B2 covers search; B-orch Phase O1 covers hybrid/spl_review discovery checklists.

**B2b. SPL source resolution (cross-plan — does not replace B2).**

Prerequisite for LLM-generated SPL to reach `normalized_spl` and enter the search gate. Documented in [`llm_lab-tier_spl_exposure` plan](/root/.cursor/plans/llm_lab-tier_spl_exposure_0c7c3c33.plan.md) Phase H; **extends** this plan, does not contradict it.

| Step | Source | Pipeline node | Executes? |
|------|--------|---------------|-----------|
| G | Lab-tier LLM SPL exposure (placeholders visible) | ✅ Done | `validate_spl_lab_candidate`, pipeline exposure split (`8f44eee`) |
| H0 | Config / skills / `SPL_ALLOWED_*` env map | ✅ Done | `source_profile_resolver.py`, `AI_SOC_SOURCE_PROFILE_MAP` |
| H1 | **RAG / playbook** — KB `splunk_indexes`, `sourcetypes`, `fields` | ✅ Done | `rag_source_profile_bridge.py` |
| H2 | MCP discovery **execution** (`splunk_get_indexes`, `splunk_get_metadata`) | ✅ Mock + Settings | `run_mcp_source_discovery()`; COE UI persist; resolve-time MCP > store (`567fe62`) |
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

## Appendix A — MCP execution orchestration (canonical)

*Merged from `2026-06-13_mcp-execution-orchestration-plan.md` (2026-06-13). Governs **who decides**, **plan vs execute**, and **what the analyst sees** for Splunk MCP in live `/chat`.*

### A.1 Design principles

| Principle | Rule |
|-----------|------|
| LLM never calls MCP | Backend-only via `evaluate_mcp_execution` / discovery helpers |
| Deterministic authority | Route, SPL validation, tool selection, execution flags, MITRE, severity stay policy-driven |
| LLM advisory only | Tool recommendations, narration — never override gates |
| Fail closed | Missing envelope, timeout, schema mismatch → no fabricated evidence |
| Separate plan vs execute | Step 5 plans *what could run*; Step 7 executes *only what passed gates* |
| No route skill for MCP | Resource Planner sub-phase — not a sixth live route skill |

### A.2 MCP tool surface (7 tools)

| Tool | Auto-execute? | Role |
|------|---------------|------|
| `splunk_get_indexes`, `splunk_get_metadata`, `splunk_get_index_info`, `splunk_get_knowledge_objects` | **No** (planned checklist) | Discovery planning |
| `splunk_get_info` | **No** | Registry/status only |
| `splunk_get_user_info` | **Never** | Blocked |
| `splunk_run_query` | **Only if all gates pass** | Search execution (Step 7) |

Mutating / SAIA / write tools: discoverable for status, always blocked.

### A.3 Dependency-aware planner model

```text
Layer 1 — Evidence/resource planning (early planner)
  Node:   graph_node_evidence_planning / compose_resource_plan
  Output: governed step graph, evidence gaps, dependencies, policy limits
  Rule:   no MCP I/O; steps describe capability needs, not user-selected authority

Layer 2 — Runtime resource scheduling
  Node:   graph_node_resource_scheduler
  Output: next ready PlanStep or terminal decision
  Inputs: step dependencies, produced evidence keys, prior outcomes, budgets
  Rule:   choose only a ready, policy-eligible step; no connector call

Layer 3 — Resource-specific planning and execution
  MCP:    graph_node_mcp_call_planning -> graph_node_mcp_execute_one -> graph_node_mcp_result_assess
  Other:  existing RAG / SPL / MITRE / HIL nodes through the same scheduler contract
  Output: produced evidence keys + step outcome + lineage

Layer 4 — Reconcile and continue
  Node:   graph_node_plan_reconcile
  Rule:   mark dependents ready, select governed fallback, request HIL, or stop
  Loop:   reconcile -> resource_scheduler until terminal or budget exhausted
```

Discovery remains a distinct call class:

```text
Discovery planning (Resource Planner)
  Output: resource_decisions.mcp.planned_discovery_calls[]
  Execute: never by default; optional only when COE enables discovery execution

Search execution
  Execute: splunk_run_query only, one call per executor-node visit
  Repeat:  bounded and serial in v1; no parallel fan-out
```

**Source-profile resolve (B2b):** `run_mcp_source_discovery()` at placeholder resolve time is separate — MCP > COE store > HIL; not auto-chained into search.

MCP call classes must remain distinct:

| Call class | Example | May run when | What it can unlock |
|------------|---------|--------------|--------------------|
| `metadata_discovery` | `splunk_get_indexes`, `splunk_get_metadata` | Plan requires missing source/schema metadata | Source-profile resolution, template selection, clarification |
| `evidence_search` | `splunk_run_query` | Approved `normalized_spl` and all execution gates pass | SourceEvidence, correlation pivots, sufficiency |
| `investigation_pivot` | second governed `splunk_run_query` | Recipe dependency and typed bounded outputs from a prior call | Cross-source correlation evidence |
| `job_lifecycle` | submit/poll/fetch or one server abstraction | Search was accepted asynchronously | Final envelope only; does not count as a new investigation decision |

The planner must distinguish **investigation calls** from **transport lifecycle operations**. A submit plus several polls is one logical `McpCallSpec` and consumes one investigation-call budget, while poll count/time is bounded separately by the connector lifecycle policy.

Search call planning remains post-resolution: the scheduler may select metadata MCP earlier, but it cannot materialize an `evidence_search` or `investigation_pivot` from `candidate_spl`. Those steps stay blocked until source resolution and full SPL validation produce approved `normalized_spl`.

### A.4 Target graph and imperative parity

```text
resource_scheduler
  -> metadata MCP ---------> assess -> reconcile ----+
  -> RAG -------------------> assess -> reconcile ----+
  -> SPL generation/resolve -> validate -> reconcile -+
  -> evidence MCP ----------> assess -> reconcile ----+--> resource_scheduler
  -> HIL/clarification -----> reconcile --------------+
  -> context_finalize when terminal
```

The same pure node functions must be used by both runtimes:

- LangGraph uses conditional edges from `resource_scheduler` and `plan_reconcile`.
- The imperative pipeline uses a bounded driver loop around the same scheduler, resource nodes, and reconcile function.
- `execute_plan_dispatch()` remains a compatibility dispatcher during migration; it must not become the multi-call planner.
- Add explicit source-resolution and reconcile stages to the live graph so LangGraph and imperative execution have the same safety order.
- The existing planner-led fan-out/fan-in shadow graph is a parity baseline, not the final adaptive execution topology. Intermediate MCP dependencies require a scheduler/reconcile loop rather than a fixed terminal MCP branch.
- LangGraph must adopt the same scheduler/reconcile semantics for the complete resource loop, not only the search stage or `execute_plan_dispatch()` on the imperative side.

### A.5 Authority matrix

| Decision | Authority | LLM role |
|----------|-----------|----------|
| Whether MCP is needed | Evidence plan + `path_type` | None |
| Investigation recipe | Deterministic recipe registry + route/evidence policy | Shadow suggestion only |
| Next resource step / stop decision | `graph_node_resource_scheduler` + `graph_node_plan_reconcile` | None |
| MCP capability needed for a step | Step `requires`/`produces` + deterministic evidence-to-capability mapping | None |
| Concrete MCP tool | Capability mapping + live safe discovery metadata + allowlist + registry health | Advisory only; cannot select |
| Tool fallback | Predeclared equivalent-capability alternatives with identical/lower authority | None |
| Discovery tools to *plan* | `plan_splunk_discovery_calls()` + path policy | None |
| Search tool to *select* | `select_mcp_tool()` | Advisory only if `LLM_TOOL_RECOMMENDATION_ENABLED` (default off) |
| Whether search may run | `evaluate_mcp_execution` + flags + B4 confirmation | None |
| Search arguments | `splunk_search_tool_arguments()` + SPL policy env | None |
| Empty vs failed vs timeout | Envelope validation + context sufficiency | Narration of deterministic conclusion only |
| MITRE / severity from rows | Deterministic MITRE + severity policy | None |

User-requested MCP server/tool: **preference only** — re-validated by `mcp_tool_selector.py`.

`PlanningDecision.selected_tools` remains route-level planning/trace metadata. It must not authorize execution. `ResourcePlanV2` step capability, runtime registry status, deterministic mapping, argument validation, and the execution gate jointly determine the concrete tool at runtime.

#### MCP decision algorithm

For every scheduler iteration:

1. Recompute unresolved required/optional evidence keys from validated step outcomes.
2. Find plan steps whose `depends_on` conditions are satisfied and whose outputs are still needed.
3. If the ready step requires an MCP capability, map the evidence need through `evidence_mcp_mapping.py` and the resource registry.
4. Intersect mapped tools with live discovered tools, server availability, read-only capability, identity/RBAC, per-server flags, and step policy.
5. Rank deterministically: exact governed tool binding, then approved equivalent-capability fallback; user/LLM preferences never outrank policy.
6. Validate arguments with the tool-specific schema. Search tools additionally require approved `normalized_spl`; metadata tools require bounded allowlisted selectors.
7. If no eligible tool exists, apply the step's declared failover. Otherwise emit one `McpCallSpec`.
8. After the result, classify the outcome, record produced evidence keys, and reconcile the next step.

### A.6 Multi-call state and contracts

Do not overload the existing singular `execution` object as the source of truth. Add a versioned orchestration envelope:

```text
mcp_orchestration:
  schema_version: "1"
  orchestration_id: <trace-scoped id>
  recipe_id: <governed recipe or single_search>
  status: planned|awaiting_approval|running|complete|partial|blocked|failed|budget_exhausted
  call_budget: {max_calls, calls_planned, calls_started, calls_completed, max_wall_time_ms}
  unresolved_evidence_keys: []
  calls: McpCallRecord[]
  next_call: McpCallSpec|null
  stop_reason: string|null
```

`McpCallSpec` must include `call_id`, `sequence`, `depends_on`, `purpose`, server/tool, argument template, normalized SPL hash, required policy checks, and approval state. `McpCallRecord` adds timestamps, outcome classification, redacted arguments, result-envelope reference, result count, warnings, and error type.

Extend `PlanStep` or introduce `ResourcePlanV2` with:

```text
depends_on[]
activation_condition
requires_evidence_keys[]
produces_evidence_keys[]
resource_capability
resource_alternatives[]
on_unavailable / on_empty / on_error / on_timeout / on_denied
max_attempts
```

Fallbacks are edges to other plan steps or terminal policies, not ad hoc exception handling inside the connector.

Compatibility during migration:

- Keep response `execution` as a derived summary of the primary/last search for existing clients.
- Make `mcp_orchestration.calls[]` authoritative for lineage and new UI.
- Update evidence adaptation to produce one `SourceEvidence` item per successful/empty call; failed calls produce limitations, never negative evidence.
- Aggregate sufficiency across call evidence without merging row counts or distinct counts across sources unless an explicit deterministic aggregation policy allows it.

### A.7 Bounded planning and stop rules

Initial defaults are conservative and remain configurable only within hard server-side caps:

- Serial execution only.
- `MCP_MAX_CALLS_PER_TURN=3` proposed default; hard cap must not be user- or LLM-controlled.
- One active logical investigation call at a time; each call has its own lifecycle timeout/poll cap and the orchestration has a total wall-clock budget.
- Every search call requires approved, non-null `normalized_spl` and deterministic validation immediately before execution.
- Approval binds `orchestration_id`, `call_id`, SPL hash, server, tool, and bounded arguments. Any material change invalidates approval.
- Default production posture requires approval per search call. A future recipe-level approval may cover multiple calls only if the UI shows every exact query/argument set before approval and COE explicitly enables it.

Stop when any condition is true:

1. Required evidence keys are satisfied.
2. The governed recipe has no eligible dependent call.
3. A call is blocked, denied, schema-invalid, or permission-failed.
4. Timeout/error policy says fail closed; retries are not automatic in v1.
5. Call or wall-clock budget is exhausted.
6. Analyst rejects or changes scope.

An empty result may activate a predeclared fallback call only when the recipe explicitly defines that edge. It must never trigger open-ended LLM replanning. The LLM *may* propose the broadened query content on such an edge (see A.17 `broaden_scope_on_empty`) — bounded by validation, allowlist, budget, and per-call approval. "Bounded LLM-proposed retry" is permitted; "open-ended LLM replanning" (LLM adds calls, raises budget, leaves allowlist, or re-plans the investigation) is not.

### A.8 Failover policy

| Failure/outcome | Allowed deterministic failover | Prohibited behavior |
|-----------------|--------------------------------|---------------------|
| Preferred tool undiscovered/unavailable | Select predeclared equivalent-capability tool on an approved server | Guess a tool name or let LLM choose |
| Metadata discovery unavailable | Use fresh COE source-profile store, then governed RAG metadata, otherwise HIL clarification | Generate executable SPL with unresolved sources |
| Search tool unavailable | Stop or use explicitly approved equivalent search tool with same validation/approval | Fall back to SAIA/generative/write/admin tool |
| Connector/transient error | At most configured retry of the same idempotent lifecycle operation; then partial/review | Generate a different search automatically |
| Async job still running | Poll within poll/time budget; optionally persist resumable job state | Count each poll as a new investigation or poll indefinitely |
| Permission denied/RBAC | Stop and request admin/analyst review | Retry with broader service identity |
| Schema mismatch | Reject envelope, mark evidence unavailable, require adapter/COE review | Pass raw rows to synthesis |
| Search validation failure | Return to SPL revision/HIL; revalidate after changes | Execute candidate or unvalidated SPL |
| Successful empty result | Mark scoped negative evidence; follow only explicit `on_empty` recipe edge | Treat as connector failure or broad “no threat” conclusion |
| Partial/truncated result | Preserve partial evidence and limitation; follow explicit recipe policy | Silently present as complete |

Fallback selection must not increase authority, data scope, time range, result cap, or tool capability. Any fallback that changes executable arguments invalidates prior approval.

### A.9 Governed recipe shape

Multi-call behavior must come from a small deterministic recipe registry, not free-form planner prose. Start with `single_search` and add one COE-approved investigation recipe at a time.

```text
recipe:
  recipe_id
  eligible_skills / path_types
  max_calls
  calls[]:
    call_id, purpose, depends_on, activation_condition
    call_class, resource_capability, resource_alternatives
    spl_template_family or deterministic transform
    required_evidence_keys
    produces_evidence_keys
    on_unavailable, on_empty, on_error, on_timeout, on_denied, terminal
```

Allowed activation conditions in v1: `always`, `previous_ok`, `previous_empty`, `evidence_key_missing`. Conditions operate on normalized envelope metadata, not arbitrary row-content interpretation. Any follow-up SPL produced by a deterministic transform re-enters source resolution and full SPL validation.

### A.10 Execution outcomes (what the analyst sees)

| Outcome | Answer mode | HIL |
|---------|-------------|-----|
| Connector error | `analyst_review_required` or partial + limitation | Yes |
| Timeout | Partial — job did not complete in window | Yes |
| Permission denied | Blocked + review | Yes |
| Failed search (validation/schema) | No evidence conclusion | Yes |
| Success, 0 rows | Honest negative — **not** “no threat” | Optional |
| Success, truncated | Partial + review truncated preview | Yes |
| Mock execution | Fixture labeled | Yes (unless demo relax flag) |
| Mixed multi-call outcomes | Partial answer with per-call limitations | Yes |
| Budget exhausted | Partial/review-required; list unresolved evidence | Yes |

**Rule:** empty ≠ failed. LLM must not treat failed execution as negative evidence. Same-turn follow-up is allowed only through a predeclared governed recipe, per-call validation, budget checks, and required HIL.

### A.11 Orchestration delivery sub-phases (O0–O7)

| Sub-phase | Scope | Status |
|-----------|-------|--------|
| **O0** | Document & align (`details.html`, this appendix) | ✅ |
| **O1** | Discovery planning for hybrid/spl_review/guided (`composer.py`) | ✅ `390e2dc` |
| **O2** | Envelope hardening | ✅ (= Phase A) |
| **O3** | Live `splunk_run_query` adapter | ✅ **Implemented (Step 3)** — `splunk_search_lifecycle.py` (async submit/poll/fetch, bounded) + `splunk_mcp.py` live `call_tool` (streamable_http bearer, alias→`splunk_run_query`) + gate honest-outcome classification + `get_mcp_connector` registry routing. `.env.splunk-live.example`, config poll flags, contract async section. `test_splunk_mcp_transport.py`. Go-live = credentials only |
| **O4** | Optional auto discovery execution | ❌ Proposed (`MCP_DISCOVERY_EXECUTION_ENABLED`) |
| **O5a** | `ResourcePlanV2` dependency/failover contracts + deterministic recipe registry | ✅ Contract landed — `app/planner/recipe_registry.py` (`single_search`, `broaden_scope_on_empty`), `app/orchestration/mcp_orchestration.py` (envelope + HIL-approval gate `can_execute_call`/`approve_call`), `ResourcePlanV2` in `resource_plan.py`; `test_recipe_registry_contract.py` (15 tests). No connector change; default-off |
| **O5b** | Resource scheduler + MCP plan/execute-one/assess + reconcile loop | ✅ Pure functions landed — `app/planner/orchestration_scheduler.py` (`schedule_next`, `outcome_edge`, evidence-key helpers); `test_orchestration_scheduler.py` (9 tests, fixture-only) proves metadata-before-SPL + Search-A→Search-B. Not wired beyond O5c-core below |
| **O5c** | Async lifecycle, evidence aggregation, lineage, UI, parity tests | 🟡 **Core landed** — `broaden_orchestration.py` in `graph_node_execution`; `spl_broaden_confirmation` HIL; `mcp_orchestration` envelope; 10 tests. **Remaining in §Next implementation:** Step 1 LangGraph parity, Step 2 per-call evidence, Step 3 production adapter **with async lifecycle inside connector** (not a separate phase). Frontend broaden card = later only. |
| **O6** | LLM narration of MCP-informed answers | 🟡 (= Phase C; flag-gated) |
| **O7** | Live activation and staged rollout | ❌ COE-gated |

### A.12 Configuration flags (MCP + confirmation)

| Flag | Default | Controls |
|------|---------|----------|
| `MCP_GLOBAL_EXECUTION_ENABLED` | false | Any live MCP call |
| `MCP_SERVER_*_EXECUTION_ENABLED` | false | Per-server execution |
| `MCP_SERVER_MOCK_EXECUTION_ENABLED` | false | Mock search in gate |
| `AI_SOC_REQUIRE_SPL_EXECUTION_CONFIRMATION` | true | Analyst confirm/update before search |
| `MCP_DISCOVERY_EXECUTION_ENABLED` | false (proposed) | Auto-run discovery tools |
| `MCP_MULTI_CALL_ORCHESTRATION_ENABLED` | ~~proposed~~ **dropped** | COE decision 2026-06-13: **no new flag.** Broaden-on-empty orchestration gates on existing `MCP_*_EXECUTION_ENABLED` + `AI_SOC_LLM_SPL_FALLBACK_ENABLED`; default-off = unchanged single-call |
| `MCP_MAX_CALLS_PER_TURN` | 3 (proposed, server-capped) | Maximum started MCP calls in one turn |
| `MCP_ORCHESTRATION_MAX_WALL_TIME_MS` | COE decision | Total MCP loop wall-clock budget |
| `MCP_MAX_POLLS_PER_CALL` | 60 (**Step 3 → `config.py`**, server-capped) | Async lifecycle poll cap **per logical call** (connector-internal) |
| `MCP_SEARCH_JOB_TIMEOUT_MS` | 120000 (**Step 3 → `config.py`**) | Max wall time for one search job |
| `MCP_SEARCH_POLL_INTERVAL_MS` | 2000 (**Step 3 → `config.py`**) | Poll interval between status checks |
| `LLM_TOOL_RECOMMENDATION_ENABLED` | false | Advisory tool hints |
| `SPL_VALIDATION_ENABLED` | true | Required before search |

### A.13 Go-live decisions (operator-owned — no external COE)

No external COE will respond; these are **our** decisions. Each is now baked to a default so go-live is credentials-only. "Config" = supply at deploy time; "Decided" = locked here; "Later" = not blocking first live search.

| # | Decision | Status | Value / default |
|---|----------|--------|-----------------|
| 1 | Splunk MCP URL, transport, auth | **Config** | `SPLUNK_MCP_BASE_URL` + `SPLUNK_MCP_TOKEN` at deploy; `MCP_MODE=registry`; transport `streamable_http` |
| 2 | Identity model | **Decided** | Service-account bearer token (`SPLUNK_MCP_TOKEN`); not analyst pass-through in v1 |
| 3 | `splunk_run_query` lifecycle | **Decided** | **Async** submit/poll/fetch inside connector; gate = one logical call |
| 4 | Canonical search tool name | **Decided** | `splunk_run_query` (`splunk_*` surface; aliases mapped at boundary) |
| 5 | Max calls per turn + wall-clock | **Decided** | `MCP_MAX_CALLS_PER_TURN=3`, `MCP_SEARCH_JOB_TIMEOUT_MS=120000` (override per deploy) |
| 6 | Production index/sourcetype allowlist | **Config** | `SPL_ALLOWED_INDEXES` / `SPL_ALLOWED_SOURCETYPES` per deployment |
| 7 | Per-call vs recipe approval | **Decided** | Per-call approval (`AI_SOC_REQUIRE_SPL_EXECUTION_CONFIRMATION=true`) |
| 8 | First governed multi-call recipe | **Decided** | `broaden_scope_on_empty` (already shipped O5a/O5c-core) |
| 9 | Equivalent-capability tool fallback allowlist | **Later** | None in v1; single search tool, no fallback tool |
| 10 | Poll interval / cancellation / resumability | **Decided** | `MCP_SEARCH_POLL_INTERVAL_MS=2000`, `MCP_MAX_POLLS_PER_CALL=60`; no resumable jobs in v1 |
| 11 | ML-model-application MCP tools | **Later** | Out of v1 scope (A.16) |
| 12 | `schema_confirmed=true` sign-off | **Operator** | Flip after our own staging smoke; no external body |

### A.14 Required tests and acceptance criteria

- Metadata MCP can run before SPL when it is an explicit prerequisite.
- Search MCP emits no call before source resolution and approved validation.
- `candidate_spl` can never enter `McpCallSpec`.
- One executor-node visit performs at most one connector call.
- Async submit/poll/fetch remains one logical investigation call with bounded polls.
- Maximum-call and wall-clock limits stop the loop deterministically.
- Empty, timeout, permission denied, schema mismatch, partial, and mixed outcomes remain distinct.
- Approval hash mismatch blocks execution after any SPL/argument change.
- A failed call cannot satisfy an evidence key or become negative evidence.
- Every call has trace/lineage records; secrets and raw auth never appear.
- Imperative and LangGraph paths produce equivalent orchestration summaries and evidence for the same fixture.
- Tool-unavailable, metadata-store, RAG-metadata, HIL, equivalent-tool, and no-fallback paths are independently tested.
- Fallback cannot increase authority/scope and argument changes invalidate approval.
- Feature flag off preserves current single-call response contracts and governance baseline.
- Governance regression, full backend tests, harness 6/6, and frontend build pass.

### A.15 Trace / UI surfaces

- `evidence_plan.resource_plan.provenance.resource_decisions.mcp` — planned discovery + skip reasons
- `execution` — tool, status, envelope, `result_count`
- `mcp_orchestration` — recipe, budget, ordered calls, per-call outcome, stop reason
- `human_review` — gate blocks, `spl_execution_confirmation`, source-profile HIL
- Settings → **Source Profiles** — COE index/sourcetype map
- Analyst card: discovery checklist, executed search, limitations on failure

### A.16 Out of scope

Splunk telemetry writes; SAIA/generative tools; free-form or LLM-initiated MCP calls; unbounded retries; parallel MCP fan-out in v1; MCP as sixth route skill.

### A.17 External guidance reconciliation — Splunk Lantern (2026-06-13)

Reviewed two Lantern MCP-investigation playbooks:

- Security / Automation: *Leveraging LLM reasoning and ML capabilities for Jira alert investigations* (Splunk MCP server for Cloud Platform + Jira; applies pre-existing ML models so users skip writing the SPL needed to run them).
- Observability / Troubleshoot: *Automating alert investigations by integrating LLMs with the Splunk platform and Confluence* (Atlassian MCP `searchConfluenceUsingCql`/`getConfluencePage` for runbooks; Splunk MCP `run_splunk_query`/`get_indexes`/`get_metadata`; Plan-Run-Adapt-Re-run loop; "stop and ask me for guidance" HIL; one-time auth).

Most guidance already matches this plan (discovery-before-query, runbook→plan→query, per-call approval, HIL, tool surface, secret-safe auth). Three deliberate divergences and one capability gap:

| # | Lantern pattern | Our governed stance | Resolution |
|---|-----------------|---------------------|------------|
| 1 | **Plan-Run-Adapt-Re-run** — on empty results the LLM autonomously widens the time window / tries alternative sourcetypes and re-runs | A.7 forbids *open-ended* LLM replanning; A.9 `on_empty` activation must be predeclared | **Adopt the value, govern the loop — LLM proposes, deterministic validates.** Add a `broaden_scope_on_empty` recipe whose retry edge is *triggered* deterministically (`previous_empty`) but whose broadened query is *proposed by the LLM* through the existing LLM-primary SPL failover path. The proposal is a lab-tier candidate — it re-enters R5 relevance → source resolve → `validate_spl` → allowlist → per-call approval before it can run. Adaptive intelligence kept; authority not ceded. Not a closed rigid transform. |
| 2 | **ML-model application without SPL** (Cloud Platform MCP runs pre-existing ML models) | Plan is SPL-search-centric; air-gapped 7-tool surface (A.2) has no model-apply tool | **Forward note only.** Treat `apply_ml_model` / model-discovery as a future call class behind the same authority matrix (capability mapping → discovery → allowlist → approval). Not in the 7-tool air-gapped surface; raise as COE decision A.13 #11. Out of v1 scope (A.16). |
| 3 | Prompt gives **contextual hints, no exact tool prescription**; LLM may steer toward an MCP | LLM is fully out of tool selection; selection is deterministic (A.5) | **No change to authority.** Contextual hints are fine *for narration only* (C2). Tool choice stays deterministic; LLM hints never authorize a call. Documented divergence — intentional, stricter than Lantern. |
| 4 | Atlassian MCP for runbook retrieval | Our runbooks live in governed SOC-KB RAG (H1), not a live Confluence MCP | **No change.** RAG path is the air-gapped equivalent; no live Confluence MCP. If COE later wants live Confluence, it enters as a separate read-only MCP under the same registry, never an LLM-direct path. |

**Governed `broaden_scope_on_empty` recipe (delta 1 — the one concrete addition):**

```text
recipe:
  recipe_id: broaden_scope_on_empty
  eligible_skills: [spl_generation, guided_investigation]   # COE to confirm
  max_calls: 2
  calls:
    - call_id: c1_primary_search
      call_class: evidence_search
      activation_condition: always
      spl_template_family: <route-bound family>
      produces_evidence_keys: [primary_search_rows]
    - call_id: c2_broadened_search
      call_class: evidence_search
      depends_on: [c1_primary_search]
      activation_condition: previous_empty   # deterministic TRIGGER
      # broadened query is LLM-PROPOSED, deterministically validated:
      spl_source: llm_failover_candidate     # reuses AI_SOC_LLM_SPL_FALLBACK path
      proposal_context:
        - empty_primary_query + route + evidence gap (no raw rows to LLM)
        - allowed indexes/sourcetypes + earliest cap (LLM proposes WITHIN bounds)
      validation_chain: [r5_relevance, source_resolve, validate_spl, allowlist, approval]
      produces_evidence_keys: [broadened_search_rows]
      on_empty: terminal   # honest negative; never "no threat"
      on_invalid_proposal: terminal   # LLM proposal fails any gate -> stop, HIL
```

**LLM-assisted failover loop (why this is not a closed rigid solution).** On `previous_empty`, the recipe invokes the existing LLM-primary SPL failover (`AI_SOC_LLM_SPL_FALLBACK_ENABLED`, default off) — *no new flag*. The LLM reasons about *why* the primary returned empty (wrong sourcetype, time window too tight for a slow attack, over-narrow filter) and proposes a broadened/alternative SPL. That proposal is **advisory and non-executable**: it enters as a lab-tier candidate (`validate_spl_lab_candidate`), passes the R5 `spl_relevance_check`, resolves sources, runs full `validate_spl`, and consumes a **fresh per-call approval** before any execution. The deterministic layer owns the bounds (LLM cannot exceed `SPL_DEFAULT_EARLIEST`, leave `SPL_ALLOWED_INDEXES`/`_SOURCETYPES`, raise the result cap, or select a blocked tool); the LLM owns the *judgment* of what to try. Scope change invalidates the prior approval hash; the call counts against `MCP_MAX_CALLS_PER_TURN`; raw rows never reach the prompt. A still-empty or gate-failed result is an honest terminal outcome — not connector failure, not "no threat." This is the governed analog of Lantern's adapt step: **LLM intelligence in the loop, deterministic authority around it.**

---

## Final architecture review (2026-06-13)

| Existing architecture contract | Final plan alignment | Implementation consequence |
|-------------------------------|----------------------|----------------------------|
| Planner-led control plane chooses paths/branches; LLM is advisory | Early planner creates governed `ResourcePlanV2`; scheduler and reconcile remain deterministic | Do not put MCP invocation or free-form tool choice in an LLM node |
| `EvidencePlan` owns required/missing evidence keys | Step `requires_evidence_keys` / `produces_evidence_keys` drive readiness and stop decisions | MCP is called only when an unresolved evidence dependency maps to an eligible MCP capability |
| MCP evidence mapping is report-only today | Promote mapping logic into a gated runtime selector without changing its authority rules | Extend mappings by capability; do not hard-code question text or trust tool suggestions |
| Resource registry owns capabilities and availability | Concrete tool selection intersects plan capability with safe live discovery and registry policy | Unknown, blocked, mutating, SAIA, and admin tools remain ineligible |
| Candidate SPL never executes | Only search-class MCP steps consume approved `normalized_spl` | Metadata MCP may run earlier; search MCP remains blocked until validation completes |
| Multi-step correlation replaces risky subsearches | Typed bounded outputs from Search A may bind governed slots in Search B | Revalidate extracted entities, rendered SPL, scope, and approval before Search B |
| Splunk may use async jobs | Submit/poll/fetch is one logical call with separate lifecycle bounds | Connector owns polling state; planner sees normalized logical outcome |
| Planner-led LangGraph shadow is current architecture baseline | New scheduler/reconcile loop extends that architecture for adaptive dependencies | Update imperative and LangGraph paths together and rerun dual parity |
| Fail closed and preserve empty-vs-failed semantics | Explicit outcome/failover matrix and per-call SourceEvidence | No failed call can unlock evidence-dependent steps or become negative evidence |

### Implementation order

1. **O5a contract commit:** ✅ **Done** — `ResourcePlanV2`, `mcp_orchestration`, recipe registry, 15 tests.
2. **O5b scheduler commit:** ✅ **Done** — `orchestration_scheduler.py`, 9 fixture tests.
3. **O5c-core integration:** ✅ **Done** — broaden-on-empty in imperative pipeline, HIL, envelope, 10 tests.
4. **Step 1 LangGraph parity:** ❌ Next — see §Next implementation.
5. **Step 2 per-call evidence:** ❌ Next — see §Next implementation.
6. **Step 3 production adapter (async lifecycle in connector):** ❌ Next — credential drop-in layer; not a stub to rebuild later.
7. **O5d scheduler/reconcile graph:** Later — not blocking credential drop-in.
8. **O7 activation:** Config + flags after Step 3 staging smoke; no code rebuild.

### Final verdict

The plan is **ready to implement** for the three remaining steps in §Next implementation. Live MCP activation requires **configuration only** once Step 3 ships — URL, auth, `schema_confirmed=true`, execution flags. Async search lifecycle is **part of Step 3**, not a follow-on.

---

## Scope guardrails (per CLAUDE.md)

- One commit per concern; do not combine execution changes with connector-readiness or UI-only changes.
- Candidate SPL stays non-executable; only approved `normalized_spl` enters the gate.
- LLM never calls MCP directly; backend mediates.
- All MCP/LLM status output redacts secrets (`url_configured`/`auth_configured` booleans only).
- Phases B/C production enablement stay flag-gated; go-live sign-off is operator-owned (no external COE) — flip `schema_confirmed=true` after staging smoke.
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

- SPL generation audit **closed** — [`2026-06-13_spl-generation-audit-completion.md`](2026-06-13_spl-generation-audit-completion.md).
- MCP orchestration content is **Appendix A** in this file (standalone orchestration plan superseded 2026-06-13).
- `2026-06-13_o5c2-mcp-implementation-instructions.md` **superseded** — content merged into §Next implementation here (2026-06-13).
- `plan-reviewer` before non-trivial open work (B2 live, C production enablement).
- `validator` after each phase.
