# Per-step hook idempotency audit (Workstream D — Item I0)

**Date:** 2026-07-28
**Scope:** read-only static call-site inspection; no implementation, no live MCP, no full pytest
**Canonical baseline:** `07438d78` (PR #114) on `master`
**Related plan:** [`plans/2026-07-28_1630_per-step-dispatch-idempotency-and-uncertain-execution-safety.md`](../../plans/2026-07-28_1630_per-step-dispatch-idempotency-and-uncertain-execution-safety.md)

## Executive summary

Cutover item 20 (`canonical_execution_idempotency.py`) covers **ResourcePlan step execution** inside `execute_plan_dispatch` (guard) and **guided hybrid collection** (`mcp_discovery`, `safe_catalog_query`). It does **not** wrap the imperative/RP **stage hooks** (`workflow_spl`, `graph_node_execution`, pre-SPL discovery) as first-class idempotent operations.

| Priority | Count | Boundary |
|----------|------:|----------|
| **P0** | 3 | MCP search execution, uncertain side-effecting MCP tools, guided safe-catalog SPL when execution flags allow invoke |
| **P1** | 6 | Executor dispatch envelope, pre-SPL discovery live path, SPL source-resolve HIL side effects, durable telemetry at hooks |
| **P2** | 12 | Read-only / candidate-only hooks (RAG, validation, governance surfaces) — document exclusions |

**Verdict:** I0 complete. Workstream D is **READY FOR IMPLEMENTATION** starting at I1 (typed replay contract), subject to Workstream C operator attestation (name/role only).

---

## Design rules (locked for D)

1. No arbitrary state-delta persistence — replay payloads are typed and allowlisted.
2. No credentials, connector objects, or transient telemetry in replay records.
3. Database leases alone do not prove exactly-once external execution.
4. Uncertain external results must not be automatically retried (`REQUIRES_RECONCILIATION`).
5. Live MCP execution remains default-off; audit classifies **possible** side effects when flags are on.

---

## Inventory

### A. Planner executor dispatch schedule (`execute_plan_dispatch`)

**Caller:** `backend/app/planner/executor.py::execute_plan_dispatch`
**Reachability:** Imperative `/chat` pipeline when `plan_dispatch` runs (`pipeline.py` ~620, 2230); RP `rp_node_composed_dispatch` → same hooks.
**Outer coverage:** `guard_plan_dispatch_idempotency` before schedule (in-progress / uncertain step inspection only).
**Step identity:** ResourcePlan `step_id` + `plan_step_operation_identity(step)` when plan walk applies; legacy schedule uses stage names not step IDs.

| Hook | File:line | Side-effect class | Retry / idempotency | Outer coverage | Per-hook coverage | Durable writes | External I/O | Downstream key | Crash / timeout | Replay fields (allowlist) | Never persist | RECON? | Pri |
|------|-----------|-------------------|---------------------|----------------|-------------------|----------------|--------------|----------------|-----------------|---------------------------|---------------|--------|-----|
| `prepare_rag_only` | `pipeline.py:3078` | Read-only (workflow + skipped execution) | Retryable | None | None | In-memory state only | No | N/A | Re-run safe | `handoff_id`, `handoff_version`, `resource_plan_id`, `stage=prepare_rag_only` | credentials, connector handles | No | P2 |
| `rag_early` | `pipeline.py:3141` | Read-only (RAG retrieve) | Retryable | None | None | `soc_kb_retrieval`, `source_evidence`; diagnostic telemetry | RAG connector read | N/A | Re-run may duplicate telemetry rows | `stage`, `query_hash`, `trace_id` | raw chunks secrets | No | P2 |
| `workflow_spl` | `pipeline.py:2720` | Read-only (candidate SPL only; never executable) | Retryable | None | None | `candidate_spl`, `spl_validation` (approved=false for lab) | Optional LLM advisory | N/A | Safe to re-run | `stage`, `template_id`, `intent_family` | LLM prompts, secrets | No | P2 |
| `spl_postprocessor` | `pipeline.py:2485` | Read-only | Retryable | None | None | SPL metadata | No | N/A | Safe | `stage`, `candidate_spl_hash` | — | No | P2 |
| `spl_source_resolve` | `pipeline.py:3199` | Read-only + **HIL persistence** (session pins) | Retryable; HIL write idempotent by session | None | None | Session pin updates, `human_review` | No external MCP | N/A | Partial pin write on crash → clarify on resume | `stage`, `slot_fingerprint`, `session_id` | credentials | No | P1 |
| `ensure_workflow_plan` | `pipeline.py:2389` | Read-only | Retryable | None | None | `workflow_plan` | No | N/A | Safe | `stage`, `skill` | — | No | P2 |
| `reference_finalize` | `pipeline.py:9598` | Read-only | Retryable | None | None | `reference_resolution` | Registry HTTP read | N/A | Safe | `stage`, `reference_ids` | — | No | P2 |
| `execution` | `pipeline.py:2877` | **Side-effecting** when gate approves | **Uncertain** without hook wrapper | `guard_plan_dispatch_idempotency` (plan-level) | **None at hook** | `execution`, `human_review`, MCP result envelope | **Splunk MCP `splunk_run_query`** when flags+credentials on | Partial (`downstream_idempotency_key` in step runner only) | Running lease / timeout → uncertain | `resource_plan_id`, `step_id`, `operation`, `handoff_id`, `handoff_version`, `normalized_spl_hash`, `tool_name`, `time_bounds` | tokens, connector, raw rows | **Yes** when uncertain | **P0** |

### B. Legacy predicate dispatch fallback

**Caller:** `executor.py::_legacy_predicate_dispatch_schedule` (when no v2 schedule / no plan walk).
**Reachability:** Same hooks as §A; schedule derived from `uses_rag_only_path`, `uses_pre_mcp_rag`, blocked steps.
**Note:** Identical hook rows — no separate wrappers. Idempotency gap is **schedule-level**, not predicate-level.

### C. RP graph dispatch wrappers

**Caller:** `resource_planner_graph.py` compiled LangGraph.
**Reachability:** Production `/chat` when RP hierarchy enabled (`run_chat_via_resource_planner_graph`).

| RP node | Delegates to | Route gate | Notes | Pri |
|---------|--------------|------------|-------|-----|
| `rp_node_composed_dispatch` | `graph_node_composed_dispatch` → `execute_plan_dispatch` | `composed_dispatch` when outcome `planned` | Inherits §A + guard | P0 via `execution` |
| `rp_node_prepare_rag_only` | `graph_node_prepare_rag_only` | `rag_only` | Skips composed executor | P2 |
| `rp_node_rag_early` | `graph_node_rag_early` | after rag_only / workflow_spl | | P2 |
| `rp_node_workflow_spl` | `graph_node_workflow_spl` | `workflow_spl` | | P2 |
| `rp_node_spl_source_resolve` | `graph_node_spl_source_resolve` | post-SPL | | P1 |
| `rp_node_non_planned_finalize` | `build_non_planned_dispatch_state` | `non_planned_finalize` | No dispatch hooks; finalize only | P2 |
| `rp_node_spl_validate` | local gate | governance chain | Forces `execution_eligible=false` if not approved | P2 |
| `rp_node_mcp_execution_gate` | `graph_node_execution` if missing | governance chain | **Same as `execution` hook** | **P0** |

**Governance chain nodes** (post-dispatch, production-reachable on SPL/MCP paths):

| Node | File:line | Side-effect | Coverage | Pri |
|------|-----------|-------------|----------|-----|
| `context_sufficiency` | `resource_planner_graph.py:600` | Read-only | None | P2 |
| `decide_facts` | `resource_planner_graph.py:615` | Read-only | None | P2 |
| `answer_guard` | `resource_planner_graph.py:674` | Read-only (dormant rules) | None | P2 |
| `human_review` | `resource_planner_graph.py:739` | Read-only surface | None | P2 |
| `policy_veto` | `resource_planner_graph.py:755` | Read-only | None | P2 |
| `finalize` | `resource_planner_graph.py:686` | Read-only (+ response compose) | None | P2 |
| `validate_final_answer` | `resource_planner_graph.py:709` | Read-only | None | P2 |

### D. Guided hybrid execution

**Caller:** `pipeline.py::_run_guided_hybrid_dispatch` (flag `ai_soc_guided_hybrid_investigation_enabled`, default false).
**Reachability:** Guided investigation with committed ResourcePlan.

| Unit | File:line | Side-effect | Idempotency today | External I/O | RECON? | Pri |
|------|-----------|-------------|-------------------|--------------|--------|-----|
| `load_committed_guided_resource_plan` | `guided_hybrid_executor.py:20` | Read-only validation | N/A | No | No | P2 |
| `collect_guided_hybrid_evidence` | `guided_hybrid_collection.py:110` | Mixed | **`run_idempotent_execution_step` per step** | MCP discovery + safe catalog SPL | Yes on uncertain contract | **P0** (safe catalog execute path) |
| `_run_mcp_discovery_step` | `guided_hybrid_collection.py:40` | Read-only default; live when flags on | Wrapped in idempotent step | `execute_loop_discovery_hop` | Yes if live + uncertain | P1 |
| `_run_safe_catalog_step` | `guided_hybrid_collection.py:66` | **Side-effecting** when `execute_safe_catalog_spl` runs | Wrapped in idempotent step | Mock/live SPL search | Yes | **P0** |

### E. SPL generation / validation / source resolution (sub-operations)

| Operation | Location | Executable? | Hook wrapper | Pri |
|-----------|----------|-------------|--------------|-----|
| Template SPL generation | `workflow_spl` internals | No (candidate only) | None | P2 |
| LLM plan compiler | `llm_plan_compiler.py` | No | None | P2 |
| `validate_spl` / lab candidate | `safeguards/spl_validator.py` | No | None | P2 |
| Slot resolution | `graph_node_spl_source_resolve` | No | None | P1 (session writes) |
| RP `spl_validate` node | `resource_planner_graph.py:584` | No | None | P2 |

### F. MCP execution gate and connector boundary

| Layer | File:line | Role | Idempotency | Pri |
|-------|-----------|------|-------------|-----|
| `evaluate_mcp_execution` | `mcp_execution_gate.py:44` | Policy + confirmation gate | None | **P0** |
| `_execution_stage` | `pipeline.py` (via `graph_node_execution`) | Selects tool, calls gate | None | **P0** |
| `splunk_search_lifecycle` | `splunk_search_lifecycle.py` | submit → poll → fetch | No hook-level lease | **P0** |
| `get_mcp_connector().call_tool` | `connectors/mcp/` | External invoke | No stable downstream key propagated from gate | **P0** |

**Crash / timeout FSM (current, pre-D):**

```text
[no record] → execute → running (lease) → completed | failed_* | execution_uncertain
                ↓ crash mid-flight
            stale running + side_effecting_without_stable_idempotency
                → guard_plan_dispatch_idempotency → REQUIRES_RECONCILIATION (state only)
```

Hook-level D work must align gate + connector with the same FSM and persisted replay blob.

### G. Discovery / pre-SPL MCP paths

| Path | File:line | Live when | Side-effect | Coverage | Pri |
|------|-----------|-----------|-------------|----------|-----|
| `graph_node_pre_spl_mcp_discovery` | `pipeline.py:2635` | `ai_soc_pipeline_dispatch_v2_enabled` + discovery flag | Read-only MCP metadata | None | P1 |
| `run_mcp_source_discovery` | `spl/mcp_source_discovery.py` | discovery + global execution | Read-only | None | P1 |
| `execute_loop_discovery_hop` | `spl/mcp_loop_discovery.py:22` | discovery + **`mcp_global_execution_enabled`** | Read-only tools; still external | None at hook | P1 |
| Guided `mcp_discovery` steps | `guided_hybrid_collection.py` | hybrid flag | Same hop | Step idempotency wrapper | P1 |

---

## Recommended P0 implementation scope (I1–I2)

1. **`execution` / `graph_node_execution` hook wrapper** — single idempotent boundary around `evaluate_mcp_execution` + connector invoke; fingerprint = hash(`normalized_spl`, `tool_name`, `earliest`, `latest`, `resource_plan_id`, `step_id`).
2. **Propagate `downstream_idempotency_key`** into Splunk MCP transport when contract is `side_effecting_with_stable_idempotency` (vendor support TBD — until verified, stay `without_stable_idempotency` + RECON).
3. **Guided `safe_catalog_query` execute callback** — reuse same wrapper; never auto-retry uncertain rows.
4. **Typed replay envelope (I1)** — see plan addendum below; reject arbitrary dict patches in unit tests.

**Explicitly out of P0:** RAG retrieval, SPL candidate generation, governance-only nodes, `no_human_review()` labelling.

---

## Typed replay schema proposal (I1)

```python
class HookReplayEnvelope(BaseModel):
    contract_version: Literal["2026-07-28"] = "2026-07-28"
    hook_name: Literal[
        "execution", "mcp_discovery_hop", "safe_catalog_execute", "pre_spl_discovery"
    ]
    resource_plan_id: str
    handoff_id: str | None
    handoff_version: int | None
    step_id: str | None
    operation_identity: str
    input_fingerprint: str  # sha256 of allowlisted fields
    downstream_idempotency_key: str | None = None
    terminal_status: ExecutionStepStatus | None = None
    result_summary: dict[str, Any] = Field(default_factory=dict)  # minimized, no rows
```

**Allowlisted fingerprint inputs:** `normalized_spl`, `selected_mcp_tool`, `earliest`, `latest`, `execution_intent`, `template_id` (guided SPL only).

**Never persist:** bearer tokens, `get_mcp_connector()` instances, full result rows, LLM prompts, session cookies.

---

## Identity / fingerprint proposal

| Layer | Key |
|-------|-----|
| Plan step (existing) | `build_idempotency_key(resource_plan_id, handoff_id, handoff_version, step_id, operation)` |
| Hook operation | `plan_step_operation_identity(step)` or `hook_name:stage` for non-plan legacy |
| Input fingerprint | `sha256(json.dumps(allowlisted_fields, sort_keys=True))` |
| Downstream | `canonical-op:{sha256(canonical_identity)}` (existing) |

---

## Minimum implementation tests (I2–I3)

| Test | Command |
|------|---------|
| Replay envelope validation | `pytest backend/app/tests/test_per_step_hook_idempotency.py -q` (new) |
| Guard + hook wrapper parity | `pytest backend/app/tests/test_execution_idempotency.py -q` (extend) |
| Postgres two-worker race | `pytest backend/app/tests/integration/test_execution_idempotency_postgres.py -q` (extend, disposable port) |

**I0 verification:** static inventory (this document) + existing reachability:

```bash
pytest backend/app/tests/test_resource_plan_authority.py::test_guided_hybrid_and_telemetry_never_mutate_committed_plan -q
```

---

## Estimated commit sequence

1. `feat(idempotency): typed HookReplayEnvelope + validation tests` (I1)
2. `feat(idempotency): wrap graph_node_execution / MCP gate invoke` (I2 P0)
3. `feat(idempotency): align guided safe-catalog with shared wrapper` (I2)
4. `test(idempotency): postgres concurrent worker + stale lease` (I3)
5. `feat(idempotency): REQUIRES_RECONCILIATION analyst surfacing` (I4)
6. `docs: close gap row 1 hook-level idempotency` (I5)

---

## Exclusions (COE read-only sign-off candidates)

Hooks with **no external side effect** under default flags and **no durable write** beyond diagnostic telemetry may remain outside lease wrappers after explicit exclusion row in gap matrix: `rag_early`, `workflow_spl`, `spl_validate`, governance chain nodes, `reference_finalize`.

---

## P0 execution invariants (implemented)

| Invariant | Enforcement |
|-----------|-------------|
| Guided safe-catalog execute callback | `collect_guided_hybrid_evidence`: when `dispatch_plan.ready` and `execute_safe_catalog_spl` is set, requires `resource_plan_id` + `step_id`; otherwise blocks with `guided_safe_catalog_idempotency_identity_missing` and `REQUIRES_RECONCILIATION` — **callback never invoked** |
| MCP connector via `graph_node_execution` | `resolve_hook_idempotency_context` + `_dispatch_connector_execution` wrap side-effecting connector calls when context present (production path always passes `trace_id` minimum) |
| Fingerprint replay | `stored_envelope_matches` — mismatch → `REQUIRES_RECONCILIATION`, never silent replay |
| Uncertain downstream | `side_effecting_without_stable_idempotency` contract → stale lease / uncertain → manual reconciliation; no automatic retry |
| JSONB compatibility | `HookReplayEnvelope` + sanitized summary in existing `canonical_execution_idempotency.result`; non-hook records unchanged |

Regression: `test_safe_catalog_execute_blocked_without_resource_plan_id`, `test_mcp_discovery_without_resource_plan_id_remains_read_only`.

---

## I0 evidence

- Inventory: this file (§Inventory).
- Reachability: `test_resource_plan_authority.py` guided hybrid guard + grep of `execute_plan_dispatch`, `run_chat_via_resource_planner_graph`, `_run_guided_hybrid_dispatch`.
- No production code changes in I0.
