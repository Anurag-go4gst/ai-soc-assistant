#!/usr/bin/env python3
"""Capture Experience Center fixtures from the REAL (non-EC) /chat pipeline.

Each EC scenario is meant to be a frozen recording of a genuine
``user query -> final result`` run (plan Track B). This harness runs the live
pipeline once per curated question and writes a versioned capture artifact to
``backend/app/demo/captures/<scenario_id>.json`` that the EC serving path replays
with no live LLM/MCP call.

Capture conditions (plan B1):
  * ``ai_soc_live_chat_ec_parity_enabled=false`` so the run hits the live path, not
    the EC early-return.
  * LLM = real on-prem llama.cpp (Foundation-Sec) when ``--live-llm`` is set; the
    captured narration is then a genuine model answer.
  * MCP = simulated search lifecycle via an injected ``FakeTransport`` (real state
    machine, representative rows); ``transport=fake`` is recorded and
    ``live_mcp_called`` stays ``false``.

Latency (plan B2/B4): stage latencies are read from the trace spine when available,
else measured around the call; ``replayed_ms = min(recorded_ms, 6000)``.

Operator commands
-----------------
Offline / CI-safe validation (NO live model — uses deterministic narration):

    PYTHONPATH=backend:. python3 scripts/capture_ec_fixtures.py --mock-llm \
        --scenario failed_login_spike_app01

Full live capture of ONE scenario (real on-prem model; run off-peak / low-contention
per [[vps-llm-cpu-steal-contention]] — verify with a gen-probe + ``vmstat st`` first):

    AI_SOC_LLM_FINAL_SYNTHESIS_ENABLED=true AI_SOC_LLM_LIVE_SYNTHESIS_ENABLED=true \
        PYTHONPATH=backend:. python3 scripts/capture_ec_fixtures.py --live-llm \
        --scenario failed_login_spike_app01

Capture all curated scenarios (live; slow — do this only off the blocking demo path):

    AI_SOC_LLM_FINAL_SYNTHESIS_ENABLED=true AI_SOC_LLM_LIVE_SYNTHESIS_ENABLED=true \
        PYTHONPATH=backend:. python3 scripts/capture_ec_fixtures.py --live-llm --all

Re-capture one scenario after the pipeline improves or at Splunk MCP go-live
(swap ``FakeTransport`` -> real transport there): pass ``--scenario`` again.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND = REPO_ROOT / "backend"
for path in (str(BACKEND), str(REPO_ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)

from app.demo.capture_loader import (  # noqa: E402
    CAPTURE_SCHEMA_VERSION,
    CAPTURES_DIR,
    MAX_REPLAYED_STAGE_MS,
)
from app.demo.scenarios import SCENARIOS  # noqa: E402

# Body keys that the EC re-stamps per run; never freeze them into an artifact.
_VOLATILE_KEYS = ("trace_id", "turn_id", "timestamp")

_FAKE_ROWS_BY_SKILL = {
    "attack_discovery": [
        {"index": "pgcil_soc", "sourcetype": "pgcil:auth", "host": "APP-01", "src": "10.10.4.21", "action": "failure", "fail_count": 42},
        {"index": "pgcil_soc", "sourcetype": "pgcil:auth", "host": "APP-01", "src": "10.10.4.22", "action": "failure", "fail_count": 31},
    ],
    "spl_generation": [
        {"user": "svc_grid_ops", "host": "APP-01", "fail_count": 58, "success_count": 1},
    ],
}


def _git_sha() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )
        return out.stdout.strip()
    except (subprocess.SubprocessError, OSError):
        return "unknown"


def _strip_volatile(body: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of the response body without re-stamped id/timestamp keys."""
    return {key: value for key, value in body.items() if key not in _VOLATILE_KEYS}


def _stage_latencies_from_trace(trace_id: str, *, fallback_total_ms: int) -> list[dict[str, Any]]:
    """Read per-node durations from the trace spine; fall back to a single measured stage."""
    try:
        from app.connectors.telemetry.read_store import fetch_trace_timeline

        timeline = fetch_trace_timeline(trace_id)
    except Exception:  # noqa: BLE001 - telemetry read is best-effort during capture
        timeline = None

    stages: list[dict[str, Any]] = []
    events = (timeline or {}).get("events") if isinstance(timeline, dict) else None
    for event in events or []:
        if not isinstance(event, dict):
            continue
        duration = event.get("duration_ms")
        if not isinstance(duration, (int, float)):
            duration = (event.get("payload") or {}).get("duration_ms") if isinstance(event.get("payload"), dict) else None
        if not isinstance(duration, (int, float)):
            continue
        name = str(event.get("name") or event.get("step") or event.get("node") or "stage")
        stages.append(
            {
                "stage": name,
                "recorded_ms": int(duration),
                "replayed_ms": min(int(duration), MAX_REPLAYED_STAGE_MS),
            }
        )
    if stages:
        return stages
    # No trace spine (e.g. telemetry disabled): record one measured end-to-end stage.
    return [
        {
            "stage": "end_to_end",
            "recorded_ms": int(fallback_total_ms),
            "replayed_ms": min(int(fallback_total_ms), MAX_REPLAYED_STAGE_MS),
        }
    ]


