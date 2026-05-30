"""Closed registry snapshot for promotion gate evaluation (read-only)."""

from __future__ import annotations

from dataclasses import dataclass

from app.coverage.coverage_loader import (
    known_detection_refs,
    known_evidence_contract_refs,
    known_lookup_refs,
    known_template_refs,
    resolve_evidence_contract_ref,
)
from app.coverage.coverage_models import CoverageReadiness
from app.routing.route_plan_models import RouteStatus, runtime_skill_values
from app.spl.template_registry import load_spl_templates


@dataclass(frozen=True)
class PromotionRegistrySnapshot:
    runtime_skills: frozenset[str]
    template_refs: frozenset[str]
    production_template_refs: frozenset[str]
    lookup_refs: frozenset[str]
    detection_refs_all: frozenset[str]
    detection_refs_bindable: frozenset[str]
    evidence_contract_refs: frozenset[str]
    readiness_labels: frozenset[str]
    route_status_values: frozenset[str]


def load_promotion_registry_snapshot() -> PromotionRegistrySnapshot:
    templates = load_spl_templates()
    production = {
        template.template_id
        for template in templates
        if not template.sample_only
    }
    return PromotionRegistrySnapshot(
        runtime_skills=frozenset(runtime_skill_values()),
        template_refs=frozenset(known_template_refs()),
        production_template_refs=frozenset(production),
        lookup_refs=frozenset(known_lookup_refs()),
        detection_refs_all=frozenset(known_detection_refs(bindable_only=False)),
        detection_refs_bindable=frozenset(known_detection_refs(bindable_only=True)),
        evidence_contract_refs=frozenset(known_evidence_contract_refs()),
        readiness_labels=frozenset(item.value for item in CoverageReadiness),
        route_status_values=frozenset(status.value for status in RouteStatus),
    )


def evidence_contract_exists(ref: str, snapshot: PromotionRegistrySnapshot) -> bool:
    if ref in snapshot.evidence_contract_refs:
        return True
    return resolve_evidence_contract_ref(ref)
