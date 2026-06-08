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

1. **Shift-left filtering** — static `index`, `sourcetype`, `EventCode`, `action`, `protocol`, and zone filters in the base `search` line where available.
2. **Keep `_time` numeric until aggregation** — avoid formatting raw event time before `stats` / `bin` / `timechart`.
3. **Normalize fields early with `coalesce()`** — alias multi-vendor field names before filters and aggregations.
4. **Escape Windows paths** — use doubled backslashes in quoted path literals (`%\\\\w3wp.exe` with `like()`).
5. **Readable timestamps after aggregation** — `strftime()` on epoch fields produced by `stats` / `bin`, not on pre-aggregate `_time`.
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
| Q03 | hard_fail | No `strftime(_time|event_time|lockout_time, ...)` before first `stats` / `bin` / `timechart` |
| Q04 | hard_fail | If `earliest(_time)` / `latest(_time)` is used, readable `strftime()` output must appear |
| Q05 | hard_fail | Draft text must not imply executed, approved, or governed SPL |
| Q06 | advisory | Prefer `coalesce()` for common multi-vendor field aliases |
| Q07 | warning | CIDR logic should use `cidrmatch()`, not `IN()` |
| Q08 | advisory | Base `search` should include `index=` and `sourcetype=` placeholders |
| Q09 | advisory | Base `search` should include static `EventCode` / `action` / `protocol` filters where available |

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
5. `esp_it_to_ot_connection` — ESP zone-to-zone allowed connections
6. `substation_hmi_brute_force` — HMI/OS portal brute-force windows

## Verification

```bash
pytest backend/app/tests/test_spl_draft_quality.py
pytest backend/app/tests/test_spl_draft_preview.py
python3 scripts/run_spl_draft_preview_eval.py
python3 scripts/run_spl_draft_preview_eval.py --check
```
