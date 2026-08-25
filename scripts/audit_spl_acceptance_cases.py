#!/usr/bin/env python3
"""Local acceptance audit for SPL semantic intent + run shape (Cases 1-5)."""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, "/workspace/backend")
sys.path.insert(0, "/workspace")

from app.graph.resource_planner_graph import run_chat_via_resource_planner_graph
from app.schemas.requests import ChatRequest
from app.spl.spl_intent_spec import build_spl_intent_spec
from app.spl.spl_semantic_fidelity import validate_semantic_fidelity


CASES = {
    "case1": "give me a spl command to get all the firewall logs for last 30 days",
    "case2": (
        "Give me an SPL query to show the top source IPs generating denied firewall "
        "traffic in the last 24 hours."
    ),
    "case3": (
        "Give me only a review-only SPL query for index=pgcil_soc and "
        "sourcetype=cisco:firepower for the last 30 days. Do not execute it."
    ),
    "case4": "Investigate firewall deny spike",
    "case5": "give me a spl command to get all the firewall logs for last 30 days",
}


def _run_case(name: str, message: str, *, llm_disabled: bool = False) -> dict:
    if llm_disabled:
        os.environ["AI_SOC_LLM_ENABLED"] = "false"
        os.environ["AI_SOC_LLM_MODE"] = "disabled"
    else:
        os.environ.setdefault("AI_SOC_LLM_ENABLED", "true")
    req = ChatRequest(message=message, session_id=f"audit-{name}")
    response = run_chat_via_resource_planner_graph(req)
    payload = response.model_dump() if response is not None else {}
    spec = build_spl_intent_spec(message)
    candidate = payload.get("candidate_spl") or {}
    spl_text = str(candidate.get("candidate_spl") or "")
    fidelity = validate_semantic_fidelity(spec, spl_text) if spl_text else {"passed": None, "losses": []}
    evidence_plan = payload.get("evidence_plan") or {}
    rqc = payload.get("resolved_query_contract") or {}
    return {
        "case": name,
        "query": message,
        "intent_spec": spec,
        "fidelity": fidelity,
        "answer_mode": payload.get("answer_mode"),
        "evidence_plan_answer_mode": evidence_plan.get("answer_mode"),
        "evidence_plan_reasons": evidence_plan.get("reasons"),
        "investigation_outcome": payload.get("investigation_outcome") is not None,
        "rqc_intent_family": rqc.get("intent_family"),
        "rqc_answer_goal": rqc.get("answer_goal"),
        "candidate_spl_len": len(spl_text),
        "candidate_spl_preview": spl_text[:400],
        "spl_authoring_unavailable": candidate.get("spl_authoring_unavailable"),
        "llm_fallback_status": candidate.get("llm_fallback_status"),
        "utility_trace": (candidate.get("utility_spl_draft_trace") or {}),
        "control_plane_keys": list((payload.get("control_plane_trace") or {}).keys()),
    }


def main() -> None:
    results = []
    for key in ("case1", "case2", "case3", "case4"):
        results.append(_run_case(key, CASES[key]))
    results.append(_run_case("case5", CASES["case5"], llm_disabled=True))
    print(json.dumps(results, indent=2, default=str))


if __name__ == "__main__":
    main()
