# Plan 6 E2 — `P6_MITRE_DRAFT_PROMOTION`

Recorded 2026-08-13. **KEEP DEFERRED.** Retain
`DEFERRED_SEPARATE_GOVERNED_PROMOTION`.

This is **not** a promoter run, not a ledger edit, and not a protected-manifest
recapture.

## Decision

**KEEP DEFERRED**

Retain: `A2.5 = DEFERRED_SEPARATE_GOVERNED_PROMOTION`

Do **not**:

- run the existing promoter CLI (`scripts/promote_mitre_registry_to_runtime.py`)
- modify the 11-row drift ledger
  (`docs/input/mitre_enrichment/unpromoted_draft_drift_v1.json`)
- modify the runtime map (`backend/app/coverage/question_runtime_map_v1.json`)
- modify the catalog (`backend/app/use_cases/catalog.json`)
- recapture the protected manifest for a promotion

## Reason

E1 confirmed the candidate mappings and measured their analyst-visible effect,
but also showed that the existing promoter CLI is broader than an 11-question-row
promotion and would rewrite four catalog use cases, including dropping
`T1110.003` on `auth_failed_login_spike`.

Plan 6 does not have approval to broaden this governed metadata change.

## Preserved hashes (unchanged from E1)

| File | SHA-256 |
|---|---|
| `question_runtime_map_v1.json` | `621232b2a97b40b2944fede12e3a42723aaef1494367cb80c8ca2c3decb20c28` |
| `use_cases/catalog.json` | `2d66a82e2ce8a4e5f257cdc5dacd2a0cce58b2c5a7b18dd86eee7f5b44f85cfa` |
| `unpromoted_draft_drift_v1.json` | `c0c78e0a4edff1b7054542e06a16427a7e82ad888fcb6d2b272c9b9879a001d2` |

`python3 scripts/freeze_execution_baseline.py --check` remains **15/15**.

## Future promotion

E1 findings remain the evidence packet for a **separate** governed MITRE
promotion decision. That decision is outside Plan 6 production activation.

If promotion is later approved, it still needs:

1. explicit scope (11 question rows only vs full promoter CLI / catalog),
2. protected-manifest recapture for any written member of `PROTECTED`,
3. an empty drift ledger only as a consequence of a real promotion, never by
   editing the ledger to silence drift.

Source: `docs/evals/plan6/mitre_11row_promotion_delta.md`.
