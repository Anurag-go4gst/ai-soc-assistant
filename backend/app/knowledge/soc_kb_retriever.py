from __future__ import annotations

import json
import logging
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.config import settings
from app.knowledge.rag_evidence_lineage import build_rag_approval_summary, classify_rag_evidence_origin
from app.knowledge.ambiguity_assist import assist_status, run_ambiguity_assist
from app.knowledge.hybrid import apply_rerank, reranker_configured, retrieval_stage_metadata, vector_backend
from app.knowledge.rag_collection_selector import select_rag_collections
from app.knowledge.repository import KnowledgeRepository, SocKbStore, get_knowledge_repository, load_soc_kb_store

TOKEN_RE = re.compile(r"[a-z0-9:_-]+")
TYPO_NORMALIZATIONS = {
    "faild": "failed",
    "logn": "login",
    "logns": "logins",
    "bruteforce": "brute force",
    "brute-force": "brute force",
    "srcip": "source ip",
}
EXCLUDED_KEYS = (
    "draft",
    "retired",
    "rejected",
    "superseded",
    "expired",
    "wrong_environment",
    "wrong_allowed_use",
)


def retrieve_soc_kb(
    *,
    query: str,
    selected_skill: str,
    workflow_stage: str | None = None,
    allowed_use: list[str] | None = None,
    environment: str | None = None,
    collection_ids: list[str] | None = None,
    document_types: list[str] | None = None,
    namespace: str | None = None,
    domain: str | None = None,
    max_results: int | None = None,
    store: SocKbStore | None = None,
    repository: KnowledgeRepository | None = None,
    workflow_plan: dict[str, Any] | None = None,
    required_sources: list[str] | None = None,
    human_review: dict[str, Any] | None = None,
    execution_block_reason: str | None = None,
) -> dict[str, Any]:
    if not settings.soc_kb_retrieval_enabled:
        return _empty_result("disabled", ["soc_kb_retrieval_disabled"])

    try:
        repo = repository or get_knowledge_repository()
        kb_store = store or load_soc_kb_store(repo)
        effective_allowed_use = allowed_use or _default_allowed_use(selected_skill, workflow_stage)
        selection = select_rag_collections(
            query=query,
            selected_skill=selected_skill,
            workflow_stage=workflow_stage,
            workflow_plan=workflow_plan,
            required_sources=required_sources,
            environment=environment or settings.soc_kb_environment,
            allowed_use=effective_allowed_use,
            human_review=human_review,
            execution_block_reason=execution_block_reason,
            repository=repo,
        )
        selected_collection_ids = collection_ids or selection["selected_collections"]
        return _retrieve(
            store=kb_store,
            query=query,
            selected_skill=selected_skill,
            workflow_stage=workflow_stage,
            allowed_use=effective_allowed_use,
            environment=environment or settings.soc_kb_environment,
            collection_ids=selected_collection_ids,
            document_types=document_types,
            namespace=namespace,
            domain=domain,
            max_results=max_results or settings.soc_kb_max_results,
            collection_selection=selection,
        )
    except Exception as exc:  # noqa: BLE001 - retrieval failures must not break chat.
        result = _empty_result("failed", [f"soc_kb_retrieval_failed:{type(exc).__name__}"])
        result["warnings"].append(str(exc)[:160])
        return result

