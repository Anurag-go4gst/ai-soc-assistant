# Stage 3K-Q1D: Non-Executable SPL Rendering For Sample Templates

## Objective

Render SPL from disabled / sample-only CIM templates using bound parameters, then prove the rendered SPL passes the Q1A validator. Answer: "Can a matched template produce validator-safe SPL?"

## Scope

- New module `app/spl/template_renderer.py` with a pure function `render_template(template, bound_params) -> RenderResult`.
- Pattern strings (`render_pattern`) added to each Q1B sample template — string templates with declared placeholders only, no free interpolation.
- Bound-parameter contract: only `required_parameters` / `optional_parameters` from the template definition may be substituted. Unknown keys are rejected.
- Time-bound binding: route plan supplies `earliest` / `latest`; if absent, fall back to template `default_time_window` (per session decision).
- Render result envelope: `rendered_spl`, `bound_parameters`, `validation_result`, `validator_approved`, `validator_profile`, `execution_eligible=False`, `render_warnings`.

## Non-Goals

- No SPL execution.
- No MCP call. No MCP execution gate change.
- No live LLM synthesis. No Answer Guard.
- No promotion of `sample_only` templates to production.
- No wiring into `/chat` (deferred to Q1E).
- No raw-search template rendering (already covered by existing generator); Q1D is CIM-only.
- No free-form parameter injection. Placeholders are strictly enumerated.

## Render Contract

Each sample template gains a `render_pattern` field (added to Q1B schema with default `None`; backward-compatible). Example for the Auth sample:

```
tstats summariesonly=true count as failed_login_count
  from datamodel=Authentication.Authentication
  where {earliest} {latest} Authentication.action=failure
  by Authentication.user
| sort - failed_login_count
| head {result_limit}
```

Declared placeholders: `{earliest}`, `{latest}`, `{result_limit}`. Renderer:

1. Reject placeholders not declared in template's `required_parameters` ∪ `optional_parameters` ∪ `{earliest, latest, result_limit}`.
2. Bind `earliest` / `latest` from normalized route plan time window. Fall back to `default_time_window` parse if route plan omits them.
3. Bind `result_limit` from `result_limits.max_rows`.
4. Reject bindings whose value is not a string of allowlisted shape (regex per parameter type).
5. Compose final SPL deterministically.
6. Call `validate_spl(rendered)`; surface `validator_profile`, `approved`, `reasons`.
7. Always set `execution_eligible=False`.

## Implementation Plan

1. Extend `SplTemplateDefinition` with optional `render_pattern: str | None = None` and `parameter_value_patterns: dict[str, str] = {}` (regex per parameter). Backward compatible.
2. Add `render_pattern` to the 3 Q1B sample templates. Add narrow regex patterns for `earliest`, `latest`, `result_limit`.
3. Write `template_renderer.render_template(template, bound_params, *, route_window=None) -> RenderResult`.
4. Internal helper `_resolve_time_window(route_window, template.default_time_window)` returns `(earliest, latest)`.
5. Renderer is a pure function. No I/O. No logging beyond returned warnings.
6. Library-level only. No `/chat` wiring.

## Tests

`backend/app/tests/test_template_renderer_stage3k_q1d.py` (deterministic core)
`backend/app/tests/test_template_renderer_llm_assist_stage3k_q1d.py` (sidecar)

Deterministic core tests:

- Each of the 3 sample templates renders SPL when given a valid route window.
- Rendered SPL passes Q1A validator with the template's declared `validator_profile`.
- Rendered SPL has `execution_eligible=False`.
- Missing route window → template `default_time_window` fallback succeeds.
- Both route window and template default missing → render rejects.
- Unknown placeholder in `render_pattern` → render rejects.
- Bound parameter that fails regex → render rejects (e.g. `earliest=*; rm -rf /`).
- Bound parameter outside declared `required_parameters` ∪ `optional_parameters` ∪ time/limit set → render rejects.
- Production templates (raw-search) are NOT rendered by this renderer (returns explicit "not supported by Q1D renderer").
- Sample template stays `sample_only=True` and `production_executable=False` after render.

Sidecar tests (stub LLM adapter):

