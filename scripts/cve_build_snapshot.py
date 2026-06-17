#!/usr/bin/env python3
"""CVE connected-zone snapshot builder (plan §3 A1–A3).

Runs in the CONNECTED zone only — it is operator tooling, never imported by the
air-gapped runtime (no `app.*` import depends on it). Produces the signed package
that the air-gapped `CveSnapshotStore` (A5) consumes:

    cve_snapshot.json   (schema cve_snapshot_v1)
    cve_change_log.json (schema cve_change_log_v1)
    manifest.json       (sha256 per artifact + signature/signer + counts + window)

Two input modes:
  --raw PATH    normalize a previously-saved NVD JSON response (offline, default)
  --online      fetch from the NVD 2.0 API (connected zone only; urllib, no deps)

NVD endpoints (A1):
  https://services.nvd.nist.gov/rest/json/cves/2.0
  https://services.nvd.nist.gov/rest/json/cvehistory/2.0
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

NVD_CVES_URL = "https://services.nvd.nist.gov/rest/json/cves/2.0"
SNAPSHOT_SCHEMA = "cve_snapshot_v1"
CHANGE_LOG_SCHEMA = "cve_change_log_v1"


def normalize_nvd_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Map NVD 2.0 `vulnerabilities[].cve` objects to the snapshot row schema.

    Pure + deterministic (sorted by cve_id). Defensive against missing fields so a
    partial NVD payload degrades to fewer fields, never a crash.
    """
    rows: list[dict[str, Any]] = []
    for item in items:
        cve = item.get("cve") if isinstance(item, dict) else None
        if not isinstance(cve, dict):
            continue
        cve_id = str(cve.get("id") or "").strip()
        if not cve_id:
            continue
        rows.append(
            {
                "cve_id": cve_id,
                "severity": _severity(cve),
                "products": _products(cve),
            }
        )
    rows.sort(key=lambda r: r["cve_id"])
    return rows


def _severity(cve: dict[str, Any]) -> str:
    metrics = cve.get("metrics") if isinstance(cve.get("metrics"), dict) else {}
    for key in ("cvssMetricV31", "cvssMetricV30", "cvssMetricV2"):
        entries = metrics.get(key)
        if isinstance(entries, list) and entries:
            data = entries[0].get("cvssData") if isinstance(entries[0], dict) else None
            sev = (entries[0].get("baseSeverity") if isinstance(entries[0], dict) else None) or (
                data.get("baseSeverity") if isinstance(data, dict) else None
            )
            if sev:
                return str(sev).upper()
    return "UNKNOWN"


def _products(cve: dict[str, Any]) -> list[str]:
    products: set[str] = set()
    for config in cve.get("configurations") or []:
        nodes = config.get("nodes") if isinstance(config, dict) else None
        for node in nodes or []:
            for match in (node.get("cpeMatch") if isinstance(node, dict) else None) or []:
                criteria = str(match.get("criteria") or "")
                parts = criteria.split(":")
                # cpe:2.3:a:vendor:product:version:...
                if len(parts) >= 5 and parts[4]:
                    products.add(parts[4])
    return sorted(products)


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def build_manifest(
    *,
    snapshot_json: str,
    change_log_json: str,
    snapshot_id: str,
    window_start: str,
    window_end: str,
    cve_count: int,
    change_count: int,
    rejected_count: int,
    signature: str,
    signer_id: str,
    reviewer: str,
    approver: str,
) -> dict[str, Any]:
    """Assemble the A2 manifest with per-artifact SHA256 + signing identity.

    `signature`/`signer_id` are required by the A5 verifier (fail-closed if empty).
    """
    return {
        "snapshot_id": snapshot_id,
        "schema_version": SNAPSHOT_SCHEMA,
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "source_window_start": window_start,
        "source_window_end": window_end,
        "counts": {"cves": cve_count, "changes": change_count, "rejected": rejected_count},
        "artifacts": {
            "cve_snapshot.json": {"sha256": _sha256_text(snapshot_json)},
            "cve_change_log.json": {"sha256": _sha256_text(change_log_json)},
        },
        "signature": signature,
        "signer_id": signer_id,
        "reviewer": reviewer,
        "approver": approver,
    }


def _fetch_online(start_index: int, results_per_page: int) -> list[dict[str, Any]]:  # pragma: no cover
    """Connected-zone NVD fetch. Imported lazily so the air-gapped runtime/tests
    never touch urllib or the network."""
    import urllib.parse
    import urllib.request

    query = urllib.parse.urlencode({"startIndex": start_index, "resultsPerPage": results_per_page})
    with urllib.request.urlopen(f"{NVD_CVES_URL}?{query}", timeout=30) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    return payload.get("vulnerabilities") or []


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a governed CVE snapshot package")
    parser.add_argument("--out", required=True, help="Output package directory")
    parser.add_argument("--raw", help="Local NVD JSON response to normalize (offline mode)")
    parser.add_argument("--online", action="store_true", help="Fetch from NVD (connected zone only)")
    parser.add_argument("--start-index", type=int, default=0)
    parser.add_argument("--results-per-page", type=int, default=2000)
    parser.add_argument("--window-start", default="")
    parser.add_argument("--window-end", default="")
    parser.add_argument("--signature", default="", help="Package signature (required by A5 verifier)")
    parser.add_argument("--signer-id", default="", help="Signing identity (required by A5 verifier)")
    parser.add_argument("--reviewer", default="")
    parser.add_argument("--approver", default="")
    args = parser.parse_args()

    if args.online:  # pragma: no cover - connected-zone only
        vulnerabilities = _fetch_online(args.start_index, args.results_per_page)
    elif args.raw:
        payload = json.loads(Path(args.raw).read_text(encoding="utf-8"))
        vulnerabilities = payload.get("vulnerabilities") or []
    else:
        parser.error("provide --raw PATH (offline) or --online (connected zone)")
        return 2

    rows = normalize_nvd_items(vulnerabilities)
    snapshot = {"schema_version": SNAPSHOT_SCHEMA, "cves": rows}
    change_log = {"schema_version": CHANGE_LOG_SCHEMA, "changes": []}
    snapshot_json = json.dumps(snapshot, indent=2)
    change_log_json = json.dumps(change_log, indent=2)

    snapshot_id = f"cve-{datetime.now(UTC).date().isoformat()}"
    manifest = build_manifest(
        snapshot_json=snapshot_json,
        change_log_json=change_log_json,
        snapshot_id=snapshot_id,
        window_start=args.window_start,
        window_end=args.window_end,
        cve_count=len(rows),
        change_count=0,
        rejected_count=len(vulnerabilities) - len(rows),
        signature=args.signature,
        signer_id=args.signer_id,
        reviewer=args.reviewer,
        approver=args.approver,
    )

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "cve_snapshot.json").write_text(snapshot_json, encoding="utf-8")
    (out / "cve_change_log.json").write_text(change_log_json, encoding="utf-8")
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(
        f"CVE package: {len(rows)} cves "
        f"({manifest['counts']['rejected']} rejected) -> {out} "
        f"(signed={'yes' if args.signature and args.signer_id else 'NO — verifier will fail closed'})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
