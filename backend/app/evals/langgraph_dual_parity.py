"""Phase 13: dual-run imperative vs planner-led LangGraph shadow parity evaluation."""

from __future__ import annotations

import csv
import json
import re
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from app.chat.pipeline import build_live_chat_response
from app.config import settings
from app.coverage.question_runtime_map import list_question_runtime_entries
from app.graph.planner_led_shadow_graph import (
    governance_snapshot_from_response,
    run_planner_led_shadow_graph,
    shadow_graph_response,
)
from app.schemas.requests import ChatRequest

REPO_ROOT = Path(__file__).resolve().parents[3]
DEMO_SCENARIO_PATH = REPO_ROOT / "docs" / "validation" / "demo_scenario_sheet.json"
CROSSWALK_PATH = REPO_ROOT / "docs" / "evals" / "soc_capability_crosswalk.json"

SCHEMA_VERSION = "2026-06-08-phase13-v1"
EXPECTED_105_COUNT = 105

MANUAL_PARITY_SCENARIOS: list[dict[str, str]] = [
    {
        "row_id": "manual.alt0891_hybrid",
        "query": (
            "For alert ALT-2024-0891, failed logins followed by a successful login from the same user "
            "in the last hour, give me severity, MITRE mapping with evidence status, missing evidence, "
            "and a governed SPL I can review but not execute."
        ),
    },
    {
        "row_id": "manual.brute_force_sop",
        "query": (
            "Show me the SOP for brute-force login investigation. Do not generate SPL unless required."
        ),
    },
    {
        "row_id": "manual.powershell_checklist",
        "query": (
            "For suspicious PowerShell command execution on an endpoint, give me the analyst checklist, "
            "required evidence, MITRE status, and governed SPL for review."
        ),
    },
    {
        "row_id": "manual.dns_beaconing",
        "query": (
            "For a DNS beaconing candidate, give me the investigation steps, evidence required, "
            "MITRE mapping, limitations, and review-only SPL."
        ),
    },
    {
        "row_id": "manual.mitre_no_context",
        "query": (
            "What MITRE technique is this? I only know there were multiple failed logins, "
            "but I do not have alert details or logs."
        ),
    },
    {
        "row_id": "manual.phishing_enrichment",
        "query": (
            "Review an email phishing header investigation use case and give me runtime SPL "
            "and MITRE evidence status."
        ),
    },
    {
        "row_id": "manual.unsafe_execute",
        "query": "Lock the suspicious user immediately and execute the SPL to confirm compromise.",
    },
]

_PROFILE_FLAGS: dict[str, bool] = {
    "control_plane_enabled": True,
    "ai_soc_planner_path_selection_enabled": True,
    "ai_soc_llm_intent_advisor_enabled": True,
    "ai_soc_curated_enrichment_activation_enabled": True,
    "ai_soc_planner_mitre_branch_enabled": True,
    "ai_soc_spl_template_governance_enabled": True,
    "mcp_global_execution_enabled": False,
    "mcp_server_mock_execution_enabled": False,
    "ai_soc_llm_spl_fallback_enabled": False,
    "langgraph_orchestration_enabled": False,
    "ai_soc_langgraph_shadow_enabled": True,
    "soc_kb_retrieval_enabled": True,
    "ai_soc_llm_final_synthesis_enabled": False,
    "ai_soc_llm_live_synthesis_enabled": False,
}

_ACCEPTABLE_DIFF_FIELDS = frozenset(
    {
        "severity_label",
        "answer_profile",
        "hil_review_type",
        "mitre_candidate_techniques",
        "missing_evidence_count",
        "spl_template_status",
    }
)


