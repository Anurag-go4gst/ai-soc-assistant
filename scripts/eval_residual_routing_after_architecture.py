#!/usr/bin/env python3
"""Plan 5 D0 — re-measure the Plan 4 residual routing set, layer by layer.

Measurement only. No routing rule is added, no skill contract is widened, no
frozen baseline is refreshed.

B6 proved the frozen truth-set arms observe only layers 1–2, so "unchanged in
`--arm both`" is not evidence that the architecture changed nothing. This probe
reports every layer for every residual row:

  L1  select_route_from_understanding      (frozen deterministic arm)
  L2  route_skill                          (frozen live arm)
  L3  ResolvedQueryContract                (Plan 5 B1/B3 — the new understanding)
  L4  adjudicate_route                     (Plan 5 B5 seam)
  L5  full `/chat` pipeline                (final committed route + product surface)

Classification is against the frozen Plan 4 baseline
(`docs/evals/routing_truth_set_baseline_v1.json`), per row:

  resolved_by_architecture  route_wrong -> route_ok, or capability_inconsistent cleared
  unchanged                 same verdicts
  regressed                 route_ok -> route_wrong, or capability_inconsistent gained

Usage:
  PYTHONPATH=backend:. python3 scripts/eval_residual_routing_after_architecture.py
  PYTHONPATH=backend:. python3 scripts/eval_residual_routing_after_architecture.py --no-pipeline
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
for _path in (REPO_ROOT / "backend", REPO_ROOT):
    _text = str(_path)
    if _text not in sys.path:
        sys.path.insert(0, _text)

TRUTH_SET = REPO_ROOT / "docs" / "evals" / "routing_truth_set_v1.json"
BASELINE = REPO_ROOT / "docs" / "evals" / "routing_truth_set_baseline_v1.json"
OUT_JSON = REPO_ROOT / "docs" / "evals" / "plan5" / "residual_routing_after_architecture.json"
OUT_MD = REPO_ROOT / "docs" / "evals" / "plan5" / "residual_routing_after_architecture_generated.md"

D2_ROWS = ("rt.d2.003", "rt.d2.010", "rt.d2.017")
OWNERSHIP_MARKERS = ("asset_identity_context", "data_source_health")


def _rows() -> list[dict[str, Any]]:
    return list(json.loads(TRUTH_SET.read_text(encoding="utf-8"))["rows"])


def _baseline() -> dict[str, dict[str, Any]]:
    payload = json.loads(BASELINE.read_text(encoding="utf-8"))
    rows = payload["rows"]
    if isinstance(rows, dict):
        return {str(key): value for key, value in rows.items()}
    return {str(row["row_id"]): row for row in rows}


def _is_paraphrase(row: dict[str, Any]) -> bool:
    return "paraphrase" in (row.get("quotas") or []) or str(row.get("source") or "").startswith(
        "paraphrase_of:"
    )


def _is_ownership(row: dict[str, Any]) -> bool:
    blob = " ".join(
        [
            str(row.get("rationale") or ""),
            str(row.get("ownership_decision") or ""),
            " ".join(str(q) for q in (row.get("quotas") or [])),
        ]
    )
    return any(marker in blob for marker in OWNERSHIP_MARKERS)


def _residual_class(row: dict[str, Any]) -> str | None:
    row_id = str(row["row_id"])
    if row_id in D2_ROWS:
        return "d2_defect"
    if _is_ownership(row):
        return "ownership_deferred"
    if _is_paraphrase(row):
        return "paraphrase"
    return None


def _capability_consistency(skill: str | None, required: list[str]) -> tuple[bool, list[str]]:
    from app.evals.routing_truth_set import capability_consistency

    consistent, denied = capability_consistency(
        selected_skill=skill, required_capabilities=required
    )
    return consistent, sorted(denied)


def _measure_layers(row: dict[str, Any]) -> dict[str, Any]:
    from app.chat.evidence_planner import plan_evidence
    from app.chat.intent_classifier import build_query_to_intent
    from app.chat.resolved_query_builder import build_resolved_query_contract
    from app.query_understanding.parser import understand_query
    from app.routing.route_adjudication import adjudicate_route
    from app.routing.select_route_from_understanding import select_route_from_understanding
    from app.routing.skill_router import route_skill

    query = str(row["query"])
    understanding = understand_query(query)

    base, provenance = select_route_from_understanding(understanding, query)
    l1_skill = base.get("skill")

    live = route_skill(query)
    l2_skill = live.get("skill")

    q2i = build_query_to_intent(query=query, query_understanding=understanding)
    match_path = str(understanding.deterministic_match_path or "unknown")
    contract = build_resolved_query_contract(
        query=query,
        query_understanding=understanding,
        qualification_tier="T4" if match_path == "out_of_registry" else "T1",
        qualification_source=match_path,
        query_to_intent=q2i,
    )

    evidence = plan_evidence(
        q2i.intent_classification.model_dump(),
        query_to_intent=q2i.model_dump(),
        query_understanding=understanding,
        routed=base,
    )
    adjudication = adjudicate_route(
        deterministic_route=str(l1_skill or "knowledge_recall"),
        route_plan_shadow={},
        evidence_plan=evidence.model_dump(),
        intent_classification=q2i.intent_classification.model_dump(),
        query_understanding=understanding,
        message=query,
        query_to_intent=q2i.model_dump(),
        resolved_query_contract=contract,
    )

    return {
        "l1_select_route": l1_skill,
        "l1_authority": provenance.get("authority_source"),
        "l1_match_path": match_path,
        "l2_route_skill": l2_skill,
        "l2_selected_by": live.get("selected_by"),
        "l3_contract": {
            "intent_family": contract.intent_family,
            "answer_goal": contract.answer_goal,
            "ambiguity_state": contract.ambiguity_state,
            "clarification_required": contract.clarification_required,
            "required_capabilities": sorted(contract.required_capabilities),
            "prohibited_capabilities": sorted(contract.prohibited_capabilities),
            "evidence_requirements": list(contract.evidence_requirements),
            "qualification_tier": contract.qualification_tier,
            "qualification_source": contract.qualification_source,
            "confidence": contract.confidence,
            "understanding_source": contract.understanding_source,
            "entity_keys": sorted(contract.entities),
            "time_scope": contract.time_scope,
        },
        "l4_adjudicated": adjudication.final_route,
        "l4_authority": adjudication.authority_source,
    }


def _measure_pipeline(row: dict[str, Any]) -> dict[str, Any]:
    """Layer 5: the committed route and the analyst-visible product surface."""
    from app.chat.pipeline import build_live_chat_response
    from app.schemas.requests import ChatRequest

    try:
        response = build_live_chat_response(ChatRequest(message=str(row["query"])))
    except Exception as exc:  # noqa: BLE001 - a failing row is data, not a crash
        return {"l5_error": f"{type(exc).__name__}: {exc}"}

    payload = response.model_dump() if hasattr(response, "model_dump") else dict(response)
    routed = payload.get("routed") if isinstance(payload.get("routed"), dict) else {}
    execution = payload.get("execution") if isinstance(payload.get("execution"), dict) else {}
    review = payload.get("human_review") if isinstance(payload.get("human_review"), dict) else {}
    validation = (
        payload.get("spl_validation") if isinstance(payload.get("spl_validation"), dict) else {}
    )
    candidate = (
        payload.get("candidate_spl") if isinstance(payload.get("candidate_spl"), dict) else {}
    )
    return {
        "l5_skill": routed.get("skill") or payload.get("selected_skill"),
        "l5_execution_status": execution.get("status"),
        "l5_execution_eligible": execution.get("execution_eligible"),
        "l5_human_review_required": bool(review.get("required")),
        "l5_human_review_type": review.get("review_type"),
        "l5_has_candidate_spl": bool(candidate.get("spl") or candidate.get("candidate_spl")),
        "l5_spl_approved": validation.get("approved"),
    }


def _classify(row: dict[str, Any], before: dict[str, Any], skill: str | None) -> dict[str, Any]:
    acceptable = set(row["acceptable_skills"])
    after_ok = skill in acceptable
    before_ok = before.get("route_verdict") == "route_ok"

    consistent, denied = _capability_consistency(skill, list(row["required_capabilities"]))
    after_inconsistent = not consistent
    before_inconsistent = bool(before.get("capability_inconsistent"))

    if (after_ok and not before_ok) or (before_inconsistent and not after_inconsistent):
        verdict = "resolved_by_architecture"
    elif (before_ok and not after_ok) or (after_inconsistent and not before_inconsistent):
        verdict = "regressed"
    else:
        verdict = "unchanged"

    return {
        "verdict": verdict,
        "before_route_verdict": before.get("route_verdict"),
        "before_selected_skill": before.get("selected_skill"),
        "before_capability_inconsistent": before_inconsistent,
        "after_route_ok": after_ok,
        "after_capability_inconsistent": after_inconsistent,
        "after_denied_capabilities": denied,
    }


def run(*, with_pipeline: bool) -> dict[str, Any]:
    baseline = _baseline()
    results: list[dict[str, Any]] = []

    for row in _rows():
        residual = _residual_class(row)
        if residual is None:
            continue
        row_id = str(row["row_id"])
        layers = _measure_layers(row)
        record: dict[str, Any] = {
            "row_id": row_id,
            "residual_class": residual,
            "query": row["query"],
            "acceptable_skills": sorted(row["acceptable_skills"]),
            "required_capabilities": sorted(row["required_capabilities"]),
            **layers,
        }
        if with_pipeline:
            record.update(_measure_pipeline(row))

        # The frozen arms gate on L1; the product is judged on the committed route.
        record["classification_l1"] = _classify(row, baseline.get(row_id, {}), layers["l1_select_route"])
        record["classification_l4"] = _classify(row, baseline.get(row_id, {}), layers["l4_adjudicated"])
        if with_pipeline and record.get("l5_skill"):
            record["classification_l5"] = _classify(row, baseline.get(row_id, {}), record["l5_skill"])
        results.append(record)

    def _tally(key: str) -> dict[str, int]:
        counts: dict[str, int] = {}
        for record in results:
            verdict = (record.get(key) or {}).get("verdict")
            if verdict:
                counts[verdict] = counts.get(verdict, 0) + 1
        return counts

    return {
        "schema_version": "plan5_d0_residual_routing_v1",
        "row_count": len(results),
        "classes": {
            name: sum(1 for r in results if r["residual_class"] == name)
            for name in ("d2_defect", "ownership_deferred", "paraphrase")
        },
        "tally_l1_select_route": _tally("classification_l1"),
        "tally_l4_adjudicated": _tally("classification_l4"),
        "tally_l5_pipeline": _tally("classification_l5"),
        "rows": results,
    }


def _md(payload: dict[str, Any]) -> str:
    lines = [
        "# Plan 5 D0 — residual routing after the architecture",
        "",
        "Measurement only. No routing rule added, no skill contract widened, no frozen baseline refreshed.",
        "",
        f"Rows: **{payload['row_count']}** "
        f"(d2 {payload['classes']['d2_defect']} · ownership {payload['classes']['ownership_deferred']} "
        f"· paraphrase {payload['classes']['paraphrase']}).",
        "",
        "| Layer | resolved | unchanged | regressed |",
        "|---|---|---|---|",
    ]
    for label, key in (
        ("L1 `select_route_from_understanding`", "tally_l1_select_route"),
        ("L4 `adjudicate_route`", "tally_l4_adjudicated"),
        ("L5 full `/chat`", "tally_l5_pipeline"),
    ):
        tally = payload[key]
        lines.append(
            f"| {label} | {tally.get('resolved_by_architecture', 0)} | "
            f"{tally.get('unchanged', 0)} | {tally.get('regressed', 0)} |"
        )

    lines += ["", "## Rows", ""]
    lines.append(
        "| row | class | L1 | L2 | L4 | L5 | contract family / goal / caps | verdict (L4) |"
    )
    lines.append("|---|---|---|---|---|---|---|---|")
    for row in payload["rows"]:
        contract = row["l3_contract"]
        caps = ",".join(contract["required_capabilities"]) or "-"
        lines.append(
            f"| `{row['row_id']}` | {row['residual_class']} | {row['l1_select_route']} | "
            f"{row['l2_route_skill']} | {row['l4_adjudicated']} | {row.get('l5_skill', 'n/a')} | "
            f"{contract['intent_family']} / {contract['answer_goal']} / {caps} | "
            f"{row['classification_l4']['verdict']} |"
        )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-pipeline", action="store_true", help="skip the layer-5 /chat arm")
    parser.add_argument("--json", default=str(OUT_JSON))
    parser.add_argument("--md", default=str(OUT_MD))
    args = parser.parse_args()

    payload = run(with_pipeline=not args.no_pipeline)
    Path(args.json).parent.mkdir(parents=True, exist_ok=True)
    Path(args.json).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    Path(args.md).write_text(_md(payload), encoding="utf-8")

    for key in ("tally_l1_select_route", "tally_l4_adjudicated", "tally_l5_pipeline"):
        print(f"{key}: {payload[key]}")
    print(f"rows={payload['row_count']} json={args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
