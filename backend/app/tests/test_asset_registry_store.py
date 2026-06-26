from __future__ import annotations

import pytest

from app.environment import asset_registry_store


def test_asset_registry_save_load_and_profile(tmp_path, monkeypatch) -> None:
    path = tmp_path / "assets.json"
    monkeypatch.setattr(asset_registry_store.settings, "ai_soc_asset_registry_store_path", str(path))
    document = asset_registry_store.save_asset_registry(
        [
            {"ip": "10.1.2.3", "asset_name": "RTU-West-01", "asset_type": "RTU", "criticality": "CII"},
            {"ip": "10.1.2.4", "asset_name": "Master-01", "asset_type": "EMS", "is_master_station": True},
        ]
    )
    assert len(document["assets"]) == 2
    loaded = asset_registry_store.load_asset_registry_document()
    assert loaded["assets"][0]["ip"] == "10.1.2.3"
    profile = asset_registry_store.build_asset_registry_profile(["phase1_rtu_ips", "master_station_ips"])
    assert profile["phase1_rtu_ips"] == '"10.1.2.3"'
    assert profile["master_station_ips"] == '"10.1.2.4"'


def test_asset_registry_rejects_invalid_ip(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(asset_registry_store.settings, "ai_soc_asset_registry_store_path", str(tmp_path / "assets.json"))
    with pytest.raises(ValueError):
        asset_registry_store.save_asset_registry([{"ip": "999.1.1.1"}])

