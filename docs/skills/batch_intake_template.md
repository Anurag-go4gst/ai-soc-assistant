# Batch GitHub Skill Intake Template

Reusable checklist for reviewing a batch of 5–10 external GitHub skills.

**Batch theme:** ____________________

**Batch owner:** ____________________

**Target review date:** ____________________

## 1. Source skills reviewed

| GitHub Skill ID | Path | Reviewer | Date |
| --------------- | ---- | -------- | ---- |
| | | | |

## 2. Safety review

- [ ] Defensive-only purpose confirmed
- [ ] Offensive / destructive steps rejected or stripped
- [ ] No arbitrary shell / curl / direct execution required
- [ ] `no_runtime_markdown_loading=true` recorded
- [ ] Rejected sections logged in `rejected_github_skills.md` if partial accept

## 3. SOC relevance review

- [ ] SOC analyst utility confirmed
- [ ] Splunk / log / alert relevance assessed
- [ ] Enterprise demo suitability assessed
- [ ] Triage scores reviewed (advisory only)

## 4. Mapping decision

| Skill | Mapping type (A–E) | Internal use case(s) | Decision | Decision reason |
| ----- | ------------------ | ---------------------- | -------- | --------------- |
| | | | accept / reject / defer / duplicate / blocked | |

**Reminder:** `accept` = accepted_for_enrichment only, not runtime_active.

## 5. Proposed use cases

| Proposed use case id | Source skill | Catalog promotion needed? | SOC approval status |
| -------------------- | ------------ | ------------------------- | ------------------- |
| | | yes / no | needs_soc_review |

## 6. Curated enrichment draft

- [ ] `content_enrichment.json` draft prepared
- [ ] evidence requirements drafted
- [ ] investigation workflow drafted
- [ ] answer rules drafted
- [ ] limitations drafted
- [ ] no raw `SKILL.md` copied into runtime paths

## 7. SPL / RAG / MITRE notes

| Item | Status | Notes |
| ---- | ------ | ----- |
| SPL template need | active / planned / sop_only / unavailable | |
| RAG / SOP need | yes / no | |
| MITRE metadata | candidates only (`metadata_not_evidence`) | |

## 8. Tests required

- [ ] enrichment schema baseline tests updated
- [ ] factory baseline tests updated
- [ ] crosswalk regeneration checked
- [ ] governance regression green

## 9. Approval status

| Gate | Status | Approver | Date |
| ---- | ------ | -------- | ---- |
| Safety review | pending / approved | | |
| SOC mapping review | pending / approved | | |
| Enrichment metadata review | pending / approved | | |
| Catalog promotion (if any) | not_requested / pending / approved | | |

## 10. Activation lifecycle status

| Use case / skill | runtime_support_status | Allowed to claim runtime_active? |
| ---------------- | ---------------------- | -------------------------------- |
| | metadata_only / planned / sop_only | no until Phase 0 gate satisfied |

**Do not mark runtime_active based on GitHub acceptance alone.**
