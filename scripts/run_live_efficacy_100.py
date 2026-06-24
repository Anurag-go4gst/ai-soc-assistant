#!/usr/bin/env python3
"""Reusable live /chat efficacy runner with telemetry, health recovery, and review.

The bank is intentionally external to this runner so later exercises can reuse
the same mechanics with a fresh corpus. Existing golden/eval artifacts are never
read or rewritten.
"""

from __future__ import annotations

import argparse
import atexit
import http.cookiejar
import json
import re
import statistics
import subprocess
import sys
import time
import urllib.error
import urllib.request
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BANK = REPO_ROOT / "docs/evals/live_efficacy_100_bank.json"
DEFAULT_OUT = REPO_ROOT / "docs/evals/live_efficacy_100"
_SECRET_KEYS = ("password", "secret", "token", "api_key", "authorization", "cookie")
_STATUS_ONLY = (
    "investigation planning is complete",
    "spl validation complete",
    "governed knowledge path selected",
    "generic soc guidance path selected",
    "governed spl drafting is in review-only mode",
)
_UNSAFE_EXECUTION = re.compile(r"\b(executed|ran|returned \d+ rows|live results show)\b", re.I)


def _env_value(key: str) -> str:
    for path in (REPO_ROOT / ".env", REPO_ROOT / ".env.example"):
        if not path.exists():
            continue
        for raw in path.read_text(encoding="utf-8").splitlines():
            if raw.startswith(f"{key}="):
                return raw.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


class LiveClient:
    def __init__(self, base_url: str, timeout: float) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.cookies = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.cookies))

    def request(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
        extra_headers: dict[str, str] | None = None,
        timeout: float | None = None,
    ) -> tuple[int, Any, dict[str, str]]:
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if extra_headers:
            headers.update(extra_headers)
        request = urllib.request.Request(f"{self.base_url}{path}", data=data, method=method, headers=headers)
        try:
            with self.opener.open(
                request, timeout=self.timeout if timeout is None else timeout
            ) as response:
                body = response.read().decode("utf-8", errors="replace")
                return response.status, json.loads(body) if body else {}, dict(response.headers)
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            resp_headers = dict(exc.headers) if exc.headers else {}
            try:
                return exc.code, json.loads(body), resp_headers
            except json.JSONDecodeError:
                return exc.code, {"detail": body[:500]}, resp_headers
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            return 0, {"detail": f"transport_error:{type(exc).__name__}:{exc}"}, {}

    def login(self) -> dict[str, Any]:
        status, payload, _ = self.request(
            "POST",
            "/auth/login",
            {"username": _env_value("APP_AUTH_USER"), "password": _env_value("APP_AUTH_PASSWORD")},
        )
        if status != 200 or not payload.get("authenticated"):
            raise RuntimeError(f"authentication_failed:http_{status}")
        return payload


def _health_guard(restart: bool, threshold: float, max_wall_seconds: float) -> dict[str, Any]:
    command = [
        sys.executable,
        str(REPO_ROOT / "scripts/llm_health_guard.py"),
        "--threshold",
        str(threshold),
        "--max-wall-seconds",
        str(max_wall_seconds),
        "--probe-timeout",
        "30",
    ]
    if restart:
        command.append("--restart")
    completed = subprocess.run(command, cwd=REPO_ROOT, capture_output=True, text=True, timeout=240)
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError:
        payload = {"healthy": False, "error": "health_guard_invalid_output"}
    payload["exit_code"] = completed.returncode
    return payload


