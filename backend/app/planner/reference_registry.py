"""Reference-knowledge dataset registry.

Canonical registry for offline taxonomy/reference datasets (ATT&CK, ATLAS, CVE).
It declares patterns and resolver bindings only; routing and answer shaping consume
this later without per-dataset branches.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Protocol

from app.cve.snapshot_store import CveSnapshotStore
from app.knowledge.mapping_exports import atlas_technique_enrichment
from app.threat.attack_data_resolver import technique_resolver_from_settings

AI_THREAT_KEYWORDS: tuple[str, ...] = (
    "llm",
    "large language model",
    "prompt injection",
    "jailbreak",
    "model theft",
    "model extraction",
    "data poisoning",
    "training data",
    "rag poisoning",
    "embedding",
    "ai model",
    "ml model",
    "machine learning model",
    "inference api",
    "model endpoint",
    "mcp server",
    "mcp tool",
    "agent",
    "ai assistant",
    "foundation model",
    "adversarial example",
    "model evasion",
)


@dataclass(frozen=True)
class ReferenceFact:
    reference_id: str
    dataset_id: str
    name: str = ""
    description: str = ""
    tactics: list[str] = field(default_factory=list)
    citation: str = ""
    provenance_tier: str = "offline_reference"
    raw: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "reference_id": self.reference_id,
            "source_dataset": self.dataset_id,
            "dataset_id": self.dataset_id,
            "name": self.name,
            "description": self.description,
            "tactics": list(self.tactics),
            "citation": self.citation,
            "provenance_tier": self.provenance_tier,
            "lookup_status": "reference_lookup",
            "raw": dict(self.raw),
        }
        if self.reference_id.upper().startswith(("T", "AML.T")):
            payload["technique_id"] = self.reference_id
        return payload


class ReferenceResolver(Protocol):
    def resolve_ids(self, ids: list[str]) -> list[ReferenceFact]:
        ...

    def search_domain(self, keywords: list[str], *, limit: int = 10) -> list[ReferenceFact]:
        ...


@dataclass(frozen=True)
class ReferenceDataset:
    dataset_id: str
    id_patterns: tuple[str, ...]
    keyword_domains: tuple[str, ...]
    resolver: ReferenceResolver
    provenance_tier: str
    answerable_without_alert: bool = True

    def matches_id(self, reference_id: str) -> bool:
        return any(re.fullmatch(pattern, reference_id, flags=re.IGNORECASE) for pattern in self.id_patterns)

    def matches_keywords(self, text: str) -> bool:
        lowered = (text or "").lower()
        return any(keyword.lower() in lowered for keyword in self.keyword_domains)


class TechniqueReferenceResolver:
    def __init__(self, *, dataset_id: str, id_prefix: str, domain: str) -> None:
        self.dataset_id = dataset_id
        self.id_prefix = id_prefix
        self.domain = domain
        self._resolver = technique_resolver_from_settings()

    def resolve_ids(self, ids: list[str]) -> list[ReferenceFact]:
        facts: list[ReferenceFact] = []
        for reference_id in ids:
            rid = reference_id.strip()
            if not rid or not rid.upper().startswith(self.id_prefix.upper()):
                continue
            detail = self._resolver.detail(rid)
            if not detail:
                continue
            facts.append(_technique_fact(self.dataset_id, rid, detail))
        return facts

    def search_domain(self, keywords: list[str], *, limit: int = 10) -> list[ReferenceFact]:
        if self.dataset_id != "mitre_atlas":
            return []
        lowered = " ".join(keywords).lower()
        if not any(keyword in lowered for keyword in AI_THREAT_KEYWORDS):
            return []
        from app.knowledge.mapping_exports import build_atlas_coverage_gap

        coverage = build_atlas_coverage_gap()
        if not str(coverage.get("atlas_source_status") or "").startswith("onboarded"):
            return []
        rows = coverage.get("top_techniques_by_case_study_frequency") or []
        ids = [str(row.get("technique_id") or "") for row in rows[:limit] if row.get("technique_id")]
        facts_by_id = {fact.reference_id: fact for fact in self.resolve_ids(ids)}
        facts: list[ReferenceFact] = []
        for row in rows[:limit]:
            rid = str(row.get("technique_id") or "")
            fact = facts_by_id.get(rid)
            if fact is not None:
                facts.append(fact)
                continue
            facts.append(
                ReferenceFact(
                    reference_id=rid,
                    dataset_id=self.dataset_id,
                    name=str(row.get("name") or ""),
                    tactics=[str(item) for item in row.get("tactics") or []],
                    citation="MITRE ATLAS local coverage artifact",
                    raw=_atlas_enrichment_raw(self.dataset_id, rid, dict(row)),
                )
            )
        return facts


class CveReferenceResolver:
    def __init__(self, *, package_dir: str | None = None, stale_after_days: int | None = None) -> None:
        if package_dir is None or stale_after_days is None:
            from app.config import settings

            package_dir = package_dir if package_dir is not None else (settings.ai_soc_cve_snapshot_dir or None)
            stale_after_days = (
                stale_after_days
                if stale_after_days is not None
                else settings.ai_soc_cve_snapshot_stale_after_days
            )
        self._store = CveSnapshotStore(package_dir=package_dir, stale_after_days=int(stale_after_days))

    def resolve_ids(self, ids: list[str]) -> list[ReferenceFact]:
        facts: list[ReferenceFact] = []
        for reference_id in ids:
            rid = reference_id.strip().upper()
            if not rid.startswith("CVE-"):
                continue
            row = self._store.lookup_cve(rid)
            if not row:
                continue
            severity = str(row.get("severity") or "").strip()
            products = [str(item) for item in row.get("products") or []]
            name = rid if not severity else f"{rid} ({severity})"
            facts.append(
                ReferenceFact(
                    reference_id=rid,
                    dataset_id="cve",
                    name=name,
                    description=", ".join(products),
                    citation="operator-vendored CVE snapshot",
                    raw=dict(row),
                )
            )
        return facts

    def search_domain(self, keywords: list[str], *, limit: int = 10) -> list[ReferenceFact]:
        return []


class ReferenceRegistry:
    def __init__(self, datasets: list[ReferenceDataset]) -> None:
        self.datasets = list(datasets)

    def by_id(self, dataset_id: str) -> ReferenceDataset | None:
        for dataset in self.datasets:
            if dataset.dataset_id == dataset_id:
                return dataset
        return None

    def match_id(self, reference_id: str) -> ReferenceDataset | None:
        for dataset in self.datasets:
            if dataset.matches_id(reference_id):
                return dataset
        return None

    def extract_ids(self, text: str) -> dict[str, list[str]]:
        out: dict[str, list[str]] = {dataset.dataset_id: [] for dataset in self.datasets}
        for dataset in self.datasets:
            seen: set[str] = set()
            for pattern in dataset.id_patterns:
                for match in re.finditer(pattern, text or "", flags=re.IGNORECASE):
                    rid = match.group(0).upper() if dataset.dataset_id == "cve" else match.group(0)
                    if rid not in seen:
                        out[dataset.dataset_id].append(rid)
                        seen.add(rid)
        return {key: value for key, value in out.items() if value}

    def search_keywords(self, text: str, *, limit: int = 10) -> dict[str, list[ReferenceFact]]:
        words = [text]
        out: dict[str, list[ReferenceFact]] = {}
        for dataset in self.datasets:
            if dataset.matches_keywords(text):
                facts = dataset.resolver.search_domain(words, limit=limit)
                if facts:
                    out[dataset.dataset_id] = facts
        return out


def load_reference_registry() -> ReferenceRegistry:
    return ReferenceRegistry(
        [
            ReferenceDataset(
                dataset_id="mitre_attack_enterprise",
                id_patterns=(r"(?<!AML\.)T\d{4}(?:\.\d{3})?",),
                keyword_domains=("mitre", "att&ck", "attack technique", "enterprise attack"),
                resolver=TechniqueReferenceResolver(
                    dataset_id="mitre_attack_enterprise",
                    id_prefix="T",
                    domain="enterprise-attack",
                ),
                provenance_tier="operator_vendored_attack_export",
            ),
            ReferenceDataset(
                dataset_id="mitre_atlas",
                id_patterns=(r"AML\.T\d{4}",),
                keyword_domains=AI_THREAT_KEYWORDS + ("atlas", "ai threat", "aml technique"),
                resolver=TechniqueReferenceResolver(dataset_id="mitre_atlas", id_prefix="AML.", domain="atlas"),
                provenance_tier="operator_vendored_atlas",
            ),
            ReferenceDataset(
                dataset_id="cve",
                id_patterns=(r"CVE-\d{4}-\d{4,7}",),
                keyword_domains=("cve", "vulnerability", "kev", "affected"),
                resolver=CveReferenceResolver(),
                provenance_tier="operator_vendored_cve_snapshot",
            ),
        ]
    )


def _atlas_enrichment_raw(dataset_id: str, reference_id: str, base_raw: dict[str, Any]) -> dict[str, Any]:
    if dataset_id != "mitre_atlas":
        return dict(base_raw)
    enrichment = atlas_technique_enrichment(reference_id)
    return {**dict(base_raw), "atlas_enrichment": enrichment}


def _technique_fact(dataset_id: str, reference_id: str, detail: dict[str, Any]) -> ReferenceFact:
    tactics_raw = detail.get("tactics")
    if isinstance(tactics_raw, str):
        tactics = [item.strip() for item in tactics_raw.split(",") if item.strip()]
    else:
        tactics = [str(item) for item in tactics_raw or []]
    citation = str(detail.get("url") or "")
    if not citation:
        citation = "MITRE ATLAS local YAML" if dataset_id == "mitre_atlas" else "MITRE ATT&CK local export"
    return ReferenceFact(
        reference_id=reference_id,
        dataset_id=dataset_id,
        name=str(detail.get("name") or ""),
        description=str(detail.get("description") or ""),
        tactics=tactics,
        citation=citation,
        raw=_atlas_enrichment_raw(dataset_id, reference_id, dict(detail)),
    )
