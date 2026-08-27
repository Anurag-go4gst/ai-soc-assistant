# SPL gate histogram v1 (plan item 4.1)

**Worktree:** `ws/post-p10-answer-tool-convergence`  
**HEAD at measurement:** `ec4c8451` (post-3.7)  
**Sources:** `docs/evals/answer_shape/trace_diagnosis_v1.md`, `docs/evals/answer_shape/convergence_expectation_bank_v1.json`  
**Vocabulary:** plan closed primary list includes `G0`, `G1`, `G-TMPL`, `G-SLOT`, `G15`, `OBJECTIVE_PERSISTENCE`, `CAPABILITY_SELECTION`, `AUTHORIZATION`, `ENVIRONMENT_UNRESOLVED`.

## Scope rule

- Histogram counts **PRIMARY_FAILURE_SEAM** only.
- CONTRIBUTING seams are listed separately and never inflate primary totals.
- Do not invent root causes for `ENVIRONMENT_UNRESOLVED` slots.
- Do **not** assume template enablement (`G-TMPL`) is the fix without primary evidence.

## Trace primary histogram (from 0.3)

| PRIMARY_FAILURE_SEAM | Count | Slots |
|---|---:|---|
| ENVIRONMENT_UNRESOLVED | 2 | prod_failure_01, prod_failure_02 |
| OBJECTIVE_PERSISTENCE | 1 | design_case_ssh_admin_in_process |
| G-TMPL | 0 | — |
| G0 / G1 / G-SLOT / G15 / AUTHORIZATION | 0 | — |
| **Total** | **3** | = traces reviewed |

**Checksum:** primary counts sum to traces reviewed (**3 = 3**).

## Bank TRACE rows (mirror of 0.3)

| row_id | PRIMARY_FAILURE_SEAM |
|---|---|
| CV.TRACE.01 | ENVIRONMENT_UNRESOLVED |
| CV.TRACE.02 | ENVIRONMENT_UNRESOLVED |
| CV.TRACE.03 | OBJECTIVE_PERSISTENCE |

Bank TRACE primary sum = **3** (matches diagnosis).

## SPL-related bank rows

| row_id | PRIMARY assigned? | Notes |
|---|---|---|
| CV.SPL.01 | **no** | `MEASURE_ON_LIVE`; pins = honest posture (`candidate_spl_execution_eligible: false`); **not** a G-TMPL miss |

No `CV.SPL.02` row exists in the bank yet (forward reference for item 4.3 surface honesty).

## MULTI product gaps (not G-TMPL)

| row_id | baseline | Material gap class |
|---|---|---|
| CV.MULTI.01A | PRODUCT_GAP_EXPECTED | objective / intent preservation / plan surfacing |
| CV.MULTI.01B | PRODUCT_GAP_EXPECTED | dual eligibility / remediation / email draft posture |
| CV.MULTI.01C | PRODUCT_GAP_EXPECTED | envelope-bound mock (Phase 5) |

None of these assign `PRIMARY_FAILURE_SEAM: G-TMPL`.

## Contributing seams (non-primary)

| Slot | CONTRIBUTING_SEAMS |
|---|---|
| CV.TRACE.03 / design-case | CAPABILITY_SELECTION, ENVIRONMENT_UNRESOLVED |

`G-TMPL` does not appear as contributing.

## Materiality conclusion

```text
G-TMPL_COUNT = 0
G-TMPL_MATERIAL = false
```

Measured objective/shape failures are ENVIRONMENT_UNRESOLVED (unavailable production traces) and OBJECTIVE_PERSISTENCE (design-case multi-goal miss). Template coverage is **not** the material seam for this convergence plan’s measured bank/trace set.

## Explicit target line

```text
TARGET: none (no template enablement); 4.2 = SKIPPED_BY_EVIDENCE (G-TMPL = 0 material failures after 4.1)
```

## Forward refs

- **4.2** — mark `SKIPPED_BY_EVIDENCE` citing this histogram; do not flip `enabled:false` templates.
- **4.3** — honest no-SPL / clarification reason surfacing (`CV.SPL.02`-class); independent of G-TMPL.
- **4.4** — confirm `spl_validator.py` untouched by Phase 4 commits.
