# Stage 3K Q1C → Q4 Roadmap (Index)

## Purpose

Sequenced bridge from current foundations (R1 route plan, R2 shadow integration, Q1A validator CIM shapes, Q1B template registry CIM metadata) to governed SOC pattern coverage. Builds the deterministic path:

```
route plan → template match → template render → SPL validation → evidence contract → IOC lookup → detection binding → demo coverage
```

Each stage stays deterministic, candidate-only, non-executable. No live LLM synthesis, no Answer Guard, no real MCP execution, no Experience Center change unless a stage explicitly says otherwise.

## Foundations Already In Place

| Stage | Status | Notes |
|-------|--------|-------|
| R1 — route plan schema, preflight, validator, normalizer | Done | `app/routing/route_plan_*` |
| R2 — route plan shadow integration in `/chat` | Done | `RoutePlanShadowEnvelope`, lineage builder |
| Q1A — SPL validator supports `raw_search`, `tstats_datamodel`, `from_datamodel` | Done | `app/safeguards/spl_validator.py` |
| Q1B — template registry schema for CIM/tstats/datamodel templates | Done | `app/spl/template_registry.py`, 3 disabled sample templates |

## Stages

| File | Stage | Status |
|------|-------|--------|
| `2026-05-28_0523_stage-3k-q1c-route-plan-template-match.md` | Q1C — deterministic dry-run route-plan ↔ template matching | Proposed |
| `2026-05-28_0523_stage-3k-q1d-sample-template-spl-render.md` | Q1D — deterministic non-executable SPL rendering for sample templates | Proposed |
| `2026-05-28_0523_stage-3k-q1e-evidence-contract-lineage.md` | Q1E — evidence output contract + `route_plan_shadow` lineage | Proposed |
| `2026-05-28_0523_stage-3k-q1f-llm-route-plan-shadow.md` | Q1F — LLM route-plan candidate generation in shadow mode (Instruct only) | Proposed |
| `2026-05-28_0523_stage-3k-q1g-llm-narrated-analyst-summary-shadow.md` | Q1G — LLM-narrated analyst summary in shadow mode (no answer change) | Proposed |
| `2026-05-28_0523_stage-3k-q2-local-ioc-lookup.md` | Q2 — local IOC / threat-intel lookup framework | Proposed |
| `2026-05-28_0523_stage-3k-q3-vetted-detection-binding.md` | Q3 — vetted detection binding framework | Proposed |
| `2026-05-28_0523_stage-3k-q4-pattern-coverage-pack.md` | Q4 — first governed SOC pattern coverage pack | Proposed |

## Sequencing Rationale

1. Q1C/D/E build the deterministic match → render → validate → evidence-contract bridge using existing sample templates. LLM is not involved.
2. Q1F introduces LLM assistance for route-plan candidate generation in shadow mode only, using Foundation-sec-Instruct, gated through every deterministic checkpoint.
3. Q2 adds IOC lookup as a special source class with air-gap staleness rules.
4. Q3 adds vetted behavioral detection binding (highest-risk class — never LLM-authored).
5. Q4 packages 8–10 representative SOC questions end-to-end with explicit fixture/source/IOC/detection readiness.

## Execution Order (approved)

1. Create roadmap index + 8 stage plan files (Q1C, Q1D, Q1E, Q1F, Q1G, Q2, Q3, Q4). (This commit.)
2. Execute Q1C (deterministic core + LLM-assist semantic hints sidecar). Pause for review.
3. Execute Q1D (deterministic core + LLM-assist parameter extraction sidecar). Pause.
4. Execute Q1E (deterministic only). Pause.
5. Execute Q1F (Instruct route-plan candidate, shadow). Pause.
6. Execute Q1G (Instruct analyst summary, shadow). Pause.
7. Execute Q2 (deterministic IOC registry only — no LLM-assist this stage). Pause.
8. Execute Q3 (deterministic detection binder only — LLM family classifier already lands via Q1F). Pause.
9. Execute Q4 (deterministic manifest + author-time LLM CLI). Pause.

## LLM Role and Boundary (applies to every stage in this roadmap)

Universal sentence (must appear verbatim in every stage plan and every commit message that touches LLM):

> LLM assistance is candidate-only. Deterministic core owns validation, normalization, binding, rendering, execution eligibility, and all blocking decisions. If LLM output disagrees with deterministic validation, deterministic wins and the disagreement is recorded.

