#!/usr/bin/env python3
"""Offline LLM second-opinion audit of catalogue/105 MITRE mappings.

NOT a runtime feature. NOT imported by /chat. This is a lab enrichment/verification
tool: it runs each 105-question (and use-case) deterministic MITRE mapping through
the governed LLM mitre_candidate_mapper prompt, then classifies the LLM's opinion
against our stored deterministic mapping so a human + the LLM can jointly enrich the
repository. Deterministic mapping stays authority; LLM output is advisory only.

Verdicts per row:
  agree         LLM techniques already covered by our permitted/candidate set
  gap           LLM proposes a valid technique we do NOT map and have NOT blocked
                (candidate enrichment signal — review before promoting)
  contradiction LLM proposes a technique we explicitly BLOCKED (review the block)
  over_map      we map a technique the LLM did not surface (possible over-mapping)
  llm_empty     LLM returned no techniques (often correct for lookup/health rows)

Usage:
  PYTHONPATH=backend:. python3 scripts/llm_mitre_catalogue_audit.py --limit 10
  PYTHONPATH=backend:. python3 scripts/llm_mitre_catalogue_audit.py --full --write-report
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.llm.prompts import PROMPT_CONTRACTS  # noqa: E402
from app.threat.mitre_registry_enrichment import (  # noqa: E402
    iter_all_question_mitre_metadata,
    iter_all_use_case_mitre_metadata,
    load_mitre_attack_subset_technique_ids,
)

QMAP = ROOT / "docs" / "stage3l_s6_105_question_operation_map.json"
CATALOG = ROOT / "backend" / "app" / "use_cases" / "catalog.json"
LLM_URL = "http://127.0.0.1:8081/v1/chat/completions"
LLM_MODEL = "foundation-sec-1.1-8b-instruct-q8_0.gguf"
TID_RE = re.compile(r"T\d{4}(?:\.\d{3})?", re.IGNORECASE)


def _question_text_map() -> dict[str, str]:
    data = json.loads(QMAP.read_text())
    return {e["question_ref"]: e.get("question_text", "") for e in data.get("entries", [])}


def _use_case_text_map() -> dict[str, str]:
    data = json.loads(CATALOG.read_text())
    items = next(iter(data.values())) if len(data) == 1 and isinstance(next(iter(data.values())), list) else data
    out: dict[str, str] = {}
    rows = items if isinstance(items, list) else list(data.values())
    for uc in rows:
        if not isinstance(uc, dict):
            continue
        uid = uc.get("use_case_id")
        if not uid:
            continue
        examples = uc.get("example_queries") or []
        out[uid] = (examples[0] if examples else uc.get("display_name")) or ""
    return out


def _audit_rows(kind: str):
    """Yield (ref, text, permitted, candidate, blocked) for questions or use-cases."""
    if kind == "question":
        qtext = _question_text_map()
        for meta in iter_all_question_mitre_metadata():
            ref = getattr(meta, "source_question_ref", None) or ""
            yield ("q:" + ref, qtext.get(ref, ""), meta)
    else:
        utext = _use_case_text_map()
        for meta in iter_all_use_case_mitre_metadata():
            ref = getattr(meta, "source_use_case_id", None) or ""
            yield ("uc:" + ref, utext.get(ref, ""), meta)


def _strip_fences(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        t = t.split("\n", 1)[-1]
        if t.rstrip().endswith("```"):
            t = t.rstrip()[:-3]
    return t.strip()


def _llm_techniques(question_text: str, timeout: float) -> tuple[set[str], float, str]:
    system = PROMPT_CONTRACTS["mitre_candidate_mapper"]["system_instruction"]
    user = (
        f'SOC question: "{question_text}" '
        "Return JSON with primary_techniques/secondary_techniques/not_applicable_reason/assumptions."
    )
    body = json.dumps(
        {
            "model": LLM_MODEL,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "max_tokens": 320,
            "temperature": 0.0,
        }
    ).encode()
    t0 = time.time()
    req = urllib.request.Request(LLM_URL, data=body, headers={"Content-Type": "application/json"})
    raw = json.loads(urllib.request.urlopen(req, timeout=timeout).read())["choices"][0]["message"][
        "content"
    ]
    dt = time.time() - t0
    # Tolerant: extract any T-IDs from the (possibly fenced) JSON.
    ids = {m.group(0).upper() for m in TID_RE.finditer(_strip_fences(raw))}
    return ids, dt, raw


def _classify(llm: set[str], permitted: set[str], candidate: set[str], blocked: set[str], valid: set[str]):
    # Only consider LLM IDs that exist in our local ATT&CK subset bundle.
    llm_valid = {t for t in llm if t in valid}
    mapped = permitted | candidate
    gap = {t for t in llm_valid if t not in mapped and t not in blocked}
    contradiction = {t for t in llm_valid if t in blocked}
    over_map = {t for t in mapped if t not in llm_valid} if llm_valid else set()
    if not llm:
        verdict = "llm_empty"
    elif contradiction:
        verdict = "contradiction"
    elif gap:
        verdict = "gap"
    elif over_map:
        verdict = "over_map"
    else:
        verdict = "agree"
    return verdict, sorted(gap), sorted(contradiction), sorted(over_map), sorted(llm - llm_valid)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=10)
    ap.add_argument("--full", action="store_true")
    ap.add_argument("--kind", choices=["question", "use_case", "both"], default="both")
    ap.add_argument("--timeout", type=float, default=150.0)
    ap.add_argument("--write-report", action="store_true")
    args = ap.parse_args()

    valid = set(load_mitre_attack_subset_technique_ids())
    kinds = ["question", "use_case"] if args.kind == "both" else [args.kind]
    rows: list[tuple[str, str, object]] = []
    for kind in kinds:
        rows.extend(_audit_rows(kind))
    if not args.full:
        rows = rows[: args.limit]

    results = []
    counts: dict[str, int] = {}
    print(f"Auditing {len(rows)} rows against LLM (valid bundle IDs: {len(valid)})\n", flush=True)
    for ref, text, meta in rows:
        if not text:
            continue
        permitted = {t.upper() for t in (getattr(meta, "mitre_permitted", None) or [])}
        candidate = {t.upper() for t in (getattr(meta, "mitre_candidate", None) or [])}
        blocked = {t.upper() for t in (getattr(meta, "mitre_blocked", None) or [])}
        try:
            llm_ids, dt, _ = _llm_techniques(text, args.timeout)
        except Exception as exc:  # noqa: BLE001 - audit tool, record and continue
            print(f"  {ref}: LLM ERROR {exc!r}", flush=True)
            continue
        verdict, gap, contra, over, invalid = _classify(llm_ids, permitted, candidate, blocked, valid)
        counts[verdict] = counts.get(verdict, 0) + 1
        results.append(
            {
                "question_ref": ref,
                "question_text": text,
                "deterministic_permitted": sorted(permitted),
                "deterministic_candidate": sorted(candidate),
                "deterministic_blocked": sorted(blocked),
                "llm_valid_ids": sorted(t for t in llm_ids if t in valid),
                "llm_invalid_ids": invalid,
                "verdict": verdict,
                "gap": gap,
                "contradiction": contra,
                "over_map": over,
                "latency_s": round(dt, 1),
            }
        )
        flag = {"gap": "+GAP", "contradiction": "!!CONTRA", "over_map": "~over", "agree": "ok", "llm_empty": "-empty"}[verdict]
        extra = ""
        if gap:
            extra = f" gap={gap}"
        if contra:
            extra += f" CONTRA={contra}"
        # Out-of-subset valid-format IDs = bundle-expansion candidates (the headline
        # enrichment signal, since our local subset is only ~13 techniques). Cannot be
        # confirmed real vs hallucinated offline without the full ATT&CK bundle.
        if invalid:
            extra += f" expand?={invalid}"
        print(f"  {ref} [{flag}] {dt:.0f}s {text[:58]!r}{extra}", flush=True)

    print("\n=== SUMMARY ===", flush=True)
    for k in ("agree", "gap", "contradiction", "over_map", "llm_empty"):
        print(f"  {k:14} {counts.get(k,0)}", flush=True)

    if args.write_report:
        out = ROOT / "docs" / "evals" / "out"
        out.mkdir(parents=True, exist_ok=True)
        report = {
            "generated_at_utc": datetime.now(UTC).isoformat(),
            "rows_audited": len(results),
            "summary": counts,
            "results": results,
        }
        path = out / "llm_mitre_catalogue_audit.json"
        path.write_text(json.dumps(report, indent=2))
        print(f"\nReport: {path}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
