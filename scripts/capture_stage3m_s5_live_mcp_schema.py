#!/usr/bin/env python3
"""Manual-only Stage 3M-S5 live Splunk MCP schema capture. Not for CI."""

from __future__ import annotations

import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from app.connectors.mcp.live_schema_capture import (  # noqa: E402
    DEFAULT_READ_ONLY_SPL,
    build_capture_document,
    preflight_live_capture,
    write_capture_file,
)

OUTPUT_PATH = REPO_ROOT / "docs" / "stage3m_s5_live_mcp_schema_capture.json"


def main() -> int:
    env = dict(os.environ)
    preflight = preflight_live_capture(env)
    if not preflight.ok:
        print(f"capture_blocked:{preflight.reason}", file=sys.stderr)
        return 2

    endpoint = env.get("STAGE3M_S5_MCP_ENDPOINT") or env.get("SPLUNK_MCP_BASE_URL", "")
    tool_name = env.get("STAGE3M_S5_MCP_TOOL", "run_splunk_query")

    # Live HTTP call is intentionally not implemented in automated paths.
    # Operators plug in COE-approved client here after RBAC review.
    print(
        "live_mcp_http_not_implemented: configure COE client, then paste raw JSON via "
        "STAGE3M_S5_RAW_FIXTURE_PATH or extend this script under change control.",
        file=sys.stderr,
    )
    fixture_path = env.get("STAGE3M_S5_RAW_FIXTURE_PATH", "").strip()
    if not fixture_path:
        return 2

    import json

    raw_payload = json.loads(Path(fixture_path).read_text(encoding="utf-8"))
    document = build_capture_document(
        raw_payload=raw_payload,
        endpoint=str(endpoint),
        tool_name=str(tool_name),
        coe_reviewed=False,
    )
    write_capture_file(OUTPUT_PATH, document)
    print(f"wrote:{OUTPUT_PATH}")
    print(f"query_policy_spl:{DEFAULT_READ_ONLY_SPL}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
