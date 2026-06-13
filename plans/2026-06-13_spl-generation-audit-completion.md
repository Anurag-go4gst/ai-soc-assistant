# SPL Generation Audit — Completion Review

**Status:** Conditionally complete (2026-06-13)  
**Date closed:** 2026-06-13 (audit phases A–D, G; E/F/H2 gaps closed in follow-up)  
**Canonical audit doc:** [`docs/architecture/spl_generation_audit.md`](../docs/architecture/spl_generation_audit.md)  
**Source plan:** `/root/.cursor/plans/spl_generation_audit_30f60bc7.plan.md`  
**Lab-tier / source-resolve plan:** `/root/.cursor/plans/llm_lab-tier_spl_exposure_0c7c3c33.plan.md`  
**Closing commit:** `8f44eee` — *Complete SPL audit phases G/E/F/H for lab exposure and source resolve*

---

## Executive summary

The relevance-first SPL audit plan is **conditionally complete**. Core mandate — correct SPL for asked questions, LLM-primary on non-template paths, catalogue coverage, governance-safe candidate-only output — is implemented. Remaining gaps (Phase E live wiring, Phase F enforceable audit, H2 discovery flag gating) were identified in completion review and addressed in follow-up work on this branch.

| Metric (final) | Result |
|----------------|--------|
| 105 spl-expected (deterministic lane) | **100/102** |
| 105 + `--llm-mock` | **102/102** (requires mock LLM path; not default deterministic) |
| Catalogue spl-expected | **31/31 (100%)** |
| Governance regression | **PASS** when full regression completes (harness 6/6) |
| `eval_105_path_honoring.py --check` | **PASS** |
| Template audit (`llm_template_audit.py`) | **10/10 pass** after template-policy validation + enforceable exit code |

**Coverage note:** Headline **100/102** is the default deterministic lane. **102/102** depends on `--llm-mock` for the two multi-signal cases — treat full 105 as complete only when those cases pass through the configured live/mock LLM path you intend to ship.

---

## Phase completion matrix

| Phase | Goal | Status | Evidence |
|-------|------|--------|----------|
| **A** | Audit + relevance baseline | ✅ Done | `spl_generation_audit.md`, `scripts/eval_spl_relevance.py` |
| **B** | Routing correctness (deterministic) | ✅ Done | DNS/SMB/PowerShell fixes; 97/102 deterministic |
| **C** | LLM-primary failover + R5 gate | ✅ Done | `spl_relevance_check.py`, `ai_soc_llm_spl_fallback_enabled` |
| **C.2** | Analyst UX (B15/B04/R1) | ✅ Done | Single SPL surface, ambiguous-family context |
| **D** | Catalogue coverage (no fabrication) | ✅ Done | `CATALOGUE_USE_CASE_FAMILY`; 22/31 |
| **D.2** | Close remaining nine | ✅ Done | 10 lab families; 31/31 catalogue |
| **G** | Lab-tier LLM SPL exposure | ✅ Done | `validate_spl_lab_candidate`, exposure split in pipeline |
| **E** | Post-validation simplifier | ✅ Done (live wired) | `merge_post_validation_optimization()` in provider + template paths |
| **F** | Offline template audit | ✅ Done | `scripts/llm_template_audit.py`; template-policy validation; exit ≠ 0 on review |
| **H** | Placeholder → `normalized_spl` | ✅ Done (H2 gated) | `graph_node_spl_source_resolve`; `MCP_DISCOVERY_ENABLED` default true |

---

## Completion review fixes (2026-06-13)

| Finding | Fix |
|---------|-----|
| P1 Phase E not live | `merge_post_validation_optimization()` replaces `candidate_spl` / `normalized_spl` when revalidation passes |
| P1 H2 bypasses execution flags | `MCP_DISCOVERY_ENABLED` gates auto-resolve; mock discovery/search gated; Settings discover uses explicit `discovery_allowed` |
| P1 Phase F template validation | Audit uses per-template `validation_rules` policy; verbosity advisory-only |
| P2 Audit always exit 0 | `main()` returns 1 when `review_required > 0` |
| P2 “Done” overstates 105 | Status → conditionally complete; metrics table clarified |

---

## What remains outside this plan (explicit deferrals)

These are **not** SPL-audit failures — downstream COE / live MCP only:

1. **Live Splunk MCP search (query→answer B2 live)** — mock path complete (`ae88760`); `SplunkMcpConnector.call_tool` HTTP transport + `schema_confirmed=true` still COE.
2. **Governed template promotion** — 5 planned templates stay blocked (`blocked_until_scd_fields_exist`); COE source profile in Settings can unblock.
3. **Orchestration Phase 4** — optional auto-execution of discovery tools in chat (`MCP_DISCOVERY_ENABLED` for auto-resolve is separate from Settings explicit discover). See query→answer plan **Appendix A §O4**.

### Source resolution — updated

| Tier | Module | Status |
|------|--------|--------|
| H0 | Config + **Settings UI** persisted map | ✅ |
| H1 | RAG bridge | ✅ |
| H2 | `run_mcp_source_discovery()` at resolve time | ✅ gated (`MCP_DISCOVERY_ENABLED=true`); MCP wins on conflict when enabled |
| H3 | HIL + session/chat slots | ✅ |
| H4 | `validate_spl` → MCP gate | ✅ when resolved |
| B4 | Analyst confirm/update SPL before execute | ✅ `spl_execution_confirmation` |

---

## Architecture delivered

### Live `/chat` SPL graph (non–rag-only path)

```text
workflow_spl → [rag_early] → spl_source_resolve → execution → context_finalize
```

### LLM failover contract (flag: `AI_SOC_LLM_SPL_FALLBACK_ENABLED`)

- Relevance gate (R5) + `validate_spl` / `validate_spl_lab_candidate`
- Lab-tier: analyst sees `candidate_spl`; `approved=false`, `normalized_spl=null`
- Execution-validated: full `validate_spl` pass → `normalized_spl` set
- Retry: `AI_SOC_LLM_SPL_FAILOVER_RETRY_ENABLED=false` (default, one call per turn)

### Source resolution ladder (Phase H)

| Tier | Module | Executes? |
|------|--------|-----------|
| H0 | `source_profile_resolver.py` + `AI_SOC_SOURCE_PROFILE_MAP` | Config only |
| H1 | `rag_source_profile_bridge.py` | RAG retrieval yes; substitution deterministic |
| H2 | `run_mcp_source_discovery()` | Gated; Settings explicit discover always allowed |
| H3 | `spl_source_profile_clarification` HIL + session `source_profile_slots` | Analyst input |
| H4 | `validate_spl` → `normalized_spl` | Deterministic |

### Phase E simplifier (live)

```text
validate_spl(candidate) → optimize_spl (simplifier) → revalidate
  → if revalidation_approved: candidate_spl + normalized_spl = simplified SPL
  → else: retain original validation output
```

---

## Verification commands

```bash
./scripts/run_stage3_governance_regression.sh
cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_spl_optimization_stage3jk0.py app/tests/test_mock_mcp_discovery_gating.py -q
PYTHONPATH=backend:. python3 scripts/llm_template_audit.py --write-report
PYTHONPATH=backend:. python3 scripts/eval_105_path_honoring.py --check
```

Expected:

- Governance regression: PASS (includes template audit section).
- Phase E/H2 unit tests: green.
- Template audit: `review_required: 0`, exit 0.
