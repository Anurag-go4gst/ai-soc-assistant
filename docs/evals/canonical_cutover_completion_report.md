# Canonical planning cutover — completion report (plan item 27)

**Plan:** `plans/2026-07-24_2310_guided-detail-tools-consumable-handoff.md` (rev 16+)  
**Report date:** 2026-07-26  
**Tree:** working tree at `40ea3bb` + uncommitted item **29** smoke harness and clarification-resume fix (`canonical_planning_orchestrator.py`, `pipeline.py`, `test_canonical_clarification_contract.py`)

---

## 1. Root cause + fix for clarification / sentinel failure

**Sentinel (Gate 1):** Pre-canonical routing left `match_path`, `intent_family`, and related fields `None` on the known lane because `query_to_intent` was not built. Fixed by wiring `build_query_to_intent` on the known catalogue path and typed `CanonicalPlanningOutcome` for clarification (items 12–14). **Current:** `eval_sentinel.py --check` → **17/17 PASS**.

**Clarification partial `EvidencePlan`:** `canonical_planning_orchestrator.py` previously wrote `answer_mode: clarification` dicts that failed `EvidencePlan.model_validate`. Replaced with typed `clarification_outcome` and no `evidence_plan` on non-planned paths (items 12–13).

**Live HTTP resume 500 (item 29):** Session-pin resume succeeded in Postgres but `/chat` returned 500 on turn 2 because the handoff-resume branch never set `query_to_intent`, so `graph_node_workflow_spl` called `_query_signals_from_state(state).get(...)` on `None`. **Fix:** build full `query_to_intent` via `build_query_to_intent` on resume; `_query_signals_from_state` now returns `{}` when absent. Regression: `test_clarification_resume_populates_query_to_intent`.

---

## 2. Pytest failure inventory disposition

| Phase | Failed | Disposition |
|-------|--------|-------------|
| Pre-cutover batch | 190 | Categories A–F migrated to canonical harness; Category G tracked per item 15 |
| Item 17 closure (`dcd5a3e`) | 0 | **4358 passed / 0 failed** |
| Post-persistence (`ed83452`) | 0 | **4507 passed** |
| Item 27 final (this session) | 0 | **4508 passed**, 2 skipped, 6 xfailed (pre-existing) |

**Category G:** empty at closure. Seven production parity rows resolved by item 32 shared seam (`run_canonical_planning`).

---

## 3. Final full pytest

```bash
cd backend && DATABASE_URL=postgresql://ai_soc:ai_soc_dev_password@127.0.0.1:5434/ai_soc_assistant \
  PYTHONPATH=../backend:.. python3 -m pytest -q
```

**Result:** **4508 passed**, 2 skipped, 6 xfailed (2026-07-26).

---

## 4. Final governance regression

```bash
./scripts/run_stage3_governance_regression.sh
```

**Result:** `stage3_governance_regression: PASS` (2026-07-26). Includes harness 6/6, sentinel, clean-answer **120/120**, Cisco 50/50, pipeline dispatch matrix 5/5.

---

## 5. Execution idempotency

- Contract: `canonical_execution_idempotency` table + `guard_plan_dispatch_idempotency` before executor dispatch (items 20, 24).
- In-memory default for unit tests; Postgres proof in `app/tests/integration/test_execution_idempotency_postgres.py` (**3 passed** at cutover; **4 passed** after workstream D hook replay test).
- Guided hybrid per-step idempotency wired in `guided_hybrid_executor.py`.

**Item 20 scope addendum (workstream D, 2026-07-28):** Cutover item 20 covered executor and guided-hybrid **per-step** idempotency. Workstream D closes the **P0 side-effecting execution boundary** only: MCP gate connector invoke and guided safe-catalog **execute callback**. P1/P2 read-only/advisory pipeline hooks remain outside durable per-hook replay by design. See [`per_step_hook_idempotency_audit.md`](../architecture/per_step_hook_idempotency_audit.md).

---

## 6. Database transaction + locking strategy

- **Canonical path:** `canonical_db.run_in_canonical_unit_of_work` — one asyncpg connection per turn scope; handoff writes + clarification resume under `SELECT … FOR UPDATE` (`canonical_handoff_resumption.py`).
- **SQLAlchemy:** `app/db/session.py` — app auth, quality ledger only; not used for canonical handoffs.
- **Telemetry connector:** `app/connectors/telemetry/db.py` — separate migration `0001`; diagnostic flush may degrade without blocking chat (`DiagnosticTelemetryPersistenceDegraded`).
- **Connection budget:** item-19a constant **5** connections/turn; smoke records `conn_budget_ref=5`.

---

## 7. Clarification cross-worker / resumption

