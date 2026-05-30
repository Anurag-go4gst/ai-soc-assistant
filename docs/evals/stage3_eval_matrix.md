# Stage 3L / 3M Evaluation Matrix

**Purpose:** Define what each governance eval checks and how 105-question buckets pass or fail.

**Not in scope:** Live MCP reads, live LLM calls, `/chat` HTTP load tests, route authority enablement, pattern #2+ pilots, or changing `selected_skill`.

---

## Regression bundle (`run_stage3_governance_regression.sh`)

| Step | Command / check | Pass criteria |
|------|-----------------|---------------|
| Backend tests | `cd backend && python3 -m pytest -q` | All tests pass |
| Harness | `python3 -m test_harness.harness.runner --json` | 6/6 `overall_pass` |
| Manifest promotion | `python tools/coverage_authoring/check_manifest_promotion.py` | S5 + S7 alignment OK |
| Operation map drift | `python tools/coverage_authoring/check_question_operation_map.py` | 105 entries, S6.1 ↔ S6.2 match |
| cov.q046 baseline | `docs/stage3l_s3_step3_coe_pilot_verification_traces.json` | Pilot id + ≥2 scenarios (`authority_disabled`, `authority_enabled_allowlisted`) |
| Live MCP capture | `scripts/capture_stage3m_s5_live_mcp_schema.py` (no env) | Exit non-zero, `live_capture_flag_missing` |
| 105-Q shadow eval | `scripts/eval_stage3l_105_question_shadow_routes.py` | All bucket rules pass |

---

## 105-question eval buckets

Source map: [`stage3l_s6_105_question_operation_map.json`](../stage3l_s6_105_question_operation_map.json).

| Eval bucket | Map source | Count driver |
|-------------|------------|--------------|
| `promoted` | `promoted_to_manifest=true` | 10 manifest rows |
| `likely_routable` | `provisional_status=likely_routable` or `likely_needs_review` (non-promoted) | ~48 |
| `lookup` | `likely_needs_lookup` | ~14 |
| `detection` | `likely_needs_detection` | ~26 |
| `multi_signal` | `likely_multi_signal` | ~7 |
| `context` | `likely_needs_context` | ~7 |
| `unsupported` | `likely_unsupported` | ~1 |

---

## Per-bucket pass rules (`eval_stage3l_105_question_shadow_routes.py`)

Each question runs:

1. `route_skill_deterministic(question_text)` → legacy `selected_skill` (observation only; never mutated).
2. `evaluate_intent_operation_bridge(legacy_skill, likely_runtime_operation)` → recorded in output; **not** a pass/fail gate (disagreement is expected shadow signal).
3. `question_runtime_entry(question_ref)` → S6.1 row (`route_blocked`, `skill_drift`, …).
4. Promoted only: `evaluate_promotion_gates` on manifest row.

| Bucket | Pass when |
|--------|-----------|
| **promoted** | `candidate_coverage_id` in manifest; promotion gates `manifest_integrity_ok`; runtime row present |
| **likely_routable** | Not `route_blocked`; `dependency_type=template`; proposed operation is template-class |
| **lookup** | `dependency_type=lookup`; proposed operation ∈ lookup operations |
| **detection** | `dependency_type=detection`; proposed operation ∈ `behavioral_detection_binding` |
| **multi_signal** | `dependency_type=multi_signal`; proposed operation = `multi_signal_correlation` |
| **context** | `dependency_type=context`; proposed operation ∈ context operations |
| **unsupported** | `route_blocked` or provisional unsupported / dependency unsupported |

---

## Outputs

| File | Description |
|------|-------------|
| `docs/evals/out/stage3l_105_shadow_eval.json` | Per-question results + bucket aggregates |
| `docs/evals/out/stage3l_105_shadow_eval.md` | Human summary |

Optional flags:

- `--no-coe-signoff` — stricter promoted authority gate checks
- `--route-skill-smoke` — one `route_skill` call under `deterministic_only` (still no live LLM)
- `--json-stdout` — print full JSON

---

## Explicit non-goals

- No live Splunk / Splunk MCP execution
- No Hugging Face or Foundation-Sec HTTP
- No `operation_authoritative_enabled` in eval
- No auto `schema_confirmed=true`
- No pattern #2 authority expansion
- No analyst-facing answer or golden demo text changes
