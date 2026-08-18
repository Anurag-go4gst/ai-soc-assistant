from __future__ import annotations

from app.connectors.mcp.discovery_snapshot import (
    DiscoveredToolRecord,
    DiscoverySnapshot,
    InMemoryDiscoverySnapshotStore,
    build_snapshot_from_handshake,
)


def test_snapshot_from_ok_handshake_captures_descriptors() -> None:
    handshake = {
        "status": "ok",
        "initialized": True,
        "initialize_ok": True,
        "tools": ["splunk_get_indexes"],
        "tool_descriptors": [
            {"name": "splunk_get_indexes", "description": "list indexes", "input_schema": {}, "input_schema_malformed": False, "annotations": {}}
        ],
    }
    snapshot = build_snapshot_from_handshake(server_name="splunk_soc", handshake_result=handshake, source="operator_refresh", now=1000.0)
    assert snapshot.status == "ok"
    assert snapshot.captured_at == 1000.0
    assert snapshot.source == "operator_refresh"
    assert snapshot.tool_by_name("splunk_get_indexes") is not None
    assert snapshot.tool_by_name("nonexistent") is None


def test_snapshot_from_blocked_handshake_is_failed_not_raised() -> None:
    handshake = {"status": "blocked", "error": "live_transport_unconfigured", "initialized": False, "tools": []}
    snapshot = build_snapshot_from_handshake(server_name="splunk_soc", handshake_result=handshake, source="startup")
    assert snapshot.status == "failed"
    assert snapshot.error_reason == "live_transport_unconfigured"
    assert snapshot.tools == ()


def test_snapshot_from_none_or_malformed_handshake_never_raises() -> None:
    for bad in (None, {}, "not-a-dict", 123, {"status": "ok"}):
        snapshot = build_snapshot_from_handshake(server_name="splunk_soc", handshake_result=bad, source="startup")
        assert snapshot.status in {"ok", "failed"}


def test_description_with_credential_pattern_is_redacted_at_storage_boundary() -> None:
    handshake = {
        "status": "ok",
        "tool_descriptors": [
            {"name": "x", "description": "Authorization: Bearer sk-live-abcdef", "input_schema": {}, "input_schema_malformed": False, "annotations": {}}
        ],
    }
    snapshot = build_snapshot_from_handshake(server_name="s", handshake_result=handshake, source="startup")
    assert "sk-live-abcdef" not in snapshot.tools[0].description
    assert "[redacted" in snapshot.tools[0].description


def test_safe_dict_never_contains_raw_input_schema_or_secrets() -> None:
    snapshot = DiscoverySnapshot(
        server_name="s",
        captured_at=1000.0,
        source="startup",
        status="ok",
        tools=(DiscoveredToolRecord(name="t", description="d", input_schema={"secret_default": "abc"}, annotations={}),),
    )
    payload = snapshot.to_safe_dict()
    assert "input_schema" not in payload["tools"][0]
    assert payload["tools"][0]["has_input_schema"] is True
    assert "abc" not in str(payload)


def test_age_seconds_computed_from_captured_at() -> None:
    snapshot = DiscoverySnapshot(server_name="s", captured_at=0.0, source="startup", status="ok", tools=())
    assert snapshot.age_seconds > 0


def test_in_memory_store_put_get_isolated_instances() -> None:
    store_a = InMemoryDiscoverySnapshotStore()
    store_b = InMemoryDiscoverySnapshotStore()
    snapshot = DiscoverySnapshot(server_name="splunk_soc", captured_at=1.0, source="startup", status="ok", tools=())
    store_a.put(snapshot)
    assert store_a.get("splunk_soc") is snapshot
    assert store_b.get("splunk_soc") is None  # no shared state across instances


def test_in_memory_store_get_missing_server_returns_none() -> None:
    store = InMemoryDiscoverySnapshotStore()
    assert store.get("never_discovered") is None


def test_in_memory_store_all_and_clear() -> None:
    store = InMemoryDiscoverySnapshotStore()
    store.put(DiscoverySnapshot(server_name="a", captured_at=1.0, source="startup", status="ok", tools=()))
    store.put(DiscoverySnapshot(server_name="b", captured_at=1.0, source="startup", status="ok", tools=()))
    assert set(store.all().keys()) == {"a", "b"}
    store.clear()
    assert store.all() == {}
