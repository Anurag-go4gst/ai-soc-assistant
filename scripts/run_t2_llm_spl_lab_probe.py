#!/usr/bin/env python3
"""T2 LLM SPL producer lab probe (plan T-1 / T-4).

Isolates the governed LLM SPL producer (`generate_llm_spl_fallback`) on
out-of-catalogue T2 hunts and proves the gate chain:
  fired -> strict JSON -> role adapter -> deterministic validation -> SOC-STD lint
  -> review-only exposure (execution_eligible forced false, normalized_spl null).

Modes:
  --mock  inject deterministic LLM JSON; offline, fast, reproducible (default)
  --live  call the on-host llama-server (foundation-sec 8B) at :8081; capped to
          --live-limit questions (default 2) because the single-slot 8B is slow.

This does NOT flip global posture: it enables the producer flags only inside this
process. MCP execution stays off; candidate SPL is never executable.
"""

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

EVALS_DIR = REPO_ROOT / "docs" / "evals"


def _out_paths(mode: str) -> tuple[Path, Path]:
    return (
        EVALS_DIR / f"t2_llm_spl_lab_probe_{mode}_results.json",
        EVALS_DIR / f"t2_llm_spl_lab_probe_{mode}_report.md",
    )

LIVE_BASE_URL = "http://127.0.0.1:8081/v1"
LIVE_MODEL = "foundation-sec-1.1-8b-instruct-q8_0.gguf"

# Out-of-catalogue T2 hunt questions (SPL-shaped) drawn from the pj/pk banks.
QUESTIONS: list[dict[str, str]] = [
    {"id": "pj.001", "q": "Hunt for a flood of DNP3 unsolicited responses from an RTU to the SCADA master outside its normal class-poll schedule."},
    {"id": "pj.002", "q": "Detect Modbus/TCP write-single-register or write-multiple-coils commands sent to boiler-control PLCs from hosts other than the approved engineering workstation."},
    {"id": "pj.004", "q": "Hunt for NTP or IRIG-B time-source manipulation across substation IEDs and the PDC."},
    {"id": "pj.007", "q": "Hunt for any outbound session from an OT asset that reached the corporate network or internet, bypassing the data diode."},
    {"id": "pj.008", "q": "Find configuration or firmware pushes to SEL or ABB numerical relays made through a vendor engineering tool outside any approved maintenance window."},
    {"id": "pj.010", "q": "Hunt for an internal host sweeping Modbus/TCP port 502 across the solar farm inverter SCADA range."},
    # Novel T2 hunts (not used while tuning the plan-compiler) — breadth eval per review verdict.
    {"id": "pn.001", "q": "Hunt for OPC tag subscription spikes on the SCADA OPC server in the last 24 hours by source host."},
    {"id": "pn.002", "q": "Detect off-hours interactive logons to substation HMI workstations grouped by user and host."},
    {"id": "pn.003", "q": "Hunt for a GOOSE message storm on the substation process LAN by source IED."},
    {"id": "pn.004", "q": "Find bulk data exports from the SCADA historian to external destinations by source host and bytes transferred."},
    {"id": "pn.005", "q": "Detect engineering VPN sessions reaching the PLC control subnet outside the approved maintenance window by user."},
    {"id": "pn.006", "q": "Hunt for DNS tunneling indicators from OT jump hosts by source host and distinct query count."},
]


def _mock_payload(query: str) -> str:
    """Deterministic, schema-valid LLM output for offline gate-chain proof."""
    # SOC-STD-SPL-001 compliant shape: epoch aliases -> strftime -> drop epoch
    # fields -> sort -> head (mirrors the governed lab-draft pattern). Placeholder
    # index/sourcetype keep it lab-tier (review-only, non-executable).
    spl = (
        "search index=<ot_index> sourcetype=<ot_sourcetype> earliest=-24h latest=now "
        "| stats count as event_count earliest(_time) as first_seen_epoch latest(_time) as last_seen_epoch "
        "by src_ip dest_ip "
        '| eval first_seen=strftime(first_seen_epoch, "%Y-%m-%d %H:%M:%S") '
        '| eval last_seen=strftime(last_seen_epoch, "%Y-%m-%d %H:%M:%S") '
        "| fields - first_seen_epoch last_seen_epoch "
        "| sort - event_count | head 100"
    )
    return json.dumps(
        {
            "status": "candidate_generated",
            "confidence_score": 0.55,
            "confidence_label": "medium",
            "detection_family": "ot_out_of_catalogue_hunt",
            "candidate_spl": spl,
            "assumptions": ["OT network/session telemetry onboarded"],
            "required_fields": ["src_ip", "dest_ip"],
            "missing_details": ["concrete index/sourcetype for this deployment"],
            "clarifying_questions": [],
            "validation_notes": [],
            "soc_std_rules_applied": [],
            "risk_notes": [],
            "execution_eligible": False,
            "governed": False,
            "catalog_approved": False,
        }
    )


def _enable_producer() -> None:
    settings.ai_soc_llm_spl_fallback_enabled = True
    settings.ai_soc_llm_enabled = True
    if settings.ai_soc_llm_mode.strip().lower() in {"disabled", "mock", ""}:
        settings.ai_soc_llm_mode = "local"


