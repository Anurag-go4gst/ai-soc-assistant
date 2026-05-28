# Stage 3K-Q1C: Dry-Run Route-Plan to Template Matching

**Status:** Done (library-only; `/chat` wiring deferred to Q1E)

## Objective

Given a validated route plan, deterministically identify the best-matching SPL template (including the disabled Q1B sample templates) without rendering SPL, calling MCP, or executing anything. Answer: "Can this route plan be served by an available template?"

## Scope

- New module `app/spl/template_matcher.py` exposing a deterministic matcher.
- Match-key contract that maps validated route-plan fields to template metadata.
- Match result envelope: `matched_template_id`, `match_score`, `match_reasons`, `mismatch_reasons`, `candidate_template_ids`, `production_executable`.
- Backend tests covering positive match, no match, ambiguous match (tie-break), unsupported datamodel, unsupported field, disabled-but-matchable sample template.

## Non-Goals

- No SPL rendering (deferred to Q1D).
- No SPL execution.
- No MCP call. No MCP gate change.
- No live LLM synthesis. No Answer Guard.
- No promotion of `sample_only` templates to production.
- No analyst-facing UI surface in this stage (lineage exposure deferred to Q1E).
- No new template additions; matcher works against existing registry only.

## Match-Key Contract

Inputs from normalized route plan map deterministically to template fields. This contract is frozen before coding Q1C; the matcher implements exactly this table.

| Route-plan field | Template field |
|------------------|----------------|
| `primary_skill` | `supported_skill` / `aggregation_shape` (skill→shape mapping below) |
| `operation_type` | `aggregation_shape` / `operation_type` |
| `source_class` | `query_shape` + `datamodel` mapping |
| `group_by.field` | `group_by_fields` |
| `metric.type` | `allowed_metrics` |
| `metric.field` | `metric_fields` |
| `time_window` | `time_bound_required` satisfied |
| `limit` | `result_limit_required` satisfied |
| `validator_profile` | `validator_profile` |

Legacy mapping (already used in normalized route plans):

| Route-plan field | Template field | Required? |
|------------------|----------------|-----------|
| `runtime_skill` (e.g. `aggregate_and_rank`) | template `aggregation_shape` mapping | required |
| `evidence_needs.datamodel` | template `datamodel` | required |
| `evidence_needs.dataset` (optional) | template `dataset` | optional; if present must match |
| `evidence_needs.group_by` | template `group_by_fields` (subset / set-equal) | required for ranked / aggregate skills |
| `evidence_needs.metric` | template `metric_fields` / `allowed_metrics` | required for ranked / aggregate skills |
| `evidence_needs.cim_fields` (referenced) | template `cim_fields` | subset |
| `evidence_needs.summariesonly` (if set) | template `summariesonly_required` | exact bool |

Skill → aggregation_shape mapping:

| Runtime skill | Expected aggregation_shape |
|---------------|----------------------------|
| `aggregate_and_rank` | `ranked_entities` |
| `threshold_anomaly` | `ranked_entities` or `non_aggregate` |
| `metadata_discovery` | `non_aggregate` |
| `entity_timeline` | `timechart` (no current template — must return no-match) |
| others | no template available yet — return no-match with reason |

Tie-break rules (deterministic, in order):

1. Exact `datamodel` match.
2. Exact `operation_type` / `aggregation_shape` match.
3. Exact `group_by_fields` set-equal AND exact `metric` match over subset match.
4. `production_executable=True` over `sample_only=True`. `enabled=false` / `sample_only=true` candidates are only allowed in dry-run paths.
5. Smaller `cim_fields` superset (closer field profile).
6. If multiple candidates are still equal, return `matched=false` with reason `ambiguous_match` and the full candidate list. Never pick arbitrarily.

No-match shape (explicit, frozen):

```
matched_template_id = None
matched = false
match_score = 0.0
mismatch_reasons = ["no_template_supports_group_by_field", ...]
candidate_template_ids = []
production_executable = false
execution_authorized = false
```

Valid `mismatch_reasons` values (closed enum, expand only via plan change):

- `unknown_datamodel`
- `unsupported_group_by`
- `unsupported_metric`
- `no_template_for_skill`
- `time_window_not_satisfiable`
- `result_limit_not_satisfiable`
- `validator_profile_mismatch`
- `ambiguous_match`

## Implementation Plan

1. Add `app/spl/template_matcher.py` with `match_route_plan_to_template(normalized_route_plan, *, include_disabled=True) -> TemplateMatchResult`.
2. Define `TemplateMatchResult` dataclass: `matched_template_id`, `match_score (0.0-1.0)`, `match_reasons`, `mismatch_reasons`, `candidate_template_ids`, `production_executable`, `sample_only`, `validator_profile`, `datamodel`.
3. Build internal index keyed by `(query_shape, datamodel, aggregation_shape)` for O(1) candidate fetch.
4. Apply tie-break rules deterministically. Always return a result; `matched_template_id=None` is valid.
5. Expose `dry_run_matches(plan)` helper that returns the full candidate list with per-candidate scoring for inspection (used by Q1E lineage later).
6. Do NOT wire matcher into `/chat`. Matcher is library-level only this stage.

