"""OPTIONAL_PHASE_S S5/S6 — live LLM probes (run outside pytest)."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
for _p in (REPO_ROOT / "backend", REPO_ROOT):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from app.config import settings  # noqa: E402
from app.spl.draft_quality import evaluate_draft_quality  # noqa: E402
from app.spl.llm_fallback import (  # noqa: E402
    generate_llm_spl_fallback,
    set_spl_efficiency_prompt_enabled,
    spl_advisory_prompts,
)
from app.spl.spl_optimization_llm import apply_optimization_llm  # noqa: E402

EVALS = REPO_ROOT / "docs" / "evals" / "spl_optimization"

S5_CASES: list[dict[str, str]] = [
    {"id": "s5.01", "q": "Top 10 source IPs with failed Windows logons in the last hour."},
    {"id": "s5.02", "q": "DNS queries to newly registered domains from OT jump hosts in the last 24h."},
    {"id": "s5.03", "q": "Modbus write commands to PLCs from non-engineering workstations."},
    {"id": "s5.04", "q": "Outbound sessions from substation IEDs to corporate network ranges."},
    {"id": "s5.05", "q": "Privileged AD group membership changes in the last 6 hours."},
    {"id": "s5.06", "q": "Sysmon process spawn where parent is a web server and child is a shell."},
    {"id": "s5.07", "q": "Firewall allows from IT zone to OT zone on non-standard ports."},
    {"id": "s5.08", "q": "Repeated authentication failures against HMI portals by source IP."},
]

S6_FIXTURE = (
    "search index=<ot_index> sourcetype=<ot_sourcetype> earliest=-24h latest=now "
    "NOT status=success | eval x=1 | stats count by src_ip dest_ip user "
    "| sort -count | head 100"
)


def _enable_llm() -> None:
    settings.ai_soc_llm_spl_fallback_enabled = True
    settings.ai_soc_llm_enabled = True
    settings.ai_soc_spl_optimization_llm_enabled = True
    if settings.ai_soc_llm_mode.strip().lower() in {"disabled", "mock", ""}:
        settings.ai_soc_llm_mode = "local"


def _gate_ok(result: Any) -> bool:
    if result is None:
        return False
    if getattr(result, "clarification_required", False):
        return False
    spl = str(getattr(result, "candidate_spl", "") or "").strip()
    if not spl:
        return False
    validation = getattr(result, "validation", {}) or {}
    return bool(validation.get("approved") is not False or spl)


def probe_s5(*, with_efficiency: bool, live_limit: int) -> dict[str, Any]:
    set_spl_efficiency_prompt_enabled(with_efficiency)
    rows: list[dict[str, Any]] = []
    for idx, case in enumerate(S5_CASES[:live_limit]):
        t0 = time.monotonic()
        result = generate_llm_spl_fallback(
            user_query=case["q"],
            correctness_mode=True,
        )
        latency_ms = int((time.monotonic() - t0) * 1000)
        spl = str(getattr(result, "candidate_spl", "") or "") if result else ""
        quality = evaluate_draft_quality(spl).to_dict() if spl else {}
        rows.append(
            {
                "id": case["id"],
                "gate_ok": _gate_ok(result),
                "latency_ms": latency_ms,
                "cold": idx == 0,
                "has_index": "index=" in spl.lower(),
                "has_time_bounds": "earliest=" in spl.lower(),
                "advisory_count": quality.get("advisory_count", 0),
                "optimization_classification": quality.get("optimization_classification"),
                "spl_len": len(spl),
            }
        )
    gate_pass = sum(1 for r in rows if r["gate_ok"])
    return {
        "variant": "with_efficiency" if with_efficiency else "baseline",
        "accuracy": f"{gate_pass}/{len(rows)}",
        "gate_pass": gate_pass,
        "total": len(rows),
        "rows": rows,
        "prompt_has_efficiency": "Efficiency guidance" in spl_advisory_prompts("probe", correctness_mode=True)[0],
    }


def probe_s6() -> dict[str, Any]:
    quality = evaluate_draft_quality(S6_FIXTURE)
    t0 = time.monotonic()
    result = apply_optimization_llm(
        S6_FIXTURE,
        classification=quality.optimization_classification,
        advisory_rules=[f.rule_id for f in quality.findings if f.severity == "advisory"],
        user_query="Hunt inefficient OT auth failures",
        llm_lineage=True,
    )
    latency_ms = int((time.monotonic() - t0) * 1000)
    return {
        "classification": quality.optimization_classification,
        "outcome": result.outcome,
        "latency_ms": latency_ms,
        "model": result.model,
        "v1_len": len(result.candidate_spl_v1),
        "v2_len": len(result.candidate_spl_v2 or ""),
        "skip_reason": result.skip_reason,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="S5/S6 live LLM probes for OPTIONAL_PHASE_S")
    parser.add_argument("--live-limit", type=int, default=4, help="S5 cases to run (default 4)")
    parser.add_argument("--s5-only", action="store_true")
    parser.add_argument("--s6-only", action="store_true")
    args = parser.parse_args()

    _enable_llm()
    EVALS.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = {"timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}

    if not args.s6_only:
        payload["s5_baseline"] = probe_s5(with_efficiency=False, live_limit=args.live_limit)
        # Warm the KV cache with efficiency block before measuring warm rows
        time.sleep(0.5)
        payload["s5_with_efficiency"] = probe_s5(with_efficiency=True, live_limit=args.live_limit)

    if not args.s5_only:
        payload["s6_optimization_llm"] = probe_s6()

    out_path = EVALS / "s5_s6_live_probe_results_v1.json"
    out_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"written": str(out_path), **{k: v for k, v in payload.items() if k != "s5_baseline"}}, indent=2))
    if not args.s6_only:
        print(
            f"S5 baseline: {payload['s5_baseline']['accuracy']} | "
            f"with efficiency: {payload['s5_with_efficiency']['accuracy']}"
        )
    if not args.s5_only:
        print(f"S6 outcome: {payload['s6_optimization_llm']['outcome']} latency={payload['s6_optimization_llm']['latency_ms']}ms")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
