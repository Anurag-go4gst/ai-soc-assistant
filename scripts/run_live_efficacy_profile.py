#!/usr/bin/env python3
"""§4.5 live-run protocol orchestrator (preflight + profile + abort + archive).

Wraps the mature single-run engine (`run_live_efficacy_100.py`) with the plan §4.5
run protocol so the operator triggers a clean, comparable live run:

1. Preflight canaries — backend health, auth, read-only debug-bundle read, LLM
   reachability, and **server posture matches the requested profile**. Any P0 canary
   failure aborts before a single question is wasted (§4.5 item 2).
2. Profiles (§4.5 item 3-4 + §4.6 controls). The client cannot flip the running
   backend's LLM mode, so a profile *verifies* the server posture rather than setting
   it; the operator configures the backend, this orchestrator refuses a mismatched run:
     - ``deterministic`` — LLM off (baseline / fallback control); no restarts.
     - ``llm``          — LLM on; no mid-run restart (baseline comparability).
     - ``resilience``   — LLM on; restart-on-degraded + 20-question LLM canary.
3. Abort threshold — >2% HTTP 5xx aborts the cohort as unusable (§4.5 item 6).
4. Archive manifest — profile, code revision, config snapshot, scorer version, model
   health, first-attempt reliability vs resilience (§4.5 item 7).

Posture is verified through ``GET /debug/readiness``. No server flags are changed
here. Use ``--dry-run`` to run preflight only (no live questions).

Usage:
  PYTHONPATH=backend:. python3 scripts/run_live_efficacy_profile.py --profile llm
  PYTHONPATH=backend:. python3 scripts/run_live_efficacy_profile.py --profile deterministic --dry-run
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
for _p in (str(REPO / "backend"), str(REPO)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

SCORER_VERSION = "live_efficacy_scorer_v1"
DEFAULT_MAX_5XX_RATE = 0.02

# Expected server posture per profile, read from GET /debug/readiness.
PROFILE_POSTURE = {
    "deterministic": {"llm_enabled": False},
    "llm": {"llm_enabled": True, "final_synthesis_enabled": True},
    "resilience": {"llm_enabled": True, "final_synthesis_enabled": True},
}


def expected_posture(profile: str) -> dict[str, Any]:
    if profile not in PROFILE_POSTURE:
        raise ValueError(f"unknown profile {profile}")
    return PROFILE_POSTURE[profile]


def check_posture(readiness: dict[str, Any], profile: str) -> tuple[bool, list[str]]:
    """Compare the live readiness LLM block to the profile's required posture."""
    llm = readiness.get("llm") or {}
    mismatches = []
    for key, want in expected_posture(profile).items():
        got = llm.get(key)
        if bool(got) != bool(want):
            mismatches.append(f"{key}: want={want} got={got}")
    return (not mismatches), mismatches


def _http_5xx_count(summary: dict[str, Any]) -> int:
    """5xx-only count from the engine's by_error_code map (excludes transport-0/4xx)."""
    by_code = (summary.get("failure_classification") or {}).get("by_error_code") or {}
    total = 0
    for code, count in by_code.items():
        try:
            if 500 <= int(code) <= 599:
                total += int(count)
        except (TypeError, ValueError):
            continue
    return total


def first_attempt_reliability(summary: dict[str, Any]) -> dict[str, Any]:
    total = int(summary.get("total") or 0)
    ok = int(summary.get("http_success") or 0)
    return {"total": total, "http_success": ok, "http_5xx": _http_5xx_count(summary),
            "success_rate": round(ok / total, 4) if total else 0.0}


def abort_threshold_exceeded(summary: dict[str, Any], max_5xx_rate: float = DEFAULT_MAX_5XX_RATE) -> bool:
    """True when the first-attempt HTTP 5xx rate exceeds the abort threshold (§4.5)."""
    total = int(summary.get("total") or 0)
    if total <= 0:
        return False
    return (_http_5xx_count(summary) / total) > max_5xx_rate


@dataclass
class PreflightResult:
    ok: bool = True
    checks: list[dict[str, Any]] = field(default_factory=list)

    def record(self, name: str, ok: bool, detail: Any = None) -> None:
        self.checks.append({"check": name, "ok": bool(ok), "detail": detail})
        if not ok:
            self.ok = False


