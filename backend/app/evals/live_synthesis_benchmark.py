"""Live synthesis baseline benchmark harness (workstream E phase 1).

Deterministic stub mode supports unit tests and CI-free verification.
Live HTTP probes require explicit operator opt-in outside this module.
"""

from __future__ import annotations

import statistics
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable

from app.synthesis.turn_timing import (
    RunKind,
    SynthesisPath,
    TurnOutcome,
    sanitize_turn_timing_payload,
)

PROBE_MATRIX_VERSION = "1"

# Closed case set for controlled baseline (sanitized ids only — no raw queries in artifacts).
DEFAULT_PROBE_MATRIX: tuple[dict[str, str], ...] = (
    {"case_id": "E-P1", "profile": "knowledge_recall", "run_kind": "cold"},
    {"case_id": "E-P2", "profile": "knowledge_recall", "run_kind": "warm"},
    {"case_id": "E-P3", "profile": "alert_summary", "run_kind": "cold"},
    {"case_id": "E-P4", "profile": "alert_summary", "run_kind": "warm"},
    {"case_id": "E-P5", "profile": "guided_investigation", "run_kind": "cold"},
    {"case_id": "E-P6", "profile": "spl_generation", "run_kind": "cold"},
)


@dataclass(frozen=True)
class BenchmarkProbeSpec:
    case_id: str
    profile: str
    run_kind: RunKind


@dataclass
class BenchmarkRunResult:
    case_id: str
    profile: str
    run_kind: str
    turn_timing: dict[str, Any]
    elapsed_ms: int
    error: str | None = None


@dataclass
class BenchmarkReport:
    harness: str = "live_synthesis_baseline"
    schema_version: str = "1"
    mode: str = "stub"
    probe_matrix_version: str = PROBE_MATRIX_VERSION
    started_at_unix: float = field(default_factory=time.time)
    completed_at_unix: float | None = None
    runs: list[BenchmarkRunResult] = field(default_factory=list)
    summary: dict[str, Any] = field(default_factory=dict)

    def to_sanitized_dict(self) -> dict[str, Any]:
        completed = self.completed_at_unix or time.time()
        payload = {
            "harness": self.harness,
            "schema_version": self.schema_version,
            "mode": self.mode,
            "probe_matrix_version": self.probe_matrix_version,
            "duration_seconds": round(completed - self.started_at_unix, 2),
            "run_count": len(self.runs),
            "error_count": sum(1 for row in self.runs if row.error),
            "runs": [
                {
                    "case_id": row.case_id,
                    "profile": row.profile,
                    "run_kind": row.run_kind,
                    "elapsed_ms": row.elapsed_ms,
                    "error": row.error,
                    "turn_timing": row.turn_timing,
                }
                for row in self.runs
            ],
            "summary": self.summary,
        }
        return sanitize_turn_timing_payload(payload)


def parse_probe_matrix(rows: list[dict[str, str]] | None = None) -> list[BenchmarkProbeSpec]:
    source = rows if rows is not None else list(DEFAULT_PROBE_MATRIX)
    specs: list[BenchmarkProbeSpec] = []
    for row in source:
        run_kind_raw = str(row.get("run_kind") or RunKind.UNKNOWN.value)
        try:
            run_kind = RunKind(run_kind_raw)
        except ValueError:
            run_kind = RunKind.UNKNOWN
        specs.append(
            BenchmarkProbeSpec(
                case_id=str(row["case_id"]),
                profile=str(row["profile"]),
                run_kind=run_kind,
            )
        )
    return specs


def _percentiles(values: list[int]) -> dict[str, int | None]:
    if not values:
        return {"p50": None, "p90": None, "p95": None}
    ordered = sorted(values)
    return {
        "p50": int(statistics.median(ordered)),
        "p90": int(statistics.quantiles(ordered, n=10)[8]) if len(ordered) >= 2 else ordered[-1],
        "p95": int(statistics.quantiles(ordered, n=20)[18]) if len(ordered) >= 2 else ordered[-1],
    }


def summarize_benchmark(report: BenchmarkReport) -> dict[str, Any]:
    ok_runs = [row for row in report.runs if row.error is None]
    e2e = [int(row.turn_timing.get("segments_ms", {}).get("end_to_end") or row.elapsed_ms) for row in ok_runs]
    endpoint = [
        int(row.turn_timing.get("segments_ms", {}).get("synthesis_endpoint") or 0)
        for row in ok_runs
        if row.turn_timing.get("segments_ms", {}).get("synthesis_endpoint") is not None
    ]
    cold_e2e = [
        int(row.turn_timing.get("segments_ms", {}).get("end_to_end") or row.elapsed_ms)
        for row in ok_runs
        if row.run_kind == RunKind.COLD.value
    ]
    warm_e2e = [
        int(row.turn_timing.get("segments_ms", {}).get("end_to_end") or row.elapsed_ms)
        for row in ok_runs
        if row.run_kind == RunKind.WARM.value
    ]
    timeout_count = sum(1 for row in ok_runs if row.turn_timing.get("outcome") == TurnOutcome.TIMEOUT.value)
    fallback_count = sum(1 for row in ok_runs if row.turn_timing.get("fallback_used") is True)
    path_counts: dict[str, int] = {}
    for row in ok_runs:
        path = str(row.turn_timing.get("synthesis_path") or SynthesisPath.SKIPPED.value)
        path_counts[path] = path_counts.get(path, 0) + 1
    return {
        "end_to_end_ms": _percentiles(e2e),
        "synthesis_endpoint_ms": _percentiles(endpoint),
        "cold_end_to_end_ms": _percentiles(cold_e2e),
        "warm_end_to_end_ms": _percentiles(warm_e2e),
        "timeout_rate": round(timeout_count / len(ok_runs), 4) if ok_runs else None,
        "fallback_rate": round(fallback_count / len(ok_runs), 4) if ok_runs else None,
        "synthesis_path_counts": path_counts,
    }