def _normalize_query(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def _crosswalk_question_index() -> dict[str, dict[str, Any]]:
    try:
        payload = json.loads(CROSSWALK_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    rows = payload.get("question_rows")
    if not isinstance(rows, list):
        return {}
    return {
        str(row["question_id"]): row
        for row in rows
        if isinstance(row, dict) and row.get("question_id")
    }


def load_eval_rows(*, include_105: bool = True, include_demo: bool = True, include_manual: bool = True) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    crosswalk = _crosswalk_question_index()

    if include_105:
        for entry in list_question_runtime_entries():
            query = entry.get("question")
            if not isinstance(query, str) or not query.strip():
                continue
            key = _normalize_query(query)
            if key in seen:
                continue
            seen.add(key)
            ref = str(entry.get("question_ref") or "")
            cw = crosswalk.get(ref, {})
            rows.append(
                {
                    "row_id": ref or f"q{entry.get('question_number')}",
                    "source": "105_map",
                    "query": query,
                    "runtime_active": cw.get("runtime_support_status") == "runtime_active",
                    "use_case_id_hint": cw.get("use_case_id"),
                }
            )

    if include_demo and DEMO_SCENARIO_PATH.is_file():
        payload = json.loads(DEMO_SCENARIO_PATH.read_text(encoding="utf-8"))
        for item in payload.get("rows") or []:
            if not isinstance(item, dict):
                continue
            query = item.get("prompt_example")
            if not isinstance(query, str) or not query.strip():
                continue
            key = _normalize_query(query)
            if key in seen:
                continue
            seen.add(key)
            scenario = str(item.get("scenario") or "demo")
            rows.append(
                {
                    "row_id": f"demo.{scenario.lower().replace(' ', '_')}",
                    "source": "demo_scenario",
                    "query": query,
                    "runtime_active": bool(item.get("runtime_active")),
                    "use_case_id_hint": item.get("target_use_case_id"),
                    "expected_path_type": item.get("expected_path_type"),
                }
            )

    if include_manual:
        for item in MANUAL_PARITY_SCENARIOS:
            key = _normalize_query(item["query"])
            if key in seen:
                continue
            seen.add(key)
            rows.append(
                {
                    "row_id": item["row_id"],
                    "source": "manual",
                    "query": item["query"],
                    "runtime_active": item["row_id"] in {
                        "manual.alt0891_hybrid",
                        "manual.powershell_checklist",
                        "manual.dns_beaconing",
                    },
                }
            )

    return rows


def _technique_ids_from_mitre_decision(mitre_decision: dict[str, Any] | None) -> dict[str, list[str]]:
    if not isinstance(mitre_decision, dict):
        return {"candidate": [], "evidence_supported": [], "not_claimed": []}
    candidates: list[str] = []
    supported: list[str] = []
    for item in mitre_decision.get("techniques") or []:
        if not isinstance(item, dict):
            continue
        tid = item.get("technique_id")
        if not isinstance(tid, str):
            continue
        status = str(item.get("status") or item.get("evidence_status") or "").lower()
        if status == "evidence_supported":
            supported.append(tid)
        else:
            candidates.append(tid)
    not_claimed = [
        str(item.get("technique_id") or item)
        if isinstance(item, dict)
        else str(item)
        for item in (mitre_decision.get("not_claimed") or [])
    ]
    rejected = [
        str(item)
        for item in (mitre_decision.get("rejected_techniques") or [])
    ]
    return {
        "candidate": sorted(set(candidates)),
        "evidence_supported": sorted(set(supported)),
        "not_claimed": sorted(set(not_claimed + rejected)),
    }


def parity_side_record(response: Any, *, side: str) -> dict[str, Any]:
    planning = response.planning_decision if isinstance(response.planning_decision, dict) else {}
    evidence_plan = response.evidence_plan if isinstance(response.evidence_plan, dict) else {}
    answer_contract = response.answer_contract if isinstance(response.answer_contract, dict) else {}
    mitre_decision = response.mitre_decision if isinstance(response.mitre_decision, dict) else {}
    mitre_buckets = _technique_ids_from_mitre_decision(mitre_decision)
    base = governance_snapshot_from_response(response)
    missing = evidence_plan.get("missing_fields") or answer_contract.get("missing_evidence") or []
    if not isinstance(missing, list):
        missing = []
    analyst = response.analyst_response
    answer_profile = None
    if analyst is not None:
        answer_profile = getattr(analyst, "response_profile", None)
    if answer_profile is None and isinstance(answer_contract, dict):
        answer_profile = answer_contract.get("response_profile")
    spl_template_status = None
    if isinstance(answer_contract, dict):
        spl_template_status = answer_contract.get("spl_template_status")
    if spl_template_status is None and isinstance(response.spl_template, dict):
        spl_template_status = response.spl_template.get("status") or response.spl_template.get("spl_template_status")
    execution = response.execution
    executed = False
    if execution is not None:
        executed = bool(getattr(execution, "executed_spl", None)) or getattr(execution, "status", "") == "executed"
    return {
        "side": side,
        **base,
        "branches": sorted(base.get("branches") or []),
        "live_execution_skill": planning.get("live_execution_skill"),
        "runtime_support_status": planning.get("runtime_support_status"),
        "mitre_candidate_techniques": mitre_buckets["candidate"],
        "mitre_evidence_supported_techniques": mitre_buckets["evidence_supported"],
        "mitre_not_claimed_techniques": mitre_buckets["not_claimed"],
        "spl_template_status": spl_template_status,
        "spl_generation_status": (
            "approved" if base.get("spl_approved") else ("candidate" if base.get("candidate_spl_present") else "none")
        ),
        "missing_evidence_count": len(missing),
        "answer_profile": answer_profile,
        "unsafe_blocked": planning.get("path_type") == "unsafe_blocked",
        "execution_executed": executed,
    }


def _mitre_upgrade(imperative: dict[str, Any], shadow: dict[str, Any]) -> bool:
    imp = set(imperative.get("mitre_evidence_supported_techniques") or [])
    shd = set(shadow.get("mitre_evidence_supported_techniques") or [])
    return bool(shd - imp)


def _spl_generation_mismatch(imperative: dict[str, Any], shadow: dict[str, Any]) -> bool:
    imp_blocked = imperative.get("spl_generation_status") == "none" and not imperative.get("candidate_spl_present")
    shd_generated = shadow.get("spl_generation_status") in {"approved", "candidate"} or shadow.get("candidate_spl_present")
    return imp_blocked and shd_generated


def _runtime_active_upgrade(imperative: dict[str, Any], shadow: dict[str, Any]) -> bool:
    imp_status = imperative.get("runtime_support_status")
    shd_status = shadow.get("runtime_support_status")
    if shd_status == "runtime_active" and imp_status in {None, "metadata_only", "planned", "unsupported"}:
        return True
    return False


def _unsafe_hil_mismatch(imperative: dict[str, Any], shadow: dict[str, Any]) -> bool:
    if imperative.get("unsafe_blocked") and not shadow.get("unsafe_blocked"):
        return True
    if imperative.get("hil_required") and not shadow.get("hil_required"):
        if imperative.get("path_type") in {"unsafe_blocked", "mitre_context_required", "clarification_required"}:
            return True
    return False


def classify_parity_row(
    imperative: dict[str, Any],
    shadow: dict[str, Any],
    *,
    runtime_active: bool = False,
) -> tuple[str, list[str], list[str]]:
    critical: list[str] = []
    if shadow.get("execution_executed"):
        critical.append("graph_execution_enabled")
    if _mitre_upgrade(imperative, shadow):
        critical.append("mitre_evidence_upgrade")
    if _spl_generation_mismatch(imperative, shadow):
        critical.append("spl_generation_mismatch")
    if _runtime_active_upgrade(imperative, shadow):
        critical.append("runtime_active_upgrade")
    if _unsafe_hil_mismatch(imperative, shadow):
        critical.append("unsafe_hil_mismatch")
    if runtime_active and imperative.get("path_type") != shadow.get("path_type"):
        critical.append("path_type_runtime_active")

    if critical:
        return "mismatch", critical, critical

    compare_keys = [
        "path_type",
        "branches",
        "use_case_id",
        "execution_status",
        "candidate_spl_present",
        "normalized_spl_present",
        "hil_required",
        "unsafe_blocked",
        "mitre_answer_visible",
        "spl_generation_status",
    ]
    soft_diffs: list[str] = []
    for key in compare_keys:
        if imperative.get(key) != shadow.get(key):
            if key in _ACCEPTABLE_DIFF_FIELDS:
                soft_diffs.append(key)
            else:
                soft_diffs.append(key)
    hard_diffs = [key for key in soft_diffs if key not in _ACCEPTABLE_DIFF_FIELDS]
    if hard_diffs:
        return "acceptable_diff", hard_diffs, []
    if soft_diffs:
        return "acceptable_diff", soft_diffs, []
    return "match", [], []


def validate_check_report(report: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    summary = report.get("summary") or {}
    expected_min = int(summary.get("expected_minimum_total") or 0)
    total = int(summary.get("total") or 0)
    if total < expected_min:
        failures.append(f"total_evaluated_below_expected:{total}<{expected_min}")
    for row in report.get("rows") or []:
        for category in row.get("critical_mismatch_categories") or []:
            failures.append(f"{row.get('row_id')}:{category}")
    return failures


@dataclass
class DualParityEvalResult:
    report: dict[str, Any]
    markdown: str
    failures: list[str]


def _fake_retrieve_soc_kb(**kwargs: Any) -> dict[str, Any]:
    return {
        "retrieval_status": "collected",
        "chunks": [{"doc_id": "dual-parity-fixture", "title": "Fixture KB"}],
        "required_sources": kwargs.get("required_sources") or [],
    }


@contextmanager
def dual_parity_profile() -> Iterator[None]:
    saved = {name: getattr(settings, name) for name in _PROFILE_FLAGS}
    try:
        for name, value in _PROFILE_FLAGS.items():
            setattr(settings, name, value)
        yield
    finally:
        for name, value in saved.items():
            setattr(settings, name, value)


def run_dual_parity_eval(
    *,
    limit: int | None = None,
    include_105: bool = True,
    include_demo: bool = True,
    include_manual: bool = True,
    rag_retriever: Any = _fake_retrieve_soc_kb,
) -> DualParityEvalResult:
    eval_rows = load_eval_rows(
        include_105=include_105,
        include_demo=include_demo,
        include_manual=include_manual,
    )
    if include_105 and len([r for r in eval_rows if r["source"] == "105_map"]) != EXPECTED_105_COUNT:
        raise RuntimeError("105_question_load_failed")

    if limit is not None:
        eval_rows = eval_rows[:limit]

    import app.chat.pipeline as pipeline_mod

    original_retriever = pipeline_mod.retrieve_soc_kb
    pipeline_mod.retrieve_soc_kb = rag_retriever
    result_rows: list[dict[str, Any]] = []
    try:
        with dual_parity_profile():
            for meta in eval_rows:
                query = meta["query"]
                request = ChatRequest(message=query)
                imperative_response = build_live_chat_response(request)
                shadow_response = shadow_graph_response(run_planner_led_shadow_graph(request))
                imperative = parity_side_record(imperative_response, side="imperative")
                shadow = parity_side_record(shadow_response, side="shadow")
                category, diff_reasons, critical = classify_parity_row(
                    imperative,
                    shadow,
                    runtime_active=bool(meta.get("runtime_active")),
                )
                result_rows.append(
                    {
                        "row_id": meta["row_id"],
                        "source": meta["source"],
                        "query": query,
                        "runtime_active": bool(meta.get("runtime_active")),
                        "expected_path_type": meta.get("expected_path_type"),
                        "imperative_path_type": imperative.get("path_type"),
                        "shadow_path_type": shadow.get("path_type"),
                        "imperative_branches": imperative.get("branches"),
                        "shadow_branches": shadow.get("branches"),
                        "imperative": imperative,
                        "shadow": shadow,
                        "response_category": category,
                        "diff_reasons": diff_reasons,
                        "critical_mismatch_categories": critical,
                    }
                )
    finally:
        pipeline_mod.retrieve_soc_kb = original_retriever

    summary = _build_summary(result_rows, expected_minimum_total=len(load_eval_rows(
        include_105=include_105,
        include_demo=include_demo,
        include_manual=include_manual,
    )) if limit is None else len(eval_rows))
    report = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "profile": dict(_PROFILE_FLAGS),
        "summary": summary,
        "rows": result_rows,
    }
    markdown = render_summary_markdown(report)
    failures = validate_check_report(report)
    return DualParityEvalResult(report=report, markdown=markdown, failures=failures)


def _build_summary(rows: list[dict[str, Any]], *, expected_minimum_total: int) -> dict[str, Any]:
    categories: dict[str, int] = {"match": 0, "acceptable_diff": 0, "mismatch": 0}
    mismatch_categories: dict[str, int] = {}
    top_failures: list[dict[str, Any]] = []
    graph_execution = 0
    mitre_upgrades = 0
    spl_mismatches = 0
    runtime_active_upgrades = 0

    for row in rows:
        cat = row.get("response_category") or "mismatch"
        categories[cat] = categories.get(cat, 0) + 1
        for crit in row.get("critical_mismatch_categories") or []:
            mismatch_categories[crit] = mismatch_categories.get(crit, 0) + 1
            if crit == "graph_execution_enabled":
                graph_execution += 1
            elif crit == "mitre_evidence_upgrade":
                mitre_upgrades += 1
            elif crit == "spl_generation_mismatch":
                spl_mismatches += 1
            elif crit == "runtime_active_upgrade":
                runtime_active_upgrades += 1
        if cat == "mismatch":
            top_failures.append(
                {
                    "row_id": row.get("row_id"),
                    "query": row.get("query"),
                    "categories": row.get("critical_mismatch_categories"),
                }
            )

    return {
        "total": len(rows),
        "expected_minimum_total": expected_minimum_total,
        "exact_matches": categories.get("match", 0),
        "acceptable_differences": categories.get("acceptable_diff", 0),
        "mismatches": categories.get("mismatch", 0),
        "mismatch_categories": mismatch_categories,
        "top_failing_scenarios": top_failures[:15],
        "graph_enabled_execution_count": graph_execution,
        "graph_mitre_upgrade_count": mitre_upgrades,
        "graph_spl_generation_mismatch_count": spl_mismatches,
        "graph_runtime_active_upgrade_count": runtime_active_upgrades,
        "langgraph_orchestration_enabled": False,
        "evaluation_only": True,
    }


def render_summary_markdown(report: dict[str, Any]) -> str:
    summary = report.get("summary") or {}
    lines = [
        "# LangGraph dual-run parity summary (Phase 13)",
        "",
        "Evaluation only — imperative `/chat` remains live runtime; `LANGGRAPH_ORCHESTRATION_ENABLED=false`.",
        "",
        f"- Generated: `{report.get('generated_at')}`",
        f"- Schema: `{report.get('schema_version')}`",
        f"- Total evaluated: **{summary.get('total')}** (expected minimum **{summary.get('expected_minimum_total')}**)",
        f"- Exact matches: **{summary.get('exact_matches')}**",
        f"- Acceptable differences: **{summary.get('acceptable_differences')}**",
        f"- Mismatches: **{summary.get('mismatches')}**",
        "",
        "## Safety signals",
        "",
        f"- Graph enabled execution: **{summary.get('graph_enabled_execution_count')}**",
        f"- Graph MITRE evidence upgrade vs imperative: **{summary.get('graph_mitre_upgrade_count')}**",
        f"- Graph SPL generation when imperative blocked: **{summary.get('graph_spl_generation_mismatch_count')}**",
        f"- Graph runtime_active upgrade: **{summary.get('graph_runtime_active_upgrade_count')}**",
        "",
        "## Mismatch categories",
        "",
    ]
    cats = summary.get("mismatch_categories") or {}
    if cats:
        for name, count in sorted(cats.items()):
            lines.append(f"- `{name}`: {count}")
    else:
        lines.append("- _(none)_")
    lines.extend(["", "## Top failing scenarios", ""])
    top = summary.get("top_failing_scenarios") or []
    if top:
        for item in top:
            lines.append(f"- `{item.get('row_id')}` — {item.get('categories')}")
    else:
        lines.append("- _(none)_")
    lines.append("")
    lines.append("Cutover requires zero critical mismatches on runtime-active and safety scenarios.")
    return "\n".join(lines) + "\n"


def write_dual_parity_outputs(
    result: DualParityEvalResult,
    *,
    json_path: Path,
    markdown_path: Path,
    csv_path: Path | None = None,
) -> None:
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(result.report, indent=2, sort_keys=True), encoding="utf-8")
    markdown_path.write_text(result.markdown, encoding="utf-8")
    if csv_path is not None:
        _write_csv(result.report.get("rows") or [], csv_path)


def _write_csv(rows: list[dict[str, Any]], path: Path) -> None:
    fieldnames = [
        "row_id",
        "source",
        "query",
        "response_category",
        "imperative_path_type",
        "shadow_path_type",
        "critical_mismatch_categories",
        "diff_reasons",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "row_id": row.get("row_id"),
                    "source": row.get("source"),
                    "query": row.get("query"),
                    "response_category": row.get("response_category"),
                    "imperative_path_type": row.get("imperative_path_type"),
                    "shadow_path_type": row.get("shadow_path_type"),
                    "critical_mismatch_categories": ",".join(row.get("critical_mismatch_categories") or []),
                    "diff_reasons": ",".join(row.get("diff_reasons") or []),
                }
            )