def _prompt_hash(query: str) -> str:
    return hashlib.sha256(query.encode("utf-8")).hexdigest()[:16]


def capture_scenario(scenario_id: str, *, mock_llm: bool, model_id: str) -> dict[str, Any]:
    """Run the real pipeline once for ``scenario_id`` and build a capture artifact."""
    scenario = SCENARIOS[scenario_id]

    # Hit the live path, never the EC early-return.
    from app.config import settings

    settings.ai_soc_live_chat_ec_parity_enabled = False

    from app.connectors.mcp.splunk_mcp import set_search_transport_factory
    from app.schemas.requests import ChatRequest

    # Import the FakeTransport from the test module so capture uses the exact same
    # real lifecycle the suite verifies (submit -> bounded poll -> fetch).
    from app.tests.test_splunk_mcp_transport import FakeTransport

    rows = _FAKE_ROWS_BY_SKILL.get(scenario.expected_skill, [{"_time": "2026-06-24T00:00:00Z", "count": 1}])
    set_search_transport_factory(lambda: FakeTransport(["running", "done"], rows=rows))
    try:
        from app.chat.pipeline import build_live_chat_response

        request = ChatRequest(message=scenario.query, session_id=f"capture-{scenario_id}")
        start = time.monotonic()
        response = build_live_chat_response(request, session_role="soc_lead")
        elapsed_ms = int((time.monotonic() - start) * 1000)
    finally:
        set_search_transport_factory(None)

    body = response.model_dump() if hasattr(response, "model_dump") else dict(response)
    trace_id = str(body.get("trace_id") or "")
    final_response = _strip_volatile(body)

    artifact = {
        "schema_version": CAPTURE_SCHEMA_VERSION,
        "scenario_id": scenario_id,
        "final_response": final_response,
        "stage_latencies": _stage_latencies_from_trace(trace_id, fallback_total_ms=elapsed_ms),
        "provenance": {
            "model_id": "mock_deterministic" if mock_llm else model_id,
            "captured_at": datetime.now(UTC).isoformat(),
            "git_sha": _git_sha(),
            "prompt_hash": _prompt_hash(scenario.query),
            "transport": "fake",
            # The model WAS called at capture only when live synthesis ran (not --mock-llm).
            "live_llm_called": not mock_llm,
            "live_mcp_called": False,
        },
    }
    return artifact


def write_artifact(scenario_id: str, artifact: dict[str, Any]) -> Path:
    """Persist the artifact and validate it round-trips through the strict loader."""
    CAPTURES_DIR.mkdir(parents=True, exist_ok=True)
    path = CAPTURES_DIR / f"{scenario_id}.json"
    path.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    # Fail loudly if what we wrote cannot be loaded back (CI/operator safety).
    from app.demo.capture_loader import load_capture_artifact

    load_capture_artifact(scenario_id)
    return path


def _resolve_scenarios(args: argparse.Namespace) -> list[str]:
    if args.all:
        return list(SCENARIOS.keys())
    if args.scenario:
        if args.scenario not in SCENARIOS:
            raise SystemExit(f"unknown scenario '{args.scenario}'")
        return [args.scenario]
    raise SystemExit("specify --scenario <id> or --all")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", help="capture a single scenario id")
    parser.add_argument("--all", action="store_true", help="capture every curated scenario")
    parser.add_argument(
        "--mock-llm",
        action="store_true",
        help="offline/CI mode: do NOT call the live model (deterministic narration)",
    )
    parser.add_argument(
        "--live-llm",
        action="store_true",
        help="live mode: expect real on-prem model output (set synthesis flags in env)",
    )
    parser.add_argument(
        "--model-id",
        default="foundation-sec-1.1-8b-instruct-q8_0",
        help="model id stamped into provenance for live captures",
    )
    args = parser.parse_args(argv)

    if args.mock_llm and args.live_llm:
        raise SystemExit("--mock-llm and --live-llm are mutually exclusive")
    mock_llm = not args.live_llm  # default to safe offline mode

    scenario_ids = _resolve_scenarios(args)
    for scenario_id in scenario_ids:
        artifact = capture_scenario(scenario_id, mock_llm=mock_llm, model_id=args.model_id)
        path = write_artifact(scenario_id, artifact)
        stage_count = len(artifact["stage_latencies"])
        print(
            f"captured {scenario_id} -> {path} "
            f"(transport=fake, live_llm={'no' if mock_llm else 'yes'}, stages={stage_count})"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
