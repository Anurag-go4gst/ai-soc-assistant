#!/usr/bin/env python3
"""Tier-D answer-quality eval over the sentinel set (T5.1, plan rev 3).

Runs every sentinel question through the in-process chat pipeline (pinned
sentinel posture) and applies the deterministic quality checks to each final
payload. Definitive verdict per docs/evals/EVAL_CONTRACT.md.

Usage:
  PYTHONPATH=backend:. python3 scripts/eval_answer_quality.py --check
  PYTHONPATH=backend:. python3 scripts/eval_answer_quality.py --json out.json
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
for _path in (REPO_ROOT / "backend", REPO_ROOT):
    _text = str(_path)
    if _text not in sys.path:
        sys.path.insert(0, _text)

from app.api.routes_chat import chat  # noqa: E402
from app.evals.golden_answer_runner import _model_to_dict  # noqa: E402
from app.evals.sentinel_eval import load_sentinel_rows, sentinel_runtime  # noqa: E402
from app.quality.answer_quality_checks import run_answer_quality_checks  # noqa: E402
from app.schemas.requests import ChatRequest  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="exit 1 if any row fails any check")
    parser.add_argument("--json", type=Path, default=None, help="write per-row check results JSON")
    args = parser.parse_args()

    rows = load_sentinel_rows()
    started = time.monotonic()
    results: dict[str, list[dict[str, object]]] = {}
    failures: list[str] = []
    failed_rows: set[str] = set()
    for row in rows:
        key = row["key"]
        try:
            import uuid

            with sentinel_runtime():
                payload = _model_to_dict(
                    chat(ChatRequest(message=row["question"], session_id=f"aq-{uuid.uuid4()}"))
                )
            checks = run_answer_quality_checks(payload)
        except Exception as exc:
            results[key] = [
                {"check_id": "pipeline", "passed": False, "reason": f"{type(exc).__name__}: {exc}"}
            ]
            failures.append(f"{key}: pipeline raised {type(exc).__name__}: {exc}")
            failed_rows.add(key)
            continue
        results[key] = [check.to_dict() for check in checks]
        for check in checks:
            if not check.passed:
                failures.append(f"{key}.{check.check_id}: {check.reason}")
                failed_rows.add(key)
    elapsed = time.monotonic() - started

    if args.json:
        args.json.write_text(json.dumps(results, indent=2, sort_keys=True), encoding="utf-8")
        print(f"wrote {args.json}")

    total = len(rows)
    if failures:
        print(f"FAILURES ({len(failures)}):")
        for item in failures:
            print(f"  - {item}")
        print(f"RESULT: FAIL ({total - len(failed_rows)}/{total} rows, {elapsed:.1f}s)")
        return 1 if args.check else 0
    print(f"RESULT: PASS ({total}/{total} rows, {elapsed:.1f}s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