- Session pins (`AI_SOC_SESSION_STORE_BACKEND=file`) carry `pending_handoff_id` / `pending_handoff_version`.
- `resolve_session_context` builds `handoff_resume` when status is `awaiting_clarification`.
- Postgres: `test_clarification_postgres.py` (**6 passed**), live smoke `t1_clarification_resume` (**20 events**, handoff v2 `plan_committed`).

---

## 8. Telemetry event coverage

Full catalog: `docs/architecture/canonical_telemetry_coverage.md`.  
Tests: `test_canonical_telemetry_coverage.py` (**31 passed**).  
Terminal events enforced: `response.validated`, `response.generated`, `request.completed` / `request.failed` on success/failure paths.

---

## 9. Response validation

`test_canonical_clarification_contract.py` — clarification carries no `evidence_plan`; `validate_final_response` passes.  
`test_canonical_planning_architecture.py` — terminal guards.  
Integration telemetry asserts correlation columns (item 21a).

---

## 10. Files + configuration removed

- `plan_dispatch_fallback`, `canonical.off` — **0 matches** in `backend/app/` (runtime).
- Legacy imperative planning path retired; single seam `run_canonical_planning`.
- `ideal_langgraph_resource_planner.md` removed from docs (git status).

---

## 11. ResourcePlan authority

`test_resource_plan_authority.py` — TEST_AUTHORITY hook for unit tests; production uses `resource_plan_authority` context. Guided dispatch cannot commit plans outside orchestrator (item 26a EC purity).

---

## 12. Postgres integration results

```bash
DATABASE_URL=postgresql://...@127.0.0.1:5434/ai_soc_assistant \
  pytest app/tests/integration/ app/tests/test_execution_idempotency.py \
  app/tests/test_canonical_telemetry_coverage.py -q
```

**68 passed, 0 skipped** (Postgres required; localhost URL for host-side runs).

---

## 13. Dead legacy / compatibility code

- `planner_led_shadow_graph` **retained** for eval-only `langgraph_dual_parity.py`; production `/chat` uses `resource_planner_graph` only (`test_dual_runtime_single_orchestration.py`).
- No runtime `plan_dispatch_fallback` or feature-flag canonical toggle.

---

## 14. Final runtime diagram

```text
/chat → run_chat_via_resource_planner_graph
      → understand_query → run_canonical_planning (shared seam)
      → lane_router / completeness / guided_resolution
      → plan_evidence_from_canonical → evidence_plan + ResourcePlan
      → workflow_spl / MCP gates (candidate-only) → response assembly
      ↔ PostgreSQL: canonical_handoffs, canonical_planning_events,
                    canonical_execution_idempotency (deploy migrations 0003–0006)
```

---

## 15. Remaining gaps

**Reconciled 2026-07-28:** see [`canonical_cutover_gap_reconciliation.md`](canonical_cutover_gap_reconciliation.md). Post-cutover hardening (workstreams A+B) closed gap 2 below.

| Gap | Severity | Status | Notes |
|-----|----------|--------|-------|
| `test_dual_runtime_behavioural_parity.py` | Medium | **Resolved (2026-07-28)** | Absent at cutover closure; added in outcome-invariant hardening (`test_dual_runtime_behavioural_parity.py`, 9 scenarios). Original Gate 3.4 **78 passed** and parity **120/0/0** evidence unchanged |
| Hook-level SPL/MCP step idempotency | Low (Medium/High before live MCP execution) | **Resolved (2026-07-28)** | Workstream D — **P0 side-effecting** MCP connector + guided safe-catalog execute only; P1/P2 read-only hooks deferred (see gap reconciliation §Gap 1) |
| LLM synthesis latency in smoke | Medium | **open** | Deferred to workstream E |
| Production migration operator attestation | Low | **evidence-pending** | Workstream C — independent of A+B |

---

## Post-cutover hardening (2026-07-28, workstreams A+B)

- Shared `enforce_canonical_outcome_invariant` gate after lane planning in `run_canonical_planning`
- Tri-state `read_canonical_planning_outcome` at dispatch/validation consumers (P1–P6)
- Pure `build_typed_planning_failure_state`; `request.failed` from gate only
- `test_dual_runtime_behavioural_parity.py` (9 scenarios, imperative vs RP bootstrap)
- Negative controls: stale EP without outcome fails closed (`non_planned_finalize`, not `workflow_spl`)

## Post-cutover hardening (2026-07-28, workstream D — P0 hook idempotency)

- Hook side-effect audit: [`per_step_hook_idempotency_audit.md`](../architecture/per_step_hook_idempotency_audit.md) (22 hooks classified; P0/P1/P2)
- **P0 resolved:** MCP gate connector dispatch + guided `safe_catalog_query` execute callback (identity required before callback)
- **P1/P2 accepted/deferred:** read-only/advisory hooks — no external duplicate side-effect risk addressed by durable replay
- Typed `HookReplayEnvelope` stored in existing `canonical_execution_idempotency.result` JSONB (no migration)
- `REQUIRES_RECONCILIATION` on stale lease, fingerprint mismatch, or missing execute identity

