# Eval artifact refresh policy

Controlled refresh rules for offline evaluation artifacts. Accidental baseline drift must not land in commits.

## Row authority report (`row_authority_report.json` / `.md`)

- **Purpose:** Report-only audit derived from `question_runtime_map_v1.json`, `pattern_coverage_v1.json`, and `catalog.json`.
- **Drift detection:** `python3 scripts/build_row_authority_report.py --check`
- **Intentional refresh:** `python3 scripts/build_row_authority_report.py --refresh`
- **Commit when:** Runtime-map / manifest / catalogue authority inputs changed and COE reviewed the regenerated report.
- **Fields:** Each 105-row entry may include `projected_demotion_reasons` (offline mirror of runtime demotion triggers; does not mutate stored `promotion_status`).

## Do not commit without explicit review

These files are local-run baselines and commonly drift without semantic product changes:

- `docs/evals/langgraph_dual_parity_report.json`
- `docs/evals/langgraph_dual_parity_summary.md`
- `docs/evals/soc_clean_answer_eval_report.json`
- `docs/evals/soc_clean_answer_eval_summary.md`
- `docs/evals/llm_template_audit_report.md`

Use `python3 scripts/build_row_authority_report.py --check --warn-eval-drift` before refreshing row-authority artifacts; `--check` fails when unrelated eval baselines differ from `HEAD`.

## Promotion status writes

- Persistent `promotion_status` changes only via `scripts/apply_promotion_status_review.py` (dry-run by default).
- Audit records append to `docs/evals/out/promotion_status_audit.jsonl` (gitignored).
- Runtime `/chat` and LLM paths remain read-only for `promotion_status`.
