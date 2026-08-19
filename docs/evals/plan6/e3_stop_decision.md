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

---

## Superseded 2026-08-19 — `E3_REFRESH_ON_CLEAN_TREE_PASS`

Recorded by the repo owner on 2026-08-19, on PR #151. **E3 CONTINUE PRESERVING no
longer applies to the six files below.** The decision above stays as the record of
what was true from 2026-08-13; it is not rewritten.

### What changed

E3's reason was *"unrelated report drift"* — governance writes these reports before
validation, so a run dirties the worktree and an agent committing that dirt would be
committing drift nobody reviewed. That reason holds for an incidental run.

It does not hold for a **reviewed refresh after a clean-tree governance PASS**, where
the regeneration is the point. The refresh committed at `092b363` was taken on a tree
with no other session mid-edit, on `53cf4e7`, with `stage3_governance_regression: PASS`,
and the gating metrics identical across the diff: `clean_pass_count 120`,
`fail_count 0`, `critical_failures 0`, `display_failures 0`. None of the six is a
protected artifact, and the protected manifest's `--check` passed in the same run.

### What replaces the standing revert list

`docs/evals/ARTIFACT_REFRESH_POLICY.md` now carries an explicit **Commit when** clause
for these files. Default behaviour is unchanged — **revert them after an incidental
governance run**. Commit them only when all of the following hold, and say so in the
commit message:

1. the working tree carried no other session's edits during the run,
2. `stage3_governance_regression` exited PASS on that tree,
3. the gating metrics in the diff are unchanged (or the change is the point and is stated),
4. none of the files is in the protected-artifact manifest and `--check` passed.

An agent that reads only this file must not conclude "always revert". Read the policy
file's Commit-when clause before deciding.
