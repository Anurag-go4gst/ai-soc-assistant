# Catalogue-known auto-execute policy (DG-5)

**COE sign-off:** 2026-07-03  
**Kill-switch:** `AI_SOC_CATALOGUE_AUTO_EXECUTE_ENABLED` (default `false`)

## Scope

In-catalogue **known** questions may **auto-execute** on live Splunk (`registry` mode) and mock when a COE-verified execution binding passes validator/allowlist gates — **without per-call analyst SPL confirmation**.

### In scope match paths

- `exact_105_question`
- `exact_105_plus_use_case_catalog`
- `use_case_catalog`
- Cisco catalogue path when `cisco_question_runtime_map` hits (same rules)

### Execution bindings (`catalogue_execution_map_v1.json`)

| `execution_mode` | MCP tool | Preconditions |
|------------------|----------|---------------|
| `governed_template` | `splunk_run_query` | `spl_validation.approved=true`, non-null `normalized_spl`, slots resolved, template source (not lab-tier LLM) |
| `saved_search` | `splunk_run_saved_search` | Name on COE allowlist, `splunk_allow_run_saved_search=true`, args validated |

Both require row fields: `coe_verified=true`, `auto_execute_eligible=true`.

## Predicate: `catalogue_auto_execute_eligible`

All must be true:

1. `AI_SOC_CATALOGUE_AUTO_EXECUTE_ENABLED=true`
2. `match_path` in catalogue set above
3. Binding resolved from map by `question_ref` and/or `use_case_id`
4. `coe_verified=true` and `auto_execute_eligible=true` on binding
5. Template path: approved `normalized_spl`, no unresolved `<slot>` placeholders
6. Saved-search path: `saved_search_name` + `saved_search_app` present; tool allowlisted
7. **Not** `llm_lineage` medium/high vigilance
8. **Not** `freeform_spl_execution_allowed` / explicit run-SPL / containment asks
9. `MCP_GLOBAL_EXECUTION_ENABLED` + per-server execution flag on
10. Deterministic tool selection succeeds

Audit trace must record: `auto_execute_reason=catalogue_known_binding`, binding id, `normalized_spl_sha256` or `saved_search_name+app`.

## Still requires HIL (unchanged)

- Out-of-registry / `guided_investigation`
- Near-miss without verified catalogue binding
- Lab-tier / LLM-produced SPL (including derived artifact medium/high)
- Catalogue row without `coe_verified` or `auto_execute_eligible`
- Post-answer action lane (mock ITSM, block IP, etc.)
- Saved search when `splunk_allow_run_saved_search=false`
- Kill-switch off (`AI_SOC_CATALOGUE_AUTO_EXECUTE_ENABLED=false`)

## DG-1 carve-out

DG-1 required per-call analyst confirmation for live registry searches. **DG-5 supersedes that only** for rows passing `catalogue_auto_execute_eligible`. All other paths keep DG-1.

## Implementation touchpoints (agent mode)

| File | Change |
|------|--------|
| `backend/app/orchestration/catalogue_execution_eligibility.py` | Pure predicate + map loader |
| `backend/app/orchestration/mcp_execution_gate.py` | Conditional `require_confirmation` |
| `backend/app/chat/pipeline.py` | Pass `match_path`, `question_ref`, `use_case_id` into gate |
| `backend/app/config.py` | `ai_soc_catalogue_auto_execute_enabled` |
| `backend/app/coverage/catalogue_execution_map_v1.json` | Pilot bindings |
| `backend/app/tests/test_catalogue_execution_eligibility.py` | Predicate + gate tests |

## Operator enablement

1. Complete Splunk MCP worksheet ([`splunk_mcp_coe_configuration_worksheet.md`](../operations/splunk_mcp_coe_configuration_worksheet.md))
2. Populate pilot rows in `catalogue_execution_map_v1.json` with `coe_verified=true`
3. Staging smoke without confirmation prompt for pilot refs
4. Set `AI_SOC_CATALOGUE_AUTO_EXECUTE_ENABLED=true` in approved env only
5. Run `./scripts/run_stage3_governance_regression.sh`