def run_preflight(client: Any, profile: str) -> PreflightResult:
    """Run P0 canaries against a live client. Aborts (ok=False) on any failure."""
    result = PreflightResult()

    health_status, health_body, _ = client.request("GET", "/health")
    result.record("backend_health", health_status == 200, {"http": health_status})

    try:
        auth = client.login()
        result.record("auth_login", bool(auth), {"debug_access": bool(auth.get("debug_access"))})
    except Exception as exc:  # noqa: BLE001 — a failed login is a hard preflight stop
        result.record("auth_login", False, {"error": type(exc).__name__})
        return result

    debug_status, _, _ = client.request("GET", "/debug/traces?limit=1")
    result.record("debug_bundle_canary", debug_status == 200, {"http": debug_status})

    ready_status, readiness, _ = client.request("GET", "/debug/readiness")
    result.record("readiness_reachable", ready_status == 200, {"http": ready_status})
    if ready_status == 200:
        posture_ok, mismatches = check_posture(readiness, profile)
        result.record(f"posture_matches_{profile}", posture_ok, {"mismatches": mismatches})
        # LLM profiles need a reachable model, not just an enabled flag.
        if profile in {"llm", "resilience"}:
            llm = readiness.get("llm") or {}
            reachable = bool(llm.get("llm_enabled")) and llm.get("llm_mode") not in {"mock", "disabled", None}
            result.record("llm_reachable", reachable, {"llm_mode": llm.get("llm_mode")})

    return result


def _code_revision() -> str:
    try:
        out = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO, capture_output=True, text=True, timeout=10)
        return out.stdout.strip() or "unknown"
    except Exception:  # noqa: BLE001
        return "unknown"


def _config_snapshot(readiness: dict[str, Any] | None) -> dict[str, Any]:
    """Redacted posture snapshot — booleans/modes only, never URLs or secrets."""
    if not readiness:
        return {}
    llm = readiness.get("llm") or {}
    rag = readiness.get("rag") or {}
    tel = readiness.get("telemetry") or {}
    return {
        "llm_enabled": llm.get("llm_enabled"),
        "llm_mode": llm.get("llm_mode"),
        "final_synthesis_enabled": llm.get("final_synthesis_enabled"),
        "answer_guard_enabled": llm.get("answer_guard_enabled"),
        "rag_retrieval_enabled": rag.get("retrieval_enabled"),
        "telemetry_sink": tel.get("telemetry_sink"),
    }


def build_archive_manifest(*, profile: str, summary: dict[str, Any] | None, readiness: dict[str, Any] | None,
                           preflight: PreflightResult) -> dict[str, Any]:
    summary = summary or {}
    return {
        "profile": profile,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "code_revision": _code_revision(),
        "scorer_version": SCORER_VERSION,
        "config_snapshot": _config_snapshot(readiness),
        "preflight_ok": preflight.ok,
        "preflight_checks": preflight.checks,
        "abort_5xx_triggered": abort_threshold_exceeded(summary) if summary else None,
        "reliability_first_attempt": first_attempt_reliability(summary) if summary else {},
        "resilience": (summary.get("resilience") or {}),
        "model_health": summary.get("llm_health_checks") or [],
        "note": "first-attempt numbers are the reliability score; restart/retry are resilience only (plan §4.5).",
    }


def _runner_argv(args: argparse.Namespace) -> list[str]:
    argv = ["--base-url", args.base_url, "--bank", str(args.bank), "--out-dir", str(args.out_dir),
            "--health-every", str(args.health_every)]
    if args.profile == "resilience":
        argv.append("--restart-llm-on-degraded")
    return argv


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", required=True, choices=sorted(PROFILE_POSTURE))
    ap.add_argument("--base-url", default="http://127.0.0.1:8010")
    ap.add_argument("--bank", type=Path, default=REPO / "docs/evals/live_efficacy_100_bank.json")
    ap.add_argument("--out-dir", type=Path, default=REPO / "docs/evals/live_efficacy_profile_run")
    ap.add_argument("--health-every", type=int, default=20)
    ap.add_argument("--max-5xx-rate", type=float, default=DEFAULT_MAX_5XX_RATE)
    ap.add_argument("--dry-run", action="store_true", help="preflight only; no live questions")
    args = ap.parse_args(argv)

    from scripts.run_live_efficacy_100 import LiveClient  # mature engine
    client = LiveClient(args.base_url, 170.0)

    preflight = run_preflight(client, args.profile)
    _, readiness, _ = client.request("GET", "/debug/readiness")
    readiness = readiness if isinstance(readiness, dict) else None

    print(f"preflight ({args.profile}): ok={preflight.ok}")
    for c in preflight.checks:
        print(f"  [{'PASS' if c['ok'] else 'FAIL'}] {c['check']} {c['detail']}")
    if not preflight.ok:
        print("ABORT: P0 preflight canary failed; not wasting questions.")
        return 2
    if args.dry_run:
        print("dry-run: preflight passed, skipping the live cohort.")
        return 0

    from scripts.run_live_efficacy_100 import main as run_engine
    rc = run_engine(_runner_argv(args))

    summary = None
    results_path = args.out_dir / "results.json"
    if results_path.exists():
        summary = json.loads(results_path.read_text()).get("summary")

    manifest = build_archive_manifest(profile=args.profile, summary=summary, readiness=readiness, preflight=preflight)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "run_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"archive manifest -> {args.out_dir / 'run_manifest.json'}")
    if manifest["abort_5xx_triggered"]:
        print(f"ABORT: HTTP 5xx rate exceeded {args.max_5xx_rate:.0%}; cohort unusable.")
        return 3
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
