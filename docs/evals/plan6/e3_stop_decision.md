# Plan 6 E3 — `P6_STALE_REPORT_DISPOSITION`

Recorded 2026-08-13. **CONTINUE PRESERVING.**

This is a deliberate preservation decision, not an unresolved gap.

## Decision

**CONTINUE PRESERVING**

Keep the six committed governance/eval reports tracked exactly as they are today.

Do **not**:

- regenerate and commit them as a new baseline
- change `docs/evals/ARTIFACT_REFRESH_POLICY.md`
- move them out of source control
- add gitignore rules
- modify governance harness paths
- turn this into a report-lifecycle redesign

## Reason

- Plan 5 already classified this as `STALE_REPORT_REFRESH` outside the activation work.
- The reports are clean vs HEAD and are not protected artifacts.
- Governance `--check` currently writes them before validation, which can dirty
  the worktree after regression runs.
- That behavior is known and does not justify broadening Plan 6 into
  governance-harness cleanup.
- Continue reverting/restoring these generated report changes after governance
  checks so unrelated report drift is not committed.

## Standing revert list (unchanged)

- `docs/evals/langgraph_dual_parity_report.json`
- `docs/evals/langgraph_dual_parity_summary.md`
- `docs/evals/soc_clean_answer_eval_report.json`
- `docs/evals/soc_clean_answer_eval_report.csv`
- `docs/evals/soc_clean_answer_eval_summary.md`
- `docs/evals/llm_template_audit_report.md`

Never `git checkout -- docs/evals/` (that would destroy `docs/evals/plan6/`).

Inventory: `docs/evals/plan6/e3_stale_report_inventory.md`.
Policy file: **unchanged**.
