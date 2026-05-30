# Stage 3L-S6: 105-Question Runtime Operation Map

**Status:** S6 map done; **S6.1** shadow consumer wired (2026-05-29)

**Artifact:** [`backend/app/coverage/question_runtime_map_v1.json`](../backend/app/coverage/question_runtime_map_v1.json)  
**Loader:** [`backend/app/coverage/question_runtime_map.py`](../backend/app/coverage/question_runtime_map.py)

## Purpose

Map each of the 105 Stage 3K-Q0 taxonomy questions to:

- Taxonomy `pattern_type`
- Proposed compact runtime `primary_skill` / `operation_type` (from Q0.5)
- Legacy router intent hint (for S2A bridge analysis)
- Manifest linkage when a Q4 row exists
- S3 authority pilot metadata for `q0.q046` only

This registry is **read-only** for runtime tooling and tests. It does not change `/chat` routing, `selected_skill`, or operation authority.

### S6.1 — Shadow surface (`question_runtime_map`)

When `route_plan_shadow` resolves a `coverage_id`, `/chat` attaches an observational block:

- [`backend/app/coverage/question_runtime_map_shadow.py`](../backend/app/coverage/question_runtime_map_shadow.py)
- Field on `RoutePlanShadowEnvelope`: `question_runtime_map` (`observation_only: true`)

No MCP/SPL/LLM enablement; no second authority pilot.

## S6.1 vs S6.2

| Artifact | Path | Role |
|----------|------|------|
| **S6.1** (this doc) | `backend/app/coverage/question_runtime_map_v1.json` | Runtime shadow map |
| **S6.2** (provisional report) | [stage3l_s6_105_question_operation_map.md](stage3l_s6_105_question_operation_map.md) | Analysis report only; not wired to `/chat` |

Both are generated from the **same builder pass**. See S6.2 doc for drift audit requirements.

## Regenerate

```bash
export PYTHONPATH=backend
python tools/coverage_authoring/coverage_drafter.py --emit-maps
python tools/coverage_authoring/check_question_operation_map.py
```

Or runtime map only:

```bash
python tools/coverage_authoring/coverage_drafter.py --emit-runtime-map
```

After adding or changing manifest rows, rerun emit and commit both JSON artifacts when using `--emit-maps`.

## Current snapshot

| Metric | Value |
|--------|------:|
| Taxonomy questions | 105 |
| Manifest rows linked | 10 |
| Authority pilot | `q0.q046` → `cov.q046.excessive_failed_logins_sample` |
| `s3_authority_ready` | `false` in map (expansion gate; COE signed pilot only — no pattern #2) |

## Skill drift

`q0.q046` taxonomy pattern is `threshold_anomaly` (proposed `threshold_anomaly`) while the manifest row uses `aggregate_and_rank` for the Experience Center sample template path. The map sets `skill_drift: true` with an explanatory note — intentional fixture calibration, not a validator bug.

## Tests

```bash
cd backend && python3 -m pytest app/tests/test_question_runtime_map_stage3l_s6.py app/tests/test_question_runtime_map_shadow_stage3l_s6.py -q
```
