# Row Authority Report

Report-only audit for the 105-question runtime map. `row_authority_status` is the reasoned enum; `s3_authority_ready` is the one-way projected readiness boolean.

- Rows: **170**
- 105-question rows: **105**
- Catalogue rows: **65**
- Projection mismatches against existing `s3_authority_ready`: **0**

## Status Counts

| row_authority_status | rows |
|---|---:|
| `catalog_weak_needs_enrichment` | 65 |
| `exact_known_needs_clarification` | 4 |
| `exact_known_needs_detection_binding` | 28 |
| `exact_known_needs_lookup` | 9 |
| `exact_known_unsupported` | 1 |
| `exact_known_weak_needs_enrichment` | 63 |

## Special Cases

| question_ref | row_authority_status | s3_authority_ready | blockers |
|---|---|---:|---|
| `q0.q002` | `exact_known_weak_needs_enrichment` | false | manifest_readiness:coe_synthetic_fixture |
| `q0.q004` | `exact_known_needs_lookup` | false | manifest_readiness:ioc_dependent |
| `q0.q007` | `exact_known_needs_detection_binding` | false | manifest_readiness:detection_dependent |
| `q0.q008` | `exact_known_needs_detection_binding` | false | manifest_readiness:detection_dependent |
| `q0.q010` | `exact_known_weak_needs_enrichment` | false | manifest_readiness:coe_synthetic_fixture |
| `q0.q017` | `exact_known_weak_needs_enrichment` | false | manifest_readiness:coe_synthetic_fixture |
| `q0.q028` | `exact_known_unsupported` | false | route_blocked, missing_proposed_primary_skill |
| `q0.q032` | `exact_known_weak_needs_enrichment` | false | manifest_readiness:dependency_missing |
| `q0.q036` | `exact_known_needs_lookup` | false | manifest_readiness:ioc_dependent |
| `q0.q045` | `exact_known_needs_clarification` | false | requires_clarification_or_case_context |
| `q0.q046` | `exact_known_weak_needs_enrichment` | false | manifest_readiness:coe_synthetic_fixture, skill_drift, coe_step3_implementation_not_approved, operation_authoritative_enabled_defaults_false |
| `q0.q062` | `exact_known_weak_needs_enrichment` | false | - |
| `q0.q103` | `exact_known_needs_clarification` | false | requires_clarification_or_case_context |
| `q0.q104` | `exact_known_needs_clarification` | false | requires_clarification_or_case_context |
| `q0.q105` | `exact_known_needs_clarification` | false | requires_clarification_or_case_context |
