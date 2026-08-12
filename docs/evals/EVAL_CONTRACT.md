# Eval Contract — definitive verdicts (T-PRE.3, plan 2026-06-10_0356 rev 3)

Every eval in this repo must give a **definitive answer** (plan Principle 4).
No eval may end on a fuzzy score without a threshold and a verdict.

## Required behavior

1. **Verdict line.** Final stdout line matches:

   ```
   RESULT: PASS (<n>/<m> rows[, extra detail])
   RESULT: FAIL (<n>/<m> rows[, extra detail])
   ```

   `n` = rows passing all gates, `m` = rows evaluated. Extra detail (violation
   counts, elapsed time) is free-form inside the parentheses.

2. **Exit codes.** In gate mode (`--check` where the script has one) the
   process exits `0` on PASS and `1` on FAIL. Report-only mode may exit `0`
   with a FAIL verdict line — CI gates must always pass `--check`.

3. **Machine-readable output.** Where a `--json` style flag exists it writes
   per-row results; the JSON must contain enough to reproduce every verdict
   (row key, observed values, violation strings).

4. **Thresholds live in code or frozen fixtures, never in heads.** Examples:
   `CLARIFICATION_BASELINE` in `eval_105_path_honoring.py`, the frozen
   `sentinel_baseline.json` fixture, `--min-rate` defaults. Loosening any
   threshold requires Anurag sign-off (plan Part E stop-the-line rule).

5. **LLM-judge evals** (Tier-L, WS5) emit per-row `PASS|FAIL|UNCERTAIN`;
   `UNCERTAIN` rows are queued for human review, never silently averaged.

## Current evals

| Script | Mode | Gate | Runtime | Notes |
|--------|------|------|---------|-------|
| `scripts/eval_sentinel.py --check` | in-process | per-commit (B3) | ~0.2 s | 17-row frozen happy-path baseline; `--freeze` re-baselines (additive-sections review rule applies) |
| `scripts/build_sentinel_set.py --check` | static | governance regression | <1 s | drift gate on the frozen sentinel selection |
| `scripts/eval_105_path_honoring.py --check` | in-process | workstream end / pre-PR (B4) | ~10 s | full 105 path honoring; `--refs q0.q001,q0.q010` = debugging subset |
| `scripts/run_powergrid_soc_question_eval.py --check` | live HTTP `/chat` | workstream end / pre-PR (B4) | minutes | needs running backend (`docker compose up -d`); profiles `deterministic` / `live_llm` |
| `python3 -m app.evals.golden_answer_runner` (Tier 0) | in-process | governance regression | seconds | golden-answer contract assertions |
| `scripts/eval_out_of_set_soc.py --check` | in-process | on demand / WS5 reporting (NOT in governance regression) | ~1 s | 36-row out-of-set corpus; critical rules gate, REVIEW rows report findings; `--llm-judge` adds the offline judge (eval-only, never gating) |
| `./scripts/run_stage3_governance_regression.sh` | umbrella | workstream end / pre-PR | minutes | generators `--check` + full pytest + harness 6/6 + Tier 0 |

## What each gate does and does not prove (Plan 4)

- **`scripts/run_production_parity_eval.py`** compares the **imperative** and
  **ResourcePlanner** runtimes *against each other*. `exact=120` is runtime
  equivalence. It is **not** answer correctness, **not** routing correctness, and
  **not** agreement with `backend/app/evals/golden_answers/question_105_golden.jsonl`
  — that file is never read by this evaluator. Never cite parity as evidence that a
  route or an answer is right.
- **`question_105_golden.jsonl`** cases assert `expected.selected_skill`, are
  self-described auto-generated shallow expectations, and are **tier 2**; the
  governance regression runs `--tier 0`. Measured 2026-08-12: they matched production
  routing on **1 of 105** rows.
- **`scripts/eval_routing_truth_set.py`** is the routing-quality gate. Labels-only,
  independently adjudicated, `acceptable_skills` is a set, and route correctness and
  capability consistency are independent verdicts. `--check` is **no-regression**
  against the frozen baseline, not identity; dropping a row counts as a regression.
  Intent family and answer shape are reported, never gated.
- **`scripts/eval_out_of_set_soc.py`** classifies behavior against corpus rules and
  has no frozen baseline. Its execution-marker check is negation-aware (an honest
  "Execution: Not executed" is not a claim) and guardrail keys such as
  `unsupported_claims_avoid` are excluded from the scanned prose; both corrected as
  instrumentation in Plan 4 without touching runtime or corpus expectations.

## Command-name notes

- The Tier-D answer-quality runner is `scripts/eval_answer_quality.py`. There
  is **no** `scripts/eval_tier_d.py` — references to that name mean this
  runner.
- Invoke all eval scripts with `python3` (the box has no `python` alias).

## COE Hard-Stop Issue Codes

`app.evals.answer_efficacy_checks.evaluate_universal_efficacy` emits these
COE-transfer stop conditions. Any occurrence should block a "ready for COE"
claim until fixed or explicitly waived.

| Code | Meaning |
|------|---------|
| `run_contract_missing` | A live `/chat` payload did not include the canonical `run_contract`. |
| `run_contract_field_missing:<field>` | `run_contract` or `run_contract.routing` is missing a Gate 4 field. |
| `live_backed_without_execution` | Visible answer says `live-backed` without `execution_status=executed` and collected evidence. |
| `results_table_not_allowed` | `splunk_results_table` is visible while `run_contract.allow_results_table=false`. |
| `priority_prefix_without_severity` | A P1/P2/P3 action prefix appears when severity is missing or not assigned. |
| `route_authority_holder_contradiction` | Displayed route authority contradicts `run_contract.routing.authority_holder`. |
| `duplicate_spl_warning` | The lab/review-only SPL warning appears more than once in visible text. |
| `duplicate_soc_review_checklist` | The SOC review checklist heading appears more than once in visible text. |

## Inner loop vs heavy gates (plan B3/B4)

Per commit: task tests → `eval_sentinel.py --check` → full backend pytest.
**Never run the full 105+50 per task.** Heavy gates run at workstream
completion and before PR only.
