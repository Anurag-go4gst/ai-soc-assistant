# MITRE expansion-candidate validation (plan §15 G3)

- Generated: `2026-06-17T08:33:53.058698+00:00`
- Audit source: `docs/evals/out/llm_mitre_catalogue_audit.json`
- Bundle techniques (excluded): **98**
- Expansion candidates: **13**
- Resolver operational: **True**

Dispositions: `deprecated`=9, `not_found`=4

> Candidates = union of all `results[*].llm_invalid_ids` (out-of-subset proposals) minus the local bundle. No `expansion` bucket exists in the audit JSON; this set is derived. When no offline resolver is onboarded, every row is `pending_bundle` (honest, not a fabricated promote/drop).

| techniqueID | disposition | name |
|---|---|---|
| `T0819` | not_found |  |
| `T0839` | not_found |  |
| `T0849` | not_found |  |
| `T0881` | not_found |  |
| `T1022` | deprecated |  |
| `T1043` | deprecated |  |
| `T1045` | deprecated |  |
| `T1053.004` | deprecated |  |
| `T1070.001` | deprecated |  |
| `T1086` | deprecated |  |
| `T1193` | deprecated |  |
| `T1562` | deprecated |  |
| `T1562.001` | deprecated |  |
