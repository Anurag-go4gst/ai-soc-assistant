# SPL Generation Audit — Completion Review

**Status:** Done  
**Date closed:** 2026-06-13  
**Canonical audit doc:** [`docs/architecture/spl_generation_audit.md`](../docs/architecture/spl_generation_audit.md)  
**Source plan:** `/root/.cursor/plans/spl_generation_audit_30f60bc7.plan.md`  
**Lab-tier / source-resolve plan:** `/root/.cursor/plans/llm_lab-tier_spl_exposure_0c7c3c33.plan.md`  
**Closing commit:** `8f44eee` — *Complete SPL audit phases G/E/F/H for lab exposure and source resolve*

---

## Executive summary

The relevance-first SPL audit plan is **complete**. The headline mandate — correct SPL for asked questions, LLM-primary on non-template paths, coverage for 105 + catalogue, governance-safe candidate-only output — is implemented and regression-green.

| Metric (final) | Result |
|----------------|--------|
| 105 spl-expected (deterministic lane) | **100/102** |
| 105 + `--llm-mock` | **102/102** |
| Catalogue spl-expected | **31/31 (100%)** |
| Governance regression | **PASS** (harness 6/6) |
| `eval_105_path_honoring.py --check` | **PASS** |

Brevity (Phase E) and offline template QA (Phase F) shipped. Lab-tier LLM exposure (Phase G) and placeholder resolution (Phase H) shipped in the same closing commit.

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
| **E** | Post-validation simplifier | ✅ Done | `spl_simplifier.py` → `optimize_spl()` |
| **F** | Offline template audit | ✅ Done | `scripts/llm_template_audit.py`; 8/10 pass |
| **H** | Placeholder → `normalized_spl` | ✅ Done (H2 scaffold) | `graph_node_spl_source_resolve`, H0–H1, H3–H4 |

---

## What remains outside this plan (explicit deferrals)

These are **not** SPL-audit failures — they belong to downstream COE / MCP plans:

1. **H2 MCP discovery execution** — scaffold only (`try_mcp_source_discovery`); real `splunk_get_indexes` execution waits on COE + [`2026-06-13_mcp-execution-orchestration-plan.md`](2026-06-13_mcp-execution-orchestration-plan.md) §6.
2. **Governed template promotion** — 5 planned templates stay blocked (`blocked_until_scd_fields_exist`); COE source profile required.
3. **Phase F template fixes** — 2/10 active templates flagged `review` in `llm_template_audit_report.md`; fixes land deterministically in `templates.json` when COE reviews.
4. **Real MCP search (query→answer B2)** — `normalized_spl` can now be produced after H resolution; gate still sends `{"query": normalized_spl}` only until B2 ships.

---

## Architecture delivered

### Live `/chat` SPL graph (non–rag-only path)

```text
workflow_spl → [rag_early] → spl_source_resolve → execution → context_finalize
```

### LLM failover contract (flag: `AI_SOC_LLM_SPL_FALLOVER_ENABLED`)

- Relevance gate (R5) + `validate_spl` / `validate_spl_lab_candidate`
- Lab-tier: analyst sees `candidate_spl`; `approved=false`, `normalized_spl=null`
- Execution-validated: full `validate_spl` pass → `normalized_spl` set
- Retry: `AI_SOC_LLM_SPL_FAILOVER_RETRY_ENABLED=false` (default, one call per turn)

### Source resolution ladder (Phase H)

| Tier | Module | Executes? |
|------|--------|-----------|
| H0 | `source_profile_resolver.py` + `AI_SOC_SOURCE_PROFILE_MAP` | Config only |
| H1 | `rag_source_profile_bridge.py` | RAG retrieval yes; substitution deterministic |
| H2 | `try_mcp_source_discovery()` | Mock scaffold only until COE |
| H3 | `spl_source_profile_clarification` HIL + session `source_profile_slots` | Analyst input |
| H4 | `validate_spl` → feeds MCP gate | When fully resolved |

---

## Verification commands (regression pins)

```bash
./scripts/run_stage3_governance_regression.sh
PYTHONPATH=backend:. python3 scripts/eval_spl_relevance.py --check
PYTHONPATH=backend:. python3 scripts/llm_template_audit.py --write-report
cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_spl_simplifier.py app/tests/test_spl_source_resolve.py app/tests/test_llm_spl_fallback.py -q
cd frontend && npm run build
```

---

## Commit trail (phases A→H)

| Commit | Phase |
|--------|-------|
| `911eed6` | B — routing relevance |
| `ad29958` | C — LLM failover + R5 |
| `35b42b0` | C.2 — analyst UX |
| `1b86da2` | D — catalogue reuse |
| `22cbbc3` | D.2 — nine lab families |
| `8f44eee` | G + E + F + H |

---

## Next plan for agents

Proceed to **query→answer Phase B** (real MCP search adapter) and **MCP orchestration plan** — SPL audit prerequisites are satisfied. Do not re-open SPL audit unless COE changes source-profile or template promotion scope.
