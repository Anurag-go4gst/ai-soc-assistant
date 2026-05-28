# Stage 3K-Q1F: LLM Route-Plan Candidate Generation In Shadow Mode (Instruct Only)

**Status:** Done (844d4f2 + 3af6423 FIX-A)
**Tests:** `backend/app/tests/test_llm_route_plan_shadow_stage3k_q1f.py`, `backend/app/tests/test_llm_route_plan_json_stage3k_q1f.py`
**Production note:** `/chat` does **not** perform a live LLM call unless an explicit provider connector is wired later. Current Q1F production path remains shadow/no-op without `llm_raw_output_provider`.

## Objective

First stage that introduces LLM into the routing path. Foundation-sec-Instruct produces a route-plan candidate in shadow mode only. Every deterministic checkpoint (preflight → normalizer → validator → composition matrix → template selector → SPL validator → MCP execution gate) still owns authority. No execution, no analyst answer change.

## Scope

- New module `app/routing/llm_route_plan_candidate.py` that calls Foundation-sec-Instruct (governed through the existing LLM registry) to produce a candidate route plan JSON.
- Hard schema contract for the candidate JSON, parsed through the guarded LLM adapter (`app/llm/adapter/`). Schema violations → drop the candidate.
- **Wrapper-tolerant JSON extraction (required):** LLM output may include markdown fences, labels, or trailing commentary. Q1F must extract the **first exact valid JSON object** from wrappers via `app/routing/llm_route_plan_json.extract_route_plan_candidate_json` (backed by `app/llm/adapter/json_extractor.extract_first_json_object`). Use `json.loads` on the extracted substring only — no repair, no field injection, no silent edits. Record warnings such as `json_extracted_from_markdown_fence`, `prose_before_json_ignored`, `prose_after_json_ignored`, `multiple_json_objects_first_used`.
- Pipeline:
  ```
  user_query
    → deterministic preflight
    → Foundation-sec-Instruct candidate route-plan
    → guarded JSON adapter
    → deterministic normalizer
    → deterministic route-plan validator
    → deterministic composition matrix
    → deterministic template selector (Q1C)
    → route_plan_shadow metadata only
  ```
- Configuration gates: `ROUTING_LLM_SHADOW_ENABLED=true` AND `AI_SOC_LLM_MODE != disabled` AND the route-plan candidate-generator role is registered in the LLM Registry with `model_family=instruct`.
- Foundation-sec-Reasoning is explicitly excluded for the routing role. Any LLM Registry attempt to assign a reasoning model to the route-plan candidate generator role is rejected with reason `reasoning_model_not_allowed_for_routing`.
- Shadow envelope extensions: `llm_called`, `llm_role`, `llm_model_family`, `llm_candidate_route_plan_available`, `llm_candidate_dropped_reasons`, `deterministic_route_plan_wins` (always true), `disagreements`.

## Non-Goals

- No SPL execution. No MCP call. No execution gate change.
- No final LLM synthesis. No Answer Guard execution.
- No reasoning model for routing.
- No analyst-facing answer change.
- No LLM-authored MCP tool selection.
- No LLM-authored lookup name or detection_ref.
- No LLM authority over final route status.

## LLM Role and Boundary

- LLM is a candidate generator only. Final route decision is deterministic.
- Only Foundation-sec-Instruct is allowed for the route-plan candidate generator role.
- Foundation-sec-Reasoning is excluded until parser / final-output stability is proven.
- LLM output must pass every deterministic checkpoint listed above. Any failure drops the candidate and records `llm_candidate_dropped_reasons`.
- LLM must never:
  - generate executable SPL directly;
  - select MCP tools directly;
  - invent lookup names;
  - invent detection refs (only `detection_family` is allowed; binding resolves `detection_ref` deterministically — see Q3);
  - decide route readiness;
  - authorize execution;
  - use confidence as authority.

## Schema Contract (LLM candidate route plan)

JSON object only, must include:

