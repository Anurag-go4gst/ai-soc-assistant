# Stage 3L-S0: Runtime Operation Contract Audit

**Status:** S0-core signed off 2026-05-29. S1 implemented per [validator spec](stage3l_s1_validator_spec.md).

**Scope:** Audit only. No runtime behavior change in this document.

**Sources reviewed:**

- [`backend/app/routing/runtime_skill_catalog.py`](../backend/app/routing/runtime_skill_catalog.py)
- [`backend/app/routing/route_plan_validator.py`](../backend/app/routing/route_plan_validator.py)
- [`backend/app/routing/route_plan_preflight.py`](../backend/app/routing/route_plan_preflight.py)
- [`backend/app/tests/test_route_plan_stage3k_r1.py`](../backend/app/tests/test_route_plan_stage3k_r1.py)
- [`backend/app/coverage/pattern_coverage_v1.json`](../backend/app/coverage/pattern_coverage_v1.json)
- [`docs/soc_runtime_skill_route_plan_stage3k_q05.md`](soc_runtime_skill_route_plan_stage3k_q05.md) (design prose; not runtime authority)

---

## Sign-off

| Role | Decision | Date |
|------|----------|------|
| S0-core reviewer | ☑ Approved — unlock S1 implementation | 2026-05-29 |
| Pre-sign-off checklist | ☑ Three uncertain cells verified (below) | 2026-05-29 |
| | ☑ Three-source conformance list accepted | 2026-05-29 |
| | ☑ All 10 operations have non-empty allowlists; fixture notes documented | 2026-05-29 |
| Notes | Human + code verification aligned. S1 gates: `sequence_detection` primary test required in S1-1; S1-6/S1-7 same completion as code. | |

---

## Code verification of uncertain cells

These rows were **re-checked in source** (not carried from draft assumptions).

### 1. `required_slots` — value-checking today?

**Verdict: presence-only except `aggregate_and_rank`.**

| Check | Location | Finding |
|-------|----------|---------|
| Slot presence | `route_plan_validator._validate_skill_slots` L125–127 | `threshold_ref`, `lookup_ref`, `detection_ref`, `match_field`, `group_by`, `metric`: blocked only if `not parameters.get(slot)` (truthy). No shape/type rules. |
| Deep metric/group_by | `_validate_aggregate_parameters` L133–135 | **Early return** unless `primary_skill == aggregate_and_rank`. |
| Non-aggregate skills | Same file | No other `_validate_*_parameters` helpers. |

So “**stronger required_slots**” in S1 is justified by code: non-aggregate skills do not get aggregate-style value checks today.

### 2. `allows_sub_invocations` — read from contract or hardcoded?

**Verdict: hardcoded; catalog field unused by validator.**

| Check | Location | Finding |
|-------|----------|---------|
| Sub-invocation gate | `_validate_composition` L226–227 | `if sub_invocations and primary_skill != RuntimeSkill.MULTI_SIGNAL_CORRELATION.value` — compares **enum constant**, not `contract["allows_sub_invocations"]`. |
| Catalog | `runtime_skill_catalog.py` | All entries define `allows_sub_invocations` (only `multi_signal_correlation` is `True`). **Grep:** field never read outside catalog + R1 presence test. |

S1-3 (“read from contract”) matches a real gap, not an assumption.

### 3. `parameters.exclusions` validation — aggregate-only?

**Verdict: applies to any route plan that includes `parameters.exclusions` (not gated on `aggregate_and_rank`).**

| Check | Location | Finding |
|-------|----------|---------|
| Call site | `validate_route_plan_candidate` L35 | `_validate_exclusions(plan, …)` always runs. |
| Guard inside | `_validate_exclusions` L169–172 | Only checks `parameters` is a dict; **no `primary_skill` check**. |
| Test coverage | `test_route_plan_stage3k_r1.py` `test_clean_route_ready_aggregate_plan_passes` | Exclusions exercised on an aggregate plan; that does not limit the validator. |

