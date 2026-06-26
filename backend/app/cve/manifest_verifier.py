"""Governed CVE snapshot package verification (plan WS-A A5)."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ManifestVerificationResult:
    ok: bool
    errors: tuple[str, ...] = ()
    manifest: dict[str, Any] | None = None


_REQUIRED_MANIFEST_KEYS = (
    "snapshot_id",
    "schema_version",
    "generated_at_utc",
    "source_window_start",
    "source_window_end",
    "counts",
    "signature",
    "signer_id",
)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_manifest(package_dir: str | Path) -> ManifestVerificationResult:
    """Verify manifest presence, required fields, and artifact SHA256 digests.

    Cryptographic signature validation is a stub: ``signature`` and ``signer_id``
    must be non-empty strings. Full PKCS verification is deferred to operator SOP.
    """
    root = Path(package_dir)
    manifest_path = root / "manifest.json"
    if not manifest_path.is_file():
        return ManifestVerificationResult(ok=False, errors=("manifest_missing",))

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ManifestVerificationResult(ok=False, errors=("manifest_invalid_json",))

    if not isinstance(manifest, dict):
        return ManifestVerificationResult(ok=False, errors=("manifest_not_object",))

    errors: list[str] = []
    for key in _REQUIRED_MANIFEST_KEYS:
        if key not in manifest or manifest.get(key) in (None, ""):
            errors.append(f"manifest_missing_{key}")

    signature = str(manifest.get("signature") or "").strip()
    signer_id = str(manifest.get("signer_id") or "").strip()
    if not signature:
        errors.append("manifest_empty_signature")
    if not signer_id:
        errors.append("manifest_empty_signer_id")

    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, dict):
        errors.append("manifest_artifacts_missing")
    else:
        for name, meta in artifacts.items():
            if not isinstance(meta, dict):
                errors.append(f"artifact_meta_invalid:{name}")
                continue
            expected = str(meta.get("sha256") or "").strip().lower()
            artifact_path = root / name
            if not artifact_path.is_file():
                errors.append(f"artifact_missing:{name}")
                continue
            # A package whose manifest omits a digest for an artifact is NOT
            # verifiable — fail closed rather than silently trusting the bytes.
            if not expected:
                errors.append(f"artifact_sha256_absent:{name}")
                continue
            actual = _sha256_file(artifact_path)
            if actual != expected:
                errors.append(f"artifact_sha256_mismatch:{name}")

    return ManifestVerificationResult(
        ok=not errors,
        errors=tuple(errors),
        manifest=manifest,
    )
