# Pending Skill Enrichment Backlog

Future GitHub skills and SOC topics for intake review.  
Workflow: [`README.md`](README.md) · Register: [`github_skill_intake_register.json`](github_skill_intake_register.json)

**Status values:** `not_reviewed` | `review_in_progress` | `accepted_for_enrichment` | `deferred` | `blocked` | `implemented` | `tested` | `rejected`

## Backlog

| Backlog ID | GitHub Skill / Topic | SOC Domain | Internal Use Case Candidate | MITRE Candidate | Priority | Dependency | Status |
| ---------- | -------------------- | ---------- | --------------------------- | --------------- | -------- | ---------- | ------ |
| BL-001 | `detecting-lateral-movement-with-splunk` | endpoint-security | `edr_lateral_movement_candidate` | T1021 | P2 | P1–P7 pilots | `deferred` |
| BL-002 | `detecting-pass-the-hash-attacks` | identity-access-management | `edr_lateral_movement_candidate` | T1550.002 | P3 | BL-001 | `not_reviewed` |
| BL-003 | `hunting-for-dcom-lateral-movement` | endpoint-security | `edr_lateral_movement_candidate` | T1021 | P3 | BL-001 | `not_reviewed` |
| BL-004 | Offline `question_id -> use_case_id` map (infra, not a GitHub skill) | coverage-tooling | all 105 | N/A | P0 | B9 generator (landed) | `in_progress` |
| BL-005 | Add explicit phishing question mappings | coverage-tooling | `email_phishing_header_review` | T1566 | P1 | authoritative question/use-case source | `deferred` |
| BL-006 | Add explicit ransomware/impact question mappings | coverage-tooling | `endpoint_ransomware_impact_review` | T1486 | P1 | authoritative question/use-case source | `deferred` |

**BL-004 note (updated 2026-06-06):** mapping layer landed — `docs/evals/question_use_case_map.json` (hand-curated, the only place to add a manual mapping) + deterministic auto-derivation in the generator (manifest `template_ref` == unique catalog `default_spl_template`). Each matrix row now carries `mapping_status` / `mapping_source_file` / `mapping_confidence`.

Current coverage: **1 / 105** rows mapped (`q0.q062` → `auth_failed_login_spike`, `mapped_from_existing_metadata`, high) — that row populates `use_case_id`, both GitHub references, intake decision, evidence requirements, and MITRE candidate end-to-end. The other **104** are `missing_authoritative_mapping` (no defensible offline source — the 105 questions and 46 catalog use cases are different corpora; 0 exact `example_queries` matches).

**To raise coverage:** add explicit, evidence-cited entries to `question_use_case_map.json` (cite the offline source per entry; never infer from fuzzy intent patterns), then re-run `python3 scripts/build_skill_coverage_matrix.py && python3 scripts/build_skill_coverage_matrix.py --check`. A future option is a one-shot runtime snapshot export of router resolutions (kept as data, not imported). Independent of mapping, `mitre_permitted` (76 rows), `live`/`planning` skill, and `spl_template_status` already carry per-question signal. See plan §R.6.

## Batch 2 (implemented baseline)

The seven mandatory GitHub skills are recorded in `github_skill_intake_register.json` and curated into `backend/app/use_cases/content_enrichment.json` (Batch 2, 2026-06-06). This is metadata only; no live routing, SPL execution, MITRE runtime behavior, or prompt-loading behavior changes.
