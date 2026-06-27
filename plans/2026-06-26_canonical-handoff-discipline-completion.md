---
name: Canonical handoff discipline completion
overview: "Complete T0/T1/T2 handoff discipline without replacing RouteContract / FinalEvidenceGate / RunContract. Each decision area gets exactly one authority; RunContract remains finalize-only public authority for execution, HIL, result claims, render permissions, and SPL lifecycle."
status: proposed
date: 2026-06-26
depends_on:
  - plans/2026-06-24_run-contract-canonical-state.md
  - plans/2026-06-25_final-evidence-gate-cross-stream.md
  - plans/2026-06-25_spl-query-fidelity-completion.md
  - plans/2026-06-26_full-canonical-handoff-t0-t1-t2-mcp.md
todos:
  - id: ws1-routing-row-authority
    content: "WS1: Wire row_authority_summary + catalog registry_tier into route adjudication; block weak-exact from exact_105_registry"
    status: pending
  - id: ws2-slot-constraint-projection
    content: "WS2: Introduce SlotConstraintProjection as SPL/planning artifact authority; unify EvidencePlan summary + SPL path + trace"
    status: pending
  - id: ws3-resourceplan-dispatch
    content: "WS3: Make execute_plan_dispatch step-driven; enforce skill-contract blocked_policy; legacy predicates become plan inputs only"
    status: pending
  - id: ws4-mcp-decision-surface
    content: "WS4: Single MCP decision on ResourcePlan MCP step; RunContract projects final posture"
    status: pending
  - id: ws5-debug-trace-labeling
    content: "WS5: Label debug/governance panels AUTHORITATIVE / PLANNING / ADVISORY / DIAGNOSTIC"
    status: pending
  - id: ws6-llm-advisor-hardening
    content: "WS6: Compact intent advisory schema, graceful drop/repair, semantic constraint hints; deterministic pre-parse always wins"
    status: pending
  - id: ws7-answer-pack-lifecycle
    content: "WS7: Wire answer_packs.json promotion path T2 lab → candidate → reviewed → governed template (separate PR)"
    status: pending
  - id: ws8-healthy-vs-bug-tests
    content: "WS8: Add healthy-contradiction vs real-bug assertion suite and debug bundle checks"
    status: pending
isProject: false
---

# Canonical Handoff Discipline — Completion Plan

## Executive Summary

Handoff discipline is partial, not complete. The shipped path remains:

```text
query -> query_to_intent -> route_adjudication -> route_contract
  -> evidence_planning/resource_plan -> execution/evidence loop
  -> FinalEvidenceGate -> RunContract -> governed answer
```

No new weak-case architecture should be introduced. Weak T0/T1/T2 cases may add evidence,
trace, or review-only artifacts, but they must flow through the same canonical handoff.

## Current State

- `RouteContract`, `FinalEvidenceGate`, and `RunContract` are the final public authority for route, execution/HIL, live-result language, and render permissions.
- Row-authority metadata is now visible in route adjudication as a trace-only advisory signal. It does not yet replace exact-105 routing authority.
- ResourcePlan composition now keeps an MCP step present for live-evidence needs and marks it `blocked_policy` when `mcp_allowed=false`.
- T2 SPL-native review-only generation is improved, but the SPL degrade chain remains mixed: template, T2 native, lab preview, and LLM failover still meet in `pipeline.py` and should be consolidated behind one SPL artifact authority.
- Answer-pack promotion/demotion remains skeletal; no populated `answer_packs.json` is live authority.

## Workstreams

### WS1 Routing + Row Authority

Status: partial, flag-gated enforcement for exact-105 route authority.

Done:

- `RouteAdjudication` carries `row_authority_status`, `row_authority_decision`, `row_authority_note`, and fallback reason.
- Weak exact rows such as q046 are visible as `would_withhold_exact_registry`.
- T1 SPL-native catalogue/meta rows are visible as `catalog_t1_spl_native`.
- When `route_authority_operation_authoritative_enabled=true`, exact-105 registry routing now also requires `row_authority_decision=exact_known_authority_ready`; weak exact rows fall through to the canonical EvidencePlan live/hybrid route.

