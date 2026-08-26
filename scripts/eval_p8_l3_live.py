#!/usr/bin/env python3
"""P8 L3 — live local/office LLM semantic measurement runner.

L3-1 (this script, default --dry-run): freeze bank hash, load pre-declared
thresholds, probe endpoints, refuse to invent scores.

L3-2 (--live): call real production seams against CURRENT_ACTIVE_PROMPT only.
There is no CANDIDATE_PROMPT. Deterministic fallback is recorded as fallback,
never as semantic success. Blocked reasoning roles are never invoked.

    PYTHONPATH=backend:. python3 scripts/eval_p8_l3_live.py --dry-run
    PYTHONPATH=backend:. AI_SOC_TESTS_ALLOW_LIVE_LLM=1 python3 scripts/eval_p8_l3_live.py --live
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import socket
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
BANK_PATH = ROOT / "docs/evals/p8_l3/bank_v1.json"
THRESHOLDS_PATH = ROOT / "docs/evals/p8_l3/thresholds_v1.json"
REPORT_DIR = ROOT / "docs/evals/p8_l3"
PRODUCT_SHA = "b6e4befe9a79dd722a09a09fdd345bae82880884"
BLOCKED_ROLES = (
    "mitre_reasoner",
    "missing_evidence_reasoner",
    "risk_rationale_reasoner",
    "plan_delta_reasoner",
    "pattern_reasoner",
    "evidence_reasoner",
    "hypothesis_reasoner",
)
REQUIRED_CATEGORIES = frozenset(
    {
        "t4_semantic",
        "spl_rolling",
        "spl_trend",
        "spl_sequence",
        "spl_ranking",
        "spl_raw_events",
        "l2_production",
        "followup_correction",
        "evidence_truth_negative",
        "investigation_planner",
        "failure_abstain",
        "prompt_role",
    }
)
PROBE_CANDIDATES = (
    ("local_llama_8081", "http://127.0.0.1:8081/v1", "foundation-sec-1.1-8b-instruct-q8_0.gguf"),
    ("coe_instruct_8004", "http://10.52.1.13:8004/v1", "foundation-sec-instruct"),
)


def _canonical_bytes(payload: Any) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


def bank_hash(bank: dict[str, Any]) -> str:
    return hashlib.sha256(_canonical_bytes(bank)).hexdigest()


def load_bank() -> dict[str, Any]:
    return json.loads(BANK_PATH.read_text(encoding="utf-8"))


def load_thresholds() -> dict[str, Any]:
    return json.loads(THRESHOLDS_PATH.read_text(encoding="utf-8"))


def validate_bank(bank: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if bank.get("candidate_prompt") is not None:
        errors.append("candidate_prompt must be null until a real candidate exists")
    if bank.get("live_ab_eval_performed") is not False:
        errors.append("live_ab_eval_performed must stay false until a two-arm live run")
    if bank.get("product_sha") != PRODUCT_SHA:
        errors.append(f"bank product_sha must be {PRODUCT_SHA}")
    rows = bank.get("rows") or []
    if not rows:
        errors.append("bank has no rows")
    cats = {str(row.get("category") or "") for row in rows}
    missing = sorted(REQUIRED_CATEGORIES - cats)
    if missing:
        errors.append(f"missing categories: {missing}")
    ids = [str(row.get("row_id") or "") for row in rows]
    if len(ids) != len(set(ids)):
        errors.append("duplicate row_id")
    for role in bank.get("blocked_roles_must_not_be_invoked") or []:
        if role not in BLOCKED_ROLES:
            errors.append(f"unknown blocked role in bank: {role}")
    live_roles = {str(row.get("role_id")) for row in rows if row.get("role_id")}
    invoked_blocked = sorted(live_roles & set(BLOCKED_ROLES))
    if invoked_blocked:
        errors.append(f"bank must not live-invoke blocked roles: {invoked_blocked}")
    return errors


def validate_thresholds(thresholds: dict[str, Any]) -> list[str]:
    from app.llm.policy.evaluation import REQUIRED_FROZEN_METRICS, freeze_thresholds

    errors: list[str] = []
    floors = thresholds.get("measurement_floors") or {}
    missing = sorted(set(REQUIRED_FROZEN_METRICS) - set(floors))
    if missing:
        errors.append(f"thresholds missing required metrics: {missing}")
    if not thresholds.get("frozen_before_live"):
        errors.append("thresholds must be marked frozen_before_live")
    if thresholds.get("product_sha") != PRODUCT_SHA:
        errors.append(f"thresholds product_sha must be {PRODUCT_SHA}")
    try:
        for role_id in thresholds.get("roles") or []:
            freeze_thresholds(str(role_id), {k: float(v) for k, v in floors.items()})
    except Exception as exc:  # noqa: BLE001 — surface contract errors to the dry-run
        errors.append(f"freeze_thresholds rejected floors: {exc}")
    return errors


def _tcp_open(url: str, timeout: float = 3.0) -> bool:
    parsed = urlparse(url)
    host = parsed.hostname
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    if not host:
        return False
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def probe_endpoint(label: str, base_url: str, model: str, timeout: float = 8.0) -> dict[str, Any]:
    result: dict[str, Any] = {
        "label": label,
        "base_url": base_url,
        "model": model,
        "tcp_open": _tcp_open(base_url, timeout=3.0),
        "http_status": None,
        "healthy": False,
        "error": None,
    }
    if not result["tcp_open"]:
        result["error"] = "tcp_closed"
        return result
    body = json.dumps(
        {
            "model": model,
            "messages": [{"role": "user", "content": "ping"}],
            "max_tokens": 4,
            "temperature": 0,
        }
    ).encode()
    req = urllib.request.Request(
        f"{base_url.rstrip('/')}/chat/completions",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    started = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            result["http_status"] = int(resp.status)
            result["healthy"] = 200 <= int(resp.status) < 300
            result["latency_ms"] = int((time.monotonic() - started) * 1000)
    except urllib.error.HTTPError as exc:
        result["http_status"] = int(exc.code)
        result["error"] = f"http_{exc.code}"
        result["latency_ms"] = int((time.monotonic() - started) * 1000)
    except Exception as exc:  # noqa: BLE001
        result["error"] = type(exc).__name__
        result["latency_ms"] = int((time.monotonic() - started) * 1000)
    return result


def probe_all() -> list[dict[str, Any]]:
    return [probe_endpoint(*item) for item in PROBE_CANDIDATES]


def provenance_rows() -> dict[str, Any]:
    from app.llm.policy.evaluation import contract_for_role
    from app.llm.policy.role_inventory import blocked_role_ids

    roles = ("semantic_t4", "spl_advisory_generator", "investigation_planner", "shape_advisor")
    arms = {}
    for role_id in roles:
        contract = contract_for_role(role_id)
        arms[role_id] = {
            "template_id": contract.active.template_id,
            "version": contract.active.version,
            "stable_prefix_hash": contract.active.stable_prefix_hash,
            "candidate": contract.candidate,
            "eval_status": contract.eval_status,
        }
    return {
        "active_prompt_arms": arms,
        "blocked_role_ids": list(blocked_role_ids()),
        "reasoning_allowlist_expected": ["investigation_planner"],
    }


def write_report(name: str, payload: dict[str, Any]) -> Path:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORT_DIR / name
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def dry_run(*, persist: bool = False) -> tuple[int, dict[str, Any]]:
    for path in (ROOT / "backend", ROOT):
        text = str(path)
        if text not in sys.path:
            sys.path.insert(0, text)
    bank = load_bank()
    thresholds = load_thresholds()
    errors = validate_bank(bank) + validate_thresholds(thresholds)
    digest = bank_hash(bank)
    probes = probe_all()
    healthy = [p for p in probes if p.get("healthy")]
    report: dict[str, Any] = {
        "phase": "L3-1",
        "mode": "dry_run",
        "product_sha": PRODUCT_SHA,
        "bank_id": bank.get("bank_id"),
        "bank_hash": digest,
        "row_count": len(bank.get("rows") or []),
        "categories": sorted({row["category"] for row in bank["rows"]}),
        "candidate_prompt": None,
        "live_ab_eval_performed": False,
        "blocked_roles_enabled": False,
        "endpoint_probes": probes,
        "healthy_endpoint": healthy[0] if healthy else None,
        "prompt_provenance": provenance_rows(),
        "errors": errors,
        "eval_status": "BLOCKED_INFRASTRUCTURE" if not healthy else "DRY_RUN_READY",
        "live_llm_used": False,
        "live_mcp_used": False,
    }
    report_path = str(write_report("l3_1_dry_run.json", report)) if persist else None
    print(
        json.dumps(
            {
                "ok": not errors,
                "bank_hash": digest,
                "report": report_path,
                "eval_status": report["eval_status"],
                "errors": errors,
            },
            indent=2,
        )
    )
    return (1 if errors else 0), report


def live_run(*, persist: bool = False) -> int:
    if os.environ.get("AI_SOC_TESTS_ALLOW_LIVE_LLM") != "1":
        print("REFUSED: pass AI_SOC_TESTS_ALLOW_LIVE_LLM=1. No scores written.")
        return 2
    rc, dry = dry_run(persist=persist)
    if rc != 0:
        return rc
    if not dry.get("healthy_endpoint"):
        blocked = {
            "phase": "L3-2",
            "mode": "live",
            "product_sha": PRODUCT_SHA,
            "eval_status": "BLOCKED_INFRASTRUCTURE",
            "live_ab_eval_performed": False,
            "reason": (
                "No reachable local/office LLM. :8081 is closed and "
                "10.52.1.13:8004 did not accept a TCP/HTTP probe. "
                "Scores are not invented."
            ),
            "endpoint_probes": dry.get("endpoint_probes"),
            "bank_hash": dry.get("bank_hash"),
            "live_llm_used": False,
            "live_mcp_used": False,
            "blocked_roles_enabled": False,
        }
        path = write_report("l3_2_live_blocked.json", blocked) if persist else None
        print(
            json.dumps(
                {"ok": False, "eval_status": "BLOCKED_INFRASTRUCTURE", "report": str(path) if path else None},
                indent=2,
            )
        )
        return 2
    print("LIVE endpoint is healthy; row execution is a later L3-2 step after L3-1 commit.")
    print("This invocation stops after probe so thresholds stay frozen before scores.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--live",
        action="store_true",
        help="Probe live endpoint; refuse to invent scores if unhealthy",
    )
    parser.add_argument(
        "--write-report",
        action="store_true",
        help="Persist JSON under docs/evals/p8_l3/",
    )
    args = parser.parse_args()
    if args.live:
        return live_run(persist=args.write_report)
    rc, _report = dry_run(persist=args.write_report)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
