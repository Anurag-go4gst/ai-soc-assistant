# BL-004 coverage mapping closeout (S1c)

Generated: 2026-07-01T17:18:57.766348+00:00

## Summary

| Metric | Value |
|--------|------:|
| Total questions | 105 |
| Mapped rows | 41 |
| Unmapped rows (warnings) | 64 |
| Curated manual mappings | 38 |
| Metadata-derived mappings | 3 |
| GitHub joins | 5 |
| Catalog use cases | 65 |
| Sample anchors (`registry_tier=sample`) | 7 |
| Reviewed unmapped (explicit gaps) | 10 |

## Mapping status breakdown

- `curated_manual`: 38
- `mapped_from_existing_metadata`: 3

## Remaining unmapped by `pattern_type`

- `new_or_unusual_source`: 14
- `dns_beaconing_dga_behavior`: 8
- `multi_signal_correlation`: 8
- `top_n_aggregation`: 7
- `notable_risk_lookup`: 5
- `suspicious_process_powershell`: 5
- `asset_identity_context`: 5
- `case_state_lookup`: 3
- `persistence_scheduled_task_service`: 3
- `data_source_health`: 2
- `threat_intel_enrichment`: 1
- `other_or_unclear`: 1
- `dlp_exfiltration`: 1
- `ioc_correlation`: 1

## Closeout decision

Remaining 64 rows are genuine offline corpus gaps — no authoritative question→use_case join without runtime router reconstruction, fuzzy intent match, or false family join.

Do **not** add further offline mappings without a new explicit evidence source (manifest `template_ref`, catalog `default_spl_template` equality, or hand-curated note with offline citation). Reviewed-unmapped rows in `question_use_case_map.json` stay unmapped by design.

## Commits

- `bf98c56` — S1a + S1a.1 curated mappings + 3 analytics sample anchors
- `b454b9f` — S1b four detection-family sample anchors + 30 curated mappings

## Next slice

**S2** — formalize `ChatPipelineState` v2 fields and per-node `node_trace` (additive; no route behavior change).
