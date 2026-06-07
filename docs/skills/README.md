# GitHub Skill Intake & Enrichment Tracking

**Planning only** — these files are governance documentation. They are **not** loaded into runtime or LLM prompts.

Canonical plan: [`plans/AI_SOC_MASTER_PLAN.md`](../../plans/AI_SOC_MASTER_PLAN.md) (Tracks B + D).

## Files

| File | Purpose |
|------|---------|
| [`github_skill_discovery_index.json`](github_skill_discovery_index.json) | Phase 0B metadata scan of local clone (no raw SKILL.md bodies) |
| [`github_skill_triage_scores.json`](github_skill_triage_scores.json) | Advisory triage scores (no auto-accept) |
| [`github_skill_intake_register.json`](github_skill_intake_register.json) | One record per GitHub skill reviewed (D1) |
| [`proposed_use_cases_from_github.json`](proposed_use_cases_from_github.json) | Proposed internal use cases (never runtime_active) |
| [`skill_enrichment_status_matrix.json`](skill_enrichment_status_matrix.json) | JSON-backed per use-case implementation status |
| [`pending_skill_enrichment_backlog.json`](pending_skill_enrichment_backlog.json) | JSON-backed advisory backlog |
| [`github_skill_intake_playbook.md`](github_skill_intake_playbook.md) | Phase 0B factory process |
| [`batch_intake_template.md`](batch_intake_template.md) | Reusable batch review checklist |
| [`rejected_github_skills.md`](rejected_github_skills.md) | Permanent rejection log (D2, markdown-backed) |
| [`pending_skill_enrichment_backlog.md`](pending_skill_enrichment_backlog.md) | Human-readable backlog notes (source for early drafts) |
| [`skill_enrichment_status_matrix.md`](skill_enrichment_status_matrix.md) | Human-readable status matrix notes |
| [`../../backend/app/use_cases/content_enrichment.json`](../../backend/app/use_cases/content_enrichment.json) | Batch 2 curated enrichment metadata keyed by internal/proposed use case |
| [`../evals/soc_capability_crosswalk.json`](../evals/soc_capability_crosswalk.json) | Canonical mapping spine (Phase 0 + factory visibility) |
| [`../evals/skill_coverage_matrix.json`](../evals/skill_coverage_matrix.json) | 105-question coverage master (legacy view) |

## Reference clone (read-only)

```text
/tmp/ai-soc-references/Anthropic-Cybersecurity-Skills
Commit: 04450304b12645cb2b974ab96d28c0664758a88d
```

Configure with `AI_SOC_GITHUB_SKILL_CLONE_ROOT` when the clone lives elsewhere.

Re-clone when reviewing new skills; always record `repo_commit` in the intake register.

**Important:** `decision=accept` means accepted_for_enrichment only — not `runtime_active`.

## Phase 0B regeneration

```bash
export AI_SOC_GITHUB_SKILL_CLONE_ROOT=/tmp/ai-soc-references/Anthropic-Cybersecurity-Skills
python3 scripts/build_github_skill_discovery_index.py
python3 scripts/score_github_skill_triage.py
python3 scripts/build_github_skill_factory_artifacts.py
python3 scripts/build_soc_capability_crosswalk.py
```

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
