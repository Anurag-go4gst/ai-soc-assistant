from __future__ import annotations

import json
import urllib.request
from typing import Any, Protocol

from app.config import settings

SUPPORTED_RERANKER_PROVIDERS = {"mock", "openai_compatible", "local_http"}


RETRIEVAL_STAGES = [
    "collection_selection",
    "metadata_filter",
    "deterministic_schema_search",
    "keyword_search",
    "dense_vector_search",
    "sparse_vector_search",
    "graph_expansion",
    "rerank",
    "policy_filter",
    "ambiguity_check",
    "final_candidate_selection",
]


class VectorBackend(Protocol):
    def search(self, query: str, candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
        ...


class NoopVectorBackend:
    backend_type = "none"

    def search(self, query: str, candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return []


class MockVectorBackend:
    backend_type = "mock"

    def search(self, query: str, candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
        # Mock vector search is safety-bounded to already eligible candidates.
        return [{**candidate, "vector_score": candidate.get("confidence", 0.0)} for candidate in candidates]


class Reranker(Protocol):
    def rerank(self, query: str, candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
        ...


class NoopReranker:
    backend_type = "mock"

    def rerank(self, query: str, candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
        # Mock reranker reorders eligible candidates by existing confidence only.
        return sorted(candidates, key=lambda item: -float(item.get("confidence") or 0.0))


class HttpReranker:
    """Real reranker over an OpenAI-compatible / local HTTP rerank endpoint.

    It reorders only the eligible candidates it is given; it never adds, fetches,
    or invents candidates. Any transport/parse failure raises so the caller can
    fall back to deterministic order.
    """

    def __init__(self, *, backend_type: str, base_url: str, api_key: str, model: str, timeout: int) -> None:
        self.backend_type = backend_type
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    def rerank(self, query: str, candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not self.base_url:
            raise ValueError("reranker_base_url_not_configured")
        documents = [str(item.get("source_excerpt") or item.get("entry_title") or "") for item in candidates]
        body = json.dumps({"model": self.model, "query": query, "documents": documents}).encode("utf-8")
        request = urllib.request.Request(f"{self.base_url}/rerank", data=body, method="POST")
        request.add_header("Content-Type", "application/json")
        if self.api_key:
            request.add_header("Authorization", f"Bearer {self.api_key}")
        with urllib.request.urlopen(request, timeout=self.timeout) as response:  # noqa: S310 - admin-configured endpoint only.
            payload = json.loads(response.read().decode("utf-8"))
        results = payload.get("results")
        if not isinstance(results, list):
            raise ValueError("reranker_response_missing_results")
        # Map returned document indexes back onto the original candidates; ignore
        # any index outside range so the reranker can only reorder, never add.
        order = [int(item.get("index")) for item in results if isinstance(item, dict) and item.get("index") is not None]
        reordered = [candidates[idx] for idx in order if 0 <= idx < len(candidates)]
        seen = {id(item) for item in reordered}
        reordered.extend(item for item in candidates if id(item) not in seen)
        return reordered


def vector_backend() -> VectorBackend:
    if settings.soc_kb_vector_backend == "mock":
        return MockVectorBackend()
    return NoopVectorBackend()


def reranker() -> Reranker:
    provider = settings.soc_kb_reranker_provider
    if provider in {"openai_compatible", "local_http"} and settings.soc_kb_reranker_base_url:
        return HttpReranker(
            backend_type=provider,
            base_url=settings.soc_kb_reranker_base_url,
            api_key=settings.soc_kb_reranker_api_key,
            model=settings.soc_kb_reranker_model,
            timeout=settings.soc_kb_reranker_timeout_seconds,
        )
    return NoopReranker()


def reranker_configured() -> bool:
    provider = settings.soc_kb_reranker_provider
    if provider == "mock":
        return True
    return provider in {"openai_compatible", "local_http"} and bool(settings.soc_kb_reranker_base_url.strip())


def apply_rerank(query: str, candidates: list[dict[str, Any]], warnings: list[str] | None = None) -> list[dict[str, Any]]:
    if not settings.soc_kb_reranker_enabled:
        return candidates
    candidate_ids = {item.get("entry_id") for item in candidates}
    try:
        ranked = reranker().rerank(query, candidates)
    except Exception as exc:  # noqa: BLE001 - reranker failure must fall back, never break retrieval.
        if warnings is not None:
            warnings.append(f"reranker_failed_fallback_deterministic:{type(exc).__name__}")
        return candidates
    # Rerankers may reorder only; they cannot add candidates or bypass policy.
    safe_ranked = [item for item in ranked if item.get("entry_id") in candidate_ids]
    dropped = len(ranked) - len(safe_ranked)
    if dropped > 0 and warnings is not None:
        warnings.append("reranker_dropped_unknown_candidates")
    top_n = settings.soc_kb_reranker_top_n if settings.soc_kb_reranker_top_n > 0 else len(safe_ranked)
    safe_ranked = safe_ranked[:top_n]
    for index, item in enumerate(safe_ranked):
        item["reranked"] = True
        item["reranker_score"] = round(1.0 - (index * 0.001), 3)
    return safe_ranked


def retrieval_stage_metadata() -> dict[str, Any]:
    return {
        "retrieval_stages": RETRIEVAL_STAGES,
        "retrieval_mode": settings.soc_kb_retrieval_mode,
        "vector_backend": settings.soc_kb_vector_backend,
        "embedding_model": settings.soc_kb_vector_model,
        "reranker_enabled": settings.soc_kb_reranker_enabled,
        "reranker_provider": settings.soc_kb_reranker_provider,
        "reranker_model": settings.soc_kb_reranker_model,
        "graph_expansion_enabled": settings.soc_kb_graph_expansion_enabled,
        "embedding_indexing_enabled": settings.soc_kb_embedding_indexing_enabled,
    }
