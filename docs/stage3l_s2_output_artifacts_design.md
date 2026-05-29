# Stage 3L-S2B: Output Artifacts — Design Note

**Status:** Design only — gated separately from [S2A intent bridge](stage3l_s2_intent_bridge_design.md).

**Purpose:** Define what `output_artifacts` means without implementing renderer or `/chat` response changes.

---

## Problem

“Show candidate SPL” vs “answer the SOC question” is an **output shape** distinction, not a `primary_skill` distinction. S2A must not collapse this into operation mapping alone.

---

## Candidate artifact tokens (draft — sign-off required)

| Token | Meaning | Typical legacy intent |
|-------|---------|------------------------|
| `candidate_spl_visible` | Analyst may see governed candidate SPL in trace/UI | `spl_generation`, some `attack_discovery` |
| `analyst_summary_only` | Narration/summary without new SPL surface | `alert_summary`, parts of `knowledge_recall` |
| `knowledge_only` | SOP/playbook/MITRE KB — no SPL | `knowledge_recall` |

Do not add tokens in implementation until listed here is approved.

---

## Consumers (map only in S2B — no code)

| Consumer | Reads artifact? | S2B action |
|----------|-----------------|------------|
| `app/spl/template_renderer.py` | If `candidate_spl_visible` | Document contract |
| Evidence / lineage (`app/evidence/`, Q1E) | Package refs | Document contract |
| Context sufficiency / answer modes | May affect `spl_review_only` | Document contract |
| `/chat` response assembly | Analyst card | **Out of scope** until later stage |

---

## Sign-off

| Reviewer | Approved | Date |
|----------|----------|------|
| | ☐ | |