def soc_kb_status_summary(store: SocKbStore | None = None) -> dict[str, Any]:
    kb_store = store or load_soc_kb_store()
    documents = kb_store.documents
    eligible = [_doc for _doc in documents if not _doc_exclusion(_doc, environment=settings.soc_kb_environment, allowed_use=None)]
    validation_warning_count = sum(len(batch.get("validation_warnings") or []) for batch in kb_store.import_batches)
    return {
        "retrieval_enabled": settings.soc_kb_retrieval_enabled,
        "repository_backend_type": settings.soc_kb_repository_backend,
        "retrieval_mode": settings.soc_kb_retrieval_mode,
        "vector_backend": settings.soc_kb_vector_backend,
        "embedding_model": settings.soc_kb_vector_model,
        "reranker_model": settings.soc_kb_reranker_model,
        "embedding_indexing_enabled": settings.soc_kb_embedding_indexing_enabled,
        "reranker_enabled": settings.soc_kb_reranker_enabled,
        "graph_expansion_enabled": settings.soc_kb_graph_expansion_enabled,
        "collections_configured_count": len(kb_store.collections),
        "documents_total_count": len(documents),
        "eligible_current_approved_document_count": len(eligible),
        "draft_count": sum(1 for doc in documents if doc.get("status") == "draft" or doc.get("approval_status") == "draft"),
        "retired_rejected_count": sum(1 for doc in documents if doc.get("status") in {"retired", "rejected"} or doc.get("approval_status") == "rejected"),
        "superseded_count": sum(1 for doc in documents if doc.get("superseded_by_doc_id") or not bool(doc.get("is_current_version", True))),
        "validation_warning_count": validation_warning_count,
        "import_batch_count": len(kb_store.import_batches),
        "environment": settings.soc_kb_environment,
        "direct_to_llm": settings.soc_kb_direct_to_llm,
        "final_synthesis_enabled": False,
        "llm_selection_enabled": settings.soc_kb_llm_selection_enabled,
        "llm_ambiguity_assist_enabled": settings.soc_kb_llm_ambiguity_assist_enabled,
        "hybrid_placeholder_enabled": settings.soc_kb_hybrid_placeholder_enabled,
        "graph_placeholder_enabled": settings.soc_kb_graph_placeholder_enabled,
        "reranker_provider": settings.soc_kb_reranker_provider,
        "reranker_configured": reranker_configured(),
        "reranker_available": settings.soc_kb_reranker_enabled and reranker_configured(),
        "ambiguity_assist": assist_status(),
        "import_prompt_available": True,
        "import_validation_enabled": True,
        "manual_edit_publish_available": True,
    }


def soc_kb_source_evidence(trace_id: str, query: str, retrieval: dict[str, Any]) -> dict[str, Any]:
    from app.evidence.source_evidence import _evidence  # Local import keeps public builder small.

    entries = retrieval.get("retrieved_entries", [])
    status = retrieval.get("retrieval_status", "no_match")
    collection_status = {
        "retrieved": "collected",
        "no_match": "no_match",
        "ambiguous": "ambiguous",
        "disabled": "skipped",
        "skipped": "skipped",
        "failed": "failed",
    }.get(str(status), "failed")
    preview_rows = [_preview_row(item) for item in entries]
    source_name = _source_name(entries)
    envelope = _evidence(
        trace_id=trace_id,
        source_type="rag",
        source_name=source_name,
        tool_name="governed_soc_kb_retrieval",
        collection_status=collection_status,
        query_or_request_summary=query[:300],
        result_count=len(entries),
        fields_returned=[],
        preview_rows=preview_rows,
        raw_result_hash=None,
        raw_result_stored=False,
        time_range=None,
        warnings=list(retrieval.get("warnings") or []),
        sensitivity_flags=sorted({flag for item in entries for flag in item.get("sensitivity_flags", [])}),
        provenance="governed_soc_kb_retrieval",
    )
    envelope["evidence_origin"] = retrieval.get("evidence_origin")
    envelope["rag_approval_summary"] = retrieval.get("rag_approval_summary")
    envelope["direct_to_llm"] = False
    _record_rag_telemetry(
        trace_id,
        collection=source_name,
        status=collection_status,
        result_count=len(entries),
        evidence_origin=retrieval.get("evidence_origin"),
    )
    return envelope


def _record_rag_telemetry(
    trace_id: str,
    *,
    collection: str | None,
    status: str,
    result_count: int,
    evidence_origin: Any,
) -> None:
    """Persist a redacted RAG-retrieval event (no chunk text) for the debug trace."""
    try:
        from app.connectors.telemetry import get_telemetry_connector

        get_telemetry_connector().record_rag_retrieval(
            trace_id,
            collection=collection,
            status=status,
            result_count=result_count,
            evidence_origin=evidence_origin if isinstance(evidence_origin, str) else None,
        )
    except Exception:  # noqa: BLE001 - telemetry must never break retrieval
        logging.getLogger("ai_soc.telemetry").warning("rag_telemetry_persist_failed", exc_info=True)


