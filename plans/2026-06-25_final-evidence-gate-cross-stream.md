# Cross-Stream FinalEvidenceGate Plan

Date: 2026-06-25
Owner: implementation agent
Status: Done — implemented 2026-06-25. Phases 0-6 complete. Full backend suite 2959 passed / 1 skipped / 6 xfailed; governance regression PASS (dual_parity 120/120, soc_clean_answer 120/120, powergrid 50/50, template audit 16/16); frontend build green. Bug corrections applied during implementation (see "Bug Corrections" below).

## Bug Corrections (applied 2026-06-25)

1. Plan file paths corrected: `answer_contract.py` → `app/chat/contracts/answer_contract.py`; `source_evidence.py` → `app/evidence/source_evidence.py`.
2. Gate location: computed in `graph_node_context_finalize()` (the only point with all inputs in scope) via `build_final_evidence_gate(state, route=route)` in `run_contract_builder.py`, not threaded through `_context_stage()` (preserves its 3-tuple signature and the two positional-call tests).
3. List-surgery bug FIXED: the gate does NOT replace the list passed to `check_context_sufficiency()`. Sufficiency relies on seeing `ambiguous`/`blocked`/`failed` records (Rules 2/3/3b) and already self-filters by `collection_status=="collected"`; dropping them would change answer modes and break governance. The gate is the counts + permissions + classification authority; the full `source_evidence` list still flows to sufficiency/MITRE/severity.
4. Single source enforced: `build_run_contract` now projects every evidence-derived field from the gate (`collected_evidence_count`, `allow_live_result_language`, `allow_results_table`, `allow_mitre_mapping`, `allow_severity_assessment`, `effective_hil_required`). Dead PR #32 helpers (`_count_collected_evidence`, `_allow_mitre_mapping`, `_allow_severity_assessment`) and their orphaned family-set constants removed; `_policy_backed_in_catalog` retained and called by the gate builder.
5. Severity intent-family parity: the gate reads `intent.get("intent_family")`; `build_final_evidence_gate` aligns it to `route.intent_family` before the call, matching the prior `_allow_severity_assessment` semantics exactly.
6. Phase 4 satisfied by projection: renderer (`final_answer_readability.py`), `answer_contract.py`, lineage builder, analyst_response_builder, efficacy checks, and the fail-closed `final_answer_validator.py` already consume `run_contract.allow_*`; the gate becomes their source with no consumer changes.
7. Scenario G support: broadened gate `_REFERENCE_SOURCE_TYPES` to include `github`/`source_reference`/`vendor_bulletin`/`mitre_reference` (none produced today; forward-safe) so reference records never misclassify as collected environment evidence.

Files: NEW `app/evidence/final_evidence_gate.py`, `app/tests/test_final_evidence_gate.py` (22), `app/tests/test_final_evidence_gate_cross_stream.py` (9 A-H); EDIT `app/chat/run_contract_builder.py`, `app/chat/pipeline.py`.

## Review Fixes (applied 2026-06-25, post-review)

Four findings from code review, all fixed:

- **[P1] Severity not gated on all surfaces** — RunContract was gate-fed but raw `severity_decision` still fed lineage, governance trace, response payload, and `action_capability.reason`. FIX: new `apply_gate_severity_cap()` in `risk/severity_policy.py` caps a P1–P4 label to "Not assigned from this question alone" when `run_contract.allow_severity_assessment` is False, applied in `graph_node_context_finalize()` immediately after the analytics guard and BEFORE action-capability/lineage/governance/response builders — so every surface honors the gate. (Side effect: pg.dns.010 sentinel severity corrected P3 Medium → Not assigned; that P3 was a meaningless `default_no_policy` value the analytics guard missed. Sentinel baseline re-frozen, 1-line diff.)
- **[P1] Stale gate vs final RunContract** — the gate payload was attached early but `build_run_contract` was rebuilt later without the gate. FIX: recompute the gate at the final rebuild via `build_final_evidence_gate(...)`, pass it into `build_run_contract(..., gate=...)`, and refresh `structured_context["final_evidence_gate"]` + `state["final_evidence_gate"]`. Added a typed `final_evidence_gate` field to `StructuredContextPackage` so it actually surfaces (was being dropped by the typed schema).
- **[P2] Filtered "canonical" list footgun** — `to_dict()` no longer serializes full filtered records; emits `gated_source_evidence_refs` only. Dataclass docstring clarifies `gated_source_evidence` is a classified VIEW, never fed into sufficiency.
- **[P2] A–H tests pure-only** — added `app/tests/test_final_evidence_gate_pipeline.py` (4 real `/chat` response tests): gate-vs-run_contract consistency (catches stale gate), gate-disallowed severity not leaked into `severity_decision`/`action_capability.reason`, no results-table permission on review turns, and an `apply_gate_severity_cap` unit test.

