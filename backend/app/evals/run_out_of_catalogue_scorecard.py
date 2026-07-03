"""Out-of-catalogue answer-quality scorecard — probe bank runner (plan 0.1).

Runs curated out-of-catalog probes through the in-process /chat pipeline and emits
one JSONL row per probe with routing, resource-plan, LLM utilization, evidence
classes, and analyst-visible answer text. Offline by default (sentinel posture,
no live LLM/MCP).
"""

from __future__ import annotations

import argparse
import json
import statistics
import subprocess
import sys
import time
import uuid
from contextlib import nullcontext
from pathlib import Path
from typing import Any, TextIO

from app.api.routes_chat import chat
from app.chat.answer_shape_router import classify_answer_shape
from app.evals.answer_efficacy_checks import analyst_visible_text, extract_response_observed
from app.evals.golden_answer_runner import _model_to_dict
from app.evals.sentinel_eval import sentinel_runtime
from app.schemas.requests import ChatRequest

PROBES_PATH = Path(__file__).resolve().parent / "out_of_catalogue_probes.json"

EVIDENCE_CLASS_ORDER = ("rag", "mcp_discovery", "mcp_search", "cve", "mitre", "none")


def load_probes(*, path: Path | None = None) -> dict[str, Any]:
    return json.loads((path or PROBES_PATH).read_text(encoding="utf-8"))


def _match_path(payload: dict[str, Any]) -> str | None:
    observed = extract_response_observed(payload, query="")
    path = observed.get("match_path")
    if path:
        return str(path)
    qti = payload.get("query_to_intent") if isinstance(payload.get("query_to_intent"), dict) else {}
    mappings = qti.get("candidate_mappings") if isinstance(qti.get("candidate_mappings"), dict) else {}
    raw = mappings.get("match_path")
    return str(raw) if raw else None


def _resource_plan_summary(payload: dict[str, Any]) -> dict[str, Any]:
    evidence_plan = payload.get("evidence_plan") if isinstance(payload.get("evidence_plan"), dict) else {}
    resource_plan = evidence_plan.get("resource_plan") if isinstance(evidence_plan.get("resource_plan"), dict) else {}
    steps_out: list[dict[str, Any]] = []
    for step in resource_plan.get("steps") or []:
        if not isinstance(step, dict):
            continue
        steps_out.append(
            {
                "step_id": step.get("step_id"),
                "purpose": step.get("purpose"),
                "resource_id": step.get("resource_id"),
                "status": step.get("status"),
            }
        )
    return {
        "plan_source": resource_plan.get("plan_source"),
        "step_count": len(steps_out),
        "steps": steps_out,
    }


def _llm_output_utilization_verdict(*, llm_called: bool, used: bool, dropped_reason: str | None) -> str:
    if used:
        return "used"
    if llm_called and dropped_reason:
        return f"dropped:{dropped_reason}"
    if llm_called:
        return "dropped:not_applied"
    return "dropped:not_called"