def _retrieve(
    *,
    store: SocKbStore,
    query: str,
    selected_skill: str,
    workflow_stage: str | None,
    allowed_use: list[str],
    environment: str,
    collection_ids: list[str] | None,
    document_types: list[str] | None,
    namespace: str | None,
    domain: str | None,
    max_results: int,
    collection_selection: dict[str, Any] | None = None,
) -> dict[str, Any]:
    excluded_counts = {key: 0 for key in EXCLUDED_KEYS}
    collections = _eligible_collections(store.collections, allowed_use, environment, collection_ids)
    documents_by_id: dict[str, dict[str, Any]] = {}
    for doc in store.documents:
        exclusion = _doc_exclusion(doc, environment=environment, allowed_use=allowed_use)
        if exclusion:
            excluded_counts[exclusion] += 1
            continue
        if doc.get("collection_id") not in collections:
            continue
        if document_types and doc.get("document_type") not in document_types:
            continue
        if namespace and doc.get("namespace") != namespace:
            continue
        if domain and doc.get("domain") != domain:
            continue
        documents_by_id[str(doc["doc_id"])] = doc

    query_terms = _expanded_terms(query)
    scored: list[tuple[float, dict[str, Any], list[str]]] = []
    for entry in store.entries:
        doc = documents_by_id.get(str(entry.get("doc_id")))
        if not doc:
            continue
        exclusion = _entry_exclusion(entry, selected_skill=selected_skill, allowed_use=allowed_use)
        if exclusion:
            excluded_counts[exclusion] += 1
            continue
        score, reasons, stage_scores = _score_entry(entry, doc, query_terms, query, selected_skill, allowed_use, environment)
        if score >= settings.soc_kb_min_confidence:
            scored.append((score, _retrieved_entry(entry, doc, collections[str(doc["collection_id"])], score, reasons, stage_scores), reasons))

    scored.sort(key=lambda item: (-item[0], -int(item[1]["collection_priority"]), item[1]["entry_id"]))
    eligible_candidates = [item[1] for item in scored]
    warnings: list[str] = []
    vector_candidates = vector_backend().search(query, eligible_candidates) if settings.soc_kb_retrieval_mode == "hybrid" else []
    retrieved = _graph_expand([item[1] for item in scored[:max_results]], eligible_candidates, max_results)
    retrieved = apply_rerank(query, retrieved, warnings)[:max_results]
    status = _retrieval_status(scored, retrieved)

    # Candidate-constrained LLM ambiguity assist runs only when retrieval is
    # ambiguous and the assist is explicitly enabled. It can only narrow to
    # already-eligible candidates; it can never add or invent sources.
    ambiguity_assist = run_ambiguity_assist(
        query=query,
        eligible_candidates=eligible_candidates,
        retrieval_status=status,
    )
    if ambiguity_assist:
        warnings.extend(ambiguity_assist.get("warnings") or [])
        if ambiguity_assist["ran"] and ambiguity_assist["selected_entry_ids"] and not ambiguity_assist["needs_human_review"]:
            selected_ids = set(ambiguity_assist["selected_entry_ids"])
            narrowed = [item for item in retrieved if item.get("entry_id") in selected_ids]
            if narrowed:
                retrieved = narrowed
                status = "retrieved"
                warnings.append("llm_ambiguity_assist_resolved")

    selection_warnings = list((collection_selection or {}).get("warnings") or [])
    warnings.extend(selection_warnings)
    if status == "no_match":
        warnings.append("no_approved_soc_kb_match")
    if status == "ambiguous":
        warnings.append("ambiguous_soc_kb_matches")
    if status == "ambiguous" and settings.soc_kb_llm_ambiguity_assist_enabled:
        warnings.append("llm_ambiguity_assist_limited_to_retrieved_candidates")

    payload = {
        "retrieved_entries": retrieved,
        "retrieval_status": status,
        "ambiguity_status": status if status == "ambiguous" else "clear",
        "ambiguity_assist": ambiguity_assist,
        "confidence": round(max((item[0] for item in scored), default=0.0), 3),
        "reasons": sorted({reason for _, _, reasons in scored[:max_results] for reason in reasons}),
        "warnings": warnings,
        "excluded_counts": excluded_counts,
        "collection_selection": collection_selection or {},
        "selected_collections": list((collection_selection or {}).get("selected_collections") or collections.keys()),
        "retrieval_mode": settings.soc_kb_retrieval_mode,
        "vector_backend": settings.soc_kb_vector_backend,
        "vector_candidate_count": len(vector_candidates),
        "retrieval_stage_metadata": retrieval_stage_metadata(),
        "direct_to_llm": False,
        "llm_selection_enabled": False,
        "llm_ambiguity_assist_enabled": settings.soc_kb_llm_ambiguity_assist_enabled,
        "hybrid_placeholder_enabled": settings.soc_kb_hybrid_placeholder_enabled,
        "graph_placeholder_enabled": settings.soc_kb_graph_placeholder_enabled,
    }
    payload["evidence_origin"] = classify_rag_evidence_origin(retrieval=payload)
    payload["rag_approval_summary"] = build_rag_approval_summary(payload)
    return payload


