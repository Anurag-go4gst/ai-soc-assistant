"""Stage 3K-Q2 local IOC lookup framework tests."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from app.config import settings
from app.intel.ioc_lookup import (
    BLOCK_CANNOT_ROUTE_LOOKUP_STALE,
    lookup_ioc,
    lookup_ioc_from_text,
    preflight_ioc_requirements,
)
from app.intel.ioc_models import IocType, StalenessStatus
from app.intel.ioc_registry import clear_ioc_registry_cache, validate_ioc_registry_payload
from app.routing.route_plan_models import PreflightContext, RouteStatus
from app.routing.route_plan_preflight import preflight_route_plan

FIXTURE_PATH = Path(__file__).resolve().parents[1] / "intel" / "fixtures" / "ioc_registry.sample.json"


@pytest.fixture(autouse=True)
def _reset_registry_cache() -> None:
    clear_ioc_registry_cache()
    yield
    clear_ioc_registry_cache()


def test_loader_rejects_malformed_ioc_records() -> None:
    payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    payload["iocs"][0]["ioc_type"] = "not_a_real_type"
    errors = validate_ioc_registry_payload(payload)
    assert errors


def test_lookup_ip_domain_hash(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ioc_registry_enabled", True)
    monkeypatch.setattr(settings, "ioc_registry_path", str(FIXTURE_PATH))

    ip = lookup_ioc("203.0.113.42", IocType.IP)
    domain = lookup_ioc("EVIL.EXAMPLE.COM", IocType.DOMAIN)
    digest = lookup_ioc("D41D8CD98F00B204E9800998ECF8427E", IocType.HASH_MD5)

    assert ip.match is True
    assert ip.confidence == "medium"
    assert ip.tlp == "AMBER"
    assert "source=internal_curated_v1" in (ip.redacted_provenance or "")

    assert domain.match is True
    assert domain.normalized_value == "evil.example.com"

    assert digest.match is True


def test_ipv6_canonical_normalization(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ioc_registry_enabled", True)
    path = FIXTURE_PATH.parent / "ioc_registry_ipv6_test.json"
    payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    payload["iocs"] = [
        {
            "value": "2001:db8::1",
            "ioc_type": "ip",
            "source_id": "internal_curated_v1",
            "confidence": "low",
            "tlp": "GREEN",
            "first_seen": "2026-05-01T00:00:00Z",
            "last_seen": "2026-05-20T00:00:00Z",
            "lookup_name": "ipv6_test",
            "provenance": "coe_synthetic_fixture",
            "update_mode": "air_gapped_bundle",
            "airgap_approved": True,
        }
    ]
    path.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr(settings, "ioc_registry_path", str(path))

    result = lookup_ioc("2001:DB8::0001", IocType.IP)
    assert result.match is True
    assert result.normalized_value == "2001:db8::1"
    path.unlink(missing_ok=True)


def test_stale_source_blocks_lookup(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ioc_registry_enabled", True)
    path = FIXTURE_PATH.parent / "ioc_registry_stale_source.json"
    payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    payload["sources"] = [
        {
            **payload["sources"][0],
            "source_id": "stale_feed_v1",
            "lookup_name": "stale_feed_v1",
            "last_refreshed": "2020-01-01T00:00:00Z",
            "max_staleness_hours": 24,
        }
    ]
    payload["iocs"] = [
        {
            "value": "198.51.100.9",
            "ioc_type": "ip",
            "source_id": "stale_feed_v1",
            "confidence": "medium",
            "tlp": "AMBER",
            "first_seen": "2019-12-01T00:00:00Z",
            "last_seen": "2019-12-31T00:00:00Z",
            "lookup_name": "stale_feed_ip",
            "provenance": "coe_synthetic_fixture_stale",
            "update_mode": "air_gapped_bundle",
            "airgap_approved": True,
        }
    ]
    path.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr(settings, "ioc_registry_path", str(path))

    result = lookup_ioc("198.51.100.9", IocType.IP)
    assert result.match is False
    assert result.staleness_status == StalenessStatus.STALE
    assert result.blocking_reason == BLOCK_CANNOT_ROUTE_LOOKUP_STALE
    path.unlink(missing_ok=True)


def test_expired_ioc_record_blocks_lookup(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ioc_registry_enabled", True)
    path = FIXTURE_PATH.parent / "ioc_registry_expired_test.json"
    payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    payload["iocs"] = [
        {
            "value": "10.9.8.7",
            "ioc_type": "ip",
            "source_id": "internal_curated_v1",
            "confidence": "low",
            "tlp": "GREEN",
            "first_seen": "2020-01-01T00:00:00Z",
            "last_seen": "2020-01-02T00:00:00Z",
            "expiry": "2020-01-03T00:00:00Z",
            "lookup_name": "expired_ip",
            "provenance": "coe_synthetic_fixture",
            "update_mode": "air_gapped_bundle",
            "airgap_approved": True,
        }
    ]
    path.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr(settings, "ioc_registry_path", str(path))

    result = lookup_ioc("10.9.8.7", IocType.IP)
    assert result.match is False
    assert result.staleness_status == StalenessStatus.EXPIRED
    path.unlink(missing_ok=True)


def test_route_plan_lookup_dependency_stale_registry_blocks_preflight(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ioc_registry_enabled", True)
    path = FIXTURE_PATH.parent / "ioc_registry_all_stale.json"
    payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    stale_time = (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
    payload["sources"] = [
        {
            **payload["sources"][0],
            "last_refreshed": stale_time,
            "max_staleness_hours": 1,
        }
    ]
    path.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr(settings, "ioc_registry_path", str(path))

    result = preflight_route_plan(
        "correlate hosts",
        PreflightContext(
            route_plan={"evidence_needs": {"lookup_required": True}},
        ),
    )
    assert result.route_status == RouteStatus.CANNOT_ROUTE_MISSING_LOOKUP
    assert BLOCK_CANNOT_ROUTE_LOOKUP_STALE in result.blocking_findings
    assert "lookup_stale" in result.blocking_findings
    path.unlink(missing_ok=True)


def test_redacted_provenance_has_no_raw_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ioc_registry_enabled", True)
    monkeypatch.setattr(settings, "ioc_registry_path", str(FIXTURE_PATH))
    result = lookup_ioc("evil.example.com", IocType.DOMAIN)
    assert result.redacted_provenance is not None
    assert "http://" not in result.redacted_provenance
    assert "analyst@" not in result.redacted_provenance.lower()


def test_no_requests_import_in_intel_package() -> None:
    import app.intel.ioc_lookup as lookup_module
    import app.intel.ioc_registry as registry_module

    source = Path(lookup_module.__file__).read_text(encoding="utf-8") + Path(registry_module.__file__).read_text(
        encoding="utf-8"
    )
    assert "import requests" not in source
    assert "httpx" not in source
    assert "urllib.request" not in source


def test_registry_disabled_preserves_legacy_missing_lookup() -> None:
    result = preflight_route_plan(
        "Which hosts contacted known malicious IPs today?",
        PreflightContext(configured_lookups=set()),
    )
    assert result.route_status == RouteStatus.CANNOT_ROUTE_MISSING_LOOKUP


def test_registry_enabled_allows_generic_ioc_query_when_fresh(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ioc_registry_enabled", True)
    monkeypatch.setattr(settings, "ioc_registry_path", str(FIXTURE_PATH))
    result = preflight_route_plan(
        "Which hosts contacted known malicious IPs today?",
        PreflightContext(configured_lookups=set()),
    )
    assert result.route_status is None


def test_unknown_ip_in_query_blocks_when_registry_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ioc_registry_enabled", True)
    monkeypatch.setattr(settings, "ioc_registry_path", str(FIXTURE_PATH))
    result = preflight_route_plan(
        "Did host 192.0.2.55 contact known malicious infrastructure?",
        PreflightContext(configured_lookups=set()),
    )
    assert result.route_status == RouteStatus.CANNOT_ROUTE_MISSING_LOOKUP


def test_lookup_ioc_from_text_infers_hash(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ioc_registry_enabled", True)
    monkeypatch.setattr(settings, "ioc_registry_path", str(FIXTURE_PATH))
    result = lookup_ioc_from_text("d41d8cd98f00b204e9800998ecf8427e")
    assert result.match is True