**Audit note:** `exclusions` is listed under `optional_slots` for aggregate/threshold/sequence in the catalog; enforcement is global when the key is present. No S1 change required unless you want exclusions restricted by skill (not in current S1 lock).

---

## Conformance alignment (three sources → code catalog)

All external vocabularies **anchor to** [`runtime_skill_catalog.py`](../backend/app/routing/runtime_skill_catalog.py) in S1:

| Source | Role | S1 work item |
|--------|------|--------------|
| **Code catalog** | **Authority** for validator `operation_type` allowlists | S1-1 validator |
| **Q4 manifest** [`pattern_coverage_v1.json`](../backend/app/coverage/pattern_coverage_v1.json) | Committed route-plan shapes; drift vs catalog | **S1-6** |
| **Q0.5 design doc** [`soc_runtime_skill_route_plan_stage3k_q05.md`](soc_runtime_skill_route_plan_stage3k_q05.md) | Prose/tables; drift vs catalog | **S1-7** |

Tests and LLM fixtures are a fourth check surface but not a conformance “source of truth.”

---

## Catalog completeness and fixture coverage

### Allowlists (all 10 operations)

**Verified:** every entry in `RUNTIME_SKILL_CATALOG` has a **non-empty** `allowed_operation_types` list (2–4 tokens each). No empty allowlist; no default-needed gap.

### `primary_skill` + `operation_type` in repo fixtures (dead-fixture check)

| primary_skill | In Q4 manifest? | In backend route-plan tests? | Notes |
|---------------|-----------------|------------------------------|--------|
| aggregate_and_rank | Yes (`top_n`) | Yes | |
| threshold_anomaly | Yes (`threshold` — **invalid** vs catalog) | Via multi_signal sub-invocations only | Fix in S1-6 |
| lookup_correlation | Yes (`correlate_lookup` — **invalid**) | No dedicated primary test | Fix in S1-6 |
| behavioral_detection_binding | Yes | Q3 tests reference skill | |
| multi_signal_correlation | Yes | Yes | |
| entity_timeline | Yes | No dedicated test | Allowlist valid (`timeline` in manifest) |
| metadata_discovery | No | Yes (`field_discovery`) | Not dead |
| sequence_detection | No | Catalog test only | **Gap (real):** no primary `route_plan` fixture yet — headline SOC op never exercised as primary. **S1-1 exit gate:** primary plan + passing validator test required before S1-1 is done. |
| entity_context_lookup | No | Post-enrichment only | **Intended:** primary operation is enrichment/chaining after another skill; no primary fixture required. Do not “fix” in S6/S1. |
| notable_risk_lookup | No | Post-enrichment only | **Intended:** same as `entity_context_lookup` — post-enrichment and ranking follow-on, not a standalone primary route in current pack. |

**S1 implication:** Allowlists are populated for all 10. Only `sequence_detection` needs a new primary route-plan fixture in S1-1 (mandatory exit criterion, not optional coverage).

---

## Canonical `operation_type` decision

**Authority:** Per-skill `allowed_operation_types` in [`runtime_skill_catalog.py`](../backend/app/routing/runtime_skill_catalog.py) is the **only** canonical allowlist for route-plan `operation_type` validation.

**Rule (S1):** When `route_status` is `route_ready` and `primary_skill` is set, `operation_type` must be a member of `get_skill_contract(primary_skill)["allowed_operation_types"]`. Otherwise blocking finding: `operation_type_not_allowed_for_skill:{primary_skill}:{operation_type}`.

**Not chosen:** A single global `OperationType` enum in `route_plan_models.py` (would fight per-skill variation).

### Per-skill allowlists (canonical)

