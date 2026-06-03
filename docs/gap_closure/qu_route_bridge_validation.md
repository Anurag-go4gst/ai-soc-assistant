# QU → route_skill Bridge — Validation Report

Generated after shipping the QU-first routing bridge (`select_route_from_understanding`, single `understand_query`, `routing_provenance`).

## How to reproduce

```bash
./scripts/run_stage3_governance_regression.sh
python3 scripts/eval_qu_route_bridge_105.py
```

Artifacts:

- `docs/evals/out/qu_route_bridge_105_routing.json` — per-105 keyword vs QU-first comparison
- `docs/evals/out/stage3l_105_shadow_eval.json` — structural S6.2 governance (unchanged contract)

## 105 routing comparison (`deterministic_only`)

Compares legacy `route_skill_deterministic` vs `route_skill` with `understand_query` on each canonical 105 question text.

| Metric | Meaning |
|--------|---------|
| `keyword_router_needs_clarification` | `tool_plan` contains `needs_clarification` (keyword path) |
| `qu_first_needs_clarification` | Same after QU-first bridge |
| `clarification_delta` | keyword − QU (positive = QU improved classification) |
| `skill_divergence_count` | Rows where final `skill` differs |

**Latest run (deterministic_only, 105 canonical questions):**

| Metric | Count |
|--------|------:|
| `keyword_router_needs_clarification` | 99 |
| `qu_first_needs_clarification` | 0 |
| `clarification_delta` | 99 |
| `skill_divergence_count` | 91 |

All 105 rows used `authority_source=query_understanding_105` on the QU path (exact or exact+catalog matches).

## Spot-check trace fields (UI / API)

For manual or automated trace review, confirm on `routed`:

| Case | `deterministic_match_path` | Expect `selected_by` | Expect `skill` |
|------|---------------------------|----------------------|----------------|
| Exact 105 (e.g. q0.q001) | `exact_105_question` | `query_understanding_105` | registry `legacy_router_intent_hint` |
| 105 + catalog (e.g. q0.q046) | `exact_105_plus_use_case_catalog` | `query_understanding_105` or `_catalog` | enum hint (e.g. `attack_discovery`) |
| Catalog non-enum | `use_case_catalog` | `query_understanding_catalog` | collapsed `knowledge_recall` + `collapsed_from` |
| Near 105 | `near_105_question` | `query_understanding_105_near` | provisional enum hint |
| Out of registry | `out_of_registry` | `query_understanding_weak` | `knowledge_recall` + `needs_clarification` |

Under `llm_assisted_semantic`, exact 105 should keep `query_understanding_105` (not `llm_assisted_semantic_normalized`). `llm_adjudication.status` is `not_needed` when deterministic path is confident.

## Registry depth (P0 follow-up in this pass)

| Item | Status |
|------|--------|
| `mitre_permitted[]` on `question_runtime_map_v1.json` | Emitted from taxonomy `suggested_MITRE_candidates` + manifest use-case overlap |
| Live `/chat` MITRE | `resolve_mitre_mappings_for_chat()` merges use-case KB + registry permitted IDs in runtime subset |
| Operation authority allowlist | All non-blocked manifest `coverage_id` values are allowlistable (default env allowlist still empty) |
| q106+ authoring | `tools/coverage_authoring/supplemental_taxonomy_rows.json` + `coverage_drafter.py --append-supplemental` + `--emit-maps` |

## Not claimed

- 105/105 live executable answers
- MITRE synthesis authority (permitted set is report-first; KB overlap only)
- Operation authority applied without explicit `ROUTE_AUTHORITY_OPERATION_COVERAGE_ALLOWLIST` env entries
