#!/usr/bin/env python3
"""Plan 7 D1 — reliability and failure behaviour on the target posture.

Runs **inside the backend container** (D0 established that the dispatch seam is
unreachable outside it). Fault injection happens at the existing provider/client
seam — the real service is never taken down, and the Cisco model is never
restarted: `architecture.md` makes model restart human-only.

Each class produces one measured row. Nothing here implements Plan 8 REL0: no
circuit breaker, no backpressure subsystem, no restart controller, no new service.

    docker compose exec -T backend python /tmp/d1.py --out /tmp/d1.json
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import threading
import time
from pathlib import Path
from typing import Any

for _path in ("/app", "/workspace", "/workspace/backend"):
    if _path not in sys.path:
        sys.path.append(_path)

RECORDED_T4 = {
    "normalized_goal": "identify the activity the analyst is asking about",
    "evidence_requirements": ["events relevant to the described activity"],
    "ambiguity_state": "unambiguous",
    "clarification_required": False,
    "confidence": 0.9,
}

SPL_QUERY = "Draft a search for failed admin logons on the domain controllers in the last 24 hours"
T4_QUERY = "signs that something is moving sideways through the estate"


def _host_state() -> dict[str, Any]:
    state: dict[str, Any] = {}
    try:
        info = {}
        for line in Path("/proc/meminfo").read_text().splitlines():
            parts = line.split()
            if len(parts) >= 2 and parts[1].isdigit():
                info[parts[0].rstrip(":")] = int(parts[1])
        state["mem_available_mb"] = info.get("MemAvailable", 0) // 1024
        state["swap_free_mb"] = info.get("SwapFree", 0) // 1024
    except OSError:
        pass
    try:
        state["loadavg"] = Path("/proc/loadavg").read_text().split()[:3]
    except OSError:
        pass
    return state


def _quiet_llm() -> None:
    from app.config import settings

    for name in (
        "ai_soc_llm_final_synthesis_enabled",
        "ai_soc_llm_live_synthesis_enabled",
        "ai_soc_llm_intent_advisor_enabled",
        "ai_soc_llm_evidence_observer_enabled",
        "ai_soc_llm_spl_fallback_enabled",
    ):
        if hasattr(settings, name):
            setattr(settings, name, False)


def _install_t4(provider) -> None:
    from app.chat import semantic_t4_understanding as t4

    t4._live_single_hop_provider = provider  # noqa: SLF001 - container-local test seam


def _recorded_provider(_query, _contract) -> str:
    return json.dumps(RECORDED_T4)


def _ask(query: str) -> dict[str, Any]:
    from app.graph.resource_planner_graph import run_chat_via_resource_planner_graph
    from app.schemas.requests import ChatRequest

    started = time.monotonic()
    response = run_chat_via_resource_planner_graph(ChatRequest(message=query))
    payload = response.model_dump()
    workflow = payload.get("workflow_plan") or {}
    cp = payload.get("control_plane_trace") or {}
    dispatch = cp.get("plan_dispatch") or {}
    resolved = cp.get("resolved_query") or {}
    semantic = resolved.get("semantic_t4") or {}
    execution = payload.get("execution") or {}
    spl = payload.get("spl_validation") or {}
    return {
        "wall_ms": int((time.monotonic() - started) * 1000),
        "trace_id": payload.get("trace_id"),
        "route": workflow.get("skill"),
        "execution_enabled": workflow.get("execution_enabled"),
        "dispatch_source": dispatch.get("dispatch_source"),
        "dispatch_schedule": dispatch.get("dispatch_schedule"),
        "t4_invoked": bool(semantic.get("invoked")),
        "t4_accepted": bool(semantic.get("accepted")),
        "t4_timed_out": bool(semantic.get("timed_out")),
        "t4_failure_kind": semantic.get("failure_kind"),
        "t4_rejected": semantic.get("rejected_reasons") or [],
        "t4_elapsed_ms": semantic.get("elapsed_ms"),
        "execution_eligible": execution.get("execution_eligible"),
        "mcp_status": (execution.get("mcp") or {}).get("status")
        if isinstance(execution.get("mcp"), dict)
        else execution.get("status"),
        "spl_approved": spl.get("approved"),
        "normalized_spl_present": bool(spl.get("normalized_spl")),
    }


def _side_effect_probe() -> dict[str, Any]:
    """Count side-effect-capable operations actually attempted."""
    from app.orchestration import mcp_execution_gate as gate

    counts = {"gate_calls": 0, "allowed": 0}
    real = gate.evaluate_mcp_execution

    def _counted(*a, **k):
        counts["gate_calls"] += 1
        result = real(*a, **k)
        payload = result if isinstance(result, dict) else getattr(result, "__dict__", {})
        if payload.get("allowed") or payload.get("status") == "executed":
            counts["allowed"] += 1
        return result

    gate.evaluate_mcp_execution = _counted
    return counts


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="/tmp/d1_reliability.json")
    args = parser.parse_args()

    _quiet_llm()
    from app.config import settings
    from app.llm.sidecar_governance import FAILURE_PROVIDER_UNAVAILABLE

    flags = {
        "resource_plan_execution": bool(settings.ai_soc_resource_plan_execution_enabled),
        "dispatch_v2": bool(settings.ai_soc_pipeline_dispatch_v2_enabled),
        "t4_enabled": bool(settings.ai_soc_t4_semantic_understanding_enabled),
        "t4_timeout_s": settings.ai_soc_t4_semantic_understanding_timeout_seconds,
        "live_capability_enforcement": bool(
            getattr(settings, "ai_soc_live_capability_enforcement_enabled", False)
        ),
        "mcp_mode": getattr(settings, "mcp_mode", None),
    }
    print("D1_FLAGS " + json.dumps(flags), flush=True)

    side_effects = _side_effect_probe()
    rows: dict[str, Any] = {}

    def record(name: str, payload: dict[str, Any]) -> None:
        payload["host"] = _host_state()
        rows[name] = payload
        # Full payload: a truncated row cannot be reconstructed if the container
        # is recreated by the restart row before the artifact is copied out.
        print(f"D1_ROW {name} " + json.dumps(payload), flush=True)

    # --- 3. repeated identical requests --------------------------------------
    _install_t4(_recorded_provider)
    before = dict(side_effects)
    repeats = [_ask(SPL_QUERY) for _ in range(3)]
    record("repeated_identical", {
        "runs": repeats,
        "distinct_trace_ids": len({r["trace_id"] for r in repeats}),
        "routes": sorted({str(r["route"]) for r in repeats}),
        "schedules_identical": len({json.dumps(r["dispatch_schedule"]) for r in repeats}) == 1,
        "gate_calls_delta": side_effects["gate_calls"] - before["gate_calls"],
        "gate_allowed_delta": side_effects["allowed"] - before["allowed"],
    })

    # --- 2 + 10. concurrency and model-slot pressure -------------------------
    results: list[dict[str, Any]] = []
    lock = threading.Lock()

    def worker(query: str) -> None:
        try:
            row = _ask(query)
        except Exception as exc:  # noqa: BLE001 - a failure is data
            row = {"error": f"{type(exc).__name__}: {exc}"[:160]}
        with lock:
            results.append(row)

    before = dict(side_effects)
    threads = [threading.Thread(target=worker, args=(SPL_QUERY,)) for _ in range(3)]
    started = time.monotonic()
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    record("concurrency", {
        "concurrency": 3,
        "wall_ms": int((time.monotonic() - started) * 1000),
        "completed": sum(1 for r in results if not r.get("error")),
        "failed": sum(1 for r in results if r.get("error")),
        "distinct_trace_ids": len({r.get("trace_id") for r in results if r.get("trace_id")}),
        "gate_calls_delta": side_effects["gate_calls"] - before["gate_calls"],
        "gate_allowed_delta": side_effects["allowed"] - before["allowed"],
        "rows": results,
    })

    # Model-slot pressure: concurrent T4-tier turns against the single-flight guard.
    slot_results: list[dict[str, Any]] = []

    def slot_worker() -> None:
        try:
            row = _ask(T4_QUERY)
        except Exception as exc:  # noqa: BLE001
            row = {"error": f"{type(exc).__name__}: {exc}"[:160]}
        with lock:
            slot_results.append(row)

    threads = [threading.Thread(target=slot_worker) for _ in range(3)]
    started = time.monotonic()
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    record("model_slot_pressure", {
        "concurrency": 3,
        "wall_ms": int((time.monotonic() - started) * 1000),
        "slot_busy_notes": sum(1 for r in slot_results if "llm_model_slot_busy" in str(r)),
        "completed": sum(1 for r in slot_results if not r.get("error")),
        "rows": slot_results,
    })

    # --- 5. LLM unavailable ---------------------------------------------------
    def _unavailable(_query, _contract) -> str:
        raise ConnectionRefusedError("connection refused")

    _install_t4(_unavailable)
    before = dict(side_effects)
    row = _ask(T4_QUERY)
    row["gate_allowed_delta"] = side_effects["allowed"] - before["allowed"]
    record("llm_unavailable", row)

    # --- 6. malformed LLM output ---------------------------------------------
    _install_t4(lambda _q, _c: "I think you should look at DNS logs, but here is no JSON")
    record("llm_malformed_output", _ask(T4_QUERY))

    # --- 7. LLM timeout -------------------------------------------------------
    def _slow(_query, _contract) -> str:
        time.sleep(min(8.0, float(settings.ai_soc_t4_semantic_understanding_timeout_seconds) + 2))
        return json.dumps(RECORDED_T4)

    original_timeout = settings.ai_soc_t4_semantic_understanding_timeout_seconds
    settings.ai_soc_t4_semantic_understanding_timeout_seconds = 1.0
    _install_t4(_slow)
    try:
        record("llm_timeout", _ask(T4_QUERY))
    finally:
        settings.ai_soc_t4_semantic_understanding_timeout_seconds = original_timeout

    # --- 9. MCP unavailable ---------------------------------------------------
    from app.orchestration import mcp_execution_gate as gate

    _install_t4(_recorded_provider)
    real_gate = gate.evaluate_mcp_execution

    def _mcp_down(*a, **k):
        raise ConnectionError("mcp endpoint unavailable")

    gate.evaluate_mcp_execution = _mcp_down
    try:
        try:
            mcp_row = _ask("Investigate lateral movement from host WKS-4471 and show the events")
            mcp_row["raised_to_caller"] = False
        except Exception as exc:  # noqa: BLE001
            mcp_row = {"raised_to_caller": True, "error": f"{type(exc).__name__}: {exc}"[:160]}
        record("mcp_unavailable", mcp_row)
    finally:
        gate.evaluate_mcp_execution = real_gate

    # --- 4. latency -----------------------------------------------------------
    _install_t4(_recorded_provider)
    samples = [_ask(SPL_QUERY)["wall_ms"] for _ in range(5)]
    ordered = sorted(samples)
    record("latency", {
        "samples_ms": samples,
        "p50_ms": statistics.median(ordered),
        "p95_ms": ordered[max(0, int(round(0.95 * (len(ordered) - 1))))],
        "note": "orchestration latency with a recorded T4 proposal; not live-model latency",
    })

    payload = {
        "flags": flags,
        "side_effect_totals": side_effects,
        "rows": rows,
        "provider_unavailable_class": FAILURE_PROVIDER_UNAVAILABLE,
    }
    Path(args.out).write_text(json.dumps(payload, indent=2), "utf-8")
    print("D1_DONE " + json.dumps({"rows": len(rows), "out": args.out}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
