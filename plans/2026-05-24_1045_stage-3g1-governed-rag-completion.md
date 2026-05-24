# Stage 3G.1 — Governed RAG Completion

**Status:** Done
**Date:** 2026-05-24

Close remaining practical RAG gaps short of real PDF/vector indexing:
LLM import-assist workflow, optional real reranker connector, optional
candidate-constrained LLM ambiguity assist, status surfaces, UI, tests.

## Hard constraints (must NOT add)
final LLM synthesis · direct RAG-to-LLM answer path · uncontrolled retrieval ·
PDF parser · real vector indexing · DB-backed KB repo · Splunk telemetry write ·
new MCP execution behavior.

## Backend

1. **config.py** — add:
   `soc_kb_reranker_provider=mock`, `soc_kb_reranker_base_url=""`,
   `soc_kb_reranker_api_key=""`, `soc_kb_reranker_timeout_seconds=10`,
   `soc_kb_reranker_top_n=5`, `soc_kb_llm_ambiguity_provider=""`,
   `soc_kb_llm_ambiguity_max_candidates=5`. All safe defaults; assist+reranker
   stay disabled by default via existing `_enabled` flags.

2. **knowledge/hybrid.py** — reranker provider:
   - `reranker()` picks Mock | HttpReranker(openai_compatible|local_http) from settings. Keep `reranker` patchable (existing test patches `hybrid.reranker`).
   - `apply_rerank(query, candidates, warnings=None)` — keep 2-arg compat;
     enforce subset (cannot add); try/except → deterministic fallback + warn
     `reranker_failed_fallback_deterministic`; cap top_n.
   - Real reranker reorders eligible only; never includes draft/unapproved.

3. **knowledge/ambiguity_assist.py** (new) — `run_ambiguity_assist(query, eligible, status)`:
   - returns None when disabled or status != ambiguous.
   - resolve `soc_kb_llm_ambiguity_provider` through `load_llm_registry_status().providers`;
     if not available → None + warn `ambiguity_assist_provider_unavailable`.
   - bounded candidate-only payload (id/title/excerpt), max N.
   - client wrapper injectable for tests; mock selects deterministically.
   - validate output: selected_entry_ids ⊆ eligible ids; drop unknown + warn
     `ambiguity_assist_ignored_unknown_entry_id`.
   - returns `{selected_entry_ids, ambiguity_reason, needs_human_review, confidence}`.
   - cannot invent entries, access drafts, or override policy.

4. **knowledge/import_prompt.py** (new) — `build_extraction_prompt(collection_id, document_type, environment)`:
   JSON-only, do-not-invent rules, governed schema (collections/documents/entries,
   source_refs, source_excerpt, allowed_use, risk_level, status=draft|ready_for_review,
   approval_status=draft, version, checksum placeholder, test_cases for high-risk,
   answer_constraints, positive/negative_examples). null/omit missing fields,
   preserve excerpts, mark uncertain for human review.

5. **knowledge/soc_kb_retriever.py** — after status compute, if ambiguous+enabled
   run assist over eligible candidates; narrow to selected & set retrieved when
   resolved + not needs_human_review; else stay ambiguous (HIL). Add
   `ambiguity_assist` block + status fields. Extend `soc_kb_status_summary` with
   reranker/ambiguity/import/synthesis fields.

6. **api/routes_knowledge.py** —
   - `GET /knowledge/import/prompt-template` (query: collection_id, document_type, environment)
   - `POST /knowledge/import/save-draft` (validate→save batch as draft only, no publish)
   - `POST /knowledge/import/publish` — extend to accept `{doc_ids:[...]}` to publish
     already-saved drafts (re-validate first); keep payload fast-path.

7. **api/routes_settings.py** — rag block: real `llm_ambiguity_assist_enabled`,
   reranker {enabled, provider, model, configured, available}, ambiguity_assist
   {enabled, provider, configured, available}, import_prompt_available,
   import_validation_enabled, manual_edit_publish_available, direct_to_llm=false,
   final_synthesis_enabled=false. No secrets (booleans only).

## Frontend
- client.ts: getImportPromptTemplate, saveKnowledgeDraft, publishKnowledgeImport.
- KnowledgePage: copy/download extraction prompt; paste extracted JSON; validate;
  show errors/warnings; manual edit textarea; save-draft; publish (enabled when valid);
  retrieval test stays; show reranker/ambiguity assist status.

## Tests (17 scenarios)
prompt template generated · prompt says JSON-only + do-not-invent · uploaded JSON
saved draft-only · draft not retrievable · validation catches missing source_refs
high-risk · publish makes entry retrievable · manual edit changes validation ·
reranker disabled default · reranker cannot add · reranker failure safe fallback ·
ambiguity assist disabled default · assist sees eligible only · assist cannot invent
ids · direct_to_llm false · no final synthesis · no Splunk telemetry write path ·
frontend build + backend tests + harness 6/6 default + TELEMETRY_MODE=none 6/6.

## Verify
backend pytest · frontend build · harness default · harness TELEMETRY_MODE=none ·
git diff --check · wiki_search support-buddy RAG cross-check for final report.
