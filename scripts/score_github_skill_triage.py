#!/usr/bin/env python3
"""Score GitHub skills for advisory triage (Phase 0B offline artifact).

Reads the discovery index and intake register. Output is advisory only and must
not auto-accept skills or promote runtime activation.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from github_skill_factory_lib import (
    GITHUB_ACCEPTANCE_NOTE,
    intake_by_skill_id,
    load_intake_register,
    load_json,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
DISCOVERY_PATH = REPO_ROOT / "docs" / "skills" / "github_skill_discovery_index.json"
OUTPUT_PATH = REPO_ROOT / "docs" / "skills" / "github_skill_triage_scores.json"

SCHEMA_VERSION = "2026-06-07-phase0b-v1"
SCORING_MODEL_VERSION = "phase0b-heuristic-v1"


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


def _score_skill(skill: dict[str, Any], intake: dict[str, Any] | None) -> dict[str, Any]:
    relevance_map = {"high": 0.9, "medium": 0.55, "low": 0.2, "unknown": 0.4}
    soc_relevance = relevance_map.get(str(skill.get("likely_soc_relevance")), 0.4)

    tags = {str(tag).lower() for tag in (skill.get("tags") or [])}
    haystack = " ".join(
        [
            str(skill.get("title") or ""),
            str(skill.get("github_skill_id") or ""),
            " ".join(tags),
        ]
    ).lower()
    defensive_terms = (
        "blue-team",
        "triage",
        "investigation",
        "detection",
        "hunt",
        "splunk",
        "siem",
        "phishing",
        "incident",
    )
    offensive_terms = ("exploit", "payload", "offensive", "red-team", "bypass")
    defensive_usefulness = 0.75 if any(t in haystack for t in defensive_terms) else 0.45
    if any(t in haystack for t in offensive_terms):
        defensive_usefulness = 0.15

    mitre = skill.get("mitre_attack") or []
    mapped_mitre_value = 0.8 if mitre else 0.2
    splunk_log_detection_relevance = (
        0.85
        if any(token in haystack for token in ("splunk", "siem", "event", "log", "edr"))
        else 0.35
    )
    enterprise_demo_value = 0.7 if soc_relevance >= 0.55 and defensive_usefulness >= 0.45 else 0.25
    evidence_model_availability = 0.7 if mitre and defensive_usefulness >= 0.45 else 0.3
    safety_risk = 0.8 if defensive_usefulness < 0.3 else 0.2
    overlap_with_existing_skill = 1.0 if skill.get("duplicate_of_existing") else 0.1
    implementation_complexity = 0.55
    data_source_availability = 0.6 if splunk_log_detection_relevance >= 0.7 else 0.4

    if intake and intake.get("decision") == "accept":
        recommended_decision = "accept_for_enrichment_only"
        priority = intake.get("priority") or "P2"
        reason = (
            "Already accepted in intake register for curated enrichment only; "
            "does not imply runtime_active."
        )
    elif safety_risk >= 0.7:
        recommended_decision = "reject"
        priority = "P3"
        reason = "High safety risk or offensive-leaning content signals."
    elif overlap_with_existing_skill >= 0.9:
        recommended_decision = "duplicate"
        priority = intake.get("priority") if intake else "P3"
        reason = "Overlaps an accepted intake-register skill."
    elif soc_relevance >= 0.7 and defensive_usefulness >= 0.6:
        recommended_decision = "review"
        priority = "P2"
        reason = "Promising defensive SOC relevance; requires human safety and mapping review."
    elif soc_relevance >= 0.45:
        recommended_decision = "defer"
        priority = "P3"
        reason = "Moderate relevance; defer until higher-priority batches complete."
    else:
        recommended_decision = "reject"
        priority = "P4"
        reason = "Low SOC relevance for current governed assistant scope."

    return {
        "github_skill_id": skill.get("github_skill_id"),
        "path": skill.get("path"),
        "soc_relevance": round(_clamp(soc_relevance), 3),
        "defensive_usefulness": round(_clamp(defensive_usefulness), 3),
        "mapped_mitre_value": round(_clamp(mapped_mitre_value), 3),
        "splunk_log_detection_relevance": round(_clamp(splunk_log_detection_relevance), 3),
        "enterprise_demo_value": round(_clamp(enterprise_demo_value), 3),
        "evidence_model_availability": round(_clamp(evidence_model_availability), 3),
        "safety_risk": round(_clamp(safety_risk), 3),
        "overlap_with_existing_skill": round(_clamp(overlap_with_existing_skill), 3),
        "implementation_complexity": round(_clamp(implementation_complexity), 3),
        "data_source_availability": round(_clamp(data_source_availability), 3),
        "recommended_decision": recommended_decision,
        "priority": priority,
        "reason": reason,
        "advisory_only": True,
        "acceptance_not_runtime_activation": True,
    }


def build_triage_scores(warnings: list[str]) -> dict[str, Any]:
    discovery = load_json(DISCOVERY_PATH, warnings)
    if not isinstance(discovery, dict):
        raise RuntimeError(f"discovery index missing or invalid: {DISCOVERY_PATH}")

    register = load_intake_register(warnings)
    intake_index = intake_by_skill_id(register)
    skills = discovery.get("skills") or []
    scores = [_score_skill(skill, intake_index.get(skill.get("github_skill_id"))) for skill in skills]
    scores.sort(key=lambda row: str(row.get("github_skill_id")))

    auto_accepted = [row for row in scores if row.get("recommended_decision") == "accept"]
    if auto_accepted:
        warnings.append(
            "triage scorer must not auto-accept new skills; "
            f"found {len(auto_accepted)} accept recommendations"
        )

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "scoring_model_version": SCORING_MODEL_VERSION,
        "source_discovery_file": "docs/skills/github_skill_discovery_index.json",
        "usage_note": GITHUB_ACCEPTANCE_NOTE,
        "row_counts": {
            "scores": len(scores),
            "accepted_for_enrichment_only": sum(
                1 for row in scores if row.get("recommended_decision") == "accept_for_enrichment_only"
            ),
            "review": sum(1 for row in scores if row.get("recommended_decision") == "review"),
            "defer": sum(1 for row in scores if row.get("recommended_decision") == "defer"),
            "reject": sum(1 for row in scores if row.get("recommended_decision") == "reject"),
        },
        "scores": scores,
        "warnings": warnings,
    }


def _serialize(payload: dict[str, Any]) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _check_payload(payload: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(payload)
    normalized["generated_at"] = "<generated>"
    return normalized


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)

    warnings: list[str] = []
    try:
        payload = build_triage_scores(warnings)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    rendered = _serialize(payload)
    if args.check:
        try:
            existing = json.loads(OUTPUT_PATH.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError, OSError) as exc:
            print(f"--check failed: {exc}", file=sys.stderr)
            return 1
        if _check_payload(existing) != _check_payload(payload):
            print(f"--check failed: {OUTPUT_PATH} is stale", file=sys.stderr)
            return 1
        print(f"--check ok: {OUTPUT_PATH} ({payload['row_counts']['scores']} scores)")
        return 0

    OUTPUT_PATH.write_text(rendered, encoding="utf-8")
    print(f"wrote {OUTPUT_PATH} ({payload['row_counts']['scores']} scores).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