Post-fix gates: full backend **2959 passed** / 1 skipped / 6 xfailed; governance regression **PASS**; frontend build green. New/edited: NEW `app/tests/test_final_evidence_gate_pipeline.py` (4); EDIT `app/risk/severity_policy.py`, `app/schemas/responses.py`, `app/chat/pipeline.py`, `app/evidence/final_evidence_gate.py`, `app/evals/fixtures/sentinel_baseline.json`.

## Objective

Implement one cross-stream `FinalEvidenceGate` inside the existing finalize path, not as a new planner/router edge. The gate must classify raw stream outputs before they feed context sufficiency, MITRE, severity, `RunContract`, `AnswerContract`, lineage, governance trace, action capability, or the final renderer.

Important: this plan must not duplicate the PR #32 `build_run_contract()` authority logic. `FinalEvidenceGate` becomes the single source for evidence classification and evidence-derived permissions; `build_run_contract()` consumes and projects the gate state.

The problem this plan addresses is the recurring "no live execution, but answer sounds confirmed" class of bugs across SPL, CVE, guided investigation, MITRE, GitHub/source-reference, RAG, and severity paths.

## Architectural Decision

Do not add a new graph edge. Compute the gate inside the context-finalize stage in `backend/app/chat/pipeline.py`. Concretely: call `apply_final_evidence_gate()` in `graph_node_context_finalize()` immediately after `_context_stage()` returns and before `build_run_contract()`/MITRE/severity. This is "inside the finalize path" and is the only point with all gate inputs in scope (`source_evidence`, `execution`, `route`, `intent_classification`, `evidence_plan`, `answer_contract`, `candidate_spl`, `spl_draft_preview`) without threading six new params through `_context_stage()` (which two tests call positionally). Attach `gate.to_dict()` to both `structured_context["final_evidence_gate"]` and `state["final_evidence_gate"]`.

Target flow:

```text
SPL/RAG/MCP/CVE/GitHub/reference stream outputs
-> structure_context()
-> check_context_sufficiency()
-> FinalEvidenceGate classification + gated permissions
-> MITRE decision
-> severity decision
-> RunContract projection from FinalEvidenceGate / AnswerContract
-> lineage / governance_trace / action_capability
-> renderer
```

Important naming rule:

- `_context_stage()` still returns the full packaged `source_evidence` list. Do not perform list surgery before sufficiency.
- `FinalEvidenceGate` classifies the full packaged list into counts, classes, refs, and permissions. It does not drop ambiguous/blocked/failed records from `source_evidence`.
- `gated_source_evidence` means "gate-classified evidence view/refs", not a replacement list passed into sufficiency.
- Downstream answer logic must consume gate counts and permissions for claims/rendering, while sufficiency continues to inspect full `source_evidence` and self-filter by `collection_status`.
- `RunContract` is the public/canonical response contract, but it must not independently re-decide evidence counts or render permissions once `FinalEvidenceGate` is present. It should project the gate result.

## Evidence Classes

Every stream output must be classified into exactly one of these classes:

```python
class EvidenceClass(str, Enum):
    COLLECTED_EVIDENCE = "collected_evidence"
    SOURCE_BACKED_REFERENCE = "source_backed_reference"
    REVIEW_ARTIFACT = "review_artifact"
    CANDIDATE_CLAIM = "candidate_claim"
    SUPPRESSED_CONFIRMED_CLAIM = "suppressed_confirmed_claim"
```

### collected_evidence

Provenance-backed evidence actually fetched or collected this turn and capable of supporting the relevant claim type.

Examples:

- Executed Splunk/MCP rows with execution provenance.
- Fetched local connector data.
- Imported telemetry, asset inventory, scanner export, or CMDB rows with provenance.

### source_backed_reference

Fetched or vendored source context that supports reference-backed guidance but not local environment confirmation.

Examples:

- RAG/SOP excerpt with source id.
- CVE advisory or vendored CVE snapshot status.
- Vendor bulletin.
- MITRE technique description.
- GitHub issue/PR/file content when used as source-reference context.

Allowed claims:

- "According to this source..."
- General guidance.
- Evidence to collect next.

Disallowed claims:

- Host is vulnerable.
- Exploit occurred.
- MITRE is confirmed.
- Incident severity is P1/P2/P3.

### review_artifact

Generated material for analyst review only. It is not source evidence.

Examples:

