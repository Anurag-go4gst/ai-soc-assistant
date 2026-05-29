# Stage 3L-S1: Runtime Operation Contract Validator Spec

**Status:** Complete (2026-05-29). S0 sign-off recorded; S1-1 gate (`sequence_detection` primary test) passed; S1-6/S1-7 shipped with code.

**S1 commit:** — (record hash here when committed; spine [STAGE_3L_S0_TO_S8_SPINE.md](../plans/STAGE_3L_S0_TO_S8_SPINE.md))

**Delivered:** Runtime operation validator v2 — `operation_type` per-skill enforcement, slot shape checks, contract-driven `allows_sub_invocations`, catalog governance/examples tests, Q4 + Q0.5 conformance, normalizer fix for bindable `detection_ref` preservation.

## Gate

- Source: [`docs/stage3l_s0_runtime_operation_contract_audit.md`](stage3l_s0_runtime_operation_contract_audit.md) — **Approved**

## S1 completion criteria (not optional trailing work)

| Criterion | Work item |
|-----------|-----------|
| **S1-1 exit gate** | Valid **primary** `sequence_detection` route plan exists and **passes** validator (first primary exercise of this skill) |
| **S1 done** | S1-1 through S1-5 **and** S1-6 (Q4 manifest) **and** S1-7 (Q0.5 doc) — enum drift reopens if 6/7 slip after code-only ship |

## Locked `operation_type` vocabulary

**Authority:** Per-skill `allowed_operation_types` in [`backend/app/routing/runtime_skill_catalog.py`](../backend/app/routing/runtime_skill_catalog.py).

**Validator rule:** For `route_status == route_ready` and non-empty `primary_skill`, require  
`operation_type in get_skill_contract(primary_skill)["allowed_operation_types"]`.  
**Blocking finding:** `operation_type_not_allowed_for_skill:{primary_skill}:{operation_type}`.

See S0 audit for full per-skill allowlists.

## Q4 manifest alignment (S1 work item S1-6)

| Today (manifest) | primary_skill | Change to |
|------------------|---------------|-----------|
| `threshold` | threshold_anomaly | `threshold_check` |
| `correlate_lookup` | lookup_correlation | `ioc_correlation` |

Update [`backend/app/coverage/pattern_coverage_v1.json`](../backend/app/coverage/pattern_coverage_v1.json) and [`app/tests/test_pattern_coverage_pack_stage3k_q4.py`](../backend/app/tests/test_pattern_coverage_pack_stage3k_q4.py).

## Enforcement table

| contract_field | enforcement_layer | rule | consumer_module | test_work_items | non_goals |
|----------------|-------------------|------|-----------------|-----------------|-----------|
| `allowed_operation_types` | validator | `operation_type` must be in contract allowlist for `primary_skill` when `route_ready` | `route_plan_validator` — new `_validate_operation_type` | `test_route_plan_stage3k_r1.py`: invalid `operation_type` per skill; valid Q4 pairs after manifest fix | Global enum in models; changing catalog allowlists without audit |
| `required_slots` | validator | Extend value constraints: `threshold_ref`, `lookup_ref`, `detection_ref`, `match_field` structured/non–free-text; reuse aggregate patterns for metric/group_by where applicable | `_validate_skill_slots` + new per-skill helpers (e.g. `_validate_threshold_parameters`) | New tests in `test_route_plan_stage3k_r1.py` or `test_route_plan_contract_stage3l_s1.py` for threshold/lookup/detection skills | Enforcing catalog `hard_preconditions`; all 10 skills deep-validated in one commit if too large — split by skill family |
| `allows_sub_invocations` | validator | If `sub_invocations` non-empty, require `contract["allows_sub_invocations"] is True`; if False, block any sub_invocations | `_validate_composition` | Sub_invocations on skill with `allows_sub_invocations: false` (simulate via plan, not catalog edit) | Nested depth beyond existing multi-signal rules |
| `governance_constraints` | test_only | Each catalog entry: non-empty list; every token in S0 global allowlist | — | `test_runtime_skill_governance_constraints_stage3l_s1.py` | Runtime rejection on missing constraint |
| `examples` | test_only | Each catalog entry: ≥1 non-empty example string | — | `test_runtime_skill_examples_stage3l_s1.py` | NLP quality / near-miss scoring |
| `non_examples` | test_only | Each catalog entry: ≥1 non-empty non_example string | — | same file as examples | same |

## Work items (ordered)

1. **S1-1** — `allowed_operation_types` validator + tests (**includes mandatory `sequence_detection` primary gate**)
2. **S1-6** — Q4 manifest `operation_type` alignment + Q4 tests (**same S1 completion**)
3. **S1-2** — `required_slots` value constraints (threshold, lookup, detection families)
4. **S1-3** — contract-driven `allows_sub_invocations`
5. **S1-4 / S1-5** — governance + examples catalog tests
6. **S1-7** — Q0.5 doc token alignment (**same S1 completion**, not deferred)

## Global S1 non-goals

- No change to `/chat` `selected_skill` or deterministic intent router authority
- No MCP or SPL execution; no workflow `execution_enabled`
- No replacement of legacy four router skills (`SKILL_ENUM`)
- No runtime enforcement of catalog `hard_preconditions` (S7)
- No `output_artifacts` / renderer changes (S2)

## Verification (after implementation)

```bash
cd backend && python3 -m pytest app/tests/test_route_plan_stage3k_r1.py app/tests/test_pattern_coverage_pack_stage3k_q4.py -q
cd backend && python3 -m pytest
python3 -m test_harness.harness.runner --json
```
