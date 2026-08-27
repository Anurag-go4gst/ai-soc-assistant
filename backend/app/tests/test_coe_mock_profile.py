"""Phase 5.1 — isolated coe-mock profile is test-only and non-default."""

from __future__ import annotations

import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]


def test_coe_mock_profile_exists_with_existing_flags_only() -> None:
    example = REPO / "env/profiles/coe-mock.env.example"
    assert example.is_file()
    text = example.read_text(encoding="utf-8")
    assert "MCP_MODE=mock" in text
    assert "MCP_GLOBAL_EXECUTION_ENABLED=true" in text
    assert "MCP_SERVER_MOCK_EXECUTION_ENABLED=true" in text
    assert "SPLUNK_MCP_ENABLED=false" in text
    assert re.search(r"^SPLUNK_MCP_BASE_URL=\s*$", text, re.M)
    assert re.search(r"^SPLUNK_MCP_TOKEN=\s*$", text, re.M)
    # No secrets in the committed example.
    assert "SPLUNK_MCP_TOKEN=ey" not in text
    assert "Bearer " not in text


def test_coe_mock_registered_test_only_and_default_coe_unchanged() -> None:
    manifest = json.loads((REPO / "env/profiles/manifest.json").read_text(encoding="utf-8"))
    by_id = {p["id"]: p for p in manifest["profiles"]}
    assert "coe-mock" in by_id
    assert by_id["coe-mock"].get("test_only") is True
    assert by_id["coe-mock"]["example_file"] == "coe-mock.env.example"

    coe = (REPO / "env/profiles/coe.env.example").read_text(encoding="utf-8")
    assert "MCP_GLOBAL_EXECUTION_ENABLED=false" in coe

    compose = (REPO / "docker-compose.yml").read_text(encoding="utf-8")
    assert "AI_SOC_ENV_PROFILE:-coe" in compose
    assert "coe-mock" not in compose

    readme = (REPO / "env/README.md").read_text(encoding="utf-8")
    assert "coe-mock" in readme
    assert "test-only" in readme.lower() or "TEST-ONLY" in readme
