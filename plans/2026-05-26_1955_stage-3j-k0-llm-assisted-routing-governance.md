# Stage 3J-K0: Govern LLM-Assisted Routing And Tool Selection

## Objective

Make LLM assistance explicit, configurable, auditable, and non-authoritative before Stage 3K synthesis. Preserve deterministic safety boundaries: final route selection, registry normalization, MCP tool mapping, SPL execution eligibility, and answer validity remain deterministic.

## Scope

- Add explicit routing modes: `deterministic_only`, `llm_shadow_only`, `llm_assisted_semantic`, and `llm_primary_lab`.
- Honor `ROUTING_LLM_SHADOW_ENABLED` and mode-specific LLM call behavior.
- Add advisory-only LLM semantic result and route decision learning metadata.
- Normalize LLM route suggestions through deterministic registries and clarification policy.
- Map LLM evidence needs to MCP tools through deterministic selector records only.
- Rename SPL optimizer `execution_eligible` to `revalidation_approved`.
- Add backend tests for routing modes, clarification override, registry normalization, deterministic MCP evidence mapping, SPL candidate invariants, and learning records.

## Non-Goals

- No final LLM synthesis.
- No Answer Guard execution.
- No direct LLM-to-MCP calls.
- No LLM-generated SPL execution.
- No remediation/write actions.
- No weakening of MCP execution gates.
- No weakening of SAIA candidate-only behavior.
- No wiring dormant semantic guards into `/chat`.

## Implementation Plan

1. Add routing mode config/status fields and safe wording for LLM advisory behavior.
2. Introduce advisory/decision data models under routing.
3. Update `route_skill()` to enforce mode behavior and deterministic final selection.
4. Add deterministic clarification override for context-dependent prompts like "Map this alert to MITRE".
5. Add deterministic evidence-need-to-tool mapping records separate from MCP execution gate selection.
6. Rename optimizer `execution_eligible` field to `revalidation_approved`.
7. Update tests and preserve response schema compatibility.

## Verification

```bash
cd backend && python3 -m pytest
python3 -m test_harness.harness.runner --json
TELEMETRY_MODE=none python3 -m test_harness.harness.runner --json
git diff --check
```

Run `cd frontend && npm run build` only if frontend files are touched.

## Safety Assertions

- LLM assists semantic planning only.
- Deterministic registry normalizes final `use_case_id` and skill.
- Deterministic selector chooses MCP tools.
- LLM cannot grant execution.
- LLM confidence is metadata only.
- `routing_llm_shadow_enabled` is honored.
- No final synthesis.
- No Answer Guard execution.
- No LLM-generated SPL execution.
- No remediation.
- MCP gates unchanged.
- SAIA candidate-only preserved.
