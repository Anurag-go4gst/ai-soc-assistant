#!/usr/bin/env python3
"""Live sample: OPTIONAL_PHASE_S Layer 3 optimization LLM (prompt sensitivity).

Run outside pytest. Shows raw model text + parsed outcome for closed cases.
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
from app.spl.spl_optimization_llm import (  # noqa: E402
    _system_prompt,
    _user_prompt,
    apply_optimization_llm,
)

CASES = [
    {
        "id": "opt.01_not_filter",
        "q": "Failed auth events excluding successes",
        "spl": (
            "search index=<auth_index> sourcetype=<auth_sourcetype> earliest=-24h latest=now "
            "NOT status=success | stats count by src_ip user | sort -count | head 100"
        ),
        "expect_note": "Q03-style NOT — model may rewrite to positive filter or abstain",
    },
    {
        "id": "opt.02_late_fields",
        "q": "Top src_ip by failed logons last hour",
        "spl": (
            "search index=<auth_index> sourcetype=<auth_sourcetype> earliest=-1h latest=now "
            "action=failure | eval noise=1 | stats count by src_ip | sort -count | head 100"
        ),
        "expect_note": "early projection / drop unused eval — safe OPTIMIZED likely",
    },
    {
        "id": "opt.03_already_good",
        "q": "Top src_ip by failed logons last hour",
        "spl": (
            "search index=<auth_index> sourcetype=<auth_sourcetype> earliest=-1h latest=now "
            "action=failure | stats count by src_ip | sort -count | head 100"
        ),
        "expect_note": "already efficient — should abstain NO_SAFE_OPTIMIZATION",
    },
    {
        "id": "opt.04_or_chain_short",
        "q": "Privileged group changes",
        "spl": (
            "search index=<windows_index> sourcetype=<windows_security_sourcetype> earliest=-6h latest=now "
            "(EventCode=4728 OR EventCode=4732 OR EventCode=4756) | stats count by user | head 100"
        ),
        "expect_note": "short OR — may IN() or abstain; must not invent EventCodes",
    },
    {
        "id": "opt.05_leading_wildcard",
        "q": "IT to OT allows",
        "spl": (
            "search index=<fw_index> sourcetype=<fw_sourcetype> earliest=-24h latest=now "
            "(*it* OR *ot*) action=allowed | stats count by src_ip dest_ip | head 100"
        ),
        "expect_note": "Q16 leading wildcards — must NOT invent zone values; abstain preferred",
    },
    {
        "id": "opt.06_sort_early",
        "q": "Auth failures ranked",
        "spl": (
            "search index=<auth_index> sourcetype=<auth_sourcetype> earliest=-24h latest=now "
            "action=failure | sort -_time | stats count by user | head 100"
        ),
        "expect_note": "Q17 non-streaming early — may move sort after stats or abstain",
    },
]


def main() -> int:
    settings.ai_soc_llm_enabled = True
    settings.ai_soc_spl_optimization_llm_enabled = True
    if settings.ai_soc_llm_mode.strip().lower() in {"disabled", "mock", ""}:
        settings.ai_soc_llm_mode = "local"

    client = build_synthesis_client_from_settings()
    if client is None:
        print("NO_CLIENT: build_synthesis_client_from_settings returned None")
        return 2

    print("=== Layer 3 SYSTEM PROMPT ===")
    print(_system_prompt())
    print()

    rows = []
    for i, case in enumerate(CASES):
        quality = evaluate_draft_quality(case["spl"])
        rules = [f.rule_id for f in quality.findings if f.severity == "advisory"]
        classification = quality.optimization_classification
        user = _user_prompt(
            candidate_spl=case["spl"],
            advisory_rules=rules,
            user_query=case["q"],
        )

        # Raw call (see exact model text — prompt sensitivity)
        t0 = time.monotonic()
        try:
            completion = client.generate(
                system_prompt=_system_prompt(),
                user_prompt=user,
                max_tokens=512,
                temperature=0.0,
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "spl_optimization",
                        "schema": {
                            "type": "object",
                            "properties": {
                                "status": {
                                    "type": "string",
                                    "enum": ["OPTIMIZED", "NO_SAFE_OPTIMIZATION"],
                                },
                                "candidate_spl": {"type": "string"},
                            },
                            "required": ["status"],
                        },
                    },
                },
            )
            raw = completion.text
            model = completion.model
            raw_ms = int((time.monotonic() - t0) * 1000)
            raw_err = None
        except Exception as exc:  # noqa: BLE001
            raw = ""
            model = None
            raw_ms = int((time.monotonic() - t0) * 1000)
            raw_err = f"{type(exc).__name__}: {exc}"

        # Governed apply path (guard + classification gate)
        result = apply_optimization_llm(
            case["spl"],
            classification=classification,
            advisory_rules=rules,
            user_query=case["q"],
            llm_raw_output_provider=(lambda text=raw: text) if raw else None,
            llm_lineage=True,
        )

        row = {
            "id": case["id"],
            "expect_note": case["expect_note"],
            "classification": classification,
            "advisory_rules": rules,
            "raw_latency_ms": raw_ms,
            "model": model,
            "raw_error": raw_err,
            "raw_output": raw,
            "governed_outcome": result.outcome,
            "v2": result.candidate_spl_v2,
            "skip_reason": result.skip_reason,
            "cold": i == 0,
        }
        rows.append(row)

        print("=" * 72)
        print(f"CASE {case['id']}  classification={classification} rules={rules}")
        print(f"NOTE: {case['expect_note']}")
        print(f"RAW latency={raw_ms}ms model={model} cold={i == 0}")
        if raw_err:
            print(f"RAW ERROR: {raw_err}")
        print("--- RAW MODEL OUTPUT ---")
        print(raw or "(empty)")
        print("--- GOVERNED ---")
        print(f"outcome={result.outcome} skip={result.skip_reason}")
        if result.candidate_spl_v2:
            print("v2:", result.candidate_spl_v2)
        print()

    out = REPO / "docs" / "evals" / "spl_optimization" / "s6_live_sample_prompt_sensitivity_v1.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "role": "spl_optimization_llm",
        "path": "build_synthesis_client_from_settings (same as Layer 3 apply)",
        "note": "Not registered as sidecar_clients timeout role; uses synthesis client.",
        "cases": rows,
    }
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"WROTE {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
