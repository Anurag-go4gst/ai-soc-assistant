"""Read-only knowledge_recall DetailTool."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from app.chat.contracts.knowledge_recall import (
    KnowledgeCitation,
    KnowledgeFact,
    KnowledgeRecallRequest,
    KnowledgeRecallResult,
)


def run_knowledge_recall(request: KnowledgeRecallRequest) -> KnowledgeRecallResult:
    """Governed read-only knowledge retrieval (reference registry first)."""
    call_id = f"kr:{uuid.uuid4().hex[:12]}"
    now = datetime.now(UTC).isoformat()
    refs = list(request.reference_ids)
    limitations: list[str] = []
    errors: list[str] = []
    facts: list[KnowledgeFact] = []
    citations: list[KnowledgeCitation] = []

    if not request.query.strip() and not refs:
        return KnowledgeRecallResult(
            status="empty",
            limitations=["No query or reference identifiers supplied."],
            tool_call_id=call_id,
            retrieved_at=now,
        )

    for ref in refs[: request.max_results]:
        source = "CVE" if ref.startswith("CVE-") else "MITRE" if ref.startswith("T") else "ATLAS"
        facts.append(
            KnowledgeFact(
                fact_id=f"fact:{ref}",
                text=f"Reference lookup for {ref} (governed registry; no live environment claim).",
                source=source,  # type: ignore[arg-type]
                reference_id=ref,
            )
        )
        citations.append(
            KnowledgeCitation(source=source, reference_id=ref, title=ref)  # type: ignore[arg-type]
        )

    if not facts and request.query.strip():
        limitations.append("No reference identifiers resolved; semantic retrieval not executed in this stage.")
        return KnowledgeRecallResult(
            status="partial",
            facts=[],
            references=refs,
            citations=[],
            source_names=["reference_registry"],
            limitations=limitations,
            tool_call_id=call_id,
            retrieved_at=now,
            confidence=0.4,
        )

    return KnowledgeRecallResult(
        status="success" if facts else "empty",
        facts=facts,
        references=refs,
        citations=citations,
        source_names=["reference_registry"],
        source_versions={"reference_registry": "governed_v1"},
        retrieved_at=now,
        confidence=0.85 if facts else 0.0,
        limitations=limitations,
        errors=errors,
        tool_call_id=call_id,
    )


def knowledge_recall_from_state(
    query: str,
    *,
    reference_ids: list[str] | None = None,
    sources: list[str] | None = None,
) -> KnowledgeRecallResult:
    return run_knowledge_recall(
        KnowledgeRecallRequest(
            query=query,
            reference_ids=list(reference_ids or []),
            sources=list(sources or []),  # type: ignore[arg-type]
        )
    )
