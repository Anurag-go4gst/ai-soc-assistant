# Stage 3K-Q1G: LLM-Narrated Analyst Summary In Shadow Mode

**Status:** Done
**Tests:** `backend/app/tests/test_analyst_summary_shadow_narration_stage3k_q1g.py`
**Production note:** Narration requires `ROUTING_LLM_SHADOW_ENABLED=true` AND `AI_SOC_LLM_SHADOW_NARRATION_ENABLED=true` AND configured `analyst_summary_narration` role. `/chat` does not call a live LLM without `llm_raw_output_provider`. When narration is disabled or dropped, deterministic skeleton may still populate shadow fields for lineage only — analyst answer envelope unchanged.

## Objective

Use Foundation-sec-Instruct to narrate a short analyst summary from the structured `route_plan_shadow` + Q1E lineage + (when available) Q4 evidence package. Shadow only. The analyst-facing answer envelope does not change. This is the honest runway toward later lighting `AI_SOC_LLM_FINAL_SYNTHESIS_ENABLED`, with Answer Guard wiring still deferred.

## Scope

- New module `app/synthesis/analyst_summary_llm_assist.py` (sidecar; deterministic narration skeleton owns authority).
- Strict JSON schema for the LLM narration output.
- Wired into the existing lineage / "How this answer was produced" reveal as a dormant block.
- Toggles: `ROUTING_LLM_SHADOW_ENABLED=true` AND `AI_SOC_LLM_SHADOW_NARRATION_ENABLED=true` AND LLM Registry role `analyst_summary_narration` configured with `model_family=instruct`.

## Non-Goals

- No change to `AnalystResponseEnvelope`.
- No final synthesis. `AI_SOC_LLM_FINAL_SYNTHESIS_ENABLED` stays inert this stage.
- No Answer Guard execution.
- No SPL execution. No MCP call. No execution gate change.
- No remediation / write actions.
- No reasoning model. Instruct only.
- No claim that a query "would run" or "is ready to run".
- No demo behavior change. Experience Center golden answers stay identical.

## LLM Role and Boundary

> LLM assistance is candidate-only. Deterministic core owns validation, normalization, binding, rendering, execution eligibility, and all blocking decisions. If LLM output disagrees with deterministic validation, deterministic wins and the disagreement is recorded.

LLM contribution in Q1G:

- Generates a 2-sentence-max summary and 3 technical-trace bullets from a structured lineage input.
- Output schema (strict, adapter-enforced):

```json
{
  "summary_sentence_1": "string (<= 240 chars)",
  "summary_sentence_2": "string (<= 240 chars) | null",
  "technical_trace_bullets": ["string", "string", "string"]
}
```

Forbidden in output (adapter rejects):

- More than 2 summary sentences.
- Any of the forbidden phrases: "this would run", "this executed", "ready to run", "we ran", "results show" (when no execution happened), "this is what runs", "production".
- Any action recommendation (no "you should…", "next, do…").
- Any concrete IOC / detection / SPL claim not present in the structured input.
- Any field outside the schema.

Adapter rules:

- Schema-invalid → drop, reason `schema_invalid`.
- Forbidden phrase detected → drop, reason `forbidden_phrase_<phrase>`.
- Length over budget → drop, reason `length_exceeded`.
- Unsupported claim (mentions an entity / number / detection / IOC not present in the structured input) → drop, reason `unsupported_claim`.

LLM must never: replace the analyst answer, override severity, override MITRE mappings, propose remediation, propose detection_ref, propose lookup names, propose SPL, authorize execution.

## Implementation Plan

1. Add `app/synthesis/analyst_summary_llm_assist.py` with `narrate_summary(structured_input) -> NarrationResult`.
2. Use the existing guarded LLM adapter (`app/llm/adapter/`) with a fixed prompt and the schema above.
3. Add `app/synthesis/analyst_summary_skeleton.py` — deterministic 1-sentence skeleton that is rendered if shadow narration is disabled or dropped.
4. Extend `RoutePlanShadowEnvelope` with optional fields:
   - `analyst_summary_shadow_available: bool`
   - `analyst_summary_shadow_text: str | None` (joined summary; never used as analyst answer)
   - `analyst_summary_trace_bullets: list[str]` (max 3)
   - `analyst_summary_dropped_reasons: list[str]`
5. Frontend lineage reveal renders the narration only inside the collapsed "How this answer was produced" section, under a "Dormant: shadow narration (no execution)" heading. The analyst summary card on top of the chat is unchanged.
6. Add LLM Registry role `analyst_summary_narration` with `model_family=instruct` only. Reasoning model rejected (`reasoning_model_not_allowed_for_narration`).

## Tests

`backend/app/tests/test_analyst_summary_shadow_narration_stage3k_q1g.py`

- Shadow off → no narration produced; envelope shows `analyst_summary_shadow_available=false`.
- Shadow on, valid narration → envelope populated; analyst answer envelope unchanged.
- Output > 2 sentences → dropped with reason `length_exceeded`.
- Output uses forbidden phrase ("ready to run") → dropped with corresponding reason.
- Output references an entity not in the structured input ("attacker 1.2.3.4" when no IP in input) → dropped with reason `unsupported_claim`.
- Reasoning model assigned to narration role → rejected.
- `AnalystResponseEnvelope` byte-equal across all narration outcomes for a given fixture.
- Experience Center golden answers unchanged.

## Verification

```bash
cd backend && python3 -m pytest
python3 -m test_harness.harness.runner --json
TELEMETRY_MODE=none python3 -m test_harness.harness.runner --json
cd frontend && npm run build  # only if frontend touched
git diff --check
```

## Fixture Honesty

Q1G tests use a stub LLM adapter producing scripted JSON. No real LLM call in tests. Fixtures labelled `coe_synthetic_fixture=true`, `captured_live_run=false`, `production_execution=false`.

## Exit Criteria

- Instruct can produce a shadow narration that passes schema + claim checks.
- Forbidden wording is blocked by adapter, never reaches the response.
- Analyst answer envelope unchanged across all narration outcomes.
- No SPL execution, no MCP call.
- Backend tests pass. Harness 6/6. Frontend builds if touched.
