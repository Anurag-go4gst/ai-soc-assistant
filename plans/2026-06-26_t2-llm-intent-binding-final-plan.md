---
status: superseded
date: 2026-06-26
superseded_by: plans/2026-06-27_handoff-t2-completion-consolidated.md
---

> **Superseded (2026-06-27):** Implementation complete on `master` @ `ca3249b`. Use [`2026-06-27_handoff-t2-completion-consolidated.md`](2026-06-27_handoff-t2-completion-consolidated.md) as the single source of truth. This file is retained for history only.

# T2 LLM Intent + Binding Final Plan

## Status

Proposed for review before implementation.

## Objective

Make T2 / out-of-registry SOC search questions produce high-fidelity, review-only answers by ensuring query understanding, LLM advisory slots, deterministic slots, source-profile bindings, SPL draft generation, metadata, and final rendering all use one canonical binding path.

This plan closes the class of issue where the route is correct and governance is safe, but the generated review-only SPL drops user constraints or falls back to placeholder searches.

## Non-Negotiable Safety Boundaries

- No live-result claims without MCP / Splunk execution.
- No severity assignment from draft SPL alone.
- No confirmed MITRE claim from draft SPL alone.
- No candidate SPL execution.
- LLM is advisory for intent and slots only.
- User-explicit constraints always win.
- Source profile / Environment KB may bind SPL sources, fields, lookups, CIDRs, and omitted time defaults; it must not count as telemetry evidence.
- `RunContract` and `FinalEvidenceGate` remain final authority for evidence, claims, severity, MITRE, and render gates.
- Any production execution flag change is out of scope.

## Target Example Queries

These are acceptance probes, not one-off special cases:

1. `Search wineventlog for Event ID 4624 for user jsmith from substation subnets over the last 7 days.`
2. `Look across syslog and cisco_asa for permits from IT VLAN to OT DMZ on port 445.`
3. `Find users with more than 10 failed logins in 30 minutes.`

Expected paths:

| Probe | Expected detection family | Primary renderer |
|-------|---------------------------|------------------|
| Winevent Event 4624 | `unmapped_live_data_request` unless a governed Windows family is added later | `build_generic_live_data_spl_skeleton()` via the shared binding-aware skeleton path |
| Firewall permit | `unmapped_live_data_request` unless a governed firewall family is added later | `build_generic_live_data_spl_skeleton()` via the shared binding-aware skeleton path |
| Failed-login threshold | `auth_failed_login_threshold` when the family matcher selects it | `customize_auth_failed_login_threshold()` or the shared user-bound skeleton if family compatibility fails |

## Current Repo-State Findings

The repo already has most required architecture:

- `UserConstraintBindings` exists and merges user, deterministic, LLM, and source-profile slots.
- The intent advisor can carry `entity_slots_candidate`.
- `graph_node_query_to_intent()` preserves a typed `LLMIntentAdvisory` for live consumers.
- Intent scheduling now uses a protected intent reserve rather than the full sidecar timeout.
- Deterministic extraction already captures many fields in the target probes.
- The weak paths are multi-index validation/rendering, scope semantics, action semantics, LLM slot normalization, and generic live-data skeleton carry-through.

Do not recreate these systems. Extend the existing modules and tests.

## Canonical Data Flow

The final path must be:

```text
query
  -> understand_query
  -> graph_node_query_to_intent
  -> LLMIntentAdvisory.entity_slots_candidate
  -> deterministic slot extraction
  -> source-profile slot fill
  -> UserConstraintBindings
  -> template / generic user-bound skeleton
  -> DraftMetadataBuilder
  -> candidate SPL / draft preview
  -> RunContract + FinalEvidenceGate
  -> review-only renderer
```

Downstream SPL code should consume canonical bindings rather than raw LLM fields when bindings are available.

## Slot Precedence

```text
user_explicit > deterministic > llm > source_profile > template_default
```

Rules:

- A lower-precedence slot may fill a blank only.
- A lower-precedence slot must never override a user-explicit value.
- Conflicts must be recorded in `slot_conflicts` / `unbound_constraints`.
- Rejected slots must be visible in trace and not silently dropped.