Remaining:

- Broaden CP-on / CP-off route matrix coverage beyond q046 and synthetic ready rows.
- Prove Environment KB/source-profile details still flow through weak-exact fallback in full `/chat` tests.

### WS2 Slot Constraint Projection

Status: partial.

Create one `SlotConstraintProjection` read model for SPL/planning:

- User constraints.
- Environment KB/source-profile fields.
- COE/manual overrides.
- LLM advisory extracted slots.
- Missing/ambiguous slot reasons.

Authority rule: user/COE/Environment KB wins; LLM fills blanks only.

Done:

- `SlotConstraintProjection` wraps existing `UserConstraintBindings` and source-profile binding; it does not introduce a third merge algorithm.
- Template SPL and T2 SPL-native candidates now carry the projection for audit/drift visibility.
- Tests cover user-explicit index precedence over source-profile defaults, off-shift source-profile constraints, planning drift, SCADA metrics, and Cisco ASA lookup/index preservation.

Remaining:

- Feed the same projection into EvidencePlan summaries before final planning, then compare planning-vs-SPL generation drift end to end.
- Keep the SPL degrade chain behind one review-only SPL artifact authority rather than letting template, T2-native, lab preview, and LLM failover present competing status surfaces.

### WS3 ResourcePlan Dispatch

Status: partial.

Done:

- ResourcePlan composer emits the same MCP step for MCP-needed cases.
- Skill-contract vetoes and MCP-off cases are represented as step status, not route replacement.

Remaining:

- Move execution dispatch toward consuming `PlanStep.status/resource_id/purpose` directly.
- Legacy booleans should remain compatibility projections, not independent execution authority.

### WS4 MCP Decision Surface

Status: partial.

Done:

- `mcp_allowed` nullable normalization fails closed.
- MCP-off live evidence can be represented as `blocked_policy` on the MCP step.

Remaining:

- Ensure API, trace, planner, executor, and RunContract all project the same MCP decision object.
- Prove off/mock/live use the same step id and envelope.

### WS5 Debug / Governance Trace Labels

Status: pending.

Every debug panel should label fields as one of:

- `AUTHORITATIVE`
- `PLANNING`
- `ADVISORY`
- `DIAGNOSTIC`

This prevents operators from confusing row-authority trace or LLM hints with runtime authority.

### WS6 LLM Advisor Hardening

Status: partial.

Keep LLM output advisory:

- Compact JSON schema.
- Graceful drop/repair on malformed output.
- Deterministic pre-parse and slot projection always win.
- No LLM-to-MCP path.
- Intent-advisor T0 skip is now gated by `can_skip_llm_for_t0`; weak exact rows no longer skip LLM solely because they matched exact-105.

Remaining:

- Extend the same promotion-aware skip contract to final synthesis/narration surfaces where applicable.

### WS7 Answer-Pack Lifecycle

Status: pending.

Do not add a fourth answer engine. Answer packs may enrich EvidencePlan only after:

- Reviewed source.
- Golden pass.
- Row authority ready.
- No raw LLM prose loaded as answer authority.

### WS8 Healthy-Contradiction vs Bug Tests

Status: pending.

Add tests distinguishing:

- Healthy contradiction: catalogue says exact row, row-authority says weak, route remains canonical; CP-off keeps compatibility, CP-on applies row-authority narrowing.
- Real bug: exact row bypasses missing bindings, live-result language appears without evidence, or MCP step disappears.

## Immediate Acceptance For This PR Slice

- Plan status no longer overclaims phase completion.
- Row authority is visible in route adjudication without creating a second route architecture.
- Flag-gated row-authority enforcement prevents weak exact rows from using `exact_105_registry` authority.
- MCP-off live-evidence ResourcePlan keeps the same MCP step and marks it blocked.
- SlotConstraintProjection exists as an SPL handoff read model while reusing existing binding authority.
- T2 SPL-native tests and ResourcePlan/adjudication focused tests pass.
