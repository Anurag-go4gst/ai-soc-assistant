#!/usr/bin/env python3
"""Evaluate 105-question shadow route governance (no live MCP / no live LLM)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
_BACKEND = _REPO / "backend"
sys.path.insert(0, str(_BACKEND))

from app.config import settings  # noqa: E402
from app.evals.stage3l_105_shadow_eval import (  # noqa: E402
    run_105_shadow_eval,
    write_eval_outputs,
)

DEFAULT_MAP = _REPO / "docs" / "stage3l_s6_105_question_operation_map.json"
DEFAULT_OUT_DIR = _REPO / "docs" / "evals" / "out"


def _assert_eval_guards() -> None:
    if settings.route_authority_operation_authoritative_enabled:
        raise RuntimeError(
            "ROUTE_AUTHORITY_OPERATION_AUTHORITATIVE_ENABLED must be false for 105-Q eval",
        )
    if settings.mcp_global_execution_enabled:
        raise RuntimeError("MCP_GLOBAL_EXECUTION_ENABLED must be false for 105-Q eval")
    if settings.demo_llm_shadow_enabled:
        raise RuntimeError("DEMO_LLM_SHADOW_ENABLED must be false for 105-Q eval")


def _optional_route_skill_smoke(query: str) -> dict:
    """Optional smoke: full route_skill stack with deterministic_only (still no live LLM)."""
    import app.config as config_module
    from app.routing.skill_router import route_skill

    saved_mode = settings.routing_mode
    saved_shadow = settings.routing_llm_shadow_enabled
    try:
        config_module.settings.routing_mode = "deterministic_only"
        config_module.settings.routing_llm_shadow_enabled = False
        return route_skill(query, trace_id="stage3l-105-eval-smoke")
    finally:
        config_module.settings.routing_mode = saved_mode
        config_module.settings.routing_llm_shadow_enabled = saved_shadow


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--map",
        type=Path,
        default=DEFAULT_MAP,
        help="S6.2 105-question operation map JSON",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=DEFAULT_OUT_DIR,
        help="Directory for JSON + markdown outputs",
    )
    parser.add_argument(
        "--json-name",
        default="stage3l_105_shadow_eval.json",
        help="JSON output filename under --out-dir",
    )
    parser.add_argument(
        "--markdown-name",
        default="stage3l_105_shadow_eval.md",
        help="Markdown output filename under --out-dir",
    )
    parser.add_argument(
        "--no-coe-signoff",
        action="store_true",
        help="Evaluate promoted rows without COE sign-off recorded on authority gates",
    )
    parser.add_argument(
        "--route-skill-smoke",
        action="store_true",
        help="Run route_skill once on first map question (deterministic_only; no /chat HTTP)",
    )
    parser.add_argument(
        "--json-stdout",
        action="store_true",
        help="Also print full eval JSON to stdout",
    )
    args = parser.parse_args(argv)

    _assert_eval_guards()
    if not args.map.is_file():
        print(f"map_missing:{args.map}", file=sys.stderr)
        return 2

    summary = run_105_shadow_eval(args.map, coe_signoff=not args.no_coe_signoff)
    json_path = args.out_dir / args.json_name
    md_path = args.out_dir / args.markdown_name
    write_eval_outputs(summary, json_path=json_path, markdown_path=md_path)

    if args.route_skill_smoke:
        first = json.loads(args.map.read_text(encoding="utf-8"))["entries"][0]
        smoke = _optional_route_skill_smoke(str(first["question_text"]))
        print(f"route_skill_smoke_skill={smoke.get('skill')}")

    print(f"wrote:{json_path}")
    print(f"wrote:{md_path}")
    print(f"overall_pass={summary.overall_pass}")
    for bucket, stats in sorted(summary.buckets.items()):
        print(f"bucket:{bucket} pass={stats['pass']} fail={stats['fail']} total={stats['total']}")

    if args.json_stdout:
        print(json.dumps(summary.to_dict(), indent=2))

    return 0 if summary.overall_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