def _eligible_collections(collections: list[dict[str, Any]], allowed_use: list[str], environment: str, collection_ids: list[str] | None) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for collection in collections:
        if not collection.get("enabled", False):
            continue
        if collection_ids and collection.get("collection_id") not in collection_ids:
            continue
        if collection.get("environment") not in {"global", environment}:
            continue
        collection_uses = set(collection.get("allowed_use") or [])
        if allowed_use and not collection_uses.intersection(allowed_use):
            continue
        result[str(collection["collection_id"])] = collection
    return result


def _doc_exclusion(doc: dict[str, Any], *, environment: str, allowed_use: list[str] | None) -> str | None:
    status = str(doc.get("status") or "")
    approval = str(doc.get("approval_status") or "")
    if status == "draft" or approval == "draft":
        return "draft"
    if status == "rejected" or approval == "rejected":
        return "rejected"
    if status == "retired":
        return "retired"
    if doc.get("superseded_by_doc_id") or not bool(doc.get("is_current_version", True)):
        if not settings.soc_kb_include_superseded:
            return "superseded"
    if doc.get("environment") not in {"global", environment}:
        return "wrong_environment"
    if status not in _csv(settings.soc_kb_allowed_statuses):
        return "rejected"
    if approval not in _csv(settings.soc_kb_approved_statuses):
        return "rejected"
    if allowed_use and not set(doc.get("allowed_use") or []).intersection(allowed_use):
        return "wrong_allowed_use"
    now = datetime.now(UTC)
    effective_from = _parse_time(doc.get("effective_from"))
    effective_to = _parse_time(doc.get("effective_to"))
    if effective_from and effective_from > now:
        return "expired"
    if effective_to and effective_to < now:
        return "expired"
    return None


def _entry_exclusion(entry: dict[str, Any], *, selected_skill: str, allowed_use: list[str]) -> str | None:
    status = str(entry.get("status") or "")
    approval = str(entry.get("approval_status") or "")
    if status == "draft" or approval == "draft":
        return "draft"
    if status == "rejected" or approval == "rejected":
        return "rejected"
    if status == "retired":
        return "retired"
    if status not in _csv(settings.soc_kb_allowed_statuses):
        return "rejected"
    if approval not in _csv(settings.soc_kb_approved_statuses):
        return "rejected"
    if allowed_use and not set(entry.get("allowed_use") or []).intersection(allowed_use):
        return "wrong_allowed_use"
    skills = set(entry.get("expected_skills") or [])
    if skills and selected_skill not in skills:
        return "wrong_allowed_use"
    return None


