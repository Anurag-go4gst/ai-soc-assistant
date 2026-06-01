# P4 — SOC RAG intake and stub evidence

**Status:** Implemented on branch `stage/p4-rag-intake-stub`.

## Goal

Prove governed SOC-KB content flows **only** through `SourceEvidence` → `StructuredContext` with explicit approval metadata and deck labels (`stub_rag` vs `live_rag`). No direct RAG-to-LLM path.

## Deliverables

| ID | Item | Location |
|----|------|----------|
| P4-9 | Intake template + approval contract | `app/knowledge/soc_kb_intake_template.py`, `GET /api/knowledge/intake/contract` |
| P4 | Evidence origin + approval summary | `app/knowledge/rag_evidence_lineage.py` |
| P4 | Retrieval envelope fields | `retrieve_soc_kb()` → `evidence_origin`, `rag_approval_summary` |
| P4 | Chat labels | `PlaceholderResponse.evidence_origin`, `answer_readiness` |
| P4 | Structured context | `rag_approval_summary`, `evidence_origin_labels` |

## Env (system-check / stub)

```text
RAG_MODE=mock
SOC_KB_RETRIEVAL_ENABLED=true
SOC_KB_REPOSITORY_BACKEND=json
```

With fixture JSON backend, live `/chat` sets `evidence_origin=stub_rag` and `answer_readiness=system_check_only`.

## Boundaries

- Draft/unapproved documents never enter runtime retrieval (`_doc_exclusion` / `_entry_exclusion`).
- `direct_to_llm` stays `false` on retrieval and RAG evidence envelopes.
- Production `live_rag` requires non-fixture repository backend and `RAG_MODE` not `mock` (COE corpus still required for real answers).

## Verification

```bash
cd backend
PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_p4_rag_intake_stub.py -q
./scripts/run_stage3_governance_regression.sh
```
