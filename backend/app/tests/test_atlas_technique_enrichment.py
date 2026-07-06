"""Tests for atlas_technique_enrichment (plan 2026-07-06 item 5)."""

from __future__ import annotations

from pathlib import Path

import app.knowledge.mapping_exports as mapping_exports
from app.knowledge.mapping_exports import atlas_technique_enrichment


def test_known_technique_has_mitigations() -> None:
    result = atlas_technique_enrichment("AML.T0000")
    assert result["mitigations"]
    assert any(item["id"] == "AML.M0000" for item in result["mitigations"])


def test_known_technique_has_case_studies() -> None:
    result = atlas_technique_enrichment("AML.T0065")
    assert result["case_studies"]
    ids = {item["id"] for item in result["case_studies"]}
    assert "AML.CS0045" in ids
    assert "AML.CS0054" in ids


def test_unknown_technique_returns_empty_lists() -> None:
    result = atlas_technique_enrichment("AML.T9999")
    assert result == {"mitigations": [], "case_studies": []}


def test_absent_normalized_files_fail_closed(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(mapping_exports, "_ATLAS_CASESTUDIES_PATH", str(tmp_path / "missing_cs.json"))
    monkeypatch.setattr(mapping_exports, "_ATLAS_MITIGATIONS_PATH", str(tmp_path / "missing_ms.json"))
    result = atlas_technique_enrichment("AML.T0065")
    assert result == {"mitigations": [], "case_studies": []}
