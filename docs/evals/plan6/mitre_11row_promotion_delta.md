# Plan 6 E1 — 11-row MITRE DRAFT promotion, analyst-visible delta

Offline measurement only. **The promoter was not run against committed artifacts.** The drift ledger was not edited.

Measured 2026-08-13 on branch `feat/plan6-production-activation` by applying `runtime_patch_for_draft_item` in memory and resolving through `registry_mitre_metadata_for_runtime` (the live `/chat` lookup used by `threat/mitre_decision.py`) plus `resolve_mitre_decision` postures. Script: `scripts/eval_plan6_e1_mitre_delta.py`. Row-level JSON: `docs/evals/plan6/mitre_11row_promotion_delta.json`.

This item does **not** decide promotion. That is `P6_MITRE_DRAFT_PROMOTION` (E2).

**E2 recorded 2026-08-13: KEEP DEFERRED.** `DEFERRED_SEPARATE_GOVERNED_PROMOTION` is retained. See `docs/evals/plan6/e2_stop_decision.md`.

## What would be written

A full `scripts/promote_mitre_registry_to_runtime.py` run (the only existing promoter) is **not** an 11-row surgical patch. In memory:

| Artifact | Rows whose promoter patch differs from committed |
|---|---|
| `backend/app/coverage/question_runtime_map_v1.json` | **exactly the 11** named below |
| `backend/app/use_cases/catalog.json` | **4** use cases (side effect of the same CLI) |

The 11 question rows change **only** `mitre_candidate` (and the mirrored `mitre_registry.candidate`). Permitted, blocked, visibility policy, evidence flags, and mapping rationale are unchanged on every row.

Ledger provenance for every added ID: `llm_catalogue_audit_2026-06-16:candidate_promotion`. Not evidence-backed.

## Protected files were not written

SHA-256 unchanged across the measurement:

| File | SHA-256 |
|---|---|
| `question_runtime_map_v1.json` | `621232b2a97b40b2944fede12e3a42723aaef1494367cb80c8ca2c3decb20c28` |
| `use_cases/catalog.json` | `2d66a82e2ce8a4e5f257cdc5dacd2a0cce58b2c5a7b18dd86eee7f5b44f85cfa` |
| `unpromoted_draft_drift_v1.json` | `c0c78e0a4edff1b7054542e06a16427a7e82ad888fcb6d2b272c9b9879a001d2` |

## Analyst-visible delta (question runtime map)

Plan 5 A1’s table (`[]` → `T1071` / `T1110` / `T1059.001` on `mitre_candidate`) is **correct for that field**. It is **not** the whole analyst-visible story: 8 of 11 rows already have permitted IDs that `resolve_mitre_decision` can show today.

Live-investigation posture used below: `intent_family=live_investigation`, `answer_mode=live_investigation`, alert context present, no extra explicit MITRE flag. That is the path where `answer_visible` can become true.

### Group 1 — new mapping (3 rows)

Currently `mitre_permitted=[]`, `mitre_candidate=[]`, visibility `trace_only`, decision `no_registry_mapping`. Promotion inserts one governed candidate. Live investigation stays `answer_visible=false` and `technique_ids=[]`. Status becomes `candidate` and `registry_candidates` gains the ID, which flows into answer-contract `candidate_mitre` / “Candidate MITRE (metadata only)” rationale.

| question_ref | Question | After `mitre_candidate` |
|---|---|---|
| `q0.q021` | Which hosts communicated with foreign IP ranges? | `T1071` |
| `q0.q028` | Which hosts showed peer-to-peer style communication? | `T1071` |
| `q0.q040` | Which hosts initiated traffic to rare countries? | `T1071` |

### Group 2 — already-visible set widens (8 rows)

These rows already have permitted techniques. Promotion **adds** the DRAFT candidate to the live answer’s technique list when MITRE is already answer-visible.

