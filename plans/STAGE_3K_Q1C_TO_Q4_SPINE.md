# Stage 3K — Q1C → Q4 Spine

Single reference document for the Q1C → Q4 stage program. Agents read this before doing anything in the Q1C → Q4 scope, and report status back against the tables at the end.

This document is canonical. The individual stage plan files give detail; this file gives the hierarchy, the rules, and the reporting contract.

---

## 1. Where we are (Foundations — Done)

| Layer | Stage | What it gives us |
|-------|-------|------------------|
| Routing | R1 | Route-plan schema, preflight, validator, normalizer (`app/routing/route_plan_*`) |
| Routing | R2 | Route-plan shadow integration in `/chat` (`RoutePlanShadowEnvelope`, lineage builder) |
| SPL | Q1A | SPL validator supports `raw_search`, `tstats_datamodel`, `from_datamodel` (`app/safeguards/spl_validator.py`) |
| SPL | Q1B | Template registry schema for CIM/tstats/datamodel templates + 3 disabled sample templates (`app/spl/template_registry.py`) |

These are the substrate the rest of the spine builds on. **No stage below is allowed to weaken them.**

---

## 2. Logic Hierarchy (the main product path)

```
user query
   │
   ▼
deterministic preflight                                          (R1)
   │
   ▼
[ shadow ] LLM route-plan candidate generator (Foundation-sec-Instruct)   (Q1F)
   │
   ▼
deterministic normalizer + route-plan validator                  (R1)
   │
   ▼
deterministic composition matrix
   │
   ▼
deterministic template matcher                                   (Q1C core)
   │           ▲
   │           │  [ shadow ] semantic hints sidecar (datamodel / field aliases)  (Q1C LLM-assist)
   │
   ▼
deterministic template renderer                                  (Q1D core)
   │           ▲
   │           │  [ shadow ] parameter extraction sidecar (host/src_ip/limit/time)  (Q1D LLM-assist)
   │
   ▼
Q1A SPL validator                                                (existing)
   │
   ▼
deterministic evidence-output contract + route_plan_shadow lineage   (Q1E)
   │
   ▼
[ shadow ] LLM-narrated analyst summary                          (Q1G)
   │
   ▼
deterministic IOC lookup binding (if route needs lookup)         (Q2)
   │
   ▼
deterministic vetted detection binding (if route needs detection)  (Q3)
   │
   ▼
governed SOC pattern coverage pack (selection / packaging)       (Q4)
   │
   ▼
MCP execution gate                                               (existing, deterministic)
   │
   ▼
[ NOT YET ] real MCP execution / final synthesis / Answer Guard  (future, out of scope here)
```

Read the chain top-to-bottom. **Every arrow that crosses from `[ shadow ]` back into the deterministic chain passes a schema-bounded adapter and a deterministic validator.** Deterministic always wins.

---

## 3. Stage Index

| Code | Stage | File | Status |
|------|-------|------|--------|
| — | Roadmap index | `plans/2026-05-28_0523_stage-3k-q1c-q4-roadmap.md` | Proposed |
| Q1C | Deterministic dry-run route-plan ↔ template matching (+ LLM-assist semantic hints sidecar) | `plans/2026-05-28_0523_stage-3k-q1c-route-plan-template-match.md` | Proposed |
| Q1D | Deterministic non-executable SPL rendering for sample templates (+ LLM-assist parameter extraction sidecar) | `plans/2026-05-28_0523_stage-3k-q1d-sample-template-spl-render.md` | Proposed |
| Q1E | Evidence output contract + `route_plan_shadow` lineage | `plans/2026-05-28_0523_stage-3k-q1e-evidence-contract-lineage.md` | Proposed |
| Q1F | LLM route-plan candidate generation in shadow mode (Instruct only) | `plans/2026-05-28_0523_stage-3k-q1f-llm-route-plan-shadow.md` | Proposed |
| Q1G | LLM-narrated analyst summary in shadow mode | `plans/2026-05-28_0523_stage-3k-q1g-llm-narrated-analyst-summary-shadow.md` | Proposed |
| Q2 | Local IOC / threat-intel lookup framework (deterministic core only) | `plans/2026-05-28_0523_stage-3k-q2-local-ioc-lookup.md` | Proposed |
| Q3 | Vetted detection binding framework (deterministic core only) | `plans/2026-05-28_0523_stage-3k-q3-vetted-detection-binding.md` | Proposed |
| Q4 | First governed SOC pattern coverage pack (deterministic runtime + author-time LLM CLI) | `plans/2026-05-28_0523_stage-3k-q4-pattern-coverage-pack.md` | Proposed |

---

## 4. Execution Order (approved)

