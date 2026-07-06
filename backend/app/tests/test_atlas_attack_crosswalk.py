"""Tests for atlas_attack_crosswalk loader (plan 2026-07-06 items 13/16)."""

from __future__ import annotations

import json
from pathlib import Path

import app.knowledge.atlas_attack_crosswalk as crosswalk
from app.knowledge.atlas_attack_crosswalk import (
    atlas_technique_suggested_remediation,
    atlas_technique_to_template_hints,
)

TEMPLATES = Path(__file__).resolve().parents[1] / "spl" / "templates.json"


def test_valid_accounts_hints_auth_templates() -> None:
    hints = atlas_technique_to_template_hints("AML.T0012")
    assert "auth_new_source_ip" in hints


def test_uncrosswalked_technique_returns_empty() -> None:
    assert atlas_technique_to_template_hints("AML.T0065") == []


def test_all_hinted_template_ids_exist_in_registry() -> None:
    payload = json.loads(crosswalk._CROSSWALK_PATH.read_text(encoding="utf-8"))
    template_ids = {row["template_id"] for row in json.loads(TEMPLATES.read_text(encoding="utf-8"))["templates"]}
    for entry in payload["entries"]:
        for template_id in entry["template_ids"]:
            assert template_id in template_ids


def test_add_new_entry_requires_no_code_change(tmp_path: Path, monkeypatch) -> None:
    payload = json.loads(crosswalk._CROSSWALK_PATH.read_text(encoding="utf-8"))
    payload["entries"].append(
        {
            "attack_technique_ref": "T9999",
            "template_ids": ["auth_failed_login_spike"],
            "strength": "moderate",
            "reasoning": "fixture-only",
        }
    )
    fixture = tmp_path / "crosswalk.json"
    fixture.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr(crosswalk, "_CROSSWALK_PATH", fixture)
    assert atlas_technique_to_template_hints("AML.T9999") == []


def test_remediation_for_crosswalked_technique() -> None:
    remediation = atlas_technique_suggested_remediation("AML.T0012")
    assert remediation is not None
    assert remediation.get("text")


def test_remediation_absent_for_uncrosswalked_technique() -> None:
    assert atlas_technique_suggested_remediation("AML.T0065") is None
