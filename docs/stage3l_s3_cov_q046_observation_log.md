# Stage 3L-S3 cov.q046 Observation Log

**Pilot:** `cov.q046.excessive_failed_logins_sample`  
**COE sign-off:** [stage3l_s3_step3_coe_gate_review.md](stage3l_s3_step3_coe_gate_review.md) (2026-05-29)  
**Capture script:** `python3 scripts/capture_stage3l_s3_coe_pilot_traces.py`  
**Machine-readable baseline:** [stage3l_s3_step3_coe_pilot_verification_traces.json](stage3l_s3_step3_coe_pilot_verification_traces.json)

---

## Config

### Production defaults

```text
ROUTE_AUTHORITY_OPERATION_AUTHORITATIVE_ENABLED=false
ROUTE_AUTHORITY_OPERATION_COVERAGE_ALLOWLIST=
```

### Lab pilot config

```text
ROUTE_AUTHORITY_OPERATION_AUTHORITATIVE_ENABLED=true
ROUTE_AUTHORITY_OPERATION_COVERAGE_ALLOWLIST=cov.q046.excessive_failed_logins_sample
```

**Lab candidate requirements (no defaults):** `threshold_ref` and `time_window` must be present in validated `route_plan_parameters` (or `route_plan_time_window`) or authority falls back.

**Baseline query:** `Find top 10 users with failed Okta logins in the last 24 hours.`

---

## Expansion rule

No second `coverage_id` until `cov.q046` runs clean with **zero unexpected disagreements** for the agreed observation window.

| Observation window | Status |
|--------------------|--------|
| Start | 2026-05-29 |
| End | *TBD — COE closes proceed-order step 7* |
| Unexpected disagreements | *Record per entry below* |

---

## Blocked (out of pilot scope)

- `entity_context_lookup` as primary
- `notable_risk_lookup` as primary
- `cov.q007.dga_detection_binding`
- any non-allowlisted `coverage_id`

---

## Baseline captures (starting point)

**Recorded:** 2026-05-29 · **Commit:** `81bc883` · **Method:** `capture_stage3l_s3_coe_pilot_traces.py` (mock `route_plan_shadow` candidate)

### 1. Default production-safe fallback

| Field | Value |
|-------|-------|
| Env | `AUTHORITATIVE_ENABLED=false`, allowlist empty |
| `coverage_id_resolved` | `cov.q046.excessive_failed_logins_sample` |
| `operation_authoritative_applied` | `false` |
| `authority_fallback_reason` | `global_kill_switch_disabled` |
| `authority_holder` | `legacy_selected_skill` |
| `selected_skill` | `attack_discovery` |
| `execution.executed_spl` | `null` |

`authority_trace`: Operation authority not applied; legacy selected_skill remains authoritative. `fallback_reason='global_kill_switch_disabled'`.

**Expected:** ✅ matches design

---

### 2. Lab happy path

| Field | Value |
|-------|-------|
| Env | `AUTHORITATIVE_ENABLED=true`, allowlist `cov.q046.excessive_failed_logins_sample` |
| Candidate | `threshold_ref` + `time_window` in parameters |
| `operation_authoritative_applied` | `true` |
| `authority_fallback_reason` | `null` |
| `authority_holder` | `route_plan_primary_skill` |
| `planning_primary_skill` | `aggregate_and_rank` |
| `selected_skill` | `attack_discovery` (legacy preserved on `/chat` response) |
| `migration_phase` | `S3_step_3_cov_q046_pilot` |
| `execution.executed_spl` | `null` |

`authority_trace`: Operation authority applied for allowlisted coverage_id `cov.q046.excessive_failed_logins_sample`; planning uses `route_plan.primary_skill='aggregate_and_rank'`.

**Expected:** ✅ matches design

---

### 3. Lab missing threshold fallback

| Field | Value |
|-------|-------|
| Env | Same lab flags as happy path |
| Candidate | Valid aggregate plan **without** `threshold_ref` |
| `operation_authoritative_applied` | `false` |
| `authority_fallback_reason` | `missing_required_threshold_ref` |
| `authority_holder` | `legacy_selected_skill` |
| `selected_skill` | `attack_discovery` |

`authority_trace`: Operation authority not applied; `fallback_reason='missing_required_threshold_ref'`. No slot values injected.

**Expected:** ✅ matches design

---

## Observation window entries

Re-run capture during the window and append a row. Log any **unexpected** `authority_fallback_reason`, bridge/validator disagreements, or `selected_skill` drift.

| Date | Run | Mode | `operation_authoritative_applied` | `authority_fallback_reason` | Unexpected? | Notes |
|------|-----|------|-----------------------------------|-----------------------------|-------------|-------|
| 2026-05-29 | baseline-1 | default | `false` | `global_kill_switch_disabled` | no | Starting baseline |
| 2026-05-29 | baseline-2 | lab happy | `true` | — | no | Starting baseline |
| 2026-05-29 | baseline-3 | lab no threshold | `false` | `missing_required_threshold_ref` | no | Starting baseline |
| | | | | | | |

---

## How to record the next observation

```bash
cd /var/www/ai-soc-assistant
python3 scripts/capture_stage3l_s3_coe_pilot_traces.py
```

Compare stdout / `docs/stage3l_s3_step3_coe_pilot_verification_traces.json` to the baseline above. Add a row to **Observation window entries** only when running under lab or default config intentionally (not only pytest CI).

**Close criterion:** COE agrees observation window is clean → proceed-order step 7 complete → then discuss pattern #2 / second `coverage_id`.
