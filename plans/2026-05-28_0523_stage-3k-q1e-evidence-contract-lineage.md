# Stage 3K-Q1E: Evidence Output Contract + Route/Template Lineage

## Objective

Connect the deterministic chain (route plan → matched template → rendered+validated SPL → evidence_output_contract) into the existing `route_plan_shadow` envelope and Stage 3D lineage trace. Answer: "If this template ran later, what evidence shape would it produce?" — without any execution and without changing analyst-visible answers.

## Scope

- Extend `RoutePlanShadowEnvelope` with new fields (all optional, backward-compatible).
- Wire `template_matcher` (Q1C) and `template_renderer` (Q1D) into the `/chat` shadow path. Both run only when `ROUTING_LLM_SHADOW_ENABLED=true` and only against the validated normalized route plan.
- Extend `lineage/builder.py` to surface the `template_match` step + validator status as a lineage hop after `route_plan_shadow`.
- Expose the matched template's `evidence_output_contract` inside the shadow envelope (internal-only field; not promoted to analyst summary).
- Keep all additions dormant w.r.t. analyst answer: no change to `AnalystResponseEnvelope`, no UI overclaim.

## Non-Goals

- No SPL execution. No MCP call. No execution gate change.
- No live LLM synthesis. No Answer Guard execution.
- No analyst-visible "this is what would run" wording.
- No promotion of sample templates to production-executable.
- No new sibling block in the response schema (we extend `route_plan_shadow`, per session decision).
- No change to Experience Center golden answers.
- No frontend behavior change beyond optionally surfacing the new fields inside the existing "How this answer was produced" lineage reveal.

## Schema Extensions

Add to `RoutePlanShadowEnvelope` (all optional, default None / False):

- `template_match_attempted: bool`
- `matched_template_id: str | None`
- `template_match_score: float | None`
- `template_match_reasons: list[str]`
- `template_mismatch_reasons: list[str]`
- `candidate_template_ids: list[str]`
- `template_production_executable: bool`
- `template_sample_only: bool`
- `template_validator_profile: str | None`
- `rendered_spl_available: bool`
- `rendered_spl_validator_approved: bool`
- `rendered_spl_execution_eligible: bool` (always False)
- `evidence_output_contract: dict[str, object] | None`

## Implementation Plan

1. Update `RoutePlanShadowEnvelope` (Pydantic schema) with the new fields.
2. In the shadow path inside `routes_chat.py` (only when shadow is enabled and route plan validates), call `template_matcher`; if a match exists, call `template_renderer` and pass result through `validate_spl`.
3. Populate shadow envelope fields from matcher + renderer results. Always set `rendered_spl_execution_eligible=False`.
4. Add lineage hop in `lineage/builder.py`:
   - Step name: `template_match_shadow`.
   - Status: matched | no_match | render_rejected | validator_rejected.
   - Payload: matched_template_id, validator_profile, evidence_output_contract.
5. Frontend lineage reveal (existing collapsed section) optionally renders the new fields under a "Dormant: template match (no execution)" sub-heading. No analyst-visible answer change.

## Tests

Backend `backend/app/tests/test_route_plan_shadow_template_lineage_stage3k_q1e.py`:

- Shadow disabled → no template_match fields populated.
- Shadow enabled, route plan validates, matcher finds sample template → envelope shows matched_template_id, sample_only=True, rendered_spl_execution_eligible=False, evidence_output_contract populated, lineage hop present.
- Shadow enabled, no matching template → matched_template_id=None, mismatch reasons present, lineage hop status=no_match.
- Shadow enabled, route plan blocked (cannot_route_*) → matcher not invoked; envelope shows template_match_attempted=False.
- Existing `route_plan_shadow` tests still pass.
- AnalystResponseEnvelope contents unchanged for all existing scenarios.
- MCP execution gate behavior unchanged (executes nothing, returns identical execution-related fields).

Frontend (only if lineage UI changes):
- `npm run build` still passes.
- Lineage reveal renders new sub-section behind the existing collapsed "Show technical trace" / "How this answer was produced" surface — no top-line copy change.

## Verification

```bash
cd backend && python3 -m pytest
python3 -m test_harness.harness.runner --json
TELEMETRY_MODE=none python3 -m test_harness.harness.runner --json
cd frontend && npm run build  # only if frontend touched
git diff --check
```

## Shadow / Lineage Wording Rules (frozen)

Any UI / trace / lineage surface that exposes Q1E data must use these terms:

- "Dormant route-plan shadow"
- "Template candidate only"
- "Not executed"
- "Execution authorized: false"

Forbidden without an explicit dormant / non-executed marker:

- "this would run"
- "this is what executes"
- "ready to run"

The analyst answer card stays unchanged. The lineage reveal is collapsed by default, consistent with Stage 3J-J.2.

## LLM Role and Boundary

> LLM assistance is candidate-only. Deterministic core owns validation, normalization, binding, rendering, execution eligibility, and all blocking decisions. If LLM output disagrees with deterministic validation, deterministic wins and the disagreement is recorded.

- Q1E is deterministic-only. No LLM call is added to `/chat` from Q1E code.
- The Q1E shadow envelope must show `llm_called=false` when no LLM ran in Q1E itself.
- Q1E extends the envelope schema so it can carry future Q1F (route-plan candidate) and Q1G (analyst narration) outputs. It does not invoke them.
- LLM must never: write directly to `evidence_output_contract`, override `matched_template_id`, override `validator_profile`, or flip `execution_eligible`.
- Schema additions for downstream stages are optional / default-None and must not change response shape when those stages are disabled.

## Fixture Honesty

Q1E tests use synthetic route-plan + template-match fixtures only. Labelled `coe_synthetic_fixture=true`, `captured_live_run=false`, `production_execution=false`. Synthetic fixtures must not be relabelled as captured live runs in any later stage.

## Exit Criteria

- `route_plan_shadow` exposes template_match + validator metadata when shadow is enabled.
- Lineage trace shows `template_match_shadow` hop with deterministic status.
- `evidence_output_contract` visible internally; never used to override analyst answer.
- No new MCP / SPL execution path. No analyst overclaim.
- Backend tests pass. Harness 6/6. Frontend builds.