def _extract_llm_calls(payload: dict[str, Any]) -> list[dict[str, Any]]:
    trace = payload.get("control_plane_trace") if isinstance(payload.get("control_plane_trace"), dict) else {}
    calls: list[dict[str, Any]] = []

    intent = trace.get("llm_intent_advisory") if isinstance(trace.get("llm_intent_advisory"), dict) else {}
    if intent.get("llm_called"):
        status = str(intent.get("adjudication_status") or "")
        dropped = (intent.get("dropped_reasons") or [None])[0]
        calls.append(
            {
                "role": "intent_advisor",
                "latency_ms": intent.get("latency_ms"),
                "llm_output_utilization": _llm_output_utilization_verdict(
                    llm_called=True,
                    used=status in {"accepted", "corrected", "applied"},
                    dropped_reason=str(dropped) if dropped else status or "rejected",
                ),
            }
        )

    shadow = trace.get("resource_plan_shadow") if isinstance(trace.get("resource_plan_shadow"), dict) else {}
    if shadow.get("llm_called") or shadow.get("skipped_reason"):
        skip = shadow.get("skipped_reason")
        has_plan = bool(shadow.get("shadow_step_count") or shadow.get("shadow_plan_source"))
        calls.append(
            {
                "role": "resource_plan_bridge",
                "latency_ms": shadow.get("latency_ms"),
                "llm_output_utilization": _llm_output_utilization_verdict(
                    llm_called=bool(shadow.get("llm_called")),
                    used=bool(shadow.get("llm_called")) and has_plan and not shadow.get("promotion_blocked", True),
                    dropped_reason=str(skip) if skip else "shadow_only",
                ),
            }
        )

    candidate_trace = (
        trace.get("candidate_spl_generation") if isinstance(trace.get("candidate_spl_generation"), dict) else {}
    )
    if candidate_trace.get("llm_fallback_used") or candidate_trace.get("llm_latency_ms"):
        calls.append(
            {
                "role": "spl_producer",
                "latency_ms": candidate_trace.get("llm_latency_ms"),
                "llm_output_utilization": _llm_output_utilization_verdict(
                    llm_called=bool(candidate_trace.get("llm_fallback_used") or candidate_trace.get("llm_latency_ms")),
                    used=bool(candidate_trace.get("candidate_spl_generated")),
                    dropped_reason=str(candidate_trace.get("llm_fallback_reason") or "not_generated"),
                ),
            }
        )

    composer = trace.get("llm_composer") if isinstance(trace.get("llm_composer"), dict) else {}
    if composer.get("composer_attempted") or composer.get("llm_composer_used"):
        skip = composer.get("llm_composer_skipped_reason")
        calls.append(
            {
                "role": "answer_composer",
                "latency_ms": composer.get("latency_ms"),
                "llm_output_utilization": _llm_output_utilization_verdict(
                    llm_called=bool(composer.get("composer_attempted")),
                    used=bool(composer.get("llm_composer_used")),
                    dropped_reason=str(skip) if skip else "not_used",
                ),
            }
        )

    advisory = trace.get("llm_advisory_trace") if isinstance(trace.get("llm_advisory_trace"), dict) else {}
    if advisory.get("llm_called") and not any(c["role"] == "route_advisor" for c in calls):
        calls.append(
            {
                "role": "route_advisor",
                "latency_ms": None,
                "llm_output_utilization": _llm_output_utilization_verdict(
                    llm_called=True,
                    used=bool(advisory.get("llm_advisory_used")) and not advisory.get("llm_overridden_by_policy"),
                    dropped_reason=(advisory.get("llm_dropped_reasons") or ["overridden"])[0],
                ),
            }
        )

    return calls


def extract_evidence_classes(payload: dict[str, Any]) -> list[str]:
    """Return evidence classes observed in the final answer envelope."""
    classes: set[str] = set()
    trace = payload.get("control_plane_trace") if isinstance(payload.get("control_plane_trace"), dict) else {}
    evidence_plan = payload.get("evidence_plan") if isinstance(payload.get("evidence_plan"), dict) else {}
    rag = payload.get("soc_kb_retrieval") if isinstance(payload.get("soc_kb_retrieval"), dict) else {}
    rag_trace = trace.get("rag_trace") if isinstance(trace.get("rag_trace"), dict) else {}

    rag_status = str(rag.get("retrieval_status") or rag_trace.get("retrieval_status") or "")
    if rag_status == "retrieved" or bool(evidence_plan.get("needs_rag")):
        classes.add("rag")

    execution = payload.get("execution") if isinstance(payload.get("execution"), dict) else {}
    mcp_trace = trace.get("mcp_execution") if isinstance(trace.get("mcp_execution"), dict) else {}
    exec_status = str(execution.get("status") or mcp_trace.get("status") or "")
    if exec_status == "executed":
        classes.add("mcp_search")
    elif bool(evidence_plan.get("discovery_allowed")) or bool(evidence_plan.get("needs_mcp")):
        intent = str(execution.get("execution_intent") or "")
        if intent == "discovery" or exec_status in {"discovery", "planned"}:
            classes.add("mcp_discovery")

    for record in payload.get("source_evidence") or []:
        if not isinstance(record, dict):
            continue
        source_type = str(record.get("source_type") or "")
        if source_type == "cve_snapshot":
            classes.add("cve")

    mitre = trace.get("mitre_decision") if isinstance(trace.get("mitre_decision"), dict) else {}
    if not mitre and isinstance(payload.get("mitre_decision"), dict):
        mitre = payload.get("mitre_decision") or {}
    techniques = mitre.get("techniques") if isinstance(mitre.get("techniques"), list) else []
    if mitre.get("answer_visible") and techniques:
        classes.add("mitre")
    contract = payload.get("answer_contract") if isinstance(payload.get("answer_contract"), dict) else {}
    if contract.get("evidence_supported_mitre") or contract.get("mitre_status"):
        classes.add("mitre")

    if not classes:
        classes.add("none")
    return [item for item in EVIDENCE_CLASS_ORDER if item in classes]


def _observed_route(payload: dict[str, Any]) -> str | None:
    routing = payload.get("routing") if isinstance(payload.get("routing"), dict) else {}
    return str(payload.get("selected_skill") or routing.get("skill") or "") or None


def _resource_plan_from_payload(payload: dict[str, Any]) -> dict[str, Any] | None:
    evidence = payload.get("evidence_plan") if isinstance(payload.get("evidence_plan"), dict) else {}
    resource_plan = evidence.get("resource_plan")
    return resource_plan if isinstance(resource_plan, dict) else None