def _summarize(result: Any) -> dict[str, Any]:
    if result is None:
        return {"fired": False, "reason": "producer_returned_none"}
    validation = getattr(result, "validation", {}) or {}
    spl = getattr(result, "candidate_spl", None) or ""
    return {
        "fired": True,
        "status": getattr(result, "status", None),
        "lab_tier": bool(getattr(result, "lab_tier", False)),
        "clarification_required": bool(getattr(result, "clarification_required", False)),
        "clarification_reason": getattr(result, "clarification_reason", None),
        # governance invariants — must hold on every row
        "validation_approved": validation.get("approved"),
        "normalized_spl_is_null": validation.get("normalized_spl") is None,
        "execution_eligible": getattr(result, "execution_eligible", None),
        "quality_status": getattr(result, "quality_status", None),
        "hard_fail_count": getattr(result, "hard_fail_count", None),
        "reject_reasons": list(validation.get("reject_reasons") or []),
        "latency_ms": getattr(result, "latency_ms", None),
        "candidate_spl_excerpt": (spl[:240] + "…") if len(spl) > 240 else spl,
        "adapter_errors": list(getattr(result, "adapter_errors", []) or []),
    }


def run(mode: str, live_limit: int, live_timeout: int = 120) -> dict[str, Any]:
    from app.spl.llm_fallback import generate_llm_spl_fallback

    _enable_producer()
    live_client = None
    if mode in {"live", "plan"}:
        from app.llm.clients.local_chat_client import LocalChatClient

        live_client = LocalChatClient(base_url=LIVE_BASE_URL, model=LIVE_MODEL, timeout_seconds=live_timeout)

    rows: list[dict[str, Any]] = []
    questions = QUESTIONS[:live_limit] if mode in {"live", "plan"} else QUESTIONS
    for entry in questions:
        started = time.monotonic()
        try:
            if mode == "plan":
                # Plan-plus-compiler: LLM emits a small detection plan (seeded),
                # deterministic code compiles SOC-STD-compliant SPL. Run twice to
                # verify the seeded plan is byte-stable.
                from app.spl.llm_plan_compiler import generate_llm_spl_via_plan

                result = generate_llm_spl_via_plan(user_query=entry["q"], client=live_client)
                second = generate_llm_spl_via_plan(user_query=entry["q"], client=live_client)
                observed = _summarize(result)
                observed["repeatable"] = (
                    result is not None
                    and second is not None
                    and getattr(result, "candidate_spl", None) == getattr(second, "candidate_spl", None)
                )
            elif mode == "live":
                # correctness_mode mirrors the pipeline's T2 producer call.
                result = generate_llm_spl_fallback(
                    user_query=entry["q"], client=live_client, correctness_mode=True
                )
                observed = _summarize(result)
            else:
                result = generate_llm_spl_fallback(
                    user_query=entry["q"], llm_raw_output_provider=lambda q=entry["q"]: _mock_payload(q)
                )
                observed = _summarize(result)
        except Exception as exc:  # noqa: BLE001 - probe must report, not crash
            observed = {"fired": False, "error": f"{type(exc).__name__}: {exc}"}
        observed["wall_ms"] = int((time.monotonic() - started) * 1000)
        rows.append({**entry, "observed": observed})

    fired = sum(1 for r in rows if r["observed"].get("fired"))
    invariants_held = sum(
        1
        for r in rows
        if r["observed"].get("fired")
        and r["observed"].get("normalized_spl_is_null") is True
        and r["observed"].get("execution_eligible") in (False, None)
        and r["observed"].get("validation_approved") in (False, None)
    )
    return {
        "mode": mode,
        "total": len(rows),
        "producer_fired": fired,
        "governance_invariants_held": invariants_held,
        "rows": rows,
    }


def write_markdown(result: dict[str, Any], out_md: Path) -> None:
    lines = [
        "# T2 LLM SPL Producer — Lab Probe",
        "",
        f"Mode: **{result['mode']}** | Questions: **{result['total']}** | "
        f"Producer fired: **{result['producer_fired']}/{result['total']}** | "
        f"Governance invariants held: **{result['governance_invariants_held']}/{result['producer_fired']}**",
        "",
        "Invariant on every fired row: `normalized_spl` is null, `execution_eligible` is false, "
        "`validation.approved` is false — candidate SPL is review-only, never executable.",
        "",
    ]
    for row in result["rows"]:
        o = row["observed"]
        lines.append(f"### {row['id']}")
        lines.append(f"> {row['q']}")
        lines.append("")
        if not o.get("fired"):
            lines.append(f"- **did not fire**: {o.get('error') or o.get('reason')}")
            lines.append("")
            continue
        lines.append(
            f"- fired=`{o['fired']}` status=`{o.get('status')}` lab_tier=`{o.get('lab_tier')}` "
            f"approved=`{o.get('validation_approved')}` normalized_spl_null=`{o.get('normalized_spl_is_null')}` "
            f"execution_eligible=`{o.get('execution_eligible')}`"
        )
        lines.append(f"- quality_status=`{o.get('quality_status')}` latency_ms=`{o.get('latency_ms')}` wall_ms=`{o.get('wall_ms')}`")
        if o.get("adapter_errors"):
            lines.append(f"- adapter_errors: {o['adapter_errors']}")
        lines.append(f"- SPL: `{o.get('candidate_spl_excerpt')}`")
        lines.append("")
    out_md.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["mock", "live", "plan"], default="mock")
    parser.add_argument("--live-limit", type=int, default=2)
    parser.add_argument("--live-timeout", type=int, default=120)
    args = parser.parse_args()
    result = run(args.mode, args.live_limit, args.live_timeout)
    out_json, out_md = _out_paths(args.mode)
    out_json.write_text(json.dumps(result, indent=2), encoding="utf-8")
    write_markdown(result, out_md)
    print(
        json.dumps(
            {
                "mode": result["mode"],
                "producer_fired": result["producer_fired"],
                "total": result["total"],
                "governance_invariants_held": result["governance_invariants_held"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
