# P0-10 — Trace and Demo Label Specification

**Status:** Specification (P0). Fields are **required on demo/system-check responses** in trace or debug UI. Live `/chat` may adopt incrementally; Experience Center already exposes some labels (`evidence_origin`, `demo_mode`).

## Why these labels exist

Reviewers must not confuse:

| Confusable pair | Label distinction |
|-----------------|-------------------|
| Flow visible vs production-ready | `flow_mode`, `answer_readiness` |
| 105 mapped vs 105 live-routable | `route_authority`, `registry_match_status` |
| LLM proposed vs LLM decided | `*_authority: false` |
| `selected_skill` visible vs authoritative | `legacy_intent_authority: false` |

## Required labels (every demo / system-check response)

```text
flow_mode: production | system_check | lab
route_authority: registry_allowlist | shadow_only | deterministic_fallback | requires_hil
legacy_intent_authority: false          # target after P2-9 on live; false in deck today
llm_semantic_intent_authority: false
llm_route_plan_authority: false
mcp_execution_mode: disabled | mock | live
rag_mode: disabled | stub | approved_production
mitre_mode: supported | candidate | needs_review | not_mapped | not_applicable
answer_mode: deterministic_status | lab_guarded_synthesis | production_guarded_synthesis
evidence_origin: live_mcp | mock_mcp | live_rag | stub_rag | registry_only | coe_synthetic_fixture | none
```

### Extended trace fields (new-question / registry paths — target)

Attach as trace or `route_plan_shadow` extensions; implement in P2+.

```text
registry_match_status: exact | nearest | weak | none
nearest_registry_hint: string | null
known_compatible: true | false
operation_provenance: registry | llm_proposed_known_compatible | llm_proposed_novel
authority_decision: allowed | shadow_only | requires_hil | blocked
mitre_status: supported | candidate | needs_review | not_mapped | not_applicable
answer_readiness: production | system_check_only | insufficient | blocked
```

### Semantic intent mapper (P2-12 — advisory only)

```text
llm_semantic_intent_called: true | false
llm_path_type_candidate: known_registry | known_compatible_ood | novel_ood | knowledge_only | clarification
selected_path_type: ...
selected_path_authority: deterministic_registry | deterministic_clarification | llm_advisory_normalized | shadow_only
semantic_intent_disagreements: []
```

### MITRE candidate mapper (P5-10 — trace/review)

```text
mitre_mapping_source: soc_approved | taxonomy | use_case | llm_candidate | deterministic_fallback | none
llm_mitre_candidate_used: true | false
llm_mitre_parse_status: valid | repaired | failed | not_run
requires_soc_review: true | false
```

## Mapping to current API (partial today)

| Label | Today |
|-------|-------|
| `evidence_origin` | [`ChatResponse.evidence_origin`](../../backend/app/schemas/responses.py); EC `coe_synthetic_fixture` |
| `demo_mode` | EC scenarios |
| `route_authority_compare` | Shadow in `route_plan_shadow` / lineage |
| `flow_mode`, `legacy_intent_authority`, … | **Spec only** — add to trace envelope in P2/UI follow-on |

## Experience Center

EC may keep `expected_skill` (4 intents) until P2-EC rebase. When demoing, still set:

```text
legacy_intent_authority: false
flow_mode: lab
evidence_origin: coe_synthetic_fixture
```

## Consumer

- Frontend: [`Stage3DTracePanel.tsx`](../../frontend/src/components/Stage3DTracePanel.tsx) — render badges when fields present
- COE scripts: [`capture_stage3l_s3_coe_pilot_traces.py`](../../scripts/capture_stage3l_s3_coe_pilot_traces.py)

## Related

- [p0_deck_zero_ambiguity_pack.md](p0_deck_zero_ambiguity_pack.md) §0 red lines
- Gap plan Section F (new-question decision path)