## Phase 1: Canonical T2 Binding Contract

Extend the existing `UserConstraintBindings` contract rather than introducing a parallel model.

Keep routing metadata separate from slot authority:

- `intent_family`
- `path_type`
- `is_live_data_request`
- `is_review_only`

These fields may appear in trace/debug context around the binding, but they should not become lower-level SPL slot values.

Required canonical binding fields:

- `explicit_indexes`
- `explicit_sourcetypes`
- `explicit_event_codes`
- `explicit_users`
- `explicit_hosts`
- `explicit_src_ips`
- `explicit_dest_ips`
- normalized `src_scope`
- normalized `dest_scope`
- `explicit_src_zones`
- `explicit_dest_zones`
- `explicit_ports`
- `explicit_services`
- `explicit_action_semantics`
- `explicit_thresholds`
- `explicit_aggregation_subject`
- `explicit_time_window`
- `explicit_lookups`
- `slot_sources`
- `unbound_constraints`
- `rejected_slots`
- `normalized_slots`

Acceptance:

- One binding object shows deterministic, LLM, and source-profile contributions.
- Existing consumers continue to work.
- No downstream T2 SPL path requires direct reads from raw `entity_slots_candidate`.
- Routing metadata is visible for trace and decisions, but slot rendering continues to use validated binding fields.
- Slot conflicts continue to use the existing locations: conflict rows in `unbound_constraints` and `debug_trace["slot_conflicts"]`. Do not add a parallel top-level conflict model unless an existing consumer requires it.
- `src_scope` / `dest_scope` are normalized slot keys, not new top-level parallel dataclass fields unless an existing consumer requires explicit convenience accessors. `allowlist_semantic` remains separate from scope slots.

## Phase 2: Normalize LLM Intent Advisor Slots

Update the LLM intent advisor schema / prompt expectations and adapter normalization so the system accepts common LLM aliases.

Canonical keys:

```text
index
indexes
sourcetype
event_code
user
host
src_ip
dest_ip
src_scope
dest_scope
src_zone
dest_zone
port
service
action_semantic
threshold
threshold_comparison
aggregation_subject
time_window
lookup
```

Alias normalization:

```text
event_id -> event_code
eventid -> event_code
account -> user
username -> user
source_index -> index
data_source -> index
src_subnet -> src_scope
source_subnet -> src_scope
dest_subnet -> dest_scope
destination_subnet -> dest_scope
```

Implementation requirements:

- Extend the slot whitelist / validation path for any new canonical slot names before emitting them. In current code, `SLOT_TYPES` in `app/spl/spl_slot_binding_validator.py` rejects unknown keys, so `src_scope`, `dest_scope`, and `aggregation_subject` must be added and validated before Phase 5 / Phase 6 can work.
- Normalize aliases before `validate_slot_map()` so aliases do not appear as unsupported slots.
- Normalize LLM aliases inside `_llm_entity_slots()` or a dedicated `normalize_llm_entity_slots()` called before merge.
- Keep unsupported aliases visible in `rejected_slots` only when they truly remain unsupported after normalization.

Acceptance:

- LLM output with `event_id` reaches bindings as `event_code`.
- LLM output with `account` reaches bindings as `user`.
- LLM output with `src_subnet` reaches bindings as `src_scope`.
- LLM slots cannot override user-explicit values.
- Rejected or unsupported LLM slots are recorded.

## Phase 3: Protect Intent Advisor for T2

The intent advisor should be prioritized for:

- `explicit_log_search`
- `live_data_request`
- out-of-registry SOC-shaped query
- ambiguous T2 query
- query with meaningful entities but no registry match

Current implementation note:

- `should_prioritize_intent_advisor()` currently covers explicit log search / live-data request plus out-of-registry-style match paths. The "ambiguous T2" and "meaningful entities but no registry match" bullets require concrete signals in `query_signals.py` or equivalent explicit checks before they can be treated as implemented.
- Scheduling / reserve / trace wiring is already partially implemented in the current worktree. Remaining Phase 3 work is limited to concrete "ambiguous T2" and "meaningful entities" signals, or narrowing the acceptance criteria if those signals are intentionally deferred.