- SPL draft.
- SPL validation record.
- Checklist.
- Planned discovery call.
- Investigation plan.
- Route shadow metadata.
- Source-profile hint.

### candidate_claim

Unvalidated hypothesis or suggestion.

Examples:

- Possible exposure.
- Possible MITRE technique.
- Possible root cause.
- Possible severity.
- Possible vulnerable asset.

### suppressed_confirmed_claim

Any confirmed-sounding claim that lacks the required evidence.

Examples:

- "Detected"
- "Observed"
- "Found"
- "Confirmed"
- "Mapped to MITRE"
- "Host is vulnerable"
- "P2 incident"

## Gate Output

Add a normalized gate state, for example in `backend/app/evidence/final_evidence_gate.py`:

```python
@dataclass(frozen=True)
class GatedEvidenceState:
    evidence_class_by_ref: dict[str, EvidenceClass]
    collected_evidence_refs: list[str]
    source_backed_reference_refs: list[str]
    review_artifact_refs: list[str]
    candidate_claim_refs: list[str]
    suppressed_claims: list[str]
    collected_evidence_count: int
    source_backed_reference_count: int
    review_artifact_count: int
    candidate_claim_count: int
    allow_live_result_language: bool
    allow_results_table: bool
    allow_environment_fact_claims: bool
    allow_vulnerability_confirmed: bool
    allow_mitre_mapping: bool
    allow_severity_assessment: bool
    source_evidence_status: str
    mitre_visibility: str
    severity_label: str | None
    effective_hil_required: bool
    debug_raw_record_count: int
```

## Universal Claim Rules

1. Environment fact claims require local/environment evidence:
   - live MCP/Splunk rows, or
   - fetched local connector data, or
   - imported telemetry/asset/scanner/CMDB export with provenance.

2. Live-result language requires the correct collected evidence type. Reference-only or review-only paths must not render "detected", "observed", "found", "currently showing", "mapped to", or "confirmed".

3. `splunk_results_table` can render only when:
   - Splunk/MCP execution actually ran,
   - result count is greater than zero,
   - rows are linked to execution provenance.

4. CVE advisory/snapshot context is not vulnerable-host confirmation. "Host is vulnerable" requires:
   - asset identity,
   - installed product/package/version evidence,
   - affected-version logic,
   - scope/context evidence.

5. MITRE visibility has three allowed postures:
   - hidden/not applicable,
   - candidate/requires validation,
   - evidence supported.
   Only evidence-supported status can render as mapped/confirmed.

6. Severity P1/P2/P3 requires severity policy permission plus policy-backed alert context or sufficient environment evidence. If severity is disallowed, render "Not assigned from this question alone" or "Not assessed".

7. `effective_hil_required` is OR-derived from:
   - `planning_decision.hil_required`,
   - `evidence_plan.needs_hil` / `requires_hil`,
   - `answer_contract.hil_status` in required/clarification/execution approval states,
   - SPL validation review requirements,
   - live data request with execution not authorized,
   - CVE/vulnerability review without inventory/version/source evidence,
   - candidate claims that could affect response, severity, MITRE, or action.

## Chronology Of Implementation

Implement in this order. Do not broaden scope before the prior step is tested.

Short chronology:

```text
0. trace current path and baseline tests
1. pure gate model + unit tests
2. compute gate in graph_node_context_finalize() after _context_stage()
3. migrate PR #32 evidence/permission authority into the gate; make RunContract consume gate state
4. make MITRE/severity/renderer honor gate permissions
5. add cross-stream A-H regressions
6. run full backend + governance gates
```

### Phase 0 - Repo Trace And Baseline

1. Read the current code. Correct paths (verified 2026-06-25):
   - `_context_stage()` is defined in `backend/app/chat/pipeline.py` (around line 5533) and re-exported via `backend/app/api/routes_chat.py`; it returns a 3-tuple `(source_evidence, structured_context, context_sufficiency)`.
   - `graph_node_context_finalize()` in `backend/app/chat/pipeline.py` (around line 1566) is the only runtime caller.
   - `backend/app/chat/run_contract_builder.py`
   - `backend/app/chat/contracts/answer_contract.py` (NOT `app/chat/answer_contract.py`)
   - `backend/app/chat/final_answer_readability.py`
   - `backend/app/chat/final_answer_validator.py`
   - `backend/app/evidence/source_evidence.py` (NOT `app/chat/source_evidence.py`)
   - `backend/app/cve/evidence_adapter.py`
   - `backend/app/chat/hil_resolution.py` (`resolve_effective_hil_required`)
   - Existing callers/tests of `_context_stage` to keep green: `app/tests/test_mcp_loop_source_evidence.py`, `app/tests/test_evidence_context.py` (both unpack the 3-tuple).