def _observed_answer_shape(query: str, payload: dict[str, Any]) -> str:
    return classify_answer_shape(query, resource_plan=_resource_plan_from_payload(payload)).primary_shape


def run_probe(probe: dict[str, Any], *, offline: bool = True) -> dict[str, Any]:
    query = str(probe["query"])
    row: dict[str, Any] = {
        "probe_id": probe["probe_id"],
        "source": probe.get("source"),
        "category": probe.get("category"),
        "query": query,
        "status": "ok",
    }
    started = time.monotonic()
    try:
        ctx = sentinel_runtime() if offline else _null_context()
        with ctx:
            response = chat(ChatRequest(message=query, session_id=f"ooc-score-{uuid.uuid4()}"))
        payload = _model_to_dict(response)
        row["elapsed_ms"] = int((time.monotonic() - started) * 1000)
        row["match_path"] = _match_path(payload)
        row["route"] = _observed_route(payload)
        row["answer_shape"] = _observed_answer_shape(query, payload)
        row["resource_plan"] = _resource_plan_summary(payload)
        row["llm_calls"] = _extract_llm_calls(payload)
        row["evidence_classes"] = extract_evidence_classes(payload)
        row["answer_text"] = analyst_visible_text(payload)
        expect = probe.get("expect") if isinstance(probe.get("expect"), dict) else {}
        if expect.get("route") and row["route"] != expect["route"]:
            row["expectation_drift"] = f"route: expected={expect['route']} actual={row['route']}"
        if expect.get("answer_shape") and row["answer_shape"] != expect["answer_shape"]:
            drift = row.get("expectation_drift") or ""
            row["expectation_drift"] = (
                f"{drift}; shape: expected={expect['answer_shape']} actual={row['answer_shape']}"
            ).strip("; ")
        if expect.get("evidence_classes"):
            expected = set(expect["evidence_classes"])
            observed = set(row["evidence_classes"])
            if not expected <= observed:
                drift = row.get("expectation_drift") or ""
                row["expectation_drift"] = (
                    f"{drift}; evidence: expected>={sorted(expected)} actual={sorted(observed)}"
                ).strip("; ")
        if expect.get("usefulness_rubric") is not None:
            row["usefulness_rubric_target"] = expect["usefulness_rubric"]
    except Exception as exc:  # pragma: no cover - surfaced in report row
        row["status"] = "error"
        row["elapsed_ms"] = int((time.monotonic() - started) * 1000)
        row["error"] = f"{type(exc).__name__}: {exc}"
    return row


def _percentile(values: list[int], pct: float) -> int | None:
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, int(round((pct / 100.0) * (len(ordered) - 1)))))
    return ordered[index]


def _vmstat_steal_snapshot() -> dict[str, Any]:
    try:
        proc = subprocess.run(
            ["vmstat", "1", "5"],
            capture_output=True,
            text=True,
            timeout=12,
            check=False,
        )
        lines = [line for line in proc.stdout.splitlines() if line.strip()]
        steal_index: int | None = None
        data_lines: list[str] = []
        for line in lines:
            lowered = line.lower()
            if "st" in line.split() and "us" in line.split() and "id" in line.split():
                parts = line.split()
                if "st" in parts:
                    steal_index = parts.index("st")
                continue
            stripped = line.strip()
            if stripped and stripped[0].isdigit():
                data_lines.append(line)
        if steal_index is None:
            return {"available": False, "reason": "steal_column_not_found"}
        steal_values: list[float] = []
        for line in data_lines:
            parts = line.split()
            if len(parts) > steal_index:
                steal_values.append(float(parts[steal_index]))
        if not steal_values:
            return {"available": False, "reason": "no_samples"}
        return {
            "available": True,
            "steal_avg_pct": round(statistics.mean(steal_values), 2),
            "steal_max_pct": round(max(steal_values), 2),
            "samples": len(steal_values),
        }
    except (OSError, subprocess.TimeoutExpired, ValueError) as exc:
        return {"available": False, "reason": str(exc)}


