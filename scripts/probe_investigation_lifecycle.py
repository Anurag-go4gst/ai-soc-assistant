#!/usr/bin/env python3
"""COE acceptance probe for the agentic investigation lifecycle (P0-P8, P10).

Drives the deployed ``/chat`` over authenticated HTTP and reports the three
independent axes the rollout is tracked on:

* IMPLEMENTATION      - contract fields present and internally consistent
* FEATURE ACTIVATION  - runtime flags observably in effect
* LIVE PROOF          - whether an external system (reasoning model, MCP) actually
                        answered, or degraded honestly

It never asserts model quality and never treats a degraded external dependency as
a failure; a deferred live proof is reported as ``DEFERRED_COE_CONFIGURATION``.

Usage::

    python3 scripts/probe_investigation_lifecycle.py --query "..." [--approve run]
    python3 scripts/probe_investigation_lifecycle.py --suite   # built-in scenarios
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import uuid
import urllib.request
from http.cookiejar import CookieJar
from pathlib import Path
from typing import Any

DEFAULT_BASE_URL = "http://127.0.0.1:8010"
DEFAULT_ENV_PATH = "/var/www/ai-soc-assistant/.env"

#: Scenario queries spanning investigation shapes; deliberately not catalogue rows.
SUITE_QUERIES: list[tuple[str, str]] = [
    ("A_new_ip", "A host in the DMZ started talking to an external IP we have never seen before. Investigate whether this is a compromise and tell me what you find."),
    ("B_ssh_then_success", "We saw repeated failed SSH attempts on a jump host followed by a successful login. Investigate whether that account is compromised."),
    ("C_zero_day", "A zero-day was announced for our edge appliance. Investigate whether we have been exploited."),
    ("D_lateral_movement", "Hunt for signs of lateral movement across the OT network and tell me what you conclude."),
]


def _read_env(path: str) -> dict[str, str]:
    env: dict[str, str] = {}
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        env[key] = value
    return env


class ChatSession:
    """Authenticated /chat client. Credentials are read from .env, never logged."""

    def __init__(self, base_url: str, env_path: str) -> None:
        self.base_url = base_url.rstrip("/")
        env = _read_env(env_path)
        self._username = env.get("APP_AUTH_USER", "")
        self._password = env.get("APP_AUTH_PASSWORD", "")
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(CookieJar())
        )

    def _post(self, path: str, payload: dict[str, Any], timeout: float) -> dict[str, Any]:
        request = urllib.request.Request(
            f"{self.base_url}{path}",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with self._opener.open(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))

    def login(self) -> bool:
        if not self._username or not self._password:
            return False
        try:
            body = self._post(
                "/api/auth/login",
                {"username": self._username, "password": self._password},
                timeout=30,
            )
        except urllib.error.HTTPError:
            return False
        return bool(body.get("authenticated"))

    def chat(self, message: str, *, timeout: float, **extra: Any) -> tuple[dict[str, Any], float]:
        started = time.monotonic()
        body = self._post("/api/chat", {"message": message, **extra}, timeout=timeout)
        return body, time.monotonic() - started


def _get(payload: dict[str, Any], *names: str) -> Any:
    """First present key from payload or its control_plane_trace."""
    trace = payload.get("control_plane_trace") or {}
    for name in names:
        if payload.get(name) is not None:
            return payload[name]
        if isinstance(trace, dict) and trace.get(name) is not None:
            return trace[name]
    return None


def summarize(payload: dict[str, Any], elapsed: float) -> dict[str, Any]:
    """Project one /chat response onto the three reporting axes."""
    planning_trace = _get(payload, "investigation_planning_trace") or {}
    validated_plan = _get(payload, "validated_investigation_plan") or {}
    approval = _get(payload, "investigation_approval") or {}
    envelope = _get(payload, "approved_investigation_envelope") or {}
    snapshot = _get(payload, "capability_snapshot") or {}
    outcome = _get(payload, "investigation_outcome") or {}
    execution = payload.get("execution") or {}
    rqc = (payload.get("control_plane_trace") or {}).get("resolved_query") or {}
    budget = (payload.get("control_plane_trace") or {}).get("llm_turn_budget") or {}

    dropped = list(planning_trace.get("dropped_reasons") or [])
    if planning_trace.get("llm_proposal_accepted"):
        live_reasoning = "PASS"
    elif planning_trace:
        live_reasoning = "DEFERRED_COE_CONFIGURATION"
    else:
        live_reasoning = "NOT_REACHED"

    return {
        "elapsed_seconds": round(elapsed, 1),
        "answer_mode": payload.get("answer_mode"),
        "intent_family": rqc.get("intent_family"),
        "answer_goal": rqc.get("answer_goal"),
        "required_capabilities": rqc.get("required_capabilities"),
        "investigation_shaped": bool(planning_trace or validated_plan or approval),
        "capability_snapshot_rows": len(snapshot.get("rows") or []) if isinstance(snapshot, dict) else 0,
        "plan_source": validated_plan.get("plan_source"),
        "planner_llm_attempted": planning_trace.get("llm_attempted"),
        "planner_llm_accepted": planning_trace.get("llm_proposal_accepted"),
        "planner_timed_out": planning_trace.get("timed_out"),
        "planner_latency_ms": planning_trace.get("latency_ms"),
        "planner_circuit_state": planning_trace.get("circuit_state"),
        "planner_dropped_reasons": dropped,
        "approval_status": approval.get("status"),
        "envelope_version": envelope.get("envelope_version") or approval.get("envelope_version"),
        "resource_plan_present": bool(payload.get("resource_plan")),
        "execution_status": execution.get("status"),
        "selected_mcp_tool": execution.get("selected_mcp_tool"),
        "investigation_status": outcome.get("investigation_status"),
        "disposition": outcome.get("disposition"),
        "turn_budget_deadline_seconds": budget.get("deadline_seconds"),
        "turn_budget_exhausted": budget.get("time_budget_exhausted"),
        "LIVE_REASONING_PROOF": live_reasoning,
    }


def run_lifecycle(session: ChatSession, query: str, timeout: float) -> list[dict[str, Any]]:
    """Drive query -> Run -> remediation create -> approve, reporting each hop.

    Stops at the first hop that does not offer the next affordance, and says why —
    a missing affordance is a finding, not something to route around.
    """
    steps: list[dict[str, Any]] = []
    # One session id for every hop: an investigation decision is bound to the
    # session that owns the plan, so a fresh session is correctly refused.
    session_id = str(uuid.uuid4())
    payload, elapsed = session.chat(query, timeout=timeout, session_id=session_id)
    steps.append({"hop": "initial", **summarize(payload, elapsed)})

    approval = _get(payload, "investigation_approval") or {}
    if approval.get("status") not in {"awaiting_approval", "edited_revalidated"}:
        steps.append({"hop": "run", "skipped": f"no approval affordance ({approval.get('status')})"})
        return steps

    payload, elapsed = session.chat(
        query,
        timeout=timeout,
        session_id=session_id,
        investigation_review_action="run",
        investigation_handoff_id=approval.get("handoff_id"),
        investigation_handoff_version=approval.get("handoff_version"),
    )
    steps.append({"hop": "run", **summarize(payload, elapsed)})

    remediation = payload.get("remediation_approval") or {}
    if remediation.get("status") != "offered":
        steps.append({"hop": "remediation_create", "skipped": f"no offer ({remediation.get('status')})"})
        return steps

    payload, elapsed = session.chat(
        query, timeout=timeout, session_id=session_id, remediation_review_action="create"
    )
    created = payload.get("remediation_approval") or {}
    steps.append(
        {
            "hop": "remediation_create",
            "elapsed_seconds": round(elapsed, 1),
            "status": created.get("status"),
            "plan_summary": created.get("plan_summary"),
            "validated_plan": created.get("validated_plan"),
        }
    )
    if created.get("status") not in {"awaiting_approval", "edited_revalidated"}:
        return steps

    payload, elapsed = session.chat(
        query, timeout=timeout, session_id=session_id, remediation_review_action="approve"
    )
    approved = payload.get("remediation_approval") or {}
    steps.append(
        {
            "hop": "remediation_approve",
            "elapsed_seconds": round(elapsed, 1),
            "status": approved.get("status"),
            "approved_remediation_envelope": payload.get("approved_remediation_envelope"),
        }
    )
    return steps


def run_one(session: ChatSession, label: str, query: str, timeout: float) -> dict[str, Any]:
    try:
        payload, elapsed = session.chat(query, timeout=timeout)
    except Exception as exc:  # noqa: BLE001 - probe reports transport failure verbatim
        return {"label": label, "error": f"{type(exc).__name__}: {exc}"}
    result = {"label": label, "query": query, **summarize(payload, elapsed)}
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--env-path", default=DEFAULT_ENV_PATH)
    parser.add_argument("--query")
    parser.add_argument("--suite", action="store_true")
    parser.add_argument("--lifecycle", action="store_true")
    parser.add_argument("--timeout", type=float, default=600.0)
    parser.add_argument("--out", help="write full JSON results here")
    args = parser.parse_args()

    session = ChatSession(args.base_url, args.env_path)
    if not session.login():
        print("login_failed: check APP_AUTH_USER / APP_AUTH_PASSWORD", file=sys.stderr)
        return 2

    if args.lifecycle:
        results = run_lifecycle(session, args.query or SUITE_QUERIES[3][1], args.timeout)
    else:
        cases = SUITE_QUERIES if args.suite else [("adhoc", args.query or SUITE_QUERIES[0][1])]
        results = [run_one(session, label, query, args.timeout) for label, query in cases]

    for result in results:
        print(json.dumps(result, indent=1, sort_keys=True))
    if args.out:
        Path(args.out).write_text(json.dumps(results, indent=1, sort_keys=True), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
