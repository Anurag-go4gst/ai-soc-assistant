"""Read-only local CVE snapshot store (plan WS-A A5)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from app.cve.manifest_verifier import verify_manifest

VulnerabilitySourceStatus = Literal["onboarded_snapshot", "not_onboarded", "stale"]


@dataclass(frozen=True)
class CveSnapshotStatus:
    status: VulnerabilitySourceStatus
    snapshot_id: str | None = None
    snapshot_generated_at: str | None = None
    snapshot_age_days: int | None = None
    limitation: str | None = None
    provenance: dict[str, Any] | None = None


@dataclass
class CveSnapshotStore:
    """Fail-closed read model for operator-vendored CVE snapshot packages."""

    package_dir: str | Path | None = None
    stale_after_days: int = 30

    def _root(self) -> Path | None:
        if not self.package_dir:
            return None
        path = Path(self.package_dir)
        return path if path.is_dir() else None

    def vulnerability_source_status(self, *, now: datetime | None = None) -> CveSnapshotStatus:
        root = self._root()
        if root is None:
            return CveSnapshotStatus(
                status="not_onboarded",
                limitation="CVE snapshot package is not configured or missing on disk.",
            )

        verification = verify_manifest(root)
        if not verification.ok:
            return CveSnapshotStatus(
                status="not_onboarded",
                limitation="CVE snapshot package failed manifest verification.",
                provenance={"verification_errors": list(verification.errors)},
            )

        manifest = verification.manifest or {}
        generated_at_raw = str(manifest.get("generated_at_utc") or "")
        age_days: int | None = None
        now = now or datetime.now(timezone.utc)
        try:
            generated_at = datetime.fromisoformat(generated_at_raw.replace("Z", "+00:00"))
            if generated_at.tzinfo is None:
                generated_at = generated_at.replace(tzinfo=timezone.utc)
            age_days = max(0, (now - generated_at.astimezone(timezone.utc)).days)
        except ValueError:
            return CveSnapshotStatus(
                status="not_onboarded",
                limitation="CVE snapshot manifest has invalid generated_at_utc.",
                provenance={"snapshot_id": manifest.get("snapshot_id")},
            )

        if age_days is not None and age_days > self.stale_after_days:
            return CveSnapshotStatus(
                status="stale",
                snapshot_id=str(manifest.get("snapshot_id") or ""),
                snapshot_generated_at=generated_at_raw,
                snapshot_age_days=age_days,
                limitation=f"CVE snapshot is older than {self.stale_after_days} days.",
                provenance=self._provenance(manifest),
            )

        return CveSnapshotStatus(
            status="onboarded_snapshot",
            snapshot_id=str(manifest.get("snapshot_id") or ""),
            snapshot_generated_at=generated_at_raw,
            snapshot_age_days=age_days,
            provenance=self._provenance(manifest),
        )

    def load_snapshot_records(self) -> list[dict[str, Any]]:
        """Return CVE rows from ``cve_snapshot.json`` when package verifies."""
        root = self._root()
        if root is None:
            return []
        verification = verify_manifest(root)
        if not verification.ok:
            return []
        snapshot_path = root / "cve_snapshot.json"
        if not snapshot_path.is_file():
            return []
        try:
            payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        cves = payload.get("cves") if isinstance(payload, dict) else None
        return [row for row in cves if isinstance(row, dict)] if isinstance(cves, list) else []

    def lookup_cve(self, cve_id: str) -> dict[str, Any] | None:
        needle = (cve_id or "").strip().upper()
        if not needle:
            return None
        for row in self.load_snapshot_records():
            if str(row.get("cve_id") or "").upper() == needle:
                return dict(row)
        return None

    @staticmethod
    def _provenance(manifest: dict[str, Any]) -> dict[str, Any]:
        return {
            "snapshot_id": manifest.get("snapshot_id"),
            "schema_version": manifest.get("schema_version"),
            "generated_at_utc": manifest.get("generated_at_utc"),
            "source_window_start": manifest.get("source_window_start"),
            "source_window_end": manifest.get("source_window_end"),
            "signer_id": manifest.get("signer_id"),
            "counts": manifest.get("counts"),
        }
