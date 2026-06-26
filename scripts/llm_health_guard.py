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
# Stream-measure the rate from the first few tokens so a slow-but-alive model
# (e.g. ~1 tok/s under CPU steal) reports its TRUE rate fast, instead of waiting
# for a large completion and timing out — which used to read as a false 0.0.
STREAM_SAMPLE_TOKENS = 12
PROBE_TOKENS = 16


def _health_ok(timeout: int = 5) -> bool:
    try:
        with urllib.request.urlopen(f"{BASE_URL}/health", timeout=timeout) as resp:  # noqa: S310
            return resp.status == 200
    except (urllib.error.URLError, OSError):
        return False


def measure_tok_per_s(timeout: int = 120) -> dict:
    """Stream a small completion and measure generation rate from inter-token timing.

    Returns ``tok_per_s`` as a float on success, or ``None`` when the rate could not
    be measured (timeout / transport / no tokens) — ``None`` means UNKNOWN, never to
    be confused with a real 0.0. A live-but-slow model yields its true low rate; only
    an actually unreachable endpoint reports ``reachable: False``.
    """
    if not _health_ok():
        return {"reachable": False, "tok_per_s": None, "status": "unreachable", "error": "health_check_failed"}
    body = json.dumps(
        {
            "model": MODEL,
            "messages": [{"role": "user", "content": "List three SOC triage steps, one short line each."}],
            "max_tokens": PROBE_TOKENS,
            "temperature": 0.0,
            "stream": True,
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        f"{BASE_URL}/v1/chat/completions",
        data=body,
        method="POST",
        headers={"Content-Type": "application/json", "Accept": "application/json"},
    )
    started = time.monotonic()
    first_token_at: float | None = None
    token_times: list[float] = []
    try:
        with urllib.request.urlopen(request, timeout=timeout) as resp:  # noqa: S310
            for raw in resp:
                line = raw.decode("utf-8", "replace").strip()
                if not line.startswith("data:"):
                    continue
                data = line[len("data:"):].strip()
                if data == "[DONE]":
                    break
                try:
                    delta = json.loads(data)["choices"][0].get("delta") or {}
                except (json.JSONDecodeError, KeyError, IndexError):
                    continue
                if delta.get("content"):
                    now = time.monotonic()
                    if first_token_at is None:
                        first_token_at = now
                    token_times.append(now)
                    if len(token_times) >= STREAM_SAMPLE_TOKENS:
                        break
    except (urllib.error.URLError, OSError) as exc:
        # Timeout/transport during streaming: rate is UNKNOWN, not zero. Preserve any
        # partial sample we did collect so a very slow model still reports a real rate.
        if len(token_times) < 2:
            return {"reachable": True, "tok_per_s": None, "status": "probe_timeout",
                    "wall_s": round(time.monotonic() - started, 2), "error": f"{type(exc).__name__}: {exc}"}

    wall_s = round(time.monotonic() - started, 2)
    if len(token_times) < 2:
        # Reached end-of-stream with too few tokens to time a rate.
        return {"reachable": True, "tok_per_s": None, "status": "no_tokens", "wall_s": wall_s}
    gen_span = token_times[-1] - token_times[0]
    tok_per_s = round((len(token_times) - 1) / gen_span, 2) if gen_span > 0 else None
    return {
        "reachable": True,
        "tok_per_s": tok_per_s,
        "status": "measured",
        "sampled_tokens": len(token_times),
        "prompt_eval_s": round((first_token_at - started), 2) if first_token_at else None,
        "wall_s": wall_s,
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


def assess_health(measure: dict, *, threshold: float, max_wall_seconds: float) -> tuple[bool, str]:
    """Classify a measurement into (healthy, reason).

    Distinguishes the states the old code collapsed into a false 0.0:
      - ``unreachable``   — endpoint down.
      - ``rate_unknown``  — probe timed out / no tokens; throughput UNKNOWN, not zero.
      - ``slow``          — a real measured rate below threshold (legit degraded).
      - ``prompt_stall``  — first token took longer than the wall budget.
      - ``ok``            — measured rate >= threshold.
    """
    if not measure.get("reachable"):
        return False, "unreachable"
    rate = measure.get("tok_per_s")
    if rate is None:
        return False, measure.get("status") or "rate_unknown"
    # Prompt-eval/queue stall is a separate signal from generation rate.
    stall = measure.get("prompt_eval_s")
    if stall is None:
        stall = measure.get("wall_s")
    if stall is not None and stall > max_wall_seconds:
        return False, "prompt_stall"
    if rate < threshold:
        return False, "slow"
    return True, "ok"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD, help="min healthy tok/s")
    parser.add_argument(
        "--max-wall-seconds",
        type=float,
        default=DEFAULT_MAX_WALL_SECONDS,
        help="maximum acceptable prompt-eval/probe latency before first token",
    )
    parser.add_argument("--probe-timeout", type=int, default=120, help="bounded completion probe timeout")
    parser.add_argument("--restart", action="store_true", help="restart the service if degraded")
    args = parser.parse_args()

    before = measure_tok_per_s(timeout=args.probe_timeout)
    healthy, reason = assess_health(before, threshold=args.threshold, max_wall_seconds=args.max_wall_seconds)
    result: dict = {
        "threshold": args.threshold,
        "max_wall_seconds": args.max_wall_seconds,
        "before": before,
        "reason": reason,
    }

    if not healthy and args.restart:
        result["restart"] = restart_service()
        after = measure_tok_per_s(timeout=args.probe_timeout)  # warm-up implicit
        result["after"] = after
        healthy, reason = assess_health(after, threshold=args.threshold, max_wall_seconds=args.max_wall_seconds)
        result["reason"] = reason

    result["healthy"] = bool(healthy)
    print(json.dumps(result, indent=2))
    return 0 if healthy else 1


if __name__ == "__main__":
    raise SystemExit(main())