## Tests

`backend/app/tests/test_template_matcher_stage3k_q1c.py` (deterministic core)
`backend/app/tests/test_template_matcher_llm_assist_stage3k_q1c.py` (sidecar)

Deterministic core tests:

- Auth `aggregate_and_rank` + `Authentication` + `group_by=user` + `metric=count` → matches `sample_auth_failed_login_top_users_tstats`.
- Network `aggregate_and_rank` + `Network_Traffic` + `group_by=src_ip` + `metric=count` → matches `sample_network_top_outbound_src_tstats`.
- DNS `aggregate_and_rank` + `Network_Resolution` + `group_by=host` → matches `sample_dns_top_query_hosts_from_datamodel`.
- Unknown datamodel `MadeUp` → no match, mismatch reason `unknown_datamodel`.
- Unknown group_by field → no match, mismatch reason `unsupported_group_by`.
- `entity_timeline` skill → no match, mismatch reason `no_template_for_skill`.
- Disabled sample is matchable but `production_executable=False`.
- Ambiguous case (two templates same datamodel + group_by): tie-break yields stable, deterministic winner.
- Result is pure: same input always returns same output.

Sidecar tests (deterministic stub LLM adapter — no real LLM call in tests):

- Sidecar disabled (shadow off) → matcher result unchanged; no hints recorded.
- Sidecar returns valid hints aligned with deterministic outcome → hints recorded; no `disagreements`.
- Sidecar returns valid hints that disagree on datamodel → deterministic wins; `disagreements[]` entry recorded.
- Sidecar returns `template_id` field → adapter strips it; reason recorded.
- Sidecar returns SPL fragment → adapter strips it; reason `spl_in_hint_forbidden`.
- Sidecar returns unknown `datamodel_hint` → adapter drops the hint; reason `unknown_datamodel`.
- Reasoning model assigned to sidecar role → rejected with reason `reasoning_model_not_allowed_for_matching`.
- Sidecar timeout (soft 1.5s) → matcher proceeds without it; envelope shows `llm_assist_timed_out=true`.

## Verification

```bash
cd backend && python3 -m pytest app/tests/test_template_matcher_stage3k_q1c.py -x
cd backend && python3 -m pytest
python3 -m test_harness.harness.runner --json
TELEMETRY_MODE=none python3 -m test_harness.harness.runner --json
git diff --check
```

## LLM Role and Boundary

> LLM assistance is candidate-only. Deterministic core owns validation, normalization, binding, rendering, execution eligibility, and all blocking decisions. If LLM output disagrees with deterministic validation, deterministic wins and the disagreement is recorded.

Q1C ships in two modules:

- `app/spl/template_matcher.py` — deterministic core. Authoritative.
- `app/spl/template_matcher_llm_assist.py` — Instruct sidecar. Optional, shadow-only.

### LLM-Assist Sidecar (semantic hints only)

Input: user query + normalized route plan.

Output schema (strict, adapter-enforced):

```json
{
  "llm_semantic_hints": {
    "source_class_hint": "okta_authentication_logs | windows_security | ...",
    "datamodel_hint": "Authentication | Network_Traffic | ...",
    "field_aliases": {
      "<natural phrase>": "<approved CIM field>"
    }
  }
}
```

Adapter rules:

- `datamodel_hint` must be in `APPROVED_DATAMODELS`; otherwise dropped.
- Every `field_aliases` value must be in `DATAMODEL_FIELD_ALLOWLIST` for the resolved datamodel; unknown aliases dropped.
- Any `template_id` field in LLM output is stripped. LLM never picks `template_id`.
- Any SPL fragment in LLM output is stripped with reason `spl_in_hint_forbidden`.
- Schema-invalid output → dropped, reason `schema_invalid`.

Matcher contract with sidecar:

1. Run deterministic matcher against normalized route plan. This result is authoritative.
2. Run sidecar in parallel (time-budgeted, soft 1.5s timeout, then proceed without it).
3. Compare: if sidecar hints would have changed datamodel / group_by / metric, record `disagreements[]` in match result. Deterministic wins.
4. Sidecar output is recorded in `route_plan_shadow.template_match_llm_hints` only when shadow mode is enabled.

Gates:

- `ROUTING_LLM_SHADOW_ENABLED=true`.
- LLM Registry role `template_match_semantic_assist` configured with `model_family=instruct` only. Reasoning model rejected with reason `reasoning_model_not_allowed_for_matching`.

LLM must never: generate executable SPL, select MCP tools, invent `template_id`, decide route readiness, authorize execution, use confidence as authority.

## Fixture Honesty

Q1C tests use synthetic route-plan fixtures only. Each fixture is labelled `coe_synthetic_fixture=true`, `captured_live_run=false`, `production_execution=false`.

## Exit Criteria

- Route plan can match disabled sample templates with deterministic scoring.
- Unsupported fields / datamodels return no-match with explicit reasons.
- Sample templates remain `production_executable=False`.
- All existing backend tests still pass. Harness 6/6.
- Matcher is not yet called from `/chat` (wired in Q1E).
