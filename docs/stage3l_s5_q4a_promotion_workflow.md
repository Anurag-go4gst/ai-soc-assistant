# Stage 3L-S5.2: Q4A Promotion Workflow

**Status:** S5.2 formalized human-reviewed promotion path (2026-05-30).

**Purpose:** End-to-end workflow from Q4A draft to reviewed manifest row **without** automatic runtime promotion.

Gate reference: [stage3l_s5_q4a_promotion_gates.md](stage3l_s5_q4a_promotion_gates.md).

## Source of truth

| Artifact | Role |
|----------|------|
| `tools/coverage_authoring/drafts/*.json` | Author-time drafts only |
| `backend/app/coverage/pattern_coverage_v1.json` | Committed runtime manifest (human edit only) |
| Closed registries | Templates, lookups, detections, evidence contracts, runtime skills |

Q4A **never** writes the committed manifest. Promotion candidate artifacts are review-only.

## Workflow

### 1. Generate Q4A draft

```bash
export PYTHONPATH=backend
python tools/coverage_authoring/coverage_drafter.py --question-ref q004
```

Output: `tools/coverage_authoring/drafts/draft_<timestamp>_<slug>.json` with `draft_only=true`, `requires_human_review=true`, `promoted_to_manifest=false`.

### 2. Draft schema validation

Draft wrapper fields are enforced by [`draft_schema.py`](../tools/coverage_authoring/draft_schema.py). Optional LLM assist remains candidate-only (Instruct offline file).

### 3. Closed-world ref validation

```bash
python tools/coverage_authoring/coverage_drafter.py --validate-draft tools/coverage_authoring/drafts/<draft>.json
```

[`validator.py`](../tools/coverage_authoring/validator.py) checks `template_ref`, `lookup_ref`, `detection_ref`, `evidence_contract_ref`, `primary_skill`, readiness labels, governance flags.

### 4. Operation contract v2 validation

Route plan `operation_type` must be in the per-skill allowlist in [`runtime_skill_catalog.py`](../backend/app/routing/runtime_skill_catalog.py). Enforced via promotion gates (`route_plan_validator_pass`, `operation_type_allowed_for_skill`).

### 5. Evidence contract validation

Evidence contract must exist in the closed catalog unless `dependency_missing` with documented `expected_blockers`.

### 6. Readiness label validation

- No readiness overclaim: `dependency_missing` requires `expected_blockers`.
- No `sample_only` template promotion (non-fixture rows).

### 7. Human review

Reviewer checklist (also embedded in promotion candidate artifact):

- Readiness and blockers match SOC intent
- Governance execution flags all false
- Route plan shape matches `entry.primary_skill`
- SOC-facing doc update if the promoted row changes demo coverage

### 8. Promotion candidate artifact (S5.2)

```bash
python tools/coverage_authoring/coverage_drafter.py \
  --entry-json tools/coverage_authoring/drafts/<draft>.json \
  --promotion-candidate

python tools/coverage_authoring/coverage_drafter.py \
  --entry-json tools/coverage_authoring/drafts/<draft>.json \
  --promotion-candidate \
  --promotion-candidate-output tools/coverage_authoring/promotion_candidates/review.json
```

Emits:

- `entry` — copy for review
- `promotion_gate_result` — full gate evaluation (`mode=draft`)
- `manifest_patch_hint` — **single** `entries[]` object for manual paste
- `review_checklist`
- `would_write_manifest`: **false** (always)

**Hard rules (S5.2):**

- Must **not** write `backend/app/coverage/pattern_coverage_v1.json`
- Must **not** write anywhere under `backend/app/coverage/`
- Must **not** produce a full replacement manifest (`pack_version` + `entries[]` wrapper)
- Must **not** set `promoted_to_manifest=true` on any draft

Alternative gate-only check:

```bash
python tools/coverage_authoring/coverage_drafter.py --entry-json <draft> --check-promotion
```

Exit `0` when `manifest_copy_ready`.

### 9. Manual manifest promotion

Human copies `manifest_patch_hint` (or reviewed `entry`) into `pattern_coverage_v1.json` `entries[]` via editor/PR. No CLI auto-write.

### 10. Committed manifest audit (S5.1)

```bash
python tools/coverage_authoring/check_manifest_promotion.py
```

All committed rows must pass `mode=committed` integrity gates (currently 10/10).

### 11. Regenerate S6 runtime map

```bash
python tools/coverage_authoring/coverage_drafter.py --emit-runtime-map
```

Updates [`question_runtime_map_v1.json`](../backend/app/coverage/question_runtime_map_v1.json) from taxonomy + manifest overlay.

### 12. Verification

```bash
cd backend && python3 -m pytest app/tests/test_pattern_coverage_pack_stage3k_q4.py app/tests/test_question_runtime_map_stage3l_s6.py app/tests/test_manifest_promotion_audit_stage3l_s5.py -q
export PYTHONPATH=backend
python -m pytest tools/coverage_authoring/tests/ -q
```

## Non-goals

- No automatic promotion from Q4A drafts
- No runtime mutation of manifest by authoring CLI
- No LLM-approved promotion
- No route-authority allowlist expansion
- No MCP/SPL execution

## Safety statement

No MCP/SPL execution. No live LLM execution. No route-authority expansion. No `selected_skill` behavior change. Production authority remains disabled by default.
