# SOC / COE Validation Package (Phase 10)

Generated review sheets derived from the governed **SOC Capability Crosswalk** spine. **Validation and documentation only — not runtime activation.**

- The crosswalk is authoritative for `runtime_support_status`, `validation_status`, `tests_added`, `live_execution_skill`, and row membership (105 questions / 49 use-case rows / 7 GitHub skills).
- Detail columns (SPL template status, enrichment, RAG docs, intake decisions) are joined by `use_case_id` / `github_skill_id`.
- `review_decision` / `*_review_notes` are blank for SOC to complete. This generator never invents approval.
- No `/chat` runtime behavior, flags, SPL execution, MCP enablement, or MITRE/SPL/composer logic is changed by this package.

## Regenerate

```bash
python3 scripts/build_soc_validation_sheets.py
python3 scripts/build_soc_validation_sheets.py --check   # CI staleness gate
```

## Artifacts

| File | Knowledge export key | CSV |
|------|----------------------|-----|
| `use_case_validation_sheet.json` | `soc_validation_use_cases` | yes |
| `spl_template_review_sheet.json` | `soc_validation_spl_templates` | yes |
| `mitre_validation_sheet.json` | `soc_validation_mitre` | yes |
| `question_validation_sheet.json` | `soc_validation_questions` | yes |
| `github_enrichment_review_sheet.json` | `soc_validation_github_enrichment` | yes |
| `github_batch_intake_sheet.json` | `soc_validation_github_batch_intake` | no |
| `rag_sop_validation_sheet.json` | `soc_validation_rag_sop` | yes |
| `pending_skill_enrichment_backlog_sheet.json` | `soc_validation_pending_backlog` | no |
| `combination_matrix_sheet.json` | `soc_validation_combination_matrix` | no |
| `demo_scenario_sheet.json` | `soc_validation_demo_scenarios` | no |

All ten sheets are exposed via `GET /knowledge/exports/{artifact}` using the keys above.
Phase 11 demo/flag guidance: `docs/demo/flag_cutover_matrix.md`, `docs/demo/demo_scenarios_readiness.md`.

## Combination cases A–H

See `combination_matrix_sheet.json` for the planner runtime behavior per case (A happy-path → H unsafe_blocked).

## Demo scenarios

`demo_scenario_sheet.json` encodes `runtime_support_status` per scenario so a demo cannot overclaim. Only `runtime_active` use cases may be shown as live-supported; enrichment-only pilots (`email_phishing_header_review`) are design-only.

