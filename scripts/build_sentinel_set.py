#!/usr/bin/env python3
"""Build the frozen sentinel eval set (12 of 105 + 5 PowerGrid) — T-PRE.1.

Selects a deterministic, class-covering subset of the canonical question
registries so later tasks have a <2 min happy-path gate instead of running
the full 105+50 evals per commit (plan rev 3, Part B3/B4).

Selection is fully deterministic: category filters are applied in a fixed
order, candidates are sorted by question ref, and the first N unclaimed rows
win. No randomness, no hand edits — regenerate via this script only.

Usage:
  PYTHONPATH=backend:. python3 scripts/build_sentinel_set.py            # write
  PYTHONPATH=backend:. python3 scripts/build_sentinel_set.py --check    # drift gate
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Callable

REPO_ROOT = Path(__file__).resolve().parents[1]
QUESTION_MAP_PATH = REPO_ROOT / "backend" / "app" / "coverage" / "question_runtime_map_v1.json"
POWERGRID_BANK_PATH = REPO_ROOT / "docs" / "evals" / "powergrid_soc_question_bank.json"
SENTINEL_PATH = REPO_ROOT / "docs" / "evals" / "sentinel_set.json"

SCHEMA_VERSION = 1

# Both exact paths are valid registry self-matches; T-PRE.2 asserts membership.
EXPECTED_MATCH_PATHS = ["exact_105_question", "exact_105_plus_use_case_catalog"]

# q0.q045 is the single recorded clarification-baseline row
# (scripts/eval_105_path_honoring.py CLARIFICATION_BASELINE = 1).
CLARIFICATION_BASELINE_REF = "q0.q045"

# (category, count, reason, predicate) applied in order; a row claimed by an
# earlier category is skipped by later ones.
Category = tuple[str, int, str, Callable[[dict[str, Any]], bool]]

QUESTION_CATEGORIES: list[Category] = [
    (
        "exact_analytics_smb_anchor",
        1,
        "exact-105 analytics anchor (q0.q010 SMB top talkers, plan rev 3 T-PRE.1)",
        lambda e: e["question_ref"] == "q0.q010",
    ),
    (
        "exact_analytics_top_n",
        1,
        "second top_n_aggregation analytics row",
        lambda e: e["pattern_type"] == "top_n_aggregation",
    ),
    (
        "hunt_threshold_anomaly",
        1,
        "hunt-pattern bridge: threshold_anomaly class",
        lambda e: e["pattern_type"] == "threshold_anomaly",
    ),
    (
        "hunt_dns_beaconing",
        1,
        "hunt-pattern bridge: dns_beaconing_dga_behavior class",
        lambda e: e["pattern_type"] == "dns_beaconing_dga_behavior",
    ),
    (
        # Before knowledge_sop: the single threat_intel_enrichment row
        # (q0.q005) is also the lowest knowledge_recall row — scarce
        # category must claim it first.
        "deferred_threat_intel",
        1,
        "deferred TI class: threat_intel_enrichment (needs own answer shape)",
        lambda e: e["pattern_type"] == "threat_intel_enrichment",
    ),
    (
        "knowledge_sop",
        1,
        "knowledge/SOP recall route (legacy_router_intent_hint=knowledge_recall)",
        lambda e: e.get("legacy_router_intent_hint") == "knowledge_recall",
    ),
    (
        "mitre_alert_context",
        1,
        "MITRE row requiring alert context (mitre_requires_alert_context=true)",
        lambda e: bool(e.get("mitre_requires_alert_context")),
    ),
    (
        "clarification_baseline",
        1,
        "the single recorded clarification-baseline row (eval_105 CLARIFICATION_BASELINE)",
        lambda e: e["question_ref"] == CLARIFICATION_BASELINE_REF,
    ),
    (
        "lab_draft_powershell",
        1,
        "lab-draft family coverage: suspicious_process_powershell",
        lambda e: e["pattern_type"] == "suspicious_process_powershell",
    ),
    (
        "lab_draft_exfiltration",
        1,
        "lab-draft family coverage: dlp_exfiltration",
        lambda e: e["pattern_type"] == "dlp_exfiltration",
    ),
    (
        "deferred_notable_risk_lookup",
        1,
        "deferred lookup class: notable_risk_lookup (needs own answer shape)",
        lambda e: e["pattern_type"] == "notable_risk_lookup",
    ),
    (
        "severity_policy_active",
        1,
        "active use-case severity policy class: success_after_failure",
        lambda e: e["pattern_type"] == "success_after_failure",
    ),
]

# One PowerGrid row per spanning class, lowest question_id wins.
POWERGRID_CATEGORIES: list[tuple[str, str]] = [
    ("authentication_vpn", "investigation class: VPN/auth anomaly"),
    ("mitre_judgment", "conceptual MITRE judgment class"),
    ("sop_playbook", "SOP/playbook knowledge class"),
    ("clarification", "clarification-required class"),
    ("unsafe_action", "unsafe/destructive action refusal class"),
]


def select_question_rows(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Pick the 12 registry rows per QUESTION_CATEGORIES, deterministically."""
    by_ref = sorted(entries, key=lambda e: str(e["question_ref"]))
    claimed: set[str] = set()
    rows: list[dict[str, Any]] = []
    for category, count, reason, predicate in QUESTION_CATEGORIES:
        matched = [
            e for e in by_ref
            if e["question_ref"] not in claimed and predicate(e)
        ][:count]
        if len(matched) < count:
            raise SystemExit(
                f"sentinel selection failed: category {category!r} matched "
                f"{len(matched)}/{count} rows — registry changed, review categories"
            )
        for entry in matched:
            claimed.add(entry["question_ref"])
            rows.append(
                {
                    "source": "question_runtime_map_105",
                    "category": category,
                    "question_ref": entry["question_ref"],
                    "question": entry["question"],
                    "pattern_type": entry["pattern_type"],
                    "expected_match_paths": EXPECTED_MATCH_PATHS,
                    "selection_reason": reason,
                }
            )
    return rows


