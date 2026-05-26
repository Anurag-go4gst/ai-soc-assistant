# Stage 3J-I.1: Guarded LLM Adapter and Active Overrides

## Scope

Implement a dormant backend LLM adapter that normalizes model output for future Stage 3K/3L use without wiring it into `/chat` final response generation.

## Confirmed Baseline

- Pydantic version: 2.13.1.
- Existing canonical registries/enums to reuse:
  - `RequestedOutputType` and `OutputTemplate`: `app.query_understanding.models`.
  - Routable skill enum: `app.routing.skills`.
  - Skill registry: `app.skills.registry`.
  - Use-case registry: `app.use_cases.registry`.
  - MITRE mapping status source: `app.threat.mitre_kb`.
  - Action capability policy: `app.actions.capability_policy`.
- Current worktree has unrelated modified files; Stage 3J-I.1 edits will remain scoped.

## Implementation Plan

1. Add `backend/app/llm/adapter/` with:
   - JSON extraction for pure JSON, fenced JSON, prose-wrapped JSON, malformed rejection, and multi-object warnings.
   - Pydantic v2 schemas for role-specific normalized payloads.
   - Role-to-schema registry for the future synthesis seam, validated against existing LLM role catalogs in `app.llm.registry_settings`.
   - Validator/adapter result contract with warnings, errors, dropped fields, disagreements, raw output hash, and debug-only raw redaction.
   - An explicit deterministic `authority_context` input contract for clarification, severity, MITRE statuses, SOP source refs, and allowed/blocked actions.
2. Add active authority overrides at adapter level:
   - Force LLM SPL `execution_eligible=false`.
   - Preserve deterministic clarification, severity, MITRE status, SOP citations, and allowed action policy.
   - Treat confidence as advisory metadata only.
3. Add backend unit tests covering:
   - Extraction behavior.
   - Schema and registry validation.
   - Active overrides and fallback/rejection behavior.
   - Dormant `/chat` behavior and safety invariants, including a monkeypatch that makes the adapter raise if `/chat` imports or calls it.
   - Default result payloads do not include raw LLM output or secrets.
4. Update `CLAUDE.md` Plans table with this plan.

## Explicit Non-Goals

- No final LLM synthesis.
- No Answer Guard execution.
- No raw LLM output as final answer.
- No execution of LLM-generated SPL.
- No remediation/write actions.
- No MCP gate weakening.
- No SAIA candidate-only weakening.
- No semantic guard wiring into `/chat`.
- No UI lineage/trace changes.

## Verification

- `cd backend && python3 -m pytest`
- `python3 -m test_harness.harness.runner --json`
- `TELEMETRY_MODE=none python3 -m test_harness.harness.runner --json`
- `git diff --check`

Frontend build is not required unless frontend files are touched.
