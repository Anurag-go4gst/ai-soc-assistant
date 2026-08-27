#!/usr/bin/env python3
"""S0 — freeze approved / normalized_spl / execution_eligible for OPTIONAL_PHASE_S.

Banks:
  - spl_golden: templates.json spl_text + deterministic compiler shapes
  - convergence: docs/evals/answer_shape/convergence_expectation_bank_v1.json

Usage:
  PYTHONPATH=backend:. python3 scripts/freeze_spl_optimization_authority.py --freeze
  PYTHONPATH=backend:. python3 scripts/freeze_spl_optimization_authority.py --check
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUT_PATH = ROOT / "docs/evals/spl_optimization/authority_baseline_v1.json"
TEMPLATES_PATH = ROOT / "backend/app/spl/templates.json"
CONVERGENCE_BANK_PATH = ROOT / "docs/evals/answer_shape/convergence_expectation_bank_v1.json"
BASE_SHA = "11a273653c3acb1a34f715ee417e2d94447b762d"

INTENT_SHAPES: list[tuple[str, str]] = [
    (
        "compiler.intent.rolling",
        "one source IP attacking multiple distinct accounts over a rolling 10-minute window",
    ),
    (
        "compiler.intent.trend",
        "hourly failed-login trend over the last 24 hours",
    ),
    (
        "compiler.intent.sequence",
        "password change followed by successful login within 5 minutes",
    ),
]

LEGACY_PLAN: dict[str, Any] = {
    "detection_family": "ot_modbus_unauthorized_write",
    "data_domain": "ot_network",
    "time_window_hours": 24,
    "filters": [{"field": "protocol", "match": "modbus"}],
    "group_by": ["src_ip", "dest_ip"],
    "metric": "count",
}


def _stable_dumps(obj: Any) -> str:
    return json.dumps(obj, indent=2, sort_keys=True, default=str) + "\n"


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _validation_fields(spl: str | None) -> dict[str, Any]:
    from app.safeguards.spl_validator import validate_spl

    if not spl:
        return {
            "approved": False,
            "normalized_spl": None,
            "execution_eligible": False,
        }
    raw = validate_spl(spl)
    d = raw if isinstance(raw, dict) else raw.model_dump()
    elig = d.get("execution_eligible")
    return {
        "approved": bool(d.get("approved")),
        "normalized_spl": d.get("normalized_spl"),
        "execution_eligible": bool(elig) if elig is not None else False,
    }


def build_artifact() -> dict[str, Any]:
    from app.spl.llm_plan_compiler import compile_intent_spec_to_spl, compile_plan_to_spl
    from app.spl.spl_intent_spec import build_spl_intent_spec

    rows: list[dict[str, Any]] = []

    templates = json.loads(TEMPLATES_PATH.read_text(encoding="utf-8"))["templates"]
    for t in templates:
        spl = t.get("spl_text") or ""
        if not spl:
            continue
        fields = _validation_fields(spl)
        rows.append(
            {
                "row_id": f"tpl.{t['template_id']}",
                "bank": "spl_golden",
                "producer_path": "template",
                "candidate_spl": spl,
                **fields,
            }
        )

    for row_id, query in INTENT_SHAPES:
        spl = compile_intent_spec_to_spl(build_spl_intent_spec(query))
        fields = _validation_fields(spl)
        rows.append(
            {
                "row_id": row_id,
                "bank": "spl_golden",
                "producer_path": "plan_compiler",
                "candidate_spl": spl,
                **fields,
            }
        )

    legacy_spl = compile_plan_to_spl(LEGACY_PLAN)
    fields = _validation_fields(legacy_spl)
    rows.append(
        {
            "row_id": "compiler.plan.ot_modbus_unauthorized_write",
            "bank": "spl_golden",
            "producer_path": "plan_compiler",
            "candidate_spl": legacy_spl,
            **fields,
        }
    )

    convergence = json.loads(CONVERGENCE_BANK_PATH.read_text(encoding="utf-8"))
    for r in convergence["rows"]:
        pins = r.get("pins") or {}
        elig_pin = pins.get("candidate_spl_execution_eligible")
        rows.append(
            {
                "row_id": r["row_id"],
                "bank": "convergence",
                "producer_path": "convergence_pin",
                "family": r.get("family"),
                "candidate_spl": None,
                "approved": False,
                "normalized_spl": None,
                # Ceiling from pin when present; otherwise false (never invent true).
                "execution_eligible": bool(elig_pin) if elig_pin is not None else False,
                "pins_execution_eligible": elig_pin,
            }
        )

    rows.sort(key=lambda r: (r["bank"], r["row_id"]))
    return {
        "authority_contract": {
            "approved": "IDENTICAL",
            "execution_eligible": "ONE_WAY_TIGHTEN_CEILING",
            "normalized_spl": (
                "IDENTICAL_FOR_PASS_AND_NO_SAFE_OPTIMIZATION__"
                "OPTIMIZED_MAY_DIFF_UNDER_GUARD"
            ),
        },
        "base_sha": BASE_SHA,
        "freeze_id": "spl_optimization_authority_baseline_v1",
        "notes": (
            "advisory_count / findings / provenance keys are expected to change; "
            "approved must stay identical; execution_eligible may only tighten "
            "(true→false enumerated); normalized_spl identity for "
            "PASS/NO_SAFE_OPTIMIZATION rows."
        ),
        "row_count": len(rows),
        "rows": rows,
        "schema_version": 1,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--freeze", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if not args.freeze and not args.check:
        parser.error("pass --freeze or --check")

    artifact = build_artifact()
    text = _stable_dumps(artifact)
    digest = _sha256_text(text)

    if args.freeze:
        OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        OUT_PATH.write_text(text, encoding="utf-8")
        print(f"froze {OUT_PATH.relative_to(ROOT)} rows={artifact['row_count']} sha256={digest}")
        return 0

    if not OUT_PATH.is_file():
        print(f"MISSING {OUT_PATH}", file=sys.stderr)
        return 2
    existing = OUT_PATH.read_text(encoding="utf-8")
    if existing != text:
        print("DRIFT: regenerating freeze is not byte-identical to committed artifact", file=sys.stderr)
        print(f"committed_sha256={_sha256_text(existing)}", file=sys.stderr)
        print(f"regen_sha256={digest}", file=sys.stderr)
        return 1
    print(f"OK byte-identical rows={artifact['row_count']} sha256={digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
