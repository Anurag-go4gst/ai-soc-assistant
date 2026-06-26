# SPL Query Fidelity — Completion Review

Date: 2026-06-25  
Status: **Done after review corrections** — Parts 1–12 implemented; review bugs corrected below.

## Objective

Preserve explicit user constraints through query understanding → slot validation → template/draft rendering without weakening `FinalEvidenceGate` governance.

## Parts delivered

| Part | Status | Notes |
|------|--------|-------|
| 1 — `LLMIntentAdvisory.entity_slots_candidate` | Done | `app/chat/contracts/llm_intent_advisory.py` |
| 2 — Intent prompt slot extraction | Done | `app/llm/sidecar_clients.py` |
| 3 — LLM slots wired with precedence | Done | `user_explicit` → deterministic → `llm` → `source_profile` → template defaults |
| 4 — Validator-gated LLM slots | Done | Rejected/conflict slots in `unbound_constraints` |
| 5 — `UserConstraintBindings` | Done | `app/spl/user_constraint_bindings.py` |
| 6 — Table-driven `customize_template_spl` | Done | `app/spl/template_slot_bindings.py` |
| 7 — Template compatibility + skeleton fallback | Done | `app/spl/template_compatibility.py` |
| 8 — Partial-bind honesty (analyst UI) | Done | `AnalystResponseCard` “Unresolved source bindings” from draft and governed-candidate `spl_unbound_constraints` |
| 9 — Source-profile binding | Done (draft path) | `build_draft_preview()` uses persisted `/settings/source-profiles` only; review-only substitution |
| 10 — FinalEvidenceGate preserved | Done | No gate weakening; source-profile bindings are not telemetry |
| 11 — Regression tests A–H | Done | `app/tests/test_spl_query_fidelity.py` |
| 12 — Acceptance criteria | Done | See verification below |

## Test I (environment fan-out)

**Partial** — multi-family VPN/PAM/jump-host decomposition is not a single draft family. Covered at routing/draft level by `test_substation_remote_access_enumeration_routes_to_esp_it_to_ot_draft` in `test_105_path_honoring.py`. Full environment fan-out remains follow-up if COE requires separate VPN/PAM session families.

## Intentional deferrals

1. **Dual validator modules** — `app/spl/spl_slot_binding_validator.py` vs `app/safeguards/spl_slot_binding_validator.py` not merged (broader control-plane consolidation).
2. **MCP discovery at bind time** — source-profile store supports MCP merge; draft auto-fill uses persisted COE store only.

## Review corrections (2026-06-25)

1. **Schema drop bug fixed** — `SplDraftPreviewEnvelope` now declares `unbound_constraints` and `source_profile_bindings`; `CandidateSplEnvelope` now declares `user_constraint_bindings` and `spl_binding_trace`. These fields were previously present in raw dicts but could be silently dropped by typed response serialization.
2. **Governed-template visibility fixed** — `build_analyst_response_for_live()` now projects draft and governed candidate binding issues into `analyst_response.spl_unbound_constraints`, and the frontend renders the same “Unresolved source bindings” section for governed SPL and draft SPL surfaces.
3. **Verification wording corrected** — prior close notes claimed full backend/governance green before it was reproducible. The final review reran the governance gate successfully after fixing a stale EC fixture-policy test.
4. **EC fixture-policy test corrected** — `run_demo_scenario()` intentionally prefers curated legacy fixtures and keeps capture artifacts as fallback. `test_ec_overhaul.py` now asserts that serving policy while still directly testing capture-artifact restamping/posture through `_serve_capture_artifact()`.

## Live-path test isolation (2026-06-25)

`test_q010_smb_top_talkers_keeps_clarification_contract` monkeypatches empty source profile to preserve the frozen clarification contract. New companion test `test_q010_smb_top_talkers_resolves_network_bindings_when_source_profile_populated` documents populated-store behavior (`spl_revision`, not `spl_source_profile_clarification`).

## Verification (2026-06-25 final review)

- Targeted SPL fidelity/schema regression: **17 passed**
- Focused SPL/source-profile/display/live-data bundle: **125 passed**
- EC overhaul regression after fixture-policy correction: **22 passed**
- Frontend build: **green**
- Governance regression: **PASS**
  - Backend pytest: **2982 passed**, 1 skipped, 6 xfailed
  - LangGraph dual-run parity: 120/120
  - SOC clean-answer eval: 120/120
  - SPL template audit: 16/16
  - Cisco power-grid catalogue gate: PASS=50 REVIEW=0 FAIL=0 CRITICAL=0

```bash
cd backend
PYTHONPATH=../backend:.. python3 -m pytest \
  app/tests/test_spl_query_fidelity.py \
  app/tests/test_spl_draft_preview.py \
  app/tests/test_spl_source_resolve.py \
  app/tests/test_spl_template_live_path.py \
  app/tests/test_phase13d_b_firewall_draft_display.py \
  -q

cd frontend && npm run build
./scripts/run_stage3_governance_regression.sh
```

## Key files

- `backend/app/spl/user_constraint_bindings.py`
- `backend/app/spl/template_slot_bindings.py`
- `backend/app/spl/template_compatibility.py`
- `backend/app/spl/draft_preview.py`
- `backend/app/chat/pipeline.py`
- `frontend/src/components/AnalystResponseCard.tsx`

## Test isolation fixes (close)

- `test_q010_smb_top_talkers_keeps_clarification_contract` — empty source profile monkeypatch
- `test_q010_smb_top_talkers_resolves_network_bindings_when_source_profile_populated` — populated-store companion
- `test_substation_live_data_prefers_family_draft_over_llm_failover` — accepts resolved `firewall_*` bindings via canonical slot mapping