def select_powergrid_rows(questions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Pick one PowerGrid row per spanning category, lowest question_id wins."""
    by_id = sorted(questions, key=lambda q: str(q["question_id"]))
    rows: list[dict[str, Any]] = []
    for category, reason in POWERGRID_CATEGORIES:
        matched = [q for q in by_id if q.get("category") == category]
        if not matched:
            raise SystemExit(
                f"sentinel selection failed: powergrid category {category!r} empty"
            )
        chosen = matched[0]
        rows.append(
            {
                "source": "powergrid_question_bank",
                "category": category,
                "question_id": chosen["question_id"],
                "question": chosen["question"],
                "expected_path_type": chosen.get("expected_path_type"),
                "selection_reason": reason,
            }
        )
    return rows


def build_sentinel_payload() -> dict[str, Any]:
    """Assemble the full sentinel set payload from both registries."""
    question_map = json.loads(QUESTION_MAP_PATH.read_text(encoding="utf-8"))
    powergrid_bank = json.loads(POWERGRID_BANK_PATH.read_text(encoding="utf-8"))
    question_rows = select_question_rows(question_map["entries"])
    powergrid_rows = select_powergrid_rows(powergrid_bank["questions"])
    return {
        "schema_version": SCHEMA_VERSION,
        "purpose": (
            "Frozen fast happy-path gate (plan rev 3 T-PRE.1). Regenerate only "
            "via scripts/build_sentinel_set.py; never hand-edit."
        ),
        "question_rows": question_rows,
        "powergrid_rows": powergrid_rows,
        "total_rows": len(question_rows) + len(powergrid_rows),
    }


def render(payload: dict[str, Any]) -> str:
    return json.dumps(payload, indent=2, ensure_ascii=False) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="exit 1 if docs/evals/sentinel_set.json drifts from regeneration",
    )
    args = parser.parse_args()

    payload = build_sentinel_payload()
    rendered = render(payload)

    if args.check:
        if not SENTINEL_PATH.exists():
            print(f"RESULT: FAIL (missing {SENTINEL_PATH})")
            return 1
        current = SENTINEL_PATH.read_text(encoding="utf-8")
        if current != rendered:
            print("RESULT: FAIL (sentinel_set.json drifted from deterministic regeneration)")
            return 1
        print(f"RESULT: PASS ({payload['total_rows']}/{payload['total_rows']} rows, no drift)")
        return 0

    SENTINEL_PATH.write_text(rendered, encoding="utf-8")
    print(f"wrote {SENTINEL_PATH} ({payload['total_rows']} rows)")
    print(f"RESULT: PASS ({payload['total_rows']}/{payload['total_rows']} rows)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
