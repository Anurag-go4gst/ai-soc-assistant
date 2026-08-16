#!/usr/bin/env python3
"""Splunk MCP COE qualification probe.

--check   Configuration/contract/readiness only. NO live MCP connection.
--live    COE ONLY. Requires AI_SOC_COE_LIVE_MCP_QUALIFICATION=1.
          Never claims LIVE_MCP_PROVEN from this VPS.

Usage:
    PYTHONPATH=backend:. python3 scripts/eval_splunk_mcp_coe_qualification.py --check
    AI_SOC_COE_LIVE_MCP_QUALIFICATION=1 PYTHONPATH=backend:. python3 scripts/eval_splunk_mcp_coe_qualification.py --live
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
for _path in (ROOT / "backend", ROOT):
    text = str(_path)
    if text not in sys.path:
        sys.path.insert(0, text)

from app.connectors.mcp.coe_qualification import (  # noqa: E402
    COE_LIVE_ENV,
    evaluate_splunk_mcp_coe_qualification,
)
from app.connectors.mcp.splunk_mcp_readiness import is_allowed_read_tool, is_disallowed_tool  # noqa: E402

OUT_DEFAULT = ROOT / "docs" / "evals" / "splunk_mcp_coe_qualification.json"


def main() -> int:
    parser = argparse.ArgumentParser(description="Splunk MCP COE qualification (config/contract only unless --live on COE).")
    parser.add_argument("--check", action="store_true", help="No network. Config/contract readiness.")
    parser.add_argument("--live", action="store_true", help="COE only. Refuses without AI_SOC_COE_LIVE_MCP_QUALIFICATION=1.")
    parser.add_argument("--out", type=Path, default=OUT_DEFAULT)
    args = parser.parse_args()
    if not args.check and not args.live:
        parser.error("specify --check or --live")

    report = evaluate_splunk_mcp_coe_qualification(live=bool(args.live))
    if args.live:
        live_block = _live_gate(report)
        report = {**report, **live_block}

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(_summary(report), indent=2, sort_keys=True))
    if report.get("LIVE_MCP_PROVEN") is True:
        print("REFUSING: LIVE_MCP_PROVEN must never be claimed by this probe without a real COE server.", file=sys.stderr)
        return 2
    if args.live and report.get("live_status") == "COE_ONLY_PENDING":
        return 2
    if report.get("STATUS") != "READY_FOR_COE_CONFIGURATION":
        return 1
    return 0


def _live_gate(report: dict[str, Any]) -> dict[str, Any]:
    opt_in = os.environ.get(COE_LIVE_ENV, "").strip().lower() in {"1", "true", "yes", "on"}
    if not opt_in:
        return {
            "mcp_called": False,
            "live_status": "COE_ONLY_PENDING",
            "LIVE_MCP_STATUS": "UNPROVEN",
            "LIVE_MCP_PROVEN": False,
            "live_block_reason": f"{COE_LIVE_ENV} is not set — --live is COE only and must not run from this VPS",
        }
    # Opt-in is present. Still do not run a live connection from a generic host
    # unless the production pipeline is the caller. Handshake + one /chat turn
    # belong on the COE Splunk MCP Server, not this VPS.
    return {
        "mcp_called": False,
        "live_status": "COE_ONLY_PENDING",
        "LIVE_MCP_STATUS": "UNPROVEN",
        "LIVE_MCP_PROVEN": False,
        "live_steps_required": [
            "TLS/connectivity",
            "MCP initialize/session establishment",
            "tools/list",
            "compare discovered enabled tools with approved read-only tool policy",
            "verify required tool permissions",
            "one controlled read-only qualification through the production /chat pipeline",
        ],
        "approved_read_only_policy": {
            "allowed_if_named": "splunk_run_query (and documented aliases)",
            "blocked_unknown": not is_allowed_read_tool("unknown_custom_tool"),
            "blocked_mutating": is_disallowed_tool("create_kvstore_collection"),
            "blocked_phase10": is_disallowed_tool("phase10_remediate_host"),
        },
    }


def _summary(report: dict[str, Any]) -> dict[str, Any]:
    return {
        "STATUS": report.get("STATUS"),
        "MCP_CONFIG_READY": report.get("MCP_CONFIG_READY"),
        "MCP_CONTRACT_READY": report.get("MCP_CONTRACT_READY"),
        "MISSING": report.get("MISSING"),
        "LIVE_MCP_STATUS": report.get("LIVE_MCP_STATUS"),
        "LIVE_MCP_PROVEN": report.get("LIVE_MCP_PROVEN"),
        "live_status": report.get("live_status"),
        "live_block_reason": report.get("live_block_reason"),
        "future_live_command": report.get("future_live_command"),
    }


if __name__ == "__main__":
    raise SystemExit(main())
