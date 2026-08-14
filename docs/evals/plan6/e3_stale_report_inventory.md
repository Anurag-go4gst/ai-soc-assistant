# Plan 6 E3 — stale governance-report inventory

Presentation for `P6_STALE_REPORT_DISPOSITION`. **No disposition is recorded here.**
Do not regenerate and commit these files as a side effect of this inventory.

Plan 5 left this as `STALE_REPORT_REFRESH` = out of scope, attributed to
Plans 2–4 drift. Plan 6 E3 is the separately scoped decision.

`docs/evals/ARTIFACT_REFRESH_POLICY.md` is **not** updated until a disposition
is recorded.

**E3 recorded 2026-08-13: CONTINUE PRESERVING.** See `docs/evals/plan6/e3_stop_decision.md`.

## The six committed reports

Named in Plan 6 “After governance: revert only”:

| # | Path | Last commit | Generated (in file) | Dirty vs HEAD now |
|---|---|---|---|---|
| 1 | `docs/evals/langgraph_dual_parity_report.json` | `9c65106` 2026-07-25 item 35 authoritative parity regen | 2026-07-25T18:13Z, commit `322c2bc`, exact=120 / approved=0 / critical=0 | clean |
| 2 | `docs/evals/langgraph_dual_parity_summary.md` | `9c65106` 2026-07-25 | same as JSON | clean |
| 3 | `docs/evals/soc_clean_answer_eval_report.json` | `8792338` 2026-07-25 Gate 1 / sentinel | 2026-07-25T10:06Z, 120/120 pass | clean |
| 4 | `docs/evals/soc_clean_answer_eval_report.csv` | `8792338` 2026-07-25 | companion of JSON | clean |
| 5 | `docs/evals/soc_clean_answer_eval_summary.md` | `8792338` 2026-07-25 | 2026-07-25T10:06Z, 120 pass / 0 fail | clean |
| 6 | `docs/evals/llm_template_audit_report.md` | `0e038b4` 2026-07-24 | 2026-07-24T05:50Z, 18 pass / 0 review | clean |

They are **not** members of `PROTECTED`. `freeze_execution_baseline.py --check`
15/15 does not guard them. That is why governance can rewrite them without
failing the freeze gate.

## Why they go stale

`./scripts/run_stage3_governance_regression.sh` invokes:

- `scripts/run_langgraph_dual_parity_eval.py --check` — writes committed JSON/MD **before** the `--check` branch (`run_soc_clean_answer_eval.py` same pattern at write-then-check).
- `scripts/run_soc_clean_answer_eval.py --check` — writes JSON/MD/CSV then checks.
- `scripts/llm_template_audit.py --write-report` — always writes the MD report.

Plan 5 / Plan 6 standing rule: after governance, revert **only these six**.
Never `git checkout -- docs/evals/` (that deletes `docs/evals/plan6/`).

A-GATE already practiced this: six reports reverted; porcelain `docs/evals/`
was only `?? docs/evals/plan6/`.

## Policy vs the six

`docs/evals/ARTIFACT_REFRESH_POLICY.md` “Do not commit without explicit review”
lists **five** paths. It omits `soc_clean_answer_eval_report.csv`.
`scripts/build_row_authority_report.py` `EVAL_DRIFT_PATHS` has the same five.
The csv is still in the Plan 6 revert list and is rewritten by the clean-answer
harness.

Updating the policy is in scope **only if** E3 changes disposition.

## What a refresh would mean

These are **eval reports**, not runtime-authoritative generated artifacts.
Plan 6 E4 says eval reports under `docs/evals/plan6/` are evidence, not
automatically protected. Refreshing the six into a new committed baseline is
a product/process choice, not required for C0 KEEP OFF or F5.

Refreshing now would also mix Plan 6 activation evidence with a governance
baseline bump. The plan forbids “simply regenerate and commit.”

## Options (do not self-select)

1. **Continue preserving** — keep the six committed and stale; keep reverting them after governance; leave `ARTIFACT_REFRESH_POLICY.md` as-is (optionally note the csv in a later non-Plan-6 hygiene change). Matches Plan 5 `STALE_REPORT_REFRESH` out of scope.
2. **Refresh as a declared new baseline** — run the three writers on purpose, review the diffs, commit the six as a named baseline refresh, then update the policy “commit when” text. Separate commit from any runtime/activation change.
3. **Replace with generated / non-committed reports** — stop treating the six as source-of-truth in git; write them under a gitignored or scratch path; `--check` compares without committing. Requires harness/path changes (not a silent move).
4. **Move out of source control** — gitignore the six; delete from the tree after copying last committed copies elsewhere. Also requires harness/path changes so governance does not keep dirtying tracked files.

Do **not** regenerate and commit as a side effect of F-GATE or G2.

## Not this STOP

- 105 answer goldens, frozen routing truth-set baseline, governed registries, runtime map, catalog — those are `PROTECTED` / other STOPs.
- Plan 6 `docs/evals/plan6/` evidence files — not stale governance reports.