1. Land roadmap + 9 plan files in one commit. (Plans only.)
2. **Q1C** — deterministic core + LLM-assist semantic hints sidecar. Pause for review.
3. **Q1D** — deterministic core + LLM-assist parameter extraction sidecar. Pause.
4. **Q1E** — deterministic only. Pause.
5. **Q1F** — Instruct route-plan candidate, shadow. Pause.
6. **Q1G** — Instruct analyst-summary narration, shadow. Pause.
7. **Q2** — deterministic IOC registry (no LLM-assist). Pause.
8. **Q3** — deterministic detection binder (no LLM-assist; family suggestion already enters via Q1F). Pause.
9. **Q4** — deterministic manifest + author-time LLM CLI. Pause.

Never skip a pause. Never combine two stages in one commit unless the spec for that stage explicitly says so.

---

## 5. Universal LLM Boundary (must appear verbatim in every LLM-touching commit message and every stage plan)

> LLM assistance is candidate-only. Deterministic core owns validation, normalization, binding, rendering, execution eligibility, and all blocking decisions. If LLM output disagrees with deterministic validation, deterministic wins and the disagreement is recorded.

Hard rules:

- Only **Foundation-sec-Instruct** is allowed for any LLM-assist role in this program.
- **Foundation-sec-Reasoning is excluded** from every routing / matching / rendering / narration role until parser and final-output stability is proven. Any LLM Registry attempt to bind a reasoning model to one of these roles is rejected with reason `reasoning_model_not_allowed_for_<role>`.
- Every LLM output passes: preflight → normalizer → route-plan validator → composition matrix → template selector → SPL validator → MCP execution gate.
- LLM must never:
  - generate executable SPL directly;
  - select MCP tools directly;
  - pick `template_id`;
  - invent `lookup_name` values;
  - invent `detection_ref` values;
  - decide route readiness;
  - authorize execution;
  - use confidence as authority.

---

## 6. Per-Stage LLM Posture

| Stage | Deterministic core | LLM sidecar | LLM role(s) |
|-------|--------------------|-------------|-------------|
| Q1C | `template_matcher.py` | `template_matcher_llm_assist.py` (semantic hints only: `source_class_hint`, `datamodel_hint`, `field_aliases`) | `template_match_semantic_assist` (Instruct only) |
| Q1D | `template_renderer.py` (pure function) | `template_renderer_llm_assist.py` (parameter extraction only: `host`, `user`, `src_ip`, `dest_ip`, `result_limit`, `time_window`) | `template_render_parameter_assist` (Instruct only) |
| Q1E | `lineage/builder.py` + `RoutePlanShadowEnvelope` extensions | None | n/a |
| Q1F | Existing deterministic routing | `llm_route_plan_candidate.py` (full route-plan candidate JSON, shadow only) | `route_plan_candidate_generator` (Instruct only) |
| Q1G | `analyst_summary_skeleton.py` (deterministic 1-sentence fallback) | `analyst_summary_llm_assist.py` (2-sentence + 3 bullets narration, shadow only) | `analyst_summary_narration` (Instruct only) |
| Q2 | `ioc_registry.py` + `ioc_lookup.py` | None this stage | n/a (re-evaluated after Q2 lands) |
| Q3 | `detection_binder.py` | None this stage; family suggestion arrives via Q1F | n/a (binder is registry-only) |
| Q4 | `coverage_loader.py` + Pydantic manifest validator | Author-time CLI in `tools/coverage_authoring/` only; **never runs in `/chat`** | `coverage_drafter` (Instruct, author-time only) |

---

## 7. Cross-Stage Rules (apply to every stage)

### 7.1 Boundary

- Never weaken Q1A validator checks.
- Never weaken Q1B template-schema CIM safety contracts.
- Never weaken MCP / SPL execution gates.
- Never silently promote `sample_only=True` templates to production.
- Never relabel a synthetic fixture as a captured live run.
- Never combine workflow / connection-readiness / UI changes in one commit unless the stage plan explicitly says so.

### 7.2 LLM-Assist sidecar contract

Every `_llm_assist` module follows the same shape:

1. Input is structured (validated route plan + structured context).
2. Output is a **strict JSON schema** parsed by the guarded LLM adapter (`app/llm/adapter/`).
3. Adapter strips fields outside the schema, fields containing SPL fragments, fields containing forbidden identifiers (`template_id`, `detection_ref`, `lookup_name` where forbidden).
4. Closed enums are enforced (datamodels, fields, families, metrics, query shapes).
5. Regex allowlist runs on every extracted scalar value.
6. Deterministic core runs in parallel with a **soft 1.5s timeout** on the sidecar; if sidecar times out, deterministic proceeds without it and the envelope records `llm_assist_timed_out=true`.
7. **Disagreement-recording rule:** every divergence between sidecar output and deterministic outcome is captured as a `disagreements[]` entry in `route_plan_shadow` with `field`, `llm_value`, `deterministic_value`, `reason_for_deterministic_win`.
8. Reasoning model assigned to any sidecar role → rejected.

### 7.3 Wording rules (lineage / UI / docs)

Allowed when surfacing any LLM-assist / shadow output:

