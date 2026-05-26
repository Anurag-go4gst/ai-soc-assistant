# Stage 3J-I.3: Prompt Contracts, Role Suitability, and LLM Settings Documentation

## Scope

Update dormant prompt contracts, Foundation-sec role suitability metadata, and documentation for the guarded LLM path planned for Stage 3K. This stage remains configuration/documentation only and does not add live LLM calls.

## Implementation Plan

1. Update `backend/app/llm/prompts.py` contracts for:
   - intent shadow classifier
   - reasoning advisory roles: `pattern_reasoner`, `mitre_reasoner`, `missing_evidence_reasoner`, and `risk_rationale_reasoner`
   - analyst response drafter
   - SPL advisory generator
2. Update role suitability metadata in `backend/app/llm/registry_settings.py`:
   - Foundation-sec-8B-Instruct role fit.
   - Foundation-sec-8B-Reasoning role fit.
   - explicit `final_answer_without_guard=not_allowed`.
   - advisory/deterministic authority notes.
3. Update canonical docs:
   - `docs/vai-soc-implementation-roadmap.md`
   - `CLAUDE.md` Plans table
   - Foundation-sec Instruct role.
   - Foundation-sec Reasoning role.
   - deterministic authority layer.
   - Stage 3J-I.1 active adapter overrides.
   - Stage 3J-I.2 dormant semantic guard rules.
   - confidence is not a gate.
   - aggregate overclaim risk.
   - SPL advisory is not recommended for execution.
   - Stage 3K prerequisites.
4. Add backend tests for prompt contract wording, role suitability statuses, governance advisory wording, and inert safety flags.
5. Add an import-boundary test proving Stage 3J-I.3 does not import or call `app.answer_guard.rules` from prompt contracts, registry status, settings routes, or `/chat`.
6. Avoid frontend changes unless needed for existing Settings UI copy.

## Non-Goals

- No final LLM synthesis.
- No Answer Guard execution.
- No live LLM calls.
- No LLM-generated SPL execution.
- No remediation/write actions.
- No dormant semantic guard wiring into `/chat`.
- No MCP gate changes.
- No SAIA candidate-only changes.

## Verification

- `cd backend && python3 -m pytest`
- `cd frontend && npm run build` only if frontend touched for this stage.
- `python3 -m test_harness.harness.runner --json`
- `TELEMETRY_MODE=none python3 -m test_harness.harness.runner --json`
- `git diff --check`