2. Run the current focused tests before editing so failures are known:

```bash
cd backend
PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_answer_contract.py app/tests/test_mitre_decision_runtime.py app/tests/test_answer_efficacy_checks.py -q
```

### Phase 1 - Gate Model And Unit Tests

1. Add `backend/app/evidence/final_evidence_gate.py`.
2. Add `backend/app/tests/test_final_evidence_gate.py`.
3. Implement pure classification and permission logic without changing pipeline behavior yet.
4. Cover these unit cases:
   - SPL draft -> `review_artifact`
   - SPL validation -> `review_artifact`
   - CVE snapshot -> `source_backed_reference`
   - RAG hit -> `source_backed_reference`
   - MITRE candidate -> `candidate_claim`
   - Executed Splunk result rows -> `collected_evidence`
   - Non-executed path -> no table/live language permissions
   - Reference-only path -> no environment fact permission

Target command:

```bash
cd backend
PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_final_evidence_gate.py -q
```

### Phase 2 - Compute Gate In `graph_node_context_finalize()`

1. Leave `_context_stage()` return shape unchanged: `(source_evidence, structured_context, context_sufficiency)`.
2. Leave `structure_context()` and `check_context_sufficiency()` inputs unchanged. They must continue to receive the full packaged `source_evidence` list.
3. Verified bug to avoid: do NOT swap the list passed to `structure_context()`/`check_context_sufficiency()` to a filtered `gated_source_evidence` list. `check_context_sufficiency()` relies on seeing `ambiguous` RAG records (Rule 3 -> analyst review required), `blocked` records (Rule 2), and executed-zero-row records (Rule 3b). It already self-filters with `collection_status == "collected"` where appropriate.
4. In `graph_node_context_finalize()`, call `apply_final_evidence_gate()` immediately after `_context_stage()` returns and before the first `build_run_contract()` call, MITRE resolution, and severity resolution.
5. Pass the gate all inputs that are in scope in finalize but not cleanly available inside `_context_stage()`: `source_evidence`, `execution`, `route`, `intent_classification`, `evidence_plan`, `planning_decision`, `candidate_spl`, `spl_validation`, `spl_draft_preview`, selected use case / route metadata, and any available CVE/source-reference metadata.
6. Attach `gate.to_dict()` to both `structured_context["final_evidence_gate"]` and `state["final_evidence_gate"]`.
7. Keep raw stream outputs debug-only in control-plane trace. Do not delete records from canonical `source_evidence`; review-artifact suppression happens at the permission/render layer.

Target command:

```bash
cd backend
PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_soc_kb_retriever.py app/tests/test_answer_contract.py -q
```

### Phase 3 - RunContract And HIL Authority

1. Review the existing PR #32 logic in `backend/app/chat/run_contract_builder.py`, especially evidence counting, result-table permission, live-result language permission, MITRE permission, severity permission, and HIL derivation.
2. Move or delegate evidence-derived authority to `FinalEvidenceGate` instead of duplicating it. Keep `build_run_contract()` as a projector/adapter for the canonical response shape.
3. Update `backend/app/chat/run_contract_builder.py` to require/consume gate counts and permissions when available.
4. Ensure `collected_evidence_count`, `allow_results_table`, `allow_live_result_language`, `allow_mitre_mapping`, and `allow_severity_assessment` come from the gate.
5. Ensure `effective_hil_required` is computed once by the gate or by a shared helper called by the gate, then used by:
   - `RunContract`,
   - `planning_decision`,
   - `governance_trace`,
   - `answer_contract`,
   - `action_capability`.
6. Remove or bypass older fallback inference only after regression tests cover the equivalent behavior. If temporary fallback is needed during migration, mark it as compatibility-only and never let it override gate state.

Target command:

```bash
cd backend
PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_answer_contract.py app/tests/test_answer_efficacy_checks.py -q
```

### Phase 4 - MITRE, Severity, And Renderer Consumption

1. MITRE may still produce candidate artifacts, but rendered confirmed mapping must honor gate permissions.
2. Severity may still compute internally, but rendered/action-facing severity must be "Not assigned" or "Not assessed" when gate disallows assessment.
3. `final_answer_readability.py` must render from gate/run-contract permissions, not raw stream fields.
4. `final_answer_validator.py` must fail closed on gate invariant violations.

Target command:

```bash
cd backend
PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_mitre_decision_runtime.py app/tests/test_mitre_risk_rationale.py app/tests/test_answer_efficacy_checks.py -q
```

### Phase 5 - Cross-Stream Regression Tests

