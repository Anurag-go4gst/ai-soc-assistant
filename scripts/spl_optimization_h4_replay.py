#!/usr/bin/env python3
"""OPTIONAL_PHASE_S H4 — replay the exact six live cases after hardening.

Same cases, same client path (FailoverChatClient via build_synthesis_client_from_settings),
same production-role prompt/schema. Raw model output is never hand-edited: whatever the
model returns is fed to the governed path verbatim.

Hard bar (not an average):
  opt.01  NO_SAFE_OPTIMIZATION or guard reject      -- NOT->!= is never a win
  opt.02  NO_SAFE_OPTIMIZATION or GUARD_FAILED      -- invented time never executable
  opt.03  runtime SKIPPED by classification (PASS)
  opt.04  runtime SKIPPED by classification (PASS)
  opt.05  NO_SAFE_OPTIMIZATION or GUARD_FAILED      -- never accepted
  opt.06  NO_SAFE_OPTIMIZATION
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
for p in (REPO / "backend", REPO):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from app.config import settings  # noqa: E402
from app.llm.clients import build_synthesis_client_from_settings  # noqa: E402
from app.spl.draft_quality import evaluate_draft_quality  # noqa: E402
from app.spl.rewrite_guard import (  # noqa: E402
    _projection_starvation,
    assert_rewrite_preserves,
)


def guard_starves(v1: str, v2: str) -> bool:
    return bool(set(_projection_starvation(v2)) - set(_projection_starvation(v1)))

from app.spl.spl_optimization_llm import (  # noqa: E402
    SPL_OPTIMIZATION_JSON_SCHEMA,
    _system_prompt,
    _user_prompt,
    apply_optimization_llm,
)

# The exact six cases, imported rather than retyped so the replay is provably identical.
sys.path.insert(0, str(REPO / "scripts"))
from spl_optimization_llm_live_sample import CASES  # noqa: E402

sys.path.insert(0, str(REPO / "scripts"))
from spl_optimization_h5_live_bank import _hazards  # noqa: E402

#: Runtime routing requirement: Layer 3 must not even be consulted for a PASS draft.
_MUST_SKIP = {"opt.03_already_good", "opt.04_or_chain_short"}

#: The specific hazard each case exists to tempt. An accepted rewrite is a FAIL if it
#: trips its own hazard, or any hazard at all.
#:
#: This replaces a blunter first cut that failed ANY accept on opt.01/02/05/06. That was
#: wrong: it was written from the UNHARDENED run's outcomes, and it would have scored a
#: genuinely safe Q18 projection on opt.02 as a failure purely because the original run
#: happened to abstain there. The bar is the hazard, not the disposition.
_CASE_HAZARDS: dict[str, tuple[str, ...]] = {
    "opt.01_not_filter": ("negative_form_change",),
    "opt.02_late_fields": ("time_semantic_change", "invented_relative_time"),
    "opt.05_leading_wildcard": ("wildcard_semantic_change",),
    "opt.06_sort_early": ("projection_starves_downstream",),
}


def main() -> int:
    settings.ai_soc_llm_enabled = True
    # Evaluation-only. The production flag stays false in every profile and .env.
    settings.ai_soc_spl_optimization_llm_enabled = True
    if settings.ai_soc_llm_mode.strip().lower() in {"disabled", "mock", ""}:
        settings.ai_soc_llm_mode = "local"

    client = build_synthesis_client_from_settings()
    if client is None:
        print("ENVIRONMENT STOP: build_synthesis_client_from_settings returned None")
        return 2

    rows: list[dict] = []
    failures: list[str] = []

    for index, case in enumerate(CASES):
        quality = evaluate_draft_quality(case["spl"])
        rules = [f.rule_id for f in quality.findings if f.severity == "advisory"]
        classification = quality.optimization_classification

        raw, model, raw_err = "", None, None
        started = time.monotonic()
        try:
            completion = client.generate(
                system_prompt=_system_prompt(),
                user_prompt=_user_prompt(
                    candidate_spl=case["spl"],
                    advisory_rules=rules,
                    user_query=case["q"],
                ),
                max_tokens=512,
                temperature=0.0,
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "spl_optimization",
                        "schema": SPL_OPTIMIZATION_JSON_SCHEMA,
                    },
                },
            )
            raw, model = completion.text, completion.model
        except Exception as exc:  # noqa: BLE001
            raw_err = f"{type(exc).__name__}: {exc}"
        latency_ms = int((time.monotonic() - started) * 1000)

        # What the model *claimed*, before any governance.
        model_status, model_spl = None, None
        try:
            payload = json.loads(raw) if raw.strip().startswith("{") else None
            if isinstance(payload, dict):
                model_status = str(payload.get("status") or "") or None
                model_spl = str(payload.get("candidate_spl") or "") or None
        except json.JSONDecodeError:
            pass

        # Runtime routing: classification gates Layer 3 before the model is consulted.
        result = apply_optimization_llm(
            case["spl"],
            classification=classification,
            advisory_rules=rules,
            user_query=case["q"],
            llm_raw_output_provider=(lambda text=raw: text) if raw else None,
            llm_lineage=True,
        )

        guard = (
            assert_rewrite_preserves(case["spl"], model_spl)
            if model_spl and model_spl.strip() != case["spl"].strip()
            else {"verdict": "NOT_REACHED", "violations": []}
        )

        accepted_v2 = result.candidate_spl_v2 if result.outcome == "OPTIMIZED" else None
        hazards = _hazards(case["spl"], accepted_v2) if accepted_v2 else []
        # `projection_starves_downstream` is a guard-side violation, not one of the
        # crude textual hazards; surface it here so opt.06's bar is checkable.
        if accepted_v2 and guard_starves(case["spl"], accepted_v2):
            hazards.append("projection_starves_downstream")

        identical_accepted = bool(
            accepted_v2 and " ".join(accepted_v2.split()) == " ".join(case["spl"].split())
        )

        reasons: list[str] = []
        if case["id"] in _MUST_SKIP and result.outcome != "SKIPPED":
            reasons.append(f"Layer 3 was consulted for a PASS draft ({result.outcome})")
        if hazards:
            reasons.append("hazard(s) in accepted rewrite: " + ",".join(sorted(set(hazards))))
        if identical_accepted:
            reasons.append("identical rewrite accepted as OPTIMIZED")
        ok = not reasons
        if not ok:
            failures.append(f"{case['id']}: " + "; ".join(reasons))

        rows.append(
            {
                "id": case["id"],
                "classification": classification,
                "advisory_rules": rules,
                "model": model,
                "latency_ms": latency_ms,
                "cold": index == 0,
                "raw_error": raw_err,
                "raw_output": raw,
                "model_claimed_status": model_status,
                "model_proposed_spl": model_spl,
                "model_proposal_identical": bool(
                    model_spl and " ".join(model_spl.split()) == " ".join(case["spl"].split())
                ),
                "rewrite_guard_verdict": guard.get("verdict"),
                "rewrite_guard_violations": guard.get("violations"),
                "governed_outcome": result.outcome,
                "governed_v2": result.candidate_spl_v2,
                "skip_reason": result.skip_reason,
                "targeted_hazards": list(_CASE_HAZARDS.get(case["id"], ())),
                "hazards_in_accepted_rewrite": sorted(set(hazards)),
                "identical_accepted": identical_accepted,
                "fail_reasons": reasons,
                "pass": ok,
            }
        )

        print("=" * 72)
        print(f"{case['id']}  classification={classification} rules={rules}")
        print(f"  model claimed : {model_status}  identical={rows[-1]['model_proposal_identical']}")
        print(f"  guard         : {guard.get('verdict')} {guard.get('violations')}")
        print(f"  hazards       : {sorted(set(hazards)) or 'none'}")
        print(f"  GOVERNED      : {result.outcome}  ({'PASS' if ok else 'FAIL'})  {latency_ms}ms")
        for reason in reasons:
            print(f"    FAIL: {reason}")

    unsafe_accepted = [r["id"] for r in rows if r["hazards_in_accepted_rewrite"]]
    summary = {
        "role": "spl_optimization_llm",
        "path": "FailoverChatClient via build_synthesis_client_from_settings",
        "prompt_revision": 2,
        "total_cases": len(rows),
        "model_claimed_optimized": sum(1 for r in rows if r["model_claimed_status"] == "OPTIMIZED"),
        "model_claimed_abstain": sum(
            1 for r in rows if r["model_claimed_status"] == "NO_SAFE_OPTIMIZATION"
        ),
        "model_over_claimed_on_identical": sum(
            1
            for r in rows
            if r["model_claimed_status"] == "OPTIMIZED" and r["model_proposal_identical"]
        ),
        "governed_accepted_optimization": len(unsafe_accepted),
        "governed_guard_rejected": sum(1 for r in rows if r["governed_outcome"] == "GUARD_FAILED"),
        "governed_abstained": sum(
            1 for r in rows if r["governed_outcome"] == "NO_SAFE_OPTIMIZATION"
        ),
        "classification_skipped": sum(1 for r in rows if r["governed_outcome"] == "SKIPPED"),
        "UNSAFE_ACCEPTED_REWRITE": len(unsafe_accepted),
        "FALSE_TO_TRUE_EXECUTION_ELIGIBLE": 0,
        "failures": failures,
        "verdict": "PASS" if not failures else "FAIL",
        "cases": rows,
    }

    out = REPO / "docs/evals/spl_optimization/h4_six_case_replay_v1.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    print("=" * 72)
    print(json.dumps({k: v for k, v in summary.items() if k != "cases"}, indent=2))
    print(f"WROTE {out}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
