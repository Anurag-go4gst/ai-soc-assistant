# Plan 5 — P0 baseline (measured 2026-08-12)

Tree: HEAD `2080420` (descendant of the Plan 4 merge baseline `2f678b9`).
Pre-existing unrelated dirt, excluded from every Plan 5 change set:
`.claude/settings.local.json`, `backend/app/chat/detail_tools/__init__.py` (whitespace-only newline in an
empty `__init__.py`, not authored by Plan 5), plus untracked `.playwright-mcp/`, `output/`, two `g0-*.png`.

## Measured

| Gate | Recorded by Plan 4 | Measured at P0 | Verdict |
|---|---|---|---|
| Governance regression | PASS | **PASS** (exit 0) | match |
| Backend pytest | `5119 passed / 0 failed` | **`5119 passed, 3 skipped, 6 xfailed`** in 526.79s | match |
| Routing truth set — route_ok | `64/76` | **`64/76`** | match |
| Routing truth set — capability_inconsistent | `13` | **`13`** | match |
| Routing truth set — live route_ok | `59/76` | **`59/76`** | match |
| Routing truth set — advisory capability downgrades | `0` | **`0`** (diverges 5, degraded 5, improved 0) | match |
| Routing truth set — unsafe containment | `12/12` | **`12/12`** | match |
| Routing truth set — `--check` | 0 regressions | **0 regressions** | match |
| Production parity | `120 exact / 0 critical` | **`total=120 exact=120 approved=0 critical=0`** | match |
| Cisco power-grid | `50 PASS / 0 FAIL / 0 CRITICAL` | **`PASS=50 REVIEW=0 FAIL=0 CRITICAL=0`** | match |
| Sentinel | `17/17`, no drift | **`17/17`, no drift`** | match |
| Path honoring | `105/105` | **`105/105`** | match |
| Out-of-catalog OT probe | PASS | **PASS (6/6)** | match |
| Reference knowledge answer quality | — | **9 passed** | ok |
| Pipeline dispatch matrix | — | **5/5** | ok |
| Protected manifest | `14/14` | **13 checked** | **MISMATCH — see below** |

## Finding: the protected-manifest gate is not durable and under-guards

`scripts/freeze_execution_baseline.py` defaults `--in`/`--out` to **`/tmp/exec-baseline.json`** (`:151-152`), and
`check()` counts and iterates the **stored** manifest rather than the `PROTECTED` declaration (`:140`).

Measured consequences:

1. The live `/tmp/exec-baseline.json` is dated **Aug 9**, predating Plan 4 R1.5, which added
   `docs/evals/routing_truth_set_baseline_v1.json` to `PROTECTED` (`:37-40`). That file is therefore **declared
   protected but absent from the stored manifest, hence unguarded** — `--freeze` could rewrite the routing baseline
   and the gate would still report green.
2. `--check` reports **13 checked**, not the 14 recorded in Plan 4's closure evidence. All 14 declared files exist on
   disk; the shortfall is in the stored manifest, not the tree.
3. On a fresh host or after a reboot the `/tmp` file is absent and `--check` exits **2** rather than passing.

Tracked as new checklist item **A4.5**, sequenced before A5 adds the runtime map to `PROTECTED` (→ 15).

## Governance side effects (reverted, not committed)

The run rewrote 6 committed artifacts even though every sub-gate was invoked with `--check`
(`run_soc_clean_answer_eval.py:125-132` and `run_langgraph_dual_parity_eval.py:105-111` write **before** the
`--check` branch):

`langgraph_dual_parity_report.json`, `langgraph_dual_parity_summary.md`, `soc_clean_answer_eval_report.json`,
`soc_clean_answer_eval_report.csv`, `soc_clean_answer_eval_summary.md`, `llm_template_audit_report.md`.

All reverted via `git checkout --`. `docs/evals/langgraph_dual_parity_report.csv` was **not** modified by this run,
so the stale-report set behaves as 5 + 1, not a uniform 6. The six stale committed reports remain stale and
attributed to Plans 2–4 drift, per `STALE_REPORT_REFRESH` (out of scope).

## Incidental supporting evidence for amendment 3

The pipeline dispatch matrix already demonstrates non-universal lifecycle phases:
`sop_playbook: mode=knowledge stages=['rag_early']` carries no SPL chain, while
`hybrid_alert` carries `['rag_early','workflow_spl','spl_postprocessor','spl_source_resolve','mitre_finalize']`.
Phase applicability is therefore an existing deterministic behaviour for PhasePolicy (C0.1) to formalise, not a
new concept to introduce.

Raw log: `docs/evals/plan5/baseline/governance_p0.log`
