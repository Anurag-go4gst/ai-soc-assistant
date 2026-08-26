# Convergence suite baseline (plan item 0.4)

**Attested_at_utc:** `2026-08-26T17:56:37Z`  
**Worktree HEAD (at freeze):** record with commit for 0.4  
**VERIFIED_RELEASE_BASELINE_SHA:** `6b63df610ff4a0994a593537ab46c71464afe570`  
**LAST_PRODUCT_CHANGE_SHA:** `c109402d69956df455a780fd49a191fa173ab7ac`

## Convergence harness

| Artifact | Path |
|---|---|
| Bank | `docs/evals/answer_shape/convergence_expectation_bank_v1.json` |
| Harness | `scripts/eval_convergence_expectations.py` |
| Frozen baseline | `docs/evals/answer_shape/convergence_expectation_baseline_v1.json` |

**Verify:** two consecutive harness runs **BYTE_IDENTICAL_OK**; `--check` **PASS**.

**Frozen summary:** `total=9`, `pass=4`, `product_gap=3` (MULTI.01A/B/C), `deferred_live=2` (SOP/SPL), `fail=0`.

## Protected execution baseline

`python3 scripts/freeze_execution_baseline.py --check` → **protected artifacts unchanged (15 checked)**.

## RACES baseline SHA (from committed test constant)

`backend/app/tests/test_live_path_untouched_by_ec.py` → `RACES_BASELINE_SHA = 27970ea4d10f0e894c8adb4214e18cd46e24b28e`

Host RACES/frontend suite not re-run in this item (deferred to phase-boundary gates).

## Backend pytest failure node-IDs (host venv run)

**Command:** worktree `backend/` via Cursor workspace `.venv`, COE example env (no secrets), `AI_SOC_T4_SEMANTIC_UNDERSTANDING_TIMEOUT_SECONDS=10`.

**Result line:** `404 failed, 6703 passed, 48 skipped, 5 xfailed` in `575.94s`.

**Node-ID list:** `docs/evals/answer_shape/pytest_failure_node_ids_v1.txt` (404 lines).

**Interpretation:** This host-venv run is **environment-contaminated** relative to the known green compose baseline cited in `AGENTS.md` (~5829 passed on clean tree). Do **not** treat these 404 node-IDs as product defects introduced by this plan until re-confirmed inside the compose `backend` service on this worktree. They are recorded so later items can diff **new** failures against this captured set.

## Governance regression / frontend

Not executed inside 0.4 (phase-boundary requirement). Recorded as pending for Phase 1/3/7 boundaries.

## Unresolved environment evidence (carried from 0.2)

Two operator production traces remain `ENVIRONMENT_UNRESOLVED`.
