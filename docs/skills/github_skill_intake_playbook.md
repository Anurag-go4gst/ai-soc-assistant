# GitHub Skill Intake Playbook (Phase 0B)

Governed process for safely discovering, triaging, reviewing, and tracking external GitHub-derived cybersecurity skills.

**Planning and export only.** This playbook does not change `/chat`, planner, LangGraph routing, SPL execution, or MITRE runtime behavior.

## Purpose

The Skill Expansion Factory lets the SOC team add more GitHub skills later without:

- changing the core planner graph
- loading raw `SKILL.md` into prompts or runtime RAG
- treating GitHub acceptance as runtime activation

Canonical artifacts:

| Artifact | Role |
|----------|------|
| `github_skill_discovery_index.json` | Metadata scan of local clone |
| `github_skill_triage_scores.json` | Advisory scoring only |
| `github_skill_intake_register.json` | Human-reviewed decisions |
| `proposed_use_cases_from_github.json` | Proposed internal use cases |
| `content_enrichment.json` | Curated enrichment metadata |
| `soc_capability_crosswalk.json` | Unified mapping spine |

## Critical rule: acceptance ≠ runtime activation

`decision=accept` in the intake register means **accepted_for_enrichment only**.

It does **not** mean:

- `runtime_active`
- a new live execution skill
- automatic planner branch eligibility
- permission to load raw `SKILL.md` into prompts or RAG

Runtime activation remains governed by catalog presence, SOC approval, allowed live skill, SPL status, tests, and crosswalk rules from Phase 0.

## Lifecycle stages

1. **Discover** — scan local clone (`AI_SOC_GITHUB_SKILL_CLONE_ROOT`) for `skills/**/SKILL.md`
2. **Triage** — advisory scores; no auto-accept
3. **Safety review** — defensive conversion checklist
4. **SOC mapping review** — map to internal use case(s)
5. **Decision** — `accept` | `reject` | `defer` | `duplicate` | `blocked`
6. **Curated enrichment** — add metadata to `content_enrichment.json` only after accept
7. **Catalog promotion** — separate SOC step if a new use case becomes catalog-backed
8. **Crosswalk refresh** — regenerate `soc_capability_crosswalk.json`
9. **Tests / validation** — schema and governance baselines only in this stage

## Mapping types

| Type | Meaning |
|------|---------|
| **A** | Existing active catalog use case |
| **B** | Existing planned catalog use case |
| **C** | Proposed new use case (not catalog-promoted) |
| **D** | SOP / RAG-only capability |
| **E** | Rejected / deferred / duplicate / no mapping |

## Defensive conversion checklist

Before accept:

- [ ] Primary purpose is defensive investigation, triage, or detection review
- [ ] Offensive execution steps removed or rejected
- [ ] No arbitrary shell / curl / direct tool execution required at runtime
- [ ] Evidence model can be expressed as bounded fields / requirements
- [ ] MITRE references treated as metadata only (`metadata_not_evidence`)
- [ ] SPL references can be converted to governed templates or marked `sop_only`
- [ ] Limitations and not-claimed defaults documented
- [ ] Human review preserved for SPL / execution gates

## What may be extracted into curated enrichment

- `evidence_requirements`
- `investigation_workflow`
- `analyst_checklist`
- `answer_rules`
- `limitations`
- `not_claimed_defaults`
- `allowed_spl_templates` references
- redacted GitHub provenance paths / ids
- MITRE candidate metadata

## What must never be extracted

- raw `SKILL.md` body into prompts or runtime RAG
- executable scripts from the reference repo
- offensive payloads, exploit chains, or destructive actions
- unreviewed MITRE claims as runtime evidence
- new live execution skills outside the 4-skill enum

## SOC approval workflow

1. Review discovery + triage exports in Knowledge UI
2. Record decision in `github_skill_intake_register.json`
3. If rejected/deferred, update `rejected_github_skills.md` or backlog artifact
4. If accepted, add curated metadata to `content_enrichment.json`
5. If proposed use case, track in `proposed_use_cases_from_github.json`
6. Regenerate factory artifacts and crosswalk
7. SOC sign-off before any catalog promotion or runtime activation claim

## Batch process (future batches of 5–10 skills)

Use [`batch_intake_template.md`](batch_intake_template.md).

Batch 2 candidates are **plan-only** in this phase. Do not implement new Batch 2 skills here.

## Regeneration commands

```bash
export AI_SOC_GITHUB_SKILL_CLONE_ROOT=/tmp/ai-soc-references/Anthropic-Cybersecurity-Skills
python3 scripts/build_github_skill_discovery_index.py
python3 scripts/score_github_skill_triage.py
python3 scripts/build_github_skill_factory_artifacts.py
python3 scripts/build_soc_capability_crosswalk.py
python3 scripts/build_soc_capability_crosswalk.py --check
```