def _stub_turn_timing(spec: BenchmarkProbeSpec) -> dict[str, Any]:
    base = 42000 if spec.run_kind is RunKind.COLD else 18000
    planning = 8000 if spec.profile != "knowledge_recall" else 5000
    retrieval = 12000 if spec.profile in {"spl_generation", "alert_summary"} else 6000
    endpoint = base - planning - retrieval - 2000
    path = SynthesisPath.COMPOSER if spec.profile == "guided_investigation" else SynthesisPath.LAB
    if spec.profile == "spl_generation":
        path = SynthesisPath.SKIPPED
        endpoint = 0
    return sanitize_turn_timing_payload(
        {
            "schema_version": "1",
            "run_kind": spec.run_kind.value,
            "synthesis_path": path.value,
            "outcome": TurnOutcome.COMPLETED.value if endpoint else TurnOutcome.SKIPPED.value,
            "timeout_applied": False,
            "fallback_used": False,
            "segments_ms": {
                "canonical_planning": planning,
                "retrieval_spl": retrieval,
                "synthesis_endpoint": endpoint or None,
                "application_overhead": 2000,
                "end_to_end": base,
            },
            "endpoint_detail": {
                "provider_label": "stub",
                "model": "stub-deterministic",
                "http_round_trip_ms": endpoint or None,
            },
        }
    )


def run_stub_benchmark(
    specs: list[BenchmarkProbeSpec] | None = None,
    *,
    sleep_ms: int = 0,
) -> BenchmarkReport:
    report = BenchmarkReport(mode="stub")
    for spec in specs or parse_probe_matrix():
        started = time.monotonic()
        if sleep_ms > 0:
            time.sleep(sleep_ms / 1000.0)
        timing = _stub_turn_timing(spec)
        elapsed_ms = int((time.monotonic() - started) * 1000)
        report.runs.append(
            BenchmarkRunResult(
                case_id=spec.case_id,
                profile=spec.profile,
                run_kind=spec.run_kind.value,
                turn_timing=timing,
                elapsed_ms=elapsed_ms,
            )
        )
    report.completed_at_unix = time.time()
    report.summary = summarize_benchmark(report)
    return report


def run_live_benchmark(
    specs: list[BenchmarkProbeSpec],
    *,
    chat_fn: Callable[[str], dict[str, Any]],
) -> BenchmarkReport:
    """Execute live probes via injected chat_fn (HTTP or in-process).

    chat_fn must return a dict containing control_plane_trace.turn_timing or raise.
    """
    report = BenchmarkReport(mode="live")
    for spec in specs:
        started = time.monotonic()
        error: str | None = None
        timing: dict[str, Any] = {}
        try:
            payload = chat_fn(f"benchmark:{spec.profile}:{uuid.uuid4().hex[:8]}")
            trace = payload.get("control_plane_trace") if isinstance(payload, dict) else None
            if not isinstance(trace, dict):
                error = "missing_control_plane_trace"
            else:
                raw_timing = trace.get("turn_timing")
                if not isinstance(raw_timing, dict):
                    error = "missing_turn_timing"
                else:
                    timing = sanitize_turn_timing_payload(raw_timing)
        except Exception as exc:  # noqa: BLE001 — benchmark captures operator failures
            error = type(exc).__name__
        report.runs.append(
            BenchmarkRunResult(
                case_id=spec.case_id,
                profile=spec.profile,
                run_kind=spec.run_kind.value,
                turn_timing=timing,
                elapsed_ms=int((time.monotonic() - started) * 1000),
                error=error,
            )
        )
    report.completed_at_unix = time.time()
    report.summary = summarize_benchmark(report)
    return report


def estimate_live_probe_cost(specs: list[BenchmarkProbeSpec] | None = None) -> dict[str, Any]:
    """Rough operator cost model — not an SLO."""
    matrix = specs or parse_probe_matrix()
    cold = sum(1 for row in matrix if row.run_kind is RunKind.COLD)
    warm = sum(1 for row in matrix if row.run_kind is RunKind.WARM)
    # Observed VPS smoke band (gap reconciliation): 90–240 s/turn with live synthesis.
    est_cold_s = cold * 150
    est_warm_s = warm * 45
    return {
        "probe_count": len(matrix),
        "cold_probes": cold,
        "warm_probes": warm,
        "estimated_runtime_seconds": est_cold_s + est_warm_s,
        "estimated_runtime_minutes": round((est_cold_s + est_warm_s) / 60, 1),
        "note": "Heuristic from 90–240s/turn smoke band; measure phase-1 baseline before SLO.",
    }
