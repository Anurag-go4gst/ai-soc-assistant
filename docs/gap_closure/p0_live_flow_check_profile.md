# P0-9 — Live Flow-Check Profile (`AI_SOC_FLOW_CHECK_MODE=stub_evidence`)

**Status:** Proposed profile (P0). Composes **existing** env vars documented in [`config.py`](../../backend/app/config.py) and [`.env.example`](../../.env.example). The setting `AI_SOC_FLOW_CHECK_MODE` is a **readiness label** in config (validated, default empty) — it does **not** auto-flip other variables until a later stage wires orchestration.

## Goal

Validate end-to-end **control flow** (routing, registry hints, LLM advisory sidecars, SPL validation, MCP/RAG evidence envelopes, sufficiency, trace/lineage) **without** real Splunk MCP or production SOC-KB corpus.

```text
User query
  → normalize / understand_query
  → registry/coverage match or OOD path (shadow/advisory)
  → primary_operation decision (allowlist-scoped when enabled)
  → route-plan validation (shadow)
  → precondition_eval (shadow/live per flags)
  → SPL validation where applicable
  → MCP/RAG stub evidence envelope
  → MITRE permitted/fallback classification
  → sufficiency classification
  → deterministic or lab guarded answer (synthesis off by default)
  → full trace/lineage + demo labels (P0-10)
```

## Proposed profile flag

```text
AI_SOC_FLOW_CHECK_MODE=stub_evidence
```

| Value | Meaning |
|-------|---------|
| *(empty)* | Unset — operator composes env manually |
| `stub_evidence` | Documented COE system-check / deck demo profile below |

## Canonical env mapping (existing vars)

| Intent | Config field / env var | System-check value |
|--------|------------------------|-------------------|
| Profile label | `AI_SOC_FLOW_CHECK_MODE` | `stub_evidence` |
| Authority compare (shadow) | `ROUTE_AUTHORITY_COMPARE_ENABLED` | `true` (default) |
| Operation authority (allowlist only) | `ROUTE_AUTHORITY_OPERATION_AUTHORITATIVE_ENABLED` + `ROUTE_AUTHORITY_OPERATION_COVERAGE_ALLOWLIST` | `true` + e.g. `cov.q046` |
| No real Splunk MCP | `MCP_GLOBAL_EXECUTION_ENABLED` | `false` for strict stub, or see mock row |
| Bounded mock MCP rows | `MCP_GLOBAL_EXECUTION_ENABLED` + `MCP_SERVER_MOCK_EXECUTION_ENABLED` | **`true` + `true`** (both required) |
| No production RAG | `RAG_MODE` | `mock` |
| OOD route-plan sidecar | `ROUTING_MODE` | `llm_shadow_only` or `llm_assisted_semantic` |
| Route-plan providers | `AI_SOC_LLM_ROUTE_PLAN_PROVIDER` / `_MODEL` | per LLM registry (no single `AI_SOC_LLM_ROUTE_PLAN_ENABLED`) |
| Lab-primary route-plan | `ROUTING_MODE=llm_primary_lab` + `ROUTING_LAB_LLM_PRIMARY_ENABLED` | non-production only |
| Semantic intent sidecar (P2-12) | `AI_SOC_LLM_INTENT_PROVIDER` + `_MODEL` | role `intent_shadow_classifier` |
| No production synthesis | `AI_SOC_LLM_FINAL_SYNTHESIS_ENABLED` | `false` |
| Answer Guard | `AI_SOC_LLM_ANSWER_GUARD_ENABLED` | `false` (true only with explicit lab synthesis) |
| MITRE candidate mapper (P5-10) | `AI_SOC_LLM_MITRE_CANDIDATE_MAPPING_ENABLED` | **proposed** — not in repo yet |

### Example composed demo (`.env.example` comment block)

```text
AI_SOC_FLOW_CHECK_MODE=stub_evidence
ROUTE_AUTHORITY_COMPARE_ENABLED=true
ROUTE_AUTHORITY_OPERATION_AUTHORITATIVE_ENABLED=true
ROUTE_AUTHORITY_OPERATION_COVERAGE_ALLOWLIST=cov.q046
ROUTING_MODE=llm_assisted_semantic
RAG_MODE=mock
MCP_GLOBAL_EXECUTION_ENABLED=true
MCP_SERVER_MOCK_EXECUTION_ENABLED=true
AI_SOC_LLM_FINAL_SYNTHESIS_ENABLED=false
AI_SOC_LLM_ANSWER_GUARD_ENABLED=false
```

## Allowed vs not allowed

**Allowed:** registry/coverage authority for allowlisted paths; LLM route-plan and semantic intent **advisory**; mock/stub MCP and fixture RAG envelopes; MITRE candidate/review statuses; full trace; deterministic status answers.

**Not allowed:** real Splunk MCP adapter execution; direct RAG→LLM; `candidate_spl` execution; novel OOD live MCP; free-form LLM MITRE invention as `supported`; silent confident answers without `evidence_origin` labels.

## Evidence origin labels (pair with P0-10)

When synthesis is off, answers must state provenance:

```text
evidence_origin = stub_mcp | stub_rag | registry_only | coe_synthetic_fixture | none
answer_readiness = system_check_only | production | insufficient | blocked
```

## Deprecated shorthand (do not implement as literal env names)

`LIVE_FLOW_CHECK_ENABLED`, `SOC_KB_PRODUCTION_RAG_ENABLED`, `AI_SOC_LLM_ROUTE_PLAN_ENABLED`, `AI_SOC_LLM_SEMANTIC_INTENT_ENABLED` — use the table above.

## Cross-references

- Deck Protocol §2: [p0_deck_zero_ambiguity_pack.md](p0_deck_zero_ambiguity_pack.md)
- Trace labels: [p0_trace_demo_labels.md](p0_trace_demo_labels.md)
- Review Appendix B in gap roadmap plan
