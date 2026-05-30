# Stage 3L-S3 Step 3: COE Gate Review — `cov.q046.excessive_failed_logins_sample`

**Date:** 2026-05-29 (COE sign-off recorded)  
**Gate review commit:** `157a83d` · **S3.3A:** `214c1e7` · **S3 Step 3:** `0494447`  
**Pilot:** `cov.q046.excessive_failed_logins_sample` — **COE-approved for lab pilot only** (see observation window below)  
**References:** [Step 3 gate design](stage3l_s3_step3_coverage_gate_design.md), [trace checkpoint](stage3l_s3_trace_review_checkpoint.md)

---

## Verdict

| Outcome | Meaning |
|---------|---------|
| **READY for lab pilot** | S3.3A harness + Step 3 minimal path landed; production defaults unchanged until COE enables env flags in a lab only |

Production remains: `ROUTE_AUTHORITY_OPERATION_AUTHORITATIVE_ENABLED=false`, allowlist empty.

---

## COE sign-off wording (approved text)

> COE acknowledges the S3 Step 3 gate review and approves implementation of the **cov.q046 authority pilot only**, behind the global kill switch and per-coverage_id allowlist.
>
> This approval does **not** approve live SPL execution, MCP execution, renderer changes, Answer Guard, final synthesis, or any second coverage_id.
>
> `threshold_ref` and `time_window` remain mandatory. If absent, the system must clarify or fall back to the legacy `selected_skill` path.

| Reviewer | Gate review acknowledged | Approve `cov.q046` for Step 3 **implementation** | Date |
|----------|--------------------------|-----------------------------------------------------|------|
| COE / Anurag | ☑ | ☑ | 2026-05-29 |

---

## COE acceptance criteria (10) — engineering evidence

