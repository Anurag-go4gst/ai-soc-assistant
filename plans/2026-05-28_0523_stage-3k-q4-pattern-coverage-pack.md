# Stage 3K-Q4: First Governed SOC Pattern Coverage Pack

**Status:** Done
**Tests:** `backend/app/tests/test_pattern_coverage_pack_stage3k_q4.py`
**Manifest:** `backend/app/coverage/pattern_coverage_v1.json`
**SOC doc:** `docs/soc_pattern_coverage_pack_stage3k_q4.md`
**Q4A (optional author CLI):** `plans/2026-05-28_0523_stage-3k-q4a-coverage-drafter-cli.md` — not implemented in Q4

## Objective

Take 8–10 representative SOC questions from the Stage 3K-Q0 taxonomy (105 set) and demonstrate them end-to-end through the governed bridge: route plan → template match (Q1C) → render+validate (Q1D) → evidence contract + lineage (Q1E), with IOC (Q2) or detection (Q3) bindings where required. No claim that all 105 are live-ready.

## Scope

- Select a mix of 8–10 questions covering at least:
  - 4+ template-only (raw-search or sample CIM) — pure aggregate / ranking / timechart.
  - 1–2 IOC lookup-dependent (uses Q2).
  - 1–2 vetted-detection-dependent (uses Q3).
  - 1 multi-signal question that combines two evidence sources (e.g. auth + network or alert + entity).
  - 1 negative case that resolves to a `cannot_route_*` status (intentional gap).
- For each selected question, define and ship:
  - route-plan shape (skill, evidence_needs, parameters, clarifications);
  - template / detection / lookup dependency reference;
  - evidence_output_contract reference;
  - fixture readiness (`coe_synthetic_fixture` vs `source_ready` vs `ioc_dependent` vs `detection_dependent`);
  - clarification rules (what's required from the analyst);
  - governance constraints (sample_only flags, execution_eligible=False).
- A coverage manifest `docs/soc_pattern_coverage_pack_stage3k_q4.md` enumerating the set, status, and grouped view for SOC team.
- A coverage manifest JSON `backend/app/coverage/pattern_coverage_v1.json` machine-readable for the dashboard / tests.
- Optional Experience Center additions only if the question is already in the demo scenarios and only as labelled coverage entries; no analyst-visible answer change.

## Non-Goals

- No claim that all 105 questions are covered.
- No SPL execution. No MCP call. No execution gate change.
- No live LLM synthesis. No Answer Guard.
- No remediation / write actions.
- No promotion of `sample_only` templates to production.
- No new IOC / detection content beyond what Q2/Q3 already seeded; if a coverage entry needs more, mark it `dependency_missing` rather than smuggle it in.

## Coverage Manifest (sketch)

```
{
  "pack_version": "stage3k_q4_v1",
  "entries": [
    {
      "coverage_id": "auth.failed_login_top_users",
      "question_ref": "q0.taxonomy.<id>",
      "skill": "aggregate_and_rank",
      "template_ref": "sample_auth_failed_login_top_users_tstats",
      "lookup_ref": null,
      "detection_ref": null,
      "evidence_contract_ref": "ranked_entities_user_failed_login",
      "readiness": "coe_synthetic_fixture",
      "clarification_required": ["time_window"],
      "governance": {"execution_eligible": false, "sample_only": true}
    }
  ]
}
```

## Implementation Plan

1. Confirm the 8–10 question selection against `docs/soc_question_taxonomy_stage3k_q0.md`. Record explicit IDs in the coverage manifest.
2. Add `backend/app/coverage/pattern_coverage_v1.json` with one entry per selected question. Schema validated by a Pydantic model under `app/coverage/coverage_models.py`.
3. Add `app/coverage/coverage_loader.py` and helpers `list_coverage()`, `coverage_for_question(question_ref)`, `coverage_for_skill(skill)`.
4. Tests assert each entry: route plan can be built, matcher / lookup / detection resolves per declared dependency, evidence_output_contract resolves, governance flags hold.
5. Docs page `docs/soc_pattern_coverage_pack_stage3k_q4.md`: grouped view (template-only / IOC-dependent / detection-dependent / negative), readiness labels, SOC-facing summary.
6. Optional analyst-trace surface: lineage reveal can show `coverage_id` when the matched question maps to a pack entry. No analyst-answer change.

## Tests

`backend/app/tests/test_pattern_coverage_pack_stage3k_q4.py`

- Manifest loads and conforms to schema.
- Every entry references a real template_ref / detection_ref / lookup_ref or null.
- Every entry's claimed `evidence_contract_ref` exists.
- For each template-only entry: matcher returns the declared template; renderer produces validator-approved SPL; `execution_eligible=False`.
- For each IOC-dependent entry: lookup dependency is wired; if registry stale, route resolves to `cannot_route_missing_lookup`.
- For each detection-dependent entry: binding resolves to declared `detection_ref` or returns `cannot_route_missing_detection`.
- Negative case entry deterministically yields the declared `cannot_route_*` status.
- No MCP execution. No live LLM call. No Answer Guard execution.

## Verification

```bash
cd backend && python3 -m pytest
python3 -m test_harness.harness.runner --json
TELEMETRY_MODE=none python3 -m test_harness.harness.runner --json
cd frontend && npm run build  # only if frontend touched
git diff --check
```

## Negative Case Importance

The negative case is part of the governance story. It proves the system refuses when a dependency is missing — IOC stale, detection unvetted, datamodel unsupported, or composition invalid. The coverage pack must include at least one negative case and document the exact `cannot_route_*` status it produces.

## LLM Role and Boundary

> LLM assistance is candidate-only. Deterministic core owns validation, normalization, binding, rendering, execution eligibility, and all blocking decisions. If LLM output disagrees with deterministic validation, deterministic wins and the disagreement is recorded.

- Q4 runtime is deterministic-only. No LLM is invoked from `/chat` for Q4 purposes.
- Q4 ships an **author-time** LLM CLI assistant (not runtime). See section below.
- If Q1F is enabled at runtime, coverage entries may show LLM candidate metadata in `route_plan_shadow`, but the analyst-facing coverage label still comes from the deterministic chain.
- LLM must never: rewrite coverage manifest entries at runtime, promote `sample_only=true` templates, flip `readiness` labels, or author negative-case explanations.

## Author-Time LLM Assistant (deferred to Q4A)

Moved to **`plans/2026-05-28_0523_stage-3k-q4a-coverage-drafter-cli.md`**. Q4 ships the deterministic manifest and loader only.

## Fixture Honesty

Every Q4 coverage entry is labelled honestly: `coe_synthetic_fixture`, `source_ready`, `ioc_dependent`, `detection_dependent`, `dependency_missing`. Synthetic fixtures are never laundered into `captured_live_run` or `production_execution`.

## Exit Criteria

- 8–10 representative SOC questions demonstrably covered end-to-end through the governed bridge.
- Coverage manifest readable by both SOC team (Markdown) and engineering (JSON).
- Each entry's readiness honestly labelled (fixture / source_ready / IOC_dependent / detection_dependent / dependency_missing).
- No production SOC template promotion. No SPL execution. No new live LLM path.
- Backend tests pass. Harness 6/6. Frontend builds if touched.
