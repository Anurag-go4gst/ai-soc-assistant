"""A governed SOC-KB retrieval record behind a procedure answer.

The record carries what the governed retriever produces at chunk level — the rewritten query, the
index it searched (dense + BM25), the candidate funnel, what the approval policy excluded before
reranking, and the kept chunks with their scores — plus the answer built from it: the source
documents with their approval dates, a short opening, the procedure steps grouped by phase, and the
escalation rule. Every step cites the chunks it rests on by their section reference.

``check_rag_record`` fails loudly when the record is internally inconsistent: a screen whose ranks,
scores or citations do not add up would undermine the whole answer.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, NoReturn


@dataclass(frozen=True)
class RagChunk:
    """One kept chunk. ``ref`` is how the answer cites it, e.g. ``3.2``, ``PH-02`` or ``Rule 3``."""

    ref: str
    chunk_id: str
    doc_id: str
    section: str
    tokens: int
    dense_score: float  # cosine similarity of the query and chunk embeddings
    dense_rank: int
    bm25_score: float
    bm25_rank: int
    rerank_score: float
    excerpt: str
    used_for: str
    used: bool = True


@dataclass(frozen=True)
class RagDocument:
    doc_id: str
    title: str
    version: str
    approved_on: str  # e.g. "12 Mar 2026"
    approval_status: str = "approved"


@dataclass(frozen=True)
class RagExclusion:
    """Chunks the approval policy removed before reranking, grouped by reason."""

    reason: str  # draft | rejected | superseded | expired | retired | wrong_environment | wrong_allowed_use
    count: int
    doc_id: str
    doc_version: str
    detail: str


@dataclass(frozen=True)
class RagIndex:
    embedding_model: str
    embedding_dims: int
    sparse_method: str
    reranker_model: str
    documents: int
    chunks: int
    chunking: str


@dataclass(frozen=True)
class RagFunnel:
    dense_candidates: int
    sparse_candidates: int
    fused: int
    fusion: str
    reranked: int
    rerank_threshold: float


@dataclass(frozen=True)
class ProcedureStep:
    """One line of the answer: what the procedure requires, who does it, and where it says so."""

    phase: str
    text: str
    owner: str
    cites: tuple[str, ...]
    condition: str = ""  # e.g. "only if a file was downloaded or ran"
    action_id: str = ""  # the proposed action that carries this step out, if any
    short: str = ""  # a few words for the done / pending summary


@dataclass(frozen=True)
class RagRecord:
    title: str
    opening: str
    query: str  # the retrieval query the question was rewritten into
    collections: tuple[str, ...]
    documents: tuple[RagDocument, ...]  # the first one is the primary source
    index: RagIndex
    funnel: RagFunnel
    exclusions: tuple[RagExclusion, ...]
    chunks: tuple[RagChunk, ...]
    steps: tuple[ProcedureStep, ...]
    escalation: ProcedureStep
    gaps: tuple[str, ...] = ()
    governance: tuple[str, ...] = ()


def answer_lines(record: RagRecord) -> tuple[str, ...]:
    """The answer as plain lines (steps, then escalation) — what the incident ticket records."""
    lines = [f"{step.text} ({step.condition})" if step.condition else step.text for step in record.steps]
    return (*lines, record.escalation.text)


def _cited_refs(record: RagRecord) -> list[str]:
    refs: list[str] = []
    for step in (*record.steps, record.escalation):
        for ref in step.cites:
            if ref not in refs:
                refs.append(ref)
    return refs


def check_rag_record(record: RagRecord, *, points: tuple[str, ...], owner: str) -> None:
    """Raise ``ValueError`` when the retrieval record does not add up."""

    def fail(reason: str) -> NoReturn:
        raise ValueError(f"{owner}: rag record {reason}")

    if not record.chunks:
        fail("has no chunks")
    if not record.documents:
        fail("names no source documents")
    refs = [chunk.ref for chunk in record.chunks]
    if len(refs) != len(set(refs)):
        fail("repeats a chunk reference")
    chunk_ids = [chunk.chunk_id for chunk in record.chunks]
    if len(chunk_ids) != len(set(chunk_ids)):
        fail("repeats a chunk id")
    rerank = [chunk.rerank_score for chunk in record.chunks]
    if rerank != sorted(rerank, reverse=True):
        fail("chunks are not ordered by rerank score")
    for field in ("dense_rank", "bm25_rank"):
        ranks = [getattr(chunk, field) for chunk in record.chunks]
        if len(ranks) != len(set(ranks)) or min(ranks) < 1:
            fail(f"has duplicate or invalid {field}")
    below = [chunk.ref for chunk in record.chunks if chunk.rerank_score < record.funnel.rerank_threshold]
    if below:
        fail(f"keeps chunks below the rerank threshold: {below}")

    documents = {document.doc_id: document for document in record.documents}
    unknown_docs = sorted({chunk.doc_id for chunk in record.chunks} - set(documents))
    if unknown_docs:
        fail(f"has chunks from documents it does not list: {unknown_docs}")
    excluded_versions = {(item.doc_id, item.doc_version) for item in record.exclusions}
    for document in record.documents:
        if (document.doc_id, document.version) in excluded_versions:
            fail(f"answers from an excluded document version: {document.doc_id} v{document.version}")

    by_ref = {chunk.ref: chunk for chunk in record.chunks}
    for step in (*record.steps, record.escalation):
        if not step.cites:
            fail(f"step has no citation: {step.text!r}")
        for ref in step.cites:
            chunk = by_ref.get(ref)
            if chunk is None:
                fail(f"cites unknown chunk {ref}")
            if not chunk.used:
                fail(f"cites chunk {ref}, which is marked not used")
    uncited_used = [chunk.ref for chunk in record.chunks if chunk.used and chunk.ref not in set(_cited_refs(record))]
    if uncited_used:
        fail(f"marks chunks used that no step cites: {uncited_used}")

    funnel = record.funnel
    excluded_total = sum(item.count for item in record.exclusions)
    if funnel.fused > funnel.dense_candidates + funnel.sparse_candidates:
        fail("fuses more candidates than were retrieved")
    if funnel.fused < len(record.chunks) + excluded_total:
        fail("keeps and excludes more chunks than were fused")
    if funnel.reranked < len(record.chunks):
        fail("keeps more chunks than were reranked")

    if tuple(points) != answer_lines(record):
        fail("answer lines differ from the scenario's points")


def _ref_payload(record: RagRecord, ref: str) -> dict[str, str]:
    chunk = next(item for item in record.chunks if item.ref == ref)
    return {"ref": ref, "doc_id": chunk.doc_id, "section": chunk.section, "excerpt": chunk.excerpt}


# Action status → (tone, label). "Requested" is not "done": another team still has to act.
_ACTION_STATUS: dict[str, tuple[str, str]] = {
    "EXECUTED": ("done", "Done"),
    "VERIFIED": ("done", "Done"),
    "AWAITING_REPLY": ("done", "Sent · awaiting reply"),
    "REQUESTED": ("requested", "Requested"),
    "SCHEDULED": ("requested", "Scheduled"),
    "FAILED": ("not_done", "Not done"),
    "NOT_SENT": ("not_done", "Not sent"),
}


def _step_status(step: ProcedureStep, progress: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Where a procedure step stands once the approved actions have run."""
    row = progress.get(step.action_id) if step.action_id else None
    if row is not None:
        if str(row.get("status")) not in _ACTION_STATUS:
            # Not approved (or not run): no ticket or email exists to show.
            return {"status": "pending", "status_label": "Not started"}
        tone, label = _ACTION_STATUS[str(row.get("status"))]
        return {
            "status": tone,
            "status_label": label,
            "ticket": row.get("ticket"),
            "email": row.get("email"),
            "email_delivery": row.get("email_delivery"),
        }
    if step.condition:
        return {"status": "conditional", "status_label": "Only if needed"}
    return {"status": "pending", "status_label": "Pending"}


