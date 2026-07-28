# Canonical cutover gap reconciliation matrix

**Date:** 2026-07-28
**Scope:** Plan and documentation only. Does **not** reopen [`plans/2026-07-24_2310_guided-detail-tools-consumable-handoff.md`](../plans/2026-07-24_2310_guided-detail-tools-consumable-handoff.md) (41/41 complete). Historical addenda live here and in the completion report §15 addendum.

**Workstream dependency order (mandatory):**

```text
A → B → C → D → E
```

| ID | Workstream |
|----|------------|
| **A** | [Canonical Outcome Invariant Hardening](../plans/2026-07-28_1610_canonical-outcome-invariant-hardening.md) |
| **B** | Behavioural parity file + documentation correction (C6/C7 of A) |
| **C** | Migration evidence closeout (documentation only) |
| **D** | [Per-Step Dispatch Idempotency and Uncertain-Execution Safety](../plans/2026-07-28_1630_per-step-dispatch-idempotency-and-uncertain-execution-safety.md) |
| **E** | [Live Synthesis Performance Baseline and SLO](../plans/2026-07-28_1630_live-synthesis-performance-baseline-and-slo.md) |

---

## Umbrella follow-up matrix

| Gap | Current factual status | Severity | Blocking | Owner / approval | Target plan | Target PR type | Acceptance evidence | Status |
|-----|------------------------|----------|----------|------------------|-------------|----------------|---------------------|--------|
| **1. Per-step SPL/MCP hook idempotency** | Item 20 covers executor + guided-hybrid per-step idempotency (`canonical_execution_idempotency.py`, 9 unit tests). **Hook-level** SPL/MCP pipeline nodes (`graph_node_workflow_spl`, MCP discovery/search hops) are **not** individually wrapped — cutover drift note item 20 scope (rev 17). | Low (correctness of cross-process replay at hook boundary) | **Not blocking A** | COE / platform owner before D implementation | [`plans/2026-07-28_1630_per-step-dispatch-idempotency-and-uncertain-execution-safety.md`](../plans/2026-07-28_1630_per-step-dispatch-idempotency-and-uncertain-execution-safety.md) | Separate feature PR after A+B+C | Hook side-effect audit doc; typed allowlisted replay payloads; lease + fingerprint tests; concurrent-worker race proof; `REQUIRES_RECONCILIATION` when exactly-once unprovable; governance regression PASS | **open** |
| **2. Missing `test_dual_runtime_behavioural_parity.py`** | File **shipped** in PR #112 (`backend/app/tests/test_dual_runtime_behavioural_parity.py`, 9 scenarios). Cutover item 34 historical substitution preserved in §Gap 2 below. | Medium (test-honesty / seam regression) | — | Engineering | [`plans/2026-07-28_1610_canonical-outcome-invariant-hardening.md`](../plans/2026-07-28_1610_canonical-outcome-invariant-hardening.md) | Merged PR #112 | 9/9 behavioural parity; negative controls 8/8; production parity **120/0/0** unchanged | **resolved (2026-07-28)** |
| **3. Production migration operator sign-off** | **Technically verified:** migrations `0001`–`0006` applied via `entrypoint.sh` / `migrate_ai_soc_db.py`; `/health` `readiness.database_migrations.ready=true`, `missing_versions=[]`; merged production checkout at cutover SHA; integration suite `34 passed / 0 skipped` on dev Postgres; no runtime DDL in handoff repository. **Formally missing:** named operator attestation (name, role, date) and a **linked** production `/health` capture or deploy log entry in the completion report. | Low (ops audit trail) | **Not blocking A** | Operator / COE signatory for closeout row | This doc §C + completion report §16 addendum | **Docs-only** PR (no migration rerun) | Completion report table row: prod env, apply date, operator name/role, link to redacted `/health` JSON or internal deploy ticket; `missing_versions=[]` quoted | **evidence-pending** |
| **4. Live-synthesis latency in smoke** | Observed **90–240 s/turn** when live synthesis enabled on VPS smoke; not a correctness defect. No baseline p50/p90/p95, no cold/warm split, no timeout/fallback rate, no endpoint-vs-app timing breakdown. SLO targets **not** declared (correct). | Medium (ops / analyst UX) | **Not blocking A–C** | COE for any future SLO; perf owner for E | [`plans/2026-07-28_1630_live-synthesis-performance-baseline-and-slo.md`](../plans/2026-07-28_1630_live-synthesis-performance-baseline-and-slo.md) | Phase 1: instrumentation docs PR; Phase 2: optimization PR after baseline | Sanitized benchmark artifact; cold/warm p50/p90/p95; timeout + fallback rates; synthesis-path timing breakdown; live probes **outside CI** | **open** |

