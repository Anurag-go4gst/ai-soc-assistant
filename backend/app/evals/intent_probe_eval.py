"""Out-of-set intent probe evaluation (intent cascade §7)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.chat.intent_classifier import build_query_to_intent
from app.query_understanding.parser import understand_query

REPO_ROOT = Path(__file__).resolve().parents[3]
PROBE_PATH = REPO_ROOT / "docs" / "evals" / "intent_out_of_set_probes.json"
BASELINE_PATH = REPO_ROOT / "docs" / "evals" / "intent_out_of_set_probes_baseline.json"

ACTIONABLE_FAMILIES = frozenset(
    {
        "spl_generation_only",
        "live_investigation",
        "hybrid_alert_review",
        "hybrid_investigation",
        "hybrid_investigation_plus_policy",
        "attack_discovery",
        "guided_investigation",
        "knowledge_only",
    }
)


def load_probes(*, path: Path | None = None) -> list[dict[str, Any]]:
    payload = json.loads((path or PROBE_PATH).read_text(encoding="utf-8"))
    probes = payload.get("probes") or []
    if not isinstance(probes, list) or not probes:
        raise ValueError("intent_out_of_set_probes.json must contain a non-empty probes array")
    return probes


def evaluate_probe(probe: dict[str, Any]) -> dict[str, Any]:
    query = str(probe["query"])
    understanding = understand_query(query)
    result = build_query_to_intent(query=query, query_understanding=understanding)
    intent = result.intent_classification
    family = intent.intent_family
    row = {
        "id": probe["id"],
        "kind": probe.get("kind"),
        "query": query,
        "intent_family": family,
        "primary_intent": intent.primary_intent,
        "match_path": result.candidate_mappings.get("match_path"),
        "requires_clarification": intent.requires_clarification,
        "requires_hil": intent.requires_hil,
        "reason": intent.reason,
        "actionable": family in ACTIONABLE_FAMILIES,
        "severity": "pass",
        "reasons": [],
    }
    expected = probe.get("expect_family")
    if expected and family != expected:
        row["severity"] = "fail"
        row["reasons"].append(f"expected intent_family={expected}, got {family}")
    forbidden = list(probe.get("forbid_families") or [])
    if family in forbidden:
        row["severity"] = "fail"
        row["reasons"].append(f"forbidden intent_family={family}")
    allowed = probe.get("allowed_families")
    if allowed and family not in allowed:
        row["severity"] = "fail"
        row["reasons"].append(f"intent_family={family} not in allowed={allowed}")
    if probe.get("expect_requires_hil") is True and not intent.requires_hil:
        row["severity"] = "fail"
        row["reasons"].append("expected requires_hil=true")
    if not expected and not allowed and family == "clarification_required" and probe.get("kind") == "novel_hunt":
        row["severity"] = "review"
        row["reasons"].append("novel hunt landed clarification_required (clarification dump risk)")
    return row


def evaluate_all(*, path: Path | None = None) -> dict[str, Any]:
    probes = load_probes(path=path)
    rows = [evaluate_probe(probe) for probe in probes]
    counts = {"pass": 0, "review": 0, "fail": 0}
    for row in rows:
        counts[row["severity"]] = counts.get(row["severity"], 0) + 1
    return {
        "probe_count": len(rows),
        "counts": counts,
        "critical_count": counts["fail"],
        "rows": rows,
    }


def freeze_baseline(report: dict[str, Any]) -> None:
    payload = {
        "version": "intent_out_of_set_probes_baseline_v1",
        "probe_count": report["probe_count"],
        "rows": {
            row["id"]: {
                "intent_family": row["intent_family"],
                "match_path": row["match_path"],
                "requires_clarification": row["requires_clarification"],
                "requires_hil": row["requires_hil"],
            }
            for row in report["rows"]
        },
    }
    BASELINE_PATH.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def check_against_baseline(report: dict[str, Any]) -> list[str]:
    if not BASELINE_PATH.is_file():
        return ["baseline missing: run scripts/eval_out_of_set_intent_probe.py --freeze"]
    baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    expected_rows = baseline.get("rows") or {}
    diffs: list[str] = []
    for row in report["rows"]:
        probe_id = row["id"]
        expected = expected_rows.get(probe_id)
        if expected is None:
            diffs.append(f"{probe_id}: missing from baseline")
            continue
        for key in ("intent_family", "match_path", "requires_clarification", "requires_hil"):
            if row.get(key) != expected.get(key):
                diffs.append(
                    f"{probe_id}.{key}: expected {expected.get(key)!r}, got {row.get(key)!r}"
                )
    return diffs
