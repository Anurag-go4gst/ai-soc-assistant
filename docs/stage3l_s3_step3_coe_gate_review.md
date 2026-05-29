# Stage 3L-S3 Step 3: COE Gate Review — `cov.q046.excessive_failed_logins_sample`

**Date:** 2026-05-29  
**Type:** Gate review (no implementation).  
**Pilot under review:** `cov.q046.excessive_failed_logins_sample` — **candidate only, not approved.**  
**References:** [Step 3 gate design](stage3l_s3_step3_coverage_gate_design.md) (`e412c7c`), [trace checkpoint](stage3l_s3_trace_review_checkpoint.md) (`df11095`).

---

## Verdict

| Outcome | Meaning |
|---------|---------|
| **NOT READY for S3 Step 3 implementation** | Engineering preconditions largely satisfied for *design*; **COE approval missing**; **authority fallback not implemented or tested** |

Do **not** start Step 3 code until every **Blocker** row below is cleared and COE signs the review table at the bottom.

---

## Review checklist

| # | Question | Result | Evidence / notes |
|---|----------|--------|------------------|
| 1 | Does COE approve `cov.q046` as the first pilot `coverage_id`? | **Blocker — No** | Gate design sign-off table is unchecked ([`stage3l_s3_step3_coverage_gate_design.md`](stage3l_s3_step3_coverage_gate_design.md)). Pilot is explicitly **not** approved operation-authoritative behavior. |
| 2 | Is the manifest row stable and reviewed? | **Pass (engineering)** | Row in [`pattern_coverage_v1.json`](../backend/app/coverage/pattern_coverage_v1.json): `primary_skill=aggregate_and_rank`, `pattern_id=top_failed_okta_login_users`, `coverage_group=template_only`, `readiness=coe_synthetic_fixture`, governance execution flags false. Q4 test `test_sample_template_matches_route_plan_shape` asserts template match for this id. **COE:** confirm row text/notes acceptable for pilot. |
| 3 | Does the route-plan fixture pass validator consistently? | **Pass** | R1 `_valid_aggregate_plan()` / R2 `_valid_route_plan_candidate()` use same shape; `test_mock_candidate_validation_path_is_observational` asserts `validation_result.is_valid` and `primary_skill=aggregate_and_rank`. S1 catalog tests cover `aggregate_and_rank` / `top_n`. |
| 4 | Is bridge status compatible? | **Pass (mock path)** | Trace review: `attack_discovery` + `aggregate_and_rank` → `bridge_status=compatible` ([checkpoint](stage3l_s3_trace_review_checkpoint.md) case 1b). Live `/chat` without shadow candidate → `not_evaluated` (expected). |
| 5 | Is `route_authority_compare` clean for this case? | **Pass (mock path)** | `test_route_authority_compare_with_mock_candidate`: `compatible`, `operation_authoritative_enabled=false`, disagreements empty on bridge path; top-level shadow `disagreements` separate from `intent_bridge_disagreements`. |
| 6 | Is fallback-to-`selected_skill` explicitly tested? | **Gap — No** | No Step 3 authority path exists yet. No `authority_fallback_reason` or tests for “allowlist miss / bridge incompatible → keep `selected_skill`”. **Required before or with Step 3 implementation**, not optional. |
| 7 | Is `operation_authoritative_enabled` still false by default? | **Pass** | `Settings.route_authority_operation_authoritative_enabled: bool = False` ([`config.py`](../backend/app/config.py)); `.env.example` `ROUTE_AUTHORITY_OPERATION_AUTHORITATIVE_ENABLED=false`; compare tests assert false on every `/chat` response. |
| 8 | Is there a kill switch? | **Pass** | Global: `ROUTE_AUTHORITY_OPERATION_AUTHORITATIVE_ENABLED=false` (design: must stay false until COE). Compare-only mode: `ROUTE_AUTHORITY_COMPARE_ENABLED` (default true). No per-id allowlist env wired yet (correct — Step 3 not built). |
| 9 | Are Experience Center and harness expectations unchanged? | **Pass** | `test_experience_center_unchanged` (S2A.1 + S3 compare tests): `route_plan_shadow=null` on demo. Harness 6/6 unchanged (no `cov.q046` in harness YAML). No `expected_skill` drift from Steps 1–2. |
| 10 | Is there a rollback path? | **Pass (design)** | Rollback = set `ROUTE_AUTHORITY_OPERATION_AUTHORITATIVE_ENABLED=false` and clear allowlist (when added). No code path today sets authority true. Redeploy prior image / env without allowlist. Document in runbook when Step 3 ships. |

---

## Explicit blocks (unchanged)

| Item | Gate |
|------|------|
| `entity_context_lookup` as primary | **Blocked** — no primary fixture |
| `notable_risk_lookup` as primary | **Blocked** — post-enrichment only |
| `cov.q007.dga_detection_binding` | **Blocked** — detection-dependent / preflight |

---

## Pilot row summary (`cov.q046`)

| Field | Value |
|-------|--------|
| Question | Which users have excessive failed logins? |
| Legacy intent (typical router) | `attack_discovery` |
| Runtime `primary_skill` | `aggregate_and_rank` |
| `pattern_id` | `top_failed_okta_login_users` |
| `template_ref` | `sample_auth_failed_login_top_users_tstats` |
| `sample_only` / execution | `true` / all execution flags false |

**COE note:** `clarification_required` includes `threshold_ref`, `time_window` — authority migration must not bypass analyst threshold policy.

---

## Conditions to start Step 3 **implementation**

1. **COE** checks “Pilot `cov.q046` approved for **implementation**” on gate design sign-off (separate from approving this review doc).
2. **Engineering** delivers Step 3 PR with:
   - Allowlist env + gate chain from design doc
   - Explicit fallback tests (incompatible bridge, validator block, not on allowlist, global kill switch false)
   - Harness/EC unchanged for non-pilot paths (regression proof)
   - Rollback note in commit / ops snippet
3. **No** authority for blocked skills/rows listed above.

---

## COE sign-off (this gate review)

| Reviewer | Gate review acknowledged | Approve `cov.q046` for Step 3 **implementation** | Date |
|----------|--------------------------|-----------------------------------------------------|------|
| COE / Anurag | ☐ | ☐ | |

Approving this document records checklist outcomes; it does **not** by itself enable operation-authoritative behavior.

---

## Verification run (2026-05-29)

```bash
cd backend && python3 -m pytest \
  app/tests/test_pattern_coverage_pack_stage3k_q4.py::test_sample_template_matches_route_plan_shape \
  app/tests/test_route_plan_stage3k_r2.py::test_mock_candidate_validation_path_is_observational \
  app/tests/test_intent_operation_bridge_shadow_stage3l_s2a1.py \
  app/tests/test_route_authority_compare_stage3l_s3.py -q
python3 -m test_harness.harness.runner --json  # 6/6
```