def _post_chat(
    client: LiveClient,
    question: dict[str, Any],
    attempt: int,
    *,
    retry_of: str | None = None,
    trace_poll_seconds: float = 90.0,
    trace_poll_interval: float = 2.0,
) -> dict[str, Any]:
    started = time.monotonic()
    status, payload, headers = 0, {"detail": "not_attempted"}, {}
    # Client-known correlation: the runner mints the trace id up front and sends it
    # as X-Request-ID, so even when a transport timeout means we never receive the
    # response (and its X-Trace-ID), we can still query the server-side trace by id.
    # A first-attempt run performs exactly one HTTP request. A resilience retry is
    # a separate call with a new request id and an explicit ``retry_of`` link; two
    # live requests must never write concurrently to the same trace row.
    request_id = str(uuid4())
    status, payload, headers = client.request(
        "POST",
        "/chat",
        {"message": question["question"], "session_id": f"live-eff-{question['id']}-a{attempt}"},
        extra_headers={"X-Request-ID": request_id},
    )
    # Distinguish an application failure (HTTP error with a JSON body — root-cause
    # classifiable via error_code/trace_id) from a transport-layer failure (status
    # 0 = client timeout/connection error). status-0 is NEVER merged into the
    # application-failure cohort.
    if status == 0:
        failure_class = "transport"
    elif status == 200:
        failure_class = "ok"
    else:
        failure_class = "application_500" if status >= 500 else "application_error"
    body = payload if isinstance(payload, dict) else {}
    echoed_trace = headers.get("X-Trace-ID") or headers.get("x-trace-id")
    # Correlation id, in priority order: echoed X-Trace-ID (success/app-error) →
    # error-envelope trace_id → the client-known request_id (the only id available
    # after a transport timeout). request_id == server trace id by construction.
    correlation_trace_id = echoed_trace or body.get("trace_id") or request_id
    result = {
        "http_status": status,
        "wall_latency_ms": int((time.monotonic() - started) * 1000),
        "transport_attempts": 1,
        "retry_of": retry_of,
        "failure_class": failure_class,
        "request_id": request_id,
        "echoed_trace_id": echoed_trace,
        "correlation_trace_id": correlation_trace_id,
        "error_code": body.get("error_code") if status != 200 else None,
        "error_trace_id": body.get("trace_id") if status != 200 else None,
        "response": payload,
    }
    # For any non-OK outcome — especially a transport timeout — ask the server what
    # actually happened to the turn, using the client-known id. This turns an
    # indeterminate transport stall into one of: still running / completed after
    # disconnect / internal error / lost before admission.
    if status == 0:
        result["server_outcome"] = _poll_server_trace_outcome(
            client,
            request_id,
            timeout_seconds=trace_poll_seconds,
            interval_seconds=trace_poll_interval,
        )
    elif status != 200:
        result["server_outcome"] = _server_trace_outcome(client, request_id)
    return result


def _server_trace_outcome(client: LiveClient, trace_id: str) -> dict[str, Any]:
    """Resolve a transport-indeterminate turn into a server-side outcome by trace id.

    Requires debug access. Classifies the admission/trace record so a client that
    never received the response can still tell what the backend did.
    """
    status, payload, _ = client.request(
        "GET", f"/debug/traces/{trace_id}", timeout=min(client.timeout, 5.0)
    )
    if status == 404:
        return {"status": "lost_before_admission", "http": status}
    if status != 200 or not isinstance(payload, dict):
        return {"status": "unknown", "http": status}
    run = payload.get("run") if isinstance(payload.get("run"), dict) else payload
    run_status = str((run or {}).get("status") or "")
    mapping = {
        "running": "running_at_timeout",
        "completed": "completed_after_disconnect",
        "human_review": "completed_after_disconnect",
        "error": "internal_error_after_disconnect",
        "failed": "internal_error_after_disconnect",
        "timeout": "server_deadline_timeout",
        "partial_timeout": "server_deadline_timeout",
        "cancelled": "server_cancelled",
    }
    return {
        "status": mapping.get(run_status, run_status or "unknown"),
        "run_status": run_status or None,
        "http": status,
    }


def _poll_server_trace_outcome(
    client: LiveClient,
    trace_id: str,
    *,
    timeout_seconds: float,
    interval_seconds: float,
) -> dict[str, Any]:
    """Poll a timed-out request to a terminal or explicitly bounded outcome."""
    deadline = time.monotonic() + max(timeout_seconds, 0.0)
    polls = 0
    last: dict[str, Any] = {"status": "unknown", "http": None}
    terminal = {
        "completed_after_disconnect",
        "internal_error_after_disconnect",
        "server_deadline_timeout",
        "server_cancelled",
    }
    while True:
        polls += 1
        last = _server_trace_outcome(client, trace_id)
        if last.get("status") in terminal:
            return {**last, "polls": polls, "poll_exhausted": False}
        if time.monotonic() >= deadline:
            status = str(last.get("status") or "unknown")
            if status == "running_at_timeout":
                status = "still_running_after_poll_limit"
            elif status == "unknown":
                status = "unknown_after_poll_limit"
            return {**last, "status": status, "polls": polls, "poll_exhausted": True}
        time.sleep(max(interval_seconds, 0.1))