---

## 16. Migration deployment

| Environment | Migrations | Verified |
|-------------|------------|----------|
| Dev Docker Postgres (`127.0.0.1:5434`) | 0001–0006 via `entrypoint.sh` / `migrate_ai_soc_db.py` | `/health` readiness + smoke `schema_migrations` check |
| VPS prod | 0001–0006 via existing entrypoint contract (no new migration in PR #112) | **Technically verified 2026-07-28:** merge `7ce1474`; `/health` `database_migrations.ready=true`, `missing_versions=[]`; backend `RestartCount=0`. **Operator attestation:** name/role **evidence-pending** (see gap reconciliation §C). |

No runtime DDL in canonical handoff repository (`rg` clean).

---

## 17. Data-layer boundary

| Layer | Technology | Scope |
|-------|------------|-------|
| Canonical UoW | asyncpg | Handoffs, planning events, idempotency |
| App ORM | SQLAlchemy | Sessions, quality ledger |
| Telemetry sink | asyncpg (optional) | `ai_trace_runs` / diagnostic |

Measured: ≤5 connections/turn (item 19a); smoke annotates `conn_budget_ref=5`.

---

## 18. Audit-critical vs diagnostic telemetry

| Class | Count | On failure |
|-------|-------|------------|
| Audit-critical | 8 | Fail-closed when DB configured and write fails |
| Diagnostic | 20+ | Degrade with warning; chat continues |

Policy: `test_telemetry_persistence_policy.py`. Sink: `TELEMETRY_MODE` / `AI_SOC_TELEMETRY_SINK`.

---

## 19. Experience Center purity

`test_experience_center_canonical_purity.py` — EC path emits **zero** canonical planning events / handoffs / plan commits. Fixture keys migrated per item 26a.

---

## 20. Retention / purge

`canonical_retention.py` + scheduler (item 28): handoff grace 24h, diagnostic 7d, audit 90d.  
`test_canonical_retention_purge.py` — **14 passed** (integration).

---

## 21. Rollback posture

- **Revert:** `git revert` of cutover commit(s); no feature flags to disable.
- **Migrations 0004/0005/0006:** additive, forward-only; no down-migration required for revert.

---

## 22. Pytest inventory (rev 10)

At item 17 closure: all failures classified A–G; **Category G = 0** at production parity baseline. Final suite: **4508 passed**, 0 failed.

---

## 23. Dual-runtime parity (authoritative)

```bash
PYTHONPATH=backend:. python3 scripts/run_langgraph_dual_parity_eval.py --check
```

**Result:** `total=120 exact=120 approved=0 critical=0`  
**Metadata:** `runtime_a=imperative_canonical`, `runtime_b=resource_planner_graph`, `base_105_loaded=105`, commit `40ea3bb` (artifact timestamp 2026-07-26T13:44Z).  
**Projection tests:** `test_dual_runtime_parity_projection.py` **40 passed**.  
No `approved_difference` rows — six-part field records **N/A**.

---

## 24. Baseline / fixture changes

| Artifact | Old → New | Contract |
|----------|-----------|----------|
| Sentinel `answer_mode` (3 rows) | `clarification` → `null` | Clarification has no `EvidencePlan`; `contract_answer_mode` still pins behaviour |
| Production parity | 113 exact / 7 critical → **120/0/0** | Shared `run_canonical_planning` seam; Category G fixes |
| Clean-answer eval | 12 critical (partial EvidencePlan) → **120/120** | Typed outcomes (items 12–13) |

All regenerations via artifact-safe writer (`9c65106`); governance regression `--check` refuses partial corpus.

---

## Gate summary (item 27 checklist)

| Gate | Command | Result |
|------|---------|--------|
| 1 | clarification arch tests + `eval_sentinel.py --check` | **27 passed**, **17/17** |
| 2 | `test_canonical_*` + authority + lane parity | **68 passed** |
| 3 | integration + idempotency + telemetry | **68 passed**, **0 skipped** |
| 3.4 | `run_langgraph_dual_parity_eval.py --check` + projection suite | **120/0/0**, **78 passed** |
| 3.5 | `scripts/smoke_canonical_paths.sh` | **6/6** (2026-07-26) |
| 4 | full `pytest -q` | **4508 passed** |
| 5 | `run_stage3_governance_regression.sh` | **PASS** |
| 6 | `rg plan_dispatch_fallback\|canonical.off` | **0 matches** |
| 7 | no runtime DDL + EC purity + retention | **rg** clean; **14** retention passed |