| primary_skill | allowed_operation_types |
|---------------|-------------------------|
| aggregate_and_rank | `top_n`, `bottom_n`, `rank`, `aggregate` |
| threshold_anomaly | `threshold_check`, `baseline_compare`, `spike_detection` |
| sequence_detection | `sequence_match`, `ordered_pattern` |
| lookup_correlation | `lookup_match`, `lookup_exclusion`, `ioc_correlation` |
| behavioral_detection_binding | `detection_binding`, `detection_lookup` |
| metadata_discovery | `field_discovery`, `source_discovery`, `schema_discovery` |
| entity_context_lookup | `entity_lookup`, `asset_lookup`, `identity_lookup` |
| notable_risk_lookup | `risk_lookup`, `notable_lookup` |
| multi_signal_correlation | `correlate_signals`, `combine_sub_results` |
| entity_timeline | `timeline`, `event_sequence` |

### Three-way drift (resolved for S1)

| Artifact | Drift | S1 remediation |
|----------|-------|----------------|
| Q0.5 design doc | Uses prose names (e.g. `rank_by_count`, `threshold_count`, `spike`) and extra types not in catalog | **Docs alignment:** update Q0.5 tables to catalog tokens (no runtime change) |
| Q4 manifest | Uses `threshold`, `correlate_lookup` not in catalog allowlists | **Manifest alignment:** rename in `pattern_coverage_v1.json` (see table below) |
| Tests / LLM fixtures | Mostly `top_n` (valid) | No change unless tests assert invalid pairs |

### Q4 manifest drift (fix in S1)

| coverage entry (approx.) | Today `operation_type` | primary_skill | Canonical `operation_type` |
|--------------------------|------------------------|---------------|----------------------------|
| threshold-style row | `threshold` | threshold_anomaly | `threshold_check` |
| IOC lookup rows | `correlate_lookup` | lookup_correlation | `ioc_correlation` |
| Other rows | `top_n`, `detection_binding`, `correlate_signals`, `timeline` | *(varies)* | Already valid |

---

## Contract field audit

| field | currently_enforced | current_consumer | future_status | risk_if_not_enforced | enforcement_cost | tests_needed |
|-------|-------------------|------------------|---------------|----------------------|------------------|--------------|
| `skill_id` | N/A (catalog key) | `get_skill_contract` | descriptive | Low | — | — |
| `purpose` | No | — | descriptive | Low | — | — |
| `allowed_operation_types` | No (presence only in R1 catalog test) | — | **enforce_in_S1** | LLM/user can set `operation_type` incompatible with skill (e.g. `top_n` on `lookup_correlation`) | Low: one validator helper | Extend `test_route_plan_stage3k_r1.py`; invalid pair per skill |
| `required_slots` | **Partial** — presence for listed slots; deep value rules only for `aggregate_and_rank` | `route_plan_validator._validate_skill_slots`, `_validate_aggregate_parameters` | **enforce_in_S1** (value constraints) | Wrong metric/group_by/threshold/lookup/detection shapes pass validation | Medium: per-skill slot validators | Slot typing tests for `threshold_anomaly`, `lookup_correlation`, `behavioral_detection_binding`, `sequence_detection` |
| `optional_slots` | No | — | descriptive | Low | — | — |
| `hard_preconditions` (catalog) | No cross-check to plan; plan field `hard_preconditions` required but not validated against catalog | Preflight uses **separate** keyword/heuristic paths (`THRESHOLD_TRIGGERS`, IOC/detection triggers) | **defer_S7** | False `route_ready` when dependencies missing | High (registry + coverage + preflight union) | S7 integration tests |
| `allowed_post_enrichments` | **Yes** | `_validate_post_enrichment` | keep (no S1 change) | — | — | Existing R1 tests |
| `allows_sub_invocations` | **Hardcoded** — validator compares `primary_skill` to `MULTI_SIGNAL_CORRELATION` constant; **never reads** `contract["allows_sub_invocations"]` (verified L226–227) | `_validate_composition` | **enforce_in_S1** | Catalog field is documentation-only today | Low: read `contract["allows_sub_invocations"]` | `test_sub_invocations_under_non_multi_signal_are_blocked` already covers behavior; add assertion that logic uses contract after S1-3 |
| `governance_constraints` | No (presence only in R1 catalog test) | — | **test_only_in_S1** | Drift in governance metadata undetected | Low: catalog unit test | `test_runtime_skill_governance_constraints_stage3l_s1.py` — non-empty list + allowed token subset per skill |
| `examples` | No (presence only) | — | **test_only_in_S1** | Near-miss documentation missing for authors/LLM | Low | Catalog test: ≥1 non-empty string per operation |
| `non_examples` | No (presence only) | — | **test_only_in_S1** | Same | Low | Catalog test: ≥1 non-empty string per operation |

