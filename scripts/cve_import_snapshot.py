#!/usr/bin/env python3
"""Air-gapped CVE snapshot import verifier (plan WS-A A5).

Validates manifest + artifact SHA256 (+ signature/signer_id presence) for an
operator-supplied package directory. Does not copy or mutate artifacts.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.cve.manifest_verifier import verify_manifest  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify a governed CVE snapshot package")
    parser.add_argument("package_dir", help="Directory containing manifest.json and artifacts")
    parser.add_argument("--json", action="store_true", help="Emit JSON result")
    args = parser.parse_args()

    result = verify_manifest(args.package_dir)
    payload = {"ok": result.ok, "errors": list(result.errors), "snapshot_id": (result.manifest or {}).get("snapshot_id")}
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        if result.ok:
            print(f"OK snapshot_id={payload['snapshot_id']}")
        else:
            print("FAILED")
            for err in result.errors:
                print(f"  - {err}")
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
