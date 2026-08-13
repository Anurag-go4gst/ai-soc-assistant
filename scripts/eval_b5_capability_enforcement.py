#!/usr/bin/env python3
"""Plan 5 B5 — OFF/ON capability-enforcement measurement (observation only).

Measures the adjudication-layer delta from `ai_soc_live_capability_enforcement_enabled`.
The frozen truth-set evaluator calls `select_route_from_understanding` / `route_skill`
and does **not** pass through `adjudicate_route`, so `--arm both` can be unchanged
even when this script reports route vetoes.

Does not patch routing, widen skill contracts, or refresh protected baselines.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
for _path in (REPO_ROOT / "backend", REPO_ROOT):
    text = str(_path)
    if text not in sys.path:
        sys.path.insert(0, text)

DEFAULT_TRUTH_SET = REPO_ROOT / "docs" / "evals" / "routing_truth_set_v1.json"
DEFAULT_JSON = REPO_ROOT / "docs" / "evals" / "plan5" / "b5_capability_enforcement_delta.json"
DEFAULT_MD = REPO_ROOT / "docs" / "evals" / "plan5" / "b5_capability_enforcement_off_on.md"

RESIDUAL_D2 = ("rt.d2.003", "rt.d2.010", "rt.d2.017")
OWNERSHIP_MARKERS = ("asset_identity_context", "data_source_health")


def _load_rows(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return list(payload["rows"])


def _is_paraphrase(row: dict[str, Any]) -> bool:
    quotas = row.get("quotas") or []
    source = str(row.get("source") or "")
    return "paraphrase" in quotas or source.startswith("paraphrase_of:")


def _granted(skill: str | None) -> frozenset[str]:
    from app.chat.skill_intent_compatibility import _contract_grants, skill_contract_for

    contract = skill_contract_for(skill)
    return frozenset(cap for cap in ("spl", "mcp") if _contract_grants(contract, cap))


def _label_exec_caps(row: dict[str, Any]) -> frozenset[str]:
    return frozenset(row.get("required_capabilities") or []) & {"spl", "mcp"}


def _is_ownership_deferred(row: dict[str, Any]) -> bool:
    blob = " ".join(
        [
            str(row.get("rationale") or ""),
            str(row.get("ownership_decision") or ""),
            " ".join(str(q) for q in (row.get("quotas") or [])),
        ]
    )
    return any(marker in blob for marker in OWNERSHIP_MARKERS)


def _surface(state: dict[str, Any]) -> dict[str, Any]:
    routed = state.get("routed") if isinstance(state.get("routed"), dict) else {}
    adj = state.get("route_adjudication") if isinstance(state.get("route_adjudication"), dict) else {}
    contract = state.get("resolved_query_contract") if isinstance(state.get("resolved_query_contract"), dict) else {}
    evidence = state.get("evidence_plan") if isinstance(state.get("evidence_plan"), dict) else {}
    human = state.get("human_review") if isinstance(state.get("human_review"), dict) else {}
    execution = state.get("execution") if isinstance(state.get("execution"), dict) else {}
    spl_val = state.get("spl_validation") if isinstance(state.get("spl_validation"), dict) else {}
    candidate = state.get("candidate_spl") if isinstance(state.get("candidate_spl"), dict) else {}
    run_contract = state.get("run_contract") if isinstance(state.get("run_contract"), dict) else {}
    return {
        "selected_skill": routed.get("skill") or adj.get("final_route"),
        "adjudicated_route": adj.get("final_route"),
        "authority_source": adj.get("authority_source"),
        "capability_enforcement": adj.get("capability_enforcement"),
        "capability_denied": list(adj.get("capability_denied") or []),
        "intent_family": contract.get("intent_family"),
        "required_capabilities": sorted(contract.get("required_capabilities") or []),
        "clarification_required": bool(contract.get("clarification_required")),
        "answer_mode": evidence.get("answer_mode"),
        "needs_spl": bool(evidence.get("needs_spl")),
        "hil_required": bool(human.get("required")),
        "hil_review_type": human.get("review_type") or human.get("type"),
        "execution_status": execution.get("status"),
        "execution_eligible": execution.get("execution_eligible"),
        "spl_approved": spl_val.get("approved"),
        "has_candidate_spl": bool(candidate),
        "run_contract_skill": run_contract.get("canonical_skill") or run_contract.get("selected_skill"),
    }


def _adjudicate_row(row: dict[str, Any], *, enabled: bool) -> dict[str, Any]:
    from app.chat.evidence_planner import plan_evidence
    from app.chat.intent_classifier import build_query_to_intent
    from app.chat.resolved_query_builder import build_resolved_query_contract
    from app.config import settings
    from app.query_understanding.parser import understand_query
    from app.routing.route_adjudication import adjudicate_route
    from app.routing.select_route_from_understanding import select_route_from_understanding

    settings.ai_soc_live_capability_enforcement_enabled = enabled
    query = str(row["query"])
    understanding = understand_query(query)
    base, provenance = select_route_from_understanding(understanding, query)
    det_skill = str(base.get("skill") or "knowledge_recall")
    q2i = build_query_to_intent(query=query, query_understanding=understanding)
    contract = build_resolved_query_contract(
        query=query,
        query_understanding=understanding,
        qualification_tier="T4" if understanding.deterministic_match_path == "out_of_registry" else "T1",
        qualification_source=str(understanding.deterministic_match_path or "unknown"),
        query_to_intent=q2i,
    )
    evidence = plan_evidence(
        q2i.intent_classification.model_dump(),
        query_to_intent=q2i.model_dump(),
        query_understanding=understanding,
        routed=base,
    )
    adjudication = adjudicate_route(
        deterministic_route=det_skill,
        route_plan_shadow={},
        evidence_plan=evidence.model_dump(),
        intent_classification=q2i.intent_classification.model_dump(),
        query_understanding=understanding,
        message=query,
        query_to_intent=q2i.model_dump(),
        resolved_query_contract=contract,
    )
    return {
        "truth_set_skill": det_skill,
        "truth_set_authority": provenance.get("authority_source"),
        "match_path": understanding.deterministic_match_path,
        "intent_family": contract.intent_family,
        "required_capabilities": sorted(contract.required_capabilities),
        "prohibited_capabilities": sorted(contract.prohibited_capabilities),
        "clarification_required": contract.clarification_required,
        "final_route": adjudication.final_route,
        "authority_source": adjudication.authority_source,
        "capability_enforcement": adjudication.capability_enforcement,
        "capability_denied": list(adjudication.capability_denied or []),
        "reason": adjudication.reason,
    }


def _rp_row(query: str, *, enabled: bool) -> dict[str, Any]:
    from app.chat import pipeline as chat_pipeline
    from app.config import settings
    from app.graph.resource_planner_graph import run_resource_planner_graph
    from app.schemas.requests import ChatRequest

    previous = {
        "enforcement": settings.ai_soc_live_capability_enforcement_enabled,
        "soc_kb": settings.soc_kb_retrieval_enabled,
        "mcp_global": settings.mcp_global_execution_enabled,
        "mcp_mock": settings.mcp_server_mock_execution_enabled,
        "retrieve": chat_pipeline.retrieve_soc_kb,
    }
    settings.ai_soc_live_capability_enforcement_enabled = enabled
    settings.soc_kb_retrieval_enabled = True
    settings.mcp_global_execution_enabled = False
    settings.mcp_server_mock_execution_enabled = False
    chat_pipeline.retrieve_soc_kb = lambda **kwargs: {
        "retrieval_status": "collected",
        "chunks": [],
        "required_sources": kwargs.get("required_sources") or [],
    }
    try:
        state = run_resource_planner_graph(ChatRequest(message=query))
    except Exception as exc:  # noqa: BLE001 — measurement must not crash the table
        return {"error": f"{type(exc).__name__}: {exc}"}
    finally:
        settings.ai_soc_live_capability_enforcement_enabled = previous["enforcement"]
        settings.soc_kb_retrieval_enabled = previous["soc_kb"]
        settings.mcp_global_execution_enabled = previous["mcp_global"]
        settings.mcp_server_mock_execution_enabled = previous["mcp_mock"]
        chat_pipeline.retrieve_soc_kb = previous["retrieve"]
    return _surface(dict(state))


def _render_md(payload: dict[str, Any]) -> str:
    rows = payload["rows"]
    changed = [r for r in rows if r["route_changed"]]
    unsatisfied = [r for r in rows if r["on"]["capability_enforcement"] == "unsatisfied"]
    vetoed = [r for r in rows if r["on"]["capability_enforcement"] == "veto"]
    lines = [
        "# Plan 5 B5 — capability enforcement OFF→ON measurement",
        "",
        "Observation only. Flag remains **default OFF**. No skill-contract widening.",
        "No protected/frozen baseline refresh.",
        "",
        "## Summary",
        "",
        f"- Truth-set rows measured: **{len(rows)}**",
        f"- Adjudication route changed OFF→ON: **{len(changed)}**",
        f"- ON veto (demote to `knowledge_recall`): **{len(vetoed)}**",
        f"- ON unsatisfied (already `knowledge_recall`, required cap denied): **{len(unsatisfied)}**",
        f"- Label required-cap denied by truth-set skill: **{sum(1 for r in rows if r.get('label_denied_by_truth_set_skill'))}**",
        f"- Label required-cap denied by adjudicated skill: **{sum(1 for r in rows if r.get('label_denied_by_adjudicated_skill'))}**",
        f"- Truth-set evaluator note: `{payload['evaluator_caveat']}`",
        "",
        "RP graph on this measurement host short-circuits when canonical planning",
        "persistence fails (`handoff_load_failed` / DNS). `route_adjudication` is then",
        "absent, so live enforcement is **unreachable** on that degrade path. The",
        "adjudication-layer table above is the authoritative OFF→ON instrument.",
        "",
        "## Route-change rows",
        "",
    ]
    if not changed:
        lines.append("_None. Enforcement did not change any adjudicated skill._")
        lines.append("")
    else:
        lines.extend(
            [
                "| row_id | OFF route | ON route | required | denied | enforcement |",
                "|---|---|---|---|---|---|",
            ]
        )
        for row in changed:
            lines.append(
                "| {row_id} | {off} | {on} | {req} | {denied} | {status} |".format(
                    row_id=row["row_id"],
                    off=row["off"]["final_route"],
                    on=row["on"]["final_route"],
                    req=",".join(row["on"]["required_capabilities"]) or "—",
                    denied=",".join(row["on"]["capability_denied"]) or "—",
                    status=row["on"]["capability_enforcement"],
                )
            )
        lines.append("")

    lines.extend(["## Residual observations (named)", ""])
    for row in rows:
        if not row["residual"]:
            continue
        lines.append(f"### {row['row_id']} ({', '.join(row['residual_tags'])})")
        lines.append("")
        lines.append(f"- Query: `{row['query']}`")
        lines.append(f"- Label acceptable skills: `{row['acceptable_skills']}`")
        lines.append(f"- Label required capabilities: `{row['label_required_capabilities']}`")
        lines.append(
            f"- Label caps denied by truth-set skill: `{row['label_denied_by_truth_set_skill']}`"
        )
        lines.append(
            f"- Label caps denied by adjudicated skill: `{row['label_denied_by_adjudicated_skill']}`"
        )
        lines.append(f"- Truth-set skill (evaluator arm): `{row['off']['truth_set_skill']}`")
        lines.append(
            f"- OFF adjudicated: `{row['off']['final_route']}` "
            f"({row['off']['authority_source']}, family `{row['off']['intent_family']}`)"
        )
        lines.append(
            f"- ON adjudicated: `{row['on']['final_route']}` "
            f"enforcement=`{row['on']['capability_enforcement']}` "
            f"denied=`{row['on']['capability_denied']}`"
        )
        lines.append(f"- Route changed: **{row['route_changed']}**")
        if row.get("rp_off") or row.get("rp_on"):
            lines.append(f"- RP OFF: `{json.dumps(row.get('rp_off'), sort_keys=True)}`")
            lines.append(f"- RP ON: `{json.dumps(row.get('rp_on'), sort_keys=True)}`")
        lines.append("")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--truth-set", type=Path, default=DEFAULT_TRUTH_SET)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--md-out", type=Path, default=DEFAULT_MD)
    parser.add_argument(
        "--rp",
        action="store_true",
        help="Run resource-planner graph for residual and route-change rows.",
    )
    parser.add_argument("--rp-all", action="store_true", help="Run RP for every truth-set row.")
    args = parser.parse_args()

    from app.config import settings

    original = settings.ai_soc_live_capability_enforcement_enabled
    rows_out: list[dict[str, Any]] = []
    try:
        for row in _load_rows(args.truth_set):
            residual_tags: list[str] = []
            if row["row_id"] in RESIDUAL_D2:
                residual_tags.append("d2_defect")
            if _is_paraphrase(row):
                residual_tags.append("paraphrase")
            if _is_ownership_deferred(row):
                residual_tags.append("ownership_deferred")
            off = _adjudicate_row(row, enabled=False)
            on = _adjudicate_row(row, enabled=True)
            label_required = _label_exec_caps(row)
            record = {
                "row_id": row["row_id"],
                "query": row["query"],
                "quotas": list(row.get("quotas") or []),
                "acceptable_skills": list(row.get("acceptable_skills") or []),
                "label_required_capabilities": sorted(label_required),
                "label_denied_by_truth_set_skill": sorted(
                    label_required - _granted(off["truth_set_skill"])
                ),
                "label_denied_by_adjudicated_skill": sorted(
                    label_required - _granted(off["final_route"])
                ),
                "ambiguous": bool(row.get("ambiguous")),
                "residual": bool(residual_tags),
                "residual_tags": residual_tags,
                "off": off,
                "on": on,
                "route_changed": off["final_route"] != on["final_route"],
                "enforcement_status_changed": off.get("capability_enforcement")
                != on.get("capability_enforcement"),
            }
            rows_out.append(record)

        need_rp = {
            r["row_id"]
            for r in rows_out
            if args.rp_all or ((args.rp or args.rp_all) and (r["residual"] or r["route_changed"]))
        }
        if args.rp or args.rp_all:
            by_id = {r["row_id"]: r for r in rows_out}
            for row in _load_rows(args.truth_set):
                if row["row_id"] not in need_rp:
                    continue
                by_id[row["row_id"]]["rp_off"] = _rp_row(str(row["query"]), enabled=False)
                by_id[row["row_id"]]["rp_on"] = _rp_row(str(row["query"]), enabled=True)
    finally:
        settings.ai_soc_live_capability_enforcement_enabled = original

    payload = {
        "schema_version": "plan5-b5-capability-enforcement-v1",
        "flag": "ai_soc_live_capability_enforcement_enabled",
        "default": False,
        "evaluator_caveat": (
            "scripts/eval_routing_truth_set.py does not call adjudicate_route; "
            "deterministic arm uses select_route_from_understanding and live arm uses "
            "route_skill. Adjudication-layer deltas in this file can be invisible to --check."
        ),
        "summary": {
            "rows": len(rows_out),
            "route_changed": sum(1 for r in rows_out if r["route_changed"]),
            "veto": sum(1 for r in rows_out if r["on"]["capability_enforcement"] == "veto"),
            "unsatisfied": sum(
                1 for r in rows_out if r["on"]["capability_enforcement"] == "unsatisfied"
            ),
            "compatible": sum(
                1 for r in rows_out if r["on"]["capability_enforcement"] == "compatible"
            ),
        },
        "rows": rows_out,
    }
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    args.md_out.write_text(_render_md(payload), encoding="utf-8")
    print(json.dumps({"json": str(args.json_out), "md": str(args.md_out), **payload["summary"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
