# Stage 3L-S2B: Output Artifacts — Design Note

**Status:** Shadow library landed (2026-05-29) — [`output_artifacts.py`](../backend/app/routing/output_artifacts.py) + shadow/lineage only. **COE sign-off still pending** before renderer or analyst-card consumers. Gated separately from [S2A intent bridge](stage3l_s2_intent_bridge_design.md).

**Purpose:** Define what `output_artifacts` means; S2B resolves tokens on `route_plan_shadow` without renderer or answer-text changes.

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

Approved for shadow resolution only (see `LEGACY_INTENT_DEFAULT_TOKENS` in code). Do not add new tokens without updating this table and COE sign-off.

---

## Shadow resolution (implemented)

| Legacy intent | Resolved tokens |
|---------------|-----------------|
| `attack_discovery` | `candidate_spl_visible` |
| `spl_generation` | `candidate_spl_visible` (bridge hint when present) |
| `knowledge_recall` | `knowledge_only` |
| `alert_summary` | `analyst_summary_only` |

`route_plan_shadow.output_artifacts.renderer_applied` is always `false`.

---

## Consumers (map only — renderer still out of scope)

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
