#!/usr/bin/env python3
"""Phase 5 — build the LLM role scorecard from captured control_plane_trace JSONL.

Reads one JSON object per line. Each line is either a full chat response payload
(with a ``control_plane_trace`` key) or a bare ``control_plane_trace`` object.

Usage:
  PYTHONPATH=backend:. python3 scripts/build_llm_role_scorecard.py --input traces.jsonl
  PYTHONPATH=backend:. python3 scripts/build_llm_role_scorecard.py --input traces.jsonl --out docs/evals/llm_role_scorecard.json
  PYTHONPATH=backend:. python3 scripts/build_llm_role_scorecard.py --input traces.jsonl --check

--check exit codes: 0 = built and no role DEGRADED; 1 = a role is DEGRADED
(INSUFFICIENT_DATA is allowed pre-production — it only blocks a prod flag flip,
not CI). 2 = could not build (bad input).

COE rule: no production flag flip for a role until its verdict is HEALTHY.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
for _path in (REPO_ROOT / "backend", REPO_ROOT):
    _text = str(_path)
    if _text not in sys.path:
        sys.path.insert(0, _text)

from app.quality.llm_role_scorecard import (  # noqa: E402
    VERDICT_DEGRADED,
    build_llm_role_scorecard,
)

DEFAULT_OUT = REPO_ROOT / "docs" / "evals" / "llm_role_scorecard.json"


def _load_traces(path: Path) -> list[dict]:
    traces: list[dict] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(obj, dict):
                continue
            trace = obj.get("control_plane_trace") if "control_plane_trace" in obj else obj
            if isinstance(trace, dict):
                traces.append(trace)
    return traces


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the LLM role scorecard.")
    parser.add_argument("--input", required=True, help="JSONL of traces or chat payloads.")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="Scorecard JSON output path.")
    parser.add_argument("--check", action="store_true", help="Exit non-zero if any role is DEGRADED.")
    args = parser.parse_args(argv)

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"input not found: {input_path}", file=sys.stderr)
        return 2

    traces = _load_traces(input_path)
    scorecard = build_llm_role_scorecard(traces)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(scorecard, indent=2) + "\n", encoding="utf-8")

    degraded = [role for role, m in scorecard["roles"].items() if m["verdict"] == VERDICT_DEGRADED]
    print(
        json.dumps(
            {
                "sample_turns": scorecard["sample_turns"],
                "overall_verdict": scorecard["overall_verdict"],
                "degraded_roles": degraded,
                "out": str(out_path),
            }
        )
    )
    if args.check and degraded:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
