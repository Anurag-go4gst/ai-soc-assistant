#!/usr/bin/env python3
"""Validate a labeled release bank against plan §4.2 schema + §4.3 checks.

Structural/coverage validation only. Expert correctness (two-reviewer §4.3) and
semantic dedup against other banks are separate human passes; a row with
``label_status='needs_expert'`` is structurally valid but NOT release-gating until
its expert fields are filled and signed off.

Usage:
  PYTHONPATH=backend:. python3 scripts/validate_release_bank.py
  PYTHONPATH=backend:. python3 scripts/validate_release_bank.py --check
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
BANK = REPO / "docs/evals/labeled_release_v1.json"

REQUIRED_FIELDS = (
    "id", "category", "tier", "question", "primary_objective", "expected_answer_shape",
    "acceptable_skills", "required_evidence_legs", "expected_artifacts", "must_include",
    "must_not_claim", "expected_hil", "latency_class", "authority_source",
)
TIERS = {"T0", "T1", "T2", "boundary"}
HIL = {"none", "review", "execution_confirmation"}
LATENCY = {"deterministic", "llm_optional", "llm_required"}
AUTHORITY = {"expert", "policy", "registry", "fixture"}
ARTIFACTS = {"guidance", "spl", "rag", "mitre", "cve", "mcp_plan"}


def validate(bank: dict) -> list[str]:
    failures: list[str] = []
    rows = bank.get("rows", [])
    ids, questions = set(), set()

    for r in rows:
        rid = r.get("id", "?")
        for f in REQUIRED_FIELDS:
            if f not in r:
                failures.append(f"{rid}: missing field {f}")
        # uniqueness
        if r.get("id") in ids:
            failures.append(f"{rid}: duplicate id")
        ids.add(r.get("id"))
        q = (r.get("question") or "").strip().lower()
        if q in questions:
            failures.append(f"{rid}: duplicate question text")
        questions.add(q)
        # enums
        if r.get("tier") not in TIERS:
            failures.append(f"{rid}: bad tier {r.get('tier')}")
        if r.get("expected_hil") not in HIL:
            failures.append(f"{rid}: bad expected_hil {r.get('expected_hil')}")
        if r.get("latency_class") not in LATENCY:
            failures.append(f"{rid}: bad latency_class {r.get('latency_class')}")
        if r.get("authority_source") not in AUTHORITY:
            failures.append(f"{rid}: bad authority_source {r.get('authority_source')}")
        for a in r.get("expected_artifacts") or []:
            if a not in ARTIFACTS:
                failures.append(f"{rid}: bad artifact {a}")
        # one primary objective present
        if not (r.get("primary_objective") or "").strip():
            failures.append(f"{rid}: empty primary_objective")
        # boundary safety: refusal rows must seed a must_not_claim safety guard
        if r.get("tier") == "boundary" and not r.get("must_not_claim"):
            failures.append(f"{rid}: boundary row missing must_not_claim safety seed")
        # non-boundary rows must declare at least one acceptable skill
        if r.get("tier") != "boundary" and not r.get("acceptable_skills"):
            failures.append(f"{rid}: non-boundary row has no acceptable_skills")

    # coverage
    tiers_present = {r.get("tier") for r in rows}
    for needed in ("T1", "T2", "boundary"):
        if needed not in tiers_present:
            failures.append(f"coverage: tier {needed} absent")
    if len({r.get("expected_answer_shape") for r in rows}) < 5:
        failures.append("coverage: fewer than 5 distinct answer shapes")
    return failures


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    bank = json.loads(BANK.read_text())
    failures = validate(bank)
    pending = sum(1 for r in bank["rows"] if r.get("label_status") == "needs_expert")
    print(f"validate_release_bank: {len(bank['rows'])} rows, structural_failures={len(failures)}")
    print(f"  rows pending expert sign-off (not release-gating): {pending}")
    for f in failures[:30]:
        print(f"  FAIL {f}")
    if args.check and failures:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
