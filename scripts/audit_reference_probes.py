#!/usr/bin/env python3
"""Audit current routing for the reference-knowledge probe contract."""

from __future__ import annotations

import json
import os
import signal
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
for _path in (ROOT / "backend", ROOT):
    _text = str(_path)
    if _text not in sys.path:
        sys.path.insert(0, _text)

# This is an offline routing/reference contract audit, not a provider availability
# test. Force advisory/live components off so local environment flags cannot add
# network noise or change the frozen route rows.
os.environ["AI_SOC_LLM_FINAL_SYNTHESIS_ENABLED"] = "false"
os.environ["AI_SOC_LLM_LIVE_SYNTHESIS_ENABLED"] = "false"
os.environ["AI_SOC_LLM_EVIDENCE_OBSERVER_ENABLED"] = "false"
os.environ["AI_SOC_LLM_SPL_FALLBACK_ENABLED"] = "false"
os.environ["AI_SOC_LLM_UTILITY_SPL_DRAFT_ENABLED"] = "false"
os.environ["MCP_GLOBAL_EXECUTION_ENABLED"] = "false"

from app.chat.pipeline import build_live_chat_response  # noqa: E402
from app.chat.answer_shape_router import classify_answer_shape  # noqa: E402
from app.config import settings  # noqa: E402
from app.schemas.requests import ChatRequest  # noqa: E402

for _setting_name in (
    "ai_soc_llm_enabled",
    "ai_soc_llm_intent_advisor_enabled",
    "ai_soc_llm_spl_fallback_enabled",
    "ai_soc_llm_utility_spl_draft_enabled",
    "ai_soc_llm_final_synthesis_enabled",
    "ai_soc_llm_live_synthesis_enabled",
    "mcp_global_execution_enabled",
):
    if hasattr(settings, _setting_name):
        setattr(settings, _setting_name, False)

PROBES = ROOT / "backend" / "app" / "tests" / "fixtures" / "reference_knowledge" / "probes.json"
OUT = ROOT / "docs" / "evals" / "reference_knowledge_baseline.md"
ROW_TIMEOUT_SECONDS = 20


class RowTimeout(RuntimeError):
    pass


def _raise_timeout(_signum: int, _frame: object) -> None:
    raise RowTimeout("row_timeout")


def _dig(payload: dict[str, Any], *keys: str) -> Any:
    cur: Any = payload
    for key in keys:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(key)
    return cur


def _route_row(probe: dict[str, Any]) -> dict[str, Any]:
    old_handler = signal.signal(signal.SIGALRM, _raise_timeout)
    signal.alarm(ROW_TIMEOUT_SECONDS)
    try:
        response = build_live_chat_response(ChatRequest(message=str(probe["query"])))
    except RowTimeout:
        return {
            "id": probe["id"],
            "kind": probe["kind"],
            "query": probe["query"],
            "selected_skill": None,
            "answer_mode": None,
            "request_mode": None,
            "stage_schedule": [],
            "primary_shape": None,
            "human_review_type": None,
            "has_mitre_panel": False,
            "has_reference_panel": False,
            "error": f"row_timeout:{ROW_TIMEOUT_SECONDS}s",
        }
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old_handler)
    payload = response.model_dump(mode="json")
    trace = payload.get("control_plane_trace") if isinstance(payload.get("control_plane_trace"), dict) else {}
    pipeline_dispatch = trace.get("pipeline_dispatch") if isinstance(trace.get("pipeline_dispatch"), dict) else {}
    dispatch_decision = pipeline_dispatch.get("decision") if isinstance(pipeline_dispatch.get("decision"), dict) else {}
    answer_shape = trace.get("answer_shape") if isinstance(trace.get("answer_shape"), dict) else {}
    analyst_response = payload.get("analyst_response") if isinstance(payload.get("analyst_response"), dict) else {}
    structured_context = payload.get("structured_context") if isinstance(payload.get("structured_context"), dict) else {}
    deterministic_shape = classify_answer_shape(str(probe["query"])).primary_shape
    return {
        "id": probe["id"],
        "kind": probe["kind"],
        "query": probe["query"],
        "selected_skill": payload.get("selected_skill"),
        "answer_mode": payload.get("answer_mode"),
        "request_mode": dispatch_decision.get("request_mode"),
        "stage_schedule": dispatch_decision.get("stage_schedule") or [],
        "primary_shape": answer_shape.get("primary_shape") or _dig(payload, "routing_skill_resolution", "answer_shape", "primary_shape") or deterministic_shape,
        "human_review_type": _dig(payload, "human_review", "review_type"),
        "has_mitre_panel": bool(payload.get("mitre_mappings") or analyst_response.get("mitre")),
        "has_reference_panel": bool(
            analyst_response.get("reference_facts") or structured_context.get("reference_facts")
        ),
    }


def _render(rows: list[dict[str, Any]]) -> str:
    now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        "# Reference Knowledge Probe Baseline",
        "",
        f"Generated: {now}",
        "",
        "Current baseline for the reference-knowledge probe contract. P1-P4 should route through `reference_taxonomy` / `reference_knowledge`; P5/P6/N1-N4 are frozen non-regression rows.",
        "",
        "| ID | Kind | Selected skill | Answer mode | Request mode | Shape | Human review | Stages |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for row in rows:
        stages = ",".join(str(item) for item in row.get("stage_schedule") or [])
        lines.append(
            "| {id} | {kind} | {selected_skill} | {answer_mode} | {request_mode} | {primary_shape} | {human_review_type} | {stages} |".format(
                stages=stages,
                **{key: row.get(key) or "" for key in ("id", "kind", "selected_skill", "answer_mode", "request_mode", "primary_shape", "human_review_type")},
            )
        )
    lines.extend(
        [
            "",
            "## Frozen Non-Regression Contract",
            "",
            "- P5/P6/N1-N4 current routes are the non-regression baseline for item 18.",
            "- N3 intentionally duplicates the alert-mapping guard class covered by P5.",
            "- This file is updated deliberately when P1/P2 flip red to green; the probe script should not be used for silent baseline drift.",
            "",
            "```json",
            json.dumps(rows, indent=2, sort_keys=True),
            "```",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    probes = json.loads(PROBES.read_text(encoding="utf-8"))
    rows = [_route_row(probe) for probe in probes]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(_render(rows), encoding="utf-8")
    print(json.dumps({"probe_count": len(rows), "baseline": str(OUT)}, sort_keys=True))


if __name__ == "__main__":
    main()
