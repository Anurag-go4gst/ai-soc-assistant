#!/usr/bin/env python3
"""Plan 7 C3 — controlled T4 re-measurement against the corrected interface.

Drives the **real** `maybe_enrich_t4_semantic` seam with the **real** live provider,
so the deterministic merge, the shape adapter and every guard are exercised exactly
as production would. It deliberately does not go through `/chat`: a full turn adds
~90s of unrelated pipeline per case and measures things this item is not asking about.

Never restarts, reconfigures or probes anything beyond one warm-up inference.
Read-only with respect to the deployment.

    python3 scripts/eval_plan7_c3_t4_measure.py --out docs/evals/plan7/c3_remeasurement.json
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
for _path in (ROOT / "backend", ROOT):
    _text = str(_path)
    if _text not in sys.path:
        sys.path.insert(0, _text)

# Match the deployed VPS remediation value. This sets the measurement's own bound;
# it does not change the deployment, which already reads 120 from its env.
os.environ.setdefault("AI_SOC_T4_SEMANTIC_UNDERSTANDING_TIMEOUT_SECONDS", "120")

from app.chat.contracts.resolved_query import ResolvedQueryContract  # noqa: E402
from app.chat.debug_summary import redact_resolved_query  # noqa: E402
from app.chat.intent_classifier import build_query_to_intent  # noqa: E402
from app.chat.resolved_query_builder import build_resolved_query_contract  # noqa: E402
from app.chat.semantic_t4_understanding import maybe_enrich_t4_semantic  # noqa: E402
from app.config import settings  # noqa: E402
from app.query_understanding.parser import understand_query  # noqa: E402

CASES: tuple[tuple[str, str, str], ...] = (
    ("lateral_movement", "signs that something is moving sideways through the estate",
     "semantic question: name the objective, keep lateral movement a hypothesis"),
    ("competing_hypotheses", "powershell on endpoints talking to new domains",
     "benign and malicious must both stay on the table"),
    ("missing_context", "compare this with what happened last week and tell me if it is getting worse",
     "unresolved referent: clarification is the correct answer"),
    ("spl_capable_paraphrase", "any domain lookups that look algorithmically generated",
     "evidence need should ultimately require SPL-capable downstream work"),
)


def _host_state() -> dict[str, Any]:
    """Memory/swap/load snapshot. Observation only."""
    state: dict[str, Any] = {}
    try:
        meminfo = dict(
            (parts[0].rstrip(":"), int(parts[1]))
            for parts in (line.split() for line in Path("/proc/meminfo").read_text().splitlines())
            if len(parts) >= 2 and parts[1].isdigit()
        )
        state["mem_total_mb"] = meminfo.get("MemTotal", 0) // 1024
        state["mem_available_mb"] = meminfo.get("MemAvailable", 0) // 1024
        state["swap_total_mb"] = meminfo.get("SwapTotal", 0) // 1024
        state["swap_free_mb"] = meminfo.get("SwapFree", 0) // 1024
    except OSError:
        pass
    try:
        state["loadavg"] = Path("/proc/loadavg").read_text().split()[:3]
    except OSError:
        pass
    try:
        proc = subprocess.run(
            ["ps", "-o", "pid=,rss=,stat=", "-C", "llama-server"],
            capture_output=True, text=True, timeout=10, check=False,
        )
        rows = [line.split() for line in (proc.stdout or "").strip().splitlines() if line.strip()]
        state["llama_server"] = [
            {"pid": row[0], "rss_mb": int(row[1]) // 1024, "stat": row[2]} for row in rows if len(row) >= 3
        ]
    except (OSError, subprocess.SubprocessError):
        pass
    return state


def _deterministic_contract(query: str) -> ResolvedQueryContract:
    """The same contract the runtime builds, pinned to T4 so the hop is eligible."""
    understanding = understand_query(query)
    q2i = build_query_to_intent(query=query, query_understanding=understanding)
    return build_resolved_query_contract(
        query=query,
        query_understanding=understanding,
        qualification_tier="T4",
        qualification_source="c3_remeasurement",
        query_to_intent=q2i,
    )


def _base_view(contract: ResolvedQueryContract) -> dict[str, Any]:
    return {
        "intent_family": contract.intent_family,
        "answer_goal": contract.answer_goal,
        "ambiguity_state": contract.ambiguity_state,
        "clarification_required": contract.clarification_required,
        "required_capabilities": sorted(contract.required_capabilities),
        "prohibited_capabilities": sorted(contract.prohibited_capabilities),
        "evidence_requirements": list(contract.evidence_requirements),
        "normalized_goal": contract.normalized_goal,
        "time_scope": contract.time_scope,
    }


def _measure(case_id: str, query: str, intent: str) -> dict[str, Any]:
    base = _deterministic_contract(query)
    before = _host_state()
    started = time.monotonic()
    enriched = maybe_enrich_t4_semantic(base, query=query)
    wall_ms = int((time.monotonic() - started) * 1000)
    after = _host_state()

    redacted = redact_resolved_query(enriched.model_dump())
    trace = redacted.get("semantic_t4") or {}
    base_view, post_view = _base_view(base), _base_view(enriched)

    added_evidence = [
        item for item in post_view["evidence_requirements"]
        if item not in base_view["evidence_requirements"]
    ]
    return {
        "case_id": case_id,
        "query": query,
        "intent_of_case": intent,
        "invoked": bool(trace.get("invoked")),
        "accepted": bool(trace.get("accepted")),
        "timed_out": bool(trace.get("timed_out")),
        "elapsed_ms": trace.get("elapsed_ms"),
        "wall_ms": wall_ms,
        "proposed_fields": trace.get("proposed_fields") or [],
        "accepted_fields": trace.get("accepted_fields") or [],
        "rejected_reasons": trace.get("rejected_reasons") or [],
        "notes": trace.get("notes") or [],
        "base": base_view,
        "post_merge": post_view,
        "clarification_added": bool(post_view["clarification_required"])
        and not bool(base_view["clarification_required"]),
        "evidence_requirements_added": added_evidence,
        "locked_facts_preserved": (
            base_view["intent_family"] == post_view["intent_family"]
            and base_view["answer_goal"] == post_view["answer_goal"]
        ),
        "capability_widening": sorted(
            set(post_view["required_capabilities"]) - set(base_view["required_capabilities"])
        ),
        "host_before": before,
        "host_after": after,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="docs/evals/plan7/c3_remeasurement.json")
    parser.add_argument("--skip-warmup", action="store_true")
    args = parser.parse_args()

    print(json.dumps({"t4_enabled": bool(settings.ai_soc_t4_semantic_understanding_enabled),
                      "timeout_s": settings.ai_soc_t4_semantic_understanding_timeout_seconds,
                      "host": _host_state()}), flush=True)

    warmup: dict[str, Any] | None = None
    if not args.skip_warmup:
        # One warm-up inference: an unpaged first token costs 50s+ on this host and
        # would otherwise be charged to case 1.
        started = time.monotonic()
        contract = _deterministic_contract(CASES[0][1])
        enriched = maybe_enrich_t4_semantic(contract, query=CASES[0][1])
        trace = (enriched.provenance or {}).get("semantic_t4") or {}
        warmup = {
            "wall_ms": int((time.monotonic() - started) * 1000),
            "accepted": bool(trace.get("accepted")),
            "timed_out": bool(trace.get("timed_out")),
            "elapsed_ms": trace.get("elapsed_ms"),
        }
        print(json.dumps({"warmup": warmup}), flush=True)

    results = []
    for case_id, query, intent in CASES:
        row = _measure(case_id, query, intent)
        results.append(row)
        print(json.dumps({k: row[k] for k in (
            "case_id", "accepted", "timed_out", "elapsed_ms",
            "proposed_fields", "accepted_fields", "rejected_reasons",
            "clarification_added", "locked_facts_preserved", "capability_widening",
        )}), flush=True)

    payload = {
        "timeout_seconds": settings.ai_soc_t4_semantic_understanding_timeout_seconds,
        "warmup": warmup,
        "cases": results,
    }
    out = ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"ok": True, "out": args.out}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
