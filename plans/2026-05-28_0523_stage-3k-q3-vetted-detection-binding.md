# Stage 3K-Q3: Vetted Detection Binding Framework

## Objective

Build the governed registry and binding contract for behavioral detections (DGA, beaconing, C2, lateral movement, encoded PowerShell, scheduled task persistence, webshell, etc.). The LLM never authors behavioral detection SPL. Binding is a deterministic registry lookup, dry-run only this stage.

## Scope

- Detection registry schema and on-disk format.
- Detection families and `detection_ref` identifiers.
- Per-detection metadata: `detection_ref`, `family`, `description`, `source` (`correlation_search` / `escu` / `soc_approved_logic`), `vetting_status`, `last_reviewed`, `risk_class`, `required_inputs`, `evidence_output_contract_ref`, `requires_human_validation`.
- Binding API `bind_detection(family, parameters) -> DetectionBindingResult` returning chosen `detection_ref` plus reasons, or `unbound` with reason.
- Route plan integration: when route plan declares behavioral detection need (`evidence_needs.detection_required`), preflight binds; missing or unvetted → `RouteStatus.CANNOT_ROUTE_MISSING_DETECTION`.
- LLM-route-suggestion governance: any LLM-proposed `detection_ref` is rejected if it is not in the registry; LLM may only suggest a family, never an identifier.

## Non-Goals

- No new detection SPL authored by LLM.
- No execution of detection SPL. No MCP call. No execution gate change.
- No bypass of Q1A validator if a detection later gets a candidate SPL.
- No live LLM synthesis. No Answer Guard.
- No remediation / write actions.
- No silent fallback from "unvetted" to "vetted".
- No commitment that all listed detection families ship with content in this stage — registry can start with a small seed.

## Schema (sketch)

```
{
  "detections": [
    {
      "detection_ref": "soc.dga.v1",
      "family": "dga",
      "description": "DGA-like domain entropy detection.",
      "source": "soc_approved_logic",
      "vetting_status": "approved",
      "last_reviewed": "2026-05-20",
      "risk_class": "behavioral",
      "required_inputs": ["query", "host"],
      "evidence_output_contract_ref": "ranked_entities_dga_v1",
      "requires_human_validation": true
    }
  ]
}
```

`vetting_status`: `approved | provisional | deprecated | unvetted`. Only `approved` is bindable; everything else returns `unbound`.

## Implementation Plan

1. `app/detections/detection_models.py` — Pydantic models.
2. `app/detections/detection_registry.py` — cached loader + index by family.
3. `app/detections/detection_binder.py` — `bind_detection(family, params)` returns `DetectionBindingResult` (`detection_ref`, `vetting_status`, `requires_human_validation`, `reasons`).
4. Wire into route-plan preflight: lack of approved binding → `CANNOT_ROUTE_MISSING_DETECTION` with explicit reason.
5. LLM advisory hardening: route-decision normalizer drops any LLM-proposed `detection_ref` not present in the registry; records the rejection in advisory metadata (consistent with 3J-K0 governance).
6. Seed registry with 2–3 approved entries + 1 provisional + 1 unvetted for test coverage. Marked `coe_synthetic_fixture`.

## Tests

`backend/app/tests/test_detection_binding_stage3k_q3.py`

- Binding for a registered approved family returns expected `detection_ref`.
- Binding for an unknown family returns `unbound` with reason `unknown_family`.
- Provisional / deprecated / unvetted detections are not bindable.
- Route plan with detection dependency + missing approved binding → `cannot_route_missing_detection`.
- LLM-proposed `detection_ref` not in registry is dropped from route decision and recorded as advisory rejection.
- `requires_human_validation=True` is preserved in binding result.
- No detection SPL is rendered or executed in this stage.

## Verification

```bash
cd backend && python3 -m pytest
python3 -m test_harness.harness.runner --json
TELEMETRY_MODE=none python3 -m test_harness.harness.runner --json
git diff --check
```

## Detection-Family vs Detection-Ref Split (frozen)

Model / LLM advisory layer may suggest:

- `detection_family` ∈ {`dga`, `beaconing`, `c2`, `lateral_movement`, `encoded_powershell`, `scheduled_task_persistence`, `webshell`, ...}

Model / LLM must never produce:

- `detection_ref` (e.g. `some_made_up_detection_name`).

Rule:

1. LLM suggests `detection_family`.
2. Deterministic registry resolves `detection_ref` from family + parameters.
3. If no registry match, route returns `cannot_route_missing_detection`.

The adapter must strip any `detection_ref` field from LLM output before normalization.

## LLM Role and Boundary

> LLM assistance is candidate-only. Deterministic core owns validation, normalization, binding, rendering, execution eligibility, and all blocking decisions. If LLM output disagrees with deterministic validation, deterministic wins and the disagreement is recorded.

- Q3 ships **deterministic core only**. No `_llm_assist` sidecar in this stage.
- Rationale: the deterministic detection registry must exist before any LLM advisory can be safely bound. LLM-assist for detection questions enters via Q1F (`detection_family` suggestion) only after Q3 lands.
- When Q1F is active, LLM may suggest `detection_family` from the closed family enum; the Q3 binder resolves `detection_ref` deterministically. Adapter strips any `detection_ref` value from LLM output.
- LLM must never: invent detection names, edit registry entries, flip `vetting_status`, override `requires_human_validation`, or author detection SPL.

## Fixture Honesty

Q3 seed detection registry is `coe_synthetic_fixture=true`, `captured_live_run=false`, `production_execution=false`. Approved entries are not implicit endorsements of production-ready content; they are governance seeds.

## Exit Criteria

- Approved detections are bindable by family.
- Missing / unvetted detections force `cannot_route_missing_detection`.
- LLM cannot inject unregistered `detection_ref`.
- No detection SPL rendered or executed.
- Backend tests pass. Harness 6/6.
