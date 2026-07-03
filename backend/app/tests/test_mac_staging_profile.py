"""Manifest includes Mac staging profile entry."""

from __future__ import annotations

import json
from pathlib import Path


def test_manifest_includes_mac_staging_profile() -> None:
    manifest_path = Path(__file__).resolve().parents[3] / "env/profiles/manifest.json"
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    ids = [p["id"] for p in data["profiles"]]
    assert "mac-staging" in ids
    mac = next(p for p in data["profiles"] if p["id"] == "mac-staging")
    assert mac["example_file"] == "mac-staging.env.example"
    example = manifest_path.parent / mac["example_file"]
    assert example.is_file()
