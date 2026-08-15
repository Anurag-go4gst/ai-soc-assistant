# Plan 7 E2 — `P7_PRODUCTION_GO_LIVE_V2` decision record

Branch: `feat/plan7-resource-plan-authority-t4` @ `f91c372`

Architecture freeze: `a8f02e3` (`architecture.md` unmodified by Plan 7 E2)

This is a **decision record only**. No engineering, no re-measurement, no flag change, no test
run was performed for E2. Every number below is cited from committed Plan 7 evidence; nothing was
re-derived, and no verdict was softened to reach an outcome.

## Recorded decision (user)

| Field | Value |
|---|---|
| `PLAN7_IMPLEMENTATION` | **COMPLETE** |
| `RESOURCEPLAN_AUTHORITY` | **APPROVED** |
| `PRODUCTION_GO_LIVE` | **DEFERRED / NO-GO** |
| `REASON` | unresolved critical T4 serving stability blocker |
| `PLAN8_MAY_START_AFTER_PLAN7_CLOSURE` | **YES** |

The intended architecture — `ResourcePlan + PhaseContract` as the sole normal execution
authority, with dispatch-v2 retired to rollback/test-only — is **approved and implemented**.
Production go-live is **not** declared. This is a deferral on serving stability, not a rejection
of the architecture and not a rollback.

**F3 is NOT recorded as an accepted risk.** It stays a CRITICAL BLOCKER. **No production-ready
claim is made anywhere in this record.**

## E2 matrix

Allowed verdicts: PASS / BLOCKER / ACCEPTED RISK / NOT IN PRODUCTION SCOPE ⋅ UNPROVEN.

| Dimension | Verdict | Basis (committed evidence) |
|---|---|---|
| Functional | **PASS** | E1 11/11; pytest `5335 passed / 0 failed`; parity `exact=120 approved=0 critical=0`; Cisco `50/0/0`; path `105/105` — `e1_closure_gates.md` |
| Safety | **PASS** | `execution_eligible` null on every corpus row; candidate SPL never executable; MCP-down → `requires_human_review`; unsafe `12/12` contained; `side_effect_totals.allowed: 0` — `runs/…/d1_reliability.md`, `d0` corpus |
| Performance | **PASS — scoped** | Deterministic orchestration p50 **853 ms** / p95 **993 ms** with a recorded T4 proposal. Live-model latency is deliberately **not** claimed here; it sits under T4 serving posture — `d1_reliability.md` |
| Reliability | **PASS** | All ten mandatory D1 failure classes measured; bounded, deterministic degradation; failure taxonomy distinguishes `timeout` / `provider_unavailable` / `pool_rejected` / `slot_busy`; no duplicate side effect observed — `d1_reliability.md` |
| Security / RBAC | **PASS** | HIL/RBAC authority retained at the MCP gate; per-call SPL execution confirmation unchanged; no secret value in any evidence artifact — E1 invariant review 7/7 |
| Observability | **UNPROVEN** | **F1**: DB loss degrades authority to `canonical_non_planned` while still answering, with no analyst-visible degrade signal. **F2**: `/v1/models` returns 200 through an unusable model. Both carried as **Plan 8 dependencies**, neither accepted as a risk here — `d1_reliability.md` |
| Deployment / restart persistence | **PASS** | D2 recreate; D3 both directions; `.env` byte-identical, non-secret flag-block hash `9613fc2cea1e4c77` before and after — `d2_persistence.md`, `d3_rollback.md` |
| Configuration rebuild resilience | **PASS — development profile only** | `CONFIG_REBUILD_DRIFT` **CLOSED** for development by `6ecf6c4`; the tracked profile plus unchanged repo defaults reconstructs all six target values. **COE/production profiles remain unproven** — `rollback_runbook.md` |
| Rollback | **PASS** | D3 drill executed in both directions with no Cisco restart (single PID, unbroken uptime); runbook separates runtime-feature rollback from orchestration code/release rollback — `d3_rollback.md`, `rollback_runbook.md` |
| Corpus | **PASS** | D0 target corpus; routing truth set **0 regressions** (64/76; live arm 59/76; capability downgrades 0) — `d0`, `e1_closure_gates.md` |
| Production flags | **PASS** | Six target flags exact and re-verified after two container recreates — `d2_persistence.md`, `d3_rollback.md` |
| **ResourcePlan production authority** | **PASS** | `merge_active` on the ResourcePlan seam rows; A3 `spl_postprocessor` contract-inserted on **every** seam row; **`V2_WINS` = 0**; `degrade_reason` null — `a4_authority_acceptance.md`, `d2`/`d3` smokes |
| T4 semantic capability | **PASS** | C3 classification separates capability from serving: `T4_SEMANTICALLY_VIABLE_…` — `c3_stop_decision_packet.md`, `c3_remediation_evidence.md` |
| **T4 serving posture** | **BLOCKER** | `…_BUT_VPS_SERVING_BLOCKER` (**F3**). E2's own GO condition (2) — "C3 approved a **viable** serving posture" — is **unmet**. POST-C3 acceptance 2/9 then 1/4 at 78.3 / 111.7 / 115.1 s, with host swap-thrash driving variance (>360 s while thrashing, 83.4 s immediately after a model restart) |
| Execution seam posture | **PASS** | dispatch-v2 retired and fenced — with ResourcePlan execution ON, v2 cannot win even if its flag is enabled. **A7 proven**: `LEGACY_FALLBACK_ROLLBACK_ONLY_RETAIN_TEMPORARILY`; the target graph cannot enter the legacy fallback and the rollback path fails closed — `a7_fallback_lifecycle_proof.md` |
| MITRE governance | **NOT IN PRODUCTION SCOPE** | Promotion **DEFERRED**; the 11-row DRAFT drift ledger is unchanged and still audited |
| **Live MCP / Splunk scope** | **UNPROVEN** | `live_mcp_unproven`. `MCP_MODE=mock` throughout; mock MCP success is **not** live Splunk readiness. **Live Splunk/MCP remains outside proven production scope.** |
| **Critical blockers** | **1** | **F3** — T4 serving stability |
| **Accepted risks** | **none recorded** | No risk has been explicitly accepted. F1, F2, F3 and `live_mcp_unproven` are **not** accepted risks. |