Rules:

- Only Foundation-sec-Instruct is allowed for any LLM-assist role in this roadmap. Foundation-sec-Reasoning is excluded until parser / final-output stability is proven.
- LLM output must always pass: preflight → normalizer → route-plan validator → composition matrix → template selector → SPL validator → MCP execution gate.
- LLM must never: generate executable SPL directly; select MCP tools directly; pick `template_id`; invent `lookup_name` values; invent `detection_ref` values; decide route readiness; authorize execution; use confidence as authority.

Per-stage LLM posture:

| Stage | LLM core role | LLM sidecar role |
|-------|---------------|------------------|
| Q1C | Deterministic matcher | `_llm_assist` semantic hints only: `source_class_hint`, `datamodel_hint`, `field_aliases`. LLM never picks `template_id`. |
| Q1D | Deterministic renderer | `_llm_assist` parameter extraction only: `host`, `user`, `src_ip`, `result_limit`, `time_window`. Every value regex/schema-checked. No free-form SPL fragment. |
| Q1E | Deterministic lineage | No LLM in Q1E. Schema only extends to carry Q1F / Q1G outputs. |
| Q1F | Deterministic route authority | LLM produces route-plan candidate in shadow mode. Deterministic wins. |
| Q1G | Deterministic summary skeleton | LLM narrates analyst summary in shadow only. Final analyst answer unchanged. |
| Q2 | Deterministic IOC registry + staleness | No LLM-assist until registry exists. Re-evaluate after Q2 lands. |
| Q3 | Deterministic detection binder | No LLM-assist until registry exists. After registry exists, LLM may suggest `detection_family` only (already specified for Q1F path). Adapter strips `detection_ref`. |
| Q4 | Deterministic manifest validator | Author-time LLM assistant allowed (CLI / script). Never runs in `/chat`. |

Disagreement-recording rule (frozen): every LLM-assist output that diverges from the deterministic outcome is captured as a `disagreements[]` entry in the shadow envelope, including the field, LLM value, deterministic value, and reason for deterministic win.

## Cross-Stage Guarantees (apply to every stage)

- No SPL execution.
- No MCP call. No MCP execution gate change.
- No live LLM synthesis. No Answer Guard execution.
- No remediation / write actions.
- No weakening of Q1A validator checks.
- No weakening of MCP/SPL execution gates.
- No silent promotion of sample-only templates to production-ready.
- Test fixtures generated for this work are flagged `coe_synthetic_fixture`, not "captured live runs".
- Every stage commit is scoped per CLAUDE.md guidance (no combined workflow/UI/connection changes).

## Execution Plan

- Plan files only this session. No code changes from this roadmap session.
- Execution next session, stage by stage, with `plan-reviewer` before each stage and `validator` after.
- Update this index and the project `CLAUDE.md` Plans table as stages move Proposed → In Progress → Done.

## Risks / Open Questions Captured At Plan Time

- Q1C match-key contract must be explicit (skill × datamodel × group_by × metric × aggregation_shape). Detailed in Q1C plan.
- Q1D rendering uses route-plan time window with template `default_time_window` as fallback (per session decision).
- Q1E lineage extends existing `route_plan_shadow` block (per session decision); does not add a new sibling block.
- Q2 lookup staleness rule is mandatory, not optional.
- Q3 detection binding rejects any LLM-proposed `detection_ref` that is not in the registry.
- Q4 coverage pack must include at least one negative `cannot_route_*` case and at least one multi-signal case.

## Cross-Stage Wording Rules (lineage / UI / docs)

When any stage exposes shadow / candidate / template-match metadata to analyst, trace, or lineage surfaces, the wording must be one of:

- "Dormant route-plan shadow"
- "Template candidate only"
- "Not executed"
- "Execution authorized: false"

Forbidden wording without an explicit dormant/non-executed marker: "this would run", "this is what executes", "ready to run".

## Fixture Honesty Rules

For Q1C / Q1D / Q1E / Q1F / Q2 / Q3 / Q4, every synthetic fixture is labelled:

- `coe_synthetic_fixture` — true
- `captured_live_run` — false
- `production_execution` — false

No fixture is renamed or laundered into a "captured live" set in any stage.
