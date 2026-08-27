"""SPL optimization registry API."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.spl.optimization_registry import build_spl_optimization_registry


def test_registry_has_live_code_anchors() -> None:
    payload = build_spl_optimization_registry()
    assert payload["entry_count"] >= 30
    q04 = next(e for e in payload["entries"] if e["logic_id"] == "draft_quality.Q04")
    assert q04["code"]["path"].endswith("draft_quality.py")
    assert q04["code"]["line"] > 0
    assert "rewrite.or_chain_to_in" in {e["logic_id"] for e in payload["entries"]}


def test_registry_api_get() -> None:
    client = TestClient(app)
    response = client.get("/api/knowledge/spl-optimization-registry")
    assert response.status_code in {200, 401}
    if response.status_code == 200:
        data = response.json()
        assert data["schema_version"] == "spl_optimization_registry_v1"
        assert "layers" in data


def test_registry_overrides_roundtrip(tmp_path, monkeypatch) -> None:
    from app.spl import optimization_registry as reg

    override_file = tmp_path / "overrides.json"
    monkeypatch.setattr(reg, "_OVERRIDES_PATH", override_file)
    reg.save_ui_overrides({"draft_quality.Q04": {"ui_enabled": False, "ui_note": "review"}})
    payload = reg.build_spl_optimization_registry()
    q04 = next(e for e in payload["entries"] if e["logic_id"] == "draft_quality.Q04")
    assert q04["ui_enabled"] is False
    assert q04["ui_note"] == "review"
