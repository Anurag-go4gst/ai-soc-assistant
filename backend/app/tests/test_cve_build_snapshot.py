"""WS-A A1-A3: connected-zone CVE snapshot builder produces an A5-consumable package."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from app.cve.manifest_verifier import verify_manifest
from app.cve.snapshot_store import CveSnapshotStore

_SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "cve_build_snapshot.py"
_spec = importlib.util.spec_from_file_location("cve_build_snapshot", _SCRIPT)
assert _spec and _spec.loader
cbs = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cbs)

_NVD_SAMPLE = {
    "vulnerabilities": [
        {
            "cve": {
                "id": "CVE-2024-1234",
                "cisaExploitAdd": "2024-03-01",
                "cisaActionDue": "2024-03-22",
                "metrics": {"cvssMetricV31": [{"cvssData": {"baseSeverity": "CRITICAL"}}]},
                "configurations": [
                    {"nodes": [{"cpeMatch": [{"criteria": "cpe:2.3:a:acme:widget:1.0:*:*:*:*:*:*:*"}]}]}
                ],
            }
        },
        {"cve": {"id": "CVE-2024-5678", "metrics": {}, "configurations": []}},
        {"not_a_cve": True},  # rejected
    ]
}


def test_normalize_nvd_items_is_deterministic_and_defensive():
    rows = cbs.normalize_nvd_items(_NVD_SAMPLE["vulnerabilities"])
    assert [r["cve_id"] for r in rows] == ["CVE-2024-1234", "CVE-2024-5678"]  # sorted, junk dropped
    assert rows[0]["severity"] == "CRITICAL"
    assert rows[0]["products"] == ["widget"]
    assert rows[1]["severity"] == "UNKNOWN"
    assert rows[1]["products"] == []
    # KEV flag derives from the NVD-embedded cisaExploitAdd field.
    assert rows[0]["kev"] is True
    assert rows[0]["kev_date_added"] == "2024-03-01"
    assert rows[1]["kev"] is False
    assert rows[1]["kev_date_added"] is None


_NVD_CHANGES_SAMPLE = {
    "cveChanges": [
        {"change": {"cveId": "CVE-2024-1234", "eventName": "CVE CISA KEV Update", "sourceIdentifier": "cisa", "created": "2024-03-01T00:00:00.000"}},
        {"change": {"cveId": "CVE-2024-5678", "eventName": "Initial Analysis", "sourceIdentifier": "nvd@nist.gov", "created": "2024-02-01T00:00:00.000"}},
        {"not_a_change": True},  # dropped
    ]
}


def test_normalize_nvd_changes_sorts_and_flags_kev():
    rows = cbs.normalize_nvd_changes(_NVD_CHANGES_SAMPLE["cveChanges"])
    assert [r["cve_id"] for r in rows] == ["CVE-2024-5678", "CVE-2024-1234"]  # sorted by created
    kev_row = next(r for r in rows if r["cve_id"] == "CVE-2024-1234")
    assert kev_row["kev_update"] is True
    assert kev_row["event"] == "CVE CISA KEV Update"
    assert all(r["kev_update"] is False for r in rows if r["cve_id"] == "CVE-2024-5678")


def test_change_log_populated_from_raw_changes(tmp_path: Path):
    import sys

    raw = tmp_path / "nvd.json"
    raw.write_text(json.dumps(_NVD_SAMPLE))
    raw_changes = tmp_path / "changes.json"
    raw_changes.write_text(json.dumps(_NVD_CHANGES_SAMPLE))
    out = tmp_path / "pkg"
    argv = sys.argv
    sys.argv = [
        "cve_build_snapshot.py", "--out", str(out), "--raw", str(raw),
        "--raw-changes", str(raw_changes),
        "--signature", "sig-abc", "--signer-id", "soc-signer",
    ]
    try:
        assert cbs.main() == 0
    finally:
        sys.argv = argv
    change_log = json.loads((out / "cve_change_log.json").read_text())
    manifest = json.loads((out / "manifest.json").read_text())
    assert len(change_log["changes"]) == 2
    assert manifest["counts"]["changes"] == 2
    assert manifest["counts"]["kev"] == 1


def test_built_package_verifies_and_loads(tmp_path: Path):
    raw = tmp_path / "nvd.json"
    raw.write_text(json.dumps(_NVD_SAMPLE))
    out = tmp_path / "pkg"
    # Build via argv (main() parses sys.argv).
    import sys

    argv = sys.argv
    sys.argv = [
        "cve_build_snapshot.py",
        "--out", str(out),
        "--raw", str(raw),
        "--window-start", "2026-06-01T00:00:00Z",
        "--window-end", "2026-06-16T00:00:00Z",
        "--signature", "sig-abc",
        "--signer-id", "soc-signer",
        "--reviewer", "rev",
        "--approver", "app",
    ]
    try:
        assert cbs.main() == 0
    finally:
        sys.argv = argv

    # The A5 verifier accepts it (sha256 + signature present) and the store reads it.
    result = verify_manifest(out)
    assert result.ok, result.errors
    store = CveSnapshotStore(package_dir=out, stale_after_days=100000)
    assert store.vulnerability_source_status().status == "onboarded_snapshot"
    assert store.lookup_cve("CVE-2024-1234")["severity"] == "CRITICAL"


def test_unsigned_package_fails_verifier(tmp_path: Path):
    raw = tmp_path / "nvd.json"
    raw.write_text(json.dumps(_NVD_SAMPLE))
    out = tmp_path / "pkg"
    import sys

    argv = sys.argv
    sys.argv = ["cve_build_snapshot.py", "--out", str(out), "--raw", str(raw)]  # no signature
    try:
        assert cbs.main() == 0
    finally:
        sys.argv = argv
    result = verify_manifest(out)
    assert result.ok is False
    assert any("signature" in e or "signer" in e for e in result.errors)
