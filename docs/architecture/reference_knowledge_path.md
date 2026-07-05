# Reference Knowledge Path

Canonical path for offline taxonomy/reference datasets:

1. Add a `ReferenceDataset` entry in `app/planner/reference_registry.py`.
2. Bind it to a resolver that returns `ReferenceFact` rows with `reference_id`, `name`, `description`, `tactics` when relevant, `source_dataset`, and `citation`.
3. Add probe rows for positive taxonomy lookups and negative live-data asks.
4. Run the reference probe audit and targeted tests.

Runtime flow:

`question -> answer_shape(reference_taxonomy) -> intent_family(reference_knowledge) -> request_mode(reference_knowledge) -> rag_early -> reference_finalize -> StructuredContext.reference_facts + SourceEvidence(reference_dataset) -> governed answer card`

Onboarding rules:

- Registry/manual resolver output is authoritative for names, tactics, and citations.
- Unresolved IDs must produce an honest not-found fact; do not fabricate rows.
- Taxonomy lookup never claims local exploitation, exposure, alert mapping, severity, or live activity.
- Live-data phrasing such as "search logs", "seen on our network", or "last week" must route away from `reference_taxonomy`.
- Adding a dataset must not require a new route, floor, request mode, dispatch stage, or feature flag.

Anti-patterns:

- Per-dataset routing branches such as `if dataset == cwe`.
- New answer shapes for each taxonomy.
- Direct RAG/LLM citations that bypass resolver output.
- Treating a taxonomy match as evidence observed in the local environment.
