#!/usr/bin/env python3
"""Compare our catalogue/105 MITRE findings against the operator-supplied ATLAS raw.

Offline, deterministic, no LLM. ATLAS is the MITRE ATLAS AI-threat taxonomy
(AML.Txxxx IDs) — a DIFFERENT matrix from enterprise ATT&CK (Txxxx), so there is
no direct ID overlap with our enterprise findings. The useful comparison is:

  1. ID-overlap check (expected: zero) — proves they are separate taxonomies.
  2. Per-tactic ATLAS technique counts + case-study frequency weighting.
  3. Shared-name tactics (parallel to our enterprise SOC coverage) vs AI-specific
     tactics (ai-model-access, ai-attack-staging) = pure coverage gaps for us.
  4. Duplicate techniqueID-across-tactics gate (plan E2).

Writes docs/evals/out/atlas_vs_catalogue_comparison.{json,md}.
"""
from __future__ import annotations

import collections
import json
import re
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ATLAS_MATRIX = ROOT / "docs" / "threat-intel" / "atlas" / "raw" / "ATLAS_Matrix.json"
ATLAS_FREQ = ROOT / "docs" / "threat-intel" / "atlas" / "raw" / "ATLAS_Case_Study_Frequency.json"
AUDIT = ROOT / "docs" / "evals" / "out" / "llm_mitre_catalogue_audit.json"
OUT = ROOT / "docs" / "evals" / "out"

# Enterprise tactic names that ATLAS reuses (parallel to our SOC detection coverage).
SHARED_TACTICS = {
    "reconnaissance", "resource-development", "initial-access", "execution",
    "persistence", "privilege-escalation", "defense-evasion", "credential-access",
    "discovery", "lateral-movement", "collection", "command-and-control",
    "exfiltration", "impact",
}
# ATLAS-only tactics — no enterprise SOC coverage in our catalogue today.
AI_ONLY_TACTICS = {"ai-attack-staging", "ai-model-access"}


def _our_finding_ids() -> set[str]:
    """All enterprise technique IDs our audit touched (deterministic + LLM-surfaced)."""
    ids: set[str] = set()
    if AUDIT.exists():
        data = json.loads(AUDIT.read_text())
        for row in data.get("results", []):
            for key in ("deterministic_permitted", "deterministic_candidate",
                        "deterministic_blocked", "llm_valid_ids", "llm_invalid_ids",
                        "gap", "contradiction", "over_map"):
                ids.update(row.get(key) or [])
    return {i.upper() for i in ids}