def summarize_scorecard(report: dict[str, Any], *, bank: dict[str, Any] | None = None) -> dict[str, Any]:
    rows = [row for row in report.get("rows") or [] if row.get("status") == "ok"]
    total = len(rows) or 1
    mcp_rows = sum(
        1
        for row in rows
        if any(cls in row.get("evidence_classes", []) for cls in ("mcp_discovery", "mcp_search"))
    )
    cve_mitre_rows = sum(
        1
        for row in rows
        if any(cls in row.get("evidence_classes", []) for cls in ("cve", "mitre"))
    )
    llm_calls = [call for row in rows for call in row.get("llm_calls") or []]
    llm_attempted = [call for call in llm_calls if str(call.get("llm_output_utilization", "")).startswith("used") or "dropped" in str(call.get("llm_output_utilization", ""))]
    llm_used = [call for call in llm_calls if str(call.get("llm_output_utilization", "")) == "used"]
    latencies = [int(row["elapsed_ms"]) for row in rows if row.get("elapsed_ms") is not None]

    hand_ids = set((bank or {}).get("hand_score_sample_probe_ids") or [])
    hand_rows = [row for row in rows if row.get("probe_id") in hand_ids]
    usefulness_targets = [
        row.get("usefulness_rubric_target")
        for row in hand_rows
        if row.get("usefulness_rubric_target") is not None
    ]

    return {
        "probe_count": len(rows),
        "offline": report.get("offline"),
        "mcp_evidence_pct": round(100.0 * mcp_rows / total, 2),
        "cve_mitre_usage_pct": round(100.0 * cve_mitre_rows / total, 2),
        "llm_output_utilization_pct": round(100.0 * len(llm_used) / max(len(llm_attempted), 1), 2),
        "llm_calls_total": len(llm_calls),
        "llm_calls_used": len(llm_used),
        "latency_ms": {
            "p50": _percentile(latencies, 50),
            "p95": _percentile(latencies, 95),
            "mean": int(statistics.mean(latencies)) if latencies else None,
        },
        "usefulness_hand_sample": {
            "probe_count": len(hand_rows),
            "target_rubric_mean": round(statistics.mean(usefulness_targets), 2) if usefulness_targets else None,
            "note": "Hand-scored usefulness baseline uses pinned target rubric until live review (plan 0.2).",
        },
        "vmstat_steal": _vmstat_steal_snapshot(),
    }


def _null_context():
    return nullcontext()


def run_scorecard(
    *,
    probes: list[dict[str, Any]] | None = None,
    offline: bool = True,
) -> dict[str, Any]:
    bank = load_probes() if probes is None else {"probes": probes}
    probe_rows = bank.get("probes") or []
    rows = [run_probe(probe, offline=offline) for probe in probe_rows]
    errors = sum(1 for row in rows if row.get("status") == "error")
    return {
        "bank": bank.get("name"),
        "version": bank.get("version"),
        "probe_count": len(rows),
        "offline": offline,
        "error_count": errors,
        "rows": rows,
    }


def write_jsonl(report: dict[str, Any], stream: TextIO) -> None:
    for row in report["rows"]:
        stream.write(json.dumps(row, ensure_ascii=False) + "\n")


def scorecard_row_contract_keys() -> frozenset[str]:
    """Stable JSONL row keys required by the 0.1 contract test."""
    return frozenset(
        {
            "probe_id",
            "match_path",
            "resource_plan",
            "llm_calls",
            "evidence_classes",
            "answer_text",
        }
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--offline", action="store_true", default=True, help="sentinel posture (default)")
    parser.add_argument("--live", action="store_true", help="run without sentinel offline overlay")
    parser.add_argument("--jsonl", type=Path, default=None, help="write one JSONL row per probe")
    parser.add_argument("--summary", type=Path, default=None, help="write summary JSON")
    parser.add_argument("--baseline-dir", type=Path, default=None, help="write scorecard.jsonl + summary.json under dir")
    parser.add_argument("--probes", type=Path, default=None, help="alternate probe bank path")
    args = parser.parse_args(argv)

    offline = not args.live
    bank = load_probes(path=args.probes) if args.probes else load_probes()
    report = run_scorecard(probes=bank.get("probes"), offline=offline)
    summary = summarize_scorecard(report, bank=bank)
    report["summary"] = summary

    jsonl_path = args.jsonl
    summary_path = args.summary
    if args.baseline_dir:
        args.baseline_dir.mkdir(parents=True, exist_ok=True)
        mode = "offline" if offline else "live"
        jsonl_path = args.baseline_dir / f"scorecard_{mode}.jsonl"
        summary_path = args.baseline_dir / f"summary_{mode}.json"

    if jsonl_path:
        jsonl_path.parent.mkdir(parents=True, exist_ok=True)
        with jsonl_path.open("w", encoding="utf-8") as handle:
            write_jsonl(report, handle)
        print(f"wrote {jsonl_path} ({report['probe_count']} rows)")

    if summary_path:
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"wrote {summary_path}")

    if report["error_count"]:
        print(f"RESULT: FAIL ({report['error_count']} errors / {report['probe_count']} probes)", file=sys.stderr)
        return 1
    print(
        "RESULT: PASS "
        f"({report['probe_count']} probes, offline={offline}, "
        f"mcp={summary['mcp_evidence_pct']}%, cve_mitre={summary['cve_mitre_usage_pct']}%, "
        f"llm_util={summary['llm_output_utilization_pct']}%)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
