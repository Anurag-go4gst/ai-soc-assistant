#!/usr/bin/env python3
"""CVE connected-zone snapshot builder (plan §3 A1–A3).

Runs in the CONNECTED zone only — it is operator tooling, never imported by the
air-gapped runtime (no `app.*` import depends on it). Produces the signed package
that the air-gapped `CveSnapshotStore` (A5) consumes:

    cve_snapshot.json   (schema cve_snapshot_v1)
    cve_change_log.json (schema cve_change_log_v1)
    manifest.json       (sha256 per artifact + signature/signer + counts + window)

Input modes:
  --raw PATH          normalize a saved NVD cves/2.0 JSON response (offline, default)
  --raw-changes PATH  normalize a saved NVD cvehistory/2.0 JSON response (offline)
  --online            fetch cves/2.0 from NVD (connected zone only; urllib, no deps)
                      + cvehistory/2.0 when --window-start/--window-end are given

NVD endpoints (A1):
  https://services.nvd.nist.gov/rest/json/cves/2.0
  https://services.nvd.nist.gov/rest/json/cvehistory/2.0

An NVD API key (--api-key or env NVD_API_KEY) raises the rate limit from 5 to 50
requests / 30s; the builder paces requests accordingly. KEV (CISA Known Exploited)
status is read from the NVD-embedded `cisaExploitAdd` field per CVE.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

NVD_CVES_URL = "https://services.nvd.nist.gov/rest/json/cves/2.0"
NVD_HISTORY_URL = "https://services.nvd.nist.gov/rest/json/cvehistory/2.0"
SNAPSHOT_SCHEMA = "cve_snapshot_v1"
CHANGE_LOG_SCHEMA = "cve_change_log_v1"
KEV_EVENT_NAME = "CVE CISA KEV Update"


def normalize_nvd_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Map NVD 2.0 `vulnerabilities[].cve` objects to the snapshot row schema.

    Pure + deterministic (sorted by cve_id). Defensive against missing fields so a
    partial NVD payload degrades to fewer fields, never a crash. `kev` reflects the
    NVD-embedded CISA Known-Exploited flag (`cisaExploitAdd`).
    """
    rows: list[dict[str, Any]] = []
    for item in items:
        cve = item.get("cve") if isinstance(item, dict) else None
        if not isinstance(cve, dict):
            continue
        cve_id = str(cve.get("id") or "").strip()
        if not cve_id:
            continue
        kev_added = str(cve.get("cisaExploitAdd") or "").strip()
        rows.append(
            {
                "cve_id": cve_id,
                "severity": _severity(cve),
                "products": _products(cve),
                "kev": bool(kev_added),
                "kev_date_added": kev_added or None,
                "kev_action_due": str(cve.get("cisaActionDue") or "").strip() or None,
            }
        )
    rows.sort(key=lambda r: r["cve_id"])
    return rows