def _debug_telemetry(client: LiveClient, trace_id: str | None) -> dict[str, Any]:
    if not trace_id:
        return {"available": False, "reason": "trace_id_missing"}
    result: dict[str, Any] = {"available": False}
    for suffix, key in (("", "timeline"), ("/bundle", "bundle")):
        status, payload, _ = client.request("GET", f"/debug/traces/{trace_id}{suffix}")
        result[f"{key}_http_status"] = status
        if status == 200:
            result[key] = payload
            result["available"] = True
        else:
            result[f"{key}_error"] = payload.get("detail") if isinstance(payload, dict) else "unknown"
    return result


def _failure_diagnostic(telemetry: dict[str, Any]) -> dict[str, str | None]:
    """Extract protected exception identity from an authenticated debug bundle."""
    bundle = telemetry.get("bundle") if isinstance(telemetry, dict) else None
    timeline = bundle.get("timeline") if isinstance(bundle, dict) else None
    if not isinstance(timeline, list):
        return {"exception_type": None, "failure_stage": None}
    for item in reversed(timeline):
        if not isinstance(item, dict):
            continue
        event = item.get("event") if isinstance(item.get("event"), dict) else {}
        exception_type = event.get("exception_type")
        step_name = item.get("step_name")
        if exception_type or step_name == "unhandled_exception":
            return {
                "exception_type": str(exception_type) if exception_type else None,
                "failure_stage": str(step_name or item.get("kind") or "unknown"),
            }
    return {"exception_type": None, "failure_stage": None}


def _score(question: dict[str, Any], run: dict[str, Any]) -> dict[str, Any]:
    response = run.get("response") if isinstance(run.get("response"), dict) else {}
    contract = response.get("answer_contract") or {}
    analyst = response.get("analyst_response") or {}
    trace = response.get("control_plane_trace") or {}
    planning = response.get("planning_decision") or {}
    execution = response.get("execution") or {}
    validation = response.get("spl_validation") or {}
    message = str(response.get("message") or analyst.get("direct_answer_summary") or "").strip()
    lowered = message.lower()
    issues: list[str] = []
    strengths: list[str] = []

    if run.get("http_status") != 200:
        issues.append(f"http_error:{run.get('http_status')}")
    if len(message) < 180 or any(stub in lowered for stub in _STATUS_ONLY):
        issues.append("thin_or_status_only_answer")
    else:
        strengths.append("substantive_answer")
    checklist = analyst.get("analyst_checklist") or contract.get("analyst_checklist_safe") or []
    actions = analyst.get("recommended_actions") or contract.get("investigation_steps") or []
    if not checklist and not actions and question["category"] not in {"boundary"}:
        issues.append("no_structured_next_steps")
    if response.get("selected_skill"):
        strengths.append("skill_selected")
    else:
        issues.append("selected_skill_missing")

    normalized_spl = validation.get("normalized_spl")
    execution_status = str(execution.get("status") or "")
    if execution_status == "executed":
        issues.append("unexpected_execution_during_default_off_test")
    if response.get("candidate_spl") and not (
        analyst.get("draft_spl_code")
        or analyst.get("spl_code")
        or (contract.get("render_sections") or {}).get("spl_artifact")
    ):
        issues.append("candidate_spl_not_visible")
    if normalized_spl and "<" not in str(normalized_spl):
        strengths.append("normalized_spl_ready")
    execution_claim = _UNSAFE_EXECUTION.search(message)
    execution_negated = any(
        phrase in lowered
        for phrase in (
            "not executed",
            "never executed",
            "no mcp execution",
            "no live query was executed",
            "no execution was",
            "without executing",
            "was not run",
        )
    )
    if execution_claim and not execution_negated and execution_status != "executed":
        issues.append("possible_execution_overclaim")

    if question["category"] == "boundary" and not any(
        marker in lowered
        for marker in ("out of scope", "cannot", "can't", "blocked", "refus", "security assistant")
    ):
        issues.append("boundary_request_not_handled")

    mitre = response.get("mitre_decision") or {}
    mitre_status = str(
        mitre.get("status")
        or mitre.get("mitre_status")
        or response.get("mitre_evidence_status")
        or ""
    )
    if "mitre" in question["question"].lower() or "att&ck" in question["question"].lower():
        if not mitre_status and not analyst.get("mitre_mappings"):
            issues.append("mitre_requested_but_status_missing")
        else:
            strengths.append("mitre_status_present")

    q_lower = question["question"].lower()
    if "cve-" in q_lower:
        vulnerability = (
            (trace.get("evidence_loop") or {}).get("vulnerability_source")
            or trace.get("vulnerability_source")
            or next(
                (
                    item.get("vulnerability_source")
                    for item in (response.get("source_evidence") or [])
                    if isinstance(item, dict) and item.get("vulnerability_source")
                ),
                None,
            )
        )
        has_vuln_source_row = any(
            (
                (isinstance(item, dict) and item.get("source_name") == "vulnerability_source")
                or (getattr(item, "source_name", None) == "vulnerability_source")
            )
            for item in (response.get("source_evidence") or [])
        )
        if not vulnerability and not has_vuln_source_row and "vulnerability_source" not in lowered:
            issues.append("cve_source_provenance_missing")

    resource_plan = (response.get("evidence_plan") or {}).get("resource_plan") or {}
    expected_artifacts = {
        str(item) for item in (question.get("expected_artifacts") or []) if item
    }
    resource_plan_required = bool(
        expected_artifacts.intersection({"resource_plan", "mcp_plan"})
    )
    if resource_plan.get("steps"):
        strengths.append("resource_plan_present")
    elif resource_plan_required:
        issues.append("resource_plan_missing")
    if planning.get("selected_tools") or (trace.get("mcp_execution") or {}).get("selected_mcp_tool"):
        strengths.append("mcp_wiring_visible")

    final_validation = response.get("final_answer_validation") or {}
    if final_validation.get("status") in {"failed", "blocked"}:
        issues.append("final_answer_validation_failed")
    score = max(0, 100 - 18 * len(set(issues)))
    return {
        "score": score,
        "issues": sorted(set(issues)),
        "strengths": sorted(set(strengths)),
        "message_len": len(message),
        "checklist_count": len(checklist) if isinstance(checklist, list) else 0,
        "action_count": len(actions) if isinstance(actions, list) else 0,
        "selected_skill": response.get("selected_skill"),
        "answer_mode": contract.get("answer_mode") or response.get("answer_mode"),
        "match_path": ((response.get("query_to_intent") or {}).get("candidate_mappings") or {}).get("match_path"),
        "mitre_status": mitre_status or None,
        "execution_status": execution_status or None,
        "mcp_block_reason": execution.get("block_reason"),
        "llm_budget": trace.get("llm_turn_budget"),
        "llm_composer": trace.get("llm_composer"),
    }