| # | Criterion | Evidence |
|---|-----------|----------|
| 1 | **Only** `cov.q046.excessive_failed_logins_sample` allowlisted | `ALLOWLISTABLE_COVERAGE_IDS` + `validate_allowlist_ids`; config rejects any other id |
| 2 | Authority false by default | `Settings.route_authority_operation_authoritative_enabled=False`; `test_production_defaults_authority_off_allowlist_empty` |
| 3 | Missing `threshold_ref` / `time_window` never defaulted | Gate `missing_required_threshold_ref` / `missing_required_time_window`; `test_unit_no_threshold_default_injected` |
| 4 | Five fallback cases pass | `test_route_authority_gate_stage3l_s3_3a.py` cases a–e |
| 5 | Happy path passes only with explicit lab config | `test_happy_path_authority_applied_only_with_explicit_lab_config` (global on + allowlist + slots present) |
| 6 | No SPL/MCP execution introduced | `execution.executed_spl is None`; workflow `execution_enabled=false`; governance unchanged |
| 7 | Experience Center + harness green | `test_experience_center_unchanged`; full pytest + harness 6/6 |
| 8 | Rollback runbook | [Rollback runbook](#rollback-runbook-operation-authority) below |
| 9 | Trace explains apply/fallback | `authority_trace`, `authority_decision`, `authority_holder` on `route_authority_compare` |
| 10 | No other pattern implicitly upgraded | `test_other_coverage_id_not_implicitly_upgraded` (e.g. q002 → `coverage_id_not_allowlisted`) |

---

## Proceed order (COE / engineering)

1. ✅ Verify S3.3A harness committed and green (`test_route_authority_gate_stage3l_s3_3a.py`, full pytest).
2. ✅ COE signs gate review + `cov.q046` implementation approval (table above).
3. ✅ Implement minimal S3 Step 3 authority path (`route_authority_apply.py`; shadow compare only; `selected_skill` preserved on `/chat`).
4. ✅ Full backend tests + harness (`587` pytest, harness `6/6`).
5. ✅ **Default mode verification** — captured 2026-05-29 ([traces](#environment-verification-traces)).
6. ✅ **Lab pilot verification** — captured 2026-05-29 ([traces](#environment-verification-traces)).
7. ☐ Observe a real window with **zero unexpected disagreements** before pattern #2 (in progress).
8. ☐ Only then discuss a second `coverage_id`.

---

## Review checklist (engineering)

| # | Question | Result | Evidence / notes |
|---|----------|--------|------------------|
| 1 | COE approve `cov.q046` pilot implementation? | **Pass (signed)** | Sign-off table + environment traces below |
| 2 | Manifest row stable? | **Pass** | `pattern_coverage_v1.json` |
| 3 | Route-plan fixture + validator? | **Pass** | R1/R2 tests |
| 4 | Bridge compatible? | **Pass (mock)** | Trace checkpoint 1b |
| 5 | Compare clean? | **Pass** | S3 compare tests |
| 6 | Fallback tested? | **Pass** | S3.3A + Step 3 tests |
| 7 | Authority off by default? | **Pass** | Config + tests |
| 8 | Kill switch + allowlist? | **Pass** | S3.3A; only `cov.q046` when non-empty |
| 9 | EC / harness unchanged? | **Pass** | Demo `route_plan_shadow=null`; harness 6/6 |
| 10 | Rollback path? | **Pass** | Runbook below |

---

## Explicit blocks (unchanged)

| Item | Gate |
|------|------|
| `entity_context_lookup` / `notable_risk_lookup` as primary | **Blocked** |
| `cov.q007.dga_detection_binding` | **Blocked** |
| Second allowlist `coverage_id` | **Blocked** until COE re-approves |

---

## Pilot row summary (`cov.q046`)

| Field | Value |
|-------|--------|
| Question | Which users have excessive failed logins? |
| Legacy intent (typical router) | `attack_discovery` |
| Runtime `primary_skill` | `aggregate_and_rank` |
| `pattern_id` | `top_failed_okta_login_users` |
| Clarification | `threshold_ref`, `time_window` — **no defaults** |

---

## Rollback runbook (operation authority)

1. Set `ROUTE_AUTHORITY_OPERATION_AUTHORITATIVE_ENABLED=false`
2. Clear `ROUTE_AUTHORITY_OPERATION_COVERAGE_ALLOWLIST=`
3. Redeploy or restart backend
4. Confirm `operation_authoritative_applied=false` and `authority_fallback_reason=global_kill_switch_disabled`
5. Confirm `/chat` `selected_skill` unchanged (legacy router)
6. Confirm `authority_holder=legacy_selected_skill`

---

## S3.3A + Step 3 behavior

| Layer | Behavior |
|-------|----------|
| S3.3A | `evaluate_route_authority()` + allowlist; fallback reasons |
| Step 3 | When gates pass + lab flags: `authority_holder=route_plan_primary_skill`, `planning_primary_skill` set; **`selected_skill` on response unchanged** |
| Out of scope | SPL/MCP execution, renderer, synthesis, Answer Guard, second coverage_id |

---

## Conditions for Step 3 **implementation** (met by engineering PR)

Engineering reuses S3.3A harness and adds shadow-only authority application with Step 3 tests. No authority for blocked rows. Harness/EC unchanged at default flags.

---

## Environment verification traces

Captured with `python3 scripts/capture_stage3l_s3_coe_pilot_traces.py` (mock `route_plan_shadow` candidate; same gate path as `/chat`). Full JSON: [`stage3l_s3_step3_coe_pilot_verification_traces.json`](stage3l_s3_step3_coe_pilot_verification_traces.json).

Query (cov.q046-shaped): `Find top 10 users with failed Okta logins in the last 24 hours.`

### 1. Default production-safe fallback

| Env | Value |
|-----|-------|
| `ROUTE_AUTHORITY_OPERATION_AUTHORITATIVE_ENABLED` | `false` |
| `ROUTE_AUTHORITY_OPERATION_COVERAGE_ALLOWLIST` | *(empty)* |

| Trace field | Value |
|-------------|-------|
| `coverage_id_resolved` | `cov.q046.excessive_failed_logins_sample` |
| `operation_authoritative_applied` | `false` |
| `authority_fallback_reason` | `global_kill_switch_disabled` |
| `authority_holder` | `legacy_selected_skill` |
| `response.selected_skill` | `attack_discovery` (unchanged) |
| `execution.executed_spl` | `null` |

`authority_trace`: Operation authority not applied; legacy selected_skill remains authoritative. `fallback_reason='global_kill_switch_disabled'`.

### 2. Lab pilot happy path

| Env | Value |
|-----|-------|
| `ROUTE_AUTHORITY_OPERATION_AUTHORITATIVE_ENABLED` | `true` |
| `ROUTE_AUTHORITY_OPERATION_COVERAGE_ALLOWLIST` | `cov.q046.excessive_failed_logins_sample` |
| Candidate | `threshold_ref` + `time_window` present in `route_plan_parameters` |

| Trace field | Value |
|-------------|-------|
| `operation_authoritative_applied` | `true` |
| `authority_fallback_reason` | `null` |
| `authority_holder` | `route_plan_primary_skill` |
| `planning_primary_skill` | `aggregate_and_rank` |
| `response.selected_skill` | `attack_discovery` (legacy preserved on response) |
| `migration_phase` | `S3_step_3_cov_q046_pilot` |

`authority_trace`: Operation authority applied for allowlisted coverage_id `cov.q046.excessive_failed_logins_sample`; planning uses `route_plan.primary_skill='aggregate_and_rank'`.

### 3. Lab pilot — missing `threshold_ref` fallback

| Env | Same lab flags as happy path |
|-----|------------------------------|
| Candidate | Valid aggregate plan **without** `threshold_ref` in parameters |

| Trace field | Value |
|-------------|-------|
| `operation_authoritative_applied` | `false` |
| `authority_fallback_reason` | `missing_required_threshold_ref` |
| `authority_holder` | `legacy_selected_skill` |
| `response.selected_skill` | `attack_discovery` |

No default injected for `threshold_ref` or `time_window`.

---

## Pilot observation rule (COE)

- **Scope:** `cov.q046.excessive_failed_logins_sample` only.
- **No pattern #2** and no second allowlist `coverage_id` until this pilot runs clean with **zero unexpected disagreements** in the observation window (proceed order step 7).
- **Log:** [stage3l_s3_cov_q046_observation_log.md](stage3l_s3_cov_q046_observation_log.md)

---

## Verification run

```bash
cd backend && python3 -m pytest app/tests/test_route_authority_gate_stage3l_s3_3a.py -q
cd backend && python3 -m pytest app/tests/test_route_authority_step3_stage3l_s3.py -q
cd backend && python3 -m pytest
python3 -m test_harness.harness.runner --json
python3 scripts/capture_stage3l_s3_coe_pilot_traces.py
```

| Check | Result |
|-------|--------|
| Backend pytest | 587 passed |
| Harness | 6/6 |
| COE trace capture | 3/3 scenarios match expected apply/fallback |
