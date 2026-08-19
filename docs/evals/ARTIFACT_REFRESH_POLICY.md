# Eval artifact refresh policy

Controlled refresh rules for offline evaluation artifacts. Accidental baseline drift must not land in commits.

## Row authority report (`row_authority_report.json` / `.md`)

- **Purpose:** Report-only audit derived from `question_runtime_map_v1.json`, `pattern_coverage_v1.json`, and `catalog.json`.
- **Drift detection:** `python3 scripts/build_row_authority_report.py --check`
- **Intentional refresh:** `python3 scripts/build_row_authority_report.py --refresh`
- **Commit when:** Runtime-map / manifest / catalogue authority inputs changed and COE reviewed the regenerated report.
- **Fields:** Each 105-row entry may include `projected_demotion_reasons` (offline mirror of runtime demotion triggers; does not mutate stored `promotion_status`).

## Governance eval reports — revert by default, commit on a reviewed refresh

These files are local-run baselines and commonly drift without semantic product changes:

- `docs/evals/langgraph_dual_parity_report.json`
- `docs/evals/langgraph_dual_parity_summary.md`
- `docs/evals/soc_clean_answer_eval_report.json`
- `docs/evals/soc_clean_answer_eval_report.csv`
- `docs/evals/soc_clean_answer_eval_summary.md`
- `docs/evals/llm_template_audit_report.md`

**Default: revert them after an incidental governance run.** The harness writes them
before validation, so any run dirties the worktree; committing that dirt commits drift
nobody reviewed.

**Commit when:** intentional refresh after a clean-tree governance PASS — all four of:

1. the working tree carried no other session's edits during the run,
2. `./scripts/run_stage3_governance_regression.sh` exited PASS on that tree,
3. gating metrics across the diff are unchanged (`clean_pass_count`, `fail_count`,
   `critical_failures`, `display_failures`), or a change is intended and stated,
4. none of the files is in `docs/evals/protected_execution_baseline.json` and
   `scripts/freeze_execution_baseline.py --check` passed in the same run.

State which of the four you verified in the commit message. Refreshing without them is
the drift this policy exists to stop.

Supersedes Plan 6 **E3 `CONTINUE PRESERVING`** for these six files (2026-08-19, PR #151).
E3's blanket "continue reverting" reasoning applied to incidental runs; it did not
anticipate a reviewed refresh. Record: `docs/evals/plan6/e3_stop_decision.md`.

Use `python3 scripts/build_row_authority_report.py --check --warn-eval-drift` before refreshing row-authority artifacts; `--check` fails when unrelated eval baselines differ from `HEAD`.

## Promotion status writes

- Persistent `promotion_status` changes only via `scripts/apply_promotion_status_review.py` (dry-run by default).
- Audit records append to `docs/evals/out/promotion_status_audit.jsonl` (gitignored).
- Runtime `/chat` and LLM paths remain read-only for `promotion_status`.