def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: "[REDACTED]" if any(token in key.lower() for token in _SECRET_KEYS) else _redact(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_redact(item) for item in value]
    return value


def _summarize(rows: list[dict[str, Any]], health: list[dict[str, Any]]) -> dict[str, Any]:
    successful = [row for row in rows if row.get("http_status") == 200]
    scores = [row["quality"]["score"] for row in successful]
    latencies = [row["wall_latency_ms"] for row in successful]
    # Quality denominators are HTTP-200 only. Reliability/failure classification
    # is reported separately so empty 500 bodies cannot inflate thin/missing counts.
    issues = Counter(issue for row in successful for issue in row["quality"]["issues"])
    skills = Counter(
        str(row["quality"].get("selected_skill") or "missing") for row in successful
    )
    categories: dict[str, list[int]] = defaultdict(list)
    for row in successful:
        categories[row["category"]].append(row["quality"]["score"])

    # Two-cohort failure classification so the non-200 split (e.g. 28 failures) is
    # visible without manual analysis: group by error_code (falling back to the
    # failure_class then "unknown") AND by latency cohort (fast <2s vs slow >=2s).
    failed = [row for row in rows if row.get("http_status") != 200]
    by_error_code: Counter = Counter()
    by_failure_class: Counter = Counter()
    by_exception_type: Counter = Counter()
    by_failure_stage: Counter = Counter()
    by_latency_cohort: Counter = Counter()
    error_code_latency: dict[str, Counter] = defaultdict(Counter)
    for row in failed:
        code = str(row.get("error_code") or row.get("failure_class") or "unknown")
        cohort = "fast_under_2s" if int(row.get("wall_latency_ms") or 0) < 2000 else "slow_2s_plus"
        by_error_code[code] += 1
        by_failure_class[str(row.get("failure_class") or "unknown")] += 1
        by_exception_type[str(row.get("exception_type") or "unclassified")] += 1
        by_failure_stage[str(row.get("failure_stage") or "unclassified")] += 1
        by_latency_cohort[cohort] += 1
        error_code_latency[code][cohort] += 1
    failure_classification = {
        "total_failures": len(failed),
        "by_error_code": dict(by_error_code.most_common()),
        "by_failure_class": dict(by_failure_class.most_common()),
        "by_exception_type": dict(by_exception_type.most_common()),
        "by_failure_stage": dict(by_failure_stage.most_common()),
        "by_latency_cohort": dict(by_latency_cohort.most_common()),
        "by_error_code_and_latency": {
            code: dict(cohorts.most_common()) for code, cohorts in error_code_latency.items()
        },
        "failed_trace_ids": [
            {"id": row.get("id"), "error_trace_id": row.get("error_trace_id"), "error_code": row.get("error_code")}
            for row in failed
            if row.get("error_trace_id")
        ],
    }
    recovery_attempted = [
        row for row in rows if isinstance(row.get("recovery_attempt"), dict)
    ]
    recovery_to_200 = sum(
        int((row.get("recovery_attempt") or {}).get("http_status") == 200)
        for row in recovery_attempted
    )
    return {
        "total": len(rows),
        "http_success": len(successful),
        "debug_telemetry_available": sum(bool(row.get("telemetry", {}).get("available")) for row in rows),
        "quality": {
            "denominator": len(successful),
            "mean": round(statistics.mean(scores), 2) if scores else 0,
            "median": round(statistics.median(scores), 2) if scores else 0,
            "rows_below_70": sum(score < 70 for score in scores),
            "issue_counts": dict(issues.most_common()),
            "by_category": {key: round(statistics.mean(vals), 2) for key, vals in categories.items()},
        },
        "latency_ms": {
            "median": round(statistics.median(latencies), 2) if latencies else 0,
            "p95": _percentile(latencies, 0.95),
            "max": max(latencies) if latencies else 0,
        },
        "skills": dict(skills.most_common()),
        "failure_classification": failure_classification,
        "resilience": {
            "retry_attempted": len(recovery_attempted),
            "retry_recovered_to_http_200": recovery_to_200,
        },
        "llm_health_checks": health,
        "retry_count": sum(bool(row.get("retried")) for row in rows),
    }


