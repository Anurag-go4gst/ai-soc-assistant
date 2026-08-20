# SPL Relevance Baseline (Phase A)

Deterministic structural relevance — does generated SPL match the asked
data source, metric/aggregation, and entity? No LLM, no app behavior change.

| Corpus | Relevant | Total | % | Lanes |
|--------|----------|-------|---|-------|
| 105 canonical | 87 | 102 | 85.3 | {'draft': 102} |
| Catalogue (spl-expected) | 40 | 46 | 87.0 | {'template': 24, 'draft': 16, 'none': 6} |

Catalogue row classes: {'spl_expected': 46, 'justified_no_spl': 12, 'deferred': 7} — `justified_no_spl`
(analyst-workflow / knowledge skills) and `deferred` (OT "later") are
excluded from the coverage denominator; they are correctly handled without SPL.

> Corpora reported separately by design — 105 (pattern_type keyspace) and
> catalogue (use_case_id keyspace) overlap; a combined /151 would double-count.

## Top mismatch reasons

- **105**: {'entity_missing': 6, 'data_source_missing:dns': 5, 'data_source_missing:auth': 5, 'data_source_missing:endpoint': 1}
- **Catalogue**: {'no_spl_generated': 6}

## Method (caveat)

SPL resolved via the real generators (`build_draft_preview` + active
`templates.json`), not a full `/chat` boot. Lane `none` = no SPL surfaced.
Relevance is structural (source/metric/entity); the Phase C gate adds LLM
self-critique. Numbers are a floor to beat in Phases B–D, not a grade.