### `required_slots` detail (S1 scope hint for spec author)

| Slot / area | Today | S1 target |
|-------------|-------|-----------|
| `group_by`, `metric` (aggregate) | Enforced (metric `MetricType`, group_by not metric expression) | Keep; reference as pattern for other skills |
| `threshold_ref` | Presence only | Structured object (e.g. `policy_id` or approved ref key); reject free-text-only strings |
| `lookup_ref` | Presence only | Structured object aligned with IOC registry binding shape |
| `detection_ref` | Presence only | Registry-bound string or structured ref; no invented IDs |
| `match_field` | Presence only | Non-empty string; optional allowlist per lookup family in S1 or S7 |
| `entities`, `time_window`, `source_class`, `domain` | Presence via plan top-level or parameters | Keep presence; optional format normalization in normalizer (S1 only if S0 confirms) |

### Allowed governance constraint tokens (S1 test-only baseline)

Use union across catalog today:  
`no_spl_execution`, `candidate_plan_only`, `deterministic_validation_required`, `no_model_authored_threshold_policy`, `no_llm_authored_detection_spl`, `no_write_actions`, `no_external_threat_intel_call`, `local_lookup_only`, `no_post_enrichment`, `no_behavioral_binding`, `no_action_chain`, `read_only`, `approved_context_only`, `max_depth_2`, `no_nested_multi_signal`, `no_nested_sub_invocations`, `entity_must_be_explicit`.

S1 tests: each operation has ≥1 constraint; each constraint token ∈ global allowlist above.

---

## S1 scope lock (from this audit)

| ID | S1 work item | Layer |
|----|--------------|-------|
| S1-1 | `operation_type` ∈ per-skill `allowed_operation_types` | validator |
| S1-2 | Strengthen `required_slots` value constraints (beyond aggregate) | validator |
| S1-3 | `allows_sub_invocations` from contract, not hardcoded skill name | validator |
| S1-4 | `governance_constraints` catalog tests | test_only |
| S1-5 | `examples` / `non_examples` non-empty catalog tests | test_only |
| S1-6 | Align Q4 manifest `operation_type` values to catalog | manifest + Q4 tests |
| S1-7 | Align Q0.5 doc operation type prose to catalog tokens | docs only |

**Explicitly out of S1:** catalog `hard_preconditions` runtime enforcement (S7); `purpose` / `optional_slots` enforcement; near-miss route fixtures unless added during S1 spec review.

---

## S0-parallel (non-blocking) references

These items do **not** gate S1:

- [`plans/STAGE_3L_S0_TO_S8_SPINE.md`](../plans/STAGE_3L_S0_TO_S8_SPINE.md) — create when convenient
- Dual-run inventory: `/chat` `selected_skill` + `route_plan_shadow`; 3J-K0 `skill_router` compare; Q1F `primary_skill` disagreements
- Migration consumers for S3 Step 3+: `demo/scenarios.py`, `test_harness/cases/test_cases.yaml`, `workflow_planner.py`

---

## Verification (S0 — audit only)

No code changes required. Confirm audit against repo:

```bash
cd backend && python3 -m pytest app/tests/test_route_plan_stage3k_r1.py -q
```
