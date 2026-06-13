# SPL Relevance Baseline (Phase A)

Deterministic structural relevance — does generated SPL match the asked
data source, metric/aggregation, and entity? No LLM, no app behavior change.

| Corpus | Relevant | Total | % | Lanes |
|--------|----------|-------|---|-------|
| 105 canonical | 97 | 102 | 95.1 | {'draft': 102} |
| Catalogue (spl-expected) | 12 | 31 | 38.7 | {'template': 10, 'none': 19, 'draft': 2} |

Catalogue row classes: {'spl_expected': 31, 'justified_no_spl': 11, 'deferred': 4} — `justified_no_spl`
(analyst-workflow / knowledge skills) and `deferred` (OT "later") are
excluded from the coverage denominator; they are correctly handled without SPL.

> Corpora reported separately by design — 105 (pattern_type keyspace) and
> catalogue (use_case_id keyspace) overlap; a combined /151 would double-count.

## Top mismatch reasons

- **105**: {'entity_missing': 3, 'data_source_missing:auth': 1, 'data_source_missing:endpoint': 1}
- **Catalogue**: {'no_spl_generated': 19}

## Method (caveat)

SPL resolved via the real generators (`build_draft_preview` + active
`templates.json`), not a full `/chat` boot. Lane `none` = no SPL surfaced.
Relevance is structural (source/metric/entity); the Phase C gate adds LLM
self-critique. Numbers are a floor to beat in Phases B–D, not a grade.