### Why GO was not available

`GO LIVE` required **zero** critical blockers plus all three T4 conditions. Condition (1)
`AI_SOC_T4_SEMANTIC_UNDERSTANDING_ENABLED=ON` holds and condition (3)'s C2 semantic/safety
criteria pass, but condition (2) — an approved **viable** serving posture — does not.

Per the Plan 7 amendment, T4 is part of the intended production architecture, so a non-viable C3
finding makes it a **CRITICAL BLOCKER** and must **not** be downgraded to
`NOT IN PRODUCTION SCOPE`. "Everything is fine except T4 is out of scope" was never an available
outcome, and is not what this record says.

**Green deterministic Cisco results (`50/0/0`) do not resolve serving reliability.** That suite
is a deterministic/reference evaluation and contributes no evidence about live-model
availability. The same applies to parity `120 exact`, which is dual-runtime equivalence — not
routing correctness, not answer correctness, and not serving health.

## Carried forward — unchanged, unaccepted, unsolved

| Item | Status | Destination |
|---|---|---|
| **F3** — `T4_SEMANTICALLY_VIABLE_BUT_VPS_SERVING_BLOCKER` | **CRITICAL BLOCKER**, not accepted, not downgraded | Blocks production GO until serving is remediated and re-measured |
| **F1** — DB loss silently degrades authority to `canonical_non_planned` | Open, not accepted | **Plan 8** (REL0 degradation signalling) |
| **F2** — model API liveness ≠ usable inference health | Open, not accepted | **Plan 8** (REL0 detection). Model restart stays **human-only** |
| **Live Splunk/MCP** | `live_mcp_unproven` | Outside proven production scope |
| **MITRE promotion** | **DEFERRED** | 11-row DRAFT drift ledger unchanged |
| **A7 legacy fallback** | `LEGACY_FALLBACK_ROLLBACK_ONLY_RETAIN_TEMPORARILY` | Retained **temporarily**, rollback-only; not in the normal target graph |
| `CONFIG_REBUILD_DRIFT` | **CLOSED for the development profile** | COE/production profiles unproven |
| Locked-field upstream quality | T4 can no longer re-classify a paraphrase into an SPL-capable family | **Plan 8** |

## Scope limits of this record

- No merge to `master` was performed. Merge remains **user-only**.
- Merging this branch is a larger action than E2: `master..HEAD` is **35 commits** — 11 unmerged
  Plan 6 commits (`F5 = DEFER`), `a8f02e3` (creates `architecture.md` on master), `bc7e2a8`
  (Plan 8 pre-binding), and 22 Plan 7 commits. E2 approving Plan 7 does **not** by itself
  authorize publishing those to `master`.
- One lost untracked document is outstanding and deliberately **not** reconstructed in this loop:
  `docs/architecture/canonical_architecture_audit_2026-08-15.md`, the declared `source_audit` of
  `plans/2026-08-15_0602_canonical-architecture-authority-convergence.md` (committed in
  `bc7e2a8`). It is Plan 8 pre-work's source document; **no Plan 7 evidence dangles**.
- No model restart was performed, requested, or scheduled. `HUMAN_RESTART_REQUIRED` did not
  arise.

## Outcome

Plan 7 is **implementation-complete** and its architecture change is **approved**. The system is
**not** declared production-ready. Production go-live is **DEFERRED / NO-GO** on the unresolved
critical T4 serving stability blocker. **Plan 8 may start after Plan 7 closure.**
