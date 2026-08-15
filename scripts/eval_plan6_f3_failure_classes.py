#!/usr/bin/env python3
"""Plan 6 F3 — observe failure-class behaviour on the persisted VPS profile.

Injections are transient and external to the app: they stop ``llama-server`` or
put a stub on the same host port the backend already points at. The persisted
env profile is never edited, so F3 keeps running *on* the production profile.

Records redacted slices only (route, gate decisions, degrade reason). Never
secrets, never SPL text, never MCP payloads.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
for _path in (REPO_ROOT / "backend", REPO_ROOT):
    _text = str(_path)
    if _text not in sys.path:
        sys.path.insert(0, _text)

ASK_CHAT = REPO_ROOT / "scripts" / "ask_chat.sh"
FETCH_BUNDLE = REPO_ROOT / "scripts" / "fetch_debug_bundle.sh"
OUT_DIR = REPO_ROOT / "docs" / "evals" / "plan6" / "runs" / "f3"
CHAT_BASE = os.environ.get("BASE", "http://127.0.0.1:8010")
LLM_SERVICE = "llama-server.service"
LLM_PORT = 8081
ASK_TIMEOUT_S = 300

QUESTION = "Summarize the current brute force alert and recommend next steps."


def _systemctl(action: str) -> dict[str, Any]:
    proc = subprocess.run(
        ["systemctl", action, LLM_SERVICE],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    return {"action": action, "exit": proc.returncode, "stderr": (proc.stderr or "")[:200]}


def _ask(question: str) -> dict[str, Any]:
    started = time.monotonic()
    try:
        proc = subprocess.run(
            [str(ASK_CHAT), question],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=ASK_TIMEOUT_S,
            check=False,
            env={**os.environ, "BASE": CHAT_BASE},
        )
    except subprocess.TimeoutExpired:
        # A client-side timeout is itself a recorded outcome, not a harness crash.
        return {
            "exit_code": None,
            "client_timeout_s": ASK_TIMEOUT_S,
            "wall_ms": int((time.monotonic() - started) * 1000),
            "trace_id": None,
        }
    wall_ms = int((time.monotonic() - started) * 1000)
    body = _last_json_object(proc.stdout or "")
    workflow = body.get("workflow_plan") if isinstance(body.get("workflow_plan"), dict) else {}
    sufficiency = (
        body.get("context_sufficiency")
        if isinstance(body.get("context_sufficiency"), dict)
        else {}
    )
    return {
        "exit_code": proc.returncode,
        "wall_ms": wall_ms,
        "trace_id": body.get("trace_id"),
        "route": workflow.get("skill") or body.get("route"),
        "answer_mode": sufficiency.get("answer_mode") or body.get("answer_mode"),
        "execution_enabled": workflow.get("execution_enabled"),
        "stderr_excerpt": (proc.stderr or "")[:200],
    }


def _last_json_object(stdout: str) -> dict[str, Any]:
    best: dict[str, Any] = {}
    depth = 0
    start = -1
    for index, char in enumerate(stdout):
        if char == "{":
            if depth == 0:
                start = index
            depth += 1
        elif char == "}" and depth:
            depth -= 1
            if depth == 0 and start >= 0:
                try:
                    parsed = json.loads(stdout[start : index + 1])
                except json.JSONDecodeError:
                    continue
                if isinstance(parsed, dict) and parsed.get("trace_id"):
                    best = parsed
    return best


def _debug_slice(trace_id: str | None) -> dict[str, Any]:
    if not trace_id:
        return {"debug_bundle": "absent"}
    proc = subprocess.run(
        [str(FETCH_BUNDLE), trace_id],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
        env={**os.environ, "BASE": CHAT_BASE},
    )
    try:
        bundle = json.loads((proc.stdout or "").strip())
    except json.JSONDecodeError:
        return {"bundle_parse_error": True}
    explain = bundle.get("explainability") if isinstance(bundle, dict) else {}
    summary = explain.get("debug_summary") if isinstance(explain, dict) else {}
    summary = summary if isinstance(summary, dict) else {}
    schedule = summary.get("schedule") if isinstance(summary.get("schedule"), dict) else {}
    resolved = (
        summary.get("resolved_query") if isinstance(summary.get("resolved_query"), dict) else {}
    )
    mcp = summary.get("mcp") if isinstance(summary.get("mcp"), dict) else {}
    hil = summary.get("hil") if isinstance(summary.get("hil"), dict) else {}
    return {
        "trace_id": trace_id,
        "qualification_tier": resolved.get("qualification_tier"),
        "semantic_t4": resolved.get("semantic_t4"),
        "degrade_reason": schedule.get("degrade_reason"),
        "phase_names": schedule.get("phase_names") or [],
        "inline_executed": schedule.get("inline_executed") or [],
        "mcp": {
            "status": mcp.get("status"),
            "allowed": mcp.get("allowed"),
            "block_reason": mcp.get("block_reason"),
        },
        "hil": {
            "kind": hil.get("kind"),
            "required": hil.get("required"),
            "reason": hil.get("reason"),
        },
        "execution_eligible": summary.get("execution_eligible"),
    }


class _StubHandler(BaseHTTPRequestHandler):
    mode = "malformed"
    delay_s = 0.0

    def do_POST(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        length = int(self.headers.get("Content-Length") or 0)
        if length:
            self.rfile.read(length)
        if self.delay_s:
            time.sleep(self.delay_s)
        payload = b'{"choices": [ {"message": {"content": "<<<not json'
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        self.send_response(200)
        self.send_header("Content-Length", "2")
        self.end_headers()
        self.wfile.write(b"{}")

    def log_message(self, *_args: Any) -> None:
        return


def _with_stub(delay_s: float) -> HTTPServer:
    _StubHandler.delay_s = delay_s
    server = HTTPServer(("0.0.0.0", LLM_PORT), _StubHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def run_llm_unavailable() -> dict[str, Any]:
    steps = [_systemctl("stop")]
    try:
        time.sleep(2)
        result = _ask(QUESTION)
    finally:
        steps.append(_systemctl("start"))
    return {"class": "llm_unavailable", "steps": steps, "chat": result,
            "debug": _debug_slice(result.get("trace_id"))}


def run_llm_malformed(delay_s: float, label: str) -> dict[str, Any]:
    steps = [_systemctl("stop")]
    server: HTTPServer | None = None
    try:
        time.sleep(2)
        server = _with_stub(delay_s)
        result = _ask(QUESTION)
    finally:
        if server is not None:
            server.shutdown()
            server.server_close()
        steps.append(_systemctl("start"))
    return {"class": label, "stub_delay_s": delay_s, "steps": steps, "chat": result,
            "debug": _debug_slice(result.get("trace_id"))}


def run_slot_pressure(n: int) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    lock = threading.Lock()

    def worker() -> None:
        row = _ask(QUESTION)
        row["debug"] = _debug_slice(row.get("trace_id"))
        with lock:
            results.append(row)

    threads = [threading.Thread(target=worker) for _ in range(n)]
    started = time.monotonic()
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    return {
        "class": "model_slot_pressure",
        "concurrency": n,
        "wall_ms": int((time.monotonic() - started) * 1000),
        "results": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--case",
        required=True,
        choices=["llm_unavailable", "llm_malformed", "llm_timeout", "slot_pressure"],
    )
    parser.add_argument("--concurrency", type=int, default=3)
    parser.add_argument("--stub-delay-s", type=float, default=180.0)
    parser.add_argument("--question", default=QUESTION)
    parser.add_argument("--label", default=None, help="artifact basename override")
    args = parser.parse_args()

    globals()["QUESTION"] = args.question

    if args.case == "llm_unavailable":
        payload = run_llm_unavailable()
    elif args.case == "llm_malformed":
        payload = run_llm_malformed(0.0, "llm_malformed_output")
    elif args.case == "llm_timeout":
        payload = run_llm_malformed(args.stub_delay_s, "llm_timeout")
    else:
        payload = run_slot_pressure(args.concurrency)

    payload["captured_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    payload["question_class"] = "llm_narrating" if args.label else "hil_short_path"
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / f"{args.label or args.case}.json"
    out_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"case": args.case, "artifact": str(out_path.relative_to(REPO_ROOT))}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
