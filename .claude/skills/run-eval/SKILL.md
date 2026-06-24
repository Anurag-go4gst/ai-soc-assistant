---
name: run-eval
description: Run AI-SOC governance regression or a named eval script with the correct PYTHONPATH and flags, and check output against the documented baseline. Use when the user says "run the regression", "run governance", "run the evals", "run eval <name>", "check the suite", or /run-eval.
disable-model-invocation: true
---

# run-eval

Run the canonical AI-SOC eval / governance suites with the right environment. Never guess invocations — use the exact ones below. Baseline expectations: `docs/evals/regression_baseline.md`.

## Environment (always)

Run from repo root `/var/www/ai-soc-assistant`. Backend needs:

```bash
export PYTHONPATH="backend:.."   # or backend:$REPO_ROOT
```

Eval scripts run from repo root with `PYTHONPATH=backend:. python3 scripts/<name>.py`.
Tests live under `backend/` and run with `cd backend && PYTHONPATH=../backend:.. python3 -m pytest ...`.

`TELEMETRY_MODE=none` for hermetic runs (no telemetry sink). Live LLM is blocked in pytest by autouse guard; set `AI_SOC_TESTS_ALLOW_LIVE_LLM=1` only if a live run is explicitly wanted.

## Commands

### Full governance regression (default)
The canonical gate. Must be green before any commit touching `backend/app/`.

```bash
./scripts/run_stage3_governance_regression.sh
```

Expected: backend pytest **0 failed**, harness **6/6** `overall_pass=true`, all `--check` staleness gates exit 0. Recorded baseline: ~897 passed, 1 skipped, 6 xfailed anchors. Report PASS/FAIL with the failing section name — do not summarize as green unless the script exits 0.

### Backend pytest only
```bash
cd backend && TELEMETRY_MODE=none PYTHONPATH=../backend:.. python3 -m pytest -q
```

### Test harness (6/6)
```bash
PYTHONPATH=backend:. python3 -m test_harness.harness.runner --json
```
Assert 6 rows, all `overall_pass=true`.

### Control-plane golden suite (flag-on)
```bash
cd backend && CONTROL_PLANE_ENABLED=true PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_chat_control_plane_golden.py -q
```
Expected: 7 passed, no xfail.

### Named eval scripts (staleness/quality gates)
Most accept `--check` (compare to committed baseline, exit nonzero on drift) and some `--llm-mock`. Run from repo root with `PYTHONPATH=backend:.`:

```bash
PYTHONPATH=backend:. python3 scripts/eval_<name>.py --check
```

Common ones: `eval_sentinel`, `eval_answer_quality`, `eval_105_path_honoring`, `eval_paraphrase`, `eval_out_of_set_soc`, `eval_spl_relevance`, `run_langgraph_dual_parity_eval`. The `--105` / `--llm-mock` deterministic eval reaches 102/102 with `--llm-mock`, 100/102 without.

## Reporting rules
- State PASS/FAIL plus the exact failing section/test ids.
- Quote real counts from output; never assert "green" without the exit code.
- On drift in a `--check` gate, the fix is usually re-running the generator without `--check` to refresh the committed artifact — confirm with the user before regenerating.
