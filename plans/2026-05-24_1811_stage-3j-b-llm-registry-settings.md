# Stage 3J-B: LLM Registry, Environment Settings, and LLM Settings UI

Base: Stage 3J (`a0ba56f`).

## Goal

Add a safe LLM configuration/status/UI layer ahead of Stage 3K (evidence-based
synthesis). No real LLM is called; no synthesis, no answer guard.

## Decision (per advisor)

Do NOT create a parallel `llm_registry` status block / second tab. The existing
`llm` status block + `LlmSettingsPanel` (already titled "LLM Registry") is the
surface. Extend it additively with a self-contained `llm.governance` object
sourced purely from new `AI_SOC_LLM_*` settings. `ai_soc_llm_mode` is canonical:
mode `disabled` forces the governed layer off.

Airgap + cloud conflict is resolved safely (not raised):
`cloud_allowed = allow_cloud and not airgap_enforced`, with a warning surfaced.

## Touch list

- `backend/app/config.py` — `AI_SOC_LLM_*` fields + mode enum validation.
- `backend/app/llm/registry_settings.py` (new) — `build_llm_governance_status()`,
  booleans only, never secrets.
- `backend/app/api/routes_settings.py` — add `governance` into the `llm` block.
- `.env.example` — `AI_SOC_LLM_*` keys, empty/placeholder; inert flags documented.
- `frontend/src/types/api.ts` — `LlmGovernanceStatus` + optional `llm.governance`.
- `frontend/src/components/settings/LlmSettingsPanel.tsx` — governance section:
  three badges (final synthesis / answer guard / context sufficiency), safety
  controls, provider readiness, governed role mapping.
- `frontend/src/mocks/settings.ts` — mock `governance` so the panel renders offline.
- `backend/app/tests/test_llm_settings_stage3jb.py` (new).

## Non-goals

No final synthesis, no answer guard, no real LLM call, no answer prompt
templates, no new providers beyond config/status, no RAG/MCP changes.

## Notes

- No JS test runner exists (no vitest/jest, no `test` script). Frontend "tests"
  satisfied by `npm run build` + mock rendering; not adding a runner (out of scope).
- `AI_SOC_LLM_FINAL_SYNTHESIS_ENABLED` / `_ANSWER_GUARD_ENABLED` are inert flags;
  flipping them runs no code in this stage.

## Verify

- `cd backend && python3 -m pytest` (176 pass)
- `cd frontend && npm run build`
- harness 6/6 default + `TELEMETRY_MODE=none`
- `git diff --check`
