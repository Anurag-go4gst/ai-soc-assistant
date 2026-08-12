# Plan 5 A1 — `mitre_runtime_kb_overlap` authority, measured

Decision recorded before measurement: **`A_KB_OVERLAP_AUTHORITY = DRAFT_AUTHORITATIVE_CURRENT_BEHAVIOR`**.
A1 measures whether the evidence contradicts it. **It does not.** No STOP; A2 proceeds.

Measured at HEAD `2080420`. Row-level data: `docs/evals/plan5/kb_overlap_rows.json` (all 61 rows).

## The conflict

`tools/coverage_authoring/mitre_permitted.py:93-94` recomputes `mitre_runtime_kb_overlap` /
`mitre_runtime_kb_match_count` as the intersection of the row's MITRE IDs with
`backend/app/threat/mitre_attack_subset.json`. The committed artifact instead holds the promoter's DRAFT
value (`scripts/promote_mitre_registry_to_runtime.py:70-73`). They disagree on **61 of 105 rows**.

Direction is uniform: **all 61 are rebuild-adds** — the recompute proposes *more* IDs than the committed
value, never fewer. The committed DRAFT value is empty on **59** of the 61 and non-empty on **2**.

Examples: `q0.q004` `[]` → `['T1071','T1041']`; `q0.q005` `[]` → `['T1071.004']`; `q0.q009` `[]` → `['T1071']`.

## Live reachability — the field IS read on the live path

Not inert. The chain is:

`chat/mitre_branch.py:72` / `threat/mitre_decision.py:67`
→ `mitre_registry_enrichment.registry_mitre_metadata_for_runtime` (`:274`)
→ `_synthetic_draft_item_from_runtime_row` (`:214`) reads `row["mitre_runtime_kb_overlap"]` into `kb_references`
→ `normalize_legacy_mitre_fields:115` extends the **candidate** technique list from it.

So the field feeds analyst-visible MITRE *candidate* IDs.

## Measured live effect: zero

Simulating the recompute on all 61 rows and re-normalizing through the real live function:

> **rows measured: 61 — rows where the recompute changes the live normalized metadata: 0**

Cause: `mitre_registry_enrichment.py:137` filters candidates against permitted —
`candidate = _dedupe([t for t in candidate if t not in set(permitted)])`. On every one of the 61 rows the
recomputed IDs are already in `mitre_permitted`, so they are dropped as redundant.

**Consequence for the decision.** The two options are indistinguishable at the live surface today. DRAFT is
therefore the correct choice on every axis: it is byte-idempotent against the committed artifact (the A0
property), it preserves current behaviour exactly, and it is the conservative direction (fewer asserted IDs)
if the `:137` filter ever changes. The recompute option is recorded as a separately-scoped future decision
with **no measured benefit** and a latent broadening risk — it should not be revisited without a reason
beyond tidiness.

## Second, larger finding: the 7 dropped fields are NOT live-inert

The same simulation run against the *other* half of the defect — stripping the 7 promoter-owned fields, i.e.
exactly what a regeneration does today — gives a different answer:

> **rows: 105 — rows whose live MITRE metadata changes if the 7 fields are dropped: 11**

None becomes `None`; all 11 differ in one field, `mitre_candidate`, and every one **broadens**:

| question_ref | `mitre_candidate` today | after a regeneration |
|---|---|---|
| `q0.q021`, `q0.q028`, `q0.q040` | `[]` | `['T1071']` |
| `q0.q046`, `q0.q047`, `q0.q060`, `q0.q062`, `q0.q089` | `[]` | `['T1110']` |
| `q0.q050`, `q0.q063`, `q0.q083` | `[]` | `['T1059.001']` |

Mechanism: `registry_mitre_metadata_for_runtime` only takes the governed runtime path when
`runtime_row.get("mitre_registry")` is a dict (`:280`). Dropping `mitre_registry` collapses those rows to the
draft/enrichment fallback, which does not apply the registry's suppression.

**This reclassifies the A2 defect.** It is not "committed metadata is lost and can be re-promoted" — a
regeneration would make the system assert MITRE technique IDs on 11 of 105 questions that the governed
registry currently suppresses. That is an unsupported-claim broadening, the exact failure mode the MITRE
visibility policy exists to prevent. It raises the priority of A3 (the test that writes the real artifact) from
hygiene to containment.