def _score_entry(
    entry: dict[str, Any],
    doc: dict[str, Any],
    query_terms: set[str],
    raw_query: str,
    selected_skill: str,
    allowed_use: list[str],
    environment: str,
) -> tuple[float, list[str], dict[str, float]]:
    reasons: list[str] = []
    negative_terms = _terms_from_items(entry.get("negative_examples") or [])
    if len(query_terms.intersection(negative_terms)) >= 2:
        return 0.0, ["negative_example_filter"], {"negative_example_penalty": -1.0}

    score = 0.0
    field_score = 0.0
    fields = {
        "title": 0.18,
        "section_title": 0.12,
        "retrieval_hints": 0.20,
        "synonyms": 0.18,
        "positive_examples": 0.18,
        "tags": 0.12,
        "mitre_refs": 0.18,
        "splunk_indexes": 0.10,
        "sourcetypes": 0.12,
        "fields": 0.08,
        "mcp_tools": 0.10,
        "source_excerpt": 0.10,
    }
    for field, weight in fields.items():
        terms = _terms_from_items(entry.get(field))
        overlap = query_terms.intersection(terms)
        if overlap:
            contribution = min(weight, weight * len(overlap) / max(1, min(4, len(terms))))
            score += contribution
            field_score += contribution
            reasons.append(f"{field}_match")

    doc_terms = _terms_from_items([doc.get("title"), doc.get("document_type"), doc.get("namespace"), doc.get("domain"), *(doc.get("tags") or [])])
    if query_terms.intersection(doc_terms):
        score += 0.08
        field_score += 0.08
        reasons.append("document_metadata_match")

    phrase_blob = " ".join(
        str(value)
        for value in [
            entry.get("title"),
            entry.get("source_excerpt"),
            " ".join(entry.get("retrieval_hints") or []),
            " ".join(entry.get("positive_examples") or []),
        ]
    ).lower()
    normalized_query = _normalize_text(raw_query)
    for phrase in entry.get("retrieval_hints") or []:
        if _normalize_text(str(phrase)) in normalized_query:
            score += 0.15
            field_score += 0.15
            reasons.append("retrieval_hint_phrase_match")
            break
    if normalized_query and normalized_query in phrase_blob:
        score += 0.10
        field_score += 0.10
        reasons.append("exact_query_substring")
    skill_penalty = 0.0
    if entry.get("expected_skills") and selected_skill not in set(entry.get("expected_skills") or []):
        skill_penalty = -0.20
        score += skill_penalty
        reasons.append("wrong_skill_penalty")
    allowed_use_penalty = 0.0
    if allowed_use and not set(entry.get("allowed_use") or []).intersection(allowed_use):
        allowed_use_penalty = -0.25
        score += allowed_use_penalty
        reasons.append("wrong_allowed_use_penalty")
    environment_penalty = 0.0
    if doc.get("environment") not in {"global", environment}:
        environment_penalty = -1.0
        score += environment_penalty
        reasons.append("wrong_environment_exclusion")

    weighted = min(1.0, score * float(entry.get("confidence_weight") or 1.0))
    stage_scores = {
        "deterministic_schema_search": round(max(field_score, 0.0), 3),
        "keyword_search": round(len(query_terms.intersection(_terms_from_items(entry.get("source_excerpt")))) / max(len(query_terms), 1), 3),
        "negative_example_penalty": -1.0 if "negative_example_filter" in reasons else 0.0,
        "wrong_allowed_use_penalty": allowed_use_penalty,
        "wrong_skill_penalty": skill_penalty,
        "wrong_environment_penalty": environment_penalty,
        "final_candidate_selection": round(max(weighted, 0.0), 3),
    }
    return round(max(weighted, 0.0), 3), sorted(set(reasons)), stage_scores


