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
| BL-004 | Offline `question_id -> use_case_id` map (infra, not a GitHub skill) | coverage-tooling | all 105 | N/A | P0 | B9 generator (landed) | `closed` (S1c — 41/105 mapped; see `docs/evals/bl004_coverage_closeout_report.md`) |
| BL-005 | Add explicit phishing question mappings | coverage-tooling | `email_phishing_header_review` | T1566 | P1 | authoritative question/use-case source | `deferred` |
| BL-006 | Add explicit ransomware/impact question mappings | coverage-tooling | `endpoint_ransomware_impact_review` | T1486 | P1 | authoritative question/use-case source | `deferred` |

**BL-004 note (updated 2026-07-01, S1c closeout):** mapping layer **closed for offline curation** — `docs/evals/question_use_case_map.json` (38 curated + 3 metadata-derived = **41/105** mapped) + deterministic auto-derivation (manifest `template_ref` == catalog `default_spl_template` or SPL-registry 3-hop). **64** rows remain `missing_authoritative_mapping` as genuine corpus gaps (`docs/evals/bl004_coverage_closeout_report.md`). Do not add mappings without explicit offline evidence.

## Batch 2 (implemented baseline)

The seven mandatory GitHub skills are recorded in `github_skill_intake_register.json` and curated into `backend/app/use_cases/content_enrichment.json` (Batch 2, 2026-06-06). This is metadata only; no live routing, SPL execution, MITRE runtime behavior, or prompt-loading behavior changes.
