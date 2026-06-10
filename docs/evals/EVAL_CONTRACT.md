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
| `./scripts/run_stage3_governance_regression.sh` | umbrella | workstream end / pre-PR | minutes | generators `--check` + full pytest + harness 6/6 + Tier 0 |

## Inner loop vs heavy gates (plan B3/B4)

Per commit: task tests → `eval_sentinel.py --check` → full backend pytest.
**Never run the full 105+50 per task.** Heavy gates run at workstream
completion and before PR only.