Add integration or focused pipeline tests for:

A. Review-only SPL, no execution.

- Draft SPL is `review_artifact`.
- `collected_evidence_count == 0`.
- No `splunk_results_table`.
- Severity not assigned.
- MITRE hidden/not assessed.
- HIL true.

B. CVE review-only, no live scan.

- CVE/advisory context is `source_backed_reference` or review artifact, not environment evidence.
- No `splunk_results_table`.
- No P3 Medium from `default_no_policy`.
- Answer says vulnerable hosts cannot be confirmed without inventory/version/exposure evidence.

C. MITRE candidate, no behavior evidence.

- Candidate techniques are hidden or require validation.
- No confirmed/mapped wording.

D. `severity.allowed=false`.

- No P1/P2/P3.
- No `default_no_policy -> P3`.

E. Guided investigation with no collected evidence.

- `source_evidence.status` is metadata-only/review-only.
- Checklist/guidance is allowed.
- No confirmed environment claims.

F. RAG no-match general guidance.

- No source-backed claims.
- General guidance has limitation wording.
- No "according to source" wording.

G. GitHub/source-reference advisory-only.

- Fetched source content can support source-backed reference claims.
- It cannot support environment execution claims, severity, or confirmed MITRE by itself.

H. Live MCP executed fixture.

- `collected_evidence_count > 0`.
- Results table allowed only with execution provenance.
- Live-result language allowed only for supported facts.
- Severity/MITRE still require their own policy/evidence thresholds.

Target command:

```bash
cd backend
PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_final_evidence_gate.py app/tests/test_answer_contract.py app/tests/test_mitre_decision_runtime.py app/tests/test_answer_efficacy_checks.py -q
```

### Phase 6 - Full Gates

Run:

```bash
cd backend
PYTHONPATH=../backend:.. python3 -m pytest
```

Then:

```bash
./scripts/run_stage3_governance_regression.sh
```

If frontend-visible response shapes change, also run:

```bash
cd frontend
npm run build
```

## Acceptance Criteria

For every non-executed path:

- No `splunk_results_table`.
- No live-result language.
- No confirmed MITRE.
- No P1/P2/P3 unless policy-backed evidence exists.
- Review artifacts are not counted as collected evidence.
- `action_capability.hil_required` is consistent with `effective_hil_required`.
- Final answer states missing evidence and what cannot be confirmed.

For fetched reference-only paths:

- Source-backed guidance is allowed.
- Local environment confirmation is not allowed.
- Severity, MITRE, and environment facts still require the correct evidence type.

For live executed paths:

- Results tables and live-result language are allowed only for facts backed by execution provenance.
- Severity and MITRE still honor their own thresholds.

## Review Notes Before Implementation

- Do not create a new planner/router edge.
- Do not fix SPL, CVE, MITRE, GitHub, RAG, and severity with separate one-off patches.
- Do not let SPL drafts, SPL validations, CVE snapshots, MITRE candidates, checklists, or source-profile hints become collected source evidence.
- Do not make `source_backed_reference` mean local environment confirmation.
- Do not treat "packaged evidence records" as equivalent to collected evidence.
- Keep raw stream outputs only in debug/control-plane trace.
- Report remaining bypasses explicitly instead of silently patching unrelated streams.

## Plan Review

Reviewed against the current pipeline shape on 2026-06-25.

Assessment:

- The plan matches the existing architecture after correction: `graph_node_context_finalize()` is the right place because `_context_stage()` must keep feeding full source records into sufficiency, while finalize has all route/intent/evidence inputs needed by the gate before `build_run_contract()`, MITRE, and severity.
- The plan does not require a new planner/router edge. It preserves the current finalize node and narrows authority there.
- The plan must treat PR #32 `build_run_contract()` behavior as existing authority to be centralized, not re-created. The implementation should migrate/delegate that logic into `FinalEvidenceGate`, then let `RunContract` mirror the gate result.
- The key implementation risk is list surgery: do not remove ambiguous/blocked/failed records before sufficiency. `source_evidence` remains the full packaged list; the gate supplies counts, classifications, refs, and permissions.
- The second risk is double-counting reference material. RAG/CVE/GitHub references can be source-backed context, but they must not increment environment-evidence counts or allow severity/MITRE/live-result claims by default.
- The third risk is HIL divergence. `effective_hil_required` must be computed once, then propagated to `RunContract`, `planning_decision`, `governance_trace`, `answer_contract`, and `action_capability`.

No contradictory turns found after the refinement above. The plan intentionally allows source-backed reference guidance while blocking local-environment confirmation, which resolves the main semantic tension in the original instruction.
