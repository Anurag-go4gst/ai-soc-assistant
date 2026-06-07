# Golden Answer Regression Fixtures

This directory contains deterministic JSONL fixtures for answer-quality regression.

Tier 0 cases intentionally assert authority fields and governed decisions rather than
full prose. Long answer text is allowed to evolve as long as stable safety and routing
contracts remain intact.

Regenerate the expectation matrix and shallow Tier 2 rows:

```bash
python3 scripts/generate_answer_expectation_matrix.py
```

Run:

```bash
cd backend
PYTHONPATH=../backend:.. python3 -m app.evals.golden_answer_runner --tier 0 --json
PYTHONPATH=../backend:.. python3 -m app.evals.golden_answer_runner --tier 2 --json   # opt-in; shallow rows
```

Tier 0 is in `./scripts/run_stage3_governance_regression.sh`. Promoted live regressions append to `flagged_regressions.jsonl` (Tier 3).