---

## Gap 3 — evidence-only closeout (workstream C)

**Do not** rerun or modify migrations.

### Already verified (factual)

| Check | Evidence source |
|-------|-----------------|
| Migrations `0001`–`0006` defined and idempotent | `backend/app/db/migration_readiness.py`, `scripts/migrate_ai_soc_db.py` |
| Dev apply + double-run no-op | Cutover item 19 evidence; `test_migration_readiness.py` **5 passed** |
| Integration harness through `0006` | `test_required_migrations_include_0006_retention_indexes`, integration **34 passed / 0 skipped** |
| Production readiness contract | `/health` → `readiness.database_migrations` with `ready`, `missing_versions`, `applied_versions` |
| No runtime DDL in repository layer | `rg` clean on `canonical_handoff_repository.py` (cutover item 19) |

### Still missing (documentation only)

1. **Operator name and role** — **evidence-pending** (requires named COE/platform signatory).
2. **Apply date** — **recorded:** 2026-07-28 UTC (PR #112 production deploy; merge SHA `7ce14748219e0943b6623dec85309241a4ac24fb`).
3. **Evidence link** — **recorded:** production `/health` post-deploy (`database_migrations.ready=true`, `missing_versions=[]`, versions `0001`–`0006` present). Redacted capture path: internal deploy record PR #112 closeout.

### Closeout checklist (documentation PR)

- [x] **C-MIG-1** — Update [`canonical_cutover_completion_report.md`](canonical_cutover_completion_report.md) §16 prod row with deploy SHA + health evidence (operator name pending).
- [x] **C-MIG-2** — Add §15 addendum cross-reference (this file).
- [x] **C-MIG-3** — No code or migration file changes in the closeout PR.

---

## Gap 2 — historical honesty (workstream B)

**Supersedes** the item 34 substitution narrative (“covered by `test_dual_runtime_lane_parity.py` + projection suite”).

| Fact | Treatment |
|------|-----------|
| Cutover checklist **41/41** | **Unchanged** — closure valid on evidence available at rev 17 |
| Gate 3.4 **120/0/0** and **78 passed** | **Preserved** — authoritative parity unchanged |
| Item 34 filename | Was **not** shipped; **added** in post-cutover hardening (workstream A/B) |
| Substitute tests | Remain valuable; they do **not** replace the dedicated behavioural parity module |

---

## Contradictions resolved (old gap record vs new audit)

| # | Old record | New disposition |
|---|------------|-----------------|
| 1 | Completion report §15: behavioural gap severity **Doc**, “covered by” substitutes | **Superseded** — gap is **open** until file lands; substitutes retained as complementary |
| 2 | Cutover item 34 **Evidence** claims behavioural parity via substitute suite | **Historical addendum** — item stays `[x]`; evidence footnote points here |
| 3 | Gate 3.4 command lists `test_dual_runtime_behavioural_parity.py` | **Acknowledged** — gate passed without file; hardening C6 adds file; Gate 3.4 wording updated in hardening R8 note only |
| 4 | Hardening L3 defers executor/idempotency vs cutover “item 20 done” | **Not a contradiction** — plan-level idempotency done; **hook-level** gap is gap 1 → plan D |
| 5 | Completion report §16 “operator sign-off pending” vs technical verify | **Reconciled** — status **evidence-pending** (attestation only), not “migrations unapplied” |

---

## Pointers

- Outcome hardening: [`plans/2026-07-28_1610_canonical-outcome-invariant-hardening.md`](../plans/2026-07-28_1610_canonical-outcome-invariant-hardening.md)
- Hook idempotency follow-up: [`plans/2026-07-28_1630_per-step-dispatch-idempotency-and-uncertain-execution-safety.md`](../plans/2026-07-28_1630_per-step-dispatch-idempotency-and-uncertain-execution-safety.md)
- Live synthesis perf: [`plans/2026-07-28_1630_live-synthesis-performance-baseline-and-slo.md`](../plans/2026-07-28_1630_live-synthesis-performance-baseline-and-slo.md)
- Cutover completion report: [`canonical_cutover_completion_report.md`](canonical_cutover_completion_report.md)
