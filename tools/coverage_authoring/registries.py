"""Closed registry snapshots for Q4A authoring (read-only)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.coverage.coverage_loader import (
    known_detection_refs,
    known_evidence_contract_refs,
    known_lookup_refs,
    known_template_refs,
    resolve_evidence_contract_ref,
)
from app.coverage.coverage_models import CoverageReadiness
from app.detections.detection_binder import bind_detection
from app.detections.detection_registry import load_detection_registry
from app.detections.detection_binder import _resolve_registry_path as detection_registry_path
from app.detections.detection_models import VettingStatus
from app.routing.route_plan_models import RouteStatus, runtime_skill_values
from app.spl.template_registry import load_spl_templates

REPO_ROOT = Path(__file__).resolve().parents[2]
TAXONOMY_PATH = REPO_ROOT / "docs" / "soc_question_taxonomy_stage3k_q0.md"
DRAFTS_DIR = Path(__file__).resolve().parent / "drafts"
MANIFEST_PATH = REPO_ROOT / "backend" / "app" / "coverage" / "pattern_coverage_v1.json"

READINESS_LABELS = {item.value for item in CoverageReadiness}
ROUTE_STATUS_VALUES = {status.value for status in RouteStatus}


@dataclass(frozen=True)
class RegistrySnapshot:
    runtime_skills: frozenset[str]
    template_refs: frozenset[str]
    production_template_refs: frozenset[str]
    lookup_refs: frozenset[str]
    detection_refs_all: frozenset[str]
    detection_refs_bindable: frozenset[str]
    detection_families: frozenset[str]
    evidence_contract_refs: frozenset[str]
    readiness_labels: frozenset[str]
    route_status_values: frozenset[str]


def load_registry_snapshot() -> RegistrySnapshot:
    templates = load_spl_templates()
    production = {
        template.template_id
        for template in templates
        if not template.sample_only and template.status == "active" and template.spl_text
    }
    registry = load_detection_registry(detection_registry_path(None))
    families = frozenset(
        record.family for record in registry.document.detections
    )
    return RegistrySnapshot(
        runtime_skills=frozenset(runtime_skill_values()),
        template_refs=frozenset(known_template_refs()),
        production_template_refs=frozenset(production),
        lookup_refs=frozenset(known_lookup_refs()),
        detection_refs_all=frozenset(known_detection_refs(bindable_only=False)),
        detection_refs_bindable=frozenset(known_detection_refs(bindable_only=True)),
        detection_families=families,
        evidence_contract_refs=frozenset(known_evidence_contract_refs()),
        readiness_labels=frozenset(READINESS_LABELS),
        route_status_values=frozenset(ROUTE_STATUS_VALUES),
    )


def bind_family(family: str) -> tuple[str | None, str | None]:
    """Return (detection_ref, evidence_contract_ref) when bindable."""
    result = bind_detection(family)
    if not result.bound or not result.detection_ref:
        return None, None
    registry = load_detection_registry(detection_registry_path(None))
    record = registry.by_ref.get(result.detection_ref)
    contract = record.evidence_output_contract_ref if record else None
    return result.detection_ref, contract or None


def evidence_contract_exists(ref: str) -> bool:
    return resolve_evidence_contract_ref(ref)