- "Dormant route-plan shadow"
- "Template candidate only"
- "Not executed"
- "Execution authorized: false"

Forbidden without an explicit dormant / non-executed marker:

- "this would run"
- "this is what executes"
- "ready to run"
- "we ran"
- "results show" (when nothing executed)

### 7.4 Fixture honesty

Every fixture produced in Q1C / Q1D / Q1E / Q1F / Q1G / Q2 / Q3 / Q4 is labelled:

- `coe_synthetic_fixture = true`
- `captured_live_run = false`
- `production_execution = false`

No fixture is relabelled later. Renaming a synthetic fixture to a captured-live-run set in a later stage is a blocking error.

### 7.5 Telemetry

Every stage that adds a new code path records:

- a structured per-turn JSONL line with `trace_id`, stage code, deterministic outcome, sidecar outcome (if any), disagreements.
- `mcp_called=false`, `spl_executed=false`, `execution_authorized=false` for all Q1C → Q1G work.

---

## 8. Required-Run Verification (every stage)

Run, and report results in the stage status report:

```bash
cd backend && python3 -m pytest
python3 -m test_harness.harness.runner --json
TELEMETRY_MODE=none python3 -m test_harness.harness.runner --json
git diff --check
# only if frontend touched:
cd frontend && npm run build
```

Baseline expectation: backend pytest all-pass; harness 6/6 default; harness 6/6 with `TELEMETRY_MODE=none`; frontend build passes when touched.

---

## 9. Stage Status — Live (agent updates this table per stage)

Agents executing a stage must update both rows for that stage at end of session: the **Plan Status** row (Proposed → In Progress → Done / Superseded) and the **Verification** row (test counts, harness, frontend).

### 9.1 Plan Status

| Stage | Status | Commit hash | Notes |
|-------|--------|-------------|-------|
| Roadmap | Proposed | — | Plans only commit pending |
| Q1C | Proposed | — | |
| Q1D | Proposed | — | |
| Q1E | Proposed | — | |
| Q1F | Proposed | — | |
| Q1G | Proposed | — | |
| Q2 | Proposed | — | |
| Q3 | Proposed | — | |
| Q4 | Proposed | — | |

### 9.2 Verification

| Stage | Backend pytest | Harness default | Harness `TELEMETRY_MODE=none` | Frontend build | `git diff --check` |
|-------|---------------|-----------------|-------------------------------|----------------|--------------------|
| Q1C | — | — | — | — | — |
| Q1D | — | — | — | — | — |
| Q1E | — | — | — | — | — |
| Q1F | — | — | — | — | — |
| Q1G | — | — | — | — | — |
| Q2 | — | — | — | — | — |
| Q3 | — | — | — | — | — |
| Q4 | — | — | — | — | — |

### 9.3 Disagreements Log (Q1F / Q1G / Q1C-sidecar / Q1D-sidecar)

When a stage that runs an LLM sidecar lands, capture a sample-run summary here:

| Stage | Sample size | Disagreement rate | Most-common disagreement | Notes |
|-------|-------------|-------------------|--------------------------|-------|
| Q1C-sidecar | — | — | — | — |
| Q1D-sidecar | — | — | — | — |
| Q1F | — | — | — | — |
| Q1G | — | — | — | — |

---

## 10. Agent Reporting Contract

When an agent finishes a stage, the response must include, in this order:

1. `git status --short` before and after.
2. Files changed (path list).
3. Schema fields / modules added.
4. Sample artefacts added (templates, fixtures, registries) — with `coe_synthetic_fixture=true` confirmed.
5. Tests added (file path + test count).
6. Verification results (the four commands in section 8).
7. Confirmation that existing R1 / R2 / Q1A / Q1B behavior is unchanged.
8. Confirmation that no MCP execution / live LLM execution / final synthesis / Answer Guard / Experience Center behavior changed (unless the stage plan explicitly says otherwise).
9. Commit hash.
10. Updates to the **Plan Status** and **Verification** tables in section 9.

If any of the above cannot be confirmed, the agent says so explicitly. No silent pass.

---

## 11. Quick Pre-Flight Checklist (read before starting any stage in this program)

- [ ] I have read this spine document and the specific stage plan file.
- [ ] I understand the deterministic core vs LLM-assist sidecar split for this stage.
- [ ] I am not changing R1 / R2 / Q1A / Q1B behavior.
- [ ] I am not enabling MCP execution, live LLM execution, final synthesis, or Answer Guard.
- [ ] I am not promoting `sample_only=true` templates.
- [ ] If a sidecar exists in this stage, it uses Instruct only and has a strict JSON schema.
- [ ] Disagreement-recording is wired before any sidecar can run.
- [ ] Fixtures are labelled `coe_synthetic_fixture=true`.
- [ ] Wording rules from section 7.3 are followed.
- [ ] The commit message includes the universal boundary sentence (section 5).
- [ ] The spine status tables (section 9) will be updated at the end of the session.
