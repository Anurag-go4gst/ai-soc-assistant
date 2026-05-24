from __future__ import annotations

import hashlib
import json
from abc import ABC, abstractmethod
from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.config import settings


@dataclass(frozen=True)
class SocKbStore:
    collections: list[dict[str, Any]]
    documents: list[dict[str, Any]]
    entries: list[dict[str, Any]]
    import_batches: list[dict[str, Any]]


class KnowledgeRepository(ABC):
    backend_type = "abstract"

    @abstractmethod
    def list_collections(self) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def list_documents(self) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def list_entries(self) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def list_import_batches(self) -> list[dict[str, Any]]:
        raise NotImplementedError

    def get_document(self, doc_id: str, version: str | None = None) -> dict[str, Any] | None:
        for doc in self.list_documents():
            if doc.get("doc_id") == doc_id and (version is None or doc.get("version") == version):
                return deepcopy(doc)
        return None

    def get_current_document(self, canonical_doc_id: str) -> dict[str, Any] | None:
        for doc in self.list_documents():
            if doc.get("canonical_doc_id") == canonical_doc_id and bool(doc.get("is_current_version", True)):
                return deepcopy(doc)
        return None

    def get_published_entries(self, filters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        filters = filters or {}
        doc_ids = {doc["doc_id"] for doc in self.list_documents() if _runtime_eligible_doc(doc, filters)}
        return [entry for entry in self.list_entries() if entry.get("doc_id") in doc_ids and _runtime_eligible_entry(entry, filters)]

    @abstractmethod
    def save_import_batch(self, batch: dict[str, Any], documents: list[dict[str, Any]], entries: list[dict[str, Any]]) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def publish_document(self, doc_id: str, approved_by: str = "admin") -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def retire_document(self, doc_id: str, retired_by: str = "admin") -> dict[str, Any]:
        raise NotImplementedError


class JsonKnowledgeRepository(KnowledgeRepository):
    backend_type = "json"

    def __init__(
        self,
        *,
        collections_path: str | None = None,
        documents_path: str | None = None,
        entries_path: str | None = None,
        import_batches_path: str | None = None,
    ) -> None:
        self.collections_path = _resolve_path(collections_path or settings.soc_kb_collections_path)
        self.documents_path = _resolve_path(documents_path or settings.soc_kb_documents_path)
        self.entries_path = _resolve_path(entries_path or settings.soc_kb_entries_path)
        self.import_batches_path = _resolve_path(import_batches_path or settings.soc_kb_import_batches_path)

    def list_collections(self) -> list[dict[str, Any]]:
        return _load_json(self.collections_path)

    def list_documents(self) -> list[dict[str, Any]]:
        return _load_json(self.documents_path)

    def list_entries(self) -> list[dict[str, Any]]:
        return _load_json(self.entries_path)

    def list_import_batches(self) -> list[dict[str, Any]]:
        if not self.import_batches_path.exists():
            return []
        return _load_json(self.import_batches_path)

    def load_store(self) -> SocKbStore:
        return SocKbStore(
            collections=self.list_collections(),
            documents=self.list_documents(),
            entries=self.list_entries(),
            import_batches=self.list_import_batches(),
        )

    def save_import_batch(self, batch: dict[str, Any], documents: list[dict[str, Any]], entries: list[dict[str, Any]]) -> dict[str, Any]:
        now = datetime.now(UTC).isoformat()
        normalized_batch = {
            "import_batch_id": batch.get("import_batch_id") or f"import-{hashlib.sha256(now.encode()).hexdigest()[:12]}",
            "source_file_name": batch.get("source_file_name") or "pasted_knowledge.json",
            "source_type": batch.get("source_type") or "json",
            "target_collection_id": batch.get("target_collection_id") or (documents[0].get("collection_id") if documents else None),
            "environment": batch.get("environment") or settings.soc_kb_environment,
            "imported_by": batch.get("imported_by") or "admin",
            "imported_at": batch.get("imported_at") or now,
            "status": batch.get("status") or "ready_for_review",
            "validation_errors": list(batch.get("validation_errors") or []),
            "validation_warnings": list(batch.get("validation_warnings") or []),
            "document_count": len(documents),
            "entry_count": len(entries),
            "checksum_sha256": batch.get("checksum_sha256") or _payload_checksum({"documents": documents, "entries": entries}),
            "generated_by": batch.get("generated_by") or "manual_json",
            "source_document_ref": batch.get("source_document_ref"),
        }
        prepared_docs = [_prepare_import_document(doc, normalized_batch) for doc in documents]
        prepared_entries = [_prepare_import_entry(entry, normalized_batch) for entry in entries]
        self._append_unique(self.documents_path, prepared_docs, "doc_id")
        self._append_unique(self.entries_path, prepared_entries, "entry_id")
        self._append_unique(self.import_batches_path, [normalized_batch], "import_batch_id")
        return deepcopy(normalized_batch)

    def publish_document(self, doc_id: str, approved_by: str = "admin") -> dict[str, Any]:
        documents = self.list_documents()
        entries = self.list_entries()
        target = next((doc for doc in documents if doc.get("doc_id") == doc_id), None)
        if not target:
            raise ValueError("document_not_found")
        if _expired(target):
            raise ValueError("expired_documents_cannot_be_published")
        canonical = target.get("canonical_doc_id") or doc_id
        now = datetime.now(UTC).isoformat()
        for doc in documents:
            if doc is target:
                continue
            if doc.get("canonical_doc_id") == canonical and bool(doc.get("is_current_version", True)):
                doc["is_current_version"] = False
                doc["superseded_by_doc_id"] = doc_id
                doc["lifecycle_stage"] = "retired" if doc.get("status") == "retired" else "published"
        target.update(
            {
                "status": "published",
                "approval_status": target.get("approval_status") if target.get("approval_status") != "draft" else "coe_reviewed",
                "lifecycle_stage": "published",
                "is_current_version": True,
                "approved_by": approved_by,
                "approved_at": target.get("approved_at") or now,
                "published_at": now,
                "superseded_by_doc_id": None,
            }
        )
        for entry in entries:
            if entry.get("doc_id") == doc_id:
                entry["status"] = "published"
                if entry.get("approval_status") == "draft":
                    entry["approval_status"] = target["approval_status"]
        _write_json(self.documents_path, documents)
        _write_json(self.entries_path, entries)
        return deepcopy(target)

    def retire_document(self, doc_id: str, retired_by: str = "admin") -> dict[str, Any]:
        documents = self.list_documents()
        entries = self.list_entries()
        target = next((doc for doc in documents if doc.get("doc_id") == doc_id), None)
        if not target:
            raise ValueError("document_not_found")
        now = datetime.now(UTC).isoformat()
        target.update({"status": "retired", "lifecycle_stage": "retired", "is_current_version": False, "retired_at": now, "retired_by": retired_by})
        for entry in entries:
            if entry.get("doc_id") == doc_id:
                entry["status"] = "retired"
        _write_json(self.documents_path, documents)
        _write_json(self.entries_path, entries)
        return deepcopy(target)

    def _append_unique(self, path: Path, items: list[dict[str, Any]], key: str) -> None:
        existing = _load_json(path) if path.exists() else []
        ids = {item.get(key) for item in existing}
        existing.extend(item for item in items if item.get(key) not in ids)
        _write_json(path, existing)


def get_knowledge_repository() -> JsonKnowledgeRepository:
    return JsonKnowledgeRepository()


def load_soc_kb_store(repository: KnowledgeRepository | None = None) -> SocKbStore:
    repo = repository or get_knowledge_repository()
    if isinstance(repo, JsonKnowledgeRepository):
        return repo.load_store()
    return SocKbStore(
        collections=repo.list_collections(),
        documents=repo.list_documents(),
        entries=repo.list_entries(),
        import_batches=repo.list_import_batches(),
    )


def _runtime_eligible_doc(doc: dict[str, Any], filters: dict[str, Any]) -> bool:
    environment = filters.get("environment") or settings.soc_kb_environment
    allowed_use = set(filters.get("allowed_use") or [])
    if not bool(doc.get("is_current_version", True)):
        return False
    if doc.get("superseded_by_doc_id"):
        return False
    if doc.get("environment") not in {"global", environment}:
        return False
    if doc.get("status") not in _csv(settings.soc_kb_allowed_statuses):
        return False
    if doc.get("approval_status") not in _csv(settings.soc_kb_approved_statuses):
        return False
    if _expired(doc):
        return False
    return not allowed_use or bool(set(doc.get("allowed_use") or []).intersection(allowed_use))


def _runtime_eligible_entry(entry: dict[str, Any], filters: dict[str, Any]) -> bool:
    allowed_use = set(filters.get("allowed_use") or [])
    if entry.get("status") not in _csv(settings.soc_kb_allowed_statuses):
        return False
    if entry.get("approval_status") not in _csv(settings.soc_kb_approved_statuses):
        return False
    return not allowed_use or bool(set(entry.get("allowed_use") or []).intersection(allowed_use))


def _prepare_import_document(doc: dict[str, Any], batch: dict[str, Any]) -> dict[str, Any]:
    item = deepcopy(doc)
    item.setdefault("status", "draft")
    item.setdefault("approval_status", "draft")
    item.setdefault("lifecycle_stage", "reviewed" if batch.get("status") == "ready_for_review" else "imported")
    item.setdefault("environment", batch.get("environment") or settings.soc_kb_environment)
    item.setdefault("import_batch_id", batch["import_batch_id"])
    item.setdefault("is_current_version", False)
    item.setdefault("canonical_doc_id", item.get("doc_id"))
    item.setdefault("created_at", datetime.now(UTC).isoformat())
    item.setdefault("updated_at", datetime.now(UTC).isoformat())
    item.setdefault("retrieval_backend", "deterministic")
    return item


def _prepare_import_entry(entry: dict[str, Any], batch: dict[str, Any]) -> dict[str, Any]:
    item = deepcopy(entry)
    item.setdefault("status", "draft")
    item.setdefault("approval_status", "draft")
    item.setdefault("import_batch_id", batch["import_batch_id"])
    item.setdefault("retrieval_backend", "deterministic")
    return item


def _resolve_path(path_value: str) -> Path:
    path = Path(path_value)
    if path.is_absolute():
        return path
    candidate = Path.cwd() / path
    if candidate.exists():
        return candidate
    return Path(__file__).resolve().parents[3] / path_value


def _load_json(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, list):
        raise ValueError(f"{path} must contain a JSON list")
    return [item for item in payload if isinstance(item, dict)]


def _write_json(path: Path, payload: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=False)
        handle.write("\n")


def _payload_checksum(payload: Any) -> str:
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _expired(doc: dict[str, Any]) -> bool:
    now = datetime.now(UTC)
    effective_to = doc.get("effective_to")
    if not effective_to:
        return False
    return datetime.fromisoformat(str(effective_to).replace("Z", "+00:00")) < now


def _csv(value: str) -> set[str]:
    return {item.strip() for item in value.split(",") if item.strip()}
