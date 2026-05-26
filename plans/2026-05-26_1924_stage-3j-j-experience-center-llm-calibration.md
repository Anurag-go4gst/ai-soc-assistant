# Stage 3J-J: Calibrate Experience Center to Governed LLM Behavior

Status: Proposed (pending plan-reviewer + approval)

## Goal

Make Experience Center scenarios reflect what the **governed pipeline** does to **real**
Foundation-sec output — not the raw model, and not hand-authored strings.

- Default visible answer = **governed final answer**.
- Collapsible section "Model output governance / Why V.AI SOC changed this" reveals
  raw → governed diff (overrides + guard findings). Collapsed by default, same UX as
  the existing "Show technical trace" pattern (Stage 3J-D3).
- Captured raw outputs are **fixtures**. Governance is **baked offline**. The live demo
  path renders baked JSON only — adapter and guards are NOT imported by demo runtime.
  Dormancy invariant from Stage 3J-I stays intact and grep-verifiable.

## Verification finding that shapes this plan

Ran the 5 captured Foundation-sec outputs through the real adapter (`/tmp/calib_probe.py`):

| Test | Role | Result | Cause |
|------|------|--------|-------|
| 1 intent | intent_shadow_classifier | REJECT | prompt vocab ≠ backend registry + skill dual-source drift |
| 2 reasoning | pattern_reasoner | REJECT | schema `list[str]`, model emits `list[object]`; `pattern_characterization` str vs object |
| 3 analyst | analyst_response_drafter | REJECT | `recommended_actions` schema `list[str]`, model emits `list[object]` |
| 4 SPL | spl_advisory_generator | PASS | `execution_eligible` correctly forced false |
| 5 severity | risk_rationale_reasoner | accepted but EMPTY | field names `why_p2/why_not_p1` dropped via `extra=ignore` |

Conclusion: a reconciliation prerequisite (J.1, J.2) must land before fixtures can be
baked (J.3) and surfaced (J.4). Otherwise the demo shows reject/empty for 4 of 5 roles.

## Commit split (one commit per class, per repo convention)

### 3J-J.1 — Adapter schema reconciliation to real captured shapes (backend)
Captured output is ground truth (Quality Loop: fixtures from live runs, not hand-rolled).
- `ReasoningAdvisoryResult`: `mitre_reasoning` and `missing_evidence_analysis` →
  `list[dict]` (or `list[str | dict]`); `pattern_characterization` → `str | dict | None`.
- `AnalystResponseDraft`: `recommended_actions` → `list[dict]` (or `list[ActionRecommendation]`).
  Confirm `_apply_authority_overrides` / `_action_id` still strip disallowed actions (they
  already handle dicts).
- `SeverityRationaleAdvisory`: add validation aliases so `why_p2→why_selected`,
  `why_not_p1→why_not_higher`, `missing_evidence_for_p1→missing_evidence_for_higher`,
  `escalate_to_p1_if→escalate_if`. Pydantic `AliasChoices`, not silent drop.
- Tests: each of the 5 captured outputs now `parsed_ok && schema_valid && accepted`,
  with the SAME override/guard findings asserted (execution_eligible flipped, etc.).
  No authority weakened — only shape widened.

### 3J-J.2 — Prompt + registry vocabulary reconciliation (backend)
- Collapse skill validation to a single source of truth: `app.routing.skills.validate_skill`
  and `app.skills.registry` must agree (`mitre_mapping` is valid in registry but rejected
  by the routing validator today).
- Align `prompts.py` allowed-value lists to the real backend enums: use-case ids,
  `SOURCE_IDS`, pipeline-stage skill ids, `RequestedOutputType`. Decision below.
- Tests: intent fixture (with alert context) validates against real registries; a
  no-context intent fixture still forces clarification deterministically.

**Open decision (default assumption):** the HF test prompt invented `soc_map_mitre`,
`mitre_kb`, `mitre_lookup`. Backend registries are the source of truth → fix the prompt to
teach real enums, do NOT invent new registry entries, unless COE confirms these belong.

### 3J-J.3 — Captured fixtures + bake script + snapshot test + scenario wiring (backend)
- Store the 5 captured raw outputs as fixtures (e.g. `backend/app/demo/llm_fixtures/`),
  origin-tagged `coe_captured_foundation_sec` (distinct from `coe_synthetic_fixture`).
- Bake script `python -m scripts.bake_llm_governance_fixtures`: raw → adapter (overrides)
  → semantic guards (run once here, offline) → emits governed payload + governance diff
  (warnings, disagreements, guard findings) → writes baked JSON.
- Snapshot test re-runs the bake on every test run and asserts equality with stored baked
  JSON — catches drift when adapter/guards change. Regeneration command documented.
- Wire baked governed output + governance diff into `demo/scenarios.py` scenario data.
  Demo runtime imports neither `llm.adapter` nor `answer_guard.rules` (grep-asserted).

### 3J-J.4 — Frontend governance expander (frontend)
- "Model output governance / Why V.AI SOC changed this" collapsible, default closed.
  Analyst summary remains the landing content.
- Renders governance diff: each override/guard finding as `raw → governed` with the
  warning id (e.g. `llm_execution_eligibility_ignored`, `guard.aggregate_overclaim`).
- Reuse `InvestigationLineagePanel` styling or extend it; do not introduce a new design
  language. Types in `frontend/src/types/api.ts`.
- Empty-diff case (e.g. a near-clean output) renders "no overrides required" — a demo
  fact, not a bug.

## Invariants preserved
- No final LLM synthesis; no live LLM calls; Answer Guard execution stays disabled.
- Raw LLM output never shown as the final answer (only inside the governance reveal, labelled).
- LLM SPL never execution-eligible; MCP gates and SAIA candidate-only untouched.
- Guards/adapter dormant in live demo + chat path; exercised only by bake script + tests.

## Verification
- `cd backend && python3 -m pytest`
- `cd frontend && npm run build`
- `python3 -m test_harness.harness.runner --json` and with `TELEMETRY_MODE=none`
- `git diff --check`
- grep-assert: `demo/` does not import `llm.adapter` or `answer_guard.rules`.
