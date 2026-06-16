"""Tests for the offline STIX technique resolver (plan §15 WS-G G2).

mitreattack-python is intentionally NOT a runtime dependency in this air-gapped
deployment, so these tests exercise the fail-closed contract and the normalization
logic with injected fakes — no real STIX bundle or library required.
"""
from __future__ import annotations

from app.threat import stix_resolver as sr
from app.threat.stix_resolver import StixTechniqueResolver


def test_no_library_or_paths_is_fail_closed():
    r = StixTechniqueResolver()
    assert r.operational is False
    assert r.detail("T1078") is None
    assert r.detail("AML.T0051") is None


def test_blank_id_returns_none():
    r = StixTechniqueResolver(attack_stix_path="/nonexistent.json")
    assert r.detail("") is None
    assert r.detail("   ") is None


def test_missing_bundle_file_degrades_to_none():
    r = StixTechniqueResolver(
        attack_stix_path="/nonexistent/enterprise-attack.json",
        atlas_stix_path="/nonexistent/atlas.json",
    )
    assert r.detail("T1059") is None
    assert r.detail("AML.T0043") is None


class _FakeData:
    """Stand-in for MitreAttackData with a tiny in-memory technique table."""

    def __init__(self, table: dict[str, dict]):
        self._table = table

    def get_object_by_attack_id(self, attack_id: str, _stix_type: str):
        return self._table.get(attack_id)


def test_detail_normalizes_enterprise_object():
    r = StixTechniqueResolver(attack_stix_path="x")  # path unused; data injected
    r._attack_data = _FakeData(
        {
            "T1059": {
                "name": "Command and Scripting Interpreter",
                "description": "Adversaries may abuse command interpreters.",
                "x_mitre_deprecated": False,
                "revoked": False,
                "external_references": [{"url": "https://attack.mitre.org/techniques/T1059"}],
            }
        }
    )
    detail = r.detail("T1059")
    assert detail == {
        "technique_id": "T1059",
        "name": "Command and Scripting Interpreter",
        "description": "Adversaries may abuse command interpreters.",
        "deprecated": False,
        "revoked": False,
        "domain": "enterprise-attack",
        "url": "https://attack.mitre.org/techniques/T1059",
    }


def test_deprecated_and_revoked_flags_and_atlas_routing():
    r = StixTechniqueResolver(atlas_stix_path="x")
    r._atlas_data = _FakeData(
        {"AML.T0043": {"name": "Craft Adversarial Data", "x_mitre_deprecated": True, "revoked": False}}
    )
    detail = r.detail("AML.T0043")
    assert detail["deprecated"] is True
    assert detail["domain"] == "atlas"
    assert detail["url"] == ""  # no external_references -> empty, not a crash


def test_unknown_id_returns_none():
    r = StixTechniqueResolver(attack_stix_path="x")
    r._attack_data = _FakeData({})
    assert r.detail("T9999") is None


def test_lookup_exception_is_swallowed():
    class _Boom:
        def get_object_by_attack_id(self, *_a):
            raise RuntimeError("boom")

    r = StixTechniqueResolver(attack_stix_path="x")
    r._attack_data = _Boom()
    assert r.detail("T1078") is None


def test_implements_technique_resolver_protocol():
    from app.chat.grounding_assembler import TechniqueResolver, assemble_grounding

    r = StixTechniqueResolver()
    assert isinstance(r, TechniqueResolver)
    # Drops into assemble_grounding with zero caller change; null bundle -> no names.
    block = assemble_grounding("hunt for AML model evasion", resolver=r)
    assert block is not None


def test_library_available_reflects_import():
    assert sr.library_available() == sr._MITREATTACK_AVAILABLE
