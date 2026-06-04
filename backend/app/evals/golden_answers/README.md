# Golden Answer Regression Fixtures

This directory contains deterministic JSONL fixtures for answer-quality regression.

Tier 0 cases intentionally assert authority fields and governed decisions rather than
full prose. Long answer text is allowed to evolve as long as stable safety and routing
contracts remain intact.

Run:

```bash
cd backend
PYTHONPATH=../backend:.. python3 -m app.evals.golden_answer_runner --tier 0 --json
```