```
{
  "primary_skill": "<runtime_skill enum>",
  "operation_type": "<aggregation_shape enum>",
  "source_class": "<allowed enum>",
  "evidence_needs": {
    "datamodel": "<approved datamodel>",
    "dataset": "<approved dataset | null>",
    "group_by": [<field>],
    "metric": {"type": "<metric_type enum>", "field": "<field>"},
    "cim_fields": [<field>],
    "summariesonly": <bool | null>,
    "lookup_required": <bool>,
    "detection_required": <bool>,
    "detection_family": "<family | null>"
  },
  "time_window": {"earliest": "...", "latest": "..."} | null,
  "limit": <int | null>,
  "clarification_questions": [...],
  "rationale": "..."
}
```

Anything not matching this schema or referencing values outside the approved enums is dropped at the adapter layer. The adapter never edits the candidate to make it conform.

## Implementation Plan

1. Wire a new LLM role `route_plan_candidate_generator` in the LLM Registry, accepting only `model_family=instruct`. Reject any provider/model where `supports_tool_calling=true` is required (still must remain `false`).
2. Implement `generate_candidate_route_plan(user_query, preflight) -> CandidateResult` calling the guarded LLM adapter with a fixed prompt and schema. Raw LLM text must pass through `extract_route_plan_candidate_json` before adapter schema validation so fenced/prose-wrapped JSON is accepted when the inner object is exact and valid.
3. After candidate returns, run: normalizer → route-plan validator → composition matrix → template selector (Q1C). Capture per-stage pass/fail in shadow envelope.
4. `routes_chat.py` shadow path: when `ROUTING_LLM_SHADOW_ENABLED=true` AND the role is configured, call the candidate generator after preflight and before deterministic route. The deterministic route remains authoritative; LLM output is observed only.
5. Add disagreement comparison: if deterministic and LLM-normalized plans diverge on `primary_skill`, `datamodel`, or `group_by`, record `disagreements` entries. No automatic merge.
6. Shadow envelope additions are optional fields (backward compatible).

## Tests

`backend/app/tests/test_llm_route_plan_shadow_stage3k_q1f.py`

- LLM disabled / mode `disabled` → no candidate produced; envelope shows `llm_called=false`.
- Candidate produced, passes every deterministic checkpoint → envelope shows `llm_candidate_route_plan_available=true`, deterministic plan wins authority anyway.
- Candidate JSON schema invalid → dropped at adapter, reason `schema_invalid`.
- Candidate wrapped in markdown fence with valid inner JSON → extracted; warnings include `json_extracted_from_markdown_fence`; payload matches inner object exactly.
- Candidate wrapped in prose + fence → extracted; prose ignored with warnings; no SPL or extra keys promoted into the object.
- Candidate references unknown datamodel → dropped at validator, reason `unknown_datamodel`.
- Candidate references `detection_ref` directly → adapter strips the field; only `detection_family` survives.
- Candidate emits SPL text → adapter strips; reason `spl_in_candidate_forbidden`.
- LLM Registry attempt to bind a reasoning model to this role → rejected with reason `reasoning_model_not_allowed_for_routing`.
- `mcp_called=false`, `spl_executed=false`, `execution_authorized=false` always.
- Analyst answer envelope unchanged across all cases.
- Stage 3D trace shows LLM candidate hop with status and reasons.

## Verification

```bash
cd backend && python3 -m pytest
python3 -m test_harness.harness.runner --json
TELEMETRY_MODE=none python3 -m test_harness.harness.runner --json
git diff --check
```

## Fixture Honesty

Q1F tests use a deterministic stub LLM adapter that returns scripted JSON payloads. No real LLM call is made in tests. Fixtures labelled `coe_synthetic_fixture=true`, `captured_live_run=false`, `production_execution=false`.

## Exit Criteria

- Foundation-sec-Instruct can produce a candidate route plan in shadow mode only.
- Every deterministic checkpoint still owns authority.
- Reasoning model rejected for routing role.
- No SPL execution, no MCP call, no analyst answer change.
- Backend tests pass. Harness 6/6.
- `backend/app/routing/llm_route_plan_json.py` tracked (FIX-A) so clean checkout of Q1F does not import-error on `llm_route_plan_candidate`.

## FIX-A (repo completeness)

Commit **Stage 3K-Q1F-FIX-A** adds the missing thin wrapper `llm_route_plan_json.py` (delegates to `json_extractor.extract_first_json_object`) and dedicated JSON extraction tests. No semantic repair, no route authority change.
