# B2 — Tier authority unification measurement

**Date:** 2026-08-12  
**Decision:** `lane_router.py` is the live-path tier authority (approved).

## Path-set disagreement

| Constant | `lane_router` | `match_tiers` (pre-B2) | Post-B2 |
|----------|---------------|------------------------|---------|
| T3-only paths | `fuzzy_alias_catalog` | _(absent)_ | **imported from lane_router** |

T1 and T2 path sets were already identical.

## Live bind disagreement (105 corpus)

Measured by running `understand_query` on all 105 runtime-map questions and comparing:

- `initial_tier_for_match_path(qu.deterministic_match_path)` (`lane_router`)
- `_tier_from_understanding(qu).tier` or `T4` (`match_tiers`)

**Result: 0 / 105 disagreements.**

Top match paths on 105: `exact_105_question` (91), `exact_105_plus_use_case_catalog` (14).

## Change applied

`match_tiers.py` imports `T1_PATHS`, `T2_PATHS`, `T3_PATHS` from `lane_router`; local duplicate literals retired to compatibility aliases.

## Live bind outcome check

`test_canonical_catalogue_tier_authority.py` (8 probes) re-run post-change — all pass. No live `live_router_bind` outcome change measured.
