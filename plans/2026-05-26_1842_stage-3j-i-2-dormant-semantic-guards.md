# Stage 3J-I.2: Dormant Semantic LLM Guard Rules

## Scope

Add pure backend semantic guard-rule functions for future LLM answer validation. The rules return findings only and remain dormant in this stage.

## Placement

Use `backend/app/answer_guard/rules.py` because the existing `answer_guard` package is the canonical location for guard status and future Stage 3L behavior. This stage will not enable Stage 3L execution.

## Guard IDs

- `guard.clarification`
- `guard.json_schema`
- `guard.registry`
- `guard.evidence_presence`
- `guard.aggregate_overclaim`
- `guard.sop_fidelity`
- `guard.mitre_status`
- `guard.severity_authority`
- `guard.action_tier`
- `guard.spl_execution`
- `guard.priority_enum`
- `guard.internal_leakage`
- `guard.splunk_table_fidelity`

## Implementation Plan

1. Define a `GuardResult` Pydantic model with stable fields:
   - `guard_id`
   - `status`
   - `severity`
   - `message`
   - `affected_field`
   - `evidence_ref`
   - `suggested_resolution`
2. Implement pure functions for each guard, reusing existing contracts where available:
   - `app.risk.severity_policy`
   - `app.actions.capability_policy`
   - `app.threat.mitre_kb`
   - `app.safeguards.spl_validator`
   - response schemas for expected structured fields.
3. Keep hard validation scoped to structured fields.
4. Treat prose scans as warning-only in this stage.
5. Use word-boundary matching for leakage and avoid substring false positives such as `demonstrate` matching `demo`.
6. Add direct backend unit tests for all guard behavior.
7. Add a dormancy test proving `/chat` does not import or call these guards, including import-time checks.
8. Do not export guard rules from `answer_guard/__init__.py`, and do not import them from `/chat`, demo scenarios, lineage, settings routes, response models, or frontend trace rendering.

## Stable Result Values

- `status`: `pass`, `warn`, `fail`
- `severity`: `info`, `warning`, `blocking_candidate`
- Prose-only scans must return `warn`/`warning` at most in this dormant stage.

## Explicit Non-Goals

- No final LLM synthesis.
- No Answer Guard execution.
- No `/chat` response blocking with these guards.
- No raw LLM output display.
- No LLM-generated SPL execution.
- No remediation/write actions.
- No MCP gate changes.
- No SAIA candidate-only changes.
- No frontend changes.

## Verification

- `cd backend && python3 -m pytest`
- `python3 -m test_harness.harness.runner --json`
- `TELEMETRY_MODE=none python3 -m test_harness.harness.runner --json`
- `git diff --check`
