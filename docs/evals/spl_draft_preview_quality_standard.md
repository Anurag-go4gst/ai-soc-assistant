# SOC-STD-SPL-001 — SPL Draft Preview Quality Standard

Lab-only quality standard for deterministic SPL draft previews in the AI SOC Assistant.
Applies when `AI_SOC_SPL_DRAFT_PREVIEW_ENABLED=true` and governed SPL is not ready.

## Governance boundaries

| Property | Draft preview | Governed SPL |
|----------|---------------|--------------|
| Status | `draft_preview_not_governed` | catalog-approved template path |
| Governed | `false` | policy-dependent |
| Catalog approved | `false` | when template active |
| Execution enabled | `false` | gated separately |
| SOC review | **required** before any use | required per Phase 6 |

**Draft SPL is not governed, not approved, and must not be executed without SOC review.**

This standard does not change Phase 6 governed SPL approval logic, MCP execution gates, or LangGraph cutover.

## Engineering principles

### Universal standards (U01–U03)

1. **U01 — Line-1 index-filter / shift-left** — static filters known from the request (`EventCode`, `action`, `status`, `protocol`, `sourcetype`, raw keywords) must appear in the base `search` before the first pipe when possible. Do not force normalized `coalesce()` conditions onto line 1. Delaying obvious static filters after the first pipe is a lint finding.
2. **U02 — Native `_time` rule** — do not use `strftime(_time, ...)` before `bin` / `stats` / `streamstats` / `timechart`. Keep `_time` numeric for aggregation and windowing; apply `strftime` only at final presentation. If `earliest(_time)` / `latest(_time)` is used, require readable `first_seen` / `last_seen` formatting after stats.
3. **U03 — Stats inclusion rule** — any field required in the final `table` after `stats` / `streamstats` must be in the `by` clause or preserved via `values()`, `latest()`, `earliest()`, `count()`, `dc()`, `list()`, etc. Critical fields (`src_zone`, `dest_zone`, `rule`, `app`, `caller_host`, `command_line`, `parent_image`, `child_image`, `target_user`, `added_user`, `group_name`, and their `*_norm` / plural aliases) hard-fail when dropped.

### Additional principles

4. **Normalize fields early with `coalesce()`** — alias multi-vendor field names before filters and aggregations.
5. **Escape Windows paths** — use doubled backslashes in quoted path literals (`%\\\\w3wp.exe` with `like()`).
6. **Use `cidrmatch()` for CIDR ranges** — prefer `cidrmatch("<cidr>", ip_field)` over `ip IN (...)`.

## Rule severity

| Severity | Effect on `quality_status` | Effect on `draft_lint_status` |
|----------|------------------------------|-------------------------------|
| `hard_fail` | `failed` | `failed` |
| `warning` | `warning` | counted in lint violations |
| `advisory` | `passed` (informational) | ignored for pass/fail |

## Rules (SOC-STD-SPL-001)

| Rule ID | Severity | Check |
|---------|----------|-------|
| Q01 | hard_fail | No newline inside quoted SPL strings |
| Q02 | hard_fail | No unescaped Windows path backslashes in quoted strings |
| U01 | hard_fail / warning | Shift-left static filters (`EventCode`, `action`, protocol keywords) into base `search`; warn when delayed |
| U02 | hard_fail | No `strftime(_time|event_time|lockout_time, ...)` before `bin` / `stats` / `streamstats` / `timechart`; `earliest`/`latest` require readable output after stats |
| U03 | hard_fail / warning | Final `table` columns must survive `stats` / `streamstats` (critical fields hard-fail) |
| Q05 | hard_fail | Draft text must not imply executed, approved, or governed SPL |
| Q06 | advisory | Prefer `coalesce()` for common multi-vendor field aliases |
| Q07 | warning | CIDR logic should use `cidrmatch()`, not `IN()` |
| Q08 | advisory | Base `search` should include `index=` and `sourcetype=` placeholders |
| Q09 | advisory | Base `search` should include static `EventCode` / `action` / `protocol` filters where available |
| Q10 | hard_fail | Event 4740 must use `caller_host_norm` with caller computer fields — not `ComputerName` alone |
| Q11 | hard_fail | HMI brute-force must use `sort 0 + _time` before `streamstats time_window=5m` |
| Q12 | warning | ESP IT→OT must use exact zone `IN()` labels or `cidrmatch()`, not fuzzy `like("%it%")` / `like("%ot%")` |
| Q13 | hard_fail | ESP IT→OT must not use noisy base-search wildcards (`*it*`, etc.) or pass blank `session_state_norm` as established |

## Family-specific engineering

Detailed per-family shift-left, `coalesce()`, path escaping, `cidrmatch()`, and aggregation rules live in:

- `backend/app/spl/family_engineering.py` — shared blocks for draft + LLM fallback prompt
- `backend/app/spl/draft_preview.py` — deterministic lab drafts
- `backend/app/spl/llm_fallback.py` — LLM SPL advisory fallback prompt

## Implementation

- Evaluator: `backend/app/spl/draft_quality.py` (`evaluate_draft_quality`)
- Draft families: `backend/app/spl/draft_preview.py`
- Back-compat facade: `backend/app/spl/draft_preview_lint.py`
- Eval harness: `scripts/run_spl_draft_preview_eval.py`

## Detection families covered

1. `windows_privileged_group_changes` — 4728/4732/4756 privileged group additions
2. `windows_account_lockout` — EventCode 4740 with caller host fields
3. `sysmon_web_shell_spawn` — web server parent → shell child (incl. `pwsh.exe`)
4. `scada_dnp3_modbus_write` — DNP3/Modbus write/modify with `cidrmatch()` allowlist
5. `esp_it_to_ot_connection` — ESP IT→OT allowed/established connections with exact zone/CIDR placeholders, session_state_norm, and operational field preservation through stats
6. `substation_hmi_brute_force` — HMI/OS portal brute-force windows

## Verification

```bash
pytest backend/app/tests/test_spl_draft_quality.py
pytest backend/app/tests/test_spl_draft_preview.py
python3 scripts/run_spl_draft_preview_eval.py
python3 scripts/run_spl_draft_preview_eval.py --check
```
