# SPL efficiency rules — shipped vs. addable

Reference artifact for **OPTIONAL_PHASE_S** in
[`plans/2026-08-26_1030_production-answer-shape-spl-mcp-convergence.md`](../../plans/2026-08-26_1030_production-answer-shape-spl-mcp-convergence.md).
Not a plan item. Nothing here is on the critical path.

Measured against HEAD on 2026-08-27. Splunk's guidance reconciled against what this repo already enforces, so
whoever picks up OPTIONAL_PHASE_S does not have to redo the research.

Sources: [Quick tips for optimization](https://help.splunk.com/en/splunk-enterprise/search/search-manual/10.2/optimize-searches/quick-tips-for-optimization) ·
[Write better searches](https://docs.splunk.com/Documentation/SplunkCloud/latest/Search/Writebettersearches)

## Two enforcement surfaces — do not confuse them

| Surface | File | Role | May reject? |
|---|---|---|---|
| Validator | `backend/app/safeguards/spl_validator.py` | **Safety.** Hard reject reasons; gates executability | Yes |
| Draft quality | `backend/app/spl/draft_quality.py` | **Quality.** `SOC-STD-SPL-001` lints, severities `hard_fail` / `warning` / `advisory` | No — advisory only |

Efficiency is **not** safety. All work below belongs in `draft_quality.py`.
Never move an efficiency rule into the validator, and never weaken an existing reject to accommodate one.

> Validator gotcha: it splits on `|` to tokenize commands, so regex alternation inside a rule can be
> misread as a pipe-command. Another reason to keep these lints out of it.

## Already shipped — 7 of 12 rules covered, 2 more strictly than Splunk advises

| # | Splunk rule | Status | Where |
|---|---|---|---|
| 1 | Narrow the time window | **Partial** — bounds are mandatory and all-time is rejected, but *narrowness* is unscored: a 90-day window on a spike hunt passes | `spl_validator.py` `missing_time_bounds`, `unbounded_all_time_search` |
| 2 | Specify `index` / `source` / `sourcetype` | **Stronger than Splunk** — Splunk says "should"; here a miss is a hard reject, plus an allowlist | `missing_index`, `missing_sourcetype`, `disallowed_index`, `disallowed_sourcetype`; advisory `Q08` |
| 3 | Field-value pairs before the first pipe | **Shipped** — this is the "shift-left" rule: `hard_fail` for family-required filters, `warning` for delayable static filters | `draft_quality.py` `U01` (`_check_shift_left`), `Q09` |
| 4 | Avoid wildcards | **Partial** — wildcard *index* is a hard reject; noisy short wildcards are banned **only for the ESP IT→OT family** | `wildcard_index_not_allowed`; `Q13` |
| 6 | Filter before calculating | **Partial** — covered incidentally by `U01` shift-left, not as a general `where`-before-`eval` rule | `U01` |
| 11 | Limit returned events | **Shipped** — mandatory and policy-capped | `missing_result_limit`, `result_limit_exceeds_policy` |
| 12 | `tstats` / summary indexing | **Shipped** — dedicated validators for both shapes, incl. `summariesonly` | `_validate_tstats_datamodel`, `_validate_from_datamodel` |
| — | Subsearches | **Stronger than Splunk** — Splunk says limit them; here they are blocked outright | `subsearches_not_allowed` |

Also already enforced and efficiency-adjacent: `first_command_must_be_search`, `missing_aggregation`,
`macros_not_allowed`, `external_calls_not_allowed`; and quality lints `Q07`/`Q12`/`Q14` (prefer `cidrmatch()`
and exact `IN()` over fuzzy `like()`), `U02` (native time handling), `U03` (columns survive `stats`).

## Genuine gaps — 5 rules, none present anywhere in `backend/app/spl/`

| # | Splunk rule | Gap | Proposed shape |
|---|---|---|---|
| 5 | Wrap minor-breaker terms in `TERM()` | **Absent** — zero occurrences of `TERM(` in the whole `spl/` package | `advisory`: base-search token contains `.` or `_` and is not already wrapped |
| 7 | Non-streaming commands (`sort`, `stats`) as late as possible | **Absent as a general rule** | `advisory`. **Must carve out `Q11`**, which deliberately mandates an *early* `sort 0 + _time` before `streamstats` for rolling-window correctness. A naive "sort late" lint would contradict a shipped `hard_fail` |
| 8 | Drop unneeded columns early with `fields` | **Absent** — `fields` is used widely but no lint asks for early projection. Note `U03` checks the near-opposite (that `table` columns survive `stats`), so the two must be written to agree | `advisory`: wide pipeline with no `fields` projection before the first aggregation |
| 9 | Avoid `NOT` / `!=`; state desired values with `OR` | **Absent** | `advisory` on `NOT` / `!=` in the base search |
| 10 | Minimise large `OR` lists; prefer a lookup or regex | **Absent** | `advisory` above a threshold (start ~10 terms) — tune against the bank, do not guess |
| 4b | Leading wildcard in search *terms* (not index) | Family-scoped only | **Do not generalise Q13** (family `hard_fail`). Add separate generic advisory **Q16** |
| 1b | Window narrowness | Unscored | Deferred. Prompt/compiler may only use governed RQC time scope — never invent a narrower window |

## Implementation notes

- **Free rule IDs: `Q03` and `Q04`** — the sequence runs `Q01`, `Q02`, `Q05`…`Q14`, so those two are unused. Beyond them, continue at `Q15`.
- Planned advisory detectors for OPTIONAL_PHASE_S S1: **Q03** (`NOT`/`!=`), **Q04** (excessive OR), **Q15** (`TERM()`),
  **Q16** (generic leading wildcard), **Q17** (non-streaming placement; carve out Q11), **Q18** (early projection; agree with U03).
- Severity: start everything at `advisory`. Promoting to `warning` changes `lint_draft_spl()`'s return value, which is a
  behaviour change with test consequences — `lint_draft_spl` returns only `hard_fail` and `warning` rule ids.
- Each lint should carry its rule number, a one-line rationale, and the doc URL.
- **Authority acceptance (corrected):** advisory detectors must not alter `approved` or `execution_eligible`.
  `normalized_spl` stays byte-identical for PASS / NO_SAFE_OPTIMIZATION rows; optimized rows may differ only when
  `assert_rewrite_preserves` PASS + full validator/risk chain PASS + before/after SPL recorded.
  Pin the S0 freeze before the first rewrite item.
- Rules 7 and 8 interact with shipped rules (`Q11`, `U03`). Write those two last, and add a test asserting the
  new lint and the existing one cannot both fire on the same correct draft.
