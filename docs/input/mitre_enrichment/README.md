# MITRE enrichment drafts (105 questions + 42 use cases)

Authoring inputs for SOC/COE review before promotion into canonical registries.

| File | Count | Paste / promote into |
|------|------:|----------------------|
| `question_105_for_mitre_enrichment.DRAFT.json` | 105 | Taxonomy `suggested_MITRE_candidates` → `coverage_drafter --emit-maps` → `question_runtime_map_v1.json` `mitre_permitted[]` |
| `use_case_42_for_mitre_enrichment.DRAFT.json` | 42 | `backend/app/use_cases/catalog.json` `mitre_candidates` (+ optional `mitre_attack_subset.json` links) |

**Sources of truth (read-only):**

- `backend/app/coverage/question_runtime_map_v1.json`
- `docs/soc_question_taxonomy_stage3k_q0.md`
- `backend/app/use_cases/catalog.json`
- `backend/app/coverage/pattern_coverage_v1.json` (manifest / `spl_template_id`)

**Do not** treat these drafts as runtime config. See `docs/gap_closure/p0_stakeholder_48_routable_and_mitre.md` and `backend/app/threat/mitre_soc_review_export.py` for SOC approval flow.
