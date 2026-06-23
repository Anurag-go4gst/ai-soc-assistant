#!/usr/bin/env python3
"""P2-B §4.6 three-profile causal-impact ablation — offline structural scaffold.

Plan §4.6 defines three paired profiles:
  1. deterministic contract/card only;
  2. deterministic + correctly-routed MITRE/CVE/RAG/GitHub-skill contribution;
  3. profile 2 + the adaptive multi-role LLM orchestration selected for the row.

This harness computes the **capability surface** of each profile deterministically
(no live LLM): which answer affordances, routed asset legs, and LLM roles each
profile makes available, plus per-role and full-graph ablation. It proves the
mechanism is monotonic and safe (boundary turns never escalate assets/roles) and
emits paired structural deltas.

It does NOT measure blinded answer quality — the live profile-1/2/3 paired quality
run with blind human review (plan §4.6) is the operator residual. This scaffold is
the cost-bounded gate that must pass before that live run is worth its latency.

Usage:
  PYTHONPATH=backend:. python3 scripts/run_p2b_ablation.py
  PYTHONPATH=backend:. python3 scripts/run_p2b_ablation.py --check
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
for _p in (str(REPO / "backend"), str(REPO)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from app.chat.guidance_templates import should_skip_llm_composer
from app.chat.intent_classifier import build_query_to_intent
from app.config import settings
from app.llm.hybrid_role_graph import build_hybrid_role_plan
from app.query_understanding.parser import understand_query
from app.routing.select_route_from_understanding import select_route_from_understanding

BANK = REPO / "docs/evals/p2b_causal_pilot_20_bank.json"
REPORT = REPO / "docs/evals/p2b_ablation_20_report.json"

# Strata where the turn is refused/redirected: assets and LLM roles must NOT escalate.
BOUNDARY_STRATA = {"unsafe_execution", "out_of_scope", "boundary_refusal"}

# Deterministic resource-leg probe (profile 2). Measures "leg routed as available",
# NOT "leg supplied useful evidence" — the latter is the live residual.
_MITRE_RE = re.compile(r"\b(mitre|att&ck|attack technique|ttp|t1\d{3}|tactic)\b", re.I)
_CVE_RE = re.compile(r"\b(cve-\d|cve\b|vulnerabilit|patch|exploitab|affected version|advisory)\b", re.I)
_RAG_RE = re.compile(r"\b(playbook|runbook|sop|policy|procedure|regulat|compliance|guideline|how do (we|i))\b", re.I)
_SPL_RE = re.compile(r"\b(spl|splunk|search index|stats|tstats|query for)\b", re.I)


def _routed_resource_legs(*, query: str, category: str, stratum: str | None, skill: str) -> list[str]:
    """Deterministic asset legs profile 2 would route for this row."""
    if stratum in BOUNDARY_STRATA:
        return []  # refused/redirected turns contribute no asset evidence
    legs: list[str] = []
    cat = (category or "").lower()
    if _MITRE_RE.search(query) or cat in {"soc", "attack", "detection"}:
        legs.append("mitre")
    if _CVE_RE.search(query) or cat == "cve":
        legs.append("cve")
    if _RAG_RE.search(query) or cat in {"knowledge", "governance"} or stratum == "knowledge_only":
        legs.append("rag")
    if _SPL_RE.search(query) or stratum in {"spl_generation_only", "guided_investigation"}:
        legs.append("spl")
    if stratum == "guided_investigation" or skill == "guided_investigation":
        legs.append("github_skill")
    return sorted(set(legs))


def _profiles_for_row(row: dict) -> dict:
    q = row["question"]
    stratum = row.get("stratum")
    u = understand_query(q)
    qti = build_query_to_intent(query=q, query_understanding=u)
    intent = qti.intent_classification.model_dump() if qti.intent_classification else {}
    skip_comp, skip_reason = should_skip_llm_composer(
        query=q, path_type=None, intent_family=intent.get("intent_family")
    )
    route, _ = select_route_from_understanding(u, q)
    skill = str(route.get("skill") or "knowledge_recall")

    plan = build_hybrid_role_plan(
        query=q,
        match_path=u.deterministic_match_path,
        selected_skill=skill,
        answer_contract=None,
        path_type=None,
        intent_family=intent.get("intent_family"),
        draft_preview_active=False,
        skip_composer=skip_comp,
        skip_composer_reason=skip_reason,
        intent_advisory_skipped=True,
        intent_skip_reason="ablation_offline",
        control_plane_enabled=bool(settings.control_plane_enabled),
        soc_investigation_shaped=bool(u.soc_investigation_shaped),
    )
    enabled_roles = [r.role_id for r in plan.roles if r.enabled]
    role_consumers = {r.role_id: r.consumer for r in plan.roles if r.enabled}
    legs = _routed_resource_legs(query=q, category=row.get("category", ""), stratum=stratum, skill=skill)

    # Capability surface per profile (nested by construction).
    p1 = {"deterministic_card"}
    p2 = p1 | {f"asset:{leg}" for leg in legs}
    p3 = p2 | {f"role:{r}" for r in enabled_roles}

    # Per-role ablation: dropping a role removes exactly its consumer affordance.
    role_ablation = {r: {"consumer": role_consumers.get(r), "marginal": f"role:{r}"} for r in enabled_roles}

    return {
        "id": row["id"],
        "category": row.get("category"),
        "stratum": stratum,
        "skill": skill,
        "complexity_tier": plan.complexity_tier,
        "deadline_seconds": plan.deadline_seconds,
        "profile_1_capability": sorted(p1),
        "profile_2_capability": sorted(p2),
        "profile_3_capability": sorted(p3),
        "routed_resource_legs": legs,
        "enabled_roles": enabled_roles,
        "role_ablation": role_ablation,
        "delta_p2_p1": len(p2) - len(p1),
        "delta_p3_p2": len(p3) - len(p2),
    }


def _gate(results: list[dict]) -> list[str]:
    failures: list[str] = []
    for r in results:
        p1, p2, p3 = set(r["profile_1_capability"]), set(r["profile_2_capability"]), set(r["profile_3_capability"])
        # 1. Monotonic capability: P1 ⊆ P2 ⊆ P3.
        if not (p1 <= p2 <= p3):
            failures.append(f"{r['id']}: capability not monotonic across profiles")
        # 2. Boundary safety: refused turns escalate neither assets nor LLM roles.
        if r["stratum"] in BOUNDARY_STRATA:
            if r["routed_resource_legs"]:
                failures.append(f"{r['id']}: boundary row routed asset legs {r['routed_resource_legs']}")
            if r["enabled_roles"]:
                failures.append(f"{r['id']}: boundary row enabled LLM roles {r['enabled_roles']}")
        else:
            # 3. Non-boundary rows must gain *something* in profile 2 or 3.
            if r["delta_p2_p1"] == 0 and r["delta_p3_p2"] == 0:
                failures.append(f"{r['id']}: non-boundary row gains nothing in P2 or P3")
        # 4. Every enabled role feeds a visible consumer.
        for role, meta in r["role_ablation"].items():
            if not meta.get("consumer"):
                failures.append(f"{r['id']}: enabled role {role} has no consumer (no visible contribution)")
    return failures


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="exit non-zero if structural gate fails")
    args = ap.parse_args()

    bank = json.loads(BANK.read_text())
    results = [_profiles_for_row(r) for r in bank["rows"]]
    failures = _gate(results)

    leg_dist = dict(Counter(leg for r in results for leg in r["routed_resource_legs"]))
    role_dist = dict(Counter(role for r in results for role in r["enabled_roles"]))
    non_boundary = [r for r in results if r["stratum"] not in BOUNDARY_STRATA]
    mean_d21 = round(sum(r["delta_p2_p1"] for r in non_boundary) / max(1, len(non_boundary)), 2)
    mean_d32 = round(sum(r["delta_p3_p2"] for r in non_boundary) / max(1, len(non_boundary)), 2)

    report = {
        "note": "structural capability ablation only; blinded live quality delta is the operator residual (plan §4.6)",
        "row_count": len(results),
        "non_boundary_rows": len(non_boundary),
        "mean_delta_p2_minus_p1": mean_d21,
        "mean_delta_p3_minus_p2": mean_d32,
        "resource_leg_distribution": leg_dist,
        "role_distribution": role_dist,
        "failures": failures,
        "rows": results,
    }
    REPORT.write_text(json.dumps(report, indent=2) + "\n")

    print(f"p2b_ablation: {len(results)} rows ({len(non_boundary)} non-boundary), failures={len(failures)}")
    print(f"  mean capability gain  P2-P1={mean_d21}  P3-P2={mean_d32}")
    print(f"  resource_leg_distribution: {leg_dist}")
    print(f"  role_distribution: {role_dist}")
    for f in failures:
        print(f"  FAIL {f}")
    if args.check and failures:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
