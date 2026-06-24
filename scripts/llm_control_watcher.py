#!/usr/bin/env python3
"""Host-side LLM control watcher — applies UI/API control requests via systemctl.

The Dockerized backend cannot (and must not) touch host systemd. It enqueues a
control request as a JSON sentinel in a shared directory; this watcher runs ON THE
HOST, polls that directory, executes ``systemctl <action> llama-server.service``, and
writes back ``last_result.json``. Run it as a host systemd service or a cron loop.

Only ``restart`` / ``stop`` / ``start`` on the single configured unit are permitted —
never arbitrary commands.

Usage (host):
  AI_SOC_LLM_CONTROL_DIR=/srv/ai-soc/llm-control \
    python3 scripts/llm_control_watcher.py --once        # apply pending then exit
  python3 scripts/llm_control_watcher.py --interval 5    # poll loop
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
from pathlib import Path

SERVICE = os.getenv("AI_SOC_LLM_SERVICE", "llama-server.service")
ALLOWED = {"restart", "stop", "start"}
REQUEST_PREFIX = "request-"
RESULT_FILE = "last_result.json"


def _control_dir() -> Path:
    raw = (os.getenv("AI_SOC_LLM_CONTROL_DIR") or "").strip()
    if not raw:
        raise SystemExit("AI_SOC_LLM_CONTROL_DIR not set")
    path = Path(raw)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _apply(action: str) -> dict:
    if action not in ALLOWED:
        return {"ok": False, "error": "invalid_action"}
    for cmd in (["sudo", "systemctl", action, SERVICE], ["systemctl", action, SERVICE]):
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue
        if proc.returncode == 0:
            return {"ok": True, "cmd": " ".join(cmd)}
    return {"ok": False, "error": "systemctl_failed"}


def _write_result(directory: Path, record: dict) -> None:
    target = directory / RESULT_FILE
    tmp = target.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(record), encoding="utf-8")
    os.replace(tmp, target)


def process_pending(directory: Path) -> int:
    applied = 0
    for req in sorted(directory.glob(f"{REQUEST_PREFIX}*.json")):
        try:
            record = json.loads(req.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            req.unlink(missing_ok=True)
            continue
        action = str(record.get("action") or "")
        result = _apply(action)
        _write_result(directory, {
            "request_id": record.get("request_id"),
            "action": action,
            "requested_by": record.get("requested_by"),
            "applied_at": time.time(),
            **result,
        })
        req.unlink(missing_ok=True)
        applied += 1
    return applied


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true", help="apply pending requests then exit")
    ap.add_argument("--interval", type=float, default=5.0, help="poll interval seconds")
    args = ap.parse_args()
    directory = _control_dir()
    if args.once:
        print(json.dumps({"applied": process_pending(directory)}))
        return 0
    while True:
        process_pending(directory)
        time.sleep(max(1.0, args.interval))


if __name__ == "__main__":
    raise SystemExit(main())
