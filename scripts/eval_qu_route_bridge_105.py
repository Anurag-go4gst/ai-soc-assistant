#!/usr/bin/env python3
"""Compare keyword-only vs QU-first routing across 105 registry questions."""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
for _path in (_REPO / "backend", _REPO):
    _text = str(_path)
    if _text not in sys.path:
        sys.path.insert(0, _text)

from app.coverage.question_runtime_map import list_question_runtime_entries  # noqa: E402
from app.query_understanding.parser import understand_query  # noqa: E402
from app.routing.deterministic_router import route_skill_deterministic  # noqa: E402
from app.routing.skill_router import route_skill  # noqa: E402


def _is_needs_clarification(routed: dict) -> bool:
    plan = routed.get("tool_plan") or []
    return "needs_clarification" in plan


def main() -> int:
    import app.config as config_module

    settings = config_module.settings
    saved_mode = settings.routing_mode
    saved_shadow = settings.routing_llm_shadow_enabled
    saved_telemetry_sink = settings.ai_soc_telemetry_sink
    try:
        settings.routing_mode = "deterministic_only"
        settings.routing_llm_shadow_enabled = False
        settings.ai_soc_telemetry_sink = "none"

        keyword_clarify = 0
        qu_clarify = 0
        skill_changes = 0
        spot_checks: list[dict] = []

        for entry in list_question_runtime_entries():
            text = str(entry.get("question") or "")
            ref = str(entry.get("question_ref") or "")
            if not text:
                continue

            keyword = route_skill_deterministic(text)
            understanding = understand_query(text)
            qu_route = route_skill(text, query_understanding=understanding)

            if _is_needs_clarification(keyword):
                keyword_clarify += 1
            if _is_needs_clarification(qu_route):
                qu_clarify += 1
            if keyword.get("skill") != qu_route.get("skill"):
                skill_changes += 1

            if ref in {"q0.q001", "q0.q046", "q0.q028", "q0.q033"}:
                spot_checks.append(
                    {
                        "question_ref": ref,
                        "match_path": understanding.deterministic_match_path,
                        "keyword_skill": keyword.get("skill"),
                        "qu_skill": qu_route.get("skill"),
                        "selected_by": qu_route.get("selected_by"),
                        "authority_source": (qu_route.get("routing_provenance") or {}).get("authority_source"),
                        "llm_adjudication": qu_route.get("llm_adjudication"),
                        "tool_plan": qu_route.get("tool_plan"),
                    }
                )

        by_authority = Counter(
            str((route_skill(str(e.get("question") or ""), query_understanding=understand_query(str(e.get("question") or ""))).get("routing_provenance") or {}).get("authority_source"))
            for e in list_question_runtime_entries()
            if e.get("question")
        )

        out = {
            "question_count": len(list_question_runtime_entries()),
            "keyword_router_needs_clarification": keyword_clarify,
            "qu_first_needs_clarification": qu_clarify,
            "clarification_delta": keyword_clarify - qu_clarify,
            "skill_divergence_count": skill_changes,
            "authority_source_counts": dict(by_authority),
            "spot_checks": spot_checks,
            "routing_mode": "deterministic_only",
        }

        out_dir = _REPO / "docs" / "evals" / "out"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / "qu_route_bridge_105_routing.json"
        out_path.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")

        print(json.dumps(out, indent=2))
        print(f"\nWrote {out_path}")
        return 0
    finally:
        settings.routing_mode = saved_mode
        settings.routing_llm_shadow_enabled = saved_shadow
        settings.ai_soc_telemetry_sink = saved_telemetry_sink


if __name__ == "__main__":
    raise SystemExit(main())
