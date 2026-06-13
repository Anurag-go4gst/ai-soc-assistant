#!/usr/bin/env python3
"""Offline LLM template cross-check (SPL audit Phase F).

Critiques active governed templates against their use-case intent. Deterministic
checks always run; optional live LLM critique is gated by
`AI_SOC_TESTS_ALLOW_LIVE_LLM=1`. Never imported by `/chat`.

Usage:
    PYTHONPATH=backend:. python3 scripts/llm_template_audit.py
    PYTHONPATH=backend:. python3 scripts/llm_template_audit.py --live-llm
    PYTHONPATH=backend:. python3 scripts/llm_template_audit.py --write-report
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
CATALOG_PATH = BACKEND / "app" / "use_cases" / "catalog.json"
REPORT_MD = ROOT / "docs" / "evals" / "llm_template_audit_report.md"

from app.safeguards.spl_validator import validate_spl  # noqa: E402
from app.spl.policy import SplValidationPolicy, load_spl_policy  # noqa: E402
from app.spl.spl_relevance_check import check_spl_relevance  # noqa: E402
from app.spl.template_registry import load_spl_templates  # noqa: E402


def _active_templates() -> list[dict[str, Any]]:
    templates: list[dict[str, Any]] = []
    for template in load_spl_templates():
        if template.status != "active" or not (template.spl_text or "").strip():
            continue
        templates.append(template.model_dump())
    return templates


def _use_case_lookup() -> dict[str, dict[str, Any]]:
    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    rows = catalog.get("use_cases") or catalog
    if isinstance(rows, list):
        return {str(row.get("use_case_id")): row for row in rows if row.get("use_case_id")}
    return {}


def _pipe_count(spl: str) -> int:
    return spl.count("|")


def _policy_for_template(template: dict[str, Any]) -> SplValidationPolicy:
    base = load_spl_policy()
    rules = template.get("validation_rules") or {}

    def _tuple_field(key: str, fallback: tuple[str, ...]) -> tuple[str, ...]:
        raw = rules.get(key)
        if isinstance(raw, list) and raw:
            return tuple(str(item).strip().lower() for item in raw if str(item).strip())
        return fallback

    return SplValidationPolicy(
        enabled=base.enabled,
        allowed_indexes=_tuple_field("allowed_indexes", base.allowed_indexes),
        allowed_sourcetypes=_tuple_field("allowed_sourcetypes", base.allowed_sourcetypes),
        default_earliest=base.default_earliest,
        default_latest=base.default_latest,
        max_result_limit=base.max_result_limit,
        allowed_commands=_tuple_field("allowed_commands", base.allowed_commands),
        blocked_commands=base.blocked_commands,
        allow_wildcard_indexes=base.allow_wildcard_indexes,
        allow_macros=base.allow_macros,
        allow_subsearches=base.allow_subsearches,
        allow_external_calls=base.allow_external_calls,
        policy_version=base.policy_version,
    )


def _deterministic_critique(template: dict[str, Any], use_case: dict[str, Any] | None) -> dict[str, Any]:
    spl = str(template.get("spl_text") or "")
    query = ""
    required_sources: list[str] = []
    if use_case:
        query = str(use_case.get("canonical_question") or use_case.get("title") or "")
        required_sources = [str(item) for item in use_case.get("required_sources") or []]

    validation = validate_spl(spl, policy=_policy_for_template(template))
    relevance = check_spl_relevance(query or "investigation query", spl, required_sources=required_sources or None)
    findings: list[str] = []
    if not validation.get("approved"):
        findings.append(f"validation_failed:{','.join(validation.get('reject_reasons') or [])}")
    if query and not relevance.relevant:
        findings.append(f"relevance_mismatch:{','.join(relevance.mismatches)}")
    if _pipe_count(spl) > 6:
        findings.append("verbosity_high")
    required_entities = [str(item) for item in template.get("required_entities") or []]
    lowered = spl.lower()
    for entity in required_entities:
        if entity.lower() not in lowered and entity not in spl:
            findings.append(f"missing_entity:{entity}")
    blocking = [item for item in findings if not item.startswith("verbosity_high")]
    return {
        "template_id": template.get("template_id"),
        "use_case_id": template.get("use_case_id"),
        "query": query,
        "approved": bool(validation.get("approved")),
        "relevant": relevance.relevant if query else None,
        "pipe_count": _pipe_count(spl),
        "findings": findings,
        "status": "pass" if not blocking else "review",
    }


def _live_llm_critique(template: dict[str, Any], use_case: dict[str, Any] | None) -> str | None:
    if os.environ.get("AI_SOC_TESTS_ALLOW_LIVE_LLM") != "1":
        return None
    try:
        from app.llm.clients.registry import get_llm_client_for_role
    except Exception:
        return None
    client = get_llm_client_for_role("spl_advisory")
    if client is None:
        return None
    query = ""
    if use_case:
        query = str(use_case.get("canonical_question") or use_case.get("title") or "")
    prompt = (
        "Critique this governed Splunk SPL template for intent fit only. "
        "Flag wrong data source, missing entity/metric, or unnecessary verbosity. "
        f"Question: {query or 'n/a'}\n"
        f"Template: {template.get('template_id')}\n"
        f"SPL:\n{template.get('spl_text')}\n"
        "Reply with 3 short bullets."
    )
    try:
        response = client.complete(prompt)
        return str(response).strip()
    except Exception as exc:  # pragma: no cover - live path only
        return f"live_llm_unavailable:{exc}"


def run_audit(*, live_llm: bool = False) -> dict[str, Any]:
    use_cases = _use_case_lookup()
    rows: list[dict[str, Any]] = []
    for template in _active_templates():
        use_case = use_cases.get(str(template.get("use_case_id")))
        row = _deterministic_critique(template, use_case)
        if live_llm:
            row["llm_critique"] = _live_llm_critique(template, use_case)
        rows.append(row)
    passed = sum(1 for row in rows if row["status"] == "pass")
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "template_count": len(rows),
        "passed": passed,
        "review_required": len(rows) - passed,
        "rows": rows,
    }


def _render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# LLM Template Audit Report (Phase F)",
        "",
        f"Generated: {report['generated_at']}",
        f"Active templates: {report['template_count']}",
        f"Pass: {report['passed']} · Review: {report['review_required']}",
        "",
        "| template_id | use_case_id | approved | relevant | pipes | status | findings |",
        "|---|---|---:|---:|---:|---|---|",
    ]
    for row in report["rows"]:
        findings = "; ".join(row.get("findings") or []) or "—"
        relevant = "—" if row.get("relevant") is None else ("yes" if row["relevant"] else "no")
        lines.append(
            f"| {row['template_id']} | {row['use_case_id']} | "
            f"{'yes' if row['approved'] else 'no'} | {relevant} | {row['pipe_count']} | "
            f"{row['status']} | {findings} |"
        )
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Offline governed template audit")
    parser.add_argument("--live-llm", action="store_true", help="Attach optional live LLM critique")
    parser.add_argument("--write-report", action="store_true", help="Write docs/evals/llm_template_audit_report.md")
    parser.add_argument("--json", dest="json_path", default="", help="Optional JSON output path")
    args = parser.parse_args()

    report = run_audit(live_llm=args.live_llm)
    if args.json_path:
        Path(args.json_path).write_text(json.dumps(report, indent=2), encoding="utf-8")
    if args.write_report:
        REPORT_MD.parent.mkdir(parents=True, exist_ok=True)
        REPORT_MD.write_text(_render_markdown(report), encoding="utf-8")
    print(json.dumps({"template_count": report["template_count"], "passed": report["passed"], "review_required": report["review_required"]}))
    return 0 if report["review_required"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
