"""WS-G: offline ATT&CK-Excel + ATLAS-YAML technique resolver tests.

Uses the vendored repo data (enterprise xlsx + ATLAS yaml) for integration coverage
and asserts fail-closed behavior when paths are absent.
"""
from __future__ import annotations

from pathlib import Path

from app.chat.grounding_assembler import TechniqueResolver
from app.threat.attack_data_resolver import AttackDataResolver

ROOT = Path(__file__).resolve().parents[3]
XLSX = ROOT / "docs" / "evals" / "enterprise-attack-v19.1.xlsx"
ATLAS = ROOT / "docs" / "threat-intel" / "atlas" / "raw" / "ATLAS.yaml"


def _resolver() -> AttackDataResolver:
    return AttackDataResolver(attack_xlsx_path=XLSX, atlas_yaml_path=ATLAS)


def test_fail_closed_without_paths():
    r = AttackDataResolver()
    assert r.operational is False
    assert r.detail("T1071") is None
    assert r.detail("AML.T0051") is None


def test_blank_and_unknown_ids_return_none():
    r = _resolver()
    assert r.detail("") is None
    assert r.detail("   ") is None
    assert r.detail("T9999") is None


def test_enterprise_present_resolves_name_and_domain():
    r = _resolver()
    d = r.detail("T1071.004")
    assert d is not None
    assert d["name"] == "Application Layer Protocol: DNS"
    assert d["domain"] == "enterprise-attack"
    assert d["deprecated"] is False
    assert d["description"]


def test_enterprise_deprecated_or_renumbered_absent():
    # v19.1 excludes deprecated/revoked; T1086 (PowerShell, deprecated) and
    # T1562.001 (renumbered to T1685) are absent -> None.
    r = _resolver()
    assert r.detail("T1086") is None
    assert r.detail("T1562.001") is None


def test_atlas_aml_resolves_name():
    r = _resolver()
    d = r.detail("AML.T0051")
    assert d is not None
    assert d["domain"] == "atlas"
    assert d["name"]  # e.g. "LLM Prompt Injection"


def test_implements_technique_resolver_protocol():
    assert isinstance(_resolver(), TechniqueResolver)


def test_absent_technique_disposition_classifies_ics_and_deprecated():
    from app.threat.attack_data_resolver import absent_technique_disposition

    assert absent_technique_disposition("T0819") == "not_found"
    assert absent_technique_disposition("T1086") == "deprecated"
    assert absent_technique_disposition("AML.T9999") == "not_found"


def test_technique_resolver_from_settings_uses_vendored_data():
    from app.threat.attack_data_resolver import AttackDataResolver, technique_resolver_from_settings

    resolver = technique_resolver_from_settings()
    assert isinstance(resolver, AttackDataResolver)
    assert resolver.detail("AML.T0051") is not None


def test_routing_by_prefix_uses_correct_source():
    r = _resolver()
    assert r.detail("T1003")["domain"] == "enterprise-attack"
    assert r.detail("AML.T0000")["domain"] == "atlas"


def test_atlas_attack_technique_ref_crosswalk() -> None:
    r = _resolver()
    assert r.detail("AML.T0012")["attack_technique_ref"] == "T1078"
    assert r.detail("AML.T0065")["attack_technique_ref"] == ""