def _step_payload(
    record: RagRecord, step: ProcedureStep, progress: dict[str, dict[str, Any]] | None = None
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "text": step.text,
        "owner": step.owner,
        "condition": step.condition,
        "refs": [_ref_payload(record, ref) for ref in step.cites],
    }
    if progress is not None:
        payload.update(_step_status(step, progress))
    return payload


def _progress_summary(record: RagRecord, progress: dict[str, dict[str, Any]]) -> dict[str, list[str]]:
    summary: dict[str, list[str]] = {"done": [], "requested": [], "pending": []}
    for step in record.steps:
        tone = _step_status(step, progress)["status"]
        label = step.short or step.text
        if tone == "conditional":
            label = f"{label} ({step.condition})"
        summary["done" if tone == "done" else "requested" if tone == "requested" else "pending"].append(label)
    return summary


def build_procedure_answer(
    record: RagRecord,
    *,
    assessment: dict[str, Any] | None,
    progress: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """The answer screen: opening, source documents, phased steps, escalation rule.

    ``progress`` (action id → action status and records) is passed once the approved actions have
    run; each step then carries its status, and the answer ends with what is done and what is not.
    """
    phases: list[dict[str, Any]] = []
    for step in record.steps:
        if not phases or phases[-1]["name"] != step.phase:
            phases.append({"name": step.phase, "steps": []})
        phases[-1]["steps"].append(_step_payload(record, step, progress))
    return {
        "title": record.title,
        "opening": record.opening,
        "assessment": assessment,
        "documents": [
            {
                "doc_id": document.doc_id,
                "title": document.title,
                "version": document.version,
                "approved_on": document.approved_on,
            }
            for document in record.documents
        ],
        "phases": phases,
        "escalation": _step_payload(record, record.escalation),
        "retrieval_summary": (
            f"{len(record.chunks)} chunks · hybrid search · top match {record.chunks[0].rerank_score:.2f}"
        ),
        "progress_summary": _progress_summary(record, progress) if progress is not None else None,
    }


def build_rag_trace(record: RagRecord) -> dict[str, Any]:
    """The retrieval panel ("How this was found"): index, funnel, exclusions, kept chunks."""
    excluded_total = sum(item.count for item in record.exclusions)
    documents = {document.doc_id: document for document in record.documents}
    return {
        "question": record.query,
        "collections": list(record.collections),
        "retrieval_mode": "hybrid",
        "top_confidence": record.chunks[0].rerank_score,
        "direct_to_llm": False,
        "excluded": [
            {"reason": item.reason, "count": item.count, "detail": item.detail} for item in record.exclusions
        ],
        "excluded_total": excluded_total,
        "index": {
            "embedding_model": record.index.embedding_model,
            "embedding_dims": record.index.embedding_dims,
            "sparse_method": record.index.sparse_method,
            "reranker_model": record.index.reranker_model,
            "documents": record.index.documents,
            "chunks": record.index.chunks,
            "chunking": record.index.chunking,
        },
        "funnel": {
            "dense_candidates": record.funnel.dense_candidates,
            "sparse_candidates": record.funnel.sparse_candidates,
            "fused": record.funnel.fused,
            "fusion": record.funnel.fusion,
            "excluded": excluded_total,
            "reranked": record.funnel.reranked,
            "rerank_threshold": record.funnel.rerank_threshold,
            "kept": len(record.chunks),
            "cited": len(_cited_refs(record)),
        },
        "passages": [
            {
                "entry_id": chunk.chunk_id,
                "label": chunk.ref,
                "citation": f"{chunk.doc_id} {chunk.section}",
                "doc_title": documents[chunk.doc_id].title,
                "doc_version": documents[chunk.doc_id].version,
                "approval_status": documents[chunk.doc_id].approval_status,
                "confidence": chunk.rerank_score,
                "excerpt": chunk.excerpt,
                "used": chunk.used,
                "used_for": chunk.used_for,
                "chunk_id": chunk.chunk_id,
                "section": chunk.section,
                "tokens": chunk.tokens,
                "scores": {
                    "dense": chunk.dense_score,
                    "dense_rank": chunk.dense_rank,
                    "bm25": chunk.bm25_score,
                    "bm25_rank": chunk.bm25_rank,
                    "rerank": chunk.rerank_score,
                },
            }
            for chunk in record.chunks
        ],
        # The answer itself is on the procedure screen; this panel only shows how it was found.
        "answer": {"headline": "", "sentences": [], "gaps": list(record.gaps)},
        "governance": list(record.governance),
    }
