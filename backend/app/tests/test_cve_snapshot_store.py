"""CVE A5 snapshot store + manifest verifier tests."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from app.cve.manifest_verifier import verify_manifest
from app.cve.snapshot_store import CveSnapshotStore

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "cve"


def test_fixture_manifest_verifies() -> None:
    result = verify_manifest(FIXTURE_DIR)
    assert result.ok, result.errors
    assert result.manifest is not None
    assert result.manifest.get("snapshot_id") == "cve-fixture-2026-06-16"


def test_store_onboarded_with_fixture() -> None:
    store = CveSnapshotStore(package_dir=FIXTURE_DIR, stale_after_days=30)
    status = store.vulnerability_source_status(now=datetime(2026, 6, 17, tzinfo=timezone.utc))
    assert status.status == "onboarded_snapshot"
    assert status.snapshot_id == "cve-fixture-2026-06-16"
    assert status.snapshot_age_days == 1


def test_store_stale_when_past_threshold() -> None:
    store = CveSnapshotStore(package_dir=FIXTURE_DIR, stale_after_days=7)
    status = store.vulnerability_source_status(now=datetime(2026, 7, 1, tzinfo=timezone.utc))
    assert status.status == "stale"
    assert status.limitation


def test_store_not_onboarded_when_missing_dir() -> None:
    store = CveSnapshotStore(package_dir="/nonexistent/cve/package")
    status = store.vulnerability_source_status()
    assert status.status == "not_onboarded"


def test_lookup_cve_from_fixture() -> None:
    store = CveSnapshotStore(package_dir=FIXTURE_DIR)
    row = store.lookup_cve("CVE-2024-0001")
    assert row is not None
    assert row.get("severity") == "HIGH"
