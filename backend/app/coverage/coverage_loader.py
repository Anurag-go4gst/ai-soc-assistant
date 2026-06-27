"""Load and query the Stage 3K-Q4 pattern coverage manifest."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from app.coverage.coverage_models import PatternCoverageEntry, PatternCoverageManifest
from app.detections.detection_binder import _resolve_registry_path as _detection_registry_path
from app.detections.detection_registry import load_detection_registry
from app.detections.detection_models import VettingStatus
from app.intel.ioc_lookup import BLOCK_CANNOT_ROUTE_LOOKUP_STALE, BLOCK_LOOKUP_STALE
from app.intel.ioc_registry import load_ioc_registry
from app.intel.ioc_lookup import _DEFAULT_IOC_REGISTRY_PATH
from app.spl.template_registry import load_spl_templates

_MANIFEST_PATH = Path(__file__).resolve().parent / "pattern_coverage_v1.json"
_MANIFEST_CACHE: PatternCoverageManifest | None = None


def load_pattern_coverage_manifest(
    path: str | Path | None = None,
    *,
    reload: bool = False,
) -> PatternCoverageManifest:
    global _MANIFEST_CACHE
    resolved = Path(path) if path else _MANIFEST_PATH
    key = str(resolved.resolve())
    if not reload and _MANIFEST_CACHE is not None and str(_MANIFEST_PATH.resolve()) == key:
        return _MANIFEST_CACHE

    raw = json.loads(resolved.read_text(encoding="utf-8"))
    manifest = PatternCoverageManifest.model_validate(raw)
    if path is None and not reload:
        _MANIFEST_CACHE = manifest
    return manifest


def clear_pattern_coverage_cache() -> None:
    global _MANIFEST_CACHE
    _MANIFEST_CACHE = None


def validate_manifest_payload(payload: dict[str, Any]) -> list[str]:
    try:
        PatternCoverageManifest.model_validate(payload)
        return []
    except ValidationError as exc:
        return [f"{'.'.join(str(part) for part in error.get('loc', ()))}: {error.get('msg')}" for error in exc.errors()]


def list_coverage(*, reload: bool = False) -> list[PatternCoverageEntry]:
    return list(load_pattern_coverage_manifest(reload=reload).entries)


def coverage_for_question(question_ref: str, *, reload: bool = False) -> list[PatternCoverageEntry]:
    return [entry for entry in list_coverage(reload=reload) if entry.question_ref == question_ref]


def coverage_for_skill(skill: str, *, reload: bool = False) -> list[PatternCoverageEntry]:
    return [entry for entry in list_coverage(reload=reload) if entry.primary_skill == skill]


def coverage_for_id(coverage_id: str, *, reload: bool = False) -> PatternCoverageEntry | None:
    for entry in list_coverage(reload=reload):
        if entry.coverage_id == coverage_id:
            return entry
    return None


def known_template_refs() -> set[str]:
    return {template.template_id for template in load_spl_templates()}


def known_lookup_refs() -> set[str]:
    registry = load_ioc_registry(_DEFAULT_IOC_REGISTRY_PATH)
    names = {record.lookup_name for record in registry.document.iocs}
    names.update(source.lookup_name for source in registry.document.sources)
    return names


def known_detection_refs(*, bindable_only: bool = False) -> set[str]:
    registry = load_detection_registry(_detection_registry_path(None))
    if bindable_only:
        return {
            record.detection_ref
            for record in registry.document.detections
            if record.vetting_status == VettingStatus.APPROVED
        }
    return set(registry.by_ref.keys())


def known_evidence_contract_refs() -> set[str]:
    refs: set[str] = set()
    for record in load_detection_registry(_detection_registry_path(None)).document.detections:
        if record.evidence_output_contract_ref:
            refs.add(record.evidence_output_contract_ref)
    for template in load_spl_templates():
        contract = template.evidence_output_contract
        if contract is None:
            continue
        refs.add(_template_evidence_contract_ref(template.template_id, contract.model_dump()))
    refs.update(_STATIC_EVIDENCE_CONTRACT_REFS)
    return refs


def resolve_evidence_contract_ref(ref: str) -> bool:
    return ref in known_evidence_contract_refs()


def entry_declares_dependency_missing(entry: PatternCoverageEntry) -> bool:
    return entry.readiness.value == "dependency_missing"


def _template_evidence_contract_ref(template_id: str, contract: dict[str, Any]) -> str:
    entity = contract.get("entity_field", "entity")
    metric = contract.get("metric_field", "metric")
    output_type = contract.get("output_type", "ranked_entities")
    return f"{output_type}:{entity}:{metric}"


_STATIC_EVIDENCE_CONTRACT_REFS = frozenset(
    {
        "raw_search_table:host:failed_logins",
        "multi_signal:dns_and_network_anomaly_flags",
        "ranked_entities:host:malicious_contact_count",
        "ranked_entities:host:connection_count",
        "ranked_entities:host:malicious_domain_contact_count",
        "raw_events:notable_id:timeline",
    }
)
