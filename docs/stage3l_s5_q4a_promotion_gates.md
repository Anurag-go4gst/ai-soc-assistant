# Stage 3L-S5: Q4A Promotion Gates

**Status:** S5 author-time gates done; **S5.1** committed-manifest audit in backend (2026-05-29). Q4A still never writes the manifest.

**Purpose:** Deterministic checklist before a human copies a draft `entry` into `backend/app/coverage/pattern_coverage_v1.json`.

## Gates (`evaluate_promotion_gates`)

| Gate ID | Requirement |
|---------|-------------|
| `registry_validation_clean` | Manifest entry validator returns no errors (draft: strict; committed: fixture-aware) |
| `coverage_id_not_in_manifest` | `coverage_id` not already present in committed manifest |
| `route_plan_primary_skill_matches_entry` | `route_plan_shape.primary_skill` == `entry.primary_skill` |
| `operation_type_allowed_for_skill` | `operation_type` in `runtime_skill_catalog.py` allowlist |
| `route_plan_validator_pass` | `validate_route_plan_candidate` valid |
| `template_promotion_policy` | No `template_ref`, or production (non-`sample_only`) template |
| `readiness_or_documented_blockers` | `dependency_missing` only when `expected_blockers` documented |
| `governance_flags_false` | All execution/synthesis flags false |

`manifest_copy_ready` is true only when every gate passes.

## Authority pilot (separate)

Additional checks on the same entry for Step 3 pilot readiness (`authority_pilot_ready`):

- Same manifest gates (including duplicate rule — existing manifest rows fail `coverage_id_not_in_manifest` by design)
- `authority_pilot_question_ref` == `q0.q046`
- `authority_pilot_coverage_id` == `cov.q046.excessive_failed_logins_sample`
- `coe_signoff_recorded` — always false until COE approves Step 3 implementation

## CLI

```bash
export PYTHONPATH=backend
python tools/coverage_authoring/coverage_drafter.py \
  --question-ref q046 \
  --check-promotion

python tools/coverage_authoring/coverage_drafter.py \
  --entry-json path/to/entry.json \
  --check-promotion
```

Exit code `0` when `manifest_copy_ready`; `1` otherwise.

## S5.1 — Committed manifest audit (backend)

Canonical implementation: [`backend/app/coverage/manifest_promotion_gates.py`](../backend/app/coverage/manifest_promotion_gates.py)
Audit helper: [`backend/app/coverage/manifest_promotion_audit.py`](../backend/app/coverage/manifest_promotion_audit.py)

| Mode | Use |
|------|-----|
| `draft` | New row before manual copy (`coverage_id_not_in_manifest`) |
| `committed` | Every row already in `pattern_coverage_v1.json` (`coverage_id_in_manifest`) |

```bash
export PYTHONPATH=backend
python tools/coverage_authoring/check_manifest_promotion.py
python tools/coverage_authoring/check_manifest_promotion.py --json
```

`pytest`: `app/tests/test_manifest_promotion_audit_stage3l_s5.py` — fails CI if any committed row regresses.

Does **not** block `/chat`; trust signal only.

## Manual promotion (unchanged)

1. Pass promotion gates for a **new** `coverage_id`.
2. Human review draft JSON.
3. Manually copy `entry` into `pattern_coverage_v1.json`.
4. Regenerate S6 map: `--emit-runtime-map`
5. Run `cd backend && python3 -m pytest app/tests/test_pattern_coverage_pack_stage3k_q4.py`
