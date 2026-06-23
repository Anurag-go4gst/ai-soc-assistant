#!/usr/bin/env python3
"""Build labeled_release_v1 from frozen discovery_v1 + P1 routing labels (plan §4.1/§4.2).

Emits the §4.2 per-question release schema for all 100 frozen `discovery_v1`
questions. Fields derivable from the existing P1 routing labels and deterministic
registries are filled; the two fields that require expert ground truth —
``must_include`` and ``must_not_claim`` — are left as empty slots with
``label_status='needs_expert'`` rather than fabricated. Plan §4.3 requires two-
reviewer expert sign-off before the bank is release-gating; this script produces the
machine-derivable scaffold that those reviewers complete.

Usage:
  PYTHONPATH=backend:. python3 scripts/build_labeled_release_v1.py
  PYTHONPATH=backend:. python3 scripts/build_labeled_release_v1.py --check
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
BANK = REPO / "docs/evals/live_efficacy_100_bank.json"
P1_LABELS = REPO / "docs/evals/live_efficacy_100_labels.json"
OUT = REPO / "docs/evals/labeled_release_v1.json"

EXPERT_FIELDS = ("must_include", "must_not_claim")

_ARTIFACT_MAP = {
    "spl_artifact": ["spl"],
    "investigation_plan": ["guidance"],
    "mitre_mapping": ["mitre"],
    "playbook_steps": ["rag"],
    "knowledge_explanation": ["rag"],
    "severity_assessment": ["guidance"],
    "source_health_assessment": ["guidance"],
    "baseline_method": ["spl", "guidance"],
    "boundary_refusal": [],
}


def _tier(intent: str, boundary: str | None) -> str:
    if boundary:
        return "boundary"
    if intent == "guided_investigation":
        return "T2"  # out-of-catalogue hunt
    return "T1"


def _expected_hil(intent: str, boundary: str | None) -> str:
    if boundary == "unsafe_execution":
        return "none"  # refused outright
    if "run" in intent or intent == "spl_generation_and_run":
        return "execution_confirmation"
    if intent in {"guided_investigation", "clarification_required"}:
        return "review"
    return "none"


def _latency_class(intent: str, boundary: str | None) -> str:
    if boundary or intent in {"knowledge_only", "policy_knowledge", "sop_or_playbook"}:
        return "deterministic"
    if intent in {"guided_investigation", "mitre_mapping", "mitre_explanation"}:
        return "llm_optional"
    return "llm_optional"


def _authority_source(boundary: str | None) -> str:
    return "policy" if boundary else "registry"


def _must_not_claim(boundary: str | None, expected_artifacts: list[str]) -> list[str]:
    """Only the safety claims that are deterministically forbidden; expert adds the rest."""
    forbidden: list[str] = []
    if boundary:
        forbidden += ["executed the search", "ran the query", "returned real results"]
    if "spl" in expected_artifacts:
        forbidden += ["this query was executed", "live results"]
    return sorted(set(forbidden))


def _primary_objective(intent: str, shape: str) -> str:
    return f"{intent.replace('_', ' ')} via {shape.replace('_', ' ')}".strip()


def _release_row(label: dict) -> dict:
    intent = str(label.get("primary_intent") or "")
    shape = str(label.get("answer_shape") or "")
    boundary = label.get("boundary_class")
    artifact_type = str(label.get("artifact_type") or "")
    expected_artifacts = list(_ARTIFACT_MAP.get(artifact_type, ["guidance"]))
    legs = [d for d in (label.get("evidence_domains") or []) if d and d != "none"]
    return {
        "id": label["id"],
        "category": label["category"],
        "tier": _tier(intent, boundary),
        "question": label["question"],
        "primary_objective": _primary_objective(intent, shape),
        "expected_answer_shape": shape,
        "acceptable_skills": list(label.get("acceptable_skills") or []),
        "required_evidence_legs": legs,
        "expected_artifacts": expected_artifacts,
        "must_include": [],            # expert
        "must_not_claim": _must_not_claim(boundary, expected_artifacts),  # safety seed; expert extends
        "expected_hil": _expected_hil(intent, boundary),
        "latency_class": _latency_class(intent, boundary),
        "authority_source": _authority_source(boundary),
        "boundary_class": boundary,
        "label_status": "needs_expert",
        "expert_fields_pending": list(EXPERT_FIELDS),
        "derived_from": "live_efficacy_100_labels.json",
    }


def build() -> dict:
    bank = json.loads(BANK.read_text())
    labels = {row["id"]: row for row in json.loads(P1_LABELS.read_text())["labels"]}
    rows = []
    for q in bank["questions"]:
        label = labels.get(q["id"])
        if not label:
            raise SystemExit(f"missing P1 label for {q['id']}")
        rows.append(_release_row(label))
    return {
        "name": "labeled_release_v1",
        "version": 1,
        "source_bank": "live_efficacy_100_bank.json (discovery_v1, frozen)",
        "schema": "plan §4.2 per-question release schema",
        "note": "must_include / must_not_claim require two-reviewer expert sign-off (plan §4.3) before this bank is release-gating; rows carry label_status='needs_expert'.",
        "row_count": len(rows),
        "rows": rows,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    out = build()
    if not args.check:
        OUT.write_text(json.dumps(out, indent=2) + "\n")
    tiers = {}
    for r in out["rows"]:
        tiers[r["tier"]] = tiers.get(r["tier"], 0) + 1
    print(f"labeled_release_v1: {out['row_count']} rows, tiers={tiers}")
    print(f"  expert fields pending on all rows: {list(EXPERT_FIELDS)}")
    if out["row_count"] != 100:
        print("  FAIL expected 100 rows")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
