# P0-9 — Live Flow-Check Profile (`AI_SOC_FLOW_CHECK_MODE=stub_evidence`)

**Status:** Governed full-throttle profile available in [`.env.live-full-throttle.example`](../../.env.live-full-throttle.example). Composes **existing** env vars documented in [`config.py`](../../backend/app/config.py), [`.env.example`](../../.env.example), and the current P1/P2/P5 control layer. The setting `AI_SOC_FLOW_CHECK_MODE` is a **readiness label** in config (validated, default empty) — it does **not** auto-flip other variables until a later stage wires orchestration.

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
| LangGraph parity path | `LANGGRAPH_ORCHESTRATION_ENABLED` | `true` |
| Operation authority (allowlist only) | `ROUTE_AUTHORITY_OPERATION_AUTHORITATIVE_ENABLED` + `ROUTE_AUTHORITY_OPERATION_COVERAGE_ALLOWLIST` | `true` + `cov.q046.excessive_failed_logins_sample` |
| 4-intent authority deprecation | `LEGACY_SELECTED_SKILL_AUTHORITY_ENABLED` | `false` |
| Open operations / supporters / audit | `ROUTE_PLAN_OPEN_OPERATIONS_ENABLED`, `ROUTE_PLAN_SUPPORTERS_RUNTIME_ENABLED`, `OPERATION_AUDIT_PERSISTENCE_ENABLED` | `true`, `true`, `true` |
| No real Splunk MCP | `MCP_GLOBAL_EXECUTION_ENABLED` | `false` for strict stub, or see mock row |
| Bounded mock MCP rows | `MCP_GLOBAL_EXECUTION_ENABLED` + `MCP_SERVER_MOCK_EXECUTION_ENABLED` | **`true` + `true`** (both required) |
| Governed fixture RAG | `RAG_MODE` + `SOC_KB_RETRIEVAL_ENABLED` | `mock` + `true` |
| OOD route-plan sidecar | `ROUTING_MODE` | `llm_shadow_only` or `llm_assisted_semantic` |
| Route-plan providers | `AI_SOC_LLM_ROUTE_PLAN_PROVIDER` / `_MODEL` | per LLM registry (no single `AI_SOC_LLM_ROUTE_PLAN_ENABLED`) |
| Lab-primary route-plan | `ROUTING_MODE=llm_primary_lab` + `ROUTING_LAB_LLM_PRIMARY_ENABLED` | non-production only |
| Semantic intent sidecar (P2-12) | `AI_SOC_LLM_INTENT_PROVIDER` + `_MODEL` | role `intent_shadow_classifier` |
| No production synthesis | `AI_SOC_LLM_FINAL_SYNTHESIS_ENABLED` | `false` |
| Answer Guard | `AI_SOC_LLM_ANSWER_GUARD_ENABLED` | `false` (true only with explicit lab synthesis) |
| MITRE candidate mapper (P5-10) | `AI_SOC_LLM_MITRE_CANDIDATE_MAPPING_ENABLED` + provider/model | `true` + `foundation_sec_instruct` / `Foundation-sec-8B-Instruct` |

### Example composed demo (`.env.example` comment block)

```text
AI_SOC_FLOW_CHECK_MODE=stub_evidence
AI_SOC_LLM_MODE=mock
LANGGRAPH_ORCHESTRATION_ENABLED=true
ROUTE_AUTHORITY_COMPARE_ENABLED=true
ROUTE_AUTHORITY_OPERATION_AUTHORITATIVE_ENABLED=true
ROUTE_AUTHORITY_OPERATION_COVERAGE_ALLOWLIST=cov.q046.excessive_failed_logins_sample
LEGACY_SELECTED_SKILL_AUTHORITY_ENABLED=false
ROUTE_PLAN_OPEN_OPERATIONS_ENABLED=true
ROUTE_PLAN_SUPPORTERS_RUNTIME_ENABLED=true
OPERATION_AUDIT_PERSISTENCE_ENABLED=true
ROUTING_MODE=llm_assisted_semantic
AI_SOC_LLM_ROUTE_PLAN_PROVIDER=foundation_sec_instruct
AI_SOC_LLM_ROUTE_PLAN_MODEL=Foundation-sec-8B-Instruct
RAG_MODE=mock
SOC_KB_RETRIEVAL_ENABLED=true
MCP_GLOBAL_EXECUTION_ENABLED=true
MCP_SERVER_MOCK_EXECUTION_ENABLED=true
AI_SOC_LLM_MITRE_CANDIDATE_MAPPING_ENABLED=true
AI_SOC_LLM_MITRE_CANDIDATE_PROVIDER=foundation_sec_instruct
AI_SOC_LLM_MITRE_CANDIDATE_MODEL=Foundation-sec-8B-Instruct
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
