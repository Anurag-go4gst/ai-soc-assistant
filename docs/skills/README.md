# GitHub Skill Intake & Enrichment Tracking

**Planning only** — these files are governance documentation. They are **not** loaded into runtime or LLM prompts.

Canonical plan: [`plans/AI_SOC_MASTER_PLAN.md`](../../plans/AI_SOC_MASTER_PLAN.md) (Tracks B + D).

## Files

| File | Purpose |
|------|---------|
| [`github_skill_intake_register.json`](github_skill_intake_register.json) | One record per GitHub skill reviewed (D1) |
| [`rejected_github_skills.md`](rejected_github_skills.md) | Permanent rejection log (D2) |
| [`pending_skill_enrichment_backlog.md`](pending_skill_enrichment_backlog.md) | Deferred / future candidates (D3) |
| [`skill_enrichment_status_matrix.md`](skill_enrichment_status_matrix.md) | Per use-case implementation status (D4) |
| [`../../backend/app/use_cases/content_enrichment.json`](../../backend/app/use_cases/content_enrichment.json) | Batch 2 curated enrichment metadata keyed by internal/proposed use case |
| [`../evals/skill_coverage_matrix.json`](../evals/skill_coverage_matrix.json) | 105-question coverage master (D5 / B9 — future) |

## Reference clone (read-only)

```text
/tmp/ai-soc-references/Anthropic-Cybersecurity-Skills
Commit: 04450304b12645cb2b974ab96d28c0664758a88d
```

Re-clone when reviewing new skills; always record `repo_commit` in the intake register.

## Decision workflow (D6)

1. Inspect `SKILL.md` locally (never execute `scripts/`).
2. Record in `github_skill_intake_register.json`.
3. Apply defensive-conversion checklist (plan §C).
4. Decide: `accept` | `reject` | `defer` | `needs_review`.
5. Rejected → `rejected_github_skills.md`. Deferred → `pending_skill_enrichment_backlog.md`.
6. Accepted → map use case, live skill, planning skill, MITRE evidence, SPL status.
7. Update `skill_enrichment_status_matrix.md`.
8. Add curated metadata to `content_enrichment.json`; do not change `catalog.json` for metadata-only batches.
9. Update `skill_coverage_matrix.json` through the offline generator.
10. Add schema/data validation tests.

## Locked constraints

- Preserve 4 live execution skills and dual semantics (`legacy_router_intent_hint`, `proposed_primary_skill`).
- No GitHub `SKILL.md` runtime loading.
- P3/P6/P7 may ship enrichment without new 105-question rows initially.