def _retrieved_entry(entry: dict[str, Any], doc: dict[str, Any], collection: dict[str, Any], confidence: float, reasons: list[str], stage_scores: dict[str, float]) -> dict[str, Any]:
    sensitivity = str(entry.get("sensitivity") or doc.get("sensitivity") or "internal")
    return {
        "collection_id": entry.get("collection_id"),
        "collection_name": collection.get("name"),
        "collection_priority": collection.get("priority", 0),
        "doc_id": doc.get("doc_id"),
        "doc_title": doc.get("title"),
        "doc_version": doc.get("version"),
        "canonical_doc_id": doc.get("canonical_doc_id") or doc.get("doc_id"),
        "is_current_version": bool(doc.get("is_current_version", True)),
        "document_type": doc.get("document_type"),
        "namespace": doc.get("namespace"),
        "domain": doc.get("domain"),
        "environment": doc.get("environment"),
        "approval_status": doc.get("approval_status"),
        "status": doc.get("status"),
        "entry_id": entry.get("entry_id"),
        "entry_title": entry.get("title"),
        "entry_type": entry.get("entry_type"),
        "allowed_use": entry.get("allowed_use") or [],
        "source_excerpt": entry.get("source_excerpt"),
        "source_refs": entry.get("source_refs") or [],
        "citation": entry.get("citation"),
        "answer_constraints": entry.get("answer_constraints") or [],
        "prohibited_conclusions": entry.get("prohibited_conclusions") or [],
        "mitre_refs": entry.get("mitre_refs") or [],
        "splunk_indexes": entry.get("splunk_indexes") or [],
        "sourcetypes": entry.get("sourcetypes") or [],
        "fields": entry.get("fields") or [],
        "mcp_tools": entry.get("mcp_tools") or [],
        "reviewer_role": entry.get("reviewer_role"),
        "recommended_actions": entry.get("recommended_actions") or [],
        "confidence": confidence,
        "reasons": reasons,
        "retrieval_mode": settings.soc_kb_retrieval_mode,
        "retrieval_stage_scores": stage_scores,
        "ambiguity_status": "candidate",
        "graph_expanded": False,
        "reranked": False,
        "validation_status": "runtime_eligible",
        "import_batch_id": entry.get("import_batch_id") or doc.get("import_batch_id"),
        "sensitivity_flags": [f"sensitivity:{sensitivity}"] if sensitivity in {"confidential", "restricted"} else [],
        "graph_node_id": entry.get("graph_node_id"),
        "graph_edges": entry.get("graph_edges") or [],
        "retrieval_backend": entry.get("retrieval_backend") or "deterministic",
    }


def _retrieval_status(scored: list[tuple[float, dict[str, Any], list[str]]], retrieved: list[dict[str, Any]]) -> str:
    if not retrieved:
        return "no_match"
    if len(scored) > 1:
        top = scored[0][0]
        near_top = [item for item in scored[:5] if top - item[0] <= 0.08]
        doc_types = {item[1]["document_type"] for item in near_top}
        domains = {item[1].get("domain") for item in near_top}
        if len(near_top) > 1 and (len(doc_types) > 1 or len(domains) > 1):
            return "ambiguous"
    return "retrieved"


def _graph_expand(seed: list[dict[str, Any]], eligible_candidates: list[dict[str, Any]], max_results: int) -> list[dict[str, Any]]:
    if not settings.soc_kb_graph_expansion_enabled:
        return seed
    selected = list(seed)
    selected_ids = {item.get("entry_id") for item in selected}
    linked_ids = {
        str(edge.get("to", "")).replace("entry:", "")
        for item in seed
        for edge in item.get("graph_edges") or []
        if isinstance(edge, dict) and str(edge.get("to", "")).startswith("entry:")
    }
    for candidate in eligible_candidates:
        if len(selected) >= max_results:
            break
        if candidate.get("entry_id") in linked_ids and candidate.get("entry_id") not in selected_ids:
            selected.append({**candidate, "graph_expanded": True})
            selected_ids.add(candidate.get("entry_id"))
    return selected


def _preview_row(item: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "collection_id",
        "doc_id",
        "doc_title",
        "title",
        "doc_version",
        "canonical_doc_id",
        "is_current_version",
        "entry_id",
        "entry_title",
        "entry_type",
        "document_type",
        "environment",
        "approval_status",
        "status",
        "allowed_use",
        "source_excerpt",
        "source_refs",
        "citation",
        "confidence",
        "reasons",
        "retrieval_mode",
        "retrieval_stage_scores",
        "ambiguity_status",
        "graph_expanded",
        "reranked",
        "validation_status",
        "import_batch_id",
        "answer_constraints",
        "prohibited_conclusions",
        "mitre_refs",
        "mcp_tools",
        "reviewer_role",
        "recommended_actions",
    )
    return {key: item.get(key) for key in keys}


