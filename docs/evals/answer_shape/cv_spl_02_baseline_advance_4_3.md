# 4.3 — intentional convergence baseline advance

**STATUS: APPLIED UNDER THE USER'S REQUEST TO EXECUTE THE EXISTING CANONICAL PLAN.**

## WHY

Item 4.3 requires a `CV.SPL.02`-class pin: non-null no-SPL reason and no empty code block.
The prior bank had only `CV.SPL.01` (`MEASURE_ON_LIVE` / deferred). Adding `CV.SPL.02`
as STRUCTURAL changes harness output shape (total 9 → 10) and therefore requires an
intentional baseline freeze — not a silent greenwash of an unexplained regression.

## WHAT CHANGED

- Bank: added `CV.SPL.02` with pins `no_spl_reason_non_null`, `empty_code_block=false`.
- Fixture: `docs/evals/answer_shape/fixtures/cv_spl_02_no_spl_reason.json`.
- Scorer: structural PASS for CV.SPL.02 from fixture.
- Baseline: refrozen after scorer+bank change; `--check` byte-identical thereafter.

## UNCHANGED

MULTI product gaps, TRACE seams, CV.SPL.01 deferred-live posture, `spl_validator.py`,
ChatPanel freeze path.
