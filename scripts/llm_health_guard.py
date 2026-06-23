#!/usr/bin/env python3
"""LLM health guard — measure generation throughput; restart the server if degraded.

The on-host Foundation-Sec 8B (llama-server) silently degrades over multi-day
uptime (observed 0.6 tok/s vs a clean ~5.7 tok/s), which times out the governed
LLM SPL producer. This guard fires a small completion, measures tokens/second,
and — when below a threshold — restarts the systemd unit and re-measures.

Usage:
  python3 scripts/llm_health_guard.py                 # check only, exit 1 if degraded
  python3 scripts/llm_health_guard.py --restart       # restart if degraded, then re-check
  python3 scripts/llm_health_guard.py --threshold 2.0 --restart

Exit codes: 0 healthy (after optional restart), 1 degraded/unreachable.
Intended for cron/manual use; safe to run before a live LLM probe.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import time
import urllib.error
import urllib.request

BASE_URL = "http://127.0.0.1:8081"
MODEL = "foundation-sec-1.1-8b-instruct-q8_0.gguf"
SERVICE = "llama-server.service"
DEFAULT_THRESHOLD = 2.0  # tok/s; observed bad=0.6, clean=~5.7
DEFAULT_MAX_WALL_SECONDS = 20.0  # catches queue/prompt-eval stalls hidden by generation tok/s
PROBE_TOKENS = 48


def _health_ok(timeout: int = 5) -> bool:
    try:
        with urllib.request.urlopen(f"{BASE_URL}/health", timeout=timeout) as resp:  # noqa: S310
            return resp.status == 200
    except (urllib.error.URLError, OSError):
        return False


def measure_tok_per_s(timeout: int = 120) -> dict:
    """Fire a small completion and return measured throughput (tok/s) + details."""
    if not _health_ok():
        return {"reachable": False, "tok_per_s": 0.0, "error": "health_check_failed"}
    body = json.dumps(
        {
            "model": MODEL,
            "messages": [{"role": "user", "content": "List three SOC triage steps, one short line each."}],
            "max_tokens": PROBE_TOKENS,
            "temperature": 0.0,
            "stream": False,
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        f"{BASE_URL}/v1/chat/completions",
        data=body,
        method="POST",
        headers={"Content-Type": "application/json", "Accept": "application/json"},
    )
    started = time.monotonic()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as resp:  # noqa: S310
            payload = json.loads(resp.read())
    except (urllib.error.URLError, OSError, json.JSONDecodeError) as exc:
        return {"reachable": True, "tok_per_s": 0.0, "error": f"{type(exc).__name__}: {exc}"}
    wall_s = time.monotonic() - started
    timings = payload.get("timings") or {}
    tok_per_s = timings.get("predicted_per_second")
    predicted = timings.get("predicted_n")
    if not isinstance(tok_per_s, (int, float)):
        # Fall back to a wall-clock estimate from usage when timings are absent.
        predicted = (payload.get("usage") or {}).get("completion_tokens") or 0
        tok_per_s = (predicted / wall_s) if wall_s > 0 else 0.0
    return {
        "reachable": True,
        "tok_per_s": round(float(tok_per_s), 2),
        "predicted_tokens": predicted,
        "wall_s": round(wall_s, 2),
    }


def restart_service() -> dict:
    for cmd in (["sudo", "systemctl", "restart", SERVICE], ["systemctl", "restart", SERVICE]):
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
            continue
        if proc.returncode == 0:
            # Wait for health to come back (bounded).
            deadline = time.monotonic() + 90
            while time.monotonic() < deadline:
                if _health_ok():
                    return {"restarted": True, "cmd": " ".join(cmd)}
                time.sleep(2)
            return {"restarted": True, "cmd": " ".join(cmd), "warning": "health_not_back_in_90s"}
    return {"restarted": False, "error": "restart_command_failed"}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD, help="min healthy tok/s")
    parser.add_argument(
        "--max-wall-seconds",
        type=float,
        default=DEFAULT_MAX_WALL_SECONDS,
        help="maximum acceptable end-to-end probe latency",
    )
    parser.add_argument("--probe-timeout", type=int, default=120, help="bounded completion probe timeout")
    parser.add_argument("--restart", action="store_true", help="restart the service if degraded")
    args = parser.parse_args()

    before = measure_tok_per_s(timeout=args.probe_timeout)
    result: dict = {
        "threshold": args.threshold,
        "max_wall_seconds": args.max_wall_seconds,
        "before": before,
    }
    healthy = (
        before.get("reachable")
        and before.get("tok_per_s", 0.0) >= args.threshold
        and before.get("wall_s", float("inf")) <= args.max_wall_seconds
    )

    if not healthy and args.restart:
        result["restart"] = restart_service()
        # Warm-up call is implicit in re-measure.
        result["after"] = measure_tok_per_s(timeout=args.probe_timeout)
        healthy = (
            result["after"].get("reachable")
            and result["after"].get("tok_per_s", 0.0) >= args.threshold
            and result["after"].get("wall_s", float("inf")) <= args.max_wall_seconds
        )

    result["healthy"] = bool(healthy)
    print(json.dumps(result, indent=2))
    return 0 if healthy else 1


if __name__ == "__main__":
    raise SystemExit(main())