def _percentile(values: list[int], fraction: float) -> int:
    if not values:
        return 0
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, max(0, int(round((len(ordered) - 1) * fraction))))]


def _write_report(result: dict[str, Any], path: Path) -> None:
    summary = result["summary"]
    lines = [
        "# Live Efficacy 100 — Review",
        "",
        f"Generated: {result['generated_at']}",
        f"HTTP success: **{summary['http_success']}/{summary['total']}**",
        f"Full debug telemetry: **{summary['debug_telemetry_available']}/{summary['total']}**",
        f"Quality mean/median: **{summary['quality']['mean']} / {summary['quality']['median']}**",
        f"Latency median/p95/max: **{summary['latency_ms']['median']} / {summary['latency_ms']['p95']} / {summary['latency_ms']['max']} ms**",
        "",
        "## Issue counts",
        "",
    ]
    for issue, count in summary["quality"]["issue_counts"].items():
        lines.append(f"- `{issue}`: {count}")
    lines.extend(["", "## Category quality", ""])
    for category, score in summary["quality"]["by_category"].items():
        lines.append(f"- `{category}`: {score}")
    lines.extend(["", "## Lowest-scoring rows", ""])
    for row in sorted(result["rows"], key=lambda item: item["quality"]["score"])[:20]:
        issues = ", ".join(row["quality"]["issues"]) or "none"
        lines.append(
            f"- **{row['id']}** ({row['category']}, score {row['quality']['score']}, "
            f"{row['wall_latency_ms']} ms): {issues}"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8010")
    parser.add_argument("--bank", type=Path, default=DEFAULT_BANK)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    # Client timeout must EXCEED the server hard turn deadline by margin so a slow
    # turn surfaces as an application response (classifiable) rather than a client
    # transport timeout. Per the plan's "+20s finalization/network margin" rule:
    # server hard deadline (~150s) + 20s = 170s. A status-0 timeout is still
    # reported as `transport`, never folded into the application-failure cohort.
    parser.add_argument("--timeout", type=float, default=170.0)
    parser.add_argument("--slow-turn-seconds", type=float, default=60.0)
    parser.add_argument("--health-every", type=int, default=20)
    parser.add_argument("--llm-tok-threshold", type=float, default=2.0)
    parser.add_argument("--llm-health-max-wall-seconds", type=float, default=20.0)
    parser.add_argument("--restart-llm-on-degraded", action="store_true")
    parser.add_argument(
        "--trace-poll-seconds",
        type=float,
        default=90.0,
        help="Bounded server-outcome polling window after a client transport timeout",
    )
    parser.add_argument("--trace-poll-interval", type=float, default=2.0)
    parser.add_argument("--resume", action="store_true", help="Resume from the per-row checkpoint")
    parser.add_argument(
        "--enable-debug-access",
        dest="enable_debug_access",
        action="store_true",
        help="Enable read-only debug access and require a preflight canary (default)",
    )
    parser.add_argument(
        "--no-debug-access",
        dest="enable_debug_access",
        action="store_false",
        help="Disable debug collection only for an explicit authorization-off test",
    )
    parser.set_defaults(enable_debug_access=True)
    parser.add_argument("--reanalyze-only", action="store_true", help="Re-score existing results without live calls")
    parser.add_argument(
        "--expected-count",
        type=int,
        default=100,
        help="Required question count (default 100). Lower it only for a diagnostic "
        "subset run such as the 28 formerly-failing rows; full baselines keep 100.",
    )
    args = parser.parse_args(argv)

    bank = json.loads(args.bank.read_text(encoding="utf-8"))
    questions = bank.get("questions") or []
    if len(questions) != args.expected_count or len({row["question"] for row in questions}) != len(questions):
        raise SystemExit(f"bank_must_contain_{args.expected_count}_unique_questions")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    results_path = args.out_dir / "results.json"
    if args.reanalyze_only:
        result = json.loads(results_path.read_text(encoding="utf-8"))
        for row in result.get("rows") or []:
            row["quality"] = _score(row, row)
        result["summary"] = _summarize(result.get("rows") or [], result["summary"].get("llm_health_checks") or [])
        results_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
        _write_report(result, args.out_dir / "report.md")
        print(json.dumps(result["summary"], indent=2))
        return 0
    client = LiveClient(args.base_url, args.timeout)
    auth = client.login()
    restore_debug_access = None
    if args.enable_debug_access and not auth.get("debug_access"):
        status, updated_auth, _ = client.request("PATCH", "/auth/profile", {"debug_access": True})
        if status != 200 or not updated_auth.get("debug_access"):
            raise SystemExit(f"debug_access_enable_failed:http_{status}")
        auth = updated_auth

        def _restore_debug_access() -> None:
            client.request("PATCH", "/auth/profile", {"debug_access": False})

        restore_debug_access = _restore_debug_access
        atexit.register(restore_debug_access)
    if args.enable_debug_access:
        debug_status, _, _ = client.request("GET", "/debug/traces?limit=1")
        if debug_status != 200:
            raise SystemExit(f"debug_access_canary_failed:http_{debug_status}")
    health_checks: list[dict[str, Any]] = []
    initial_health = _health_guard(False, args.llm_tok_threshold, args.llm_health_max_wall_seconds)
    initial_health["position"] = "before_run"
    health_checks.append(initial_health)

    checkpoint_path = args.out_dir / "checkpoint.json"
    rows: list[dict[str, Any]] = []
    if args.resume and checkpoint_path.exists():
        checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
        rows = list(checkpoint.get("rows") or [])
        health_checks.extend(checkpoint.get("llm_health_checks") or [])
        if auth.get("debug_access"):
            for prior in rows:
                if prior.get("telemetry", {}).get("available"):
                    continue
                response = prior.get("response") if isinstance(prior.get("response"), dict) else {}
                prior_trace = str(
                    response.get("trace_id")
                    or prior.get("correlation_trace_id")
                    or prior.get("error_trace_id")
                    or ""
                ) or None
                prior["telemetry"] = _redact(_debug_telemetry(client, prior_trace))
                if prior.get("http_status") != 200:
                    prior.update(_failure_diagnostic(prior["telemetry"]))
            checkpoint_path.write_text(
                json.dumps({"rows": rows, "llm_health_checks": health_checks}, indent=2),
                encoding="utf-8",
            )
    completed_ids = {str(row.get("id")) for row in rows}
    for index, question in enumerate(questions, start=1):
        if question["id"] in completed_ids:
            continue
        run = _post_chat(
            client,
            question,
            1,
            trace_poll_seconds=args.trace_poll_seconds,
            trace_poll_interval=args.trace_poll_interval,
        )
        attempts = [_redact(run)]
        recovery_run: dict[str, Any] | None = None
        retried = False
        health_event: dict[str, Any] | None = None
        slow = run["wall_latency_ms"] >= int(args.slow_turn_seconds * 1000)
        if slow or (args.health_every > 0 and index % args.health_every == 0):
            health_event = _health_guard(
                args.restart_llm_on_degraded,
                args.llm_tok_threshold,
                args.llm_health_max_wall_seconds,
            )
            health_event["position"] = index
            health_event["trigger"] = "slow_turn" if slow else "periodic"
            if args.restart_llm_on_degraded and health_event.get("restart"):
                if health_event.get("healthy"):
                    recovery_run = _post_chat(
                        client,
                        question,
                        2,
                        retry_of=str(run.get("request_id") or "") or None,
                        trace_poll_seconds=args.trace_poll_seconds,
                        trace_poll_interval=args.trace_poll_interval,
                    )
                    attempts.append(_redact(recovery_run))
                    retried = True
            health_checks.append(health_event)

        response = run.get("response") if isinstance(run.get("response"), dict) else {}
        # Correlate a failed turn too: on a non-200 the success trace_id is absent,
        # so fall back to the error envelope's trace_id captured in _post_chat.
        trace_for_debug = str(
            response.get("trace_id")
            or run.get("correlation_trace_id")
            or run.get("error_trace_id")
            or ""
        ) or None
        telemetry = (
            _debug_telemetry(client, trace_for_debug)
            if auth.get("debug_access")
            else {"available": False, "reason": "debug_access_disabled"}
        )
        failure_diagnostic = (
            _failure_diagnostic(telemetry)
            if run.get("http_status") != 200
            else {"exception_type": None, "failure_stage": None}
        )
        row = {
            **question,
            **run,
            "retried": retried,
            "attempts": attempts,
            "recovery_attempt": _redact(recovery_run) if recovery_run is not None else None,
            "telemetry": telemetry,
            **failure_diagnostic,
        }
        row["quality"] = _score(question, row)
        rows.append(_redact(row))
        checkpoint_path.write_text(
            json.dumps({"rows": rows, "llm_health_checks": health_checks}, indent=2),
            encoding="utf-8",
        )
        print(
            json.dumps(
                {
                    "progress": f"{index}/{len(questions)}",
                    "id": question["id"],
                    "http": run["http_status"],
                    "latency_ms": run["wall_latency_ms"],
                    "score": row["quality"]["score"],
                    "issues": row["quality"]["issues"],
                    "retried": retried,
                    "recovery_http": recovery_run.get("http_status") if recovery_run else None,
                },
                separators=(",", ":"),
            ),
            flush=True,
        )

    result = {
        "generated_at": datetime.now(UTC).isoformat(),
        "bank": {key: value for key, value in bank.items() if key != "questions"},
        "run_config": {
            "base_url": args.base_url,
            "timeout": args.timeout,
            "slow_turn_seconds": args.slow_turn_seconds,
            "health_every": args.health_every,
            "llm_tok_threshold": args.llm_tok_threshold,
            "llm_health_max_wall_seconds": args.llm_health_max_wall_seconds,
            "restart_llm_on_degraded": args.restart_llm_on_degraded,
            "trace_poll_seconds": args.trace_poll_seconds,
            "trace_poll_interval": args.trace_poll_interval,
            "authenticated_role": auth.get("role"),
            "debug_access": auth.get("debug_access"),
        },
        "rows": rows,
    }
    result["summary"] = _summarize(rows, health_checks)
    results_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    _write_report(result, args.out_dir / "report.md")
    print(json.dumps(result["summary"], indent=2))
    if restore_debug_access is not None:
        restore_debug_access()
        atexit.unregister(restore_debug_access)
    return 0 if result["summary"]["http_success"] == 100 else 1


if __name__ == "__main__":
    raise SystemExit(main())
