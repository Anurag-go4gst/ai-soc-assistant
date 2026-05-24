# Stage 3J: Context Sufficiency Gate

Base: HEAD `80d8e35`.

## Goal

Replace the coarse `check_context_sufficiency` pass/partial/fail/requires_human_review output
with a typed `ContextSufficiencyResult` that classifies the current
`SourceEvidence` + `StructuredContext` package into one of seven answer modes,
without enabling synthesis.

## Constraints (from stage prompt + CLAUDE.md)

- Do not modify RAG retrieval behavior unless a test fails.
- Do not add final synthesis. `synthesis_allowed` stays `False` everywhere.
- Do not add an answer guard or new provider integrations.
- Synthesis readiness is a new, separate signal — the future synthesis stage
  ANDs it with its own enablement; this stage never flips `synthesis_allowed`.

## Seven modes

- `full_answer`
- `partial_answer`
- `analyst_review_required`
- `spl_review_only`
- `knowledge_only_answer`
- `blocked_by_policy`
- `insufficient_evidence`

## Design

`ContextSufficiencyResult` = `@dataclass` in `app/evidence/context_sufficiency.py`:
`mode`, `synthesis_readiness`, `reasons`, `missing_evidence`, `human_review`.
`.to_envelope()` returns the dict the route already consumes, with `status=mode`,
`synthesis_allowed=False`, plus new `synthesis_readiness`.

`check_context_sufficiency(...)` keeps its signature, returns `.to_envelope()`.

### Priority cascade (first match wins)

1. sensitive leak on any collected evidence -> `blocked_by_policy`
2. `context_quality == "blocked"` (execution blocked by policy/HIL) -> `blocked_by_policy`
3. no collected evidence -> `insufficient_evidence`
4. any structured fact with empty `source_refs` -> `insufficient_evidence`
5. `mitre_candidates` non-empty AND `mitre_grounding_refs` empty -> `analyst_review_required`
6. asset-criticality claim present AND `environment_grounding_refs` empty -> `analyst_review_required`
7. any `rag` evidence `collection_status == "ambiguous"` -> `analyst_review_required`
8. only SAIA/candidate-SPL collected, no executed `splunk_mcp` -> `spl_review_only`
9. only `rag` collected (no execution) -> `knowledge_only_answer`
10. execution collected + `missing_evidence` non-empty -> `partial_answer`
11. otherwise -> `full_answer`

`synthesis_readiness=True` only for `full_answer`, `partial_answer`, `knowledge_only_answer`.

`human_review` attached for `analyst_review_required` and `blocked_by_policy`
(distinct review_type/reason).

### Rule coverage mapping

- SAIA advisory only / candidate SPL alone -> rule 8 (`spl_review_only`, readiness False).
- RAG supports SOP/knowledge -> rule 9 (`knowledge_only_answer`).
- Facts without source_refs -> rule 4 (`insufficient_evidence`).
- MITRE conclusions need grounding -> rule 5.
- Asset criticality needs asset evidence -> rule 6. Detected by scanning
  `structured_facts` statements for criticality keywords. Known partial hook:
  the structurer does not yet emit an explicit criticality field, so the rule
  fires only on keyworded facts — acceptable for this stage.
- Sensitive leak -> rule 1.

## Touch list

- `backend/app/evidence/context_sufficiency.py` — rewrite with dataclass + cascade.
- `backend/app/schemas/responses.py` — add `synthesis_readiness: bool = False` to envelope.
- `backend/app/api/routes_chat.py` — record `synthesis_readiness` in telemetry; keep flow.
- `frontend/src/types/api.ts` — widen status union, add `synthesis_readiness`.
- `frontend/src/components/Stage3DTracePanel.tsx` — badge variant for new modes.
- `backend/app/tests/test_evidence_context.py` — update 2 old-vocab asserts.
- New `backend/app/tests/test_context_sufficiency_stage3j.py` — one test per mode + rule.

## Verify

- `cd backend && python3 -m pytest`
- `cd frontend && npm run build`
- harness 6/6 (default + `TELEMETRY_MODE=none`)