| question_ref | Question | Permitted today | Added candidate | Live `technique_ids` today → after |
|---|---|---|---|---|
| `q0.q046` | Which users have excessive failed logins? | `T1110.001` | `T1110` | `T1110.001` → `T1110.001, T1110` |
| `q0.q047` | Is one IP attacking many accounts? | `T1110.001` | `T1110` | `T1110.001` → `T1110.001, T1110` |
| `q0.q060` | Which accounts had a successful login after repeated failures? | `T1078`, `T1110.001` | `T1110` | `T1110.001` → `T1110.001, T1110` |
| `q0.q062` | Which hosts show a spike in failed logins? | `T1110.001` | `T1110` | `T1110.001` → `T1110.001, T1110` |
| `q0.q089` | Which users authenticated to VPN after repeated MFA failures? | `T1078`, `T1110.001` | `T1110` | `T1110.001` → `T1110.001, T1110` |
| `q0.q050` | Did Office apps spawn cmd or PowerShell? | `T1204`, `T1059` | `T1059.001` | `T1059` → `T1059, T1059.001` |
| `q0.q063` | Which endpoints spawned script interpreters recently? | `T1059` | `T1059.001` | `T1059` → `T1059, T1059.001` |
| `q0.q083` | Which hosts have suspicious parent-child process chains? | `T1059`, `T1204` | `T1059.001` | `T1059` → `T1059, T1059.001` |

On these 8, `answer_visible` is already `true` under live investigation and stays `true`. The widening is an extra parent (`T1110`) or extra sub-technique (`T1059.001`) on the analyst-visible candidate list.

Parent vs sub-technique: the DRAFT adds `T1110` beside an already-permitted `T1110.001`, and `T1059.001` beside an already-permitted `T1059`. That is a specificity change, not a first mapping.

### Other postures (same 11 rows)

- **No intent / knowledge `rag_only`:** Group 1 stays not answer-visible (`no_registry_mapping` → `not_answer_visible`). Group 2 stays `requires_alert_context` or equivalent; `registry_candidates` still grow.
- **Explicit MITRE without alert:** Group 2 (alert-required) stays hidden (`requires_alert_context`); Group 1 can enter `candidate` with the ID in `not_claimed` / `registry_candidates`.
- **Explicit MITRE with alert:** matches live investigation for Group 2 (technique list widens). Group 1 remains `answer_visible=false`.

Visibility policy does not change on any of the 11 (`trace_only` stays `trace_only`; `answer_if_requested` / `answer_if_supported` stay).

## Catalog side effect (if the existing promoter CLI is used)

Not requested as the 11-row question delta, but the same CLI would rewrite `catalog.json`:

| use_case_id | Analyst-visible candidate change |
|---|---|
| `auth_account_lockout_trend` | `T1110.001` → `T1110.001, T1110` (widens) |
| `auth_failed_login_spike` | `T1110, T1110.001, T1110.003` → `T1110.001, T1110` (**drops `T1110.003`**) |
| `net_new_outbound_destination` | `[]` → `T1071` (new mapping, same shape as Group 1) |
| `edr_malware_alert_summary` | `mitre_registry` block rewrite only; candidate IDs stay empty |

E2 cannot treat “promote the 11 questions” as equivalent to “run the promoter.” The CLI also mutates the protected catalog, including one **narrowing**.

## What this is not

- Not a regeneration / `mitre_registry`-drop. That is the Plan 5 A2 containment defect; builder tests still pin it.
- Not an evidence-supported claim. Added IDs stay candidates. Group 1 stays trace/metadata-only on the live-investigation posture measured here.
- Not a recommendation to promote. Group 2 **does** add IDs to an already answer-visible list. Provenance is an LLM catalogue audit.

## E2 decision inputs

Keep `DEFERRED_SEPARATE_GOVERNED_PROMOTION` unless the user explicitly approves promotion **and** protected-manifest recapture.

If promotion is approved later, capture at least:

- `backend/app/coverage/question_runtime_map_v1.json`
- `backend/app/use_cases/catalog.json`

and decide whether the 4 catalog diffs are in scope. Do not empty `docs/input/mitre_enrichment/unpromoted_draft_drift_v1.json` by editing it; only a real promotion that removes measured drift may empty `rows`.
