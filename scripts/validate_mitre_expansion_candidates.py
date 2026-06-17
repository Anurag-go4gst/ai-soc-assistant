#!/usr/bin/env python3
"""Validate the MITRE-audit expansion candidates into a promote/drop list (plan §15 G3).

Offline, deterministic, no LLM. Two stages:

  1. EXTRACTION (always runs, no bundle needed): compute the expansion-candidate set
     as the union of every ``results[*].llm_invalid_ids`` in the catalogue audit, minus
     the local bundle (``mitre_attack_subset.json``), deduplicated. Audit semantics:
     ``llm_valid_ids`` = IDs that matched the local 13-technique subset;
     ``llm_invalid_ids`` = IDs the LLM proposed that are OUTSIDE the subset — i.e. the
     expansion candidates (97 of them). There is NO ``expansion`` bucket in the audit
     JSON; this set is derived, per COE report §4.

  2. DISPOSITION (resolver-gated): when an offline resolver is operational
     (``AttackDataResolver`` xlsx/yaml preferred, else ``StixTechniqueResolver`` STIX),
     classify each ID as ``promote_candidate``, ``deprecated``/``revoked``, or
     ``not_found``. Until a resolver is onboarded every row is ``pending_bundle``.

Writes docs/evals/mitre_expansion_validated.{json,md}. Exit 0.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "docs" / "evals" / "out" / "llm_mitre_catalogue_audit.json"
SUBSET = ROOT / "backend" / "app" / "threat" / "mitre_attack_subset.json"
OUT_DIR = ROOT / "docs" / "evals"

# Make backend importable for the resolver + config.
sys.path.insert(0, str(ROOT / "backend"))


def _bundle_ids() -> set[str]:
    payload = json.loads(SUBSET.read_text(encoding="utf-8"))
    techniques = payload.get("techniques", []) if isinstance(payload, dict) else []
    return {
        str(t.get("technique_id")).strip()
        for t in techniques
        if isinstance(t, dict) and t.get("technique_id")
    }


def extract_candidates() -> tuple[list[str], set[str]]:
    """Return (sorted expansion candidate IDs, bundle IDs). Candidates = union of all
    llm_invalid_ids (out-of-subset proposals) minus the local bundle."""
    audit = json.loads(AUDIT.read_text(encoding="utf-8"))
    bundle = _bundle_ids()
    out_of_subset: set[str] = set()
    for row in audit.get("results", []):
        for tid in row.get("llm_invalid_ids", []) or []:
            tid = str(tid).strip()
            if tid:
                out_of_subset.add(tid)
    candidates = sorted(out_of_subset - bundle)
    return candidates, bundle


def _resolver():
    """Build a technique resolver from config paths; None on any import/config failure."""
    try:
        from app.threat.attack_data_resolver import technique_resolver_from_settings

        resolver = technique_resolver_from_settings()
        if not getattr(resolver, "operational", False):
            return None
        return resolver
    except Exception:  # noqa: BLE001 - resolver is optional; extraction still runs
        return None


def disposition(candidates: list[str], resolver) -> list[dict]:
    from app.threat.attack_data_resolver import AttackDataResolver, absent_technique_disposition

    rows: list[dict] = []
    operational = bool(resolver and getattr(resolver, "operational", False))
    for tid in candidates:
        if not operational:
            rows.append({"technique_id": tid, "disposition": "pending_bundle", "detail": None})
            continue
        detail = resolver.detail(tid)
        if detail is None:
            verdict = (
                absent_technique_disposition(tid)
                if isinstance(resolver, AttackDataResolver)
                else "not_found"
            )
        elif detail.get("deprecated") or detail.get("revoked"):
            verdict = "deprecated"
        else:
            verdict = "promote_candidate"
        rows.append({"technique_id": tid, "disposition": verdict, "detail": detail})
    return rows


def _render_md(report: dict) -> str:
    counts = report["disposition_counts"]
    lines = [
        "# MITRE expansion-candidate validation (plan §15 G3)",
        "",
        f"- Generated: `{report['generated_at_utc']}`",
        f"- Audit source: `{report['audit_source']}`",
        f"- Bundle techniques (excluded): **{report['bundle_count']}**",
        f"- Expansion candidates: **{report['candidate_count']}**",
        f"- Resolver operational: **{report['resolver_operational']}**",
        "",
        "Dispositions: "
        + ", ".join(f"`{k}`={v}" for k, v in sorted(counts.items())),
        "",
        "> Candidates = union of all `results[*].llm_invalid_ids` (out-of-subset "
        "proposals) minus the local bundle. No `expansion` bucket exists in the audit "
        "JSON; this set is derived. When no offline resolver is onboarded, every row "
        "is `pending_bundle` (honest, not a fabricated promote/drop).",
        "",
        "| techniqueID | disposition | name |",
        "|---|---|---|",
    ]
    for row in report["candidates"]:
        name = (row.get("detail") or {}).get("name", "") if row.get("detail") else ""
        lines.append(f"| `{row['technique_id']}` | {row['disposition']} | {name} |")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    candidates, bundle = extract_candidates()
    resolver = _resolver()
    rows = disposition(candidates, resolver)
    counts: dict[str, int] = {}
    for row in rows:
        counts[row["disposition"]] = counts.get(row["disposition"], 0) + 1

    report = {
        "schema_role": "mitre_expansion_validated_v1",
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "audit_source": str(AUDIT.relative_to(ROOT)),
        "bundle_count": len(bundle),
        "candidate_count": len(candidates),
        "resolver_operational": bool(resolver and getattr(resolver, "operational", False)),
        "disposition_counts": counts,
        "candidates": rows,
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "mitre_expansion_validated.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    (OUT_DIR / "mitre_expansion_validated.md").write_text(_render_md(report), encoding="utf-8")
    print(
        f"Expansion candidates: {len(candidates)} (bundle {len(bundle)} excluded); "
        f"resolver_operational={report['resolver_operational']}; "
        f"dispositions={counts} -> docs/evals/mitre_expansion_validated.{{json,md}}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
