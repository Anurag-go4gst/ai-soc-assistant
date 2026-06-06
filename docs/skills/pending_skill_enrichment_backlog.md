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
| BL-004 | Offline `question_id → use_case_id` map (infra, not a GitHub skill) | coverage-tooling | all 105 | — | P0 | B9 generator (landed) | `not_reviewed` |

**BL-004 note:** B9's `skill_coverage_matrix.json` cannot populate `use_case_id` / `github_reference_skill` / `github_intake_decision` / `evidence_requirements` until a deterministic offline question→use_case mapping exists (runtime router resolution is `app.*`, not importable by the offline generator). Curate a JSON map or export a one-shot runtime snapshot, then re-run `scripts/build_skill_coverage_matrix.py`. See plan §R.6.

## Batch 1 (in register — not backlog)

The seven mandatory GitHub skills are recorded in `github_skill_intake_register.json` (slice 0, 2026-06-06). See plan `plans/AI_SOC_MASTER_PLAN.md` §H D7.