- Sidecar disabled → renderer uses route-plan params only.
- Sidecar extracts valid `host`, `src_ip`, `result_limit` → merged; route-plan values win on conflict.
- Sidecar emits SPL fragment in output → stripped; reason `spl_in_extraction_forbidden`.
- Sidecar emits invalid IP → dropped; renderer proceeds without it.
- Sidecar emits `result_limit > SPL_MAX_RESULT_LIMIT` → dropped.
- Sidecar emits `template_id` or `detection_ref` → stripped.
- Reasoning model assigned to sidecar role → rejected.
- Sidecar timeout → renderer proceeds; envelope shows `llm_assist_timed_out=true`.
- Rendered SPL still passes Q1A validator in every passing case.

## Verification

```bash
cd backend && python3 -m pytest app/tests/test_template_renderer_stage3k_q1d.py -x
cd backend && python3 -m pytest
python3 -m test_harness.harness.runner --json
TELEMETRY_MODE=none python3 -m test_harness.harness.runner --json
git diff --check
```

## Rendering Contract (frozen rules)

Q1D is a small safe rendering engine, not free string interpolation.

- `render(template, bound_params) -> spl_text` is a pure function.
- No I/O. No MCP. No execution.
- Only declared parameters can be substituted (template `required_parameters` ∪ `optional_parameters` ∪ {`earliest`, `latest`, `result_limit`}).
- No free-form SPL fragments accepted.
- Rendered SPL must pass the Q1A validator before the render result is returned.
- `execution_eligible=false` on every render result.
- Samples stay `sample_only=true` after Q1D. Samples do not become production templates in Q1D.
- No `enabled=false` template is silently flipped to `enabled=true` by the renderer.

## LLM Role and Boundary

> LLM assistance is candidate-only. Deterministic core owns validation, normalization, binding, rendering, execution eligibility, and all blocking decisions. If LLM output disagrees with deterministic validation, deterministic wins and the disagreement is recorded.

Q1D ships in two modules:

- `app/spl/template_renderer.py` — deterministic core. Pure function. Authoritative.
- `app/spl/template_renderer_llm_assist.py` — Instruct sidecar. Parameter extraction only.

### LLM-Assist Sidecar (parameter extraction only)

Input: user query + matched template (from Q1C) + route plan time window.

Output schema (strict, adapter-enforced):

```json
{
  "extracted_parameters": {
    "host": "<string>",
    "user": "<string>",
    "src_ip": "<string>",
    "dest_ip": "<string>",
    "result_limit": <int>,
    "time_window": {"earliest": "...", "latest": "..."}
  }
}
```

Every extracted value passes deterministic checks before binding:

- `host` → regex from template `parameter_value_patterns["host"]`, else dropped.
- `user` → regex from `parameter_value_patterns["user"]`, else dropped.
- `src_ip` / `dest_ip` → canonical IP parse (IPv4 / IPv6); invalid → dropped.
- `result_limit` → integer, `1 <= n <= SPL_MAX_RESULT_LIMIT`.
- `time_window` → values must match `earliest=-Nm|h|d` / `latest=now` shape (or equivalent allowlisted form).

After extraction:

1. Surviving values are merged with route-plan parameters. Route-plan values win on conflict (deterministic source-of-truth).
2. Merged parameters passed to deterministic renderer.
3. Rendered SPL passes through Q1A validator. Validator failure → render fails; sidecar values are NOT retried with relaxed rules.
4. Sidecar output captured in `route_plan_shadow.parameter_extraction_llm` only when shadow mode is enabled.

Forbidden in sidecar output (adapter strips with reason):

- Any field outside the `extracted_parameters` schema.
- Any SPL fragment (`| stats`, `index=...`, etc.).
- Any datamodel / `template_id` / `detection_ref` / `lookup_name` value.
- Any free-form `where` clause.

Gates:

- `ROUTING_LLM_SHADOW_ENABLED=true`.
- LLM Registry role `template_render_parameter_assist` configured with `model_family=instruct` only. Reasoning model rejected.

LLM must never: generate executable SPL, select MCP tools, invent template_ids, invent placeholder names, authorize execution.

## Fixture Honesty

Q1D tests use synthetic templates and synthetic bound parameters only. Labelled `coe_synthetic_fixture=true`, `captured_live_run=false`, `production_execution=false`.

## Exit Criteria

- Sample template renders SPL deterministically.
- Rendered SPL passes Q1A validator with the right `validator_profile`.
- `execution_eligible=False` on every render result.
- No MCP call, no execution path.
- Backend tests pass. Harness 6/6.
- Renderer is not called from `/chat` yet.
