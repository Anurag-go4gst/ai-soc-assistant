---
name: soc-kb-ingest
description: Ingest a SOC knowledge doc (SOP, playbook, runbook, detection note) into the governed SOC-KB RAG so it flows through SourceEvidence/StructuredContext — never directly to the LLM. Use when the user says "add a KB doc", "ingest a playbook", "add to SOC-KB", "import knowledge", or /soc-kb-ingest.
---

# soc-kb-ingest

Add governed knowledge to the SOC-KB the safe way. The SOC-KB is RAG retrieval that flows **only** into `SourceEvidence`/`StructuredContext`; there is **no direct RAG→LLM path** and drafts never affect runtime until human-reviewed and published.

## Governance contract (hard rules)
From `app/knowledge/soc_kb_intake_template.py` → `soc_kb_intake_contract()`:
- `runtime_use=False`, `direct_rag_to_llm=False`, `drafts_affect_runtime=False`, `human_review_required=True`.
- Document must match `SUPPORTED_DOCUMENT_TYPES` and `SUPPORTED_ALLOWED_USE` (`app/knowledge/validation.py`).
- **Provenance = clean tags only**, never URLs or `SKILL.md` paths in content. Use tags like `source:github_skill_intake` / `source:internal_curated`. Raw URLs trip the answer composer's provenance-marker guard. Full provenance lives in `docs/skills/*`.
- Playbooks/SOPs live in the SOC-KB's own RAG collection, **not** Confluence.

## Two ingestion paths

### A. Curated skill-enrichment knowledge (deterministic, idempotent)
For SOP content driven from `backend/app/use_cases/content_enrichment.json`:
```bash
cd /var/www/ai-soc-assistant
PYTHONPATH=backend:. python3 scripts/import_skill_knowledge_to_kb.py          # write fixtures
PYTHONPATH=backend:. python3 scripts/import_skill_knowledge_to_kb.py --check  # drift gate (exit 1 on drift)
```
Regenerates `skill-enrich-*` rows wholesale into `soc_kb_documents.json` / `soc_kb_entries.json`. `--check` is part of the staleness gates.

### B. New free-form doc via the governed import API
Behind `/api/knowledge/import/*`. Follow the intake contract — validate before save, save draft, then publish (human review between):
- `GET /api/knowledge/import/contract` — machine-readable rules
- `GET /api/knowledge/import/prompt-template` — extraction skeleton
- `POST /api/knowledge/import/validate` — schema/allowed-use check (no persist)
- `POST /api/knowledge/import/save-draft` — draft only (no runtime effect)
- `POST /api/knowledge/import/publish` — promote after review
Build the template with `build_soc_kb_intake_template(collection_id=, document_type=)`. Pick the collection via `app/knowledge/rag_collection_selector.py`. Retrieval served by `app/knowledge/soc_kb_retriever.py` (hybrid keyword+vector: `app/rag/retriever_keyword.py`, `retriever_vector.py`).

## Verify
```bash
cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_soc_kb_retriever.py app/tests/test_soc_kb_stage3g1.py app/tests/test_soc_kb_stage3g.py -q
```
Then the full gate (fixtures are committed artifacts): `./scripts/run_stage3_governance_regression.sh`.

## Done when
Doc validates against the contract, fixtures regenerated (`--check` clean for path A), SOC-KB retriever tests pass, governance regression PASS. Commit fixtures + `content_enrichment.json` together.