def normalize_nvd_changes(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Map NVD 2.0 `cveChanges[].change` objects to the change-log row schema.

    Pure + deterministic (sorted by created, then cve_id). Each row records the
    CVE-ID, event name, source, created timestamp, and whether it is a KEV update.
    """
    rows: list[dict[str, Any]] = []
    for item in items:
        change = item.get("change") if isinstance(item, dict) else None
        if not isinstance(change, dict):
            continue
        cve_id = str(change.get("cveId") or "").strip()
        event = str(change.get("eventName") or "").strip()
        if not cve_id or not event:
            continue
        rows.append(
            {
                "cve_id": cve_id,
                "event": event,
                "source": str(change.get("sourceIdentifier") or "").strip(),
                "created": str(change.get("created") or "").strip(),
                "kev_update": event == KEV_EVENT_NAME,
            }
        )
    rows.sort(key=lambda r: (r["created"], r["cve_id"]))
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
    kev_count: int,
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
        "counts": {
            "cves": cve_count,
            "changes": change_count,
            "rejected": rejected_count,
            "kev": kev_count,
        },
        "artifacts": {
            "cve_snapshot.json": {"sha256": _sha256_text(snapshot_json)},
            "cve_change_log.json": {"sha256": _sha256_text(change_log_json)},
        },
        "signature": signature,
        "signer_id": signer_id,
        "reviewer": reviewer,
        "approver": approver,
    }


# --- Connected-zone network helpers (lazy urllib; air-gapped runtime never calls these) ---


def _http_get_json(url: str, params: dict[str, Any], api_key: str) -> dict[str, Any]:  # pragma: no cover
    import urllib.parse
    import urllib.request

    headers = {"apiKey": api_key} if api_key else {}
    request = urllib.request.Request(f"{url}?{urllib.parse.urlencode(params)}", headers=headers)
    with urllib.request.urlopen(request, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _paginate(  # pragma: no cover - connected-zone only
    url: str,
    base_params: dict[str, Any],
    results_key: str,
    *,
    api_key: str,
    start_index: int,
    results_per_page: int,
    max_records: int,
) -> list[dict[str, Any]]:
    """Page through an NVD collection endpoint, pacing for the rate limit."""
    import time

    collected: list[dict[str, Any]] = []
    pause = 0.6 if api_key else 6.0  # NVD guidance: ~50/30s keyed, ~5/30s anonymous
    index = start_index
    while True:
        params = {**base_params, "startIndex": index, "resultsPerPage": results_per_page}
        payload = _http_get_json(url, params, api_key)
        page = payload.get(results_key) or []
        collected.extend(page)
        total = int(payload.get("totalResults") or 0)
        index += len(page)
        if not page or index >= total or (max_records and len(collected) >= max_records):
            break
        time.sleep(pause)
    return collected[:max_records] if max_records else collected


def _fetch_cves_online(  # pragma: no cover - connected-zone only
    api_key: str, start_index: int, results_per_page: int, max_records: int
) -> list[dict[str, Any]]:
    return _paginate(
        NVD_CVES_URL,
        {},
        "vulnerabilities",
        api_key=api_key,
        start_index=start_index,
        results_per_page=results_per_page,
        max_records=max_records,
    )


def _fetch_changes_online(  # pragma: no cover - connected-zone only
    api_key: str, window_start: str, window_end: str, results_per_page: int, max_records: int
) -> list[dict[str, Any]]:
    return _paginate(
        NVD_HISTORY_URL,
        {"changeStartDate": window_start, "changeEndDate": window_end},
        "cveChanges",
        api_key=api_key,
        start_index=0,
        results_per_page=min(results_per_page, 5000),
        max_records=max_records,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a governed CVE snapshot package")
    parser.add_argument("--out", required=True, help="Output package directory")
    parser.add_argument("--raw", help="Local NVD cves/2.0 JSON to normalize (offline)")
    parser.add_argument("--raw-changes", help="Local NVD cvehistory/2.0 JSON to normalize (offline)")
    parser.add_argument("--online", action="store_true", help="Fetch from NVD (connected zone only)")
    parser.add_argument(
        "--api-key", default=os.environ.get("NVD_API_KEY", ""), help="NVD API key (or env NVD_API_KEY)"
    )
    parser.add_argument("--start-index", type=int, default=0)
    parser.add_argument("--results-per-page", type=int, default=2000)
    parser.add_argument("--max-records", type=int, default=0, help="Cap total records fetched (0 = no cap)")
    parser.add_argument("--window-start", default="", help="ISO-8601; with --online also pulls cvehistory")
    parser.add_argument("--window-end", default="")
    parser.add_argument("--signature", default="", help="Package signature (required by A5 verifier)")
    parser.add_argument("--signer-id", default="", help="Signing identity (required by A5 verifier)")
    parser.add_argument("--reviewer", default="")
    parser.add_argument("--approver", default="")
    args = parser.parse_args()

    change_items: list[dict[str, Any]] = []
    if args.online:  # pragma: no cover - connected-zone only
        vulnerabilities = _fetch_cves_online(
            args.api_key, args.start_index, args.results_per_page, args.max_records
        )
        if args.window_start and args.window_end:
            change_items = _fetch_changes_online(
                args.api_key, args.window_start, args.window_end, args.results_per_page, args.max_records
            )
    elif args.raw:
        payload = json.loads(Path(args.raw).read_text(encoding="utf-8"))
        vulnerabilities = payload.get("vulnerabilities") or []
        if args.raw_changes:
            change_items = (json.loads(Path(args.raw_changes).read_text(encoding="utf-8")) or {}).get(
                "cveChanges"
            ) or []
    else:
        parser.error("provide --raw PATH (offline) or --online (connected zone)")
        return 2

    rows = normalize_nvd_items(vulnerabilities)
    changes = normalize_nvd_changes(change_items)
    kev_count = sum(1 for r in rows if r.get("kev"))
    snapshot = {"schema_version": SNAPSHOT_SCHEMA, "cves": rows}
    change_log = {"schema_version": CHANGE_LOG_SCHEMA, "changes": changes}
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
        change_count=len(changes),
        rejected_count=len(vulnerabilities) - len(rows),
        kev_count=kev_count,
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
        f"CVE package: {len(rows)} cves ({kev_count} KEV, "
        f"{manifest['counts']['rejected']} rejected), {len(changes)} change events -> {out} "
        f"(signed={'yes' if args.signature and args.signer_id else 'NO — verifier will fail closed'})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
