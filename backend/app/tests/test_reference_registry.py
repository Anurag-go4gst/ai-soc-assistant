from __future__ import annotations

from pathlib import Path

from app.planner.reference_registry import CveReferenceResolver, load_reference_registry


FIXTURE_CVE_DIR = Path(__file__).resolve().parent / "fixtures" / "cve"


def test_reference_registry_loads_three_canonical_datasets() -> None:
    registry = load_reference_registry()
    assert {dataset.dataset_id for dataset in registry.datasets} == {
        "mitre_attack_enterprise",
        "mitre_atlas",
        "cve",
    }
    assert all(dataset.answerable_without_alert for dataset in registry.datasets)


def test_id_pattern_match_dispatches_to_dataset() -> None:
    registry = load_reference_registry()
    assert registry.match_id("T1110.003").dataset_id == "mitre_attack_enterprise"
    assert registry.match_id("AML.T0051").dataset_id == "mitre_atlas"
    assert registry.match_id("CVE-2024-3400").dataset_id == "cve"
    assert registry.match_id("XYZ-123") is None


def test_extract_ids_groups_by_dataset() -> None:
    registry = load_reference_registry()
    grouped = registry.extract_ids("Compare AML.T0051, T1110.003, and CVE-2024-3400.")
    assert grouped["mitre_atlas"] == ["AML.T0051"]
    assert grouped["mitre_attack_enterprise"] == ["T1110.003"]
    assert grouped["cve"] == ["CVE-2024-3400"]


def test_atlas_id_resolves_offline_with_name() -> None:
    registry = load_reference_registry()
    atlas = registry.by_id("mitre_atlas")
    facts = atlas.resolver.resolve_ids(["AML.T0051"])
    assert facts
    fact = facts[0]
    assert fact.reference_id == "AML.T0051"
    assert fact.dataset_id == "mitre_atlas"
    assert fact.name
    assert fact.citation


def test_atlas_keyword_search_returns_ranked_facts() -> None:
    registry = load_reference_registry()
    facts_by_dataset = registry.search_keywords("prompt injection against an LLM agent using MCP tools")
    facts = facts_by_dataset.get("mitre_atlas") or []
    assert facts
    assert all(fact.reference_id.startswith("AML.T") for fact in facts)


def test_cve_resolver_uses_snapshot_store_fixture() -> None:
    resolver = CveReferenceResolver(package_dir=str(FIXTURE_CVE_DIR), stale_after_days=30)
    facts = resolver.resolve_ids(["CVE-2024-0001"])
    assert facts
    assert facts[0].reference_id == "CVE-2024-0001"
    assert facts[0].dataset_id == "cve"
    assert "HIGH" in facts[0].name


def test_unknown_ids_fail_closed_without_fabrication() -> None:
    registry = load_reference_registry()
    assert registry.by_id("mitre_atlas").resolver.resolve_ids(["AML.T9999"]) == []
    assert registry.by_id("mitre_attack_enterprise").resolver.resolve_ids(["T9999"]) == []
    assert CveReferenceResolver(package_dir=str(FIXTURE_CVE_DIR)).resolve_ids(["CVE-2099-9999"]) == []