It should still be skipped for:

- unsafe execution / containment
- clear guidance / SOP-only request
- high-confidence deterministic exact or registry-backed match
- provider unavailable
- true budget exhaustion

Keep the current protected reserve model, but audit it:

- `insufficient_deadline_reserve` should fire only when remaining time is below the configured intent reserve.
- The scheduling trace must include remaining time, required reserve, skip policy, fallback reason, and selected route after skip.

Acceptance:

- T2 questions are not skipped merely because deterministic matching failed.
- A tight budget still fails closed and uses deterministic binding fallback.
- Targeted scheduling tests cover called, skipped, and budget-blocked cases.

## Phase 4: Fix Multi-Index Binding

For queries like:

```text
Look across syslog and cisco_asa ...
```

preserve all accepted indexes:

```spl
(index=syslog OR index=cisco_asa)
```

Acceptance:

- Multi-index list validates each index independently.
- A valid `indexes` list is not rejected by list stringification.
- `validate_slot_map()` / `validate_slot_value()` must handle Python list inputs for `indexes`, similar to existing special handling for `function_code` and `protocols`.
- Each index in `indexes` must pass the same pattern and allowlist validation as a single `index`.
- Extend partial acceptance to the `indexes` list, similar to the existing single-index `preserve_user_explicit_indexes` path in `build_user_constraint_bindings()`.
- Record rejected indexes in `unbound_constraints` while keeping accepted indexes in `explicit_indexes`.
- One bad index is recorded precisely; accepted indexes remain visible if policy allows partial binding.
- The final skeleton does not degrade to only the first index.
- Regression tests must verify the renderer consumes the full accepted index list, not only `indexes[0]`.

Current bug to remove:

- `indexes` is extracted as a Python list. Current validation stringifies it to `"['syslog', 'cisco_asa']"`, the brackets trip `_INJECTION_PATTERN`, and the whole multi-index slot is rejected as `slot_injection_blocked:indexes`. Fix list handling before renderer work.

## Phase 5: Fix Scope Semantics

Separate:

```text
src_scope
dest_scope
allowlist_scope
approved_destination_cidr
substation_subnet
```

Do not map `from substation subnets` to destination allowlist exclusion.

Expected behavior:

- Windows logon query: `from substation subnets` means source/client scope.
- OT Modbus unexpected destination query: `unexpected IPs` means destination allowlist / approved target semantics.
- Firewall zone query: `from IT VLAN to OT DMZ` means source zone and destination zone.

Current bug to remove:

- `extract_natural_language_slots()` currently maps any query containing `substation` to `allowlist_semantic=substation_subnet`. Because this is extracted as user-explicit, it can beat later lower-precedence source/LLM slots and force the wrong destination-allowlist rendering. Replace this with direction-aware extraction:
  - `from substation subnet(s)` -> `src_scope=substation_subnet`
  - `to substation subnet(s)` -> `dest_scope=substation_subnet`
  - ambiguous `substation subnet(s)` -> unbound scope requiring source-profile review unless family context safely resolves direction
  - `unexpected IP(s)` / `approved destination` -> allowlist semantics only when the phrase actually implies allowlist comparison

Acceptance:

- Windows Event 4624 query filters source/client subnet side when source-profile scope binding exists.
- Without source-profile scope binding, the answer marks the scope as unbound instead of inventing a CIDR.
- OT unexpected-destination behavior remains destination-oriented.
- Map `zone` from deterministic query understanding into `src_zone` / `dest_zone` when direction is known, or extend `_entities_to_slots()` so `zone_labels` do not collapse to a directionless `zone` when the query says `from ... to ...`.

## Phase 6: Fix Action Semantics

Action semantics must create real filters before aggregation or output.

Failed-login queries must filter failures before `stats`:

```spl
| eval action_norm=lower(coalesce(action, status, result, signature, ""))
| where like(action_norm, "%fail%") OR event_code_norm IN (...)
| stats count by user
| where count > 10
```

Permit queries must filter allowed traffic:

```spl
| where like(lower(coalesce(action,status,result,"")), "%permit%")
```

Acceptance:

- Failed-login threshold does not count all logins.
- Permit query filters permit / allowed traffic.
- Action semantics are visible in assumptions and binding metadata.
- Build filters and pre-where eval commands before aggregation; do not early-return from the threshold branch before action/event filters are applied.
- `failed_login` action semantics should render log-realistic failure matching such as `fail`, `failure`, relevant result/status fields, or validated event-code filters. Do not render only `like(..., "%failed_login%")`.
- For `auth_failed_login_threshold`, preserve the family-specific failure filter and inject the explicit threshold (`> 10`) and time window (`earliest=-30m latest=now`) when bound. Probe 3 may not use the generic skeleton.
- Render `aggregation_subject` when present: `user` -> aggregate by user, `host` -> aggregate by host, and default to user for failed-login threshold queries when the query says "Find users ...".

## Phase 7: Make Generic T2 Fallback Binding-Aware

Replace fixed generic live-data skeleton behavior with the binding-aware skeleton whenever useful bindings exist.

Entry point:

- `app/spl/draft_preview.py::build_generic_live_data_spl_skeleton()`
- The generic branch in `build_draft_preview(..., live_data_request=True)` when no strong family match is found.

Signature / threading requirement:

- Extend `build_generic_live_data_spl_skeleton(user_query, *, llm_intent_advisory=None, query_understanding=None)`.
- Pass `llm_intent_advisory` and available `query_understanding` from `build_draft_preview()` when `live_data_request=True` and no family match is found.
- Phase 11 LLM matrix tests must cover this generic branch; otherwise LLM slots can be correctly produced but never reach probes 1-2.

Current bad fallback:

```spl
search index=<index> sourcetype=<sourcetype> earliest=-24h latest=now
```

Required behavior:

- Build `UserConstraintBindings`.
- Merge deterministic, LLM, and source-profile slots.
- Render via the user-bound skeleton path.
- Gate on useful bindings such as `bindings.normalized_slots`, `bindings.explicit_indexes`, or other explicit constraints. When no useful binding exists, keep a conservative placeholder scaffold with precise unbound constraints.
- Attach binding metadata.
- Keep review-only governance labels.

Acceptance:

- If an index exists, no `<index>` placeholder is shown for that index.
- If an event code exists, event-code filter appears.
- If a user exists, user filter appears.
- If a threshold exists, aggregation appears.
- Missing values are represented as unbound constraints, not fake values.

## Phase 8: Source Profile / Environment KB Fill

Use source profile to fill blanks only.

Examples:

- `wineventlog` may fill `sourcetype=WinEventLog:Security`.
- Auth queries may fill `auth_index` / `auth_sourcetype`.
- Firewall queries may fill `firewall_index` / `firewall_sourcetype` / field mappings.
- Substation scope may fill `substation_networks_lookup` or `substation_cidr`.

Acceptance:

- Source profile never overrides user-explicit index.
- Source profile never counts as telemetry evidence.
- Missing source profile produces precise missing bindings.
- Source-profile field mappings affect SPL rendering only after validation.

## Phase 9: Draft Metadata and Renderer Alignment

Concrete entry points:

- `app/spl/draft_metadata_builder.py`
- `app/chat/review_only_spl_renderer.py`
- `app/chat/analyst_response_builder.py`
- `app/spl/draft_preview.py::build_draft_preview()`
- `app/spl/draft_preview.py::build_generic_live_data_spl_skeleton()`

The rendered answer must show:

- Review-only SPL draft.
- Execution: not executed.
- Evidence: no live telemetry collected.
- Bound user constraints.
- Source profile used.
- Missing bindings.
- Draft SPL.
- Assumptions.
- What cannot be concluded.

Acceptance:

- One clean answer body.
- No duplicate SPL warnings.
- No `live-backed` wording without execution.
- No P1 / P2 / P3 severity unless evidence / policy permits.
- No confirmed MITRE unless evidence permits.
- Binding trace is visible in technical/debug trace.

## Phase 10: End-to-End Regression Tests

Add tests for all three target probes.

Test harness requirement:

- For probes 1-2, use `build_draft_preview(query, spl_validation={"spl_template_status": "missing"}, live_data_request=True)` or equivalent live-data invocation so the generic T2 branch is exercised.
- Add `render_review_only_spl_answer()` or analyst-response assertions where useful to verify the answer stays review-only: no execution claim, no live-backed wording, no severity, and no confirmed MITRE.

### Probe 1

Query:

```text
Search wineventlog for Event ID 4624 for user jsmith from substation subnets over the last 7 days.
```

Must include:

```text
index=wineventlog
earliest=-7d latest=now
event_code_norm IN (4624)
user="jsmith"
```

Must not:

- claim execution
- claim matches found
- assign severity
- confirm MITRE
- apply destination allowlist semantics to `from substation subnets`

### Probe 2

Query:

```text
Look across syslog and cisco_asa for permits from IT VLAN to OT DMZ on port 445.
```

Must include:

```text
(index=syslog OR index=cisco_asa)
dest_port=445
src_zone="IT VLAN"
dest_zone="OT DMZ"
permit / allowed action filter
```

Must not:

- drop `cisco_asa`
- execute
- claim traffic exists

### Probe 3

Query:

```text
Find users with more than 10 failed logins in 30 minutes.
```

Must include:

```text
earliest=-30m latest=now
failed-login filter before stats
explicit aggregation by user
explicit threshold equivalent to count > 10
```

The SPL shape may come from `auth_failed_login_threshold` rather than the generic skeleton. Do not require the exact text `stats count by user` if the auth-family draft uses an equivalent failure-filtered aggregation.

Must not:

- count all logins
- claim users exist
- assign severity without evidence

## Phase 11: LLM-Skipped and LLM-Called Matrix

For each target probe, test:

- LLM disabled / skipped.
- LLM called with mock advisory slots.
- LLM called with alias slots.
- LLM called with a conflicting lower-precedence slot.

Acceptance:

- Deterministic path gives a useful review-only draft.
- LLM path improves or fills blanks.
- LLM path never weakens governance.
- LLM wrong slot cannot override user-explicit slot.
- If LLM skips due to reserve, fallback still uses deterministic bindings.

## Phase 12: Verification Gate

Run targeted backend tests:

```bash
cd backend
PYTHONPATH=../backend:.. python3 -m pytest \
  app/tests/test_intent_advisor_scheduling.py \
  app/tests/test_turn_llm_budget_deadline.py \
  app/tests/test_llm_intent_advisory_boundary.py \
  app/tests/test_llm_intent_advisor_phase2.py \
  app/tests/test_spl_query_fidelity.py \
  app/tests/test_draft_preview_customization.py \
  app/tests/test_live_data_request_routing.py \
  -q
```

If intent scheduling, prioritization, or query-signal behavior changes, also run:

```bash
PYTHONPATH=backend:. python3 scripts/eval_out_of_set_intent_probe.py --check
```

Then run canonical governance regression:

```bash
./scripts/run_stage3_governance_regression.sh
```

Do not commit eval baseline drift unless the task explicitly asks for a baseline refresh.

Ops note:

- If implementation introduces or renames configuration variables, update the relevant `.env.example` / sample environment documentation in the same change set. Do not mix unrelated runtime flag flips into this plan.

## Definition of Done

This plan is done only when:

- T2 intent advisor is protected and traceable.
- LLM slots are normalized and merged into canonical bindings.
- Deterministic fallback remains useful when LLM is skipped.
- Multi-index, threshold, action semantics, event code, user, time window, and subnet scope render correctly.
- Environment KB fills source / profile blanks without becoming evidence.
- The three target questions produce clean review-only answers.
- `FinalEvidenceGate` / `RunContract` still suppress fake evidence, fake severity, fake MITRE, and fake execution.
- Targeted tests and governance regression pass.

