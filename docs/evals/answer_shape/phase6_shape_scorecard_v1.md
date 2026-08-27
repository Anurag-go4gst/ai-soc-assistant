# Phase 6 shape scorecard (item 6.9)

**Worktree:** `ws/post-p10-answer-tool-convergence`  
**HEAD at score:** _(filled at commit)_  
**Compared to:** `docs/evals/answer_shape/convergence_expectation_baseline_v1.json` (post-4.3 freeze, bank total 10)

## Method

Score production answer **SHAPE** via `scripts/eval_convergence_expectations.py` — not EC prose equality.
EC fixtures remain isolated.

## Harness summary (current)

| Metric | Count |
|---|---:|
| total rows | 10 |
| PASS | 5 |
| PRODUCT_GAP | 3 (MULTI.01A/B/C design-case capture gaps) |
| DEFERRED_LIVE_MEASURE | 2 (SOP.01, SPL.01) |
| FAIL | 0 |

`--check` vs frozen baseline: **PASS** (byte-identical).

## Shape arc vs states A–E

| State | Contract | Status |
|---|---|---|
| A | Plan pending approval; no fake terminal conclusion | Canonical InvestigationPlanApprovalCard (6.2); dual HIL plan label removed |
| B | Progress may render; progress ≠ evidence | OutcomeCard + progress tests green (6.1) |
| C | Honest inconclusive; PENDING_CONDITION visible; no false CTA | MULTI.01A fixtures + conditional UI (6.3–6.5) |
| D | Suspicious; remediation may be eligible; email draft per predicate; send HIL | MULTI.01B + Phase 3 dual gates (6.6–6.7) |
| E | Pure SOP/knowledge; no investigation plan unless investigation-shaped | SOP.01 deferred-live; J7 knowledge ABSENT pins |

## MULTI residual (honest PRODUCT_GAP)

Design-case in-process capture still reports investigation_plan / conditional intent preservation gaps on the **stale** capture JSON — not regressions of Final-RQC/Phase-10 product seams proven by unit tests. MULTI.01C mock envelope path still PRODUCT_GAP_EXPECTED on design-case capture; Phase 5 unit/gate proofs cover envelope-bound mock separately.

## Movement vs 0.4

- Added CV.SPL.02 STRUCTURAL PASS (4.3 intentional baseline advance).
- No unexplained FAIL node IDs.
- Product gaps remain the three MULTI rows expected since 0.4.

## Verdict

Phase 6 shape convergence **ACCEPTED** for checklist closure: production shape contracts pinned; EC prose not chased; residuals named as PRODUCT_GAP / ENVIRONMENT / deferred-live without silent baseline rewrite.