def _source_name(entries: list[dict[str, Any]]) -> str:
    if not entries:
        return "governed_soc_kb"
    doc_titles = []
    for entry in entries:
        title = str(entry.get("doc_title") or entry.get("collection_name") or "governed_soc_kb")
        if title not in doc_titles:
            doc_titles.append(title)
    return "; ".join(doc_titles[:2])


def _default_allowed_use(selected_skill: str, workflow_stage: str | None) -> list[str]:
    uses = ["synthesis_context"]
    if selected_skill in {"attack_discovery", "alert_summary"}:
        uses.extend(["hil_guidance", "mitre_grounding", "environment_grounding"])
    if selected_skill == "spl_generation" or workflow_stage == "spl_generation":
        uses.extend(["spl_generation", "validation", "tool_selection"])
    if selected_skill == "knowledge_recall":
        uses.extend(["hil_guidance", "mitre_grounding"])
    return sorted(set(uses))


def _expanded_terms(query: str) -> set[str]:
    normalized = _normalize_text(query)
    terms = set(TOKEN_RE.findall(normalized))
    for original, replacement in TYPO_NORMALIZATIONS.items():
        if original in normalized:
            terms.update(TOKEN_RE.findall(replacement))
    if {"failed", "login"}.issubset(terms) or {"failed", "logins"}.issubset(terms):
        terms.update({"auth", "authentication", "failure", "failures"})
    if {"source", "ip"}.issubset(terms):
        terms.update({"src", "remote", "address"})
    if "lockout" in terms:
        terms.add("locked")
    return terms


def _terms_from_items(value: Any) -> set[str]:
    if value is None:
        return set()
    if isinstance(value, list):
        text = " ".join(str(item) for item in value)
    else:
        text = str(value)
    return set(TOKEN_RE.findall(_normalize_text(text)))


def _normalize_text(value: str) -> str:
    text = value.lower()
    for original, replacement in TYPO_NORMALIZATIONS.items():
        text = text.replace(original, replacement)
    return text


def _load_json(path_value: str) -> list[dict[str, Any]]:
    path = Path(path_value)
    if not path.is_absolute():
        path = Path.cwd() / path
    if not path.exists():
        repo_root = Path(__file__).resolve().parents[3]
        path = repo_root / path_value
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, list):
        raise ValueError(f"{path} must contain a JSON list")
    return [item for item in payload if isinstance(item, dict)]


def _csv(value: str) -> set[str]:
    return {item.strip() for item in value.split(",") if item.strip()}


def _parse_time(value: Any) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def _empty_result(status: str, reasons: list[str]) -> dict[str, Any]:
    payload = {
        "retrieved_entries": [],
        "retrieval_status": status,
        "ambiguity_status": "clear",
        "ambiguity_assist": None,
        "confidence": 0.0,
        "reasons": reasons,
        "warnings": [],
        "excluded_counts": {key: 0 for key in EXCLUDED_KEYS},
        "selected_collections": [],
        "collection_selection": {},
        "retrieval_mode": settings.soc_kb_retrieval_mode,
        "vector_backend": settings.soc_kb_vector_backend,
        "retrieval_stage_metadata": retrieval_stage_metadata(),
        "direct_to_llm": False,
        "llm_selection_enabled": False,
        "llm_ambiguity_assist_enabled": settings.soc_kb_llm_ambiguity_assist_enabled,
        "hybrid_placeholder_enabled": settings.soc_kb_hybrid_placeholder_enabled,
        "graph_placeholder_enabled": settings.soc_kb_graph_placeholder_enabled,
    }
    payload["evidence_origin"] = classify_rag_evidence_origin(retrieval=payload)
    payload["rag_approval_summary"] = build_rag_approval_summary(payload)
    return payload