## Suggested Implementation Order

0. Inspect the dirty worktree, especially intent scheduling, budget, pipeline, config, and eval files.
1. Phase 2: extend `SLOT_TYPES` / validation and normalize LLM aliases.
2. Phase 4: fix `indexes` list handling plus per-index allowlist validation.
3. Phase 5: replace broad `substation -> allowlist_semantic` with direction-aware scope extraction.
4. Phase 6: compose action / event filters before thresholds in both skeleton and `auth_failed_login_threshold`.
5. Phase 7: make the generic live-data fallback binding-aware.
6. Phase 8: add source-profile fill for Windows / firewall / substation blanks only.
7. Phase 9: align metadata and renderer.
8. Phase 3: finish scheduling audit or add concrete signals if needed.
9. Phases 10-11: add end-to-end and LLM matrix tests.
10. Phase 12: run targeted tests and governance regression.

## Agent Playbook For This Plan

Before coding, inspect canonical seams:

```bash
rg "UserConstraintBindings|build_user_constraint_bindings|build_user_bound_skeleton" backend/app
rg "build_generic_live_data_spl_skeleton|unmapped_live_data_request" backend/app
rg "entity_slots_candidate|_llm_entity_slots" backend/app
rg "extract_natural_language_slots|validate_slot_map" backend/app/spl
```

Read:

- `backend/app/spl/user_constraint_bindings.py`
- `backend/app/spl/spl_slot_binding_validator.py`
- `backend/app/spl/template_slot_bindings.py`
- `backend/app/spl/draft_preview.py`
- `backend/app/spl/draft_preview_customization.py`
- `backend/app/chat/pipeline.py`

Use `backend/app/tests/test_spl_query_fidelity.py` and the Modbus coverage as the reference pattern for binding -> skeleton -> metadata tests.

## Common Implementation Mistakes

| Mistake | Effect |
|---------|--------|
| Fix extraction only, skip `validate_slot_map()` list handling | Multi-index still drops |
| Fix skeleton only, skip `build_generic_live_data_spl_skeleton()` | Probes 1-2 stay placeholder |
| Add `src_scope` to `SLOT_TYPES` but not skeleton rendering | Slot accepted but invisible in SPL |
| Test slot extraction only | False green; E2E still broken |
| Override `allowlist_semantic` without fixing precedence/source extraction | Substation bug persists |
| Wire LLM slots without alias normalization | `event_id` / `account` silently rejected |
| Touch `FinalEvidenceGate`, MCP execution flags, or eval baselines | Scope and governance drift |

## Review Addendum: Risks and Clarifications

### R1: Avoid a Parallel Binding Model

The phrase "canonical T2 binding contract" means extending `UserConstraintBindings`, not introducing a new object that drifts from the existing SPL path.

### R2: Keep LLM Advisory-Only

LLM slot extraction may influence draft SPL construction after deterministic validation. It must not create execution eligibility, severity, MITRE confirmation, source evidence rows, or policy overrides.

### R3: Be Precise About Scope

`substation subnets` is not always an allowlist. The implementation must consider phrase direction (`from`, `to`, `unexpected`, `approved`) and family context before choosing `src_scope`, `dest_scope`, or allowlist semantics.

### R4: Multi-Index Partial Acceptance Needs Policy Choice

If an index list includes both valid and invalid values, preserve valid user-explicit indexes for review-only drafts while recording rejected values. Governed executable paths must still fail closed unless existing policy explicitly supports partial acceptance.

### R5: Source Profile Values Must Be Validated

Environment KB values still need slot validation before rendering into SPL. COE/manual values have precedence but are not exempt from syntax safety.

### R6: Renderer Must Not Overclaim

A better draft can make the answer look more confident. Keep the renderer explicit that the output is review-only and no telemetry was collected.

### R7: Existing Dirty Worktree

At plan creation time, the repo already had uncommitted changes in intent, budget, config, and eval files. Implementation agents must inspect current state and avoid overwriting unrelated user changes.
