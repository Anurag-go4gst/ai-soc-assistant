#!/usr/bin/env python3
"""P3 — deterministic asset-contribution eval (plan §456).

Proves the chain "asset exists -> governed contribution -> visible structure with
provenance" deterministically, for MITRE, CVE, GitHub-skill, and RAG classes, driven
from the REAL repo assets (use-case catalog, ATT&CK bundle, CVE snapshot store, skill
registry). It asserts governed contribution + provenance + the no-fabrication
invariants, NOT subjective answer quality.

The live ≥90% answer-relevance/evidence-linkage rubric on `/chat` and the human-rated
GitHub-skill usefulness (plan §456 gate) are the operator residual; this eval is the
deterministic floor that must hold first.

Usage:
  PYTHONPATH=backend:. python3 scripts/eval_p3_contribution.py
  PYTHONPATH=backend:. python3 scripts/eval_p3_contribution.py --check
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
for _p in (str(REPO / "backend"), str(REPO)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

REPORT = REPO / "docs/evals/p3_contribution_report.json"

# Governed MITRE status vocab — "confirmed" must NEVER appear (ATT&CK = behavior,
# not analytics; mappings are candidate/needs_review until SOC-approved).
MITRE_STATUS_VOCAB = {"supported", "candidate", "needs_review", "not_mapped", "not_applicable"}
FORBIDDEN_MITRE_STATUS = {"confirmed", "proven", "verified"}


def _eval_mitre() -> dict:
    from app.threat.mitre_permitted_builder import build_mitre_permitted_for_question
    from app.use_cases.registry import load_use_case_catalog

    cat = load_use_case_catalog()
    items = list(cat.values()) if isinstance(cat, dict) else cat
    with_mitre = [u for u in items if getattr(u, "mitre_candidates", None)][:15]
    rows, failures = [], []
    for uc in with_mitre:
        uid = getattr(uc, "use_case_id", getattr(uc, "id", "?"))
        result = build_mitre_permitted_for_question(query_text=None, use_case_id=uid, question_ref=None)
        d = result.to_dict() if hasattr(result, "to_dict") else result
        entries = d.get("entries") or []
        statuses = {e.get("status") for e in entries}
        bad = statuses & FORBIDDEN_MITRE_STATUS
        has_provenance = all(e.get("use_case_ids") and "in_local_bundle" in e for e in entries)
        bucketed = all(e.get("status") in MITRE_STATUS_VOCAB for e in entries)
        ok = bool(entries) and not bad and has_provenance and bucketed
        if not ok:
            failures.append(f"mitre:{uid}: entries={len(entries)} bad_status={bad} provenance={has_provenance} bucketed={bucketed}")
        rows.append({"class": "mitre", "use_case_id": uid, "entry_count": len(entries),
                     "statuses": sorted(s for s in statuses if s), "provenance": has_provenance, "ok": ok})
    return {"rows": rows, "failures": failures}


def _eval_cve() -> dict:
    from app.cve.snapshot_store import CveSnapshotStore
    from app.config import settings

    store = CveSnapshotStore(
        package_dir=settings.ai_soc_cve_snapshot_dir or None,
        stale_after_days=settings.ai_soc_cve_snapshot_stale_after_days,
    )
    status = store.vulnerability_source_status()
    queries = [
        "Is CVE-2021-44228 (log4j) exploitable on our hosts?",
        "Affected versions for the OpenSSL advisory?",
        "Scanner says critical but vendor disputes — which is right?",
        "Join CVE findings to our asset inventory.",
        "Unknown CVE-9999-0000 — do we have it?",
        "How stale is the vulnerability snapshot?",
    ]
    rows, failures = [], []
    for q in queries:
        # Honest chain: a typed status + provenance; not-onboarded must be substantive
        # (carry a limitation), never silently empty or fabricated.
        honest = bool(status.status) and (
            status.status != "not_onboarded" or bool(getattr(status, "limitation", None))
        )
        provenance_present = hasattr(status, "provenance")
        ok = honest and provenance_present
        if not ok:
            failures.append(f"cve:{q[:30]}: status={status.status} honest={honest} provenance={provenance_present}")
        rows.append({"class": "cve", "query": q, "status": status.status,
                     "limitation": bool(getattr(status, "limitation", None)), "ok": ok})
    return {"rows": rows, "failures": failures}


def _eval_skills() -> dict:
    from app.skills.registry import load_skill_registry

    AUTHORITY_OVERRIDE_FIELDS = {"system_prompt", "authority", "execution_policy", "safety_override"}
    reg = load_skill_registry()[:15]
    rows, failures = [], []
    for skill in reg:
        d = skill.model_dump() if hasattr(skill, "model_dump") else dict(skill)
        sid = d.get("skill_id") or d.get("display_name") or "?"
        # Governed contract present: capability + safety surfaces.
        contract_ok = all(k in d for k in ("display_name", "allowed_tools", "blocked_tools", "hil_policy", "action_tier_allowed"))
        # Untrusted-data invariant: a skill definition never carries authority/system override.
        no_override = not (set(d.keys()) & AUTHORITY_OVERRIDE_FIELDS)
        ok = contract_ok and no_override
        if not ok:
            failures.append(f"skill:{sid}: contract={contract_ok} no_override={no_override}")
        rows.append({"class": "github_skill", "skill_id": sid, "contract_ok": contract_ok,
                     "no_authority_override": no_override, "ok": ok})
    return {"rows": rows, "failures": failures}


def _eval_rag() -> dict:
    """Structural honesty: the offline retriever never fabricates a citation; it
    returns an explicit no-match/not-implemented note. Live governed SOC-KB retrieval
    into SourceEvidence is the operator residual."""
    from app.rag.retriever_keyword import retrieve_keyword

    rows, failures = [], []
    for q in ["account lockout playbook", "NERC CIP incident reporting timeline", "no such knowledge xyz123"]:
        hits = retrieve_keyword(q)
        honest = bool(hits) and all(("note" in h or "text" in h) for h in hits)
        fabricated = any(h.get("text") and "fabric" in str(h.get("source", "")).lower() for h in hits)
        ok = honest and not fabricated
        if not ok:
            failures.append(f"rag:{q[:30]}: honest={honest} fabricated={fabricated}")
        rows.append({"class": "rag", "query": q, "honest_no_fabrication": ok})
    return {"rows": rows, "failures": failures}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()

    sections = {
        "mitre": _eval_mitre(),
        "cve": _eval_cve(),
        "github_skill": _eval_skills(),
        "rag": _eval_rag(),
    }
    failures = [f for s in sections.values() for f in s["failures"]]
    report = {
        "note": "deterministic asset-contribution floor; live ≥90% relevance rubric + human-rated usefulness are the operator residual (plan §456). RAG live SOC-KB retrieval is residual.",
        "class_counts": {k: len(v["rows"]) for k, v in sections.items()},
        "failures": failures,
        "sections": sections,
    }
    REPORT.write_text(json.dumps(report, indent=2) + "\n")

    print("p3_contribution:")
    for k, v in sections.items():
        ok = sum(1 for r in v["rows"] if r.get("ok", r.get("honest_no_fabrication")))
        print(f"  {k}: {ok}/{len(v['rows'])} ok")
    print(f"  total failures: {len(failures)}")
    for f in failures[:20]:
        print(f"  FAIL {f}")
    if args.check and failures:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