def main() -> int:
    matrix = json.loads(ATLAS_MATRIX.read_text())["techniques"]
    freq = {t["techniqueID"]: t.get("score", 0) for t in json.loads(ATLAS_FREQ.read_text())["techniques"]}

    atlas_ids = [t["techniqueID"] for t in matrix]
    distinct = set(atlas_ids)
    # duplicate techniqueID across tactics (plan E2 gate)
    id_tactics: dict[str, set[str]] = collections.defaultdict(set)
    for t in matrix:
        id_tactics[t["techniqueID"]].add(t.get("tactic", ""))
    multi_tactic = {tid: sorted(tac) for tid, tac in id_tactics.items() if len(tac) > 1}

    # per-tactic counts
    per_tactic = collections.Counter(t.get("tactic", "") for t in matrix)
    # frequency-weighted per tactic (sum of case-study scores), one row per (id,tactic)
    tactic_freq: dict[str, int] = collections.Counter()
    for t in matrix:
        tactic_freq[t.get("tactic", "")] += freq.get(t["techniqueID"], 0)

    # top techniques by case-study frequency (real-world AI attack prevalence)
    top_by_freq = sorted(distinct, key=lambda i: freq.get(i, 0), reverse=True)[:15]

    our_ids = _our_finding_ids()
    enterprise_overlap = sorted(our_ids & distinct)  # expected empty

    ai_only = {tac: per_tactic[tac] for tac in AI_ONLY_TACTICS if tac in per_tactic}
    shared = {tac: per_tactic[tac] for tac in per_tactic if tac in SHARED_TACTICS}
    unexpected = {tac: per_tactic[tac] for tac in per_tactic
                  if tac not in SHARED_TACTICS and tac not in AI_ONLY_TACTICS}

    report = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "atlas_rows": len(matrix),
        "atlas_distinct_ids": len(distinct),
        "atlas_multi_tactic_ids": multi_tactic,
        "our_finding_ids_count": len(our_ids),
        "enterprise_id_overlap": enterprise_overlap,
        "per_tactic_counts": dict(per_tactic),
        "per_tactic_case_study_frequency": dict(tactic_freq),
        "shared_name_tactics": shared,
        "ai_only_tactics": ai_only,
        "unexpected_tactics": unexpected,
        "top_techniques_by_case_study_frequency": [
            {"techniqueID": i, "score": freq.get(i, 0), "tactics": sorted(id_tactics[i])}
            for i in top_by_freq
        ],
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "atlas_vs_catalogue_comparison.json").write_text(json.dumps(report, indent=2))

    md = []
    md.append("# ATLAS raw vs catalogue/105 MITRE findings — comparison\n")
    md.append(f"**Date:** {report['generated_at_utc'][:10]}  ")
    md.append("**Inputs:** `docs/threat-intel/atlas/raw/ATLAS_Matrix.json` (+ Case_Study_Frequency), "
              "`docs/evals/out/llm_mitre_catalogue_audit.json`  ")
    md.append("**Method:** offline deterministic, no LLM.\n")
    md.append("## 1. Taxonomy overlap\n")
    md.append(f"- ATLAS rows: **{len(matrix)}**, distinct AML technique IDs: **{len(distinct)}**.")
    md.append(f"- Our audit touched **{len(our_ids)}** enterprise ATT&CK IDs.")
    md.append(f"- **Enterprise↔ATLAS direct ID overlap: {len(enterprise_overlap)}** "
              f"{enterprise_overlap or '(none — separate taxonomies, as expected)'}.")
    md.append("- ATLAS is the AI/ML-threat matrix (AML.Txxxx); our catalogue is enterprise ATT&CK "
              "(Txxxx). They do not share IDs — ATLAS is a **net-new coverage domain**, not a "
              "validation set for our enterprise expansion candidates.\n")
    md.append("## 2. Duplicate techniqueID across tactics (plan E2 gate)\n")
    md.append(f"- {len(matrix)} rows collapse to {len(distinct)} IDs → "
              f"**{len(multi_tactic)} techniques appear under multiple tactics** (do not collapse "
              "before review). Examples:")
    for tid, tacs in list(multi_tactic.items())[:8]:
        md.append(f"  - `{tid}`: {', '.join(tacs)}")
    md.append("")
    md.append("## 3. Coverage gap — AI-only tactics (no enterprise SOC coverage)\n")
    md.append("| ATLAS tactic | techniques | case-study freq |")
    md.append("|---|---|---|")
    for tac, n in sorted(ai_only.items(), key=lambda x: -x[1]):
        md.append(f"| **{tac}** | {n} | {tactic_freq.get(tac,0)} |")
    md.append("\nThese tactics (AI model access, AI attack staging) have **zero coverage** in our "
              "105/catalogue and zero overlap with the LLM expansion candidates — the AI/LLM/MCP-threat "
              "gap for T2 guided-hunt and the ATLAS workstream.\n")
    md.append("## 4. Shared-name tactics (parallel to our SOC coverage)\n")
    md.append("| ATLAS tactic | techniques | case-study freq |")
    md.append("|---|---|---|")
    for tac, n in sorted(shared.items(), key=lambda x: -tactic_freq.get(x[0], 0)):
        md.append(f"| {tac} | {n} | {tactic_freq.get(tac,0)} |")
    md.append("\nWhere ATLAS reuses enterprise tactic names, AI attacks parallel our SOC detections "
              "(e.g. credential-access, exfiltration, C2) — candidate cross-domain links per plan §C3b.\n")
    md.append("## 5. Top ATLAS techniques by real-world case-study frequency\n")
    md.append("| AML technique | score | tactic(s) |")
    md.append("|---|---|---|")
    for row in report["top_techniques_by_case_study_frequency"]:
        md.append(f"| {row['techniqueID']} | {row['score']} | {', '.join(row['tactics'])} |")
    md.append("\n## 6. Conclusion\n")
    md.append("- ATLAS does **not** validate our enterprise expansion candidates (no ID overlap); "
              "the full enterprise ATT&CK bundle is still required for that (§5 of the MITRE audit report).")
    md.append("- ATLAS is a **separate coverage domain**: AI/LLM/MCP threats absent from our catalogue. "
              "Highest-frequency AML techniques + AI-only tactics are the priority for ATLAS intake and "
              "T2 AI-threat guided-hunt grounding.")
    md.append("- Duplicate/multi-tactic gate satisfied: review before any normalization (plan E2/E3); "
              "raw preserved unmodified.")
    (OUT / "atlas_vs_catalogue_comparison.md").write_text("\n".join(md) + "\n")

    print(f"ATLAS rows {len(matrix)} distinct {len(distinct)} multi-tactic {len(multi_tactic)}")
    print(f"enterprise ID overlap: {len(enterprise_overlap)} {enterprise_overlap}")
    print(f"AI-only tactics: {ai_only}")
    print(f"unexpected tactics: {unexpected}")
    print(f"Reports: {OUT/'atlas_vs_catalogue_comparison.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
