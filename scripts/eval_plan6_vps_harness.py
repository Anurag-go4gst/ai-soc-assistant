#!/usr/bin/env python3
"""Plan 6 VPS harness — wrap scripts/ask_chat.sh with redacted env capture.

Does not invent a second chat client. Secret-shaped env keys fail closed.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
for _path in (REPO_ROOT / "backend", REPO_ROOT):
    text = str(_path)
    if text not in sys.path:
        sys.path.insert(0, text)

from app.evals.plan6_env_capture import validate_env_capture  # noqa: E402

CORPUS_PATH = REPO_ROOT / "docs" / "evals" / "plan6" / "vps_corpus_v1.json"
ASK_CHAT = REPO_ROOT / "scripts" / "ask_chat.sh"
RUNS_DIR = REPO_ROOT / "docs" / "evals" / "plan6" / "runs"

REQUIRED_CLASSES = frozenset(
    {
        "t1_exact_known_knowledge",
        "t2_t3_known_nontrivial",
        "t4_out_of_registry_investigation",
        "spl_only_draft_review",
        "spl_plus_mcp_mock",
        "knowledge_spl_mcp_multistep",
        "clarification_required",
        "unsafe_action_request",
        "supplied_alert_summarization",
        "live_posture_ratified_row",
        "repeated_evidence_refinement",
        "failure_degraded_dependency",
        "t4_residual_paraphrase",
    }
)

SAFE_FLAG_NAMES = (
    "AI_SOC_RESOURCE_PLAN_EXECUTION_ENABLED",
    "AI_SOC_T4_SEMANTIC_UNDERSTANDING_ENABLED",
    "AI_SOC_T4_SEMANTIC_UNDERSTANDING_TIMEOUT_SECONDS",
    "AI_SOC_LIVE_CAPABILITY_ENFORCEMENT_ENABLED",
    "AI_SOC_PIPELINE_DISPATCH_V2_ENABLED",
    "LANGGRAPH_ORCHESTRATION_ENABLED",
    "MCP_MODE",
    "MCP_GLOBAL_EXECUTION_ENABLED",
    "MCP_SERVER_MOCK_EXECUTION_ENABLED",
)


LANE_CLASSES = frozenset(
    {
        "t1_exact_known_knowledge",
        "t2_t3_known_nontrivial",
        "t4_out_of_registry_investigation",
        "clarification_required",
    }
)
ASK_CHAT_TIMEOUT_S = 240
CHAT_BASE = os.environ.get("BASE", "http://127.0.0.1:8010")


def _boolish(raw: str | None) -> bool | str | float | None:
    if raw is None or raw == "":
        return None
    lowered = raw.strip().lower()
    if lowered in {"1", "true", "yes", "on"}:
        return True
    if lowered in {"0", "false", "no", "off"}:
        return False
    try:
        return float(raw)
    except ValueError:
        return raw


def _docker_printenv(name: str) -> str | None:
    try:
        proc = subprocess.run(
            ["docker", "compose", "exec", "-T", "backend", "printenv", name],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0:
        return None
    raw = (proc.stdout or "").strip()
    return raw or None


def capture_env(*, environment_identity: str = "local") -> dict[str, Any]:
    sha = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True
    ).strip()
    flags: dict[str, Any] = {}
    flag_presence: dict[str, str] = {}
    for name in SAFE_FLAG_NAMES:
        docker_raw = _docker_printenv(name)
        raw = docker_raw if docker_raw is not None else os.environ.get(name)
        if docker_raw is None and os.environ.get(name) is None:
            flag_presence[name] = "unset"
            if name.endswith("_SECONDS"):
                flags[name] = 2.0
            elif name == "MCP_MODE":
                continue
            else:
                flags[name] = False
            continue
        flag_presence[name] = "docker" if docker_raw is not None else "process"
        value = _boolish(raw)
        if value is None:
            continue
        flags[name] = value
    mcp_mode = str(flags.get("MCP_MODE") or _docker_printenv("MCP_MODE") or os.environ.get("MCP_MODE") or "unknown")
    payload = {
        "git_sha": sha,
        "flags": flags,
        "flag_presence": flag_presence,
        "model_endpoint_host": os.environ.get("FOUNDATION_SEC_INSTRUCT_HOST")
        or os.environ.get("LLM_ENDPOINT_HOST"),
        "model_role": "instruct",
        "db_reachable": True,
        "mcp_mode": mcp_mode if isinstance(mcp_mode, str) else "unknown",
        "mcp_connectivity": str(mcp_mode).lower() == "mock",
        "environment_identity": environment_identity,
        "test_account_role": os.environ.get("APP_AUTH_ROLE") or "demo_analyst",
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "corpus_version": "vps_corpus_v1",
    }
    errors = validate_env_capture(payload)
    if errors:
        raise SystemExit("env capture rejected: " + "; ".join(errors))
    return payload


def load_corpus() -> dict[str, Any]:
    data = json.loads(CORPUS_PATH.read_text(encoding="utf-8"))
    rows = data.get("rows")
    if not isinstance(rows, list) or not rows:
        raise SystemExit("corpus has no rows")
    classes = {str(row.get("class")) for row in rows if isinstance(row, dict)}
    missing = REQUIRED_CLASSES - classes
    if missing:
        raise SystemExit(f"corpus missing classes: {sorted(missing)}")
    return data


def rows_for_arm(corpus: dict[str, Any], arm: str) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    for row in corpus["rows"]:
        if not isinstance(row, dict):
            continue
        arms = row.get("arms") or []
        if arm in arms:
            selected.append(row)
    return selected


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Plan 6 VPS harness wrapping scripts/ask_chat.sh"
    )
    parser.add_argument("--dry-run", action="store_true", help="validate corpus + env capture only")
    parser.add_argument("--arm", default="A", help="corpus arm filter (A/B/C/D/F)")
    parser.add_argument("--environment-identity", default="local")
    parser.add_argument(
        "--row-id",
        action="append",
        default=[],
        help="optional row_id filter (repeatable). Applied after arm filter.",
    )
    parser.add_argument(
        "--env-capture-json",
        help="optional JSON file to use as env capture (must pass schema)",
    )
    args = parser.parse_args()

    corpus = load_corpus()
    if args.env_capture_json:
        capture = json.loads(Path(args.env_capture_json).read_text(encoding="utf-8"))
        errors = validate_env_capture(capture)
        if errors:
            raise SystemExit("env capture rejected: " + "; ".join(errors))
    else:
        capture = capture_env(environment_identity=args.environment_identity)

    if not capture:
        raise SystemExit("refusing to start without env capture")

    selected = rows_for_arm(corpus, args.arm)
    if args.row_id:
        wanted = set(args.row_id)
        selected = [row for row in selected if row.get("row_id") in wanted]
        if not selected:
            raise SystemExit(f"no rows matched --row-id {sorted(wanted)}")
    if args.dry_run:
        print(
            json.dumps(
                {
                    "ok": True,
                    "dry_run": True,
                    "corpus_version": corpus.get("corpus_version"),
                    "arm": args.arm,
                    "row_count": len(selected),
                    "classes": sorted(
                        {str(row.get("class")) for row in corpus["rows"] if isinstance(row, dict)}
                    ),
                    "env_git_sha": capture.get("git_sha"),
                    "ask_chat": str(ASK_CHAT),
                    "ask_chat_executable": ASK_CHAT.is_file() and os.access(ASK_CHAT, os.X_OK),
                },
                indent=2,
            )
        )
        return 0

    if not ASK_CHAT.is_file() or not os.access(ASK_CHAT, os.X_OK):
        raise SystemExit(f"ask_chat wrapper missing or not executable: {ASK_CHAT}")

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = RUNS_DIR / stamp
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "env_capture.json").write_text(
        json.dumps(capture, indent=2) + "\n", encoding="utf-8"
    )
    results: list[dict[str, Any]] = []
    missing_tier: list[str] = []
    for row in selected:
        query = str(row.get("query") or "")
        started = time.monotonic()
        try:
            proc = subprocess.run(
                [str(ASK_CHAT), query],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                check=False,
                timeout=ASK_CHAT_TIMEOUT_S,
            )
        except subprocess.TimeoutExpired:
            results.append(
                {
                    "row_id": row.get("row_id"),
                    "class": row.get("class"),
                    "exit_code": 124,
                    "trace_id": None,
                    "wall_ms": int((time.monotonic() - started) * 1000),
                    "chat": {},
                    "debug_summary_fields": {"timeout": True},
                }
            )
            if row.get("class") in LANE_CLASSES:
                missing_tier.append(str(row.get("row_id") or "timeout"))
            continue
        wall_ms = int((time.monotonic() - started) * 1000)
        body = _parse_ask_chat_body(proc.stdout or "")
        trace_id = str((body or {}).get("trace_id") or "")
        bundle_fields = _fetch_debug_field_presence(trace_id) if trace_id else {}
        row_id = str(row.get("row_id") or "")
        if row.get("class") in LANE_CLASSES and not bundle_fields.get("qualification_tier"):
            missing_tier.append(row_id or query[:40])
        results.append(
            {
                "row_id": row.get("row_id"),
                "class": row.get("class"),
                "exit_code": proc.returncode,
                "trace_id": trace_id or None,
                "wall_ms": wall_ms,
                "chat": _redact_chat_slice(body),
                "debug_summary_fields": bundle_fields,
            }
        )
    summary = {"arm": args.arm, "results": results, "missing_qualification_tier": missing_tier}
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"ok": not missing_tier, "out_dir": str(out_dir), "rows": len(results)}))
    if missing_tier:
        raise SystemExit("missing qualification_tier on debug bundle: " + ", ".join(missing_tier))
    return 0


def _parse_ask_chat_body(stdout: str) -> dict[str, Any] | None:
    marker = "--- full ---"
    if marker not in stdout:
        return None
    blob = stdout.split(marker, 1)[1].strip()
    for line in blob.splitlines():
        text = line.strip()
        if not text.startswith("{"):
            continue
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    return None


def _redact_chat_slice(body: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(body, dict):
        return {}
    workflow = body.get("workflow_plan") if isinstance(body.get("workflow_plan"), dict) else {}
    sufficiency = body.get("context_sufficiency") if isinstance(body.get("context_sufficiency"), dict) else {}
    return {
        "trace_id": body.get("trace_id"),
        "route": workflow.get("skill") or body.get("route"),
        "answer_mode": sufficiency.get("answer_mode") or body.get("answer_mode"),
        "execution_enabled": workflow.get("execution_enabled"),
    }


def _fetch_debug_field_presence(trace_id: str) -> dict[str, Any]:
    """Same auth path as ask_chat.sh. Persists field presence only, never secrets."""
    helper = REPO_ROOT / "scripts" / "fetch_debug_bundle.sh"
    proc = subprocess.run(
        [str(helper), trace_id],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
        env={**os.environ, "BASE": CHAT_BASE},
    )
    text = (proc.stdout or "").strip()
    try:
        bundle = json.loads(text)
    except json.JSONDecodeError:
        return {"bundle_parse_error": True, "http_excerpt": text[:80]}
    explain = bundle.get("explainability") if isinstance(bundle, dict) else None
    summary = explain.get("debug_summary") if isinstance(explain, dict) else None
    if not isinstance(summary, dict):
        return {"debug_summary_present": False}
    resolved = summary.get("resolved_query") if isinstance(summary.get("resolved_query"), dict) else {}
    schedule = summary.get("schedule") if isinstance(summary.get("schedule"), dict) else {}
    return {
        "debug_summary_present": True,
        "qualification_tier": resolved.get("qualification_tier"),
        "intent_family": resolved.get("intent_family"),
        "answer_goal": resolved.get("answer_goal"),
        "ambiguity_state": resolved.get("ambiguity_state"),
        "resource_plan_fingerprint": schedule.get("resource_plan_fingerprint"),
        "degrade_reason": schedule.get("degrade_reason"),
        "dispatch_schedule_present": bool(schedule.get("dispatch_schedule")),
        "phase_names": schedule.get("phase_names") or [],
        "semantic_t4": resolved.get("semantic_t4"),
        "understanding_source": resolved.get("understanding_source"),
    }


if __name__ == "__main__":
    raise SystemExit(main())
